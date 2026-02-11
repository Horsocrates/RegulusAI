"""
Lab v2 Analytics — Report generation from test run results.

Generates analysis reports with:
- Summary statistics
- Per-domain analysis with common errors
- Per-team analysis with performance trends
- Failure pattern detection
- Actionable recommendations
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from regulus.api.models.lab import QuestionResult
from regulus.lab.metrics import RunMetrics, compute_run_metrics


@dataclass
class ReportSummary:
    accuracy: float
    total_questions: int
    correct: int
    wrong: int
    partial: int
    error: int
    total_cost: float
    total_time_seconds: float
    avg_time_per_question: float

    def to_dict(self) -> dict:
        return {
            "accuracy": round(self.accuracy, 4),
            "total_questions": self.total_questions,
            "correct": self.correct,
            "wrong": self.wrong,
            "partial": self.partial,
            "error": self.error,
            "total_cost": round(self.total_cost, 6),
            "total_time_seconds": round(self.total_time_seconds, 2),
            "avg_time_per_question": round(self.avg_time_per_question, 2),
        }


@dataclass
class DomainAnalysis:
    domain: str
    accuracy: float
    total: int
    correct: int
    wrong: int
    common_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "accuracy": round(self.accuracy, 4),
            "total": self.total,
            "correct": self.correct,
            "wrong": self.wrong,
            "common_errors": self.common_errors,
        }


@dataclass
class TeamAnalysis:
    team_index: int
    total: int
    correct: int
    accuracy: float
    performance_trend: str = "stable"  # "improving" | "declining" | "stable"

    def to_dict(self) -> dict:
        return {
            "team_index": self.team_index,
            "total": self.total,
            "correct": self.correct,
            "accuracy": round(self.accuracy, 4),
            "performance_trend": self.performance_trend,
        }


@dataclass
class FailurePattern:
    pattern_type: str
    description: str
    affected_questions: list[str] = field(default_factory=list)
    frequency: int = 0
    suggested_fix: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "pattern_type": self.pattern_type,
            "description": self.description,
            "affected_questions": self.affected_questions,
            "frequency": self.frequency,
            "suggested_fix": self.suggested_fix,
        }


@dataclass
class AnalysisReport:
    """Comprehensive analysis report for a test run."""
    run_id: str
    generated_at: str
    summary: ReportSummary
    domain_analysis: list[DomainAnalysis]
    team_analysis: list[TeamAnalysis]
    failure_patterns: list[FailurePattern]
    recommendations: list[str]

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "summary": self.summary.to_dict(),
            "domain_analysis": [d.to_dict() for d in self.domain_analysis],
            "team_analysis": [t.to_dict() for t in self.team_analysis],
            "failure_patterns": [f.to_dict() for f in self.failure_patterns],
            "recommendations": self.recommendations,
        }


class ReportGenerator:
    """Generates analysis reports from test results.

    Pure computation — no LLM calls. Analyzes results statistically.
    """

    def generate_report(
        self,
        run_id: str,
        results: list[QuestionResult],
        total_questions: int = 0,
    ) -> AnalysisReport:
        """Generate comprehensive analysis report."""
        metrics = compute_run_metrics(results, total_questions=total_questions)

        summary = self._generate_summary(metrics)
        domain_analysis = self._analyze_domains(results, metrics)
        team_analysis = self._analyze_teams(metrics)
        failure_patterns = self._detect_failure_patterns(results)
        recommendations = self._generate_recommendations(
            domain_analysis, team_analysis, failure_patterns, metrics,
        )

        return AnalysisReport(
            run_id=run_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            summary=summary,
            domain_analysis=domain_analysis,
            team_analysis=team_analysis,
            failure_patterns=failure_patterns,
            recommendations=recommendations,
        )

    def _generate_summary(self, metrics: RunMetrics) -> ReportSummary:
        return ReportSummary(
            accuracy=metrics.accuracy,
            total_questions=metrics.total_questions,
            correct=metrics.correct_count,
            wrong=metrics.wrong_count,
            partial=metrics.partial_count,
            error=metrics.error_count,
            total_cost=metrics.total_cost,
            total_time_seconds=metrics.total_time_ms / 1000,
            avg_time_per_question=metrics.avg_time_per_question_ms / 1000,
        )

    def _analyze_domains(
        self,
        results: list[QuestionResult],
        metrics: RunMetrics,
    ) -> list[DomainAnalysis]:
        """Analyze performance by domain, extracting common errors."""
        analyses = []

        for domain, dm in metrics.by_domain.items():
            # Extract error explanations for wrong answers in this domain
            wrong_explanations = [
                r.judgment_explanation
                for r in results
                if r.domain == domain
                and r.judgment_verdict == "wrong"
                and r.judgment_explanation
            ]
            common_errors = wrong_explanations[:5]

            analyses.append(DomainAnalysis(
                domain=domain,
                accuracy=dm.accuracy,
                total=dm.total,
                correct=dm.correct,
                wrong=dm.wrong,
                common_errors=common_errors,
            ))

        # Sort by accuracy (worst first)
        analyses.sort(key=lambda x: x.accuracy)
        return analyses

    def _analyze_teams(self, metrics: RunMetrics) -> list[TeamAnalysis]:
        """Analyze performance by team rotation with trend detection."""
        analyses = []
        accuracies = []

        for idx, tm in sorted(metrics.by_team.items()):
            analyses.append(TeamAnalysis(
                team_index=idx,
                total=tm.total,
                correct=tm.correct,
                accuracy=tm.accuracy,
                performance_trend="stable",
            ))
            accuracies.append(tm.accuracy)

        # Detect trends (need at least 3 teams)
        if len(accuracies) >= 3:
            for i in range(1, len(analyses)):
                window = min(3, i + 1)
                recent_avg = sum(accuracies[max(0, i - window + 1):i + 1]) / window
                prev_avg = sum(accuracies[:i]) / i

                if recent_avg > prev_avg + 0.1:
                    analyses[i].performance_trend = "improving"
                elif recent_avg < prev_avg - 0.1:
                    analyses[i].performance_trend = "declining"

        return analyses

    def _detect_failure_patterns(
        self,
        results: list[QuestionResult],
    ) -> list[FailurePattern]:
        """Detect common failure patterns statistically (no LLM)."""
        patterns = []

        wrong_results = [r for r in results if r.judgment_verdict == "wrong"]
        error_results = [r for r in results if r.status == "error"]

        if not wrong_results and not error_results:
            return []

        # Pattern 1: No answer produced
        no_answer = [r for r in wrong_results if not r.final_answer]
        if no_answer:
            patterns.append(FailurePattern(
                pattern_type="no_answer",
                description="Model produced no answer",
                affected_questions=[r.question_id for r in no_answer],
                frequency=len(no_answer),
                suggested_fix="Check model instructions — ensure answer extraction is explicit.",
            ))

        # Pattern 2: Execution errors
        if error_results:
            patterns.append(FailurePattern(
                pattern_type="execution_error",
                description="Question processing failed with errors",
                affected_questions=[r.question_id for r in error_results],
                frequency=len(error_results),
                suggested_fix="Review error logs. May indicate API rate limits or timeouts.",
            ))

        # Pattern 3: Domain concentration (>60% of failures in one domain)
        if wrong_results:
            domain_counts = defaultdict(int)
            for r in wrong_results:
                domain_counts[r.domain] += 1

            total_wrong = len(wrong_results)
            for domain, count in domain_counts.items():
                if count / total_wrong > 0.6 and count >= 3:
                    patterns.append(FailurePattern(
                        pattern_type="domain_concentration",
                        description=f"Failures concentrated in '{domain}' domain ({count}/{total_wrong})",
                        affected_questions=[r.question_id for r in wrong_results if r.domain == domain],
                        frequency=count,
                        suggested_fix=f"Add domain-specific instructions for '{domain}' in agent config.",
                    ))

        # Pattern 4: Late-run degradation (last team has >20% worse accuracy than first)
        if len(results) >= 6:
            first_quarter = results[:len(results) // 4]
            last_quarter = results[-(len(results) // 4):]

            first_correct = sum(1 for r in first_quarter if r.judgment_verdict == "correct")
            last_correct = sum(1 for r in last_quarter if r.judgment_verdict == "correct")

            if first_quarter and last_quarter:
                first_acc = first_correct / len(first_quarter)
                last_acc = last_correct / len(last_quarter)

                if first_acc - last_acc > 0.2:
                    patterns.append(FailurePattern(
                        pattern_type="late_degradation",
                        description=(
                            f"Performance degraded: first quarter {first_acc:.0%} "
                            f"vs last quarter {last_acc:.0%}"
                        ),
                        frequency=1,
                        suggested_fix="Reduce questions_per_team to rotate contexts more frequently.",
                    ))

        return patterns

    def _generate_recommendations(
        self,
        domain_analysis: list[DomainAnalysis],
        team_analysis: list[TeamAnalysis],
        failure_patterns: list[FailurePattern],
        metrics: RunMetrics,
    ) -> list[str]:
        """Generate actionable recommendations."""
        recs = []

        # Overall accuracy recommendation
        if metrics.accuracy < 0.5:
            recs.append(
                f"Overall accuracy is low ({metrics.accuracy:.0%}). "
                "Consider reviewing team configuration, model selection, and instructions."
            )

        # Weak domains
        weak = [d for d in domain_analysis if d.accuracy < 0.5 and d.total >= 3]
        for d in weak[:2]:
            recs.append(
                f"Domain '{d.domain}' has low accuracy ({d.accuracy:.0%}). "
                "Consider adding domain-specific instructions or using a stronger model."
            )

        # Declining teams
        declining = [t for t in team_analysis if t.performance_trend == "declining"]
        if declining:
            recs.append(
                "Performance is declining over team rotations. "
                "Reduce questions_per_team to refresh context more frequently."
            )

        # Pattern-based
        for fp in failure_patterns:
            if fp.suggested_fix and fp.suggested_fix not in recs:
                recs.append(fp.suggested_fix)

        # Cost optimization
        if metrics.avg_cost_per_question > 0.10:
            recs.append(
                f"Average cost per question is high (${metrics.avg_cost_per_question:.3f}). "
                "Consider using gpt-4o-mini for domain agents to reduce costs."
            )

        return recs[:10]  # Cap at 10
