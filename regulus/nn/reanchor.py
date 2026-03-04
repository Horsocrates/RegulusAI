"""
Process-Based Interval Propagation (P4 Hypothesis).

Instead of propagating intervals through the entire model (exponential blowup),
split into blocks and re-anchor (collapse to midpoint + small eps) between them.

Four strategies:
  midpoint      -- always re-anchor after each block (fixed eps)
  adaptive      -- re-anchor only when width exceeds threshold
  hybrid        -- try naive first, fall back to midpoint if too wide
  proportional  -- re-anchor with fraction of current width (preserves signal)

Formal backing (PInterval_Composition.v, axiom-free):
  - pi_reanchor_width: width(reanchor(I, eps)) == 2 * eps
  - pi_reanchor_contains_midpoint: midpoint(I) in reanchor(I, eps)
  - single_block_after_reanchor: output width <= factor * (2 * eps)
  - reanchored_depth_independent: final width bounded independent of depth

CRITICAL LIMITATION (Coq-proven, pi_reanchor_loses_containment):
  Re-anchoring is LOSSY -- it does NOT preserve interval containment.
  Counterexample: I=[0,10], eps=1 => midpoint=5, reanchored=[4,6].
  The point x=0 is in I but NOT in reanchor(I, 1).

  This means: after re-anchoring, the interval is no longer GUARANTEED
  to contain the true value. The system provides NARROW MARGINS
  (controlled width) rather than END-TO-END SOUNDNESS.

  Naive (un-reanchored) IBP gives true soundness but exponential blowup.
  Re-anchored IBP gives depth-independent width at the cost of soundness.
  The "hybrid" strategy tries naive first and only sacrifices soundness
  when width exceeds a threshold.
"""

from __future__ import annotations

import numpy as np
import torch.nn as nn

from regulus.nn.interval_tensor import IntervalTensor
from regulus.nn.model import IntervalSequential, convert_model
from regulus.interval.composition import (
    LayerSpec, chain_width, factor_product, reanchored_chain_width,
    predict_block_factors, predict_optimal_eps,
)


