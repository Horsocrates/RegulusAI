"""
Regulus AI - Reasoning Providers
=================================

Abstraction layer for reasoning models (DeepSeek-R1, Claude thinking, OpenAI o-series).
Each provider returns a ReasoningResult with the model's answer and chain-of-thought trace.
"""

from .provider import TraceFormat, ReasoningResult, ReasoningProvider

__all__ = ["TraceFormat", "ReasoningResult", "ReasoningProvider", "get_provider"]


def get_provider(name: str, api_key: str = "", **kwargs) -> ReasoningProvider:
    """Convenience re-export. See factory.py for details."""
    from .factory import get_provider as _get
    return _get(name, api_key=api_key, **kwargs)

__all__ = ["TraceFormat", "ReasoningResult", "ReasoningProvider", "get_provider"]
