"""
Test Runs API router.

Endpoints:
    POST   /api/lab/tests/{id}/run        -> Start a new test run
    GET    /api/lab/v2/runs               -> list[TestRunResponse]
    GET    /api/lab/v2/runs/{id}          -> TestRunResponse (with results summary)
    POST   /api/lab/v2/runs/{id}/pause    -> TestRunResponse
    POST   /api/lab/v2/runs/{id}/resume   -> TestRunResponse
    POST   /api/lab/v2/runs/{id}/stop     -> TestRunResponse
    GET    /api/lab/v2/runs/{id}/results  -> list[QuestionResultResponse]
    GET    /api/lab/v2/runs/{id}/stream   -> SSE stream of execution progress
    POST   /api/lab/v2/runs/{id}/execute  -> Start execution (returns immediately)
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from regulus.api.errors import LabErrorCode, lab_error
from regulus.api.models.lab import LabNewDB, TestRun, QuestionResult
from regulus.lab.rotation import TeamRotationManager

router = APIRouter(tags=["lab-runs"])

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


class StartRunRequest(BaseModel):
    dry_run: bool = False
    start_from: int = Field(default=0, ge=0)


class TestRunResponse(BaseModel):
    id: str
    config_id: str
    status: str
    current_question_index: int
    total_questions: int
    current_team_index: int
    current_step: int
    started_at: Optional[str]
    paused_at: Optional[str]
    completed_at: Optional[str]
    teams_used: list[dict]
    progress_percent: float


class QuestionResultResponse(BaseModel):
    id: str
    run_id: str
    question_index: int
    question_id: str
    domain: str
    input_text: str
    team_index: int
    status: str
    final_answer: Optional[str]
    judgment_verdict: Optional[str]
    judgment_confidence: Optional[float]
    judgment_explanation: Optional[str]
    total_time_ms: int
    total_tokens_in: int
    total_tokens_out: int
    estimated_cost: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_to_response(run: TestRun) -> TestRunResponse:
    progress = 0.0
    if run.total_questions > 0:
        progress = round(run.current_question_index / run.total_questions * 100, 1)
    return TestRunResponse(
        id=run.id,
        config_id=run.config_id,
        status=run.status,
        current_question_index=run.current_question_index,
        total_questions=run.total_questions,
        current_team_index=run.current_team_index,
        current_step=run.current_step,
        started_at=run.started_at,
        paused_at=run.paused_at,
        completed_at=run.completed_at,
        teams_used=run.teams_used,
        progress_percent=progress,
    )


def _result_to_response(r: QuestionResult) -> QuestionResultResponse:
    return QuestionResultResponse(
        id=r.id,
        run_id=r.run_id,
        question_index=r.question_index,
        question_id=r.question_id,
        domain=r.domain,
        input_text=r.input_text[:500],
        team_index=r.team_index,
        status=r.status,
        final_answer=r.final_answer,
        judgment_verdict=r.judgment_verdict,
        judgment_confidence=r.judgment_confidence,
        judgment_explanation=r.judgment_explanation,
        total_time_ms=r.total_time_ms,
        total_tokens_in=r.total_tokens_in,
        total_tokens_out=r.total_tokens_out,
        estimated_cost=r.estimated_cost,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/api/lab/tests/{config_id}/run", response_model=TestRunResponse, status_code=201)
async def start_test_run(config_id: str, body: StartRunRequest = StartRunRequest()):
    """Create and start a new test run from a test configuration."""
    db = get_db()

    # Validate config
    cfg = db.get_test_config(config_id)
    if not cfg:
        raise lab_error(LabErrorCode.CONFIG_NOT_FOUND, id=config_id)

    # Validate team exists
    if cfg.team_id:
        team = db.get_team(cfg.team_id)
        if not team:
            raise lab_error(LabErrorCode.TEAM_NOT_FOUND, id=cfg.team_id)

    # Determine total questions
    from regulus.data.bbeh import get_loader
    try:
        loader = get_loader(cfg.benchmark)
    except ValueError:
        raise lab_error(LabErrorCode.BENCHMARK_LOAD_FAILED, detail=cfg.benchmark)

    if cfg.question_ids:
        total_questions = len(cfg.question_ids)
    elif cfg.question_count:
        total_questions = cfg.question_count
    else:
        info = loader.info()
        total_questions = info.total_examples

    # Set up rotation
    rotation = TeamRotationManager(
        base_team_id=cfg.team_id,
        questions_per_team=cfg.questions_per_team,
        total_questions=total_questions,
    )

    if body.dry_run:
        # Return preview without creating the run
        preview_run = TestRun(
            config_id=config_id,
            status="dry_run",
            total_questions=total_questions,
        )
        resp = _run_to_response(preview_run)
        resp.teams_used = [
            {"index": i, "question_range": [
                i * cfg.questions_per_team,
                min((i + 1) * cfg.questions_per_team, total_questions),
            ]}
            for i in range(rotation.total_teams_needed)
        ]
        return resp

    # Create the run
    now = datetime.now(timezone.utc).isoformat()
    run = TestRun(
        config_id=config_id,
        status="pending",
        total_questions=total_questions,
        current_question_index=body.start_from,
        current_team_index=rotation.get_team_index_for_question(body.start_from),
        current_step=0,
        started_at=now,
        teams_used=[],
    )
    run = db.create_test_run(run)

    return _run_to_response(run)


@router.get("/api/lab/v2/runs", response_model=list[TestRunResponse])
async def list_test_runs(
    config_id: str | None = Query(default=None),
):
    """List all test runs, optionally filtered by config."""
    db = get_db()
    runs = db.list_test_runs(config_id=config_id)
    return [_run_to_response(r) for r in runs]


@router.get("/api/lab/v2/runs/{run_id}", response_model=TestRunResponse)
async def get_test_run(run_id: str):
    """Get test run status."""
    db = get_db()
    run = db.get_test_run(run_id)
    if not run:
        raise lab_error(LabErrorCode.RUN_NOT_FOUND, id=run_id)
    return _run_to_response(run)


@router.post("/api/lab/v2/runs/{run_id}/pause", response_model=TestRunResponse)
async def pause_test_run(run_id: str):
    """Pause a running test."""
    db = get_db()
    run = db.get_test_run(run_id)
    if not run:
        raise lab_error(LabErrorCode.RUN_NOT_FOUND, id=run_id)

    if run.status != "running":
        raise lab_error(LabErrorCode.INVALID_RUN_STATUS, expected="running", actual=run.status)

    now = datetime.now(timezone.utc).isoformat()
    run = db.update_test_run_status(run_id, "paused", paused_at=now)
    return _run_to_response(run)


@router.post("/api/lab/v2/runs/{run_id}/resume", response_model=TestRunResponse)
async def resume_test_run(run_id: str):
    """Resume a paused test."""
    db = get_db()
    run = db.get_test_run(run_id)
    if not run:
        raise lab_error(LabErrorCode.RUN_NOT_FOUND, id=run_id)

    if run.status != "paused":
        raise lab_error(LabErrorCode.INVALID_RUN_STATUS, expected="paused", actual=run.status)

    run = db.update_test_run_status(run_id, "running", paused_at=None)
    return _run_to_response(run)


@router.post("/api/lab/v2/runs/{run_id}/stop", response_model=TestRunResponse)
async def stop_test_run(run_id: str):
    """Stop (cancel) a running or paused test."""
    db = get_db()
    run = db.get_test_run(run_id)
    if not run:
        raise lab_error(LabErrorCode.RUN_NOT_FOUND, id=run_id)

    if run.status not in ("running", "paused", "pending"):
        raise lab_error(LabErrorCode.INVALID_RUN_STATUS, expected="running/paused/pending", actual=run.status)

    # Signal executor to stop if active
    executor = _executors.get(run_id)
    if executor:
        executor.request_stop()

    now = datetime.now(timezone.utc).isoformat()
    run = db.update_test_run_status(run_id, "cancelled", completed_at=now)
    return _run_to_response(run)


@router.get("/api/lab/v2/runs/{run_id}/results", response_model=list[QuestionResultResponse])
async def get_run_results(
    run_id: str,
    status: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    team_index: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """Get question results for a test run with optional filters."""
    db = get_db()
    run = db.get_test_run(run_id)
    if not run:
        raise lab_error(LabErrorCode.RUN_NOT_FOUND, id=run_id)

    results = db.list_question_results(
        run_id, status=status, domain=domain,
        team_index=team_index, limit=limit, offset=offset,
    )
    return [_result_to_response(r) for r in results]


# ---------------------------------------------------------------------------
# Execution + SSE Streaming
# ---------------------------------------------------------------------------

# Track active executors for stop requests
_executors: dict[str, "TestExecutor"] = {}


@router.post("/api/lab/v2/runs/{run_id}/execute", status_code=202)
async def execute_test_run(run_id: str):
    """Start asynchronous execution of a test run.

    Use GET /api/lab/v2/runs/{run_id}/stream to monitor progress via SSE.
    """
    db = get_db()
    run = db.get_test_run(run_id)
    if not run:
        raise lab_error(LabErrorCode.RUN_NOT_FOUND, id=run_id)

    if run.status not in ("pending",):
        raise lab_error(LabErrorCode.INVALID_RUN_STATUS, expected="pending", actual=run.status)

    from regulus.lab.executor import TestExecutor

    executor = TestExecutor(db)
    _executors[run_id] = executor

    async def _run_in_background():
        try:
            async for _event in executor.execute(run_id):
                pass  # events consumed by SSE stream if connected
        finally:
            _executors.pop(run_id, None)

    asyncio.create_task(_run_in_background())

    return {"status": "started", "run_id": run_id}


@router.get("/api/lab/v2/runs/{run_id}/stream")
async def stream_test_run(run_id: str):
    """Stream test execution progress via Server-Sent Events.

    Can be connected during or after execution start.
    Emits events: run_start, question_start, question_complete,
    team_rotation, judgment, run_complete, error.
    """
    db = get_db()
    run = db.get_test_run(run_id)
    if not run:
        raise lab_error(LabErrorCode.RUN_NOT_FOUND, id=run_id)

    from regulus.lab.executor import TestExecutor

    async def generate():
        executor = TestExecutor(db)
        _executors[run_id] = executor

        try:
            async for event in executor.execute(run_id):
                event_data = {
                    "type": event.type,
                    "run_id": event.run_id,
                    "question_index": event.question_index,
                    "total_questions": event.total_questions,
                    "team_index": event.team_index,
                    **event.data,
                    "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                }
                yield f"event: {event.type}\ndata: {json.dumps(event_data)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            _executors.pop(run_id, None)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
