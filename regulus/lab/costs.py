"""
Cost estimation for LLM API usage.

Pricing as of 2024 (per 1M tokens):
- Claude Sonnet 4: $3 input, $15 output
- GPT-4o: $2.50 input, $10 output
- GPT-4o-mini: $0.15 input, $0.60 output

Note: Judge calls use the opposite provider (cross-judge architecture).
"""

from dataclasses import dataclass
from typing import Optional


# Pricing per 1M tokens (in USD)
PRICING = {
    "claude": {
        "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
        "default": {"input": 3.00, "output": 15.00},
    },
    "openai": {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "default": {"input": 2.50, "output": 10.00},
    },
}

# Estimated tokens per question (based on Socratic pipeline)
# This includes: 6 domain passes + synthesis + judge
ESTIMATED_TOKENS_PER_QUESTION = {
    "input": 8000,   # ~8K input tokens per question
    "output": 4000,  # ~4K output tokens per question
}


@dataclass
class CostEstimate:
    """Cost estimation result."""
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    provider: str
    currency: str = "USD"

    def to_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "input_cost": round(self.input_cost, 4),
            "output_cost": round(self.output_cost, 4),
            "total_cost": round(self.total_cost, 4),
            "provider": self.provider,
            "currency": self.currency,
        }


def get_pricing(provider: str, model: Optional[str] = None) -> dict:
    """Get pricing for a provider/model."""
    provider_pricing = PRICING.get(provider, PRICING["claude"])
    if model and model in provider_pricing:
        return provider_pricing[model]
    return provider_pricing["default"]


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    provider: str,
    model: Optional[str] = None,
) -> CostEstimate:
    """Calculate cost for given token usage."""
    pricing = get_pricing(provider, model)

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    return CostEstimate(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_cost=input_cost,
        output_cost=output_cost,
        total_cost=input_cost + output_cost,
        provider=provider,
    )


def estimate_run_cost(
    total_questions: int,
    provider: str,
    model: Optional[str] = None,
) -> CostEstimate:
    """
    Estimate cost for a full benchmark run.

    Uses average token estimates per question.
    """
    input_tokens = total_questions * ESTIMATED_TOKENS_PER_QUESTION["input"]
    output_tokens = total_questions * ESTIMATED_TOKENS_PER_QUESTION["output"]

    return calculate_cost(input_tokens, output_tokens, provider, model)


def estimate_remaining_cost(
    remaining_questions: int,
    avg_input_tokens_per_q: float,
    avg_output_tokens_per_q: float,
    provider: str,
    model: Optional[str] = None,
) -> CostEstimate:
    """
    Estimate cost for remaining questions based on actual averages.
    """
    input_tokens = int(remaining_questions * avg_input_tokens_per_q)
    output_tokens = int(remaining_questions * avg_output_tokens_per_q)

    return calculate_cost(input_tokens, output_tokens, provider, model)


def format_cost(cost: float, currency: str = "USD") -> str:
    """Format cost for display."""
    if cost < 0.01:
        return f"<$0.01"
    elif cost < 1.00:
        return f"${cost:.2f}"
    else:
        return f"${cost:.2f}"


def format_tokens(tokens: int) -> str:
    """Format token count for display."""
    if tokens < 1000:
        return str(tokens)
    elif tokens < 1_000_000:
        return f"{tokens / 1000:.1f}K"
    else:
        return f"{tokens / 1_000_000:.2f}M"
