"""
Benchmarks API router — list/browse available benchmarks via the new loader infra.

Endpoints:
    GET  /api/lab/benchmarks                  -> list of available benchmarks
    GET  /api/lab/benchmarks/{id}             -> benchmark info + domains
    GET  /api/lab/benchmarks/{id}/domains     -> list of domains with stats
    GET  /api/lab/benchmarks/{id}/sample      -> sample questions for preview
    POST /api/lab/benchmarks/{id}/index       -> trigger benchmark indexing
    GET  /api/lab/benchmarks/{id}/index       -> check index status
    GET  /api/lab/benchmarks/{id}/questions   -> browse indexed questions
    GET  /api/lab/benchmarks/{id}/questions/{qid} -> single question + history
    POST /api/lab/benchmarks/{id}/load        -> load/cache benchmark data
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from regulus.api.errors import LabErrorCode, lab_error
from regulus.api.models.lab import LabNewDB
from regulus.data.bbeh import BENCHMARK_REGISTRY, get_loader, _ensure_registry
from regulus.lab.indexer import BenchmarkIndexer

router = APIRouter(prefix="/api/lab/benchmarks", tags=["lab-benchmarks"])

# ---------------------------------------------------------------------------
# DB singleton
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


class BenchmarkSummary(BaseModel):
    id: str
    name: str
    description: str
    source: str
    total_examples: int
    domains_count: int
    version: str


class BenchmarkDetail(BenchmarkSummary):
    domains: list[str]


class DomainInfo(BaseModel):
    name: str
    example_count: int


class DomainStatsResponse(BaseModel):
    domain: str
    total: int
    attempted: int
    correct: int
    wrong: int
    accuracy: float
    new_count: int
    failed_count: int


class SampleQuestion(BaseModel):
    id: str
    domain: str
    input: str
    target: str


class IndexStatusResponse(BaseModel):
    benchmark_id: str
    status: str  # not_indexed, pending, indexing, ready, error
    total_questions: int
    domains: list[str]
    indexed_at: str | None
    error_message: str | None
    questions_attempted: int = 0
    overall_accuracy: float = 0.0


class IndexedQuestionResponse(BaseModel):
    question_id: str
    domain: str
    input_preview: str
    target_short: str
    status: str  # new, passed, failed
    total_attempts: int
    correct_count: int
    wrong_count: int
    accuracy: float
    last_result: str | None


class QuestionDetailResponse(BaseModel):
    id: str
    question_id: str
    domain: str
    input: str
    target: str
    target_hash: str
    difficulty: str | None
    tags: list[str]
    status: str
    total_attempts: int
    correct_count: int
    wrong_count: int
    accuracy: float
    last_attempt_at: str | None
    last_result: str | None
    attempts: list[AttemptResponse] = []


class AttemptResponse(BaseModel):
    id: str
    run_id: str
    team_id: str
    model_answer: str
    judgment: str
    confidence: float
    paradigm_used: str | None
    time_ms: int
    tokens_in: int
    tokens_out: int
    cost: float
    attempted_at: str
    analysis: str | None
    failure_category: str | None


# Fix forward reference
QuestionDetailResponse.model_rebuild()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[BenchmarkSummary])
async def list_benchmarks():
    """List all available benchmarks."""
    _ensure_registry()
    results = []
    for benchmark_id, loader_cls in BENCHMARK_REGISTRY.items():
        if loader_cls is None:
            continue
        loader = loader_cls()
        info = loader.info()
        results.append(
            BenchmarkSummary(
                id=info.id,
                name=info.name,
                description=info.description,
                source=info.source,
                total_examples=info.total_examples,
                domains_count=len(info.domains),
                version=info.version,
            )
        )
    return results


@router.get("/{benchmark_id}", response_model=BenchmarkDetail)
async def get_benchmark(benchmark_id: str):
    """Get benchmark info with full domain list."""
    try:
        loader = get_loader(benchmark_id)
    except ValueError:
        raise lab_error(LabErrorCode.BENCHMARK_LOAD_FAILED, status_code=404, detail=f"'{benchmark_id}' not found")

    info = loader.info()
    return BenchmarkDetail(
        id=info.id,
        name=info.name,
        description=info.description,
        source=info.source,
        total_examples=info.total_examples,
        domains_count=len(info.domains),
        version=info.version,
        domains=info.domains,
    )


@router.get("/{benchmark_id}/domains", response_model=list[DomainInfo])
async def get_benchmark_domains(benchmark_id: str):
    """Get domains with example counts. Uses index if available, falls back to loader."""
    db = get_db()

    # Try index first
    idx = db.get_benchmark_index(benchmark_id)
    if idx and idx.status == "ready":
        domain_counts = db.get_benchmark_domain_counts(benchmark_id)
        return [DomainInfo(name=d, example_count=c) for d, c in domain_counts]

    # Fallback: loader-based (existing code)
    try:
        loader = get_loader(benchmark_id)
    except ValueError:
        raise lab_error(LabErrorCode.BENCHMARK_LOAD_FAILED, status_code=404, detail=f"'{benchmark_id}' not found")

    info = loader.info()
    results = []
    fallback_per_domain = max(1, info.total_examples // max(1, len(info.domains)))
    for domain in info.domains:
        try:
            examples = loader.load_domain(domain)
            count = len(examples)
        except Exception:
            count = 0
        results.append(DomainInfo(name=domain, example_count=count or fallback_per_domain))
    return results


@router.get("/{benchmark_id}/domains/stats", response_model=list[DomainStatsResponse])
async def get_benchmark_domain_stats(benchmark_id: str):
    """Get enriched domain stats with attempted/correct/accuracy info."""
    db = get_db()

    idx = db.get_benchmark_index(benchmark_id)
    if not idx or idx.status != "ready":
        raise lab_error(LabErrorCode.BENCHMARK_NOT_INDEXED, id=benchmark_id)

    stats = db.get_benchmark_domain_stats(benchmark_id)
    return [DomainStatsResponse(**s) for s in stats]


@router.get("/{benchmark_id}/sample", response_model=list[SampleQuestion])
async def get_benchmark_sample(
    benchmark_id: str,
    n: int = Query(default=5, ge=1, le=50),
    domain: str | None = Query(default=None),
):
    """Get sample questions for preview."""
    try:
        loader = get_loader(benchmark_id)
    except ValueError:
        raise lab_error(LabErrorCode.BENCHMARK_LOAD_FAILED, status_code=404, detail=f"'{benchmark_id}' not found")

    domains = [domain] if domain else None
    examples = loader.load_sample(n=n, domains=domains)

    return [
        SampleQuestion(
            id=ex.id,
            domain=ex.domain,
            input=ex.input[:500],
            target=ex.target,
        )
        for ex in examples
    ]


@router.post("/{benchmark_id}/index", response_model=IndexStatusResponse)
async def index_benchmark(
    benchmark_id: str,
    force: bool = Query(default=False),
):
    """Trigger benchmark indexing. Downloads & indexes all questions into DB."""
    try:
        get_loader(benchmark_id)
    except ValueError:
        raise lab_error(LabErrorCode.BENCHMARK_LOAD_FAILED, status_code=404, detail=f"'{benchmark_id}' not found")

    db = get_db()
    indexer = BenchmarkIndexer(db)
    idx = indexer.index_benchmark(benchmark_id, force=force)

    # Compute aggregate stats
    questions_attempted = 0
    overall_accuracy = 0.0
    if idx.status == "ready":
        domain_stats = db.get_benchmark_domain_stats(benchmark_id)
        questions_attempted = sum(s["attempted"] for s in domain_stats)
        total_correct = sum(s["correct"] for s in domain_stats)
        overall_accuracy = (total_correct / questions_attempted) if questions_attempted > 0 else 0.0

    return IndexStatusResponse(
        benchmark_id=idx.benchmark_id,
        status=idx.status,
        total_questions=idx.total_questions,
        domains=idx.domains,
        indexed_at=idx.indexed_at,
        error_message=idx.error_message,
        questions_attempted=questions_attempted,
        overall_accuracy=round(overall_accuracy, 4),
    )


@router.get("/{benchmark_id}/index", response_model=IndexStatusResponse)
async def get_index_status(benchmark_id: str):
    """Check benchmark index status with aggregate stats."""
    db = get_db()
    idx = db.get_benchmark_index(benchmark_id)
    if not idx:
        return IndexStatusResponse(
            benchmark_id=benchmark_id,
            status="not_indexed",
            total_questions=0,
            domains=[],
            indexed_at=None,
            error_message=None,
        )

    questions_attempted = 0
    overall_accuracy = 0.0
    if idx.status == "ready":
        domain_stats = db.get_benchmark_domain_stats(benchmark_id)
        questions_attempted = sum(s["attempted"] for s in domain_stats)
        total_correct = sum(s["correct"] for s in domain_stats)
        overall_accuracy = (total_correct / questions_attempted) if questions_attempted > 0 else 0.0

    return IndexStatusResponse(
        benchmark_id=idx.benchmark_id,
        status=idx.status,
        total_questions=idx.total_questions,
        domains=idx.domains,
        indexed_at=idx.indexed_at,
        error_message=idx.error_message,
        questions_attempted=questions_attempted,
        overall_accuracy=round(overall_accuracy, 4),
    )


@router.get("/{benchmark_id}/questions", response_model=list[IndexedQuestionResponse])
async def list_indexed_questions(
    benchmark_id: str,
    domain: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None, pattern="^(new|passed|failed|all)$"),
    min_attempts: Optional[int] = Query(default=None, ge=0),
    max_accuracy: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Browse indexed questions with filters (new/passed/failed, min_attempts, max_accuracy)."""
    db = get_db()

    idx = db.get_benchmark_index(benchmark_id)
    if not idx or idx.status != "ready":
        raise lab_error(LabErrorCode.BENCHMARK_NOT_INDEXED, id=benchmark_id)

    effective_status = status if status and status != "all" else None

    questions = db.list_benchmark_questions(
        benchmark_id=benchmark_id,
        domain=domain,
        status=effective_status,
        min_attempts=min_attempts,
        max_accuracy=max_accuracy,
        limit=limit,
        offset=offset,
    )

    return [
        IndexedQuestionResponse(
            question_id=q.question_id,
            domain=q.domain,
            input_preview=q.input_preview,
            target_short=q.target_short,
            status=q.status,
            total_attempts=q.total_attempts,
            correct_count=q.correct_count,
            wrong_count=q.wrong_count,
            accuracy=round(q.accuracy, 4),
            last_result=q.last_result,
        )
        for q in questions
    ]


