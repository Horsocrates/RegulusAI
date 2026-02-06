"""
Regulus AI - Base LLM Client
=============================

Abstract base class for LLM integrations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    """Response from LLM with usage information."""
    text: str
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMClient(ABC):
    """Base class for LLM client adapters."""

    @abstractmethod
    async def generate(self, prompt: str, system: str | None = None) -> str:
        """
        Generate a response from the LLM.

        Args:
            prompt: User prompt
            system: Optional system prompt

        Returns:
            Generated text response
        """
        ...

    async def generate_with_usage(self, prompt: str, system: str | None = None) -> LLMResponse:
        """
        Generate a response with token usage information.

        Default implementation calls generate() without usage tracking.
        Override in subclasses to provide actual usage data.
        """
        text = await self.generate(prompt, system)
        return LLMResponse(text=text)
