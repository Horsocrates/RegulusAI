"""
Regulus AI - v2 Audit Pipeline Test Suite
==========================================

Tests for the reasoning → audit → correct pipeline.
All tests use mocks (no API keys needed).
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Optional

import pytest

from regulus.reasoning.provider import (
    TraceFormat,
    ReasoningResult,
    ReasoningProvider,
)
from regulus.reasoning.factory import get_provider
from regulus.llm.client import LLMClient, LLMResponse
from regulus.audit.types import (
    TraceSegment,
    ParsedTrace,
    DomainAuditResult,
    AuditResult,
    AuditConfig,
    CorrectionFeedback,
    V2Response,
)
from regulus.audit.auditor import Auditor, _parse_audit_response, _build_audit_prompt
from regulus.audit.zero_gate import compute_audit_gate, compute_audit_total_gate
from regulus.audit.feedback import FeedbackGenerator
from regulus.audit.orchestrator import AuditOrchestrator
from regulus.lab.models import LabDB, Run
from regulus.lab.benchmark_v2 import compare_runs


# ============================================================
# Mock Helpers
# ============================================================

class MockReasoningProvider(ReasoningProvider):
    """Mock reasoning provider returning configurable results."""

    def __init__(
        self,
        answer: str = "42",
        thinking: str = "I thought about it.",
        trace_format: TraceFormat = TraceFormat.FULL_COT,
        call_count_tracker: list | None = None,
    ):
        self._answer = answer
        self._thinking = thinking
        self._trace_format = trace_format
        self._calls = call_count_tracker if call_count_tracker is not None else []

    @property
    def name(self) -> str:
        return "mock"

    @property
    def default_trace_format(self) -> TraceFormat:
        return self._trace_format

    async def reason(self, query: str, system: Optional[str] = None) -> ReasoningResult:
        self._calls.append(query)
        return ReasoningResult(
            answer=self._answer,
            thinking=self._thinking,
            trace_format=self._trace_format,
            model="mock-v1",
            input_tokens=100,
            output_tokens=200,
            time_seconds=0.5,
        )


def _make_audit_json(
    weights: list[int] | None = None,
    present: list[bool] | None = None,
    err_signals: list[dict] | None = None,
    parse_quality: float = 0.9,
    violation_patterns: list[str] | None = None,
) -> str:
    """Build a mock audit JSON response."""
    if weights is None:
        weights = [75, 75, 75, 75, 75, 75]
    if present is None:
        present = [True] * 6

    domains = []
    for i in range(6):
        d = {
            "domain": f"D{i+1}",
            "present": present[i],
            "e_exists": present[i],
            "r_exists": present[i],
            "rule_exists": present[i],
            "s_exists": present[i],
            "deps_declared": present[i],
            "l1_l3_ok": True,
            "l5_ok": True,
            "issues": [] if present[i] else [f"D{i+1} missing"],
            "weight": weights[i] if present[i] else 0,
            "segment_summary": f"D{i+1} content" if present[i] else "",
        }
        if err_signals and i < len(err_signals) and err_signals[i] is not None:
            d.update(err_signals[i])
        domains.append(d)

    return json.dumps({
        "domains": domains,
        "overall_issues": [],
        "violation_patterns": violation_patterns or [],
        "parse_quality": parse_quality,
    })


class MockAuditLLM(LLMClient):
    """Mock LLM that returns configurable audit JSON."""

    def __init__(self, responses: list[str] | None = None):
        self._responses = responses or [_make_audit_json()]
        self._call_idx = 0

    async def generate(self, prompt: str, system: str | None = None) -> str:
        r = await self.generate_with_usage(prompt, system)
        return r.text

    async def generate_with_usage(self, prompt: str, system: str | None = None) -> LLMResponse:
        idx = min(self._call_idx, len(self._responses) - 1)
        self._call_idx += 1
        return LLMResponse(
            text=self._responses[idx],
            input_tokens=50,
            output_tokens=150,
        )


# ============================================================
# Phase 0: Types
# ============================================================

class TestTypes:
    def test_trace_segment(self):
        seg = TraceSegment(domain="D1", content="test", summary="sum")
        assert seg.domain == "D1"

    def test_parsed_trace_missing(self):
        pt = ParsedTrace(
            segments=[TraceSegment(domain="D1"), TraceSegment(domain="D3")],
            parse_quality=0.5,
        )
        assert "D1" in pt.domains_present
        assert "D2" in pt.domains_missing
        assert "D4" in pt.domains_missing

    def test_domain_audit_result_gate(self):
        d = DomainAuditResult(
            domain="D1", present=True,
            e_exists=True, r_exists=True, rule_exists=True,
            s_exists=True, deps_declared=True,
        )
        assert d.gate_passed is True

        d2 = DomainAuditResult(
            domain="D2", present=True,
            e_exists=False, r_exists=True, rule_exists=True,
            s_exists=True, deps_declared=True,
        )
        assert d2.gate_passed is False

    def test_audit_result_properties(self):
        result = AuditResult(
            domains=[
                DomainAuditResult(domain="D1", present=True, e_exists=True, r_exists=True, rule_exists=True, s_exists=True, deps_declared=True, weight=80),
                DomainAuditResult(domain="D2", present=False, weight=0),
            ],
            parse_quality=0.7,
        )
        assert result.total_weight == 80
        assert result.domains_present == ["D1"]
        assert "D2" in result.domains_missing
        assert result.all_gates_passed is True  # D2 not present, so not counted as failed

    def test_audit_result_failed_gates(self):
        result = AuditResult(
            domains=[
                DomainAuditResult(domain="D1", present=True, e_exists=True, r_exists=True, rule_exists=True, s_exists=True, deps_declared=True, weight=80),
                DomainAuditResult(domain="D2", present=True, e_exists=False, r_exists=True, rule_exists=True, s_exists=True, deps_declared=True, weight=0),
            ],
        )
        assert result.failed_gates == ["D2"]
        assert result.all_gates_passed is False

    def test_audit_config_passing(self):
        config = AuditConfig(min_domains=2, weight_threshold=50, err_required=True)
        passing = AuditResult(
            domains=[
                DomainAuditResult(domain=f"D{i}", present=True, e_exists=True, r_exists=True, rule_exists=True, s_exists=True, deps_declared=True, weight=30)
                for i in range(1, 7)
            ],
        )
        assert config.is_passing(passing) is True

        failing = AuditResult(
            domains=[
                DomainAuditResult(domain="D1", present=True, e_exists=True, r_exists=True, rule_exists=True, s_exists=True, deps_declared=True, weight=20),
            ],
        )
        assert config.is_passing(failing) is False  # only 1 domain present

    def test_v2_response_json_serialization(self):
        resp = V2Response(
            query="test",
            answer="42",
            valid=True,
            reasoning_model="deepseek-reasoner",
            trace_format="full_cot",
            audit_rounds=1,
        )
        data = json.loads(resp.reasoning_json)
        assert data["version"] == "2.0"
        assert data["reasoning_model"] == "deepseek-reasoner"
        assert data["trace_format"] == "full_cot"

    def test_v2_response_to_dict(self):
        resp = V2Response(query="q", answer="a", valid=False)
        d = resp.to_dict()
        assert d["query"] == "q"
        assert d["valid"] is False

    def test_correction_feedback(self):
        fb = CorrectionFeedback(
            prompt="Fix D3",
            failed_domains=["D3"],
            failed_gates=["D3"],
            issues=["No modeling"],
            round_number=1,
        )
        assert fb.round_number == 1
        assert "D3" in fb.failed_domains


# ============================================================
# Phase 1: Reasoning Providers
# ============================================================

class TestReasoningProviders:
    def test_factory_deepseek(self):
        p = get_provider("deepseek", api_key="test")
        assert p.name == "deepseek"
        assert p.default_trace_format == TraceFormat.FULL_COT

    def test_factory_claude(self):
        p = get_provider("claude-thinking", api_key="test")
        assert p.name == "claude-thinking"
        assert p.default_trace_format == TraceFormat.SUMMARY

    def test_factory_openai(self):
        p = get_provider("openai-reasoning", api_key="test")
        assert p.name == "openai-reasoning"
        assert p.default_trace_format == TraceFormat.NONE

    def test_factory_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown reasoning provider"):
            get_provider("unknown", api_key="test")

    def test_reasoning_result_has_trace(self):
        r = ReasoningResult(answer="a", thinking="t", trace_format=TraceFormat.FULL_COT)
        assert r.has_trace is True

        r2 = ReasoningResult(answer="a", thinking="", trace_format=TraceFormat.FULL_COT)
        assert r2.has_trace is False

        r3 = ReasoningResult(answer="a", thinking="t", trace_format=TraceFormat.NONE)
        assert r3.has_trace is False

    def test_reasoning_result_total_tokens(self):
        r = ReasoningResult(
            answer="a", input_tokens=100, output_tokens=200, reasoning_tokens=50,
        )
        assert r.total_tokens == 350


# ============================================================
# Phase 2: Auditor
# ============================================================

class TestAuditor:
    def test_parse_good_response(self):
        result = _parse_audit_response(_make_audit_json())
        assert len(result.domains) == 6
        assert result.all_gates_passed is True
        assert result.parse_quality == 0.9

    def test_parse_missing_domain(self):
        result = _parse_audit_response(_make_audit_json(
            present=[True, True, False, True, True, True],
            weights=[80, 75, 0, 70, 85, 60],
        ))
        assert "D3" in result.domains_missing
        assert result.total_weight == 370

    def test_parse_self_referential(self):
        result = _parse_audit_response(_make_audit_json(
            err_signals=[
                None, None, None, None,
                {"l1_l3_ok": False, "issues": ["Self-reference"], "weight": 0},
                None,
            ],
        ))
        assert "D5" in result.failed_gates

    def test_parse_markdown_wrapped(self):
        raw = "```json\n" + _make_audit_json() + "\n```"
        result = _parse_audit_response(raw)
        assert len(result.domains) == 6

    def test_parse_fills_missing_domains(self):
        """If LLM only returns D1-D3, parser should fill D4-D6."""
        partial = json.dumps({
            "domains": [
                {"domain": f"D{i}", "present": True, "e_exists": True, "r_exists": True,
                 "rule_exists": True, "l1_l3_ok": True, "l5_ok": True,
                 "issues": [], "weight": 70, "segment_summary": ""}
                for i in range(1, 4)
            ],
            "overall_issues": [],
            "parse_quality": 0.5,
        })
        result = _parse_audit_response(partial)
        assert len(result.domains) == 6
        assert result.domains[3].present is False  # D4 was filled

    def test_parse_d1_deps_always_true(self):
        """D1 is root domain — parser should force deps_declared=True even if LLM says false."""
        raw_json = json.dumps({
            "domains": [
                {"domain": "D1", "present": True, "e_exists": True, "r_exists": True,
                 "rule_exists": True, "s_exists": True, "deps_declared": False,
                 "l1_l3_ok": True, "l5_ok": True,
                 "issues": [], "weight": 75, "segment_summary": "root"},
                {"domain": "D2", "present": True, "e_exists": True, "r_exists": True,
                 "rule_exists": True, "s_exists": True, "deps_declared": True,
                 "l1_l3_ok": True, "l5_ok": True,
                 "issues": [], "weight": 80, "segment_summary": ""},
            ],
            "overall_issues": [],
            "parse_quality": 0.8,
        })
        result = _parse_audit_response(raw_json)
        d1 = result.domains[0]
        assert d1.domain == "D1"
        assert d1.deps_declared is True  # Forced true by parser
        assert d1.gate_passed is True

    def test_parse_invalid_json_raises(self):
        """_parse_audit_response raises on invalid JSON; Auditor.audit() catches it."""
        with pytest.raises(json.JSONDecodeError):
            _parse_audit_response("not valid json {{{")

    def test_build_prompt_full_cot(self):
        prompt = _build_audit_prompt("q", "trace", "answer", TraceFormat.FULL_COT)
        assert "full chain-of-thought" in prompt

    def test_build_prompt_summary(self):
        prompt = _build_audit_prompt("q", "trace", "answer", TraceFormat.SUMMARY)
        assert "condensed summary" in prompt

    def test_build_prompt_none(self):
        prompt = _build_audit_prompt("q", "", "answer", TraceFormat.NONE)
        assert "No reasoning trace" in prompt

    @pytest.mark.asyncio
    async def test_auditor_cache(self):
        """Same input should hit cache on second call."""
        llm = MockAuditLLM()
        auditor = Auditor(llm)

        r1 = await auditor.audit("trace", "answer", "query")
        r2 = await auditor.audit("trace", "answer", "query")

        assert llm._call_idx == 1  # Only one LLM call
        assert r1.parse_quality == r2.parse_quality

    @pytest.mark.asyncio
    async def test_auditor_different_input_no_cache(self):
        llm = MockAuditLLM()
        auditor = Auditor(llm)

        await auditor.audit("trace1", "answer", "query")
        await auditor.audit("trace2", "answer", "query")

        assert llm._call_idx == 2

    @pytest.mark.asyncio
    async def test_auditor_clear_cache(self):
        llm = MockAuditLLM()
        auditor = Auditor(llm)

        await auditor.audit("trace", "answer", "query")
        auditor.clear_cache()
        await auditor.audit("trace", "answer", "query")

        assert llm._call_idx == 2

    @pytest.mark.asyncio
    async def test_auditor_handles_bad_llm_response(self):
        """Auditor should return fallback result on parse failure."""
        llm = MockAuditLLM(responses=["not json at all"])
        auditor = Auditor(llm)

        result = await auditor.audit("trace", "answer", "query")
        assert result.parse_quality == 0.0
        assert len(result.overall_issues) > 0


# ============================================================
# Phase 3: Zero-Gate + Feedback
# ============================================================

class TestZeroGateAudit:
    def test_passing_gate(self):
        d = DomainAuditResult(
            domain="D1", present=True,
            e_exists=True, r_exists=True, rule_exists=True,
            s_exists=True, deps_declared=True,
        )
        gate = compute_audit_gate(d)
        assert gate.is_valid is True

    def test_missing_element(self):
        d = DomainAuditResult(
            domain="D2", present=True,
            e_exists=False, r_exists=True, rule_exists=True,
            s_exists=True, deps_declared=True,
        )
        gate = compute_audit_gate(d)
        assert gate.err_complete is False
        assert gate.is_valid is False

    def test_missing_role(self):
        d = DomainAuditResult(
            domain="D3", present=True,
            e_exists=True, r_exists=False, rule_exists=True,
            s_exists=True, deps_declared=True,
        )
        gate = compute_audit_gate(d)
        assert gate.err_complete is False

    def test_missing_rule(self):
        d = DomainAuditResult(
            domain="D4", present=True,
            e_exists=True, r_exists=True, rule_exists=False,
            s_exists=True, deps_declared=True,
        )
        gate = compute_audit_gate(d)
        assert gate.err_complete is False

    def test_missing_status(self):
        d = DomainAuditResult(
            domain="D1", present=True,
            e_exists=True, r_exists=True, rule_exists=True,
            s_exists=False, deps_declared=True,
        )
        gate = compute_audit_gate(d)
        assert gate.err_complete is False
        assert gate.is_valid is False

    def test_missing_deps(self):
        d = DomainAuditResult(
            domain="D3", present=True,
            e_exists=True, r_exists=True, rule_exists=True,
            s_exists=True, deps_declared=False,
        )
        gate = compute_audit_gate(d)
        assert gate.deps_valid is False
        assert gate.is_valid is False

    def test_levels_violation(self):
        d = DomainAuditResult(
            domain="D5", present=True,
            e_exists=True, r_exists=True, rule_exists=True,
            s_exists=True, deps_declared=True,
            l1_l3_ok=False,
        )
        gate = compute_audit_gate(d)
        assert gate.levels_valid is False
        assert gate.is_valid is False

    def test_order_violation(self):
        d = DomainAuditResult(
            domain="D6", present=True,
            e_exists=True, r_exists=True, rule_exists=True,
            s_exists=True, deps_declared=True,
            l5_ok=False,
        )
        gate = compute_audit_gate(d)
        assert gate.order_valid is False
        assert gate.is_valid is False

    def test_total_gate_with_config(self):
        config = AuditConfig(min_domains=4, weight_threshold=200)
        result = AuditResult(
            domains=[
                DomainAuditResult(domain=f"D{i}", present=True, e_exists=True, r_exists=True, rule_exists=True, s_exists=True, deps_declared=True, weight=60)
                for i in range(1, 7)
            ],
        )
        assert compute_audit_total_gate(result, config) is True


class TestFeedback:
    def test_no_feedback_on_passing(self):
        config = AuditConfig(min_domains=2, weight_threshold=50)
        fg = FeedbackGenerator(config)
        passing = AuditResult(
            domains=[
                DomainAuditResult(domain=f"D{i}", present=True, e_exists=True, r_exists=True, rule_exists=True, s_exists=True, deps_declared=True, weight=30)
                for i in range(1, 7)
            ],
        )
        assert fg.generate(passing, "q", 1) is None

    def test_feedback_on_missing_domains(self):
        config = AuditConfig(min_domains=4, weight_threshold=100)
        fg = FeedbackGenerator(config)
        failing = AuditResult(
            domains=[
                DomainAuditResult(domain="D1", present=True, e_exists=True, r_exists=True, rule_exists=True, s_exists=True, deps_declared=True, weight=80),
                DomainAuditResult(domain="D2", present=False, weight=0),
                DomainAuditResult(domain="D3", present=False, weight=0),
                DomainAuditResult(domain="D4", present=False, weight=0),
                DomainAuditResult(domain="D5", present=True, e_exists=True, r_exists=True, rule_exists=True, s_exists=True, deps_declared=True, weight=80),
                DomainAuditResult(domain="D6", present=False, weight=0),
            ],
        )
        fb = fg.generate(failing, "What is 2+2?", 1)
        assert fb is not None
        assert "D2" in fb.failed_domains
        assert "D3" in fb.failed_domains
        assert "MISSING DOMAINS" in fb.prompt

    def test_feedback_on_gate_failure(self):
        config = AuditConfig(min_domains=1, weight_threshold=0, err_required=True)
        fg = FeedbackGenerator(config)
        failing = AuditResult(
            domains=[
                DomainAuditResult(domain="D1", present=True, e_exists=False, r_exists=True, rule_exists=True, s_exists=True, deps_declared=True, weight=0),
            ],
        )
        fb = fg.generate(failing, "q", 1)
        assert fb is not None
        assert "D1" in fb.failed_gates
        assert "Element" in fb.prompt

    def test_feedback_round_number(self):
        config = AuditConfig(min_domains=6)
        fg = FeedbackGenerator(config)
        failing = AuditResult(
            domains=[DomainAuditResult(domain="D1", present=True, e_exists=True, r_exists=True, rule_exists=True, s_exists=True, deps_declared=True, weight=50)],
        )
        fb = fg.generate(failing, "q", 3)
        assert fb.round_number == 3
        assert "correction round 3" in fb.prompt


# ============================================================
# Phase 4: AuditOrchestrator
# ============================================================

class TestAuditOrchestrator:
    @pytest.mark.asyncio
    async def test_passing_first_try(self):
        """Audit passes on first try — no corrections."""
        orch = AuditOrchestrator(
            reasoning_provider=MockReasoningProvider(),
            audit_llm=MockAuditLLM(),
            config=AuditConfig(min_domains=4, weight_threshold=60),
        )
        result = await orch.process_query("What is 2+2?")

        assert result.valid is True
        assert result.audit_rounds == 1
        assert len(result.corrections) == 0
        assert result.reasoning_model == "mock-v1"
        assert result.answer == "42"

    @pytest.mark.asyncio
    async def test_correction_loop(self):
        """First audit fails, correction succeeds."""
        failing_audit = _make_audit_json(
            present=[True, False, False, False, True, False],
            weights=[40, 0, 0, 0, 50, 0],
            parse_quality=0.3,
        )
        passing_audit = _make_audit_json()

        orch = AuditOrchestrator(
            reasoning_provider=MockReasoningProvider(),
            audit_llm=MockAuditLLM(responses=[failing_audit, passing_audit]),
            config=AuditConfig(min_domains=4, weight_threshold=200, max_corrections=2),
        )
        result = await orch.process_query("test")

        assert result.valid is True
        assert result.audit_rounds == 2
        assert len(result.corrections) == 1

    @pytest.mark.asyncio
    async def test_early_abort_no_improvement(self):
        """Correction doesn't improve weight — aborts early."""
        stagnant_audit = _make_audit_json(
            present=[True, False, False, False, False, False],
            weights=[30, 0, 0, 0, 0, 0],
            parse_quality=0.2,
        )
        calls = []
        orch = AuditOrchestrator(
            reasoning_provider=MockReasoningProvider(call_count_tracker=calls),
            audit_llm=MockAuditLLM(responses=[stagnant_audit, stagnant_audit, stagnant_audit]),
            config=AuditConfig(min_domains=4, weight_threshold=200, max_corrections=3),
        )
        result = await orch.process_query("test")

        assert result.valid is False
        assert result.audit_rounds == 2  # initial + 1 correction (then abort)
        assert len(calls) == 2  # reason + 1 correction

    @pytest.mark.asyncio
    async def test_callbacks_emitted(self):
        """Verify SSE callbacks fire in expected order."""
        events = []

        def on_start(d, n):
            events.append(("start", d))

        def on_complete(d, r):
            events.append(("complete", d))

        def on_correction(d, a, v, f):
            events.append(("correction", d))

        orch = AuditOrchestrator(
            reasoning_provider=MockReasoningProvider(),
            audit_llm=MockAuditLLM(),
            config=AuditConfig(min_domains=4, weight_threshold=60),
            on_domain_start=on_start,
            on_domain_complete=on_complete,
            on_correction=on_correction,
        )
        await orch.process_query("test")

        starts = [e for e in events if e[0] == "start"]
        completes = [e for e in events if e[0] == "complete"]

        # REASON + D1..D6 = 7 starts and 7 completes
        assert len(starts) == 7
        assert len(completes) == 7
        assert starts[0] == ("start", "REASON")
        assert starts[1] == ("start", "D1")

    @pytest.mark.asyncio
    async def test_graceful_degradation_no_trace(self):
        """Provider returns NONE trace format — audit still works."""
        orch = AuditOrchestrator(
            reasoning_provider=MockReasoningProvider(
                thinking="",
                trace_format=TraceFormat.NONE,
            ),
            audit_llm=MockAuditLLM(),
            config=AuditConfig(min_domains=4, weight_threshold=60),
        )
        result = await orch.process_query("test")
        assert result.trace_format == "none"

    @pytest.mark.asyncio
    async def test_v2_response_reasoning_json(self):
        """V2Response.reasoning_json should be valid JSON with audit trail."""
        orch = AuditOrchestrator(
            reasoning_provider=MockReasoningProvider(),
            audit_llm=MockAuditLLM(),
            config=AuditConfig(min_domains=4, weight_threshold=60),
        )
        result = await orch.process_query("test")

        data = json.loads(result.reasoning_json)
        assert data["version"] == "2.0"
        assert len(data["audits"]) == 1
        assert data["audits"][0]["total_weight"] == 450

    @pytest.mark.asyncio
    async def test_token_accounting(self):
        """Token counts should accumulate from reasoning + audit calls."""
        orch = AuditOrchestrator(
            reasoning_provider=MockReasoningProvider(),
            audit_llm=MockAuditLLM(),
            config=AuditConfig(min_domains=4, weight_threshold=60),
        )
        result = await orch.process_query("test")

        assert result.input_tokens == 150  # 100 (reason) + 50 (audit)
        assert result.output_tokens == 350  # 200 (reason) + 150 (audit)


