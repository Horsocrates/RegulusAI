"""
math_verifier.py — D4 Verified Computation Integration.

When D4 performs mathematical computation, checks if a verified theorem applies.
If yes, uses the verified backend instead of relying on LLM computation.

Verified steps receive confidence_override = 100 (machine-checked = certain).
"""

from __future__ import annotations

from typing import Optional

from regulus.verified.bridge import VerifiedBackend, VerifiedResult


class MathVerifier:
    """Checks if verified theorems apply to D4 computation tasks.

    Used after D3 selects a framework and D4 produces computation data.
    If a verified theorem matches, the result has machine-checked certainty.
    """

    def __init__(self, backend: Optional[VerifiedBackend] = None):
        self.backend = backend or VerifiedBackend()

    def try_verify(
        self, d3_framework: str, d4_data: dict
    ) -> Optional[VerifiedResult]:
        """Given D3's chosen framework and D4's data, try to apply a verified theorem.

        Returns VerifiedResult if a theorem applies, None otherwise.
        When result is returned, D4 confidence for this step = 100%.

        Args:
            d3_framework: The framework/method selected by D3
            d4_data: Computation data from D4 (function values, bounds, etc.)
        """
        framework_lower = d3_framework.lower()

        # IVT detection
        if any(
            kw in framework_lower
            for kw in ["intermediate value", "ivt", "root finding", "zero crossing"]
        ):
            return self._try_ivt(d4_data)

        # EVT detection
        if any(
            kw in framework_lower
            for kw in [
                "extreme value",
                "evt",
                "maximum",
                "minimum",
                "optimization",
                "argmax",
            ]
        ):
            return self._try_evt(d4_data)

        # CROWN / interval bound detection
        if any(
            kw in framework_lower
            for kw in [
                "crown",
                "interval bound",
                "neural network bound",
                "interval arithmetic",
                "ibp",
            ]
        ):
            return self._try_crown(d4_data)

        # Series convergence detection
        if any(
            kw in framework_lower
            for kw in [
                "convergence",
                "series",
                "ratio test",
                "geometric series",
            ]
        ):
            return self._try_convergence(d4_data)

        # Fixed point / contraction detection
        if any(
            kw in framework_lower
            for kw in [
                "fixed point",
                "contraction",
                "banach",
                "iteration",
                "iterative",
            ]
        ):
            return self._try_contraction(d4_data)

        return None  # No verified theorem applicable

    def _try_ivt(self, data: dict) -> Optional[VerifiedResult]:
        f_a = data.get("f_a")
        f_b = data.get("f_b")
        if f_a is not None and f_b is not None:
            return self.backend.check_ivt(float(f_a), float(f_b))
        return None

    def _try_evt(self, data: dict) -> Optional[VerifiedResult]:
        values = data.get("values") or data.get("function_values")
        if values:
            return self.backend.check_evt([float(v) for v in values])
        return None

    def _try_crown(self, data: dict) -> Optional[VerifiedResult]:
        if all(k in data for k in ["weights", "bias", "input_lo", "input_hi"]):
            return self.backend.check_crown_bounds(
                data["weights"], data["bias"], data["input_lo"], data["input_hi"]
            )
        return None

    def _try_convergence(self, data: dict) -> Optional[VerifiedResult]:
        ratio = data.get("ratio")
        if ratio is not None:
            threshold = data.get("threshold", 1.0)
            return self.backend.check_convergence(float(ratio), float(threshold))
        return None

    def _try_contraction(self, data: dict) -> Optional[VerifiedResult]:
        factor = data.get("factor") or data.get("contraction_factor")
        if factor is not None:
            x0 = float(data.get("x0", 0))
            x1 = float(data.get("x1", 1))
            return self.backend.check_contraction(float(factor), x0, x1)
        return None

    def annotate_d4_output(
        self, d3_output: dict, d4_output: dict
    ) -> dict:
        """After D4 completes, check if verified theorem applies and annotate.

        Modifies d4_output in-place by adding `verified_result` key if applicable.
        Returns the (possibly annotated) d4_output.
        """
        verified = self.try_verify(
            d3_framework=d3_output.get("framework", ""),
            d4_data=d4_output.get("computation_data", {}),
        )
        if verified and verified.success:
            d4_output["verified_result"] = {
                "value": verified.value,
                "certificate": verified.certificate,
                "theorem": verified.theorem_used,
                "confidence_override": 100,  # Machine-checked = certain
            }
        return d4_output