class ReanchoredIntervalModel:
    """Interval model with periodic re-anchoring to control width blowup.

    Coq-verified properties (PInterval_Composition.v):
      - After re-anchoring with eps, output width = 2*eps (exact).
      - Through one block with width factor F, output width <= F * 2*eps.
      - Final width is bounded INDEPENDENTLY of network depth.
      - WARNING: re-anchoring breaks containment (proven negative result).
        Use "hybrid" strategy when soundness matters.

    Composition-aware mode (use_composition=True):
      - Inspects block weights to predict width amplification factors
      - Uses chain_width_product theorem to allocate per-block reanchor_eps
      - Adaptive threshold derived from composition predictions
      - Tracks predicted vs actual widths for diagnostics

    Parameters:
        torch_model: trained PyTorch nn.Sequential
        block_size: number of activation functions (ReLU/Sigmoid) per block
        reanchor_eps: half-width of new interval after re-anchoring
        strategy: 'midpoint' | 'adaptive' | 'hybrid' | 'proportional'
        adaptive_threshold: max_width trigger for adaptive re-anchoring
        shrink_factor: for proportional strategy, multiply width by this (0..1)
        use_composition: if True, use composition-predicted factors for
            adaptive eps control (chain_width_product theorem)
        target_output_width: desired output width for composition-aware mode
    """

    def __init__(
        self,
        torch_model: nn.Sequential,
        block_size: int = 1,
        reanchor_eps: float = 0.001,
        strategy: str = "midpoint",
        adaptive_threshold: float = 1.0,
        shrink_factor: float = 0.1,
        use_composition: bool = False,
        target_output_width: float = 0.5,
    ) -> None:
        self.torch_model = torch_model
        self.block_size = block_size
        self.reanchor_eps = reanchor_eps
        self.strategy = strategy
        self.adaptive_threshold = adaptive_threshold
        self.shrink_factor = shrink_factor
        self.use_composition = use_composition
        self.target_output_width = target_output_width

        # Split into blocks and convert each to interval version
        self._torch_blocks = self._split_into_blocks(torch_model, block_size)
        self.interval_blocks: list[IntervalSequential] = [
            convert_model(b) for b in self._torch_blocks
        ]

        # For hybrid: also keep the full naive model
        if strategy == "hybrid":
            self._naive_model = convert_model(torch_model)

        # Diagnostics (updated on each forward call)
        self.block_widths: list[float] = []
        self.n_reanchors: int = 0

        # Composition tracking (PInterval_Composition.v, chain_width_product)
        # Predicted factors from block weights (static analysis)
        self.layer_specs: list[LayerSpec] = predict_block_factors(
            self.interval_blocks
        )
        # Per-block adaptive eps (computed from composition predictions)
        self.composition_eps_schedule: list[float] = (
            self._compute_eps_schedule()
        )
        # Populated after forward() — predicted vs actual widths
        self.composition_predicted_widths: list[float] = []
        self.composition_factors: list[float] = []

    def _compute_eps_schedule(self) -> list[float]:
        """Compute per-block reanchor eps using composition theorem.

        For each block i (0..n-2), compute optimal eps such that the
        remaining chain (blocks i+1..n-1) will produce output width
        ≤ target_output_width.

        Uses reanchored_depth_independent:
            output_width ≤ remaining_factor_product * 2 * eps

        Returns list of eps values, one per reanchor point.
        """
        n = len(self.interval_blocks)
        eps_schedule: list[float] = []
        for i in range(n - 1):
            if self.use_composition and self.layer_specs:
                optimal = predict_optimal_eps(
                    self.layer_specs, i, self.target_output_width,
                )
                # Use the minimum of fixed eps and optimal eps
                # (never exceed fixed eps, but can be tighter)
                eps_schedule.append(min(self.reanchor_eps, optimal))
            else:
                eps_schedule.append(self.reanchor_eps)
        return eps_schedule

    @staticmethod
    def _split_into_blocks(
        torch_model: nn.Sequential, block_size: int
    ) -> list[nn.Sequential]:
        """Split torch model into blocks by counting activations.

        Each block ends after ``block_size`` activation functions
        (ReLU or Sigmoid). The final block may have fewer activations
        or none (e.g. a bare Linear output layer).

        Example for [L,R,L,R,L,R,L] with block_size=1:
            Block 0: [L,R]
            Block 1: [L,R]
            Block 2: [L,R]
            Block 3: [L]          (final, no activation)

        With block_size=2:
            Block 0: [L,R,L,R]
            Block 1: [L,R,L]      (remainder)
        """
        children = list(torch_model.children())
        blocks: list[nn.Sequential] = []
        current: list[nn.Module] = []
        activation_count = 0

        for layer in children:
            current.append(layer)
            if isinstance(layer, (nn.ReLU, nn.Sigmoid, nn.Tanh, nn.GELU, nn.ELU)):
                activation_count += 1
                if activation_count == block_size:
                    blocks.append(nn.Sequential(*current))
                    current = []
                    activation_count = 0

        if current:
            blocks.append(nn.Sequential(*current))

        return blocks

    # ------------------------------------------------------------------
    # Forward dispatch
    # ------------------------------------------------------------------

    def __call__(self, x: IntervalTensor) -> IntervalTensor:
        return self.forward(x)

    def forward(self, x: IntervalTensor) -> IntervalTensor:
        if self.strategy == "midpoint":
            return self._forward_midpoint(x)
        elif self.strategy == "adaptive":
            return self._forward_adaptive(x)
        elif self.strategy == "hybrid":
            return self._forward_hybrid(x)
        elif self.strategy == "proportional":
            return self._forward_proportional(x)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")

    # ------------------------------------------------------------------
    # Strategy 1: Midpoint re-anchoring (always)
    # ------------------------------------------------------------------

    def _forward_midpoint(self, x: IntervalTensor) -> IntervalTensor:
        """After every block (except the last), collapse to midpoint + eps.

        When use_composition=True, uses per-block eps from composition
        theorem predictions (chain_width_product / reanchored_depth_independent).

        Tracks composition width factors for diagnostics.
        """
        self.block_widths = [x.mean_width()]
        self.n_reanchors = 0
        self.composition_factors = []
        self.composition_predicted_widths = []

        current = x
        for i, block in enumerate(self.interval_blocks):
            pre_width = current.mean_width()

            # Predict output width using composition theorem BEFORE executing
            if self.use_composition and i < len(self.layer_specs):
                predicted = self.layer_specs[i].factor * pre_width
                self.composition_predicted_widths.append(predicted)
            else:
                self.composition_predicted_widths.append(0.0)

            current = block(current)
            post_width = current.mean_width()
            self.block_widths.append(post_width)

            # Track empirical width factor for this block
            # chain_width_product: chain_width == factor_product * input_width
            if pre_width > 1e-15:
                factor = post_width / pre_width
            else:
                factor = 1.0
            self.composition_factors.append(factor)

            # Re-anchor between blocks (not after final)
            if i < len(self.interval_blocks) - 1:
                mid = current.midpoint  # numpy array
                # Use composition-predicted eps or fixed eps
                eps = self.composition_eps_schedule[i] if self.use_composition else self.reanchor_eps
                current = IntervalTensor.from_uncertainty(mid, eps)
                self.n_reanchors += 1
                self.block_widths.append(current.mean_width())

        return current

    # ------------------------------------------------------------------
    # Strategy 2: Adaptive re-anchoring (only when width exceeds threshold)
    # ------------------------------------------------------------------

    def _forward_adaptive(self, x: IntervalTensor) -> IntervalTensor:
        """Re-anchor only if max_width exceeds threshold.

        When use_composition=True, the threshold is derived from composition
        predictions: threshold_i = layer_specs[i].factor * 2 * reanchor_eps.
        This means we reanchor when the block output width significantly
        exceeds what a reanchored input would produce.
        """
        self.block_widths = [x.mean_width()]
        self.n_reanchors = 0
        self.composition_factors = []
        self.composition_predicted_widths = []

        current = x
        for i, block in enumerate(self.interval_blocks):
            pre_width = current.mean_width()
            current = block(current)
            post_width = current.mean_width()
            self.block_widths.append(post_width)

            # Track empirical factor
            if pre_width > 1e-15:
                factor = post_width / pre_width
            else:
                factor = 1.0
            self.composition_factors.append(factor)
            self.composition_predicted_widths.append(
                self.layer_specs[i].factor * pre_width if (
                    self.use_composition and i < len(self.layer_specs)
                ) else 0.0
            )

            if i < len(self.interval_blocks) - 1:
                # Composition-derived threshold: expected width after
                # reanchoring through this block (factor * 2 * eps)
                if self.use_composition and i < len(self.layer_specs):
                    threshold = self.layer_specs[i].factor * 2.0 * self.reanchor_eps
                else:
                    threshold = self.adaptive_threshold

                if current.max_width() > threshold:
                    mid = current.midpoint
                    eps = self.composition_eps_schedule[i] if self.use_composition else self.reanchor_eps
                    current = IntervalTensor.from_uncertainty(mid, eps)
                    self.n_reanchors += 1
                    self.block_widths.append(current.mean_width())

        return current

    # ------------------------------------------------------------------
    # Strategy 3: Hybrid (try naive first, fall back to midpoint)
    # ------------------------------------------------------------------

    def _forward_hybrid(self, x: IntervalTensor) -> IntervalTensor:
        """Try naive IBP; if output width too large, fall back to midpoint."""
        # Attempt 1: naive (full chain, global guarantee)
        naive_result = self._naive_model(x)

        if naive_result.max_width() < self.adaptive_threshold:
            # Narrow enough -- keep global guarantee
            self.block_widths = list(self._naive_model.layer_widths)
            self.n_reanchors = 0
            return naive_result

        # Attempt 2: midpoint re-anchoring
        return self._forward_midpoint(x)

    # ------------------------------------------------------------------
    # Strategy 4: Proportional re-anchoring (preserves relative signal)
    # ------------------------------------------------------------------

    def _forward_proportional(self, x: IntervalTensor) -> IntervalTensor:
        """Re-anchor using a fraction of current width (preserves signal).

        Instead of collapsing to midpoint +/- fixed_eps, collapse to
        midpoint +/- (shrink_factor * width / 2) per dimension.
        This preserves which dimensions are wider/narrower, maintaining
        sample-dependent uncertainty information.
        """
        self.block_widths = [x.mean_width()]
        self.n_reanchors = 0

        current = x
        for i, block in enumerate(self.interval_blocks):
            current = block(current)
            self.block_widths.append(current.mean_width())

            # Re-anchor between blocks (not after final)
            if i < len(self.interval_blocks) - 1:
                mid = current.midpoint
                half_w = current.width / 2  # per-dimension half-widths
                shrunk_hw = half_w * self.shrink_factor
                # Clamp to minimum reanchor_eps to avoid degenerate 0-width
                shrunk_hw = np.maximum(shrunk_hw, self.reanchor_eps)
                current = IntervalTensor(mid - shrunk_hw, mid + shrunk_hw)
                self.n_reanchors += 1
                self.block_widths.append(current.mean_width())

        return current

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def width_report(self) -> str:
        """ASCII report of per-block widths with composition diagnostics."""
        lines = [
            f"ReanchoredIntervalModel (bs={self.block_size}, "
            f"eps={self.reanchor_eps}, strategy={self.strategy}, "
            f"composition={'ON' if self.use_composition else 'OFF'})",
            f"Blocks: {len(self.interval_blocks)}, "
            f"Re-anchors: {self.n_reanchors}",
        ]

        # Show composition predictions if available
        if self.layer_specs:
            factors_str = ", ".join(f"{s.factor:.2f}" for s in self.layer_specs)
            lines.append(f"Predicted factors: [{factors_str}]")
            total = factor_product(self.layer_specs)
            lines.append(f"Total factor product: {total:.4f}")

        if self.use_composition and self.composition_eps_schedule:
            eps_str = ", ".join(f"{e:.6f}" for e in self.composition_eps_schedule)
            lines.append(f"Composition eps schedule: [{eps_str}]")

        lines.append("")
        lines.append("Step         | Mean Width")
        lines.append("-------------|----------")

        for i, w in enumerate(self.block_widths):
            lines.append(f"  step {i:<3d}   | {w:.6f}")

        # Show predicted vs actual comparison
        if self.composition_factors:
            lines.append("")
            lines.append("Block | Predicted Factor | Actual Factor | Predicted Width | Actual Width")
            lines.append("------|-----------------|---------------|-----------------|-------------")
            for i, (actual_f) in enumerate(self.composition_factors):
                pred_f = self.layer_specs[i].factor if i < len(self.layer_specs) else 0.0
                pred_w = self.composition_predicted_widths[i] if i < len(self.composition_predicted_widths) else 0.0
                # Actual output width = block_widths[i+1] (after block i)
                actual_w = self.block_widths[i + 1] if (i + 1) < len(self.block_widths) else 0.0
                sound = "✓" if pred_w >= actual_w - 1e-10 else "✗"
                lines.append(
                    f"  {i:<3d} | {pred_f:>14.4f}  | {actual_f:>12.4f}  | "
                    f"{pred_w:>14.6f}  | {actual_w:>10.6f} {sound}"
                )

        return "\n".join(lines)
