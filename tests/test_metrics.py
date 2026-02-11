"""Tests for Lab v2 Metrics aggregation."""

import pytest

from regulus.api.models.lab import QuestionResult
from regulus.lab.metrics import (
    compute_run_metrics,
    DomainMetrics,
    TeamMetrics,
    RunMetrics,
)


def _make_result(
    idx=0, domain="boolean_expressions", team_index=0,
    verdict="correct", status="completed",
    time_ms=1000, tokens_in=500, tokens_out=200, cost=0.01,
):
    return QuestionResult(
        id=f"r-{idx}",
        run_id="run-1",
        question_index=idx,
        question_id=f"q-{idx}",
        domain=domain,
        input_text=f"Question {idx}",
        team_index=team_index,
        status=status,
        final_answer=f"Answer {idx}",
        judgment_verdict=verdict,
        judgment_confidence=1.0,
        judgment_explanation="test",
        total_time_ms=time_ms,
        total_tokens_in=tokens_in,
        total_tokens_out=tokens_out,
        estimated_cost=cost,
    )


# ===================================================================
# Empty results
# ===================================================================


class TestEmptyMetrics:
    def test_empty_results(self):
        m = compute_run_metrics([])
        assert m.total_questions == 0
        assert m.completed_questions == 0
        assert m.accuracy == 0.0

    def test_empty_with_total(self):
        m = compute_run_metrics([], total_questions=10)
        assert m.total_questions == 10
        assert m.completed_questions == 0


# ===================================================================
# Basic aggregation
# ===================================================================


class TestBasicAggregation:
    def test_all_correct(self):
        results = [_make_result(i, verdict="correct") for i in range(5)]
        m = compute_run_metrics(results)
        assert m.correct_count == 5
        assert m.wrong_count == 0
        assert m.accuracy == 1.0

    def test_all_wrong(self):
        results = [_make_result(i, verdict="wrong") for i in range(3)]
        m = compute_run_metrics(results)
        assert m.correct_count == 0
        assert m.wrong_count == 3
        assert m.accuracy == 0.0

    def test_mixed_verdicts(self):
        results = [
            _make_result(0, verdict="correct"),
            _make_result(1, verdict="wrong"),
            _make_result(2, verdict="correct"),
            _make_result(3, verdict="partial"),
            _make_result(4, verdict="wrong"),
        ]
        m = compute_run_metrics(results)
        assert m.correct_count == 2
        assert m.wrong_count == 2
        assert m.partial_count == 1
        assert m.accuracy == pytest.approx(2 / 5)

    def test_errors_excluded_from_accuracy(self):
        results = [
            _make_result(0, verdict="correct"),
            _make_result(1, verdict="wrong"),
            _make_result(2, status="error", verdict="error"),
        ]
        m = compute_run_metrics(results)
        assert m.error_count == 1
        assert m.completed_questions == 2
        assert m.accuracy == pytest.approx(1 / 2)

    def test_total_questions_override(self):
        results = [_make_result(0), _make_result(1)]
        m = compute_run_metrics(results, total_questions=10)
        assert m.total_questions == 10
        assert m.completed_questions == 2


# ===================================================================
# Token & cost aggregation
# ===================================================================


class TestTokenCostAggregation:
    def test_totals(self):
        results = [
            _make_result(0, tokens_in=100, tokens_out=50, cost=0.01),
            _make_result(1, tokens_in=200, tokens_out=80, cost=0.02),
        ]
        m = compute_run_metrics(results)
        assert m.total_tokens_in == 300
        assert m.total_tokens_out == 130
        assert m.total_cost == pytest.approx(0.03)

    def test_averages(self):
        results = [
            _make_result(0, time_ms=1000, tokens_in=100, tokens_out=50, cost=0.01),
            _make_result(1, time_ms=3000, tokens_in=300, tokens_out=150, cost=0.03),
        ]
        m = compute_run_metrics(results)
        assert m.avg_time_per_question_ms == pytest.approx(2000)
        assert m.avg_tokens_per_question == pytest.approx(300)
        assert m.avg_cost_per_question == pytest.approx(0.02)


