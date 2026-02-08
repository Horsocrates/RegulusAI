"""
Regulus AI - MAS Phase 1 Test Suite
=====================================

Tests for the Multi-Agent Structured pipeline scaffolding.
All tests use mocks (no API keys needed).
"""

import json
import tempfile
from pathlib import Path

import pytest

from regulus.mas.types import (
    Complexity,
    DomainStatus,
    TaskStatus,
    MASConfig,
    MASResponse,
)
from regulus.mas.table import (
    DomainOutput,
    Component,
    TaskTable,
    DOMAIN_CODES,
)
from regulus.mas.contracts import (
    DomainInput,
    D1Input, D1Output,
    D2Input, D2Output,
    D3Input, D3Output,
    D4Input, D4Output,
    D5Input, D5Output,
    D6Input, D6Output,
    DOMAIN_INPUT_TYPES,
    DOMAIN_OUTPUT_TYPES,
)
from regulus.mas.workers import DomainWorker, MockWorker
from regulus.mas.routing import DomainRoute, RoutingConfig
from regulus.mas.orchestrator import MASOrchestrator
from regulus.lab.models import LabDB, Run


# ============================================================
# TestMASTypes
# ============================================================

class TestMASTypes:
    """Tests for enums, MASConfig, and MASResponse."""

    def test_complexity_values(self):
        assert Complexity.EASY.value == "easy"
        assert Complexity.MEDIUM.value == "medium"
        assert Complexity.HARD.value == "hard"

    def test_domain_status_values(self):
        assert DomainStatus.PENDING.value == "pending"
        assert DomainStatus.RUNNING.value == "running"
        assert DomainStatus.COMPLETED.value == "completed"
        assert DomainStatus.FAILED.value == "failed"
        assert DomainStatus.SKIPPED.value == "skipped"

    def test_task_status_values(self):
        assert TaskStatus.CREATED.value == "created"
        assert TaskStatus.CLASSIFYING.value == "classifying"
        assert TaskStatus.DECOMPOSING.value == "decomposing"
        assert TaskStatus.PROCESSING.value == "processing"
        assert TaskStatus.VERIFYING.value == "verifying"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"

    def test_config_defaults(self):
        cfg = MASConfig()
        assert cfg.min_domains == 4
        assert cfg.weight_threshold == 60
        assert cfg.err_required is True
        assert cfg.max_corrections == 2
        assert cfg.max_decomposition_depth == 3
        assert cfg.default_model == "gpt-4o-mini"
        assert cfg.reasoning_model == "deepseek"
        assert cfg.domain_timeout_seconds == 30.0

    def test_config_is_passing_true(self):
        cfg = MASConfig()
        assert cfg.is_passing(total_weight=300, domains_present=6, all_gates_passed=True)

    def test_config_is_passing_low_weight(self):
        cfg = MASConfig()
        assert not cfg.is_passing(total_weight=50, domains_present=6, all_gates_passed=True)

    def test_config_is_passing_few_domains(self):
        cfg = MASConfig()
        assert not cfg.is_passing(total_weight=300, domains_present=3, all_gates_passed=True)

    def test_config_is_passing_gates_failed(self):
        cfg = MASConfig()
        assert not cfg.is_passing(total_weight=300, domains_present=6, all_gates_passed=False)

    def test_response_reasoning_json(self):
        resp = MASResponse(
            query="test",
            answer="42",
            valid=True,
            complexity="easy",
            components_count=1,
            task_table_json='{"test": true}',
            audit_summary={"total_weight": 450},
            corrections=0,
        )
        data = json.loads(resp.reasoning_json)
        assert data["version"] == "3.0"
        assert data["pipeline"] == "mas"
        assert data["complexity"] == "easy"
        assert data["components_count"] == 1


# ============================================================
# TestTaskTable
# ============================================================

