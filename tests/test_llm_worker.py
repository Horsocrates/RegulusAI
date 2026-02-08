"""
Regulus AI - MAS Phase 2 LLM Worker Tests
===========================================

Tests for LLMWorker, WorkerFactory, prompts, and typed output chaining.
All tests use mocks (no API keys needed).
"""

import json

import pytest

from regulus.llm.client import LLMClient, LLMResponse
from regulus.mas.types import DomainStatus
from regulus.mas.table import Component, DomainOutput, DOMAIN_CODES
from regulus.mas.contracts import (
    DomainInput,
    D1Input, D1Output,
    D2Input, D2Output,
    D3Input, D3Output,
    D4Input, D4Output,
    D5Input, D5Output,
    D6Input, D6Output,
)
from regulus.mas.workers import MockWorker
from regulus.mas.llm_worker import LLMWorker, WorkerError, _parse_json_response
from regulus.mas.worker_factory import (
    MODEL_REGISTRY,
    create_workers_from_routing,
    clear_client_cache,
)
from regulus.mas.routing import RoutingConfig
from regulus.mas.prompts import DOMAIN_PROMPTS
from regulus.mas.orchestrator import MASOrchestrator


# ============================================================
# Mock LLM Client
# ============================================================

class MockMASLLM(LLMClient):
    """Mock LLM client that returns pre-configured JSON responses per domain."""

    def __init__(self, responses: dict[str, str] | None = None):
        self._responses = responses or {}
        self._calls: list[dict] = []
        self._default_response = json.dumps({
            "components": [{"id": "C1", "name": "test", "type": "entity"}],
            "task_type": "analytical",
            "internal_log": "Mock reasoning",
        })

    async def generate(self, prompt: str, system: str = "") -> str:
        self._calls.append({"prompt": prompt, "system": system})
        # Detect domain from system prompt
        for domain, response in self._responses.items():
            if domain.lower() in system.lower():
                return response
        return self._default_response

    async def generate_with_usage(self, prompt: str, system: str = "") -> LLMResponse:
        text = await self.generate(prompt, system)
        return LLMResponse(text=text, input_tokens=100, output_tokens=200)


# ============================================================
# Pre-built JSON responses for each domain
# ============================================================

D1_RESPONSE = json.dumps({
    "components": [
        {"id": "C1", "name": "arithmetic", "type": "entity",
         "elements": {"E": "addition", "R": "operands", "rule": "sum", "S": "integers"},
         "subcomponents": []}
    ],
    "task_type": "factual",
    "internal_log": "Simple arithmetic query",
})

D2_RESPONSE = json.dumps({
    "components": [
        {"id": "C1", "name": "arithmetic", "defined_terms": {"addition": "sum operation"},
         "scope": "integer arithmetic", "ambiguities": []}
    ],
    "hidden_assumptions": ["Numbers are base-10"],
    "internal_log": "Clarified arithmetic scope",
})

D3_RESPONSE = json.dumps({
    "framework": {
        "name": "Deductive Reasoning",
        "type": "deductive",
        "justification": "Simple mathematical proof",
        "criteria": ["validity", "completeness"],
    },
    "objectivity": {
        "type": "deterministic",
        "bias_flags": [],
    },
    "internal_log": "Selected deductive framework",
})

D4_RESPONSE = json.dumps({
    "comparisons": [
        {"criterion": "validity", "evidence": "2+2=4 by definition", "strength": "strong"},
    ],
    "aristotle_check": {"presence": True, "absence": False, "degree": True},
    "coverage": {"addressed": ["validity"], "gaps": []},
    "internal_log": "Compared evidence",
})

D5_RESPONSE = json.dumps({
    "conclusion": {
        "answer": "4",
        "certainty_type": "necessary",
        "reasoning": "2+2=4 by arithmetic axioms",
    },
    "logical_form": "2+2=4",
    "overreach_check": "No overreach",
    "avoidance_check": "Directly answers question",
    "internal_log": "Inferred conclusion",
})

D6_RESPONSE = json.dumps({
    "scope": {
        "applies_when": "Standard integer arithmetic",
        "does_not_apply_when": "Non-standard number systems",
    },
    "assumptions": ["Standard arithmetic axioms"],
    "limitations": ["Only applies to base-10"],
    "new_questions": ["Does this hold in modular arithmetic?"],
    "return_assessment": {
        "errors_found": False,
        "weak_points": [],
        "suggested_corrections": [],
    },
    "internal_log": "Reflected on reasoning chain",
})