# ============================================================
# Phase 5: Integration (LabDB + Runner)
# ============================================================

class TestLabModels:
    def test_run_has_v2_fields(self):
        run = Run(mode="v2", reasoning_model="deepseek")
        assert run.mode == "v2"
        assert run.reasoning_model == "deepseek"

    def test_run_defaults_to_v1(self):
        run = Run()
        assert run.mode == "v1"
        assert run.reasoning_model == ""

    def test_db_create_run_v2(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = LabDB(db_path=Path(tmp) / "test.db")
            run = db.create_run(
                name="test",
                total_questions=5,
                num_steps=1,
                mode="v2",
                reasoning_model="deepseek",
            )
            assert run.mode == "v2"
            assert run.reasoning_model == "deepseek"

    def test_db_get_run_v2(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = LabDB(db_path=Path(tmp) / "test.db")
            created = db.create_run(
                name="test", total_questions=3, num_steps=1,
                mode="v2", reasoning_model="claude-thinking",
            )
            fetched = db.get_run(created.id)
            assert fetched.mode == "v2"
            assert fetched.reasoning_model == "claude-thinking"

    def test_db_list_runs_v2(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = LabDB(db_path=Path(tmp) / "test.db")
            db.create_run(name="v1-run", total_questions=5, num_steps=1, mode="v1")
            db.create_run(name="v2-run", total_questions=5, num_steps=1, mode="v2", reasoning_model="deepseek")

            runs = db.list_runs()
            assert len(runs) == 2
            modes = {r.name: r.mode for r in runs}
            assert modes["v1-run"] == "v1"
            assert modes["v2-run"] == "v2"

    def test_db_backward_compat(self):
        """Old runs without mode/reasoning_model should default to v1."""
        with tempfile.TemporaryDirectory() as tmp:
            db = LabDB(db_path=Path(tmp) / "test.db")
            run = db.create_run(name="old-run", total_questions=5, num_steps=1)
            assert run.mode == "v1"
            assert run.reasoning_model == ""


# ============================================================
# Phase 6: Benchmark Comparison
# ============================================================

class TestBenchmarkComparison:
    def test_compare_runs(self):
        from regulus.lab.models import Result

        with tempfile.TemporaryDirectory() as tmp:
            db = LabDB(db_path=Path(tmp) / "test.db")

            v1_run = db.create_run(name="v1", total_questions=3, num_steps=1, mode="v1")
            v2_run = db.create_run(name="v2", total_questions=3, num_steps=1, mode="v2", reasoning_model="deepseek")

            v1_step = v1_run.steps[0]
            v2_step = v2_run.steps[0]

            questions = ["Q1?", "Q2?", "Q3?"]
            for q in questions:
                db.add_result(v1_step.id, Result(question=q, expected="A", answer="A", valid=True, correct=True, time_seconds=10.0))
                db.add_result(v2_step.id, Result(question=q, expected="A", answer="A", valid=True, correct=True, time_seconds=2.0))

            comp = compare_runs(db, v1_run.id, v2_run.id)
            assert comp["matched_questions"] == 3
            assert comp["v1"]["correct"] == 3
            assert comp["v2"]["correct"] == 3
            assert comp["v1"]["accuracy"] == 1.0
            assert comp["delta"]["accuracy_diff"] == 0.0
            assert comp["delta"]["speedup"] == 5.0  # 30s / 6s

    def test_compare_with_differences(self):
        from regulus.lab.models import Result

        with tempfile.TemporaryDirectory() as tmp:
            db = LabDB(db_path=Path(tmp) / "test.db")

            v1_run = db.create_run(name="v1", total_questions=2, num_steps=1, mode="v1")
            v2_run = db.create_run(name="v2", total_questions=2, num_steps=1, mode="v2", reasoning_model="deepseek")

            v1_step = v1_run.steps[0]
            v2_step = v2_run.steps[0]

            # v1 gets Q1 right, v2 gets Q2 right
            db.add_result(v1_step.id, Result(question="Q1", expected="A", answer="A", valid=True, correct=True))
            db.add_result(v1_step.id, Result(question="Q2", expected="A", answer="B", valid=True, correct=False))
            db.add_result(v2_step.id, Result(question="Q1", expected="A", answer="B", valid=True, correct=False))
            db.add_result(v2_step.id, Result(question="Q2", expected="A", answer="A", valid=True, correct=True))

            comp = compare_runs(db, v1_run.id, v2_run.id)
            assert comp["v1"]["correct"] == 1
            assert comp["v2"]["correct"] == 1
            assert len(comp["improvements"]) == 1  # v2 fixed Q2
            assert len(comp["regressions"]) == 1    # v2 missed Q1


# ============================================================
# Phase 7: v1.0a — Domain-Specific Fields + Violations
# ============================================================

from regulus.audit.types import CRITICAL_VIOLATIONS
from regulus.audit.d1_validator import D1Validator, D1ValidationResult


class TestDomainSpecificFields:
    """Tests for v1.0a domain-specific audit fields."""

    def test_parse_d1_depth(self):
        raw = _make_audit_json(err_signals=[{"d1_depth": 3}, None, None, None, None, None])
        result = _parse_audit_response(raw)
        assert result.domains[0].d1_depth == 3
        assert result.domains[1].d1_depth is None  # Only D1 gets d1_depth

    def test_parse_d2_depth(self):
        raw = _make_audit_json(err_signals=[None, {"d2_depth": 2}, None, None, None, None])
        result = _parse_audit_response(raw)
        assert result.domains[1].d2_depth == 2

    def test_parse_d3_objectivity(self):
        raw = _make_audit_json(err_signals=[None, None, {"d3_objectivity_pass": True}, None, None, None])
        result = _parse_audit_response(raw)
        assert result.domains[2].d3_objectivity_pass is True

    def test_d3_objectivity_false_kills_gate(self):
        d = DomainAuditResult(
            domain="D3", present=True,
            e_exists=True, r_exists=True, rule_exists=True,
            s_exists=True, deps_declared=True,
            d3_objectivity_pass=False,
        )
        assert d.gate_passed is False
        assert d.gate.err_complete is False  # Objectivity failure breaks ERR

    def test_d3_objectivity_false_zeroes_weight_in_parser(self):
        raw = _make_audit_json(
            weights=[75, 75, 70, 75, 75, 75],
            err_signals=[None, None, {"d3_objectivity_pass": False}, None, None, None],
        )
        result = _parse_audit_response(raw)
        assert result.domains[2].weight == 0  # Parser zeroed it
        assert result.domains[2].d3_objectivity_pass is False

    def test_parse_d4_aristotle(self):
        raw = _make_audit_json(err_signals=[None, None, None, {"d4_aristotle_ok": False}, None, None])
        result = _parse_audit_response(raw)
        assert result.domains[3].d4_aristotle_ok is False

    def test_parse_d5_certainty_type(self):
        raw = _make_audit_json(err_signals=[None, None, None, None, {"d5_certainty_type": "necessary"}, None])
        result = _parse_audit_response(raw)
        assert result.domains[4].d5_certainty_type == "necessary"

    def test_parse_d6_genuine(self):
        raw = _make_audit_json(err_signals=[None, None, None, None, None, {"d6_genuine": False}])
        result = _parse_audit_response(raw)
        assert result.domains[5].d6_genuine is False

    def test_to_dict_includes_domain_fields(self):
        d = DomainAuditResult(
            domain="D1", present=True, weight=75,
            e_exists=True, r_exists=True, rule_exists=True,
            s_exists=True, deps_declared=True, d1_depth=3,
        )
        result = AuditResult(domains=[d])
        d_dict = result.to_dict()["domains"][0]
        assert d_dict["d1_depth"] == 3

    def test_to_dict_always_includes_v10a_fields(self):
        """v1.0a fields are always serialized (even as None) for downstream consistency."""
        d = DomainAuditResult(domain="D2", present=True, weight=50,
                              e_exists=True, r_exists=True, rule_exists=True,
                              s_exists=True, deps_declared=True)
        result = AuditResult(domains=[d])
        d_dict = result.to_dict()["domains"][0]
        assert "d1_depth" in d_dict
        assert d_dict["d1_depth"] is None
        assert "d3_objectivity_pass" in d_dict
        assert d_dict["d3_objectivity_pass"] is None


class TestViolationPatterns:
    """Tests for v1.0a violation pattern detection and enforcement."""

    def test_parse_violation_patterns(self):
        raw = _make_audit_json(violation_patterns=["ORDER_INVERSION", "FALSE_REFLECTION"])
        result = _parse_audit_response(raw)
        assert result.violation_patterns == ["ORDER_INVERSION", "FALSE_REFLECTION"]

    def test_parse_no_violations(self):
        raw = _make_audit_json()
        result = _parse_audit_response(raw)
        assert result.violation_patterns == []

    def test_critical_violations_fail_passing(self):
        config = AuditConfig(min_domains=2, weight_threshold=50)
        for violation in CRITICAL_VIOLATIONS:
            result = AuditResult(
                domains=[
                    DomainAuditResult(domain=f"D{i}", present=True, e_exists=True, r_exists=True, rule_exists=True, s_exists=True, deps_declared=True, weight=80)
                    for i in range(1, 7)
                ],
                violation_patterns=[violation],
            )
            assert config.is_passing(result) is False, f"{violation} should cause failure"

    def test_noncritical_violations_still_pass(self):
        config = AuditConfig(min_domains=2, weight_threshold=50)
        noncritical = ["DOMAIN_SKIP", "PREMATURE_CLOSURE", "FALSE_REFLECTION",
                       "FRAMEWORK_AS_ELEMENT", "RATIONALIZATION_AS_REFLECTION"]
        for violation in noncritical:
            result = AuditResult(
                domains=[
                    DomainAuditResult(domain=f"D{i}", present=True, e_exists=True, r_exists=True, rule_exists=True, s_exists=True, deps_declared=True, weight=80)
                    for i in range(1, 7)
                ],
                violation_patterns=[violation],
            )
            assert config.is_passing(result) is True, f"{violation} should not cause failure"

    def test_violation_patterns_in_to_dict(self):
        result = AuditResult(
            domains=[DomainAuditResult(domain="D1", present=True, weight=50)],
            violation_patterns=["RATIONALIZATION"],
        )
        d = result.to_dict()
        assert d["violation_patterns"] == ["RATIONALIZATION"]

    def test_feedback_includes_violation_info(self):
        config = AuditConfig(min_domains=2, weight_threshold=50)
        fg = FeedbackGenerator(config)
        result = AuditResult(
            domains=[DomainAuditResult(domain="D1", present=True, e_exists=True, r_exists=True, rule_exists=True, s_exists=True, deps_declared=True, weight=30)],
            violation_patterns=["ORDER_INVERSION", "RATIONALIZATION"],
        )
        fb = fg.generate(result, "q", 1)
        assert fb is not None
        assert "VIOLATION PATTERNS DETECTED" in fb.prompt
        assert "ORDER_INVERSION" in fb.prompt
        assert "predetermined conclusion" in fb.prompt.lower() or "RATIONALIZATION" in fb.prompt

    def test_feedback_d3_objectivity_failure(self):
        config = AuditConfig(min_domains=1, weight_threshold=0, err_required=True)
        fg = FeedbackGenerator(config)
        result = AuditResult(
            domains=[
                DomainAuditResult(domain="D3", present=True, weight=0, e_exists=True, r_exists=True, rule_exists=True, s_exists=True, deps_declared=True, d3_objectivity_pass=False),
            ],
        )
        fb = fg.generate(result, "q", 1)
        assert fb is not None
        assert "OBJECTIVITY FAILURE" in fb.prompt


class TestD1Validator:
    """Tests for D1 external validator."""

    def test_d1_validation_result_faithful(self):
        r = D1ValidationResult(fidelity=0.9)
        assert r.is_faithful is True
        assert r.is_critical_failure is False

    def test_d1_validation_result_unfaithful(self):
        r = D1ValidationResult(fidelity=0.6)
        assert r.is_faithful is False
        assert r.is_critical_failure is False

    def test_d1_validation_result_critical(self):
        r = D1ValidationResult(fidelity=0.3)
        assert r.is_faithful is False
        assert r.is_critical_failure is True

    @pytest.mark.asyncio
    async def test_d1_validator_parses_good_response(self):
        good_response = json.dumps({
            "fidelity": 0.95,
            "issues": [],
            "recommended_d1_depth": 3,
            "recommended_d1_weight": 75,
            "explanation": "D1 faithfully captures the query",
        })
        llm = MockAuditLLM(responses=[good_response])
        validator = D1Validator(llm)
        result = await validator.validate("What is 2+2?", "Identifies math question", "4")
        assert result.fidelity == 0.95
        assert result.is_faithful is True
        assert result.recommended_depth == 3

    @pytest.mark.asyncio
    async def test_d1_validator_parses_bad_response(self):
        bad_response = json.dumps({
            "fidelity": 0.3,
            "issues": ["STRAW_MAN: query simplified", "OMISSION: constraints missed"],
            "recommended_d1_depth": 1,
            "recommended_d1_weight": 20,
            "explanation": "D1 drops key constraints from the query",
        })
        llm = MockAuditLLM(responses=[bad_response])
        validator = D1Validator(llm)
        result = await validator.validate("complex query", "simple summary", "wrong")
        assert result.fidelity == 0.3
        assert result.is_critical_failure is True
        assert len(result.issues) == 2

    @pytest.mark.asyncio
    async def test_d1_validator_handles_parse_error(self):
        llm = MockAuditLLM(responses=["not json"])
        validator = D1Validator(llm)
        result = await validator.validate("q", "d1", "a")
        assert result.fidelity == 1.0  # Default to passing
        assert "parse failed" in result.issues[0]

    @pytest.mark.asyncio
    async def test_orchestrator_d1_validation_triggers_on_low_depth(self):
        """D1 validator should trigger when d1_depth < 3."""
        d1_low_depth = _make_audit_json(
            weights=[40, 75, 75, 75, 75, 75],
            err_signals=[{"d1_depth": 1}, None, None, None, None, None],
        )
        d1_val_response = json.dumps({
            "fidelity": 0.5,
            "issues": ["STRAW_MAN: oversimplified"],
            "recommended_d1_depth": 1,
            "recommended_d1_weight": 20,
            "explanation": "D1 misses key entities",
        })
        # MockAuditLLM returns: first call = audit, second call = D1 validator
        llm = MockAuditLLM(responses=[d1_low_depth, d1_val_response])
        events = []

        def on_start(d, n):
            events.append(("start", d))

        orch = AuditOrchestrator(
            reasoning_provider=MockReasoningProvider(),
            audit_llm=llm,
            config=AuditConfig(min_domains=4, weight_threshold=60),
            on_domain_start=on_start,
        )
        result = await orch.process_query("test")

        # D1_VAL event should be emitted
        d1_val_events = [e for e in events if e[1] == "D1_VAL"]
        assert len(d1_val_events) == 1

        # D1 weight should be capped by validator recommendation
        d1 = next(d for d in result.final_audit.domains if d.domain == "D1")
        assert d1.weight <= 20  # Validator recommended 20

    @pytest.mark.asyncio
    async def test_orchestrator_d1_validation_skipped_on_good_depth(self):
        """D1 validator should NOT trigger when d1_depth >= 3 and weight >= 60."""
        d1_good_depth = _make_audit_json(
            err_signals=[{"d1_depth": 3}, None, None, None, None, None],
        )
        events = []

        def on_start(d, n):
            events.append(("start", d))

        orch = AuditOrchestrator(
            reasoning_provider=MockReasoningProvider(),
            audit_llm=MockAuditLLM(responses=[d1_good_depth]),
            config=AuditConfig(min_domains=4, weight_threshold=60),
            on_domain_start=on_start,
        )
        await orch.process_query("test")

        d1_val_events = [e for e in events if e[1] == "D1_VAL"]
        assert len(d1_val_events) == 0  # D1 validator should NOT trigger
