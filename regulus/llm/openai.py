"""
Regulus AI - OpenAI LLM Client
===============================

OpenAI API integration.
"""

from .client import LLMClient


class OpenAIClient(LLMClient):
    """OpenAI API client adapter."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=2048,
            messages=messages
        )
        return response.choices[0].message.content or ""
