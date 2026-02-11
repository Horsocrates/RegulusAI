"""
Lab v2 Judge — Strict and Semantic evaluation modes.

StrictJudge: Normalized exact-match (no LLM call, free, instant).
SemanticJudge: LLM-based semantic comparison (uses existing CrossJudge).

Both return a unified JudgmentResult dataclass.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class JudgmentResult:
    """Unified judgment result for Lab v2."""
    verdict: str  # "correct" | "wrong" | "partial" | "error"
    confidence: float  # 0.0–1.0
    explanation: str
    judge_model: str  # "exact_match" or LLM model name
    judged_at: str = ""

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "judge_model": self.judge_model,
            "judged_at": self.judged_at,
        }


class StrictJudge:
    """Exact match judge — normalizes both answers and compares.

    Best for benchmarks with clear, unambiguous answers (BBEH, math, etc.).
    Zero cost, instant evaluation.
    """

    def evaluate(
        self,
        model_answer: str,
        expected_answer: str,
        question: Optional[str] = None,
    ) -> JudgmentResult:
        model_norm = self._normalize(model_answer or "")
        expected_norm = self._normalize(expected_answer or "")

        is_correct = model_norm == expected_norm

        return JudgmentResult(
            verdict="correct" if is_correct else "wrong",
            confidence=1.0,
            explanation=f"Normalized match: '{model_norm}' == '{expected_norm}'" if is_correct
                        else f"Mismatch: '{model_norm}' != '{expected_norm}'",
            judge_model="exact_match",
            judged_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize answer for comparison."""
        text = text.lower().strip()

        # Remove common answer prefixes
        prefixes = [
            "the answer is", "answer:", "final answer:", "therefore,",
            "the correct answer is", "my answer is", "result:",
        ]
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()

        # Remove trailing period
        if text.endswith("."):
            text = text[:-1].strip()

        # Remove surrounding quotes
        if len(text) >= 2 and text[0] in ('"', "'") and text[-1] == text[0]:
            text = text[1:-1].strip()

        # Remove punctuation (but keep digits and letters)
        text = re.sub(r'[^\w\s]', '', text)

        # Collapse whitespace
        text = ' '.join(text.split())

        return text


class SemanticJudge:
    """LLM-based semantic judge — uses CrossJudge for cross-provider evaluation.

    Best for open-ended questions where exact match is too strict.
    """

    def __init__(self):
        self._cross_judge = None

    def _get_cross_judge(self):
        if self._cross_judge is None:
            from regulus.judge import CrossJudge
            self._cross_judge = CrossJudge()
        return self._cross_judge

    def evaluate(
        self,
        model_answer: str,
        expected_answer: str,
        question: Optional[str] = None,
        answer_provider: str = "openai",
    ) -> JudgmentResult:
        judge = self._get_cross_judge()
        result = judge.evaluate(
            question=question or "",
            reference=expected_answer,
            answer=model_answer or "",
            answer_provider=answer_provider,
        )

        truthful = result.get("truthful")
        informative = result.get("informative")

        # Handle judge errors (None values)
        if truthful is None or informative is None:
            return JudgmentResult(
                verdict="error",
                confidence=0.0,
                explanation=result.get("truth_reason", "") or result.get("info_reason", ""),
                judge_model="cross_judge",
                judged_at=datetime.now(timezone.utc).isoformat(),
            )

        if truthful and informative:
            verdict = "correct"
        elif truthful and not informative:
            verdict = "partial"
        else:
            verdict = "wrong"

        confidence = result.get("truth_confidence", 50) / 100.0

        return JudgmentResult(
            verdict=verdict,
            confidence=confidence,
            explanation=result.get("truth_reason", ""),
            judge_model="cross_judge",
            judged_at=datetime.now(timezone.utc).isoformat(),
        )


def create_judge(config: dict) -> StrictJudge | SemanticJudge:
    """Create judge from config dict.

    config keys:
        strict_mode: bool (default False) — use exact match
    """
    if config.get("strict_mode", False):
        return StrictJudge()
    return SemanticJudge()
