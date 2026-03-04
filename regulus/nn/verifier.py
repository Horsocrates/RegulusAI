"""
NNVerificationEngine: end-to-end neural network verification.

Takes a trained PyTorch model + input intervals,
returns certified robustness results.

Two verification modes:
  CERT — Sound IBP. certified=True means provably robust.
         Only naive strategy allowed. Coq backing: pi_add/sub/mul/relu etc.
  UQ   — Reanchored uncertainty quantification. NOT sound
         (Coq: pi_reanchor_loses_containment). Risk signal only.

Example usage:
    # Legacy API (backward compatible):
    engine = NNVerificationEngine(strategy="naive")
    result = engine.verify_from_point(model, input_numpy, epsilon=0.01)
    print(result.summary())

    # New API with explicit mode:
    engine = NNVerificationEngine(mode="cert")
    contract = engine.verify_contract(model, input_numpy, epsilon=0.01)
    print(contract.summary())
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
import torch
import torch.nn as nn

from regulus.nn.interval_tensor import IntervalTensor
from regulus.nn.model import IntervalSequential, convert_model
from regulus.nn.reanchor import ReanchoredIntervalModel
from regulus.analysis.reliability import ReliabilityAnalysis
from regulus.interval.evt import argmax_idx, max_on_grid


# =============================================================
# Verification Mode
# =============================================================


class VerificationMode(Enum):
    """Verification mode: sound certification vs uncertainty quantification.

    CERT: Sound IBP verification. certified=True means provably robust.
          Only naive strategy is allowed (full chain IBP, no reanchoring).
          Coq backing: all interval operations proven sound.

    UQ:   Reanchored uncertainty quantification. NOT sound — the reanchoring
          step loses containment (Coq: pi_reanchor_loses_containment).
          Useful as a risk signal, but cannot certify anything.
    """
    CERT = "cert"
    UQ = "uq"


# =============================================================
# Verification Contract
# =============================================================


@dataclass
class VerificationContract:
    """Structured result from verification with explicit mode semantics.

    This is the primary output for I3+ code. It makes the certification
    vs UQ distinction explicit in the type system.

    Fields:
        mode:              CERT or UQ
        predicted_class:   Argmax of midpoint output
        certified:         True ONLY if mode=CERT and bounds don't overlap.
                          Always False in UQ mode.
        margin:            Gap between predicted and second-best class.
                          Positive = predicted class dominates.
        max_output_width:  Maximum width across output neurons.
        risk:              0.0 = fully certified, 1.0 = max uncertainty.
                          CERT: 0.0 if certified, 1.0 otherwise.
                          UQ: min(1.0, max_width / (|margin| + 1e-10))
        output_bounds:     Full interval output (lo, hi arrays).
        per_layer_widths:  Width progression through the network.
        total_time_ms:     Total verification time.
        metadata:          Strategy-specific details (strategy, fold_bn, etc.)
        logic_guard_gate:  Hook for future LogicGuard D1 gating integration.
                          None by default. Future D1 integration will populate
                          this with True/False based on the Zero-Gate check
                          over the verification result. Pattern:
                            if contract.certified and contract.logic_guard_gate:
                                # Fully verified: IBP + LogicGuard agree
                            elif contract.certified:
                                # IBP certified but LogicGuard not yet checked
    """

    mode: VerificationMode
    predicted_class: int
    certified: bool
    margin: float
    max_output_width: float
    risk: float
    output_bounds: tuple[np.ndarray, np.ndarray]  # (lo, hi)
    per_layer_widths: list[float]
    total_time_ms: float
    metadata: dict = field(default_factory=dict)
    logic_guard_gate: Optional[bool] = None
    evt_margin: Optional[float] = None  # EVT-based margin (argmax gap)

    def summary(self) -> str:
        """Human-readable summary."""
        mode_label = "CERTIFICATION" if self.mode == VerificationMode.CERT else "UQ (Risk Signal)"
        status = "CERTIFIED" if self.certified else "NOT CERTIFIED"
        lines = [
            f"Verification Contract [{mode_label}]",
            f"  Status:           {status}",
            f"  Predicted class:  {self.predicted_class}",
            f"  Margin:           {self.margin:.6f}",
            f"  Max output width: {self.max_output_width:.6f}",
            f"  Risk:             {self.risk:.4f}",
            f"  Time:             {self.total_time_ms:.1f}ms",
        ]
        if self.evt_margin is not None:
            lines.append(f"  EVT margin:       {self.evt_margin:.6f}")
        if self.logic_guard_gate is not None:
            lg_status = "PASS" if self.logic_guard_gate else "FAIL"
            lines.append(f"  LogicGuard gate:  {lg_status}")
        strategy = self.metadata.get("strategy", "?")
        lines.append(f"  Strategy:         {strategy}")
        return "\n".join(lines)


@dataclass
class NNVerificationResult:
    """Result of neural network interval verification."""

    # Output bounds
    output_lo: np.ndarray
    output_hi: np.ndarray
    output_width: np.ndarray

    # Classification
    predicted_class: int
    certified_robust: bool  # True if predicted class has non-overlapping bounds
    margin: float  # Gap between predicted and second-best class

    # Per-layer diagnostics
    layer_widths: list[float] = field(default_factory=list)
    layer_diagnostics: list[dict] = field(default_factory=list)
    input_eps: float = 0.0

    # Timing
    conversion_time_ms: float = 0.0
    propagation_time_ms: float = 0.0

    # Strategy and options
    strategy: str = "naive"
    bn_folded: bool = False

    # EVT-based reliability
    evt_margin: Optional[float] = None  # EVT argmax margin (lo[pred] - hi[2nd])

    def summary(self) -> str:
        """Human-readable summary."""
        status = "CERTIFIED" if self.certified_robust else "NOT CERTIFIED"
        lines = [
            f"NN Verification Result: {status}",
            f"  Predicted class: {self.predicted_class}",
            f"  Certified robust: {self.certified_robust}",
            f"  Margin: {self.margin:.6f}",
            f"  Max output width: {np.max(self.output_width):.6f}",
            f"  Mean output width: {np.mean(self.output_width):.6f}",
            f"  Input epsilon: {self.input_eps:.6f}",
            f"  Strategy: {self.strategy}",
            f"  Time: {self.conversion_time_ms + self.propagation_time_ms:.1f}ms",
        ]
        if self.layer_widths:
            lines.append(f"  Layers: {len(self.layer_widths)}")
            lines.append(f"  Width blowup: {self.layer_widths[-1] / self.layer_widths[0]:.2f}x"
                         if self.layer_widths[0] > 0 else "  Width blowup: N/A")
        return "\n".join(lines)

    def width_report(self) -> str:
        """Per-layer width report."""
        if not self.layer_widths:
            return "No layer width data available."
        lines = ["Layer  | Mean Width | Ratio"]
        lines.append("-------|------------|------")
        w0 = self.layer_widths[0]
        for i, w in enumerate(self.layer_widths):
            ratio = w / w0 if w0 > 0 else float("inf")
            label = "Input " if i == 0 else f"Layer{i}"
            lines.append(f"{label} | {w:.6f}   | {ratio:.2f}x")
        return "\n".join(lines)

    def diagnostics_report(self) -> str:
        """Detailed per-layer diagnostics with unstable ReLU counts."""
        if not self.layer_diagnostics:
            return "No diagnostic data available."
        lines = [
            "Layer               | Mean W  | Max W   | Unstable | Stab%",
            "--------------------|---------|---------|----------|------",
        ]
        for d in self.layer_diagnostics:
            name = d["name"][:19].ljust(19)
            mean_w = f"{d['mean_width']:.5f}"
            max_w = f"{d['max_width']:.5f}"
            unstable = str(d.get("unstable_relu_count", "-")).rjust(8)
            stab = d.get("stability_ratio")
            stab_s = f"{stab * 100:.1f}%" if stab is not None else "  -  "
            lines.append(f"{name} | {mean_w} | {max_w} | {unstable} | {stab_s}")
        return "\n".join(lines)


def _compute_evt_margin(
    output_lo: np.ndarray, output_hi: np.ndarray, predicted: int,
) -> float:
    """Compute EVT-based margin between predicted class and runner-up.

    Uses EVT argmax_idx to find the class whose upper bound is closest
    to threatening the predicted class's lower bound. The margin is:
        evt_margin = lo[predicted] - max_{j != predicted}(hi[j])

    Positive margin = certified separation. Negative = overlap exists.

    This is the interval-level analog of EVT's argmax: instead of
    searching over a grid of input perturbations, we search over
    the output classes to find the "most threatening" competitor.
    """
    n_classes = len(output_lo)
    if n_classes <= 1:
        return float(output_lo[predicted])

    # Build list of competitor upper bounds (exclude predicted class)
    competitors = []
    competitor_indices = []
    for j in range(n_classes):
        if j != predicted:
            competitors.append(float(output_hi[j]))
            competitor_indices.append(j)

    # Use EVT argmax_idx to find the most threatening competitor
    # (the one with highest upper bound)
    threat_idx = argmax_idx(lambda x: x, competitors)
    worst_hi = competitors[threat_idx]

    return float(output_lo[predicted]) - worst_hi


class NNVerificationEngine:
    """Verify neural network outputs using interval bound propagation.

    Two modes:
    - CERT: Sound certification. Only naive strategy allowed.
    - UQ: Uncertainty quantification. Only reanchored strategies allowed.

    Legacy usage (backward compatible):
        engine = NNVerificationEngine(strategy="naive")  # no mode → legacy

    New usage with explicit mode:
        engine = NNVerificationEngine(mode="cert")           # CERT + naive
        engine = NNVerificationEngine(mode="uq", strategy="proportional")

    Invalid combinations raise ValueError:
        NNVerificationEngine(mode="cert", strategy="midpoint")  # ERROR
        NNVerificationEngine(mode="uq", strategy="naive")       # ERROR
    """

    # Strategies allowed per mode
    _CERT_STRATEGIES = frozenset({"naive", "crown"})
    _UQ_STRATEGIES = frozenset({"midpoint", "adaptive", "hybrid", "proportional"})

    def __init__(
        self,
        strategy: str = "naive",
        reanchor_eps: float = 0.001,
        block_size: int = 1,
        adaptive_threshold: float = 1.0,
        fold_bn: bool = False,
        mode: Optional[str] = None,
        crown_alpha_mode: str = "adaptive",
        crown_depth: str = "fc",
    ) -> None:
        # Validate strategy
        all_strategies = self._CERT_STRATEGIES | self._UQ_STRATEGIES
        if strategy not in all_strategies:
            raise ValueError(
                f"Unknown strategy: {strategy}. "
                f"Supported: {', '.join(sorted(all_strategies))}"
            )

        # Mode validation
        self.mode: Optional[VerificationMode] = None
        if mode is not None:
            try:
                self.mode = VerificationMode(mode)
            except ValueError:
                raise ValueError(
                    f"Unknown mode: {mode}. Supported: 'cert', 'uq'"
                )

            # Validate mode + strategy compatibility
            if self.mode == VerificationMode.CERT and strategy not in self._CERT_STRATEGIES:
                raise ValueError(
                    f"CERT mode requires naive or crown strategy, got '{strategy}'. "
                    f"Reanchored strategies are not sound — use mode='uq'."
                )
            if self.mode == VerificationMode.UQ and strategy not in self._UQ_STRATEGIES:
                raise ValueError(
                    f"UQ mode requires a reanchored strategy "
                    f"({', '.join(sorted(self._UQ_STRATEGIES))}), got '{strategy}'. "
                    f"Naive IBP is sound — use mode='cert'."
                )

        self.strategy = strategy
        self.reanchor_eps = reanchor_eps
        self.block_size = block_size
        self.adaptive_threshold = adaptive_threshold
        self.fold_bn = fold_bn
        self.crown_alpha_mode = crown_alpha_mode
        self.crown_depth = crown_depth

    def verify(
        self,
        model: nn.Module,
        input_interval: IntervalTensor,
        true_label: Optional[int] = None,
    ) -> NNVerificationResult:
        """Run full verification pipeline.

        Args:
            model: Trained PyTorch model (must be in eval mode).
            input_interval: Input with interval bounds.
            true_label: Optional ground truth label for reporting.

        Returns:
            NNVerificationResult with output bounds and certification status.
        """
        model.eval()

        if self.strategy == "crown":
            return self._verify_crown(model, input_interval, true_label)

        # Step 1: Convert model
        t0 = time.perf_counter()
        if self.strategy == "naive":
            interval_model = convert_model(model, fold_bn=self.fold_bn)
        else:
            interval_model = ReanchoredIntervalModel(
                model,
                block_size=self.block_size,
                reanchor_eps=self.reanchor_eps,
                strategy=self.strategy,
                adaptive_threshold=self.adaptive_threshold,
            )
        conversion_ms = (time.perf_counter() - t0) * 1000

        # Step 2: Propagate intervals
        t1 = time.perf_counter()
        output = interval_model(input_interval)
        propagation_ms = (time.perf_counter() - t1) * 1000

        # Step 3: Analyze output for certification
        analysis = ReliabilityAnalysis.classify(output)
        predicted = analysis["predicted_class"]
        certified = analysis["reliable"]
        margin = analysis["gap"]

        # Step 3b: EVT margin — use argmax_idx on per-class margins
        evt_margin = _compute_evt_margin(output.lo, output.hi, predicted)

        # Step 4: Collect per-layer widths and diagnostics
        layer_widths: list[float] = []
        layer_diagnostics: list[dict] = []
        if hasattr(interval_model, "layer_widths"):
            layer_widths = list(interval_model.layer_widths)
        elif hasattr(interval_model, "block_widths"):
            layer_widths = list(interval_model.block_widths)
        if hasattr(interval_model, "layer_diagnostics"):
            layer_diagnostics = list(interval_model.layer_diagnostics)

        return NNVerificationResult(
            output_lo=output.lo.copy(),
            output_hi=output.hi.copy(),
            output_width=output.width.copy(),
            predicted_class=predicted,
            certified_robust=certified,
            margin=margin,
            layer_widths=layer_widths,
            layer_diagnostics=layer_diagnostics,
            input_eps=float(input_interval.mean_width() / 2),
            conversion_time_ms=conversion_ms,
            propagation_time_ms=propagation_ms,
            strategy=self.strategy,
            bn_folded=self.fold_bn,
            evt_margin=evt_margin,
        )

    def _verify_crown(
        self,
        model: nn.Module,
        input_interval: IntervalTensor,
        true_label: Optional[int] = None,
    ) -> NNVerificationResult:
        """Run CROWN verification (tighter bounds than naive IBP).

        CROWN is sound: bounds are guaranteed to contain the true output.
        Uses backward-mode linear relaxation for tighter bounds.
        """
        from regulus.nn.crown import CROWNEngine

        t0 = time.perf_counter()
        engine = CROWNEngine(alpha_mode=self.crown_alpha_mode, crown_depth=self.crown_depth)
        conversion_ms = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        center = input_interval.midpoint
        epsilon = float(input_interval.mean_width() / 2)
        result = engine.compute_bounds(model, center, epsilon)
        propagation_ms = (time.perf_counter() - t1) * 1000

        # Build IntervalTensor from CROWN output
        output = IntervalTensor(result.output_lo, result.output_hi)

        # Analyze for certification
        analysis = ReliabilityAnalysis.classify(output)
        predicted = analysis["predicted_class"]
        certified = analysis["reliable"]
        margin = analysis["gap"]

        # EVT margin
        evt_margin = _compute_evt_margin(result.output_lo, result.output_hi, predicted)

        # Collect per-layer width info from CROWN
        layer_widths = []
        for lb in result.layer_bounds:
            width = float(np.mean(lb.post_hi - lb.post_lo))
            layer_widths.append(width)

        return NNVerificationResult(
            output_lo=result.output_lo.copy(),
            output_hi=result.output_hi.copy(),
            output_width=(result.output_hi - result.output_lo).copy(),
            predicted_class=predicted,
            certified_robust=certified,
            margin=margin,
            layer_widths=layer_widths,
            layer_diagnostics=[],
            input_eps=epsilon,
            conversion_time_ms=conversion_ms,
            propagation_time_ms=propagation_ms,
            strategy="crown",
            bn_folded=True,  # CROWN always folds BN
            evt_margin=evt_margin,
        )

    def verify_from_point(
        self,
        model: nn.Module,
        input_point: np.ndarray,
        epsilon: float,
        true_label: Optional[int] = None,
    ) -> NNVerificationResult:
        """Convenience: verify with point input ± epsilon perturbation.

        Args:
            model: Trained PyTorch model (must be in eval mode).
            input_point: Center point as numpy array.
            epsilon: Perturbation radius.
            true_label: Optional ground truth label.

        Returns:
            NNVerificationResult.
        """
        input_interval = IntervalTensor.from_uncertainty(
            np.asarray(input_point, dtype=np.float64), epsilon
        )
        return self.verify(model, input_interval, true_label)

    def verify_contract(
        self,
        model: nn.Module,
        input_point: np.ndarray,
        epsilon: float,
        true_label: Optional[int] = None,
    ) -> VerificationContract:
        """Verify and return a VerificationContract with mode semantics.

        Requires mode to be set at construction time.

        Args:
            model: Trained PyTorch model.
            input_point: Center point as numpy array.
            epsilon: Perturbation radius.
            true_label: Optional ground truth label.

        Returns:
            VerificationContract with explicit mode/certified/risk fields.

        Raises:
            ValueError: If mode was not set at construction time.
        """
        if self.mode is None:
            raise ValueError(
                "verify_contract() requires mode to be set. "
                "Use NNVerificationEngine(mode='cert') or mode='uq'."
            )

        # Run underlying verification
        result = self.verify_from_point(model, input_point, epsilon, true_label)

        # Compute mode-specific fields
        max_width = float(np.max(result.output_width))

        if self.mode == VerificationMode.CERT:
            # Sound certification: certified only if bounds don't overlap
            certified = result.certified_robust
            risk = 0.0 if certified else 1.0
        else:
            # UQ mode: never certified (reanchoring is not sound)
            certified = False
            risk = min(1.0, max_width / (abs(result.margin) + 1e-10))

        # EVT-based risk: use evt_margin for finer risk estimation
        evt_risk = risk
        if result.evt_margin is not None and self.mode == VerificationMode.CERT:
            # EVT risk: 0 if margin > 0 (certified), else proportion of gap
            evt_risk = 0.0 if result.evt_margin > 0 else min(
                1.0, max_width / (abs(result.evt_margin) + 1e-10)
            )

        return VerificationContract(
            mode=self.mode,
            predicted_class=result.predicted_class,
            certified=certified,
            margin=result.margin,
            max_output_width=max_width,
            risk=evt_risk if result.evt_margin is not None else risk,
            output_bounds=(result.output_lo, result.output_hi),
            per_layer_widths=result.layer_widths,
            total_time_ms=result.conversion_time_ms + result.propagation_time_ms,
            evt_margin=result.evt_margin,
            metadata={
                "strategy": self.strategy,
                "fold_bn": self.fold_bn,
                "input_eps": result.input_eps,
                "bn_folded": result.bn_folded,
            },
        )
