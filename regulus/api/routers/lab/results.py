"""
Results & Analytics API router.

Endpoints:
    GET    /api/lab/v2/runs/{id}/stats           -> RunMetrics summary
    GET    /api/lab/v2/runs/{id}/stats/domains    -> list[DomainMetrics]
    GET    /api/lab/v2/runs/{id}/stats/teams      -> list[TeamMetrics]
    GET    /api/lab/v2/runs/{id}/question/{idx}   -> single QuestionResult detail
    GET    /api/lab/v2/runs/{id}/export           -> CSV or JSON export
    GET    /api/lab/v2/runs/{id}/report           -> AnalysisReport
    GET    /api/lab/v2/dashboard                  -> Dashboard aggregate stats
    GET    /api/lab/v2/results                    -> Paginated results across all runs
    GET    /api/lab/v2/results/stats              -> Aggregated result stats
    POST   /api/lab/v2/results/{id}/analyze       -> Trigger AI analysis
    GET    /api/lab/v2/results/{id}/analysis      -> Get analysis for result
    GET    /api/lab/v2/results/analysis-stats     -> Analysis statistics
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from regulus.api.errors import LabErrorCode, lab_error
from regulus.api.models.lab import LabNewDB
from regulus.lab.analytics import ReportGenerator
from regulus.lab.metrics import compute_run_metrics

router = APIRouter(tags=["lab-results"])

# ---------------------------------------------------------------------------
# Singleton DB instance
# ---------------------------------------------------------------------------

_db: LabNewDB | None = None


def get_db() -> LabNewDB:
    global _db
    if _db is None:
        _db = LabNewDB()
    return _db


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class DomainMetricsResponse(BaseModel):
    domain: str
    total: int
    correct: int
    wrong: int
    partial: int
    error: int
    accuracy: float
    avg_time_ms: float
    total_tokens_in: int
    total_tokens_out: int
    total_cost: float


class TeamMetricsResponse(BaseModel):
    team_index: int
    total: int
    correct: int
    wrong: int
    accuracy: float
    avg_time_ms: float


class RunStatsResponse(BaseModel):
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
    accuracy: float
    by_domain: dict
    by_team: dict


class QuestionDetailResponse(BaseModel):
    id: str
    run_id: str
    question_index: int
    question_id: str
    domain: str
    input_text: str
    team_index: int
    status: str
    agent_outputs: dict
    final_answer: Optional[str]
    judgment_verdict: Optional[str]
    judgment_confidence: Optional[float]
    judgment_explanation: Optional[str]
    judged_at: Optional[str]
    total_time_ms: int
    total_tokens_in: int
    total_tokens_out: int
    estimated_cost: float


class AnalysisResponse(BaseModel):
    id: str
    question_result_id: str
    status: str
    failure_category: Optional[str] = None
    root_cause: Optional[str] = None
    summary: Optional[str] = None
    recommendations: list[str] = []
    model_used: str = ""
    cost: float = 0.0
    created_at: str = ""
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


class ResultsStatsResponse(BaseModel):
    total: int
    correct: int
    wrong: int
    partial: int
    error: int
    pending: int
    domains: list[str]
    run_ids: list[str]


class AnalysisStatsResponse(BaseModel):
    total: int
    completed: int
    by_category: dict[str, int]


class DomainNode(BaseModel):
    domain: str
    total: int
    correct: int
    wrong: int
    accuracy: float


class ParticipantNode(BaseModel):
    participant: str
    name: str
    run_ids: list[str]
    total: int
    correct: int
    wrong: int
    accuracy: float
    domains: list[DomainNode]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/api/lab/v2/runs/{run_id}/stats", response_model=RunStatsResponse)
async def get_run_stats(run_id: str):
    """Get aggregated metrics for a test run."""
    db = get_db()
    run = db.get_test_run(run_id)
    if not run:
        raise lab_error(LabErrorCode.RUN_NOT_FOUND, id=run_id)

    results = db.list_question_results(run_id, limit=10000)
    metrics = compute_run_metrics(results, total_questions=run.total_questions)
    return RunStatsResponse(**metrics.to_dict())


@router.get(
    "/api/lab/v2/runs/{run_id}/stats/domains",
    response_model=list[DomainMetricsResponse],
)
async def get_domain_stats(run_id: str):
    """Get per-domain metrics breakdown."""
    db = get_db()
    run = db.get_test_run(run_id)
    if not run:
        raise lab_error(LabErrorCode.RUN_NOT_FOUND, id=run_id)

    results = db.list_question_results(run_id, limit=10000)
    metrics = compute_run_metrics(results, total_questions=run.total_questions)

    return [
        DomainMetricsResponse(**dm.to_dict())
        for dm in sorted(metrics.by_domain.values(), key=lambda d: d.accuracy)
    ]


@router.get(
    "/api/lab/v2/runs/{run_id}/stats/teams",
    response_model=list[TeamMetricsResponse],
)
async def get_team_stats(run_id: str):
    """Get per-team metrics breakdown."""
    db = get_db()
    run = db.get_test_run(run_id)
    if not run:
        raise lab_error(LabErrorCode.RUN_NOT_FOUND, id=run_id)

    results = db.list_question_results(run_id, limit=10000)
    metrics = compute_run_metrics(results, total_questions=run.total_questions)

    return [
        TeamMetricsResponse(**tm.to_dict())
        for tm in sorted(metrics.by_team.values(), key=lambda t: t.team_index)
    ]


@router.get(
    "/api/lab/v2/runs/{run_id}/question/{question_index}",
    response_model=QuestionDetailResponse,
)
async def get_question_detail(run_id: str, question_index: int):
    """Get detailed result for a single question."""
    db = get_db()
    run = db.get_test_run(run_id)
    if not run:
        raise lab_error(LabErrorCode.RUN_NOT_FOUND, id=run_id)

    # Find result by question_index
    results = db.list_question_results(run_id, limit=10000)
    result = next((r for r in results if r.question_index == question_index), None)
    if not result:
        raise lab_error(
            LabErrorCode.INVALID_QUESTION_RANGE,
            status_code=404,
            detail=f"No result for question index {question_index}",
        )

    return QuestionDetailResponse(
        id=result.id,
        run_id=result.run_id,
        question_index=result.question_index,
        question_id=result.question_id,
        domain=result.domain,
        input_text=result.input_text,
        team_index=result.team_index,
        status=result.status,
        agent_outputs=result.agent_outputs,
        final_answer=result.final_answer,
        judgment_verdict=result.judgment_verdict,
        judgment_confidence=result.judgment_confidence,
        judgment_explanation=result.judgment_explanation,
        judged_at=result.judged_at,
        total_time_ms=result.total_time_ms,
        total_tokens_in=result.total_tokens_in,
        total_tokens_out=result.total_tokens_out,
        estimated_cost=result.estimated_cost,
    )


@router.get("/api/lab/v2/runs/{run_id}/export")
async def export_run_results(
    run_id: str,
    format: str = Query(default="json", pattern="^(json|csv)$"),
):
    """Export run results as JSON or CSV.

    Query params:
        format: "json" (default) or "csv"
    """
    db = get_db()
    run = db.get_test_run(run_id)
    if not run:
        raise lab_error(LabErrorCode.RUN_NOT_FOUND, id=run_id)

    results = db.list_question_results(run_id, limit=10000)
    metrics = compute_run_metrics(results, total_questions=run.total_questions)

    if format == "csv":
        return _export_csv(run_id, results, metrics)
    else:
        return _export_json(run_id, results, metrics)


@router.get("/api/lab/v2/runs/{run_id}/report")
async def get_analysis_report(run_id: str):
    """Generate analysis report with failure patterns and recommendations."""
    db = get_db()
    run = db.get_test_run(run_id)
    if not run:
        raise lab_error(LabErrorCode.RUN_NOT_FOUND, id=run_id)

    results = db.list_question_results(run_id, limit=10000)
    generator = ReportGenerator()
    report = generator.generate_report(
        run_id=run_id,
        results=results,
        total_questions=run.total_questions,
    )
    return report.to_dict()


@router.get("/api/lab/v2/dashboard")
async def get_dashboard():
    """Aggregate dashboard stats across all runs."""
    db = get_db()
    runs = db.list_test_runs()

    total_runs = len(runs)
    completed_runs = sum(1 for r in runs if r.status == "completed")
    running_runs = sum(1 for r in runs if r.status == "running")

    total_questions = 0
    total_correct = 0
    total_wrong = 0
    total_cost = 0.0
    total_time_ms = 0

    for run in runs:
        results = db.list_question_results(run.id, limit=10000)
        if not results:
            continue
        metrics = compute_run_metrics(results, total_questions=run.total_questions)
        total_questions += metrics.completed_questions
        total_correct += metrics.correct_count
        total_wrong += metrics.wrong_count
        total_cost += metrics.total_cost
        total_time_ms += metrics.total_time_ms

    accuracy = total_correct / total_questions if total_questions > 0 else 0.0

    return {
        "total_runs": total_runs,
        "completed_runs": completed_runs,
        "running_runs": running_runs,
        "total_questions_answered": total_questions,
        "overall_accuracy": round(accuracy, 4),
        "total_correct": total_correct,
        "total_wrong": total_wrong,
        "total_cost": round(total_cost, 6),
        "total_time_seconds": round(total_time_ms / 1000, 2),
    }


@router.get("/api/lab/v2/results/tree", response_model=list[ParticipantNode])
async def get_results_tree():
    """Hierarchical view: participant -> domain -> counts."""
    db = get_db()
    return db.get_results_tree()


@router.get("/api/lab/v2/results/stats", response_model=ResultsStatsResponse)
async def get_results_stats(
    verdict: Optional[str] = Query(default=None),
    domain: Optional[str] = Query(default=None),
    run_id: Optional[str] = Query(default=None),
):
    """Aggregated stats across all results."""
    db = get_db()
    stats = db.get_results_stats(verdict=verdict, domain=domain, run_id=run_id)
    return ResultsStatsResponse(**stats)


@router.get("/api/lab/v2/results/analysis-stats", response_model=AnalysisStatsResponse)
async def get_all_analysis_stats():
    """Get analysis statistics across all results."""
    db = get_db()
    stats = db.get_analysis_stats()
    return AnalysisStatsResponse(**stats)


@router.get("/api/lab/v2/results")
async def list_all_results(
    verdict: Optional[str] = Query(default=None),
    domain: Optional[str] = Query(default=None),
    run_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Paginated list of results across all runs."""
    db = get_db()
    results = db.list_all_results(
        verdict=verdict, domain=domain, run_id=run_id,
        limit=limit, offset=offset,
    )
    total = db.count_all_results(verdict=verdict, domain=domain, run_id=run_id)

    items = []
    for r in results:
        analysis = db.get_analysis_for_result(r.id)
        items.append({
            "id": r.id,
            "run_id": r.run_id,
            "question_index": r.question_index,
            "question_id": r.question_id,
            "domain": r.domain,
            "input_text": r.input_text[:200],
            "team_index": r.team_index,
            "status": r.status,
            "final_answer": r.final_answer,
            "judgment_verdict": r.judgment_verdict,
            "judgment_confidence": r.judgment_confidence,
            "judgment_explanation": r.judgment_explanation,
            "total_time_ms": r.total_time_ms,
            "total_tokens_in": r.total_tokens_in,
            "total_tokens_out": r.total_tokens_out,
            "estimated_cost": r.estimated_cost,
            "has_analysis": analysis is not None,
            "agent_outputs": r.agent_outputs,
        })

    return {
        "results": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/api/lab/v2/results/{result_id}/analyze", response_model=AnalysisResponse)
async def analyze_result(result_id: str):
    """Trigger AI analysis for a question result."""
    db = get_db()
    qr = db.get_question_result(result_id)
    if not qr:
        raise lab_error(LabErrorCode.RUN_NOT_FOUND, id=result_id)

    # Check for existing analysis
    existing = db.get_analysis_for_result(result_id)
    if existing and existing.status in ("running", "completed"):
        return AnalysisResponse(
            id=existing.id,
            question_result_id=existing.question_result_id,
            status=existing.status,
            failure_category=existing.failure_category,
            root_cause=existing.root_cause,
            summary=existing.summary,
            recommendations=existing.recommendations,
            model_used=existing.model_used,
            cost=existing.cost,
            created_at=existing.created_at,
            completed_at=existing.completed_at,
            error_message=existing.error_message,
        )

    # Create pending record and run in background
    from regulus.api.models.lab import Analysis
    from regulus.lab.analyst import LabAnalyst

    analyst = LabAnalyst(db=db)
    analysis = Analysis(
        question_result_id=result_id,
        status="pending",
        model_used=analyst.model,
    )
    analysis = db.create_analysis(analysis)

    async def _run_analysis():
        try:
            await analyst.analyze_result(result_id)
        except Exception:
            pass  # errors captured in the analysis record

    loop = asyncio.get_event_loop()
    loop.create_task(_run_analysis())

    return AnalysisResponse(
        id=analysis.id,
        question_result_id=analysis.question_result_id,
        status=analysis.status,
        model_used=analysis.model_used,
        created_at=analysis.created_at,
    )


@router.get("/api/lab/v2/results/{result_id}/analysis", response_model=AnalysisResponse)
async def get_result_analysis(result_id: str):
    """Get the most recent analysis for a question result."""
    db = get_db()
    analysis = db.get_analysis_for_result(result_id)
    if not analysis:
        raise lab_error(LabErrorCode.ANALYSIS_NOT_FOUND, id=result_id)
    return AnalysisResponse(
        id=analysis.id,
        question_result_id=analysis.question_result_id,
        status=analysis.status,
        failure_category=analysis.failure_category,
        root_cause=analysis.root_cause,
        summary=analysis.summary,
        recommendations=analysis.recommendations,
        model_used=analysis.model_used,
        cost=analysis.cost,
        created_at=analysis.created_at,
        completed_at=analysis.completed_at,
        error_message=analysis.error_message,
    )


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


def _export_json(run_id: str, results, metrics):
    """Generate JSON export."""
    data = {
        "run_id": run_id,
        "metrics": metrics.to_dict(),
        "results": [
            {
                "question_index": r.question_index,
                "question_id": r.question_id,
                "domain": r.domain,
                "input_text": r.input_text,
                "team_index": r.team_index,
                "status": r.status,
                "final_answer": r.final_answer,
                "judgment_verdict": r.judgment_verdict,
                "judgment_confidence": r.judgment_confidence,
                "judgment_explanation": r.judgment_explanation,
                "total_time_ms": r.total_time_ms,
                "total_tokens_in": r.total_tokens_in,
                "total_tokens_out": r.total_tokens_out,
                "estimated_cost": r.estimated_cost,
            }
            for r in results
        ],
    }

    content = json.dumps(data, indent=2, ensure_ascii=False)

    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="run_{run_id}.json"',
        },
    )


def _export_csv(run_id: str, results, metrics):
    """Generate CSV export."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "question_index", "question_id", "domain", "team_index",
        "status", "final_answer", "judgment_verdict", "judgment_confidence",
        "judgment_explanation", "total_time_ms",
        "total_tokens_in", "total_tokens_out", "estimated_cost",
    ])

    for r in results:
        writer.writerow([
            r.question_index,
            r.question_id,
            r.domain,
            r.team_index,
            r.status,
            r.final_answer or "",
            r.judgment_verdict or "",
            r.judgment_confidence or "",
            r.judgment_explanation or "",
            r.total_time_ms,
            r.total_tokens_in,
            r.total_tokens_out,
            r.estimated_cost,
        ])

    content = output.getvalue()
    output.close()

    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="run_{run_id}.csv"',
        },
    )
