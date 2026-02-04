"""
Regulus AI - LLM Integration Module
====================================

Provides LLM client adapters and signal extraction via LLM.
"""

from .client import LLMClient
from .claude import ClaudeClient
from .openai import OpenAIClient
from .sensor import HeuristicSignalExtractor, LLMSignalExtractor

__all__ = [
    "LLMClient",
    "ClaudeClient",
    "OpenAIClient",
    "HeuristicSignalExtractor",
    "LLMSignalExtractor",
]
