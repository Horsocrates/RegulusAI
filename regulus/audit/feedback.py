"""
Regulus AI - Feedback Generator
=================================

Builds targeted correction prompts that reference specific failed
domains, gates, and issues. Not generic "try again" — precise.
"""

from typing import Optional

from regulus.audit.types import AuditResult, AuditConfig, CorrectionFeedback


DOMAIN_NAMES = {
    "D1": "Recognition (What is actually here?)",
    "D2": "Clarification (What does it mean?)",
    "D3": "Framework Selection (Through which lens?)",
    "D4": "Comparison (What does the evidence show?)",
    "D5": "Inference (What follows?)",
    "D6": "Reflection (Is this right? What are the limits?)",
}

VIOLATION_DESCRIPTIONS = {
    "DOMAIN_SKIP": "A domain was not traversed at all — reasoning jumps over it",
    "ORDER_INVERSION": "Domains traversed in wrong order — conclusion before evidence or framework after evaluation (rationalization mechanism)",
    "PREMATURE_CLOSURE": "A domain was started but not completed — reasoning moves on too early",
    "FALSE_REFLECTION": "D6 exists but merely restates D5 without adding scope, assumptions, or limitations",
    "RATIONALIZATION": "Conclusion was predetermined and arguments were constructed to fit — D5 substance appears in D1/D2, D4 evidence is one-sided",
    "FRAMEWORK_AS_ELEMENT": "D3 framework was imported as given data, not consciously chosen — Rule masquerading as Element",
    "CONCLUSION_BEFORE_EVIDENCE": "D5 conclusion substance appears before D4 evidence — dependency reversal (L5 violation)",
    "RATIONALIZATION_AS_REFLECTION": "D6 confirms D5 without genuine analysis — Status self-referentially confirmed",
}

GATE_NAMES = {
    "err_complete": "ERRS (Element/Role/Rule/Status) structural completeness",
    "deps_valid": "Dependencies on prior domains explicitly declared",
    "levels_valid": "L1-L3 hierarchy (no self-referential loops)",
    "order_valid": "L5 Law of Order (D1→D6 sequence)",
}


class FeedbackGenerator:
    """Generates targeted correction prompts from audit results."""

    def __init__(self, config: AuditConfig):
        self.config = config

    def generate(
        self,
        audit: AuditResult,
        query: str,
        round_number: int,
    ) -> Optional[CorrectionFeedback]:
        """
        Generate correction feedback if the audit failed.

        Returns None if the audit passes (no correction needed).
        """
        if self.config.is_passing(audit):
            return None

        failed_domains = []
        failed_gates = []
        issues = []

        # Collect domain-specific failures
        for d in audit.domains:
            domain_issues = []

            if not d.present:
                failed_domains.append(d.domain)
                domain_issues.append(f"{d.domain} ({DOMAIN_NAMES.get(d.domain, '')}) is missing entirely")
                continue

            if not d.gate_passed:
                failed_gates.append(d.domain)
                gate = d.gate
                if not gate.err_complete:
                    if not d.e_exists:
                        domain_issues.append(f"{d.domain}: Missing concrete Element (identifiable object)")
                    if not d.r_exists:
                        domain_issues.append(f"{d.domain}: Missing functional Role (purpose)")
                    if not d.rule_exists:
                        domain_issues.append(f"{d.domain}: Missing logical Rule (connection)")
                    if not d.s_exists:
                        domain_issues.append(f"{d.domain}: Missing Status/States (possible states + current state)")
                if not gate.deps_valid:
                    domain_issues.append(f"{d.domain}: Dependencies on prior domains not declared")
                if not gate.levels_valid:
                    domain_issues.append(f"{d.domain}: Self-referential reasoning detected (L1-L3 violation)")
                if not gate.order_valid:
                    domain_issues.append(f"{d.domain}: Domain ordering violated (L5)")

            for issue in d.issues:
                domain_issues.append(f"{d.domain}: {issue}")

            issues.extend(domain_issues)

        # Add domain-specific diagnostic issues
        for d in audit.domains:
            if d.present:
                if d.d3_objectivity_pass is False:
                    issues.append(f"D3: OBJECTIVITY FAILURE — framework excludes possible answers a priori (rationalization, not investigation)")
                if d.d4_aristotle_ok is False:
                    issues.append(f"D4: Aristotle's comparison rules violated (same relation / same criterion / same time)")
                if d.d6_genuine is False:
                    issues.append(f"D6: Reflection is not genuine — merely restates D5 without adding scope/assumptions/limitations")

        # Add violation pattern issues
        for vp in audit.violation_patterns:
            desc = VIOLATION_DESCRIPTIONS.get(vp, vp)
            issues.append(f"VIOLATION [{vp}]: {desc}")

        # Add overall issues
        issues.extend(audit.overall_issues)

        # Build the correction prompt
        prompt_parts = [
            f"Your previous reasoning about the following question had structural issues "
            f"that need to be addressed (correction round {round_number}).",
            f"\nQUESTION: {query}",
            f"\nSTRUCTURAL ISSUES FOUND:",
        ]

        for i, issue in enumerate(issues[:10], 1):  # Cap at 10 issues
            prompt_parts.append(f"  {i}. {issue}")

        if failed_domains:
            prompt_parts.append(
                f"\nMISSING DOMAINS: {', '.join(failed_domains)}"
            )
            prompt_parts.append(
                "Please ensure your reasoning explicitly covers these domains:"
            )
            for d in failed_domains:
                prompt_parts.append(f"  - {DOMAIN_NAMES.get(d, d)}")

        if failed_gates:
            prompt_parts.append(
                f"\nFAILED STRUCTURAL GATES in: {', '.join(failed_gates)}"
            )
            prompt_parts.append(
                "For each domain, ensure you have:\n"
                "  - A concrete Element (what is the identifiable object?)\n"
                "  - A functional Role (what purpose does it serve?)\n"
                "  - A logical Rule (how are roles connected?)\n"
                "  - Defined States (what are the possible states and the current state?)\n"
                "  - Declared Dependencies (what prior domains/steps does this depend on?)"
            )

        if audit.violation_patterns:
            prompt_parts.append(
                f"\nVIOLATION PATTERNS DETECTED: {', '.join(audit.violation_patterns)}"
            )
            prompt_parts.append(
                "These indicate structural reasoning errors. Key corrections:"
            )
            if "ORDER_INVERSION" in audit.violation_patterns or "CONCLUSION_BEFORE_EVIDENCE" in audit.violation_patterns:
                prompt_parts.append("  - Ensure conclusions (D5) come AFTER evidence (D4), not before")
            if "RATIONALIZATION" in audit.violation_patterns:
                prompt_parts.append("  - Do not start with a predetermined conclusion — follow the evidence")
            if "FALSE_REFLECTION" in audit.violation_patterns or "RATIONALIZATION_AS_REFLECTION" in audit.violation_patterns:
                prompt_parts.append("  - D6 reflection must ADD something (scope, assumptions, limitations) — not just restate D5")
            if "FRAMEWORK_AS_ELEMENT" in audit.violation_patterns:
                prompt_parts.append("  - Explicitly choose and justify your framework in D3 — do not treat it as given data")

        prompt_parts.append(
            "\nPlease re-reason about the question, addressing all issues above. "
            "Think step by step through all six domains (D1-D6)."
        )

        return CorrectionFeedback(
            prompt="\n".join(prompt_parts),
            failed_domains=failed_domains,
            failed_gates=failed_gates,
            issues=issues,
            round_number=round_number,
        )