class TestTaskTable:
    """Tests for DomainOutput, Component, and TaskTable."""

    def test_domain_output_gate_all_true(self):
        d = DomainOutput(
            domain="D1", status=DomainStatus.COMPLETED,
            e_exists=True, r_exists=True, rule_exists=True, s_exists=True,
            deps_declared=True, l1_l3_ok=True, l5_ok=True,
        )
        assert d.gate_passed is True

    def test_domain_output_gate_missing_element(self):
        d = DomainOutput(
            domain="D1", status=DomainStatus.COMPLETED,
            e_exists=False, r_exists=True, rule_exists=True, s_exists=True,
            deps_declared=True, l1_l3_ok=True, l5_ok=True,
        )
        assert d.gate_passed is False

    def test_domain_output_gate_deps_false(self):
        d = DomainOutput(
            domain="D1", status=DomainStatus.COMPLETED,
            e_exists=True, r_exists=True, rule_exists=True, s_exists=True,
            deps_declared=False, l1_l3_ok=True, l5_ok=True,
        )
        assert d.gate_passed is False

    def test_domain_output_roundtrip(self):
        d = DomainOutput(
            domain="D3", status=DomainStatus.COMPLETED, content="analysis",
            weight=80, e_exists=True, r_exists=True, rule_exists=True, s_exists=True,
            deps_declared=True, l1_l3_ok=True, l5_ok=True,
            issues=["minor"], model_used="gpt-4o",
        )
        d2 = DomainOutput.from_dict(d.to_dict())
        assert d2.domain == "D3"
        assert d2.weight == 80
        assert d2.gate_passed is True
        assert d2.issues == ["minor"]

    def test_component_depth(self):
        assert Component(component_id="C1").depth == 1
        assert Component(component_id="C1.1").depth == 2
        assert Component(component_id="C1.1.2").depth == 3

    def test_component_total_weight(self):
        comp = Component(component_id="C1")
        comp.domains["D1"] = DomainOutput(domain="D1", status=DomainStatus.COMPLETED, weight=80)
        comp.domains["D2"] = DomainOutput(domain="D2", status=DomainStatus.COMPLETED, weight=70)
        comp.domains["D3"] = DomainOutput(domain="D3", status=DomainStatus.PENDING, weight=50)
        assert comp.total_weight == 150  # only completed domains

    def test_component_all_gates_passed(self):
        comp = Component(component_id="C1")
        comp.domains["D1"] = DomainOutput(
            domain="D1", status=DomainStatus.COMPLETED,
            e_exists=True, r_exists=True, rule_exists=True, s_exists=True,
            deps_declared=True, l1_l3_ok=True, l5_ok=True,
        )
        assert comp.all_gates_passed is True

    def test_component_all_gates_no_completed(self):
        comp = Component(component_id="C1")
        comp.init_domains()
        assert comp.all_gates_passed is False  # no completed domains

    def test_component_is_leaf(self):
        parent = Component(component_id="C1")
        child = Component(component_id="C1.1", parent_id="C1")
        parent.children.append(child)
        assert parent.is_leaf is False
        assert child.is_leaf is True

    def test_component_init_domains(self):
        comp = Component(component_id="C1")
        comp.init_domains()
        assert len(comp.domains) == 6
        for code in DOMAIN_CODES:
            assert code in comp.domains
            assert comp.domains[code].status == DomainStatus.PENDING

    def test_component_roundtrip(self):
        comp = Component(component_id="C1.2", parent_id="C1", description="sub-task")
        comp.init_domains()
        comp.domains["D1"].status = DomainStatus.COMPLETED
        comp.domains["D1"].weight = 85

        d = comp.to_dict()
        comp2 = Component.from_dict(d)
        assert comp2.component_id == "C1.2"
        assert comp2.parent_id == "C1"
        assert comp2.domains["D1"].weight == 85

    def test_task_table_flat_traversal(self):
        table = TaskTable(query="test")
        parent = Component(component_id="C1")
        child1 = Component(component_id="C1.1", parent_id="C1")
        child2 = Component(component_id="C1.2", parent_id="C1")
        grandchild = Component(component_id="C1.1.1", parent_id="C1.1")
        child1.children.append(grandchild)
        parent.children.extend([child1, child2])
        table.components = [parent]

        flat = table.all_components_flat
        ids = [c.component_id for c in flat]
        assert ids == ["C1", "C1.1", "C1.2", "C1.1.1"]

    def test_task_table_total_weight_leaf_only(self):
        table = TaskTable(query="test")
        parent = Component(component_id="C1")
        child = Component(component_id="C1.1", parent_id="C1")
        child.domains["D1"] = DomainOutput(domain="D1", status=DomainStatus.COMPLETED, weight=80)
        parent.domains["D1"] = DomainOutput(domain="D1", status=DomainStatus.COMPLETED, weight=99)
        parent.children.append(child)
        table.components = [parent]
        # parent is not leaf, only child counts
        assert table.total_weight == 80

    def test_task_table_domains_summary(self):
        table = TaskTable(query="test")
        comp = Component(component_id="C1")
        comp.domains["D1"] = DomainOutput(domain="D1", status=DomainStatus.COMPLETED, weight=80)
        comp.domains["D2"] = DomainOutput(domain="D2", status=DomainStatus.COMPLETED, weight=60)
        table.components = [comp]
        summary = table.domains_summary
        assert summary["D1"] == 80
        assert summary["D2"] == 60

    def test_task_table_json_roundtrip(self):
        table = TaskTable(
            query="What is 2+2?",
            complexity=Complexity.EASY,
            status=TaskStatus.COMPLETED,
            answer="4",
            classification_reason="word_count=4",
        )
        comp = Component(component_id="C1", description="main")
        comp.init_domains()
        comp.domains["D5"].status = DomainStatus.COMPLETED
        comp.domains["D5"].content = "4"
        comp.domains["D5"].weight = 90
        table.components = [comp]

        json_str = table.to_json()
        table2 = TaskTable.from_json(json_str)
        assert table2.query == "What is 2+2?"
        assert table2.complexity == Complexity.EASY
        assert table2.answer == "4"
        assert table2.components[0].domains["D5"].weight == 90

    def test_task_table_tokens(self):
        table = TaskTable(query="test")
        comp = Component(component_id="C1")
        comp.domains["D1"] = DomainOutput(domain="D1", input_tokens=100, output_tokens=200)
        comp.domains["D2"] = DomainOutput(domain="D2", input_tokens=50, output_tokens=80)
        table.components = [comp]
        assert table.total_input_tokens == 150
        assert table.total_output_tokens == 280