def _make_domain_llm() -> MockMASLLM:
    """Create a mock LLM that returns domain-specific responses."""
    return MockMASLLM(responses={
        "domain 1": D1_RESPONSE,
        "recognition": D1_RESPONSE,
        "domain 2": D2_RESPONSE,
        "clarification": D2_RESPONSE,
        "domain 3": D3_RESPONSE,
        "framework": D3_RESPONSE,
        "domain 4": D4_RESPONSE,
        "comparison": D4_RESPONSE,
        "domain 5": D5_RESPONSE,
        "inference": D5_RESPONSE,
        "domain 6": D6_RESPONSE,
        "reflection": D6_RESPONSE,
    })


# ============================================================
# TestParseJsonResponse
# ============================================================

class TestParseJsonResponse:
    """Tests for the JSON parser."""

    def test_clean_json(self):
        result = _parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_markdown_fences(self):
        text = '```json\n{"key": "value"}\n```'
        result = _parse_json_response(text)
        assert result == {"key": "value"}

    def test_preamble_text(self):
        text = 'Here is the JSON:\n{"key": "value"}\nDone.'
        result = _parse_json_response(text)
        assert result == {"key": "value"}

    def test_trailing_comma_object(self):
        text = '{"a": 1, "b": 2,}'
        result = _parse_json_response(text)
        assert result == {"a": 1, "b": 2}

    def test_trailing_comma_array(self):
        text = '{"items": [1, 2, 3,]}'
        result = _parse_json_response(text)
        assert result == {"items": [1, 2, 3]}

    def test_no_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_json_response("no json here")

    def test_nested_json(self):
        text = '{"outer": {"inner": [1, 2]}}'
        result = _parse_json_response(text)
        assert result["outer"]["inner"] == [1, 2]

    def test_string_with_braces(self):
        text = '{"msg": "use {x} and {y}"}'
        result = _parse_json_response(text)
        assert result["msg"] == "use {x} and {y}"


# ============================================================
# TestLLMWorkerProcess
# ============================================================

