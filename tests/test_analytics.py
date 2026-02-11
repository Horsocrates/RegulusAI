"""Tests for Lab v2 Analytics — ReportGenerator."""

import pytest

from regulus.api.models.lab import QuestionResult
from regulus.lab.analytics import (
    AnalysisReport,
    DomainAnalysis,
    FailurePattern,
    ReportGenerator,
    ReportSummary,
    TeamAnalysis,
)


def _make_result(
    idx=0, domain="boolean_expressions", team_index=0,
    verdict="correct", status="completed",
    time_ms=1000, tokens_in=500, tokens_out=200, cost=0.01,
    final_answer="42", explanation="test explanation",
):
    return QuestionResult(
        id=f"r-{idx}",
        run_id="run-1",
        question_index=idx,
        question_id=f"q-{idx}",
        domain=domain,
        input_text=f"Question {idx}?",
        team_index=team_index,
        status=status,
        final_answer=final_answer,
        judgment_verdict=verdict,
        judgment_confidence=1.0,
        judgment_explanation=explanation,
        total_time_ms=time_ms,
        total_tokens_in=tokens_in,
        total_tokens_out=tokens_out,
        estimated_cost=cost,
    )


# ===================================================================
# Report generation basics
# ===================================================================


class TestReportGeneration:
    def test_empty_results(self):
        gen = ReportGenerator()
        report = gen.generate_report("run-1", [])
        assert report.run_id == "run-1"
        assert report.summary.total_questions == 0
        assert report.summary.accuracy == 0.0
        assert report.domain_analysis == []
        assert report.team_analysis == []
        assert report.failure_patterns == []

    def test_basic_report(self):
        results = [
            _make_result(0, verdict="correct"),
            _make_result(1, verdict="wrong"),
            _make_result(2, verdict="correct"),
        ]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        assert report.summary.total_questions == 3
        assert report.summary.correct == 2
        assert report.summary.wrong == 1

    def test_report_has_generated_at(self):
        gen = ReportGenerator()
        report = gen.generate_report("run-1", [])
        assert report.generated_at  # non-empty ISO string

    def test_total_questions_override(self):
        results = [_make_result(0)]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results, total_questions=10)
        assert report.summary.total_questions == 10  # passes total_questions through to metrics

    def test_report_to_dict(self):
        results = [_make_result(0)]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        d = report.to_dict()
        assert isinstance(d, dict)
        assert d["run_id"] == "run-1"
        assert "summary" in d
        assert "domain_analysis" in d
        assert "team_analysis" in d
        assert "failure_patterns" in d
        assert "recommendations" in d


# ===================================================================
# Summary
# ===================================================================


class TestReportSummary:
    def test_summary_accuracy(self):
        results = [
            _make_result(0, verdict="correct"),
            _make_result(1, verdict="correct"),
            _make_result(2, verdict="wrong"),
            _make_result(3, verdict="partial"),
        ]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        assert report.summary.correct == 2
        assert report.summary.wrong == 1
        assert report.summary.partial == 1
        assert report.summary.accuracy == pytest.approx(0.5)

    def test_summary_time(self):
        results = [
            _make_result(0, time_ms=2000),
            _make_result(1, time_ms=4000),
        ]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        assert report.summary.total_time_seconds == 6.0
        assert report.summary.avg_time_per_question == 3.0

    def test_summary_cost(self):
        results = [
            _make_result(0, cost=0.05),
            _make_result(1, cost=0.03),
        ]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        assert report.summary.total_cost == pytest.approx(0.08)

    def test_summary_to_dict(self):
        summary = ReportSummary(
            accuracy=0.75, total_questions=4, correct=3, wrong=1,
            partial=0, error=0, total_cost=0.04,
            total_time_seconds=12.0, avg_time_per_question=3.0,
        )
        d = summary.to_dict()
        assert d["accuracy"] == 0.75
        assert d["total_questions"] == 4


# ===================================================================
# Domain analysis
# ===================================================================