# ============================================================
# TestContracts
# ============================================================

class TestContracts:
    """Tests for domain I/O type definitions."""

    def test_domain_input_types_mapping(self):
        assert DOMAIN_INPUT_TYPES["D1"] is D1Input
        assert DOMAIN_INPUT_TYPES["D2"] is D2Input
        assert DOMAIN_INPUT_TYPES["D3"] is D3Input
        assert DOMAIN_INPUT_TYPES["D4"] is D4Input
        assert DOMAIN_INPUT_TYPES["D5"] is D5Input
        assert DOMAIN_INPUT_TYPES["D6"] is D6Input

    def test_domain_output_types_mapping(self):
        assert DOMAIN_OUTPUT_TYPES["D1"] is D1Output
        assert DOMAIN_OUTPUT_TYPES["D2"] is D2Output
        assert DOMAIN_OUTPUT_TYPES["D3"] is D3Output
        assert DOMAIN_OUTPUT_TYPES["D4"] is D4Output
        assert DOMAIN_OUTPUT_TYPES["D5"] is D5Output
        assert DOMAIN_OUTPUT_TYPES["D6"] is D6Output

    def test_inheritance(self):
        d1 = D1Input(query="test", component_id="C1")
        assert isinstance(d1, DomainInput)
        d6 = D6Input(query="test", component_id="C1")
        assert isinstance(d6, DomainInput)

    def test_d5_output_fields(self):
        d5 = D5Output(
            conclusion={"answer": "42", "certainty_type": "necessary"},
            answer="42",
            certainty_type="necessary",
            content="The answer is 42",
        )
        assert d5.conclusion == {"answer": "42", "certainty_type": "necessary"}
        assert d5.answer == "42"
        assert d5.certainty_type == "necessary"


# ============================================================
# TestWorkers
# ============================================================

