"""
Regulus AI - Reasoning Provider Adapter
========================================

Wraps a ReasoningProvider (DeepSeek-R1, etc.) as an LLMClient
so reasoning models can be used as MAS domain workers.
"""

from dataclasses import dataclass
from typing import Optional

from regulus.llm.client import LLMClient, LLMResponse
from regulus.reasoning.provider import ReasoningProvider


@dataclass
class ReasoningLLMResponse(LLMResponse):
    """LLMResponse with additional reasoning token tracking."""
    reasoning_tokens: int = 0
    thinking: str = ""


class ReasoningProviderAdapter(LLMClient):
    """
    Wraps a ReasoningProvider to work as an LLMClient.

    This allows reasoning models like DeepSeek-R1 to be used as
    domain workers in the MAS pipeline. The reasoning trace is
    discarded for the domain output, but reasoning_tokens are
    tracked via ReasoningLLMResponse for cost analysis.
    """

    def __init__(self, provider: ReasoningProvider):
        self.provider = provider

    async def generate(self, prompt: str, system: str | None = None) -> str:
        result = await self.provider.reason(prompt, system=system)
        return result.answer

    async def generate_with_usage(
        self, prompt: str, system: str | None = None
    ) -> ReasoningLLMResponse:
        result = await self.provider.reason(prompt, system=system)
        return ReasoningLLMResponse(
            text=result.answer,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            reasoning_tokens=result.reasoning_tokens,
            thinking=result.thinking,
        )
