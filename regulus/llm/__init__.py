"""
Regulus AI - LLM Integration Module
====================================

Provides LLM client adapters, signal extraction, diagnostic probing,
and source verification.
"""

from .client import LLMClient
from .claude import ClaudeClient
from .openai import OpenAIClient
from .sensor import HeuristicSignalExtractor, LLMSignalExtractor
from .prober import Prober, evaluate_and_probe
from .source_verifier import (
    SourceVerifier,
    SourceResult,
    VerificationResult,
    verify_and_enhance,
)

__all__ = [
    "LLMClient",
    "ClaudeClient",
    "OpenAIClient",
    "HeuristicSignalExtractor",
    "LLMSignalExtractor",
    "Prober",
    "evaluate_and_probe",
    "SourceVerifier",
    "SourceResult",
    "VerificationResult",
    "verify_and_enhance",
]
