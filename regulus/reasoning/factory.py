"""
Regulus AI - Reasoning Provider Factory
========================================

Factory function to instantiate reasoning providers by name.
"""

from typing import Optional

from .provider import ReasoningProvider


def get_provider(name: str, api_key: str = "", **kwargs) -> ReasoningProvider:
    """
    Get a reasoning provider by name.

    Args:
        name: Provider name ('deepseek', 'claude-thinking', 'openai-reasoning')
        api_key: API key for the provider
        **kwargs: Additional provider-specific arguments

    Returns:
        ReasoningProvider instance
    """
    if name == "deepseek":
        from .deepseek_provider import DeepSeekProvider
        return DeepSeekProvider(api_key=api_key, **kwargs)
    elif name == "claude-thinking":
        from .claude_provider import ClaudeThinkingProvider
        return ClaudeThinkingProvider(api_key=api_key, **kwargs)
    elif name == "openai-reasoning":
        from .openai_provider import OpenAIReasoningProvider
        return OpenAIReasoningProvider(api_key=api_key, **kwargs)
    else:
        raise ValueError(
            f"Unknown reasoning provider: {name!r}. "
            f"Available: 'deepseek', 'claude-thinking', 'openai-reasoning'"
        )
