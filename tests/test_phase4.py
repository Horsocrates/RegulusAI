"""
Regulus AI - Phase 4 Tests (UX & Battle Mode)
===============================================

Tests for:
- ReasoningTreeRenderer (Rich tree rendering)
- ReportExporter (Markdown report generation)
- BattleMode / BattleResult (side-by-side comparison)
"""

import pytest
import tempfile
from pathlib import Path
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

from rich.tree import Tree
from rich.panel import Panel
from rich.text import Text

from regulus.core.types import (
    Node, Status, Domain, GateSignals, RawScores, IntegrityGate,
    Diagnostic, VerificationResult,
)
from regulus.ui.renderer import ReasoningTreeRenderer
from regulus.reporting.exporter import ReportExporter
from regulus.battle import BattleMode, BattleResult
from regulus.orchestrator import VerifiedResponse, CorrectionAttempt


# ============================================================
# Fixtures
# ============================================================

def _make_node(
    node_id: str,
    parent_id: str | None,
    idx: int,
    weight: int,
    status: Status,
    valid: bool = True,
    domain: int = 1,
) -> Node:
    """Create a node with gate and status pre-set."""
    node = Node(
        node_id=node_id,
        parent_id=parent_id,
        entity_id=f"E_{idx}",
        content=f"Content for {node_id}",
        legacy_idx=idx,
        gate_signals=GateSignals(
            e_exists=True, r_exists=True, rule_exists=valid,
            l1_l3_ok=True, l5_ok=True,
        ),
        raw_scores=RawScores(struct_points=5, domain_points=5, current_domain=domain),
    )
    node.gate = IntegrityGate(
        err_complete=valid, levels_valid=valid, order_valid=valid,
    )
    node.final_weight = weight
    node.status = status
    return node


@pytest.fixture
def sample_result() -> VerificationResult:
    """A 3-node VerificationResult with one primary, one candidate, one invalid."""
    root = _make_node("root", None, 0, 28, Status.CANDIDATE, domain=1)
    step1 = _make_node("step_1", "root", 1, 35, Status.PRIMARY_MAX, domain=2)
    step2 = _make_node("step_2", "step_1", 2, 0, Status.INVALID, valid=False, domain=5)

    diags = [
        Diagnostic(
            node_id=n.node_id, entity_id=n.entity_id, status=n.status,
            gate_vector=n.gate.to_dict() if n.gate else {},
            final_weight=n.final_weight, diagnostic_code=None, reason=None,
        )
        for n in [root, step1, step2]
    ]
    # Set diagnostic code for the invalid node
    diags[2].diagnostic_code = "ERR_RULE"
    diags[2].reason = "Rule missing"

    return VerificationResult(
        nodes=[root, step1, step2],
        diagnostics=diags,
        primary_max=step1,
        secondary_max=[],
        historical_max=[],
        invalid_count=1,
    )


@pytest.fixture
def sample_response(sample_result) -> VerifiedResponse:
    """A VerifiedResponse wrapping the sample result."""
    return VerifiedResponse(
        query="Test query",
        result=sample_result,
        reasoning_steps=[
            {"domain": "D1", "content": "Content for root"},
            {"domain": "D2", "content": "Content for step_1"},
            {"domain": "D5", "content": "Content for step_2"},
        ],
        corrections=[
            CorrectionAttempt(
                step_index=2, attempt=1,
                original_content="bad content",
                diagnostic_code="ERR_RULE",
                fix_prompt="Add a rule",
                corrected_content=None,
                success=False,
            ),
        ],
    )


# ============================================================
# ReasoningTreeRenderer Tests
# ============================================================

