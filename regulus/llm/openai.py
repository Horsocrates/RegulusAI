"""
Regulus AI - OpenAI LLM Client
===============================

OpenAI API integration.
"""

import asyncio

from .client import LLMClient, LLMResponse

MAX_RETRIES = 5
BASE_DELAY = 3.0  # seconds


class OpenAIClient(LLMClient):
    """OpenAI API client adapter."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate(self, prompt: str, system: str | None = None) -> str:
        response = await self._call_api(prompt, system)
        return response.text

    async def generate_with_usage(self, prompt: str, system: str | None = None) -> LLMResponse:
        return await self._call_api(prompt, system)

    async def _call_api(self, prompt: str, system: str | None = None) -> LLMResponse:
        from openai import RateLimitError

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=2048,
                    messages=messages
                )

                usage = response.usage
                return LLMResponse(
                    text=response.choices[0].message.content or "",
                    input_tokens=usage.prompt_tokens if usage else 0,
                    output_tokens=usage.completion_tokens if usage else 0,
                )
            except RateLimitError as e:
                if attempt == MAX_RETRIES - 1:
                    raise
                delay = BASE_DELAY * (2 ** attempt)
                print(f"[OpenAI] Rate limit hit, retry {attempt + 1}/{MAX_RETRIES} in {delay:.0f}s")
                await asyncio.sleep(delay)
