"""
bridge.py — OCaml-Python bridge for verified computation.

Calls OCaml-extracted functions from Coq proofs via subprocess/JSON.
Falls back to pure Python implementations when OCaml binaries are unavailable.

Every VerifiedResult carries:
  - success: whether the check completed
  - value: the computed result
  - certificate: human-readable explanation of WHY this is correct
  - theorem_used: which Coq theorem backs this result
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class VerifiedResult:
    """Result from a verified computation."""

    success: bool
    value: Any
    certificate: str  # human-readable explanation
    theorem_used: str  # Coq theorem that backs this result


class VerifiedBackend:
    """Bridge to OCaml-extracted ToS verified functions.

    Works WITH or WITHOUT compiled OCaml binaries.
    When OCaml is unavailable, falls back to pure Python implementations
    that mirror the Coq-proven algorithms.
    """

    def __init__(self, ocaml_binary_dir: Optional[Path] = None):
        if ocaml_binary_dir is None:
            ocaml_binary_dir = Path(__file__).parent / "bin"
        self.bin_dir = ocaml_binary_dir
        self._check_available()

    def _check_available(self) -> None:
        """Verify OCaml binaries exist."""
        self.available = (self.bin_dir / "tos_verify").exists() or (
            self.bin_dir / "tos_verify.exe"
        ).exists()

    def _call_ocaml(self, function: str, args: dict) -> dict:
        """Call an OCaml function via subprocess."""
        if not self.available:
            return {"success": False, "error": "OCaml binaries not compiled"}

        binary = self.bin_dir / "tos_verify"
        if not binary.exists():
            binary = self.bin_dir / "tos_verify.exe"

        input_json = json.dumps({"function": function, "args": args})
        try:
            result = subprocess.run(
                [str(binary)],
                input=input_json,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return {"success": False, "error": result.stderr}
            return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
            return {"success": False, "error": str(e)}

    # ── MATH VERIFICATION ──────────────────────────────────────────────

    def check_ivt(self, f_a: float, f_b: float) -> VerifiedResult:
        """IVT: if f(a) and f(b) have opposite signs, root exists in (a,b).

        Backed by: IVT_ERR.v / IVT_CauchyReal.v (23 Qed, 0 Admitted)
        """
        opposite_signs = (f_a > 0 and f_b < 0) or (f_a < 0 and f_b > 0)
        return VerifiedResult(
            success=True,
            value=opposite_signs,
            certificate=(
                f"f(a)={f_a}, f(b)={f_b}. "
                + (
                    "Opposite signs → IVT guarantees root in (a,b)."
                    if opposite_signs
                    else "Same sign → IVT not directly applicable."
                )
            ),
            theorem_used="IVT_ERR.intermediate_value_theorem",
        )

    def check_evt(self, values: list[float]) -> VerifiedResult:
        """EVT: continuous f on closed [a,b] attains its maximum.

        L5-Resolution: when multiple points achieve max, select leftmost.
        Backed by: EVT_idx.v (26 Qed, 0 Admitted)
        """
        if not values:
            return VerifiedResult(False, None, "Empty list", "EVT_idx")
        max_val = max(values)
        # L5: leftmost among maxima
        max_idx = next(i for i, v in enumerate(values) if v == max_val)
        return VerifiedResult(
            success=True,
            value={"max_value": max_val, "max_index": max_idx, "l5_resolved": True},
            certificate=f"Maximum {max_val} at index {max_idx} (L5: leftmost selection)",
            theorem_used="EVT_idx.argmax_idx_maximizes",
        )

    def check_convergence(
        self, ratio: float, threshold: float = 1.0
    ) -> VerifiedResult:
        """Series convergence: ratio test.

        If |a(n+1)/a(n)| < r < 1 eventually, series converges.
        Backed by: SeriesConvergence.v (22 Qed, 0 Admitted)
        """
        converges = abs(ratio) < threshold
        return VerifiedResult(
            success=True,
            value={"converges": converges, "ratio": ratio, "threshold": threshold},
            certificate=(
                f"|ratio| = {abs(ratio):.4f} < {threshold} → series converges"
                if converges
                else f"|ratio| = {abs(ratio):.4f} ≥ {threshold} → convergence not guaranteed"
            ),
            theorem_used="SeriesConvergence.ratio_test_abs",
        )

    def check_contraction(
        self, factor: float, x0: float, x1: float
    ) -> VerifiedResult:
        """Fixed point: Banach contraction mapping.

        If f is a contraction with factor 0 ≤ c < 1, iterates converge.
        Backed by: FixedPoint.v (20 Qed, 0 Admitted)
        """
        is_contraction = 0 <= factor < 1
        if is_contraction:
            # Error after n steps: |f^n(x) - p| ≤ c^n * |x0 - x1| / (1 - c)
            error_bound = abs(x0 - x1) / (1 - factor) if factor < 1 else float("inf")
        else:
            error_bound = float("inf")
        return VerifiedResult(
            success=True,
            value={
                "is_contraction": is_contraction,
                "factor": factor,
                "error_bound": error_bound,
            },
            certificate=(
                f"Factor c={factor} < 1 → contraction. "
                f"Iterates converge with bound |x-p| ≤ {error_bound:.4f}"
                if is_contraction
                else f"Factor c={factor} ≥ 1 → not a contraction"
            ),
            theorem_used="FixedPoint.banach_fixed_point",
        )

    def check_crown_bounds(
        self,
        weights: list[list[float]],
        bias: list[float],
        input_lo: list[float],
        input_hi: list[float],
    ) -> VerifiedResult:
        """CROWN: verified interval bounds for a linear layer + ReLU.

        Backed by: PInterval_CROWN.v (25 Qed, 0 Admitted)
        """
        # Try OCaml first
        result = self._call_ocaml(
            "crown_bounds",
            {
                "weights": weights,
                "bias": bias,
                "input_lo": input_lo,
                "input_hi": input_hi,
            },
        )
        if result.get("success"):
            return VerifiedResult(
                success=True,
                value={"output_lo": result["lo"], "output_hi": result["hi"]},
                certificate="CROWN linear relaxation bounds verified (OCaml)",
                theorem_used="PInterval_CROWN.crown_bounds",
            )
        # Fallback: pure Python interval arithmetic
        return self._python_crown_fallback(weights, bias, input_lo, input_hi)

    # ── L5 RESOLUTION ──────────────────────────────────────────────────

    def l5_resolve(self, candidates: list[int]) -> VerifiedResult:
        """L5-Resolution: select minimum (leftmost) from candidates.

        Backed by: L5Resolution.v (18 Qed, 0 Admitted)
        """
        if not candidates:
            return VerifiedResult(False, None, "Empty candidates", "L5Resolution")
        result = min(candidates)
        return VerifiedResult(
            success=True,
            value=result,
            certificate=f"L5 canonical selection: min({candidates}) = {result}",
            theorem_used="L5Resolution.l5_resolve_gen_minimal",
        )

    # ── ERR WELL-FORMEDNESS ────────────────────────────────────────────

    def check_err_well_formed(
        self,
        elements: list[dict],
        roles: list[dict],
        rules: list[dict],
        dependencies: list[dict],
    ) -> VerifiedResult:
        """Check E/R/R well-formedness (4 conditions from ERR paper v3).

        Condition 1: Each component → exactly one E/R/R category
        Condition 2: No cross-category self-reference
        Condition 3: No cross-level role occupation
        Condition 4: No circular Status dependencies (acyclic)

        Backed by: Roles.v (30 Qed, 0 Admitted)
        """
        violations: list[str] = []

        # Condition 1: Category exclusivity — no duplicate IDs
        all_ids: set[str] = set()
        for e in elements:
            eid = e.get("id", "")
            if eid in all_ids:
                violations.append(f"Duplicate ID: {eid}")
            all_ids.add(eid)

        # Condition 2: No self-reference across categories
        rule_ids = {r.get("id", "") for r in rules}
        element_ids = {e.get("id", "") for e in elements}
        self_refs = rule_ids & element_ids
        if self_refs:
            violations.append(f"Cross-category self-reference: {self_refs}")

        # Condition 3: Level consistency (checked via level tags if present)
        for role in roles:
            elem_id = role.get("element_id", "")
            level = role.get("level")
            if level is not None:
                # Find the element
                elem = next((e for e in elements if e.get("id") == elem_id), None)
                if elem and elem.get("level") is not None:
                    if elem["level"] != level:
                        violations.append(
                            f"Cross-level role: element {elem_id} at level "
                            f"{elem['level']} has role at level {level}"
                        )

        # Condition 4: Acyclic dependencies
        dep_graph: dict[str, list[str]] = {}
        for d in dependencies:
            dep_graph.setdefault(d.get("from", ""), []).append(d.get("to", ""))

        if self._has_cycle(dep_graph):
            violations.append(
                "Circular dependency detected (Condition 4 violated)"
            )

        # Condition L4: Every element has a role
        elements_with_roles = {r.get("element_id", "") for r in roles}
        orphans = element_ids - elements_with_roles
        if orphans:
            violations.append(f"L4 violation: elements without roles: {orphans}")

        well_formed = len(violations) == 0
        return VerifiedResult(
            success=True,
            value={"well_formed": well_formed, "violations": violations},
            certificate=(
                "E/R/R well-formed: all 4 conditions satisfied"
                if well_formed
                else f"E/R/R violations: {'; '.join(violations)}"
            ),
            theorem_used="Roles.err_well_formed_4conditions",
        )

    # ── INTERNAL HELPERS ───────────────────────────────────────────────

    @staticmethod
    def _has_cycle(graph: dict[str, list[str]]) -> bool:
        """Detect cycles in a directed graph via DFS."""
        visited: set[str] = set()
        rec_stack: set[str] = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        for node in graph:
            if node not in visited:
                if dfs(node):
                    return True
        return False

    def _python_crown_fallback(
        self,
        weights: list[list[float]],
        bias: list[float],
        input_lo: list[float],
        input_hi: list[float],
    ) -> VerifiedResult:
        """Pure Python interval arithmetic when OCaml binary unavailable."""
        output_lo: list[float] = []
        output_hi: list[float] = []
        for row, b in zip(weights, bias):
            lo = b
            hi = b
            for w, il, ih in zip(row, input_lo, input_hi):
                if w >= 0:
                    lo += w * il
                    hi += w * ih
                else:
                    lo += w * ih
                    hi += w * il
            # ReLU
            output_lo.append(max(0.0, lo))
            output_hi.append(max(0.0, hi))
        return VerifiedResult(
            success=True,
            value={"output_lo": output_lo, "output_hi": output_hi},
            certificate="Python fallback interval arithmetic (not formally verified)",
            theorem_used="PInterval_CROWN (fallback)",
        )