class TestLLMWorkerProcess:
    """Tests for LLMWorker.process() across all domains."""

    @pytest.mark.asyncio
    async def test_d1_worker_returns_domain_output(self):
        llm = MockMASLLM(responses={"recognition": D1_RESPONSE})
        worker = LLMWorker(domain="D1", llm_client=llm)
        comp = Component(component_id="C1")
        inp = D1Input(query="What is 2+2?")

        result = await worker.process(comp, inp, "gpt-4o-mini")

        assert isinstance(result, DomainOutput)
        assert result.domain == "D1"
        assert result.status == DomainStatus.COMPLETED
        assert result.weight == 75
        assert result.gate_passed is True

    @pytest.mark.asyncio
    async def test_d1_worker_typed_output(self):
        llm = MockMASLLM(responses={"recognition": D1_RESPONSE})
        worker = LLMWorker(domain="D1", llm_client=llm)
        comp = Component(component_id="C1")
        inp = D1Input(query="What is 2+2?")

        result = await worker.process(comp, inp, "gpt-4o-mini")

        assert hasattr(result, '_typed_output')
        typed = result._typed_output
        assert isinstance(typed, D1Output)
        assert typed.task_type == "factual"
        assert len(typed.components) == 1
        assert typed.input_tokens == 100
        assert typed.output_tokens == 200

    @pytest.mark.asyncio
    async def test_d2_worker_typed_output(self):
        llm = MockMASLLM(responses={"clarification": D2_RESPONSE})
        worker = LLMWorker(domain="D2", llm_client=llm)
        comp = Component(component_id="C1")
        inp = D2Input(query="test", components=[{"id": "C1", "name": "test"}])

        result = await worker.process(comp, inp, "gpt-4o-mini")

        typed = result._typed_output
        assert isinstance(typed, D2Output)
        assert typed.hidden_assumptions == ["Numbers are base-10"]

    @pytest.mark.asyncio
    async def test_d3_worker_typed_output(self):
        llm = MockMASLLM(responses={"framework": D3_RESPONSE})
        worker = LLMWorker(domain="D3", llm_client=llm)
        comp = Component(component_id="C1")
        inp = D3Input(query="test")

        result = await worker.process(comp, inp, "gpt-4o-mini")

        typed = result._typed_output
        assert isinstance(typed, D3Output)
        assert typed.framework["name"] == "Deductive Reasoning"

    @pytest.mark.asyncio
    async def test_d4_worker_typed_output(self):
        llm = MockMASLLM(responses={"comparison": D4_RESPONSE})
        worker = LLMWorker(domain="D4", llm_client=llm)
        comp = Component(component_id="C1")
        inp = D4Input(query="test")

        result = await worker.process(comp, inp, "gpt-4o-mini")

        typed = result._typed_output
        assert isinstance(typed, D4Output)
        assert len(typed.comparisons) == 1

    @pytest.mark.asyncio
    async def test_d5_worker_typed_output(self):
        llm = MockMASLLM(responses={"inference": D5_RESPONSE})
        worker = LLMWorker(domain="D5", llm_client=llm)
        comp = Component(component_id="C1")
        inp = D5Input(query="test")

        result = await worker.process(comp, inp, "gpt-4o-mini")

        typed = result._typed_output
        assert isinstance(typed, D5Output)
        assert typed.answer == "4"
        assert typed.certainty_type == "necessary"
        assert typed.conclusion["answer"] == "4"

    @pytest.mark.asyncio
    async def test_d6_worker_typed_output(self):
        llm = MockMASLLM(responses={"reflection": D6_RESPONSE})
        worker = LLMWorker(domain="D6", llm_client=llm)
        comp = Component(component_id="C1")
        inp = D6Input(query="test")

        result = await worker.process(comp, inp, "gpt-4o-mini")

        typed = result._typed_output
        assert isinstance(typed, D6Output)
        assert len(typed.assumptions) == 1
        assert typed.return_assessment["errors_found"] is False

    @pytest.mark.asyncio
    async def test_worker_invalid_domain(self):
        llm = MockMASLLM()
        with pytest.raises(ValueError, match="Unknown domain"):
            LLMWorker(domain="D99", llm_client=llm)

    @pytest.mark.asyncio
    async def test_worker_retry_on_json_failure(self):
        """Worker retries when LLM returns invalid JSON first."""
        call_count = 0

        class RetryLLM(LLMClient):
            async def generate(self, prompt, system=""):
                return ""

            async def generate_with_usage(self, prompt, system=""):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return LLMResponse(text="not json", input_tokens=10, output_tokens=20)
                return LLMResponse(text=D1_RESPONSE, input_tokens=100, output_tokens=200)

        worker = LLMWorker(domain="D1", llm_client=RetryLLM(), max_retries=1)
        comp = Component(component_id="C1")
        inp = D1Input(query="test")

        result = await worker.process(comp, inp, "gpt-4o-mini")
        assert call_count == 2
        assert result.status == DomainStatus.COMPLETED
        assert "[RETRY" in result._typed_output.internal_log

    @pytest.mark.asyncio
    async def test_worker_error_after_retries_exhausted(self):
        """Worker raises WorkerError when all retries fail."""

        class BadLLM(LLMClient):
            async def generate(self, prompt, system=""):
                return ""

            async def generate_with_usage(self, prompt, system=""):
                return LLMResponse(text="not json at all", input_tokens=10, output_tokens=20)

        worker = LLMWorker(domain="D1", llm_client=BadLLM(), max_retries=1)
        comp = Component(component_id="C1")
        inp = D1Input(query="test")

        with pytest.raises(WorkerError, match="JSON parse failed"):
            await worker.process(comp, inp, "gpt-4o-mini")

    @pytest.mark.asyncio
    async def test_worker_llm_exception_raises_worker_error(self):
        """Worker wraps unexpected LLM errors in WorkerError."""

        class FailLLM(LLMClient):
            async def generate(self, prompt, system=""):
                raise RuntimeError("API down")

            async def generate_with_usage(self, prompt, system=""):
                raise RuntimeError("API down")

        worker = LLMWorker(domain="D1", llm_client=FailLLM(), max_retries=0)
        comp = Component(component_id="C1")
        inp = D1Input(query="test")

        with pytest.raises(WorkerError, match="LLM call failed"):
            await worker.process(comp, inp, "gpt-4o-mini")

    @pytest.mark.asyncio
    async def test_d5_content_is_answer(self):
        """D5 DomainOutput.content should be the answer text."""
        llm = MockMASLLM(responses={"inference": D5_RESPONSE})
        worker = LLMWorker(domain="D5", llm_client=llm)
        comp = Component(component_id="C1")
        inp = D5Input(query="test")

        result = await worker.process(comp, inp, "gpt-4o-mini")
        # D5's content should be the answer
        assert result.content == "4"


