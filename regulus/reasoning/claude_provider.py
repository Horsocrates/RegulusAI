"""
Regulus AI - Claude Thinking Provider
=======================================

Uses Claude's extended thinking feature. Returns thinking block summaries
(not full raw CoT — Claude only exposes summaries).
"""

import asyncio
import time
from typing import Optional

from .provider import ReasoningProvider, ReasoningResult, TraceFormat

MAX_RETRIES = 5
BASE_DELAY = 3.0


class ClaudeThinkingProvider(ReasoningProvider):
    """Claude extended thinking provider (summary traces)."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-4-6",
        budget_tokens: int = 10000,
        max_tokens: int = 64000,
        interleaved_thinking: bool = False,
        temperature: float = 1.0,
        use_tos_prompt: bool = False,
    ):
        from anthropic import AsyncAnthropic
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.budget_tokens = budget_tokens
        self.max_tokens = max_tokens
        self.interleaved_thinking = interleaved_thinking
        self.temperature = temperature
        self.use_tos_prompt = use_tos_prompt

    @property
    def name(self) -> str:
        return "claude-thinking"

    @property
    def default_trace_format(self) -> TraceFormat:
        return TraceFormat.SUMMARY

    async def reason(self, query: str, system: Optional[str] = None) -> ReasoningResult:
        from anthropic import RateLimitError

        start = time.time()

        # Resolve system prompt: explicit > ToS > None
        effective_system = system
        if effective_system is None and self.use_tos_prompt:
            from regulus.reasoning.tos_prompt import TOS_SYSTEM_PROMPT
            effective_system = TOS_SYSTEM_PROMPT

        for attempt in range(MAX_RETRIES):
            try:
                kwargs: dict = {
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "thinking": {
                        "type": "enabled",
                        "budget_tokens": self.budget_tokens,
                    },
                    "messages": [{"role": "user", "content": query}],
                }
                if effective_system:
                    kwargs["system"] = effective_system
                if self.interleaved_thinking:
                    kwargs["betas"] = ["interleaved-thinking-2025-05-14"]
                if self.temperature != 1.0:
                    kwargs["temperature"] = self.temperature

                response = await self.client.messages.create(**kwargs)
                elapsed = time.time() - start

                # Extract thinking and answer from content blocks
                thinking_parts = []
                answer_parts = []
                for block in response.content:
                    if block.type == "thinking":
                        thinking_parts.append(block.thinking)
                    elif block.type == "text":
                        answer_parts.append(block.text)

                thinking = "\n".join(thinking_parts)
                answer = "\n".join(answer_parts)

                return ReasoningResult(
                    answer=answer,
                    thinking=thinking,
                    trace_format=TraceFormat.SUMMARY if thinking else TraceFormat.NONE,
                    model=self.model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    reasoning_tokens=0,
                    time_seconds=elapsed,
                )
            except RateLimitError:
                if attempt == MAX_RETRIES - 1:
                    raise
                delay = BASE_DELAY * (2 ** attempt)
                print(f"[Claude] Rate limit hit, retry {attempt + 1}/{MAX_RETRIES} in {delay:.0f}s")
                await asyncio.sleep(delay)

        raise RuntimeError("Unreachable")