class TestWorkers:
    """Tests for MockWorker."""

    def test_mock_worker_domain_code(self):
        w = MockWorker(domain_code="D3")
        assert w.domain_code == "D3"

    @pytest.mark.asyncio
    async def test_mock_worker_returns_configured(self):
        w = MockWorker(domain_code="D1", weight=85, gate_pass=True, content="test output")
        comp = Component(component_id="C1")
        inp = D1Input(query="test")

        result = await w.process(comp, inp, "gpt-4o")
        assert result.domain == "D1"
        assert result.weight == 85
        assert result.content == "test output"
        assert result.gate_passed is True
        assert result.status == DomainStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_mock_worker_call_tracking(self):
        tracker = []
        w = MockWorker(domain_code="D2", call_tracker=tracker)
        comp = Component(component_id="C1")
        inp = D2Input(query="test")

        await w.process(comp, inp, "gpt-4o-mini")
        assert len(tracker) == 1
        assert tracker[0]["domain"] == "D2"
        assert tracker[0]["component_id"] == "C1"
        assert tracker[0]["model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_mock_worker_gate_fail(self):
        w = MockWorker(domain_code="D4", gate_pass=False, weight=30)
        comp = Component(component_id="C1")
        inp = D4Input(query="test")

        result = await w.process(comp, inp, "gpt-4o")
        assert result.gate_passed is False
        assert result.weight == 30


# ============================================================
# TestRouting
# ============================================================

class TestRouting:
    """Tests for RoutingConfig."""

    def test_default_easy_all_mini(self):
        rc = RoutingConfig.default()
        for d in DOMAIN_CODES:
            assert rc.get_model("easy", d) == "gpt-4o-mini"

    def test_default_medium_d1_d5_upgraded(self):
        rc = RoutingConfig.default()
        assert rc.get_model("medium", "D1") == "gpt-4o"
        assert rc.get_model("medium", "D5") == "gpt-4o"
        assert rc.get_model("medium", "D2") == "gpt-4o-mini"
        assert rc.get_model("medium", "D4") == "gpt-4o-mini"

    def test_default_hard_deepseek_for_key_domains(self):
        rc = RoutingConfig.default()
        assert rc.get_model("hard", "D1") == "deepseek"
        assert rc.get_model("hard", "D3") == "deepseek"
        assert rc.get_model("hard", "D5") == "deepseek"
        assert rc.get_model("hard", "D2") == "gpt-4o"

    def test_unknown_domain_fallback(self):
        rc = RoutingConfig.default()
        model = rc.get_model("easy", "D99")
        assert model == "gpt-4o-mini"  # fallback


# ============================================================
# TestMASOrchestrator
# ============================================================

class TestMASOrchestrator:
    """Tests for MASOrchestrator pipeline."""

    @pytest.mark.asyncio
    async def test_process_query_returns_response(self):
        orch = MASOrchestrator()
        resp = await orch.process_query("What is 2+2?")
        assert isinstance(resp, MASResponse)
        assert resp.query == "What is 2+2?"

    @pytest.mark.asyncio
    async def test_classification_easy(self):
        orch = MASOrchestrator()
        resp = await orch.process_query("What is 2+2?")
        assert resp.complexity == "easy"

    @pytest.mark.asyncio
    async def test_classification_medium(self):
        orch = MASOrchestrator()
        query = " ".join(["word"] * 30)  # 30 words
        resp = await orch.process_query(query)
        assert resp.complexity == "medium"

    @pytest.mark.asyncio
    async def test_classification_hard(self):
        orch = MASOrchestrator()
        query = " ".join(["word"] * 60)  # 60 words
        resp = await orch.process_query(query)
        assert resp.complexity == "hard"

    @pytest.mark.asyncio
    async def test_decomposition_single_component(self):
        orch = MASOrchestrator()
        resp = await orch.process_query("test")
        assert resp.components_count == 1

    @pytest.mark.asyncio
    async def test_all_six_domains_processed(self):
        tracker = []
        workers = {
            code: MockWorker(domain_code=code, call_tracker=tracker)
            for code in DOMAIN_CODES
        }
        orch = MASOrchestrator(workers=workers)
        await orch.process_query("test")
        domains_called = [c["domain"] for c in tracker]
        assert domains_called == ["D1", "D2", "D3", "D4", "D5", "D6"]

    @pytest.mark.asyncio
    async def test_answer_from_d5(self):
        workers = {}
        for code in DOMAIN_CODES:
            if code == "D5":
                workers[code] = MockWorker(domain_code=code, content="The answer is 42")
            else:
                workers[code] = MockWorker(domain_code=code, content=f"Content for {code}")
        orch = MASOrchestrator(workers=workers)
        resp = await orch.process_query("test")
        assert resp.answer == "The answer is 42"

    @pytest.mark.asyncio
    async def test_tokens_accumulated(self):
        orch = MASOrchestrator()
        resp = await orch.process_query("test")
        # 6 domains × 50 input + 6 × 100 output
        assert resp.input_tokens == 300
        assert resp.output_tokens == 600

    @pytest.mark.asyncio
    async def test_callbacks_emitted(self):
        events = []

        def on_start(domain, name):
            events.append(("start", domain))

        def on_complete(domain, data):
            events.append(("complete", domain))

        orch = MASOrchestrator(
            on_domain_start=on_start,
            on_domain_complete=on_complete,
        )
        await orch.process_query("test")

        start_domains = [e[1] for e in events if e[0] == "start"]
        assert "CLASSIFY" in start_domains
        assert "DECOMPOSE" in start_domains
        assert "D1" in start_domains
        assert "D6" in start_domains
        assert "VERIFY" in start_domains

    @pytest.mark.asyncio
    async def test_valid_with_all_gates(self):
        workers = {
            code: MockWorker(domain_code=code, weight=75, gate_pass=True)
            for code in DOMAIN_CODES
        }
        orch = MASOrchestrator(workers=workers)
        resp = await orch.process_query("test")
        # 6 domains * 75 = 450 weight, 6 present, all gates
        assert resp.valid is True

    @pytest.mark.asyncio
    async def test_invalid_with_gate_failure(self):
        workers = {}
        for code in DOMAIN_CODES:
            if code == "D3":
                workers[code] = MockWorker(domain_code=code, weight=75, gate_pass=False)
            else:
                workers[code] = MockWorker(domain_code=code, weight=75, gate_pass=True)
        orch = MASOrchestrator(workers=workers)
        resp = await orch.process_query("test")
        assert resp.valid is False


# ============================================================
# TestLabIntegration
# ============================================================

class TestLabIntegration:
    """Tests for MAS integration with lab infrastructure."""

    def test_reasoning_json_structure(self):
        resp = MASResponse(
            query="test", answer="42", valid=True,
            complexity="easy", components_count=1,
            task_table_json='{}', audit_summary={"total_weight": 450},
        )
        data = json.loads(resp.reasoning_json)
        assert data["version"] == "3.0"
        assert data["pipeline"] == "mas"
        assert "task_table" in data
        assert "audit_summary" in data

    def test_run_mode_mas(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = LabDB(db_path=Path(tmp) / "test.db")
            run = db.create_run(
                name="MAS test",
                total_questions=5,
                num_steps=1,
                mode="mas",
            )
            assert run.mode == "mas"

    def test_lab_db_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = LabDB(db_path=Path(tmp) / "test.db")
            run = db.create_run(
                name="MAS roundtrip",
                total_questions=10,
                num_steps=2,
                mode="mas",
                reasoning_model="deepseek",
            )
            loaded = db.get_run(run.id)
            assert loaded.mode == "mas"
            assert loaded.reasoning_model == "deepseek"

    def test_task_table_json_in_reasoning(self):
        table = TaskTable(query="test", complexity=Complexity.EASY, status=TaskStatus.COMPLETED)
        comp = Component(component_id="C1")
        comp.init_domains()
        for code in DOMAIN_CODES:
            comp.domains[code].status = DomainStatus.COMPLETED
            comp.domains[code].weight = 75
            comp.domains[code].e_exists = True
            comp.domains[code].r_exists = True
            comp.domains[code].rule_exists = True
            comp.domains[code].s_exists = True
            comp.domains[code].deps_declared = True
        table.components = [comp]

        resp = MASResponse(
            query="test", answer="result", valid=True,
            complexity="easy", components_count=1,
            task_table_json=table.to_json(),
            audit_summary={"total_weight": 450},
        )
        data = json.loads(resp.reasoning_json)
        # The task_table field contains the serialized TaskTable
        inner = json.loads(data["task_table"])
        assert inner["query"] == "test"
        assert len(inner["components"]) == 1
