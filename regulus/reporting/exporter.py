"""
Regulus AI - Report Exporter
==============================

Generates Markdown verification reports with formal proof sections.

Report structure:
    1. Header (query, timestamp, status)
    2. Reasoning Tree (ASCII in code fence)
    3. Formal Proof Section (Zero-Gate table + Coq invariants)
    4. Corrections Log
    5. Final Answer
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

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
        if response.primary_answer:
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
    # Helpers
    # ----------------------------------------------------------

    @staticmethod
    def _generate_filename(query: str) -> str:
        """Generate a safe filename from query + timestamp."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r"[^a-z0-9]+", "_", query.lower())[:40].strip("_")
        return f"{ts}_{slug}.md"
