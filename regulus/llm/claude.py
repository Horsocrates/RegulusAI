"""
Regulus AI - Claude LLM Client
===============================

Claude API integration via Anthropic SDK.
"""

from .client import LLMClient, LLMResponse


class ClaudeClient(LLMClient):
    """Claude API client adapter."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        from anthropic import AsyncAnthropic
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def generate(self, prompt: str, system: str | None = None) -> str:
        response = await self._call_api(prompt, system)
        return response.text

    async def generate_with_usage(self, prompt: str, system: str | None = None) -> LLMResponse:
        return await self._call_api(prompt, system)

    async def _call_api(self, prompt: str, system: str | None = None) -> LLMResponse:
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system or "",
            messages=[{"role": "user", "content": prompt}]
        )
        return LLMResponse(
            text=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