# ============================================================
# TestWorkerFactory
# ============================================================

class TestWorkerFactory:
    """Tests for worker_factory module."""

    def test_model_registry_entries(self):
        assert "gpt-4o" in MODEL_REGISTRY
        assert "gpt-4o-mini" in MODEL_REGISTRY
        assert "sonnet" in MODEL_REGISTRY
        assert "haiku" in MODEL_REGISTRY
        assert "mini" in MODEL_REGISTRY

    def test_create_workers_from_routing_mock_fallback(self):
        """Unknown models in registry should fall back to MockWorker."""
        routing = RoutingConfig.default()
        # Hard routing uses "deepseek" which isn't in MODEL_REGISTRY
        workers = create_workers_from_routing(routing, complexity="hard")
        # D1 uses deepseek -> MockWorker fallback
        from regulus.mas.workers import MockWorker
        assert isinstance(workers["D1"], MockWorker)
        # D2 uses gpt-4o -> LLMWorker
        assert isinstance(workers["D2"], LLMWorker)

    def test_create_workers_easy_all_llm(self):
        """Easy routing uses gpt-4o-mini for all — should create LLMWorkers."""
        clear_client_cache()
        routing = RoutingConfig.default()
        workers = create_workers_from_routing(routing, complexity="easy")
        for code in DOMAIN_CODES:
            assert isinstance(workers[code], LLMWorker)
        clear_client_cache()

    def test_all_six_domains_created(self):
        clear_client_cache()
        routing = RoutingConfig.default()
        workers = create_workers_from_routing(routing, complexity="easy")
        assert set(workers.keys()) == set(DOMAIN_CODES)
        clear_client_cache()


# ============================================================
# TestPrompts
# ============================================================

class TestPrompts:
    """Tests for domain prompt modules."""

    def test_all_domains_have_prompts(self):
        for code in DOMAIN_CODES:
            assert code in DOMAIN_PROMPTS, f"Missing prompt for {code}"

    def test_orchestrator_prompt_exists(self):
        assert "orchestrator" in DOMAIN_PROMPTS

    def test_each_prompt_has_system_and_builder(self):
        for code in DOMAIN_CODES:
            mod = DOMAIN_PROMPTS[code]
            assert hasattr(mod, 'SYSTEM_PROMPT'), f"{code} missing SYSTEM_PROMPT"
            assert hasattr(mod, 'build_user_prompt'), f"{code} missing build_user_prompt"
            assert callable(mod.build_user_prompt)

    def test_d1_build_user_prompt(self):
        mod = DOMAIN_PROMPTS["D1"]
        result = mod.build_user_prompt(query="What is 2+2?", goal="Calculate sum")
        assert "What is 2+2?" in result
        assert "Calculate sum" in result

    def test_d5_build_user_prompt(self):
        mod = DOMAIN_PROMPTS["D5"]
        result = mod.build_user_prompt(
            query="test", goal="test",
            comparisons_json="[]", framework_json="{}",
        )
        assert "test" in result

    def test_d6_build_user_prompt(self):
        mod = DOMAIN_PROMPTS["D6"]
        result = mod.build_user_prompt(
            query="test", goal="test",
            conclusion_json="{}", full_table_summary="summary",
        )
        assert "summary" in result


# ============================================================
# TestTypedOutputChaining
# ============================================================

