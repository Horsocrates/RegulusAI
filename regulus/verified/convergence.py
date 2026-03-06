"""
convergence.py — Convergence calculator based on Banach contraction principle.

Analyzes sequences of confidence scores from iterative verification to estimate
contraction factors, predict convergence, and recommend next actions.

Theorem backing: FixedPoint.v (Banach_contraction_principle)
  If T : X -> X is a contraction with factor c < 1 on a complete metric space,
  then T has a unique fixed point x* and ||T^n(x0) - x*|| <= c^n / (1 - c) * ||x0 - T(x0)||.

In our setting:
  - "x" = current confidence level
  - "T" = one iteration of the verification pipeline
  - "c" = estimated contraction factor (ratio of successive gaps)
  - "d0" = initial gap to target (100 - initial_confidence)
  - Convergence criterion: gap < epsilon (default 5.0 confidence points)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ContractionEstimate:
    """Estimated contraction parameters for a verification sequence.

    Attributes:
        factor: Estimated contraction factor c (ratio of successive gaps).
        initial_gap: Gap at first observation d0 = 100 - confidence_at_start.
        confidence_at_start: Confidence level at the first iteration.
    """

    factor: float
    initial_gap: float
    confidence_at_start: float

    @property
    def is_contractive(self) -> bool:
        """True if 0 < factor < 1 (Banach contraction condition)."""
        return 0.0 < self.factor < 1.0

    def iterations_needed(self, epsilon: float = 5.0) -> int:
        """Estimate iterations to reach gap < epsilon from current state.

        Uses Banach bound: n >= log(epsilon * (1 - c) / d0) / log(c).

        Returns:
            Non-negative int if contractive and gap > epsilon.
            0 if gap is already <= epsilon.
            -1 if not contractive (will never converge).
        """
        if self.initial_gap <= epsilon:
            return 0
        if not self.is_contractive:
            return -1

        # From Banach: c^n * d0 / (1 - c) < epsilon
        # => c^n < epsilon * (1 - c) / d0
        # => n > log(epsilon * (1 - c) / d0) / log(c)
        # Note: log(c) < 0 since 0 < c < 1, so inequality flips.
        numerator = epsilon * (1.0 - self.factor) / self.initial_gap
        if numerator >= 1.0:
            # Already within bound at n=0
            return 0
        n = math.log(numerator) / math.log(self.factor)
        return max(1, math.ceil(n))

    def predicted_confidence_at(self, n: int) -> float:
        """Predict confidence after n iterations from start.

        Uses: confidence(n) = 100 - d0 * c^n / (1 - c)
        Clamped to [0, 100].

        Args:
            n: Number of iterations from start.

        Returns:
            Predicted confidence level.
        """
        if not self.is_contractive:
            # Non-contractive: return start confidence (no convergence guarantee)
            return self.confidence_at_start
        remaining_gap = self.initial_gap * (self.factor ** n) / (1.0 - self.factor)
        predicted = 100.0 - remaining_gap
        return max(0.0, min(100.0, predicted))

    def should_paradigm_shift(self, consecutive_stalls: int) -> bool:
        """Whether to recommend a paradigm shift (change strategy).

        A paradigm shift is recommended when:
        - The sequence is not contractive (factor >= 1), OR
        - There have been 3+ consecutive stalls (no improvement).

        Args:
            consecutive_stalls: Number of consecutive iterations without improvement.

        Returns:
            True if a paradigm shift is recommended.
        """
        if not self.is_contractive:
            return True
        if consecutive_stalls >= 3:
            return True
        return False


class ConvergenceAnalyzer:
    """Analyzes a sequence of confidence scores to estimate convergence.

    Records iterations and computes contraction estimates using the
    Banach fixed-point theorem framework from FixedPoint.v.
    """

    def __init__(self) -> None:
        self._history: list[float] = []

    @property
    def history(self) -> list[float]:
        """Read-only access to recorded confidence history."""
        return list(self._history)

    def record_iteration(self, confidence: float) -> None:
        """Record a confidence score from one pipeline iteration.

        Args:
            confidence: Confidence level in [0, 100].
        """
        self._history.append(float(confidence))

    def estimate_contraction(self) -> Optional[ContractionEstimate]:
        """Estimate contraction factor from recorded history.

        Needs at least 3 data points to compute gap ratios.
        Uses median of consecutive gap ratios for robustness.

        Returns:
            ContractionEstimate if enough data, None otherwise.
        """
        if len(self._history) < 3:
            return None

        # Compute gaps to target (100)
        gaps = [100.0 - c for c in self._history]

        # Compute consecutive gap ratios
        ratios: list[float] = []
        for i in range(1, len(gaps)):
            if abs(gaps[i - 1]) < 1e-12:
                # Previous gap was ~0, can't compute ratio
                continue
            ratios.append(gaps[i] / gaps[i - 1])

        if not ratios:
            return None

        # Use median ratio as the estimated contraction factor
        sorted_ratios = sorted(ratios)
        mid = len(sorted_ratios) // 2
        if len(sorted_ratios) % 2 == 0:
            factor = (sorted_ratios[mid - 1] + sorted_ratios[mid]) / 2.0
        else:
            factor = sorted_ratios[mid]

        return ContractionEstimate(
            factor=factor,
            initial_gap=gaps[0],
            confidence_at_start=self._history[0],
        )

    def _count_consecutive_stalls(self, threshold: float = 0.5) -> int:
        """Count consecutive stalls at the end of the history.

        A stall is when the confidence improvement is less than threshold.

        Args:
            threshold: Minimum improvement to not count as a stall.

        Returns:
            Number of consecutive stalls at the tail.
        """
        if len(self._history) < 2:
            return 0
        count = 0
        for i in range(len(self._history) - 1, 0, -1):
            improvement = self._history[i] - self._history[i - 1]
            if improvement < threshold:
                count += 1
            else:
                break
        return count

    def recommend(self) -> dict:
        """Generate a recommendation based on convergence analysis.

        Returns a dict with:
            action: "continue" | "stop_converged" | "paradigm_shift"
            reason: Human-readable explanation.
            estimated_iterations_remaining: int or None.
            contraction_factor: float or None.
            predicted_final_confidence: float or None.
            theorem_backing: str — Coq theorem reference.
        """
        estimate = self.estimate_contraction()
        stalls = self._count_consecutive_stalls()

        base = {
            "theorem_backing": "FixedPoint.v: Banach_contraction_principle",
        }

        if estimate is None:
            return {
                **base,
                "action": "continue",
                "reason": "Insufficient data (need >= 3 iterations).",
                "estimated_iterations_remaining": None,
                "contraction_factor": None,
                "predicted_final_confidence": None,
            }

        current_confidence = self._history[-1]
        current_gap = 100.0 - current_confidence

        # Check if already converged (gap < 5)
        if current_gap < 5.0:
            return {
                **base,
                "action": "stop_converged",
                "reason": (
                    f"Confidence {current_confidence:.1f}% is within 5pp of target. "
                    f"Banach bound satisfied."
                ),
                "estimated_iterations_remaining": 0,
                "contraction_factor": estimate.factor,
                "predicted_final_confidence": current_confidence,
            }

        # Check if paradigm shift needed
        if estimate.should_paradigm_shift(stalls):
            reason_parts = []
            if not estimate.is_contractive:
                reason_parts.append(
                    f"Contraction factor c={estimate.factor:.3f} >= 1 "
                    f"(not contractive)."
                )
            if stalls >= 3:
                reason_parts.append(
                    f"{stalls} consecutive stalls detected."
                )
            return {
                **base,
                "action": "paradigm_shift",
                "reason": " ".join(reason_parts) + " Recommend changing strategy.",
                "estimated_iterations_remaining": -1,
                "contraction_factor": estimate.factor,
                "predicted_final_confidence": None,
            }

        # Contractive and not yet converged: continue
        iters = estimate.iterations_needed(epsilon=5.0)
        n_done = len(self._history) - 1
        predicted = estimate.predicted_confidence_at(n_done + iters)

        return {
            **base,
            "action": "continue",
            "reason": (
                f"Contractive (c={estimate.factor:.3f}). "
                f"Estimated {iters} more iteration(s) to converge."
            ),
            "estimated_iterations_remaining": iters,
            "contraction_factor": estimate.factor,
            "predicted_final_confidence": predicted,
        }

    def derive_deployment_profile(self) -> dict:
        """Derive a deployment readiness profile from the convergence history.

        Returns a dict with:
            iterations_completed: int
            current_confidence: float or None
            contraction_factor: float or None
            is_contractive: bool
            estimated_total_iterations: int or None
            convergence_status: str
            theorem_backing: str
        """
        estimate = self.estimate_contraction()

        current = self._history[-1] if self._history else None
        n_done = len(self._history)

        if estimate is None:
            return {
                "iterations_completed": n_done,
                "current_confidence": current,
                "contraction_factor": None,
                "is_contractive": False,
                "estimated_total_iterations": None,
                "convergence_status": "insufficient_data",
                "theorem_backing": "FixedPoint.v: Banach_contraction_principle",
            }

        iters_remaining = estimate.iterations_needed(epsilon=5.0)
        if iters_remaining == 0:
            status = "converged"
            total = n_done
        elif iters_remaining == -1:
            status = "divergent"
            total = None
        else:
            status = "converging"
            total = n_done + iters_remaining

        return {
            "iterations_completed": n_done,
            "current_confidence": current,
            "contraction_factor": estimate.factor,
            "is_contractive": estimate.is_contractive,
            "estimated_total_iterations": total,
            "convergence_status": status,
            "theorem_backing": "FixedPoint.v: Banach_contraction_principle",
        }
