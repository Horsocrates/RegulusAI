"""
convergence_advisor.py — Human-readable convergence advisor.

Wraps ConvergenceAnalyzer to produce formatted advice strings
with theorem references, suitable for CLI output or logging.

Theorem backing: FixedPoint.v (Banach_contraction_principle)
"""

from __future__ import annotations

from regulus.verified.convergence import ConvergenceAnalyzer


class ConvergenceAdvisor:
    """Provides human-readable convergence advice with theorem backing.

    Wraps ConvergenceAnalyzer and formats recommendations as
    actionable strings with Coq theorem references.
    """

    def __init__(self) -> None:
        self._analyzer = ConvergenceAnalyzer()

    def record(self, confidence: float) -> None:
        """Record a confidence score from one pipeline iteration.

        Args:
            confidence: Confidence level in [0, 100].
        """
        self._analyzer.record_iteration(confidence)

    def advise(self) -> str:
        """Generate human-readable advice with theorem reference.

        Returns:
            Formatted string with [ACTION], [REASON], [THEOREM],
            and optionally [ESTIMATE] tags.
        """
        rec = self._analyzer.recommend()

        parts: list[str] = []

        # Action tag
        action = rec["action"].upper().replace("_", " ")
        parts.append(f"[ACTION] {action}")

        # Reason tag
        parts.append(f"[REASON] {rec['reason']}")

        # Estimate tag (if applicable)
        iters = rec.get("estimated_iterations_remaining")
        factor = rec.get("contraction_factor")
        predicted = rec.get("predicted_final_confidence")

        if factor is not None:
            estimate_parts = [f"c = {factor:.3f}"]
            if iters is not None and iters >= 0:
                estimate_parts.append(f"iterations remaining = {iters}")
            if predicted is not None:
                estimate_parts.append(f"predicted final confidence = {predicted:.1f}%")
            parts.append(f"[ESTIMATE] {', '.join(estimate_parts)}")

        # Theorem tag
        parts.append(f"[THEOREM] {rec['theorem_backing']}")

        return "\n".join(parts)
