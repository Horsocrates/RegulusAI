"""
Regulus AI - Hybrid LLM Client
===============================

Routes requests to different models based on domain context.
- Heavy domains (D4, D5, final_answer) → GPT-4o (accuracy)
- Light domains (D1, D2, D3, D6, probes) → GPT-4o-mini (cost)

Cost savings: ~70% vs pure 4o, ~25 runs/month vs ~7.
"""

from .client import LLMClient, LLMResponse
from .openai import OpenAIClient


# Domains that need strong reasoning → 4o
HEAVY_DOMAINS = {"D4", "D5", "final"}

# Everything else → 4o-mini
# D1 (recognition), D2 (clarification), D3 (modeling), D6 (reflection), probes


class HybridClient(LLMClient):
    """Routes to 4o or 4o-mini based on current domain context."""

    def __init__(self, api_key: str, heavy_model: str = "gpt-4o", light_model: str = "gpt-4o-mini"):
        self.heavy = OpenAIClient(api_key=api_key, model=heavy_model)
        self.light = OpenAIClient(api_key=api_key, model=light_model)
        self._current_domain: str = ""  # Set by orchestrator before each call

    @property
    def current_domain(self) -> str:
        return self._current_domain

    @current_domain.setter
    def current_domain(self, domain: str):
        self._current_domain = domain

    def _pick_client(self) -> OpenAIClient:
        """Pick client based on current domain."""
        if self._current_domain in HEAVY_DOMAINS:
            return self.heavy
        return self.light

    @property
    def model(self) -> str:
        """Current model name for logging."""
        return self._pick_client().model

    async def generate(self, prompt: str, system: str | None = None) -> str:
        return await self._pick_client().generate(prompt, system)

    async def generate_with_usage(self, prompt: str, system: str | None = None) -> LLMResponse:
        return await self._pick_client().generate_with_usage(prompt, system)
