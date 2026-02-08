"""
Regulus AI - DeepSeek Reasoning Provider
==========================================

DeepSeek-R1 exposes full raw chain-of-thought via `message.reasoning_content`.
Uses the OpenAI-compatible API at https://api.deepseek.com.
"""

import asyncio
import time
from typing import Optional

from .provider import ReasoningProvider, ReasoningResult, TraceFormat

MAX_RETRIES = 5
BASE_DELAY = 3.0


class DeepSeekProvider(ReasoningProvider):
    """DeepSeek-R1 reasoning provider with full CoT access."""

    def __init__(self, api_key: str, model: str = "deepseek-reasoner", use_tos_prompt: bool = False):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
        self.model = model
        self.use_tos_prompt = use_tos_prompt

    @property
    def name(self) -> str:
        return "deepseek"

    @property
    def default_trace_format(self) -> TraceFormat:
        return TraceFormat.FULL_COT

    async def reason(self, query: str, system: Optional[str] = None) -> ReasoningResult:
        from openai import RateLimitError

        # Resolve system prompt: explicit > ToS > None
        effective_system = system
        if effective_system is None and self.use_tos_prompt:
            from regulus.reasoning.tos_prompt import TOS_SYSTEM_PROMPT
            effective_system = TOS_SYSTEM_PROMPT

        messages = []
        if effective_system:
            messages.append({"role": "system", "content": effective_system})
        messages.append({"role": "user", "content": query})

        start = time.time()

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                )
                elapsed = time.time() - start

                choice = response.choices[0]
                answer = choice.message.content or ""
                thinking = getattr(choice.message, "reasoning_content", "") or ""

                usage = response.usage
                input_tokens = usage.prompt_tokens if usage else 0
                output_tokens = usage.completion_tokens if usage else 0
                reasoning_tokens = 0
                if usage and hasattr(usage, "completion_tokens_details"):
                    details = usage.completion_tokens_details
                    if details and hasattr(details, "reasoning_tokens"):
                        reasoning_tokens = details.reasoning_tokens or 0

                return ReasoningResult(
                    answer=answer,
                    thinking=thinking,
                    trace_format=TraceFormat.FULL_COT if thinking else TraceFormat.NONE,
                    model=self.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    reasoning_tokens=reasoning_tokens,
                    time_seconds=elapsed,
                )
            except RateLimitError:
                if attempt == MAX_RETRIES - 1:
                    raise
                delay = BASE_DELAY * (2 ** attempt)
                print(f"[DeepSeek] Rate limit hit, retry {attempt + 1}/{MAX_RETRIES} in {delay:.0f}s")
                await asyncio.sleep(delay)

        raise RuntimeError("Unreachable")