class TestReasoningTreeRenderer:

    def test_render_final_returns_tree(self, sample_result):
        """render_final should return a rich.tree.Tree instance."""
        renderer = ReasoningTreeRenderer()
        tree = renderer.render_final(sample_result)
        assert isinstance(tree, Tree)

    def test_render_final_contains_all_nodes(self, sample_result):
        """The rendered tree should reference all node IDs."""
        renderer = ReasoningTreeRenderer()
        tree = renderer.render_final(sample_result)
        # Convert tree to string to check content
        from rich.console import Console
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=200)
        console.print(tree)
        output = buf.getvalue()
        assert "root" in output
        assert "step_1" in output
        assert "step_2" in output

    def test_format_rich_label_primary(self):
        """PrimaryMax label should contain the star symbol and 'PRIMARY'."""
        renderer = ReasoningTreeRenderer()
        node = _make_node("n1", None, 0, 50, Status.PRIMARY_MAX)
        label = renderer._format_rich_label(node)
        assert isinstance(label, Text)
        text = label.plain
        assert "PRIMARY" in text
        assert "n1" in text

    def test_format_rich_label_invalid(self):
        """Invalid label should contain error code."""
        renderer = ReasoningTreeRenderer()
        node = _make_node("n2", None, 1, 0, Status.INVALID, valid=False)
        label = renderer._format_rich_label(node)
        text = label.plain
        assert "ERR" in text
        assert "W:0" in text

    def test_format_rich_label_candidate(self):
        """Candidate label should show weight and domain."""
        renderer = ReasoningTreeRenderer()
        node = _make_node("n3", None, 2, 42, Status.CANDIDATE, domain=3)
        label = renderer._format_rich_label(node)
        text = label.plain
        assert "D3" in text
        assert "W:42" in text

    def test_format_rich_label_secondary(self):
        """SecondaryMax label should contain 'SECONDARY'."""
        renderer = ReasoningTreeRenderer()
        node = _make_node("n4", None, 3, 35, Status.SECONDARY_MAX)
        label = renderer._format_rich_label(node)
        assert "SECONDARY" in label.plain

    def test_show_domain_panel(self):
        """show_domain_panel should return a Panel with the domain question."""
        renderer = ReasoningTreeRenderer()
        panel = renderer.show_domain_panel(Domain.D1_RECOGNITION)
        assert isinstance(panel, Panel)

    def test_render_to_console_runs(self, sample_result):
        """render_to_console should not raise."""
        renderer = ReasoningTreeRenderer()
        # Redirect to string buffer
        buf = StringIO()
        from rich.console import Console
        renderer._console = Console(file=buf, force_terminal=True, width=200)
        renderer.render_to_console(sample_result)
        output = buf.getvalue()
        assert "Regulus AI Verification" in output
        assert "step_1" in output


# ============================================================
# ReportExporter Tests
# ============================================================