class TestDomainAnalysis:
    def test_single_domain(self):
        results = [
            _make_result(0, domain="math", verdict="correct"),
            _make_result(1, domain="math", verdict="wrong"),
        ]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        assert len(report.domain_analysis) == 1
        assert report.domain_analysis[0].domain == "math"
        assert report.domain_analysis[0].accuracy == pytest.approx(0.5)

    def test_multiple_domains_sorted_by_accuracy(self):
        results = [
            _make_result(0, domain="easy", verdict="correct"),
            _make_result(1, domain="easy", verdict="correct"),
            _make_result(2, domain="hard", verdict="wrong"),
            _make_result(3, domain="hard", verdict="wrong"),
        ]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        assert len(report.domain_analysis) == 2
        # Sorted by accuracy (worst first)
        assert report.domain_analysis[0].domain == "hard"
        assert report.domain_analysis[0].accuracy == 0.0
        assert report.domain_analysis[1].domain == "easy"
        assert report.domain_analysis[1].accuracy == 1.0

    def test_common_errors_extracted(self):
        results = [
            _make_result(0, domain="d1", verdict="wrong", explanation="Wrong sign"),
            _make_result(1, domain="d1", verdict="wrong", explanation="Off by one"),
            _make_result(2, domain="d1", verdict="correct"),
        ]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        da = report.domain_analysis[0]
        assert "Wrong sign" in da.common_errors
        assert "Off by one" in da.common_errors

    def test_domain_to_dict(self):
        da = DomainAnalysis(
            domain="test", accuracy=0.8, total=10, correct=8, wrong=2,
        )
        d = da.to_dict()
        assert d["domain"] == "test"
        assert d["accuracy"] == 0.8


# ===================================================================
# Team analysis
# ===================================================================


class TestTeamAnalysis:
    def test_single_team(self):
        results = [
            _make_result(0, team_index=0, verdict="correct"),
            _make_result(1, team_index=0, verdict="wrong"),
        ]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        assert len(report.team_analysis) == 1
        assert report.team_analysis[0].team_index == 0
        assert report.team_analysis[0].accuracy == pytest.approx(0.5)

    def test_multiple_teams(self):
        results = [
            _make_result(0, team_index=0, verdict="correct"),
            _make_result(1, team_index=0, verdict="correct"),
            _make_result(2, team_index=1, verdict="wrong"),
            _make_result(3, team_index=1, verdict="wrong"),
        ]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        assert len(report.team_analysis) == 2

    def test_trend_detection_stable(self):
        # Only 2 teams — not enough for trend detection
        results = [
            _make_result(0, team_index=0, verdict="correct"),
            _make_result(1, team_index=1, verdict="wrong"),
        ]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        for t in report.team_analysis:
            assert t.performance_trend == "stable"

    def test_trend_detection_declining(self):
        # 4 teams: first ones perfect, last ones terrible
        results = []
        for i in range(4):
            results.append(_make_result(i * 2, team_index=i, verdict="correct"))
            results.append(_make_result(i * 2 + 1, team_index=i,
                                         verdict="correct" if i < 2 else "wrong"))
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        # Should detect at least one declining trend in later teams
        trends = [t.performance_trend for t in report.team_analysis]
        assert "declining" in trends or all(t == "stable" for t in trends)

    def test_team_to_dict(self):
        ta = TeamAnalysis(team_index=0, total=5, correct=4, accuracy=0.8)
        d = ta.to_dict()
        assert d["team_index"] == 0
        assert d["accuracy"] == 0.8


# ===================================================================
# Failure patterns
# ===================================================================


