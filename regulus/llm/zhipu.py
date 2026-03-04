"""
Regulus AI - ZhipuAI (GLM-5) LLM Client
==========================================

ZhipuAI API (OpenAI-compatible) for structured JSON generation.
Uses GLM-5 model via open.bigmodel.cn/api/paas/v4/.
"""

import asyncio

from .client import LLMClient, LLMResponse

MAX_RETRIES = 5
BASE_DELAY = 3.0


class ZhipuClient(LLMClient):
    """ZhipuAI API client (OpenAI-compatible)."""

    def __init__(self, api_key: str, model: str = "glm-4-plus"):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://open.bigmodel.cn/api/paas/v4/",
        )
        self.model = model

    async def generate(self, prompt: str, system: str | None = None) -> str:
        response = await self._call_api(prompt, system)
        return response.text

    async def generate_with_usage(self, prompt: str, system: str | None = None) -> LLMResponse:
        return await self._call_api(prompt, system)

    async def _call_api(self, prompt: str, system: str | None = None, max_tokens: int = 8192) -> LLMResponse:
        from openai import RateLimitError

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=messages,
                )

                usage = response.usage
                return LLMResponse(
                    text=response.choices[0].message.content or "",
                    input_tokens=usage.prompt_tokens if usage else 0,
                    output_tokens=usage.completion_tokens if usage else 0,
                )
            except RateLimitError:
                if attempt == MAX_RETRIES - 1:
                    raise
                delay = BASE_DELAY * (2 ** attempt)
                print(f"[ZhipuAI] Rate limit hit, retry {attempt + 1}/{MAX_RETRIES} in {delay:.0f}s")
                await asyncio.sleep(delay)