@router.get("/{benchmark_id}/questions/{question_id}", response_model=QuestionDetailResponse)
async def get_question_detail(benchmark_id: str, question_id: str):
    """Get single question with full text and attempt history."""
    db = get_db()

    composite_id = f"{benchmark_id}:{question_id}"
    q = db.get_benchmark_question(composite_id)
    if not q:
        raise lab_error(LabErrorCode.BENCHMARK_LOAD_FAILED, status_code=404, detail=f"Question '{question_id}' not found")

    attempts = db.get_question_attempts(composite_id, limit=50)

    return QuestionDetailResponse(
        id=q.id,
        question_id=q.question_id,
        domain=q.domain,
        input=q.input,
        target=q.target,
        target_hash=q.target_hash,
        difficulty=q.difficulty,
        tags=q.tags,
        status=q.status,
        total_attempts=q.total_attempts,
        correct_count=q.correct_count,
        wrong_count=q.wrong_count,
        accuracy=round(q.accuracy, 4),
        last_attempt_at=q.last_attempt_at,
        last_result=q.last_result,
        attempts=[
            AttemptResponse(
                id=a.id,
                run_id=a.run_id,
                team_id=a.team_id,
                model_answer=a.model_answer,
                judgment=a.judgment,
                confidence=a.confidence,
                paradigm_used=a.paradigm_used,
                time_ms=a.time_ms,
                tokens_in=a.tokens_in,
                tokens_out=a.tokens_out,
                cost=a.cost,
                attempted_at=a.attempted_at,
                analysis=a.analysis,
                failure_category=a.failure_category,
            )
            for a in attempts
        ],
    )


@router.post("/{benchmark_id}/load")
async def load_benchmark(benchmark_id: str):
    """Load/refresh benchmark data into cache.

    Downloads data if not cached, otherwise returns cached info.
    """
    try:
        loader = get_loader(benchmark_id)
    except ValueError:
        raise lab_error(LabErrorCode.BENCHMARK_LOAD_FAILED, status_code=404, detail=f"'{benchmark_id}' not found")

    info = loader.info()
    try:
        examples = loader.load_all()
        loaded_count = len(examples)
    except Exception as e:
        raise lab_error(LabErrorCode.BENCHMARK_LOAD_FAILED, status_code=502, detail=str(e))

    return {
        "benchmark_id": info.id,
        "name": info.name,
        "loaded_examples": loaded_count,
        "domains": info.domains,
        "status": "ok",
    }