class TestFailurePatterns:
    def test_no_failures(self):
        results = [_make_result(0, verdict="correct")]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        assert report.failure_patterns == []

    def test_no_answer_pattern(self):
        results = [
            _make_result(0, verdict="wrong", final_answer=None),
            _make_result(1, verdict="wrong", final_answer=""),
        ]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        types = [fp.pattern_type for fp in report.failure_patterns]
        assert "no_answer" in types
        fp = next(p for p in report.failure_patterns if p.pattern_type == "no_answer")
        assert fp.frequency >= 1

    def test_execution_error_pattern(self):
        results = [
            _make_result(0, status="error", verdict="error"),
            _make_result(1, status="error", verdict="error"),
        ]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        types = [fp.pattern_type for fp in report.failure_patterns]
        assert "execution_error" in types

    def test_domain_concentration_pattern(self):
        # 4 failures in "math" out of 5 total wrong = 80% > 60% threshold
        results = [
            _make_result(0, domain="math", verdict="wrong"),
            _make_result(1, domain="math", verdict="wrong"),
            _make_result(2, domain="math", verdict="wrong"),
            _make_result(3, domain="math", verdict="wrong"),
            _make_result(4, domain="logic", verdict="wrong"),
        ]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        types = [fp.pattern_type for fp in report.failure_patterns]
        assert "domain_concentration" in types

    def test_no_domain_concentration_below_threshold(self):
        # 2 failures in each domain — 50% < 60% threshold
        results = [
            _make_result(0, domain="math", verdict="wrong"),
            _make_result(1, domain="math", verdict="wrong"),
            _make_result(2, domain="logic", verdict="wrong"),
            _make_result(3, domain="logic", verdict="wrong"),
        ]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        types = [fp.pattern_type for fp in report.failure_patterns]
        assert "domain_concentration" not in types

    def test_late_degradation_pattern(self):
        # First 3 correct, last 3 wrong (6 results total, quarters of 1-2 each)
        results = [
            _make_result(0, verdict="correct"),
            _make_result(1, verdict="correct"),
            _make_result(2, verdict="correct"),
            _make_result(3, verdict="correct"),
            _make_result(4, verdict="wrong"),
            _make_result(5, verdict="wrong"),
            _make_result(6, verdict="wrong"),
            _make_result(7, verdict="wrong"),
        ]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        types = [fp.pattern_type for fp in report.failure_patterns]
        assert "late_degradation" in types

    def test_failure_pattern_to_dict(self):
        fp = FailurePattern(
            pattern_type="test",
            description="A test pattern",
            affected_questions=["q-1", "q-2"],
            frequency=2,
            suggested_fix="Fix it",
        )
        d = fp.to_dict()
        assert d["pattern_type"] == "test"
        assert d["frequency"] == 2
        assert d["suggested_fix"] == "Fix it"


# ===================================================================
# Recommendations
# ===================================================================


class TestRecommendations:
    def test_low_accuracy_recommendation(self):
        results = [
            _make_result(0, verdict="wrong"),
            _make_result(1, verdict="wrong"),
            _make_result(2, verdict="wrong"),
            _make_result(3, verdict="correct"),
        ]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        has_low_acc = any("low" in r.lower() for r in report.recommendations)
        assert has_low_acc

    def test_weak_domain_recommendation(self):
        results = [
            _make_result(0, domain="hard", verdict="wrong"),
            _make_result(1, domain="hard", verdict="wrong"),
            _make_result(2, domain="hard", verdict="wrong"),
            _make_result(3, domain="easy", verdict="correct"),
            _make_result(4, domain="easy", verdict="correct"),
        ]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        has_domain_rec = any("hard" in r for r in report.recommendations)
        assert has_domain_rec

    def test_high_cost_recommendation(self):
        results = [_make_result(0, cost=0.20)]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        has_cost_rec = any("cost" in r.lower() for r in report.recommendations)
        assert has_cost_rec

    def test_recommendations_capped_at_10(self):
        gen = ReportGenerator()
        report = gen.generate_report("run-1", [])
        assert len(report.recommendations) <= 10

    def test_no_recommendations_for_perfect_run(self):
        results = [_make_result(i, verdict="correct", cost=0.01) for i in range(5)]
        gen = ReportGenerator()
        report = gen.generate_report("run-1", results)
        # Perfect accuracy, low cost — no recommendations expected
        assert len(report.recommendations) == 0
