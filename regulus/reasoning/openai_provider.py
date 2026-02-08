"""
Regulus AI - OpenAI Reasoning Provider (Stub)
===============================================

Stub for OpenAI o-series models. Uses standard chat completion since
reasoning summaries are not yet exposed via the chat API.
"""

import asyncio
import time
from typing import Optional

from .provider import ReasoningProvider, ReasoningResult, TraceFormat

MAX_RETRIES = 5
BASE_DELAY = 3.0


class OpenAIReasoningProvider(ReasoningProvider):
    """OpenAI o-series reasoning provider (stub — no trace access yet)."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    @property
    def name(self) -> str:
        return "openai-reasoning"

    @property
    def default_trace_format(self) -> TraceFormat:
        return TraceFormat.NONE

    async def reason(self, query: str, system: Optional[str] = None) -> ReasoningResult:
        from openai import RateLimitError

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": query})

        start = time.time()

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=4096,
                    messages=messages,
                )
                elapsed = time.time() - start

                answer = response.choices[0].message.content or ""
                usage = response.usage

                return ReasoningResult(
                    answer=answer,
                    thinking="",
                    trace_format=TraceFormat.NONE,
                    model=self.model,
                    input_tokens=usage.prompt_tokens if usage else 0,
                    output_tokens=usage.completion_tokens if usage else 0,
                    reasoning_tokens=0,
                    time_seconds=elapsed,
                )
            except RateLimitError:
                if attempt == MAX_RETRIES - 1:
                    raise
                delay = BASE_DELAY * (2 ** attempt)
                print(f"[OpenAI] Rate limit hit, retry {attempt + 1}/{MAX_RETRIES} in {delay:.0f}s")
                await asyncio.sleep(delay)

        raise RuntimeError("Unreachable")
