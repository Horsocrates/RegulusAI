"""
Regulus AI - Report Exporter
==============================

Generates two types of reports:

1. INTERNAL report - Full reasoning process for developers:
   - Domain progression (D1→D6)
   - ERR analysis, TYPE classification
   - Weights, probes, corrections
   - Zero-Gate analysis

2. ANSWER report - Clean final answer for judge:
   - Question
   - Final answer only (no ERR tags, no process details)
   - Sources cited
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Tuple

from ..core.status_machine import run_all_verifications
from ..core.types import VerificationResult
from ..orchestrator import CorrectionAttempt, VerifiedResponse
from ..ui.console import render_ascii_tree


class ReportExporter:
    """Export verification results as Markdown reports."""

    def __init__(self, output_dir: Path = Path("reports")) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_markdown(
        self,
        query: str,
        response: VerifiedResponse,
        tree_repr: str | None = None,
    ) -> Path:
        """
        Write a full Markdown report to disk.

        Returns:
            Path to the written .md file.
        """
        if tree_repr is None:
            tree_repr = render_ascii_tree(response.result)

        sections = [
            self._build_header(query, response),
            self._build_tree_section(response.result, tree_repr),
            self._build_formal_proof_section(response.result),
        ]

        if response.corrections:
            sections.append(self._build_corrections_section(response.corrections))

        sections.append(self._build_answer_section(response))

        content = "\n\n---\n\n".join(sections)

        filename = self._generate_filename(query)
        filepath = self.output_dir / filename
        filepath.write_text(content, encoding="utf-8")

        return filepath

    def export_battle_markdown(
        self,
        query: str,
        raw_answer: str,
        response: VerifiedResponse,
        category: str = "Unknown",
        raw_duration: float = 0.0,
        guarded_duration: float = 0.0,
    ) -> Path:
        """
        Write a battle report (raw vs guarded) to disk.
        DEPRECATED: Use export_split_reports() for separate INTERNAL/ANSWER files.

        Returns:
            Path to the written .md file.
        """
        tree_repr = render_ascii_tree(response.result)

        sections = [
            self._build_battle_header(query, category, response),
            self._build_raw_section(raw_answer, raw_duration),
            self._build_guarded_section(response, tree_repr, guarded_duration),
        ]

        content = "\n\n---\n\n".join(sections)

        filename = self._generate_filename(query)
        filepath = self.output_dir / filename
        filepath.write_text(content, encoding="utf-8")

        return filepath

    def export_split_reports(
        self,
        query: str,
        raw_answer: str,
        response: VerifiedResponse,
        category: str = "Unknown",
        raw_duration: float = 0.0,
        guarded_duration: float = 0.0,
    ) -> Tuple[Path, Path]:
        """
        Export two separate reports: INTERNAL (process) and ANSWER (for judge).

        Returns:
            (internal_path, answer_path)
        """
        base_filename = self._generate_filename(query).replace(".md", "")

        # Export INTERNAL report (full process)
        internal_path = self._export_internal_report(
            query, raw_answer, response, category, raw_duration, guarded_duration, base_filename
        )

        # Export ANSWER report (clean for judge)
        answer_path = self._export_answer_report(
            query, raw_answer, response, category, base_filename
        )

        return internal_path, answer_path

    def _export_internal_report(
        self,
        query: str,
        raw_answer: str,
        response: VerifiedResponse,
        category: str,
        raw_duration: float,
        guarded_duration: float,
        base_filename: str,
    ) -> Path:
        """Export INTERNAL report with full reasoning process."""
        tree_repr = render_ascii_tree(response.result)

        lines = [
            "# Regulus AI — INTERNAL Process Report",
            "",
            f"**Question:** {query}",
            f"**Category:** {category}",
            f"**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Status:** {'PrimaryMax found' if response.is_valid else 'No valid PrimaryMax'}",
            "",
            "---",
            "",
            "## Domain Progression",
            "",
        ]

        # Add each domain's content with full details
        for step in response.reasoning_steps:
            domain = step.get("domain", "?")
            content = step.get("content", "")
            lines.append(f"### [{domain}]")
            lines.append("")
            lines.append(content)
            lines.append("")

        # Reasoning Tree
        lines.extend([
            "---",
            "",
            "## Reasoning Tree",
            "",
            "```",
            tree_repr,
            "```",
            "",
        ])

        # Zero-Gate Analysis
        lines.extend([
            "---",
            "",
            "## Zero-Gate Analysis",
            "",
            "| Node | ERR | Levels | Order | G_total | Weight | Diagnostic |",
            "|------|-----|--------|-------|---------|--------|------------|",
        ])

        for diag in response.result.diagnostics:
            err = diag.gate_vector.get("ERR", "N/A")
            levels = diag.gate_vector.get("Levels", "N/A")
            order = diag.gate_vector.get("Order", "N/A")
            g_total = diag.gate_vector.get("G_total", False)
            g_str = "PASS" if g_total else "FAIL"
            code = diag.diagnostic_code or "-"
            lines.append(
                f"| {diag.node_id} | {err} | {levels} | {order} "
                f"| {g_str} | {diag.final_weight} | {code} |"
            )

        # Corrections Log
        if response.corrections:
            lines.extend([
                "",
                "---",
                "",
                "## Corrections Log",
                "",
                "| Step | Attempt | Code | Result |",
                "|------|---------|------|--------|",
            ])
            for c in response.corrections:
                status = "OK" if c.success else "FAIL"
                lines.append(f"| {c.step_index} | {c.attempt} | {c.diagnostic_code} | {status} |")

        # Timing
        lines.extend([
            "",
            "---",
            "",
            "## Timing",
            "",
            f"- Raw Model: {raw_duration:.2f}s",
            f"- Regulus Guarded: {guarded_duration:.2f}s",
            f"- Overhead: {((guarded_duration / raw_duration - 1) * 100):.0f}%" if raw_duration > 0 else "- Overhead: N/A",
        ])

        content = "\n".join(lines)
        filepath = self.output_dir / f"{base_filename}_INTERNAL.md"
        filepath.write_text(content, encoding="utf-8")

        return filepath

    def _export_answer_report(
        self,
        query: str,
        raw_answer: str,
        response: VerifiedResponse,
        category: str,
        base_filename: str,
    ) -> Path:
        """Export ANSWER report with clean answers for judge."""
        # Extract clean final answer (no ERR tags)
        regulus_answer = self._extract_clean_answer(response)

        lines = [
            "# Regulus AI — ANSWER Report (For Judge)",
            "",
            f"**Question:** {query}",
            f"**Category:** {category}",
            f"**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "",
            "## Raw Model Answer",
            "",
            raw_answer,
            "",
            "---",
            "",
            "## Regulus Answer",
            "",
            regulus_answer,
            "",
            "---",
            "",
            f"**Regulus Status:** {'VALID (PrimaryMax found)' if response.is_valid else 'INVALID (No PrimaryMax)'}",
            f"**Corrections Applied:** {response.total_corrections}",
        ]

        content = "\n".join(lines)
        filepath = self.output_dir / f"{base_filename}_ANSWER.md"
        filepath.write_text(content, encoding="utf-8")

        return filepath

    def _extract_clean_answer(self, response) -> str:
        """
        Extract clean final answer without ERR tags or domain markers.

        Priority:
        1. response.final_answer (already clean)
        2. Extract conclusion from D5/D6 content
        3. Clean D5 content as fallback
        4. primary_answer as final fallback
        """
        # Best case: we have a clean final_answer
        if hasattr(response, 'final_answer') and response.final_answer:
            return response.final_answer

        # Try to extract conclusion paragraphs from D5 and D6
        conclusion_parts = []
        for step in response.reasoning_steps:
            domain = step.get("domain", "")
            content = step.get("content", "")

            if domain in ("D5", "D6"):
                # Look for conclusion sections
                conclusion_match = re.search(
                    r"\*\*CONCLUSION:\*\*\s*([\s\S]+?)(?:\n\n\*\*|\Z)",
                    content
                )
                if conclusion_match:
                    conclusion_parts.append(conclusion_match.group(1).strip())

                # Also look for "According to..." sentences
                according_match = re.search(
                    r"According to[^.]+\.[^\n]+",
                    content
                )
                if according_match and not conclusion_parts:
                    conclusion_parts.append(according_match.group(0).strip())

        if conclusion_parts:
            return self._clean_content("\n\n".join(conclusion_parts))

        # Fallback: get D5 content and clean it heavily
        for step in response.reasoning_steps:
            if step.get("domain") == "D5":
                content = step.get("content", "")
                return self._clean_content(content)

        # Final fallback to primary_answer
        if hasattr(response, 'primary_answer') and response.primary_answer:
            return self._clean_content(response.primary_answer)

        return "*No valid answer produced.*"

    @staticmethod
    def _clean_content(content: str) -> str:
        """Remove ERR tags and domain markers from content."""
        # Remove domain tags like [D1], [D2], etc.
        content = re.sub(r"\[D\d\]\s*", "", content)

        # Remove "DOMAIN Dx:" prefixes
        content = re.sub(r"(?:\*\*)?DOMAIN\s+D\d[^:]*:(?:\*\*)?\s*", "", content, flags=re.IGNORECASE)

        # Remove ERR format brackets: [E: ...], [R: ...], [RULE: ...]
        content = re.sub(r"\[E:\s*[^\]]+\]", "", content)
        content = re.sub(r"\[R:\s*[^\]]+\]", "", content)
        content = re.sub(r"\[RULE:\s*[^\]]+\]", "", content)

        # Remove framework headers like **INFERENCE FRAMEWORK:**, **PRIMARY INFERENCE:**
        content = re.sub(r"\*\*[A-Z][A-Z\s_]+:\*\*\s*", "", content)
        content = re.sub(r"\*\*[A-Z][A-Z\s_]+\*\*\s*", "", content)

        # Remove section headers with colons like "**GEOGRAPHIC CONCLUSION:**"
        content = re.sub(r"\*\*[A-Za-z\s]+:\*\*\s*", "", content)

        # Remove old format: "Element (E):", "Role (R):", "Rule:"
        content = re.sub(r"Element\s*(?:\([ER]\))?:\s*", "", content)
        content = re.sub(r"Role\s*(?:\([ER]\))?:\s*", "", content)
        content = re.sub(r"Rule:\s*", "", content)

        # Remove status tags like [CERTAINTY: X%], [CONFIRMED], etc.
        content = re.sub(r"\[CERTAINTY:\s*\d+%\]", "", content)
        content = re.sub(r"\[D\d\s+VALIDATED\]", "", content)
        content = re.sub(r"\[DIRECT LOGICAL CONCLUSION\][^\n]*", "", content)
        content = re.sub(r"\[CONFIRMED\]", "", content)
        content = re.sub(r"\[UPDATED\]", "", content)
        content = re.sub(r"\[UNCONFIRMED\]", "", content)

        # Remove "D4/D5 VALIDATION" lines
        content = re.sub(r"D\d\s+VALIDATION[^\n]*\n?", "", content, flags=re.IGNORECASE)

        # Clean up extra whitespace and blank lines
        content = re.sub(r"\n{3,}", "\n\n", content)
        content = re.sub(r"^\s*\n", "", content, flags=re.MULTILINE)
        content = content.strip()

        return content

    def export_pdf(self, *args, **kwargs) -> Path:
        """PDF export is not available (fpdf2 not in dependencies)."""
        raise NotImplementedError(
            "PDF export requires fpdf2. Install with: uv add fpdf2"
        )

    # ----------------------------------------------------------
    # Section builders
    # ----------------------------------------------------------

    @staticmethod
    def _build_header(query: str, response: VerifiedResponse) -> str:
        status = "PrimaryMax found" if response.is_valid else "No valid PrimaryMax"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return "\n".join([
            "# Regulus AI Verification Report",
            "",
            f"**Query:** {query}",
            f"**Timestamp:** {ts}",
            f"**Status:** {status}",
            f"**Corrections:** {response.total_corrections}",
        ])

    @staticmethod
    def _build_tree_section(result: VerificationResult, tree_repr: str) -> str:
        return "\n".join([
            "## Reasoning Tree",
            "",
            "```",
            tree_repr,
            "```",
        ])

    @staticmethod
    def _build_formal_proof_section(result: VerificationResult) -> str:
        lines = ["## Formal Proof Section", ""]

        # Zero-Gate triggers table
        lines.append("### Zero-Gate Analysis")
        lines.append("")
        lines.append("| Node | ERR | Levels | Order | G_total | Weight | Diagnostic |")
        lines.append("|------|-----|--------|-------|---------|--------|------------|")

        for diag in result.diagnostics:
            err = diag.gate_vector.get("ERR", "N/A")
            levels = diag.gate_vector.get("Levels", "N/A")
            order = diag.gate_vector.get("Order", "N/A")
            g_total = diag.gate_vector.get("G_total", False)
            g_str = "PASS" if g_total else "FAIL"
            code = diag.diagnostic_code or "-"
            lines.append(
                f"| {diag.node_id} | {err} | {levels} | {order} "
                f"| {g_str} | {diag.final_weight} | {code} |"
            )

        lines.append("")

        # Coq invariants checklist
        lines.append("### Coq-Proven Invariants")
        lines.append("")

        verifications = run_all_verifications(result.nodes)
        for prop_name, (passed, msg) in verifications.items():
            check = "x" if passed else " "
            lines.append(f"- [{check}] **{prop_name}**: {msg}")

        return "\n".join(lines)

    @staticmethod
    def _build_corrections_section(corrections: list[CorrectionAttempt]) -> str:
        lines = ["## Corrections Log", ""]
        lines.append("| Step | Attempt | Code | Result |")
        lines.append("|------|---------|------|--------|")
        for c in corrections:
            status = "OK" if c.success else "FAIL"
            lines.append(f"| {c.step_index} | {c.attempt} | {c.diagnostic_code} | {status} |")
        return "\n".join(lines)

    @staticmethod
    def _build_answer_section(response: VerifiedResponse) -> str:
        lines = ["## Final Answer", ""]

        # Prefer clean final_answer if available
        if response.final_answer:
            lines.append(response.final_answer)
        else:
            # Fallback: Extract D5 (inference) + D6 (reflection)
            answer_text = "\n\n".join(
                step.get("content", "")
                for step in response.reasoning_steps
                if step.get("domain", "") in ("D5", "D6")
            )

            if answer_text:
                lines.append(answer_text)
            elif response.primary_answer:
                lines.append(response.primary_answer)
            else:
                lines.append("*No valid answer produced.*")

        if response.alternatives:
            lines.append("")
            lines.append("### Alternatives")
            for alt in response.alternatives:
                lines.append(f"- {alt}")

        return "\n".join(lines)

    # ----------------------------------------------------------
    # Battle report builders
    # ----------------------------------------------------------

    @staticmethod
    def _build_battle_header(query: str, category: str, response: VerifiedResponse) -> str:
        status = "PrimaryMax found" if response.is_valid else "No valid PrimaryMax"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return "\n".join([
            "# Regulus AI — Battle Report",
            "",
            f"**Question:** {query}",
            f"**Category:** {category}",
            f"**Timestamp:** {ts}",
            f"**Status:** {status}",
        ])

    @staticmethod
    def _build_raw_section(raw_answer: str, duration: float) -> str:
        lines = [
            "## Raw Model",
            "",
            raw_answer,
            "",
            f"*Duration: {duration:.2f}s*",
        ]
        return "\n".join(lines)

    @staticmethod
    def _build_guarded_section(
        response: VerifiedResponse,
        tree_repr: str,
        duration: float,
    ) -> str:
        lines = [
            "## Regulus Guarded",
            "",
            "Reasoning Tree:",
            "```",
            tree_repr,
            "```",
            "",
        ]

        if response.is_valid:
            lines.append("Status: PrimaryMax FOUND")
            # Prefer clean final_answer if available
            if response.final_answer:
                answer = response.final_answer
            else:
                # Fallback: Extract all reasoning steps (D1-D6)
                answer_parts = []
                for step in response.reasoning_steps:
                    domain = step.get("domain", "?")
                    content = step.get("content", "")
                    if content:
                        answer_parts.append(f"[{domain}] {content}")
                answer = "\n".join(answer_parts) or response.primary_answer or ""
            lines.append(f"Answer: {answer}")
        else:
            lines.append("Status: NO PrimaryMax")

        lines.append("")
        lines.append(f"Corrections: {response.total_corrections}")
        lines.append(f"Invalid nodes: {response.result.invalid_count}")
        lines.append("")
        lines.append(f"*Duration: {duration:.2f}s*")

        return "\n".join(lines)

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------

    @staticmethod
    def _generate_filename(query: str) -> str:
        """Generate a safe filename from query + timestamp."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r"[^a-z0-9]+", "_", query.lower())[:40].strip("_")
        return f"{ts}_{slug}.md"
