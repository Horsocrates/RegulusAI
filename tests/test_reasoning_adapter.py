"""Tests for ReasoningProviderAdapter and R1 integration."""

import asyncio
import pytest

from regulus.llm.client import LLMResponse
from regulus.reasoning.provider import ReasoningProvider, ReasoningResult, TraceFormat
from regulus.mas.reasoning_adapter import ReasoningProviderAdapter, ReasoningLLMResponse
from regulus.mas.worker_factory import MODEL_REGISTRY, _get_client, clear_client_cache
from regulus.mas.routing import RoutingConfig
from regulus.mas.table import DomainOutput, DomainStatus, TaskTable, Component, DOMAIN_CODES
from regulus.mas.types import MASResponse


# --- Mock ReasoningProvider ---

class MockReasoningProvider(ReasoningProvider):
    """Mock reasoning provider for testing the adapter."""

    def __init__(self, answer="42", thinking="Let me think...", reasoning_tokens=500):
        self._answer = answer
        self._thinking = thinking
        self._reasoning_tokens = reasoning_tokens
        self.calls = []

    @property
    def name(self) -> str:
        return "mock-reasoning"

    @property
    def default_trace_format(self) -> TraceFormat:
        return TraceFormat.FULL_COT

    async def reason(self, query, system=None):
        self.calls.append({"query": query, "system": system})
        return ReasoningResult(
            answer=self._answer,
            thinking=self._thinking,
            trace_format=TraceFormat.FULL_COT,
            model="mock-reasoner",
            input_tokens=100,
            output_tokens=50,
            reasoning_tokens=self._reasoning_tokens,
            time_seconds=1.5,
        )


# --- Tests: ReasoningLLMResponse ---

class TestReasoningLLMResponse:
    def test_is_subclass_of_llm_response(self):
        r = ReasoningLLMResponse(text="hello", input_tokens=10, output_tokens=5)
        assert isinstance(r, LLMResponse)

    def test_has_reasoning_tokens(self):
        r = ReasoningLLMResponse(
            text="answer", input_tokens=100, output_tokens=50,
            reasoning_tokens=500, thinking="my thoughts",
        )
        assert r.reasoning_tokens == 500
        assert r.thinking == "my thoughts"
        assert r.text == "answer"

    def test_total_tokens_excludes_reasoning(self):
        """LLMResponse.total_tokens = input + output (not reasoning)."""
        r = ReasoningLLMResponse(
            text="x", input_tokens=100, output_tokens=50, reasoning_tokens=500,
        )
        assert r.total_tokens == 150

    def test_defaults(self):
        r = ReasoningLLMResponse(text="hi")
        assert r.reasoning_tokens == 0
        assert r.thinking == ""


# --- Tests: ReasoningProviderAdapter ---

class TestReasoningProviderAdapter:
    @pytest.mark.asyncio
    async def test_generate_returns_answer(self):
        provider = MockReasoningProvider(answer="The answer is 42")
        adapter = ReasoningProviderAdapter(provider)
        result = await adapter.generate("What is the meaning of life?")
        assert result == "The answer is 42"

    @pytest.mark.asyncio
    async def test_generate_passes_system_prompt(self):
        provider = MockReasoningProvider()
        adapter = ReasoningProviderAdapter(provider)
        await adapter.generate("query", system="Be helpful")
        assert provider.calls[0]["system"] == "Be helpful"

    @pytest.mark.asyncio
    async def test_generate_with_usage_returns_reasoning_response(self):
        provider = MockReasoningProvider(
            answer="42", thinking="deep thoughts", reasoning_tokens=1000,
        )
        adapter = ReasoningProviderAdapter(provider)
        response = await adapter.generate_with_usage("query")
        assert isinstance(response, ReasoningLLMResponse)
        assert response.text == "42"
        assert response.input_tokens == 100
        assert response.output_tokens == 50
        assert response.reasoning_tokens == 1000
        assert response.thinking == "deep thoughts"

    def test_adapter_is_llm_client(self):
        from regulus.llm.client import LLMClient
        provider = MockReasoningProvider()
        adapter = ReasoningProviderAdapter(provider)
        assert isinstance(adapter, LLMClient)

    @pytest.mark.asyncio
    async def test_multiple_calls_tracked(self):
        provider = MockReasoningProvider()
        adapter = ReasoningProviderAdapter(provider)
        await adapter.generate("q1")
        await adapter.generate("q2", system="sys")
        assert len(provider.calls) == 2
        assert provider.calls[0]["query"] == "q1"
        assert provider.calls[1]["system"] == "sys"


# --- Tests: MODEL_REGISTRY R1 entries ---

class TestModelRegistryR1:
    def test_deepseek_r1_in_registry(self):
        assert "deepseek-r1" in MODEL_REGISTRY
        provider, model = MODEL_REGISTRY["deepseek-r1"]
        assert provider == "deepseek-reasoning"
        assert model == "deepseek-reasoner"

    def test_r1_alias_in_registry(self):
        assert "r1" in MODEL_REGISTRY
        provider, model = MODEL_REGISTRY["r1"]
        assert provider == "deepseek-reasoning"
        assert model == "deepseek-reasoner"

    def test_deepseek_chat_still_works(self):
        assert "deepseek" in MODEL_REGISTRY
        provider, model = MODEL_REGISTRY["deepseek"]
        assert provider == "deepseek"
        assert model == "deepseek-chat"


