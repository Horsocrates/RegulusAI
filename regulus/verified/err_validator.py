"""
err_validator.py — D1 E/R/R Structural Validator.

After D1 produces E/R/R output, validates it formally before D2 proceeds.
Checks the 4 well-formedness conditions from Roles.v (30 Qed, 0 Admitted).

If validation fails, returns specific violations and actionable suggestions
for re-running D1 with correction guidance.
"""

from __future__ import annotations

from typing import Optional

from regulus.verified.bridge import VerifiedBackend


class ERRValidator:
    """Validates D1's E/R/R output against formal well-formedness criteria.

    Uses VerifiedBackend.check_err_well_formed which implements the
    4 conditions from Roles.v (ERR paper v3, §7):

    Condition 1: Category exclusivity — each component has exactly one E/R/R category
    Condition 2: No cross-category self-reference
    Condition 3: No cross-level role occupation
    Condition 4: Acyclic dependencies (no circular status)
    + L4: Every element has a role
    """

    def __init__(self, backend: Optional[VerifiedBackend] = None):
        self.backend = backend or VerifiedBackend()

    def validate_d1_output(self, d1_output: dict) -> dict:
        """Validate D1 E/R/R structure.

        Args:
            d1_output: The D1 domain output containing elements, roles, rules,
                       dependencies, and err_hierarchy_check.

        Returns:
            {
                "valid": bool,
                "violations": list[str],
                "suggestions": list[str],
                "certificate": str
            }
        """
        elements = d1_output.get("elements", [])
        roles = d1_output.get("roles", [])
        rules = d1_output.get("rules", [])
        dependencies = d1_output.get("dependencies", [])

        # Formal check via verified backend
        result = self.backend.check_err_well_formed(
            elements, roles, rules, dependencies
        )

        violations = result.value.get("violations", [])
        suggestions = self._generate_suggestions(violations)

        # Cross-check with D1's own hierarchy check if present
        d1_self_check = d1_output.get("err_hierarchy_check", {})
        cross_check_issues = self._cross_check(d1_self_check, violations)

        return {
            "valid": result.value["well_formed"],
            "violations": violations,
            "suggestions": suggestions,
            "certificate": result.certificate,
            "cross_check": cross_check_issues,
        }

    def gate_d1_to_d2(self, d1_output: dict) -> dict:
        """Gate function: validates D1 and decides whether to proceed to D2.

        Returns:
            {"action": "proceed_to_d2", "d1_output": ...} on success
            {"action": "retry_d1", "reason": ..., "guidance": ...} on failure
        """
        check = self.validate_d1_output(d1_output)

        if not check["valid"]:
            return {
                "action": "retry_d1",
                "reason": check["violations"],
                "guidance": check["suggestions"],
            }

        # D1 passed — annotate with certificate and proceed
        d1_output["err_certificate"] = check["certificate"]
        return {"action": "proceed_to_d2", "d1_output": d1_output}

    def _generate_suggestions(self, violations: list[str]) -> list[str]:
        """Generate actionable suggestions for each violation."""
        suggestions: list[str] = []
        for v in violations:
            if "Circular" in v:
                suggestions.append(
                    "RETURN TO D1: Break the circular dependency. "
                    "Identify which element's status depends on itself "
                    "and introduce an intermediate step."
                )
            elif "without roles" in v:
                orphans = v.split(": ")[-1] if ": " in v else "unknown"
                suggestions.append(
                    "RETURN TO D1: Every element needs a role (L4). "
                    f"Assign roles to: {orphans}"
                )
            elif "self-reference" in v:
                suggestions.append(
                    "RETURN TO D1: An element cannot serve as its own rule. "
                    "Separate the element from the rule that governs it."
                )
            elif "Duplicate ID" in v:
                suggestions.append(
                    "RETURN TO D1: Each component must have a unique ID. "
                    "Rename the duplicate to distinguish the two components."
                )
            elif "Cross-level" in v:
                suggestions.append(
                    "RETURN TO D1: An element's role must be at the same level "
                    "as the element itself. Check level assignments."
                )
        return suggestions

    def _cross_check(
        self, d1_self_check: dict, formal_violations: list[str]
    ) -> list[str]:
        """Cross-check D1's own hierarchy check against formal validation.

        If D1 claims everything is fine but formal check found violations,
        flag the discrepancy (possible LLM hallucination in self-check).
        """
        issues: list[str] = []
        if not d1_self_check:
            return issues

        # D1 says "no circular dependencies" but we found one
        if d1_self_check.get("no_circular_dependencies") and any(
            "Circular" in v for v in formal_violations
        ):
            issues.append(
                "DISCREPANCY: D1 claims no circular dependencies, "
                "but formal check detected a cycle. "
                "D1's self-check may be hallucinated."
            )

        # D1 says "elements ground system" but we found orphans
        if d1_self_check.get("elements_ground_system") and any(
            "without roles" in v for v in formal_violations
        ):
            issues.append(
                "DISCREPANCY: D1 claims elements ground the system, "
                "but some elements lack roles. "
                "L4 (every element needs a role) is violated."
            )

        return issues
