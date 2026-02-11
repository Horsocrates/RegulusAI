"""
Lab v2 Metrics — aggregation from QuestionResult records.

Computes run-level, domain-level, and team-level metrics from
stored question results. No in-memory state needed — reads from DB.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from regulus.api.models.lab import QuestionResult


@dataclass
class DomainMetrics:
    """Metrics aggregated by benchmark domain."""
    domain: str
    total: int
    correct: int
    wrong: int
    partial: int
    error: int
    accuracy: float
    avg_time_ms: float
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_cost: float = 0.0

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "total": self.total,
            "correct": self.correct,
            "wrong": self.wrong,
            "partial": self.partial,
            "error": self.error,
            "accuracy": round(self.accuracy, 4),
            "avg_time_ms": round(self.avg_time_ms, 1),
            "total_tokens_in": self.total_tokens_in,
            "total_tokens_out": self.total_tokens_out,
            "total_cost": round(self.total_cost, 6),
        }


@dataclass
class TeamMetrics:
    """Metrics aggregated by team rotation."""
    team_index: int
    total: int
    correct: int
    wrong: int
    accuracy: float
    avg_time_ms: float

    def to_dict(self) -> dict:
        return {
            "team_index": self.team_index,
            "total": self.total,
            "correct": self.correct,
            "wrong": self.wrong,
            "accuracy": round(self.accuracy, 4),
            "avg_time_ms": round(self.avg_time_ms, 1),
        }


@dataclass
class RunMetrics:
    """Aggregated metrics for an entire test run."""
    total_questions: int
    completed_questions: int
    correct_count: int
    wrong_count: int
    partial_count: int
    error_count: int

    total_time_ms: int
    total_tokens_in: int
    total_tokens_out: int
    total_cost: float

    avg_time_per_question_ms: float
    avg_tokens_per_question: float
    avg_cost_per_question: float

    accuracy: float  # correct / (completed - errors)

    by_domain: dict[str, DomainMetrics] = field(default_factory=dict)
    by_team: dict[int, TeamMetrics] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total_questions": self.total_questions,
            "completed_questions": self.completed_questions,
            "correct_count": self.correct_count,
            "wrong_count": self.wrong_count,
            "partial_count": self.partial_count,
            "error_count": self.error_count,
            "total_time_ms": self.total_time_ms,
            "total_tokens_in": self.total_tokens_in,
            "total_tokens_out": self.total_tokens_out,
            "total_cost": round(self.total_cost, 6),
            "avg_time_per_question_ms": round(self.avg_time_per_question_ms, 1),
            "avg_tokens_per_question": round(self.avg_tokens_per_question, 1),
            "avg_cost_per_question": round(self.avg_cost_per_question, 6),
            "accuracy": round(self.accuracy, 4),
            "by_domain": {k: v.to_dict() for k, v in self.by_domain.items()},
            "by_team": {str(k): v.to_dict() for k, v in self.by_team.items()},
        }


def compute_run_metrics(
    results: list[QuestionResult],
    total_questions: int = 0,
) -> RunMetrics:
    """Compute aggregated metrics from a list of QuestionResults.

    Args:
        results: List of question results from DB.
        total_questions: Total expected questions (for progress calculation).
                         If 0, uses len(results).
    """
    if not results:
        return _empty_metrics(total_questions)

    n = len(results)
    if total_questions <= 0:
        total_questions = n

    correct = sum(1 for r in results if r.judgment_verdict == "correct")
    wrong = sum(1 for r in results if r.judgment_verdict == "wrong")
    partial = sum(1 for r in results if r.judgment_verdict == "partial")
    errors = sum(1 for r in results if r.status == "error")
    completed = n - errors

    total_time = sum(r.total_time_ms for r in results)
    total_in = sum(r.total_tokens_in for r in results)
    total_out = sum(r.total_tokens_out for r in results)
    total_cost = sum(r.estimated_cost for r in results)

    accuracy = correct / completed if completed > 0 else 0.0

    by_domain = _aggregate_by_domain(results)
    by_team = _aggregate_by_team(results)

    return RunMetrics(
        total_questions=total_questions,
        completed_questions=completed,
        correct_count=correct,
        wrong_count=wrong,
        partial_count=partial,
        error_count=errors,
        total_time_ms=total_time,
        total_tokens_in=total_in,
        total_tokens_out=total_out,
        total_cost=total_cost,
        avg_time_per_question_ms=total_time / n if n else 0,
        avg_tokens_per_question=(total_in + total_out) / n if n else 0,
        avg_cost_per_question=total_cost / n if n else 0,
        accuracy=accuracy,
        by_domain=by_domain,
        by_team=by_team,
    )


def _aggregate_by_domain(results: list[QuestionResult]) -> dict[str, DomainMetrics]:
    """Aggregate metrics by domain."""
    data = defaultdict(lambda: {
        "total": 0, "correct": 0, "wrong": 0, "partial": 0, "error": 0,
        "times": [], "tokens_in": 0, "tokens_out": 0, "cost": 0.0,
    })

    for r in results:
        d = data[r.domain]
        d["total"] += 1
        if r.judgment_verdict == "correct":
            d["correct"] += 1
        elif r.judgment_verdict == "wrong":
            d["wrong"] += 1
        elif r.judgment_verdict == "partial":
            d["partial"] += 1
        if r.status == "error":
            d["error"] += 1
        d["times"].append(r.total_time_ms)
        d["tokens_in"] += r.total_tokens_in
        d["tokens_out"] += r.total_tokens_out
        d["cost"] += r.estimated_cost

    return {
        domain: DomainMetrics(
            domain=domain,
            total=dd["total"],
            correct=dd["correct"],
            wrong=dd["wrong"],
            partial=dd["partial"],
            error=dd["error"],
            accuracy=dd["correct"] / dd["total"] if dd["total"] else 0,
            avg_time_ms=sum(dd["times"]) / len(dd["times"]) if dd["times"] else 0,
            total_tokens_in=dd["tokens_in"],
            total_tokens_out=dd["tokens_out"],
            total_cost=dd["cost"],
        )
        for domain, dd in sorted(data.items())
    }


def _aggregate_by_team(results: list[QuestionResult]) -> dict[int, TeamMetrics]:
    """Aggregate metrics by team index."""
    data = defaultdict(lambda: {
        "total": 0, "correct": 0, "wrong": 0, "times": [],
    })

    for r in results:
        td = data[r.team_index]
        td["total"] += 1
        if r.judgment_verdict == "correct":
            td["correct"] += 1
        elif r.judgment_verdict == "wrong":
            td["wrong"] += 1
        td["times"].append(r.total_time_ms)

    return {
        idx: TeamMetrics(
            team_index=idx,
            total=td["total"],
            correct=td["correct"],
            wrong=td["wrong"],
            accuracy=td["correct"] / td["total"] if td["total"] else 0,
            avg_time_ms=sum(td["times"]) / len(td["times"]) if td["times"] else 0,
        )
        for idx, td in sorted(data.items())
    }


def _empty_metrics(total_questions: int = 0) -> RunMetrics:
    return RunMetrics(
        total_questions=total_questions,
        completed_questions=0,
        correct_count=0,
        wrong_count=0,
        partial_count=0,
        error_count=0,
        total_time_ms=0,
        total_tokens_in=0,
        total_tokens_out=0,
        total_cost=0.0,
        avg_time_per_question_ms=0,
        avg_tokens_per_question=0,
        avg_cost_per_question=0,
        accuracy=0.0,
    )