class TestReportExporter:

    def test_export_markdown_creates_file(self, sample_response):
        """export_markdown should create a .md file in the output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = ReportExporter(output_dir=Path(tmpdir))
            path = exporter.export_markdown("Test query", sample_response)
            assert path.exists()
            assert path.suffix == ".md"

    def test_markdown_contains_header(self, sample_response):
        """Report should contain the query and status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = ReportExporter(output_dir=Path(tmpdir))
            path = exporter.export_markdown("Test query", sample_response)
            content = path.read_text(encoding="utf-8")
            assert "# Regulus AI Verification Report" in content
            assert "Test query" in content
            assert "PrimaryMax found" in content

    def test_markdown_contains_formal_proof(self, sample_response):
        """Report should contain the Coq invariants checklist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = ReportExporter(output_dir=Path(tmpdir))
            path = exporter.export_markdown("Test query", sample_response)
            content = path.read_text(encoding="utf-8")
            assert "## Formal Proof Section" in content
            assert "uniqueness" in content
            assert "stability" in content
            assert "zero_gate_law" in content

    def test_markdown_contains_tree(self, sample_response):
        """Report should contain the ASCII tree in a code fence."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = ReportExporter(output_dir=Path(tmpdir))
            path = exporter.export_markdown("Test query", sample_response)
            content = path.read_text(encoding="utf-8")
            assert "## Reasoning Tree" in content
            assert "```" in content
            assert "root" in content

    def test_markdown_contains_corrections(self, sample_response):
        """Report should contain the corrections log when corrections exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = ReportExporter(output_dir=Path(tmpdir))
            path = exporter.export_markdown("Test query", sample_response)
            content = path.read_text(encoding="utf-8")
            assert "## Corrections Log" in content
            assert "ERR_RULE" in content

    def test_markdown_contains_answer(self, sample_response):
        """Report should contain the final answer section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = ReportExporter(output_dir=Path(tmpdir))
            path = exporter.export_markdown("Test query", sample_response)
            content = path.read_text(encoding="utf-8")
            assert "## Final Answer" in content

    def test_export_pdf_raises(self):
        """export_pdf should raise NotImplementedError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = ReportExporter(output_dir=Path(tmpdir))
            with pytest.raises(NotImplementedError):
                exporter.export_pdf()


# ============================================================
# BattleMode Tests
# ============================================================

class TestBattleResult:

    def test_battle_result_fields(self, sample_response):
        """BattleResult should store all fields correctly."""
        result = BattleResult(
            query="test",
            raw_response="raw answer",
            guarded=sample_response,
            raw_duration=1.5,
            guarded_duration=5.0,
        )
        assert result.query == "test"
        assert result.raw_response == "raw answer"
        assert result.guarded is sample_response
        assert result.raw_duration == 1.5
        assert result.guarded_duration == 5.0


class TestBattleMode:

    def test_render_comparison_runs(self, sample_response):
        """render_comparison should not raise and should produce output."""
        result = BattleResult(
            query="test query",
            raw_response="The ball costs $0.10.",
            guarded=sample_response,
            raw_duration=0.8,
            guarded_duration=4.2,
        )

        mock_client = MagicMock()
        mock_orchestrator = MagicMock()
        bm = BattleMode(orchestrator=mock_orchestrator, llm_client=mock_client)

        buf = StringIO()
        from rich.console import Console
        bm._console = Console(file=buf, force_terminal=True, width=200)
        bm.render_comparison(result)
        output = buf.getvalue()
        assert "BATTLE MODE" in output
        assert "Raw Model" in output
        assert "Regulus Guarded" in output

    def test_annihilation_banner_shown(self, sample_response):
        """Banner should appear when corrections > 0 and is_valid."""
        # sample_response has 1 correction and is_valid=True
        result = BattleResult(
            query="test",
            raw_response="wrong",
            guarded=sample_response,
            raw_duration=1.0,
            guarded_duration=3.0,
        )

        mock_client = MagicMock()
        mock_orchestrator = MagicMock()
        bm = BattleMode(orchestrator=mock_orchestrator, llm_client=mock_client)

        buf = StringIO()
        from rich.console import Console
        bm._console = Console(file=buf, force_terminal=True, width=200)
        bm.render_comparison(result)
        output = buf.getvalue()
        assert "HALLUCINATION ANNIHILATED" in output

    def test_no_banner_without_corrections(self):
        """Banner should NOT appear when there are no corrections."""
        # Build a response with 0 corrections
        node = _make_node("root", None, 0, 50, Status.PRIMARY_MAX)
        diag = Diagnostic(
            node_id="root", entity_id="E_0", status=Status.PRIMARY_MAX,
            gate_vector={"ERR": "OK", "Levels": "OK", "Order": "OK", "G_total": True},
            final_weight=50,
        )
        vr = VerificationResult(
            nodes=[node], diagnostics=[diag],
            primary_max=node, secondary_max=[], historical_max=[], invalid_count=0,
        )
        response = VerifiedResponse(
            query="clean query", result=vr,
            reasoning_steps=[{"domain": "D1", "content": "ok"}],
            corrections=[],
        )
        result = BattleResult(
            query="clean query", raw_response="answer",
            guarded=response, raw_duration=1.0, guarded_duration=2.0,
        )

        mock_client = MagicMock()
        mock_orchestrator = MagicMock()
        bm = BattleMode(orchestrator=mock_orchestrator, llm_client=mock_client)

        buf = StringIO()
        from rich.console import Console
        bm._console = Console(file=buf, force_terminal=True, width=200)
        bm.render_comparison(result)
        output = buf.getvalue()
        assert "HALLUCINATION ANNIHILATED" not in output

    @pytest.mark.asyncio
    async def test_run_battle_calls_both(self):
        """run_battle should call both raw and guarded paths."""
        # Mock LLM client
        mock_client = AsyncMock()
        mock_client.generate.return_value = "Raw response"

        # Mock orchestrator
        mock_orchestrator = MagicMock()
        node = _make_node("root", None, 0, 50, Status.PRIMARY_MAX)
        diag = Diagnostic(
            node_id="root", entity_id="E_0", status=Status.PRIMARY_MAX,
            gate_vector={}, final_weight=50,
        )
        vr = VerificationResult(
            nodes=[node], diagnostics=[diag],
            primary_max=node, secondary_max=[], historical_max=[], invalid_count=0,
        )
        mock_response = VerifiedResponse(
            query="q", result=vr,
            reasoning_steps=[], corrections=[],
        )
        mock_orchestrator.process_query = AsyncMock(return_value=mock_response)

        bm = BattleMode(orchestrator=mock_orchestrator, llm_client=mock_client)
        result = await bm.run_battle("test query")

        assert result.raw_response == "Raw response"
        assert result.guarded is mock_response
        assert result.raw_duration >= 0
        assert result.guarded_duration >= 0
        mock_client.generate.assert_called_once()
        mock_orchestrator.process_query.assert_called_once_with("test query")
