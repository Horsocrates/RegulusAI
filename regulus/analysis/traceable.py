"""
Traceable Uncertainty Analysis -- per-block interval decomposition.

Propagates intervals block-by-block through an IntervalSequential,
re-anchoring between blocks, and computing margin at each boundary.
Identifies the "critical block" (weakest link in the chain).

L4 (Law of Sufficient Reason): every prediction has a traceable cause.
If unreliable -- there is a specific block where margin collapses.

Usage:
    model = make_mlp()        # or any architecture
    model.eval()
    imodel = convert_model(model)
    tracer = TraceableAnalysis(reanchor_eps=0.01)
    report = tracer.trace(imodel, x_interval)

    report.reliable           # bool
    report.predicted_class    # int
    report.final_margin       # float
    report.block_reports      # list of BlockReport per block
    report.critical_block     # index of weakest block
    report.explanation        # human-readable string
"""

from __future__ import annotations

import dataclasses
from typing import Optional

import numpy as np

from regulus.nn.interval_tensor import IntervalTensor
from regulus.nn.model import IntervalSequential
from regulus.nn.layers import IntervalReLU


@dataclasses.dataclass
class BlockReport:
    """Report for a single block in the trace."""
    block_idx: int
    margin: float
    mean_width: float
    is_final: bool
    top_class: Optional[int] = None
    runner_up: Optional[int] = None
    gap: Optional[float] = None
    max_width: Optional[float] = None


@dataclasses.dataclass
class TraceReport:
    """Full traceable uncertainty report."""
    reliable: bool
    predicted_class: int
    final_margin: float
    block_reports: list
    critical_block: int
    explanation: str
    n_blocks: int

    def print_summary(self):
        """Print human-readable summary."""
        print(f"Prediction: class {self.predicted_class}")
        print(f"Reliable: {'YES' if self.reliable else 'NO'}")
        print(f"Final margin: {self.final_margin:.3f}")
        print(f"Critical block: {self.critical_block}")
        print(f"\nPer-block margins:")
        for b in self.block_reports:
            marker = ">>>" if b.block_idx == self.critical_block else "   "
            final_tag = " [FINAL]" if b.is_final else ""
            class_info = (f" (class {b.top_class} vs {b.runner_up})"
                          if b.is_final and b.top_class is not None else "")
            print(f"  {marker} Block {b.block_idx}: margin={b.margin:.3f}, "
                  f"width={b.mean_width:.4f}{class_info}{final_tag}")
        print(f"\n{self.explanation}")


class TraceableAnalysis:
    """Per-block interval decomposition with re-anchoring.

    Walks through an IntervalSequential layer by layer, grouping layers
    into "blocks" at activation boundaries (IntervalReLU or IntervalResBlock).
    At each boundary, computes a margin and re-anchors.

    This mirrors the _ra_margin_forward() pattern from
    architecture_benchmark.py but records per-block diagnostics.
    """

    def __init__(self, reanchor_eps: float = 0.01,
                 threshold: float = 1.0) -> None:
        self.reanchor_eps = reanchor_eps
        self.threshold = threshold

    def trace(self, imodel: IntervalSequential,
              x: IntervalTensor) -> TraceReport:
        """Trace interval propagation block-by-block.

        Parameters
        ----------
        imodel : IntervalSequential
            Interval model (output of convert_model).
        x : IntervalTensor
            Input interval (e.g. from_uncertainty(input, eps)).

        Returns
        -------
        TraceReport with per-block margins and critical block identification.
        """
        # Lazy import to avoid circular dependency
        from regulus.nn.architectures import IntervalResBlock

        layers = imodel.layers
        n = len(layers)

        # Group layers into blocks: each block ends at an activation
        # (IntervalReLU or IntervalResBlock).
        # The final group (after last activation) is the output block.
        block_layers: list[list] = []
        current_group: list = []

        for layer in layers:
            current_group.append(layer)
            if isinstance(layer, (IntervalReLU, IntervalResBlock)):
                block_layers.append(current_group)
                current_group = []

        # Remaining layers after last activation (e.g., final Linear)
        if current_group:
            block_layers.append(current_group)

        # Propagate through blocks
        current = x
        block_reports = []
        n_blocks = len(block_layers)

        for block_idx, group in enumerate(block_layers):
            is_final = (block_idx == n_blocks - 1)

            # Propagate through all layers in this block
            for layer in group:
                current = layer(current)

            # Compute margin on current output
            flat_lo = current.lo.flatten()
            flat_hi = current.hi.flatten()
            midpoints = (flat_lo + flat_hi) / 2
            widths = flat_hi - flat_lo

            max_w = float(widths.max()) if widths.size > 0 else 1e-10
            max_w = max(max_w, 1e-10)
            mean_w = float(widths.mean()) if widths.size > 0 else 0.0

            if is_final:
                # Final block: margin between top-2 classes
                sorted_idx = np.argsort(midpoints)[::-1]
                c1, c2 = int(sorted_idx[0]), int(sorted_idx[1])
                gap = float(midpoints[c1] - midpoints[c2])
                margin = gap / max_w

                block_reports.append(BlockReport(
                    block_idx=block_idx,
                    margin=margin,
                    mean_width=mean_w,
                    is_final=True,
                    top_class=c1,
                    runner_up=c2,
                    gap=gap,
                    max_width=max_w,
                ))
            else:
                # Intermediate block: margin between top-2 activations
                if len(midpoints) >= 2:
                    sorted_vals = np.sort(midpoints)[::-1]
                    gap = float(sorted_vals[0] - sorted_vals[1])
                    margin = gap / max_w
                else:
                    margin = float("inf")

                block_reports.append(BlockReport(
                    block_idx=block_idx,
                    margin=margin,
                    mean_width=mean_w,
                    is_final=False,
                ))

                # Re-anchor (not after last block)
                mid = (current.lo + current.hi) / 2
                current = IntervalTensor(
                    mid - self.reanchor_eps,
                    mid + self.reanchor_eps,
                )

        # Assemble report
        final = block_reports[-1]
        margins = [b.margin for b in block_reports]
        critical_idx = int(np.argmin(margins))
        reliable = final.margin > self.threshold

        explanation = self._generate_explanation(
            block_reports, final, critical_idx, reliable
        )

        return TraceReport(
            reliable=reliable,
            predicted_class=final.top_class if final.top_class is not None else -1,
            final_margin=final.margin,
            block_reports=block_reports,
            critical_block=critical_idx,
            explanation=explanation,
            n_blocks=n_blocks,
        )

    def _generate_explanation(self, blocks, final, critical_idx, reliable):
        """Generate human-readable explanation."""
        if reliable:
            return (
                f"Prediction: class {final.top_class} (reliable). "
                f"Final margin: {final.margin:.2f}. "
                f"The network consistently distinguishes class {final.top_class} "
                f"from runner-up class {final.runner_up} across all blocks."
            )
        else:
            critical = blocks[critical_idx]
            return (
                f"Prediction: class {final.top_class} (UNRELIABLE). "
                f"Final margin: {final.margin:.2f}. "
                f"Critical block: {critical_idx} "
                f"(margin={critical.margin:.2f}). "
                f"At block {critical_idx}, the network struggles to "
                f"distinguish the leading activation from competitors, "
                f"indicating ambiguity in intermediate representations."
            )
