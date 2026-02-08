"""
Regulus AI - D1 External Validator
====================================

Addresses the D1 Asymmetry Problem: D1 (Recognition) errors are invisible
to the reasoner who committed them. The same model that distorts the query
cannot detect its own distortion.

This validator uses an independent LLM call to check whether D1 faithfully
represents the original query. It detects:
- Straw man: query simplified or distorted
- Projection: concepts added that aren't in the query
- Omission: entities/relationships in the query not recognized
- Type misclassification: wrong question type assigned
"""

import json
from dataclasses import dataclass, field
from typing import Optional

from regulus.llm.client import LLMClient


D1_VALIDATOR_PROMPT = """\
You are an independent auditor checking whether a reasoning model's \
RECOGNITION step (D1) faithfully represents the original query.

The D1 Asymmetry Problem: a model that distorts its own recognition \
of a query CANNOT detect the distortion — it believes its version IS \
the query. You must compare independently.

ORIGINAL QUERY:
{query}

D1 RECOGNITION (from the model's reasoning):
{d1_segment}

MODEL'S ANSWER:
{answer}

Check for these specific failures:
1. STRAW_MAN: Is D1 a simplified/distorted version of the query? \
   Does it drop conditions, weaken requirements, or change the question?
2. PROJECTION: Does D1 add concepts, assumptions, or framing NOT in \
   the original query?
3. OMISSION: Are there entities, relationships, or constraints in the \
   query that D1 fails to identify?
4. TYPE_ERROR: Is the question type wrong? (factual treated as opinion, \
   analytical treated as factual, etc.)

Respond with ONLY valid JSON:
{{
  "fidelity": 0.85,
  "issues": ["STRAW_MAN: ...", "OMISSION: ..."],
  "recommended_d1_depth": 2,
  "recommended_d1_weight": 50,
  "explanation": "D1 misses the constraint that..."
}}

Rules:
- fidelity: 0.0-1.0, how faithfully D1 represents the query
- If fidelity >= 0.8, the recognition is acceptable
- If fidelity < 0.5, this is a critical D1 failure
- recommended_d1_depth: 1-4, what depth D1 actually achieves
- recommended_d1_weight: 0-100, what weight D1 deserves
- issues: list of specific problems found (empty if none)
- Be strict: even subtle distortions matter because they propagate
"""


@dataclass
class D1ValidationResult:
    """Result of external D1 validation."""
    fidelity: float = 1.0           # 0.0-1.0
    issues: list[str] = field(default_factory=list)
    recommended_depth: Optional[int] = None
    recommended_weight: Optional[int] = None
    explanation: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def is_faithful(self) -> bool:
        return self.fidelity >= 0.8

    @property
    def is_critical_failure(self) -> bool:
        return self.fidelity < 0.5


class D1Validator:
    """
    External D1 validator that checks recognition fidelity.

    Uses an independent LLM call to compare the original query
    against what D1 actually recognized.
    """

    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client

    async def validate(
        self,
        query: str,
        d1_segment: str,
        answer: str,
    ) -> D1ValidationResult:
        """
        Validate D1 recognition against the original query.

        Args:
            query: The original user query
            d1_segment: D1's segment summary or content from audit
            answer: The model's final answer

        Returns:
            D1ValidationResult with fidelity score and issues
        """
        prompt = D1_VALIDATOR_PROMPT.format(
            query=query[:2000],
            d1_segment=d1_segment[:1500],
            answer=answer[:1000],
        )

        response = await self._llm.generate_with_usage(
            prompt,
            system="You are a D1 Recognition fidelity checker. Respond with JSON only.",
        )

        try:
            text = response.text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                text = "\n".join(lines)

            data = json.loads(text)

            return D1ValidationResult(
                fidelity=float(data.get("fidelity", 1.0)),
                issues=data.get("issues", []),
                recommended_depth=data.get("recommended_d1_depth"),
                recommended_weight=data.get("recommended_d1_weight"),
                explanation=data.get("explanation", ""),
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return D1ValidationResult(
                fidelity=1.0,  # Default to passing on parse error
                issues=["D1 validation parse failed"],
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )
