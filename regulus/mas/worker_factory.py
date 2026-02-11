"""
Regulus AI - MAS Worker Factory
================================

Creates domain workers from routing configuration.
Reads the routing config (which model for which domain)
and creates appropriately configured LLMWorker instances.
"""

import os
from typing import Optional

from regulus.llm.client import LLMClient
from regulus.llm.openai import OpenAIClient
from regulus.llm.claude import ClaudeClient
from regulus.llm.deepseek import DeepSeekClient
from regulus.mas.llm_worker import LLMWorker
from regulus.mas.workers import DomainWorker, MockWorker
from regulus.mas.routing import RoutingConfig
from regulus.mas.table import DOMAIN_CODES


# Model string -> (provider, model_name)
MODEL_REGISTRY = {
    # OpenAI
    "gpt-4o": ("openai", "gpt-4o"),
    "gpt-4o-mini": ("openai", "gpt-4o-mini"),
    # Anthropic
    "sonnet": ("anthropic", "claude-sonnet-4-20250514"),
    "haiku": ("anthropic", "claude-haiku-4-5-20251001"),
    # DeepSeek
    "deepseek": ("deepseek", "deepseek-chat"),
    "deepseek-chat": ("deepseek", "deepseek-chat"),
    # DeepSeek R1 (reasoning model — uses ReasoningProviderAdapter)
    "deepseek-r1": ("deepseek-reasoning", "deepseek-reasoner"),
    "r1": ("deepseek-reasoning", "deepseek-reasoner"),
    # Short aliases
    "mini": ("openai", "gpt-4o-mini"),
}

# Cached clients to avoid re-creating for each worker
_client_cache: dict[str, LLMClient] = {}


def _get_client(model_key: str) -> LLMClient:
    """Get or create an LLM client for the given model key."""
    if model_key in _client_cache:
        return _client_cache[model_key]

    if model_key not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model: {model_key}. "
            f"Available: {list(MODEL_REGISTRY.keys())}"
        )

    provider, model_name = MODEL_REGISTRY[model_key]

    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        client = OpenAIClient(api_key=api_key, model=model_name)
    elif provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        client = ClaudeClient(api_key=api_key, model=model_name)
    elif provider == "deepseek":
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        client = DeepSeekClient(api_key=api_key, model=model_name)
    elif provider == "deepseek-reasoning":
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        from regulus.reasoning.deepseek_provider import DeepSeekProvider
        from regulus.mas.reasoning_adapter import ReasoningProviderAdapter
        reasoning_provider = DeepSeekProvider(api_key=api_key, model=model_name)
        client = ReasoningProviderAdapter(reasoning_provider)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    _client_cache[model_key] = client
    return client


def create_worker(domain: str, model_key: str, max_retries: int = 1) -> LLMWorker:
    """
    Create an LLM worker for a specific domain.

    Args:
        domain: "D1" through "D6"
        model_key: Key from MODEL_REGISTRY (e.g., "haiku", "gpt-4o-mini")
        max_retries: Retries on parse failure

    Returns:
        Configured LLMWorker
    """
    client = _get_client(model_key)
    return LLMWorker(domain=domain, llm_client=client, max_retries=max_retries)


def create_workers_from_routing(
    routing: RoutingConfig,
    complexity: str = "easy",
) -> dict[str, DomainWorker]:
    """
    Create all domain workers based on routing config and complexity.

    Args:
        routing: The routing configuration
        complexity: "easy", "medium", or "hard"

    Returns:
        Dict mapping domain code -> DomainWorker
    """
    workers = {}

    for domain in DOMAIN_CODES:
        model_key = routing.get_model(complexity, domain)

        if model_key in MODEL_REGISTRY:
            retries = 1 if complexity == "hard" else 0
            workers[domain] = create_worker(
                domain=domain, model_key=model_key, max_retries=retries,
            )
        else:
            # Unknown model key — fallback to mock
            workers[domain] = MockWorker(domain_code=domain)

    return workers


def clear_client_cache():
    """Clear the cached LLM clients (useful for testing)."""
    _client_cache.clear()
