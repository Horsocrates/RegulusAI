"""
Regulus AI - Base LLM Client
=============================

Abstract base class for LLM integrations.
"""

from abc import ABC, abstractmethod


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
