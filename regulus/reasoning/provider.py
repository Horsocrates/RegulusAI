"""
Regulus AI - Reasoning Provider ABC
=====================================

Defines the abstract interface for reasoning models and shared data types.

TraceFormat indicates what kind of chain-of-thought the provider exposes:
- FULL_COT: Raw, unedited chain-of-thought (DeepSeek-R1)
- SUMMARY: Condensed thinking summary (Claude extended thinking, OpenAI o-series)
- NONE: No reasoning trace available (fallback / standard chat models)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TraceFormat(Enum):
    FULL_COT = "full_cot"
    SUMMARY = "summary"
    NONE = "none"


@dataclass
class ReasoningResult:
    """Output from a reasoning model."""
    answer: str
    thinking: str = ""
    trace_format: TraceFormat = TraceFormat.NONE
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    time_seconds: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.reasoning_tokens

    @property
    def has_trace(self) -> bool:
        return self.trace_format != TraceFormat.NONE and bool(self.thinking)


class ReasoningProvider(ABC):
    """Abstract base class for reasoning model providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'deepseek', 'claude-thinking')."""
        ...

    @property
    @abstractmethod
    def default_trace_format(self) -> TraceFormat:
        """The trace format this provider typically returns."""
        ...

    @abstractmethod
    async def reason(self, query: str, system: Optional[str] = None) -> ReasoningResult:
        """
        Send a query to the reasoning model and return the result.

        Args:
            query: The question or problem to reason about.
            system: Optional system prompt.

        Returns:
            ReasoningResult with answer, thinking trace, and usage info.
        """
        ...