# ===================================================================
# Domain metrics
# ===================================================================


class TestDomainMetrics:
    def test_single_domain(self):
        results = [
            _make_result(0, domain="math", verdict="correct"),
            _make_result(1, domain="math", verdict="wrong"),
        ]
        m = compute_run_metrics(results)
        assert "math" in m.by_domain
        dm = m.by_domain["math"]
        assert dm.total == 2
        assert dm.correct == 1
        assert dm.wrong == 1
        assert dm.accuracy == pytest.approx(0.5)

    def test_multiple_domains(self):
        results = [
            _make_result(0, domain="math", verdict="correct"),
            _make_result(1, domain="logic", verdict="correct"),
            _make_result(2, domain="logic", verdict="wrong"),
        ]
        m = compute_run_metrics(results)
        assert len(m.by_domain) == 2
        assert m.by_domain["math"].accuracy == 1.0
        assert m.by_domain["logic"].accuracy == pytest.approx(0.5)

    def test_domain_avg_time(self):
        results = [
            _make_result(0, domain="d1", time_ms=1000),
            _make_result(1, domain="d1", time_ms=3000),
        ]
        m = compute_run_metrics(results)
        assert m.by_domain["d1"].avg_time_ms == pytest.approx(2000)

    def test_domain_tokens_cost(self):
        results = [
            _make_result(0, domain="d1", tokens_in=100, tokens_out=50, cost=0.01),
            _make_result(1, domain="d1", tokens_in=200, tokens_out=100, cost=0.02),
        ]
        m = compute_run_metrics(results)
        dm = m.by_domain["d1"]
        assert dm.total_tokens_in == 300
        assert dm.total_tokens_out == 150
        assert dm.total_cost == pytest.approx(0.03)


# ===================================================================
# Team metrics
# ===================================================================


class TestTeamMetrics:
    def test_single_team(self):
        results = [_make_result(i, team_index=0) for i in range(3)]
        m = compute_run_metrics(results)
        assert 0 in m.by_team
        assert m.by_team[0].total == 3

    def test_multiple_teams(self):
        results = [
            _make_result(0, team_index=0, verdict="correct"),
            _make_result(1, team_index=0, verdict="correct"),
            _make_result(2, team_index=1, verdict="correct"),
            _make_result(3, team_index=1, verdict="wrong"),
        ]
        m = compute_run_metrics(results)
        assert len(m.by_team) == 2
        assert m.by_team[0].accuracy == 1.0
        assert m.by_team[1].accuracy == pytest.approx(0.5)

    def test_team_avg_time(self):
        results = [
            _make_result(0, team_index=0, time_ms=500),
            _make_result(1, team_index=0, time_ms=1500),
            _make_result(2, team_index=1, time_ms=3000),
        ]
        m = compute_run_metrics(results)
        assert m.by_team[0].avg_time_ms == pytest.approx(1000)
        assert m.by_team[1].avg_time_ms == pytest.approx(3000)


# ===================================================================
# Serialization
# ===================================================================


class TestMetricsSerialization:
    def test_run_metrics_to_dict(self):
        results = [
            _make_result(0, domain="d1", team_index=0, verdict="correct"),
            _make_result(1, domain="d2", team_index=1, verdict="wrong"),
        ]
        m = compute_run_metrics(results)
        d = m.to_dict()
        assert isinstance(d, dict)
        assert d["total_questions"] == 2
        assert "d1" in d["by_domain"]
        assert "0" in d["by_team"]  # keys are stringified ints

    def test_domain_metrics_to_dict(self):
        dm = DomainMetrics(
            domain="test", total=10, correct=7, wrong=2, partial=1,
            error=0, accuracy=0.7, avg_time_ms=1500.5,
        )
        d = dm.to_dict()
        assert d["domain"] == "test"
        assert d["accuracy"] == 0.7

    def test_team_metrics_to_dict(self):
        tm = TeamMetrics(
            team_index=0, total=5, correct=4, wrong=1,
            accuracy=0.8, avg_time_ms=2000.3,
        )
        d = tm.to_dict()
        assert d["team_index"] == 0
        assert d["accuracy"] == 0.8