class TestTypedOutputChaining:
    """Tests for typed output chaining through the orchestrator."""

    @pytest.mark.asyncio
    async def test_orchestrator_with_llm_workers(self):
        """Full pipeline with LLM workers returns valid response."""
        llm = _make_domain_llm()
        workers = {}
        for code in DOMAIN_CODES:
            workers[code] = LLMWorker(domain=code, llm_client=llm, max_retries=0)

        orch = MASOrchestrator(workers=workers)
        resp = await orch.process_query("What is 2+2?")

        assert resp.answer  # has an answer
        assert resp.input_tokens > 0
        assert resp.output_tokens > 0

    @pytest.mark.asyncio
    async def test_d5_answer_extracted(self):
        """Orchestrator extracts answer from typed D5 output."""
        llm = _make_domain_llm()
        workers = {
            code: LLMWorker(domain=code, llm_client=llm, max_retries=0)
            for code in DOMAIN_CODES
        }

        orch = MASOrchestrator(workers=workers)
        resp = await orch.process_query("What is 2+2?")

        # D5 typed output has answer="4"
        assert resp.answer == "4"

    @pytest.mark.asyncio
    async def test_typed_outputs_chained(self):
        """D2 receives components from D1, D3 receives from D2, etc."""
        call_log = []

        class TracingLLM(LLMClient):
            async def generate(self, prompt, system=""):
                return ""

            async def generate_with_usage(self, prompt, system=""):
                call_log.append({"prompt": prompt, "system": system})
                # Return appropriate response based on system prompt
                sys_lower = system.lower()
                if "recognition" in sys_lower or "domain 1" in sys_lower:
                    return LLMResponse(text=D1_RESPONSE, input_tokens=10, output_tokens=20)
                elif "clarification" in sys_lower or "domain 2" in sys_lower:
                    return LLMResponse(text=D2_RESPONSE, input_tokens=10, output_tokens=20)
                elif "framework" in sys_lower or "domain 3" in sys_lower:
                    return LLMResponse(text=D3_RESPONSE, input_tokens=10, output_tokens=20)
                elif "comparison" in sys_lower or "domain 4" in sys_lower:
                    return LLMResponse(text=D4_RESPONSE, input_tokens=10, output_tokens=20)
                elif "inference" in sys_lower or "domain 5" in sys_lower:
                    return LLMResponse(text=D5_RESPONSE, input_tokens=10, output_tokens=20)
                elif "reflection" in sys_lower or "domain 6" in sys_lower:
                    return LLMResponse(text=D6_RESPONSE, input_tokens=10, output_tokens=20)
                return LLMResponse(text=D1_RESPONSE, input_tokens=10, output_tokens=20)

        workers = {
            code: LLMWorker(domain=code, llm_client=TracingLLM(), max_retries=0)
            for code in DOMAIN_CODES
        }

        orch = MASOrchestrator(workers=workers)
        resp = await orch.process_query("What is 2+2?")

        # All 6 domains should have been called
        assert len(call_log) == 6

        # D2 prompt should contain components from D1
        d2_prompt = call_log[1]["prompt"]
        assert "arithmetic" in d2_prompt  # D1 component name passed through

    @pytest.mark.asyncio
    async def test_mock_workers_still_work(self):
        """Orchestrator works with MockWorkers (no typed outputs)."""
        workers = {
            code: MockWorker(domain_code=code, content=f"Mock {code}")
            for code in DOMAIN_CODES
        }
        orch = MASOrchestrator(workers=workers)
        resp = await orch.process_query("test query")

        # Should still get answer from D5 content
        assert resp.answer == "Mock D5"
        assert resp.valid is True

    @pytest.mark.asyncio
    async def test_mixed_workers(self):
        """Mix of LLM and Mock workers doesn't crash."""
        llm = _make_domain_llm()
        workers = {}
        for code in DOMAIN_CODES:
            if code in ("D1", "D5"):
                workers[code] = LLMWorker(domain=code, llm_client=llm, max_retries=0)
            else:
                workers[code] = MockWorker(domain_code=code)

        orch = MASOrchestrator(workers=workers)
        resp = await orch.process_query("What is 2+2?")

        # D5 is LLM worker, should get typed answer
        assert resp.answer == "4"

    @pytest.mark.asyncio
    async def test_callbacks_with_llm_workers(self):
        """Callbacks fire correctly with LLM workers."""
        events = []

        def on_start(domain, name):
            events.append(("start", domain))

        def on_complete(domain, data):
            events.append(("complete", domain))

        llm = _make_domain_llm()
        workers = {
            code: LLMWorker(domain=code, llm_client=llm, max_retries=0)
            for code in DOMAIN_CODES
        }
        orch = MASOrchestrator(
            workers=workers,
            on_domain_start=on_start,
            on_domain_complete=on_complete,
        )
        await orch.process_query("test")

        start_domains = [e[1] for e in events if e[0] == "start"]
        assert "D1" in start_domains
        assert "D6" in start_domains
        assert "CLASSIFY" in start_domains
        assert "VERIFY" in start_domains