# --- Tests: all-R1 routing ---

class TestAllR1Routing:
    def test_all_r1_routing_exists(self):
        routing = RoutingConfig.all_r1()
        assert routing is not None

    def test_all_r1_uses_deepseek_r1_everywhere(self):
        routing = RoutingConfig.all_r1()
        for complexity in ["easy", "medium", "hard"]:
            for domain in ["D1", "D2", "D3", "D4", "D5", "D6"]:
                model = routing.get_model(complexity, domain)
                assert model == "deepseek-r1", f"{complexity}/{domain} got {model}"

    def test_default_routing_unchanged(self):
        """Ensure adding all_r1 didn't break default routing."""
        routing = RoutingConfig.default()
        assert routing.get_model("easy", "D1") == "gpt-4o-mini"
        assert routing.get_model("hard", "D4") == "deepseek"


# --- Tests: DomainOutput reasoning_tokens ---

class TestDomainOutputReasoningTokens:
    def test_reasoning_tokens_field(self):
        d = DomainOutput(
            domain="D4", status=DomainStatus.COMPLETED,
            input_tokens=100, output_tokens=50, reasoning_tokens=500,
        )
        assert d.reasoning_tokens == 500

    def test_reasoning_tokens_default_zero(self):
        d = DomainOutput(domain="D1")
        assert d.reasoning_tokens == 0

    def test_reasoning_tokens_serialized(self):
        d = DomainOutput(
            domain="D1", status=DomainStatus.COMPLETED,
            reasoning_tokens=1000,
        )
        data = d.to_dict()
        assert data["reasoning_tokens"] == 1000

    def test_reasoning_tokens_deserialized(self):
        d = DomainOutput.from_dict({
            "domain": "D4",
            "status": "completed",
            "reasoning_tokens": 750,
        })
        assert d.reasoning_tokens == 750

    def test_reasoning_tokens_missing_in_dict(self):
        """Backward compat: old data without reasoning_tokens."""
        d = DomainOutput.from_dict({"domain": "D1", "status": "completed"})
        assert d.reasoning_tokens == 0


# --- Tests: TaskTable total_reasoning_tokens ---

class TestTaskTableReasoningTokens:
    def test_total_reasoning_tokens(self):
        comp = Component(component_id="C1")
        comp.domains["D1"] = DomainOutput(
            domain="D1", status=DomainStatus.COMPLETED, reasoning_tokens=100,
        )
        comp.domains["D4"] = DomainOutput(
            domain="D4", status=DomainStatus.COMPLETED, reasoning_tokens=500,
        )
        table = TaskTable(query="test", components=[comp])
        assert table.total_reasoning_tokens == 600

    def test_total_reasoning_tokens_zero_default(self):
        comp = Component(component_id="C1")
        comp.init_domains()
        table = TaskTable(query="test", components=[comp])
        assert table.total_reasoning_tokens == 0


# --- Tests: MASResponse reasoning_tokens ---

class TestMASResponseReasoningTokens:
    def test_reasoning_tokens_field(self):
        r = MASResponse(
            query="test", answer="42",
            input_tokens=1000, output_tokens=500, reasoning_tokens=5000,
        )
        assert r.reasoning_tokens == 5000

    def test_reasoning_tokens_default_zero(self):
        r = MASResponse()
        assert r.reasoning_tokens == 0


# --- Tests: Full pipeline with adapter ---

class TestAdapterInPipeline:
    @pytest.mark.asyncio
    async def test_llm_worker_with_adapter(self):
        """LLMWorker processes domain with ReasoningProviderAdapter and tracks reasoning_tokens."""
        from regulus.mas.llm_worker import LLMWorker
        from regulus.mas.contracts import D1Input

        provider = MockReasoningProvider(
            answer='{"components": [{"name": "test", "type": "value"}], "task_type": "analytical", "internal_log": "R1 reasoning"}',
            reasoning_tokens=800,
        )
        adapter = ReasoningProviderAdapter(provider)
        worker = LLMWorker(domain="D1", llm_client=adapter, max_retries=0)

        comp = Component(component_id="C1", description="test")
        comp.init_domains()
        d1_input = D1Input(query="What is 2+2?", goal="solve", component_id="C1", component_description="test")

        result = await worker.process(comp, d1_input, "deepseek-r1")

        assert result.status == DomainStatus.COMPLETED
        assert result.model_used == "deepseek-r1"
        assert result.reasoning_tokens == 800
        assert result.input_tokens == 100
        assert result.output_tokens == 50

    @pytest.mark.asyncio
    async def test_non_reasoning_worker_zero_reasoning_tokens(self):
        """Standard LLMClient returns zero reasoning_tokens."""
        from regulus.mas.llm_worker import LLMWorker
        from regulus.mas.contracts import D1Input

        class FakeLLM:
            async def generate_with_usage(self, prompt, system=None):
                return LLMResponse(
                    text='{"components": [{"name": "x"}], "task_type": "analytical", "internal_log": "ok"}',
                    input_tokens=50,
                    output_tokens=30,
                )

        worker = LLMWorker(domain="D1", llm_client=FakeLLM(), max_retries=0)
        comp = Component(component_id="C1", description="test")
        comp.init_domains()
        d1_input = D1Input(query="test", goal="test", component_id="C1", component_description="test")

        result = await worker.process(comp, d1_input, "gpt-4o-mini")
        assert result.reasoning_tokens == 0
