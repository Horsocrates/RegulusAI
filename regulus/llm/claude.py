"""
Regulus AI - Claude LLM Client
===============================

Claude API integration via Anthropic SDK.
"""

from .client import LLMClient


class ClaudeClient(LLMClient):
    """Claude API client adapter."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        from anthropic import AsyncAnthropic
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def generate(self, prompt: str, system: str | None = None) -> str:
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system or "",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
