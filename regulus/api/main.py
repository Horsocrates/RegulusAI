"""
Regulus AI API — FastAPI backend for LLM reasoning verification.

Endpoints:
    GET  /api/health            — Health check
    POST /api/verify            — Run verification on a query
    POST /api/battle            — Compare raw LLM vs Regulus-guarded
    POST /api/dual              — Run on both Claude and OpenAI
    POST /api/benchmark         — Run SimpleQA benchmark (batch)
    GET  /api/benchmark/stream  — Stream benchmark results (SSE + parallel)
    GET  /api/simpleqa/topics   — Get SimpleQA topic distribution
"""

import os
import time
import json
import asyncio
import logging
import traceback
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("regulus.api")

from regulus.orchestrator import SocraticOrchestrator
from regulus.llm.claude import ClaudeClient
from regulus.llm.openai import OpenAIClient
from regulus.llm.hybrid import HybridClient
from regulus.data.simpleqa import load_dataset as load_simpleqa, get_topics
from regulus.lab import LabDB, LabRunner, ReportGenerator, RunStatus, StepStatus
from regulus.lab.costs import estimate_run_cost, calculate_cost, estimate_remaining_cost

# ============================================================================
# Pydantic Models
# ============================================================================

class VerifyRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    provider: str = Field(default="openai", pattern="^(claude|openai)$")

class StepModel(BaseModel):
    domain: str
    content: str
    passed: bool
    weight: float
    probes_used: int

class VerifyResponse(BaseModel):
    query: str
    valid: bool
    answer: str | None           # final_answer
    primary_answer: str | None   # PrimaryMax raw content (d5_content)
    corrections: int
    violations: list[str]
    steps: list[StepModel]
    branches_explored: int = 1
    confidence_level: str = ""
    time_seconds: float
    version: str = "1.0a"

class HealthResponse(BaseModel):
    status: str
    version: str

class BattleResponse(BaseModel):
    query: str
    raw_answer: str
    raw_time: float
    guarded_answer: str | None
    guarded_valid: bool
    guarded_corrections: int
    guarded_violations: list[str]
    guarded_confidence: str = ""
    guarded_time: float
    comparison: str  # "MATCH", "CORRECTED", "BLOCKED"

class DualResponse(BaseModel):
    query: str
    claude_answer: str | None
    claude_valid: bool
    claude_confidence: str = ""
    claude_time: float
    openai_answer: str | None
    openai_valid: bool
    openai_confidence: str = ""
    openai_time: float
    agreement: bool  # Согласны ли модели

class BenchmarkRequest(BaseModel):
    n: int = Field(default=10, ge=1, le=100, description="Number of questions")
    provider: str = Field(default="openai", pattern="^(claude|openai)$")
    topic: str | None = Field(default=None, description="Filter by topic")

class BenchmarkItem(BaseModel):
    question: str
    expected: str
    answer: str | None
    synthesized: bool  # True if final_answer (clean), False if d5_content (ERR)
    valid: bool
    corrections: int
    time_seconds: float

class BenchmarkResponse(BaseModel):
    total: int
    valid_count: int
    valid_rate: float
    avg_corrections: float
    avg_time: float
    items: list[BenchmarkItem]

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Regulus AI API",
    description="Structural Guardrail for LLM Reasoning Verification",
    version="1.0a"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from regulus.api.rate_limit import RateLimitMiddleware  # noqa: E402

app.add_middleware(RateLimitMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return structured error."""
    logger.error(f"Unhandled error on {request.url}: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "type": type(exc).__name__,
            "version": "1.0a",
        }
    )


async def with_timeout(coro, timeout_seconds: int = 120):
    """Wrap async operation with timeout protection."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Request timed out after {timeout_seconds}s. The LLM may be slow or unresponsive."
        )


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/api/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    logger.info("Health check called")
    return HealthResponse(status="ok", version="1.0a")


@app.get("/api/info")
async def info():
    """System information and capabilities."""
    return {
        "name": "Regulus AI",
        "version": "1.0a",
        "engine": "SocraticOrchestrator v2",
        "theory": "Theory of Systems (Laws L1-L5, Principles P1-P4)",
        "features": {
            "socratic_pipeline": True,
            "trisection": True,
            "source_verification": True,
            "quality_gates": True,
            "cross_judge": True,
            "lab_benchmarks": True,
        },
        "domains": {
            "D1": "Recognition — What is actually here?",
            "D2": "Clarification — What exactly is this?",
            "D3": "Framework — How do we connect this?",
            "D4": "Comparison — How does it process?",
            "D5": "Inference — What follows?",
            "D6": "Reflection — Where doesn't it work?",
        },
        "providers": ["claude", "openai"],
        "endpoints": [
            "/api/health",
            "/api/info",
            "/api/verify",
            "/api/battle",
            "/api/dual",
            "/api/benchmark",
            "/api/benchmark/stream",
            "/api/lab/*",
        ],
    }


@app.post("/api/verify", response_model=VerifyResponse)
async def verify(request: VerifyRequest):
    """Run verification on a query using Socratic pipeline."""
    start_time = time.time()

    try:
        if request.provider == "claude":
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            client = ClaudeClient(api_key=api_key)
        else:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            client = HybridClient(api_key=api_key)

        orch = SocraticOrchestrator(llm_client=client)
        result = await with_timeout(orch.process_query(request.query), timeout_seconds=240)

        # Convert domain_records to steps
        steps = []
        for record in result.domain_records:
            steps.append(StepModel(
                domain=record.domain,
                content=record.content[:2000] if record.content else "",
                passed=record.passed,
                weight=float(record.final_weight),
                probes_used=len(record.probes_used),
            ))

        # Collect violations from failed domains
        violations = [
            record.domain for record in result.domain_records
            if not record.passed
        ]

        return VerifyResponse(
            query=request.query,
            valid=result.is_valid,
            answer=result.final_answer,
            primary_answer=result.d5_content,
            corrections=result.total_probes,
            violations=violations,
            steps=steps,
            branches_explored=len(result.domain_records),
            confidence_level=result.confidence_level,
            time_seconds=time.time() - start_time,
            version="1.0a",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/battle", response_model=BattleResponse)
async def battle(request: VerifyRequest):
    """Battle mode: compare raw LLM vs Regulus-guarded response."""

    try:
        # Create LLM client
        if request.provider == "claude":
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            client = ClaudeClient(api_key=api_key)
        else:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            client = HybridClient(api_key=api_key)

        # 1. Raw LLM response
        raw_start = time.time()
        raw_response = await with_timeout(client.generate(request.query), timeout_seconds=60)
        raw_time = time.time() - raw_start

        # 2. Guarded response via SocraticOrchestrator
        guarded_start = time.time()
        orch = SocraticOrchestrator(llm_client=client)
        result = await with_timeout(orch.process_query(request.query), timeout_seconds=240)
        guarded_time = time.time() - guarded_start

        # 3. Get guarded answer (prefer final_answer, fallback to d5_content)
        guarded_answer = result.final_answer or result.d5_content
        if guarded_answer:
            guarded_answer = guarded_answer[:2000]

        # 4. Determine comparison result
        if not guarded_answer:
            comparison = "BLOCKED"
        elif result.total_probes > 0:
            comparison = "CORRECTED"
        else:
            comparison = "MATCH"

        # Violations from failed domains
        violations = [
            record.domain for record in result.domain_records
            if not record.passed
        ]

        return BattleResponse(
            query=request.query,
            raw_answer=raw_response[:2000],
            raw_time=raw_time,
            guarded_answer=guarded_answer,
            guarded_valid=result.is_valid,
            guarded_corrections=result.total_probes,
            guarded_violations=violations,
            guarded_confidence=result.confidence_level,
            guarded_time=guarded_time,
            comparison=comparison,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/dual", response_model=DualResponse)
async def dual(request: VerifyRequest):
    """Run verification on both Claude and OpenAI, compare results."""

    async def run_with_provider(provider: str):
        start = time.time()
        try:
            if provider == "claude":
                api_key = os.environ.get("ANTHROPIC_API_KEY", "")
                client = ClaudeClient(api_key=api_key)
            else:
                api_key = os.environ.get("OPENAI_API_KEY", "")
                client = HybridClient(api_key=api_key)

            orch = SocraticOrchestrator(llm_client=client)
            result = await with_timeout(orch.process_query(request.query), timeout_seconds=240)

            # Prefer final_answer, fallback to d5_content
            answer = result.final_answer or result.d5_content
            if answer:
                answer = answer[:2000]
            valid = result.is_valid

            return {
                "answer": answer,
                "valid": valid,
                "confidence": result.confidence_level,
                "time": time.time() - start
            }
        except Exception as e:
            return {
                "answer": f"Error: {str(e)}",
                "valid": False,
                "confidence": "",
                "time": time.time() - start
            }

    # Run in parallel
    claude_result, openai_result = await asyncio.gather(
        run_with_provider("claude"),
        run_with_provider("openai")
    )

    return DualResponse(
        query=request.query,
        claude_answer=claude_result["answer"],
        claude_valid=claude_result["valid"],
        claude_confidence=claude_result.get("confidence", ""),
        claude_time=claude_result["time"],
        openai_answer=openai_result["answer"],
        openai_valid=openai_result["valid"],
        openai_confidence=openai_result.get("confidence", ""),
        openai_time=openai_result["time"],
        agreement=claude_result["valid"] == openai_result["valid"]
    )

@app.post("/api/benchmark", response_model=BenchmarkResponse)
async def benchmark(request: BenchmarkRequest):
    """Run Regulus Socratic verification on SimpleQA questions."""
    items = load_simpleqa(n=request.n, topic_filter=request.topic)

    if request.provider == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        client = ClaudeClient(api_key=api_key)
    else:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        client = HybridClient(api_key=api_key)

    results = []
    for item in items:
        start = time.time()
        try:
            # Use SocraticOrchestrator for clean final_answer synthesis
            orch = SocraticOrchestrator(llm_client=client)
            result = await orch.process_query(item.problem)

            # Prefer final_answer (clean synthesis), fallback to d5_content
            synthesized = result.final_answer is not None
            answer = result.final_answer or result.d5_content or None
            if answer:
                answer = answer[:500]
            valid = result.is_valid
            corrections = result.total_corrections
        except Exception as e:
            answer = f"Error: {str(e)}"
            synthesized = False
            valid = False
            corrections = 0

        results.append(BenchmarkItem(
            question=item.problem,
            expected=item.answer,
            answer=answer,
            synthesized=synthesized,
            valid=valid,
            corrections=corrections,
            time_seconds=time.time() - start,
        ))

    valid_count = sum(1 for r in results if r.valid)

    return BenchmarkResponse(
        total=len(results),
        valid_count=valid_count,
        valid_rate=valid_count / len(results) if results else 0,
        avg_corrections=sum(r.corrections for r in results) / len(results) if results else 0,
        avg_time=sum(r.time_seconds for r in results) / len(results) if results else 0,
        items=results,
    )

@app.get("/api/simpleqa/topics")
async def simpleqa_topics():
    """Get SimpleQA topic distribution."""
    return get_topics()


@app.get("/api/benchmark/stream")
async def benchmark_stream(
    n: int = Query(default=10, ge=1, le=5000, description="Number of questions"),
    concurrency: int = Query(default=5, ge=1, le=20, description="Parallel workers"),
    provider: str = Query(default="openai", pattern="^(claude|openai)$"),
    with_judge: bool = Query(default=True, description="Run judge evaluation"),
):
    """
    Stream benchmark results via Server-Sent Events with reasoning visibility.

    Events:
    - {"type": "status", "index": 0, "phase": "reasoning", "question": "..."}
    - {"type": "reasoning", "index": 0, "domain": "D1", "content": "..."}
    - {"type": "status", "index": 0, "phase": "synthesizing"}
    - {"type": "status", "index": 0, "phase": "judging"}
    - {"type": "progress", "index": 0, "item": {...}, "judge": {...}}
    - {"type": "done", "summary": {...}}
    """
    from regulus.judge import CrossJudge

    items = load_simpleqa(n=n)
    judge = CrossJudge() if with_judge else None

    # Create LLM client (shared across workers)
    if provider == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        client = ClaudeClient(api_key=api_key)
    else:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        client = HybridClient(api_key=api_key)

    async def generate():
        semaphore = asyncio.Semaphore(concurrency)
        results_queue: asyncio.Queue = asyncio.Queue()
        status_queue: asyncio.Queue = asyncio.Queue()  # For status updates from first worker
        completed = {"count": 0, "valid": 0, "correct": 0, "total_time": 0.0, "total_corrections": 0}

        async def process_one(item, index: int, is_first: bool):
            async with semaphore:
                start = time.time()
                reasoning_steps = []

                # Send status: reasoning
                if is_first:
                    await status_queue.put({
                        "type": "status",
                        "index": index,
                        "phase": "reasoning",
                        "question": item.problem[:200],
                    })

                try:
                    orch = SocraticOrchestrator(llm_client=client)
                    result = await orch.process_query(item.problem)

                    # Extract reasoning steps for display
                    for step in result.reasoning_steps:
                        domain = step.get("domain", "")
                        content = step.get("content", "")[:500]
                        reasoning_steps.append({"domain": domain, "content": content})
                        if is_first:
                            await status_queue.put({
                                "type": "reasoning",
                                "index": index,
                                "domain": domain,
                                "content": content,
                            })

                    # Send status: synthesizing
                    if is_first:
                        await status_queue.put({
                            "type": "status",
                            "index": index,
                            "phase": "synthesizing",
                        })

                    answer = result.final_answer or result.d5_content or None
                    valid = result.is_valid
                    corrections = result.total_corrections
                    synthesized = result.final_answer is not None

                except Exception as e:
                    answer = f"Error: {str(e)}"
                    valid = False
                    corrections = 0
                    synthesized = False
                    reasoning_steps = []

                elapsed = time.time() - start

                # Judge evaluation
                judge_result = None
                if judge and answer and valid:
                    if is_first:
                        await status_queue.put({
                            "type": "status",
                            "index": index,
                            "phase": "judging",
                        })
                    try:
                        prov = "anthropic" if provider == "claude" else "openai"
                        eval_result = judge.evaluate(
                            question=item.problem,
                            reference=item.answer,
                            answer=answer,
                            answer_provider=prov,
                        )
                        judge_result = {
                            "correct": eval_result.get("truthful", False),
                            "informative": eval_result.get("informative", False),
                            "reason": eval_result.get("truth_reason", ""),
                        }
                    except Exception:
                        judge_result = {"correct": False, "informative": False, "reason": "Judge error"}

                result_item = {
                    "question": item.problem,
                    "expected": item.answer,
                    "answer": answer,
                    "synthesized": synthesized,
                    "valid": valid,
                    "corrections": corrections,
                    "time_seconds": elapsed,
                    "reasoning_steps": reasoning_steps,
                    "judge": judge_result,
                }
                await results_queue.put((index, result_item, is_first))

        # Start all tasks - mark first one for detailed logging
        tasks = [
            asyncio.create_task(process_one(item, i, i == 0))
            for i, item in enumerate(items)
        ]

        # Stream results and status updates as they come
        total = len(items)
        pending_statuses = True

        while completed["count"] < total or pending_statuses:
            # Check for status updates (non-blocking)
            try:
                while True:
                    status = status_queue.get_nowait()
                    yield f"data: {json.dumps(status)}\n\n"
            except asyncio.QueueEmpty:
                pass

            # Check for results
            try:
                index, result_item, is_first = await asyncio.wait_for(
                    results_queue.get(), timeout=1.0
                )
                completed["count"] += 1
                completed["total_time"] += result_item["time_seconds"]
                completed["total_corrections"] += result_item["corrections"]
                if result_item["valid"]:
                    completed["valid"] += 1
                if result_item.get("judge", {}).get("correct"):
                    completed["correct"] += 1

                if is_first:
                    pending_statuses = False

                # Send progress update
                progress_data = {
                    "type": "progress",
                    "index": index,
                    "completed": completed["count"],
                    "total": total,
                    "valid_so_far": completed["valid"],
                    "correct_so_far": completed["correct"],
                    "item": result_item,
                }
                yield f"data: {json.dumps(progress_data)}\n\n"

            except asyncio.TimeoutError:
                if completed["count"] >= total:
                    break
                continue

        # Wait for all tasks to complete (cleanup)
        await asyncio.gather(*tasks, return_exceptions=True)

        # Send final summary
        n_done = completed["count"]
        summary = {
            "type": "done",
            "summary": {
                "total": n_done,
                "valid_count": completed["valid"],
                "valid_rate": completed["valid"] / n_done if n_done else 0,
                "avg_corrections": completed["total_corrections"] / n_done if n_done else 0,
                "avg_time": completed["total_time"] / n_done if n_done else 0,
            }
        }
        yield f"data: {json.dumps(summary)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


# ============================================================================
# Lab API Endpoints
# ============================================================================

class LabCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    total_questions: int = Field(..., ge=1, le=5000)
    num_steps: int = Field(..., ge=1, le=5000)
    dataset: str = Field(default="simpleqa")
    provider: str = Field(default="openai", pattern="^(claude|openai)$")
    concurrency: int = Field(default=5, ge=1, le=20)
    mode: str = Field(default="v1", pattern="^(v1|v2)$")
    reasoning_model: str = Field(default="", description="For v2 mode: deepseek, claude-thinking, openai-reasoning")
    seed: int = Field(default=42, ge=0, description="Random seed for dataset sampling")


class CostInfo(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    spent_cost: float
    estimated_remaining: float
    estimated_total: float
    currency: str = "USD"


class LabRunSummary(BaseModel):
    id: int
    name: str
    dataset: str
    provider: str
    total_questions: int
    num_steps: int
    concurrency: int
    status: str
    current_step: int
    completed_questions: int
    valid_count: int
    correct_count: int
    total_time: float
    progress_percent: float
    input_tokens: int
    output_tokens: int
    cost: CostInfo | None = None
    mode: str = "v1"
    reasoning_model: str = ""
    created_at: str
    updated_at: str


class LabStepSummary(BaseModel):
    id: int
    step_number: int
    status: str
    questions_start: int
    questions_end: int
    valid_count: int
    correct_count: int
    total_time: float
    started_at: str | None
    completed_at: str | None


class LabResultItem(BaseModel):
    id: int
    question: str
    expected: str
    answer: str | None
    valid: bool
    correct: bool | None
    informative: bool | None
    judge_reason: str | None
    failure_reason: str | None = None
    corrections: int
    time_seconds: float


class LabRunDetail(LabRunSummary):
    steps: list[LabStepSummary]


# Global Lab instances
_lab_db = None
_lab_runner = None
_report_generator = None


def get_lab_db() -> LabDB:
    global _lab_db
    if _lab_db is None:
        _lab_db = LabDB()
    return _lab_db


def get_lab_runner() -> LabRunner:
    global _lab_runner
    if _lab_runner is None:
        _lab_runner = LabRunner(get_lab_db())
    return _lab_runner


def get_report_generator() -> ReportGenerator:
    global _report_generator
    if _report_generator is None:
        _report_generator = ReportGenerator()
    return _report_generator


def run_to_summary(run) -> LabRunSummary:
    # Calculate cost info
    cost_info = None
    remaining_questions = run.total_questions - run.completed_questions

    if run.completed_questions > 0:
        # Use actual averages to estimate remaining cost
        spent = calculate_cost(run.input_tokens, run.output_tokens, run.provider)
        remaining = estimate_remaining_cost(
            remaining_questions,
            run.avg_input_tokens_per_question,
            run.avg_output_tokens_per_question,
            run.provider,
        )
        cost_info = CostInfo(
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            total_tokens=run.total_tokens,
            spent_cost=round(spent.total_cost, 4),
            estimated_remaining=round(remaining.total_cost, 4),
            estimated_total=round(spent.total_cost + remaining.total_cost, 4),
        )
    else:
        # Use default estimates
        est = estimate_run_cost(run.total_questions, run.provider)
        cost_info = CostInfo(
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            spent_cost=0.0,
            estimated_remaining=round(est.total_cost, 4),
            estimated_total=round(est.total_cost, 4),
        )

    return LabRunSummary(
        id=run.id,
        name=run.name,
        dataset=run.dataset,
        provider=run.provider,
        total_questions=run.total_questions,
        num_steps=run.num_steps,
        concurrency=run.concurrency,
        status=run.status.value,
        current_step=run.current_step,
        completed_questions=run.completed_questions,
        valid_count=run.valid_count,
        correct_count=run.correct_count,
        total_time=run.total_time,
        progress_percent=run.progress_percent,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        cost=cost_info,
        mode=getattr(run, 'mode', 'v1'),
        reasoning_model=getattr(run, 'reasoning_model', ''),
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def step_to_summary(step) -> LabStepSummary:
    return LabStepSummary(
        id=step.id,
        step_number=step.step_number,
        status=step.status.value,
        questions_start=step.questions_start,
        questions_end=step.questions_end,
        valid_count=step.valid_count,
        correct_count=step.correct_count,
        total_time=step.total_time,
        started_at=step.started_at,
        completed_at=step.completed_at,
    )


@app.post("/api/lab/runs", response_model=LabRunSummary)
async def lab_create_run(request: LabCreateRequest):
    """Create a new Lab run."""
    runner = get_lab_runner()
    run = runner.create_run(
        name=request.name,
        total_questions=request.total_questions,
        num_steps=request.num_steps,
        dataset=request.dataset,
        provider=request.provider,
        concurrency=request.concurrency,
        mode=request.mode,
        reasoning_model=request.reasoning_model,
        seed=request.seed,
    )
    return run_to_summary(run)


@app.get("/api/lab/runs", response_model=list[LabRunSummary])
async def lab_list_runs(limit: int = Query(default=50, ge=1, le=200)):
    """List all Lab runs."""
    runner = get_lab_runner()
    runs = runner.list_runs(limit=limit)
    return [run_to_summary(r) for r in runs]


@app.get("/api/lab/runs/{run_id}", response_model=LabRunDetail)
async def lab_get_run(run_id: int):
    """Get details of a Lab run."""
    runner = get_lab_runner()
    run = runner.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Calculate cost info (same logic as run_to_summary)
    remaining_questions = run.total_questions - run.completed_questions

    if run.completed_questions > 0:
        spent = calculate_cost(run.input_tokens, run.output_tokens, run.provider)
        remaining = estimate_remaining_cost(
            remaining_questions,
            run.avg_input_tokens_per_question,
            run.avg_output_tokens_per_question,
            run.provider,
        )
        cost_info = CostInfo(
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            total_tokens=run.total_tokens,
            spent_cost=round(spent.total_cost, 4),
            estimated_remaining=round(remaining.total_cost, 4),
            estimated_total=round(spent.total_cost + remaining.total_cost, 4),
        )
    else:
        est = estimate_run_cost(run.total_questions, run.provider)
        cost_info = CostInfo(
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            spent_cost=0.0,
            estimated_remaining=round(est.total_cost, 4),
            estimated_total=round(est.total_cost, 4),
        )

    return LabRunDetail(
        id=run.id,
        name=run.name,
        dataset=run.dataset,
        provider=run.provider,
        total_questions=run.total_questions,
        num_steps=run.num_steps,
        concurrency=run.concurrency,
        status=run.status.value,
        current_step=run.current_step,
        completed_questions=run.completed_questions,
        valid_count=run.valid_count,
        correct_count=run.correct_count,
        total_time=run.total_time,
        progress_percent=run.progress_percent,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        cost=cost_info,
        created_at=run.created_at,
        updated_at=run.updated_at,
        steps=[step_to_summary(s) for s in run.steps],
    )


@app.get("/api/lab/runs/{run_id}/steps/{step_number}/results", response_model=list[LabResultItem])
async def lab_get_step_results(run_id: int, step_number: int):
    """Get results for a specific step."""
    db = get_lab_db()
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    step = next((s for s in run.steps if s.step_number == step_number), None)
    if not step:
        raise HTTPException(status_code=404, detail=f"Step {step_number} not found")

    return [
        LabResultItem(
            id=r.id,
            question=r.question,
            expected=r.expected,
            answer=r.answer,
            valid=r.valid,
            correct=r.correct,
            informative=r.informative,
            judge_reason=r.judge_reason,
            failure_reason=r.failure_reason,
            corrections=r.corrections,
            time_seconds=r.time_seconds,
        )
        for r in step.results
    ]


@app.delete("/api/lab/runs/{run_id}")
async def lab_delete_run(run_id: int):
    """Delete a Lab run."""
    db = get_lab_db()
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    db.delete_run(run_id)
    return {"status": "deleted", "run_id": run_id}


@app.post("/api/lab/runs/{run_id}/reset-stuck")
async def lab_reset_stuck_steps(run_id: int):
    """
    Reset stuck running steps that have no results.
    Useful for recovering from interrupted executions.
    """
    db = get_lab_db()
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    reset_count = 0
    for step in run.steps:
        if step.status == StepStatus.RUNNING:
            # Check if step has any results
            results = db.get_step_results(step.id)
            if len(results) == 0:
                db.update_step_status(step.id, StepStatus.PENDING)
                reset_count += 1
                logger.info(f"Reset stuck step {step.step_number} to PENDING")

    # Also reset run status if it was running
    if run.status == RunStatus.RUNNING:
        db.update_run_status(run_id, RunStatus.PAUSED)

    return {"status": "ok", "reset_count": reset_count}


class LabConfigUpdate(BaseModel):
    concurrency: int | None = Field(default=None, ge=1, le=20)
    remaining_steps: int | None = Field(default=None, ge=1)


@app.patch("/api/lab/runs/{run_id}/config")
async def lab_update_config(run_id: int, config: LabConfigUpdate):
    """
    Update run configuration (concurrency and/or resplit remaining steps).
    Only works when run is paused or created.
    """
    db = get_lab_db()
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if run.status not in (RunStatus.CREATED, RunStatus.PAUSED):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot modify config while run is {run.status.value}"
        )

    changes = {}

    if config.concurrency is not None:
        db.update_run_concurrency(run_id, config.concurrency)
        changes["concurrency"] = config.concurrency

    if config.remaining_steps is not None:
        run = db.resplit_pending_steps(run_id, config.remaining_steps)
        pending = [s for s in run.steps if s.status.value == "pending"]
        changes["remaining_steps"] = len(pending)
        changes["new_total_steps"] = run.num_steps

    return {
        "status": "updated",
        "run_id": run_id,
        "changes": changes,
    }


@app.post("/api/lab/runs/{run_id}/continue")
async def lab_continue_run(run_id: int):
    """
    Continue running the next pending step.
    Returns immediately, use /api/lab/runs/{run_id}/stream to monitor progress.
    """
    runner = get_lab_runner()
    run = runner.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    pending_steps = [s for s in run.steps if s.status == StepStatus.PENDING]
    if not pending_steps:
        raise HTTPException(status_code=400, detail="No pending steps to run")

    # Return info about what will run
    next_step = pending_steps[0]
    return {
        "status": "started",
        "run_id": run_id,
        "step_number": next_step.step_number,
        "questions": next_step.questions_end - next_step.questions_start,
    }


@app.get("/api/lab/runs/{run_id}/stream")
async def lab_stream_step(
    run_id: int,
    step_number: int = Query(default=None, description="Step to run, or next pending if omitted"),
):
    """
    Stream step execution progress via Server-Sent Events.
    """
    logger.info(f"Stream requested for run {run_id}, step {step_number}")

    runner = get_lab_runner()
    run = runner.get_run(run_id)
    if not run:
        logger.warning(f"Run {run_id} not found")
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    logger.info(f"Run found: {run.name}, status={run.status.value}")

    async def generate():
        logger.debug("Generator starting")
        try:
            async for progress in runner.stream_step(run_id, step_number):
                logger.debug(f"Progress: type={progress.type}, step={progress.step_number}")

                # Domain-level events use named SSE event types
                if progress.type in ("domain_start", "domain_complete", "correction", "judge_result"):
                    event_data = progress.event_data or {}
                    event_data["timestamp"] = datetime.now(timezone.utc).isoformat() + "Z"
                    yield f"event: {progress.type}\ndata: {json.dumps(event_data)}\n\n"
                    continue

                event_data = {
                    "type": progress.type,
                    "step_number": progress.step_number,
                    "question_index": progress.question_index,
                    "total_in_step": progress.total_in_step,
                    "agent_id": progress.agent_id,
                }
                if progress.result:
                    result_dict = progress.result.to_dict()
                    reasoning_steps = getattr(progress, '_reasoning_steps', [])
                    if reasoning_steps:
                        result_dict["reasoning_steps"] = reasoning_steps
                    event_data["result"] = result_dict
                if progress.error:
                    event_data["error"] = progress.error

                yield f"data: {json.dumps(event_data)}\n\n"

        except Exception as e:
            logger.error(f"Stream error: {e}\n{traceback.format_exc()}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )


@app.post("/api/lab/runs/{run_id}/stop")
async def lab_stop_run(run_id: int):
    """Request graceful stop of current step execution."""
    runner = get_lab_runner()
    run = runner.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    runner.request_stop()
    return {"status": "stop_requested", "run_id": run_id}


@app.post("/api/lab/runs/{run_id}/export")
async def lab_export_run(run_id: int):
    """Export run as JSON and Markdown reports."""
    db = get_lab_db()
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    generator = get_report_generator()
    paths = generator.export(run)

    return {
        "status": "exported",
        "run_id": run_id,
        "files": paths,
    }


@app.get("/api/lab/datasets")
async def lab_list_datasets():
    """List available benchmark datasets with metadata."""
    datasets = []

    # SimpleQA
    try:
        from regulus.data.simpleqa import (
            total_count as simpleqa_total,
            get_categories as simpleqa_categories,
        )
        datasets.append({
            "id": "simpleqa",
            "name": "SimpleQA",
            "description": "Factual question answering benchmark by OpenAI",
            "total_questions": simpleqa_total(),
            "categories": simpleqa_categories(),
            "type": "factual",
        })
    except Exception:
        pass

    # BBEH
    try:
        from regulus.data.bbeh import (
            total_count as bbeh_total,
            get_categories as bbeh_categories,
        )
        datasets.append({
            "id": "bbeh",
            "name": "BBEH (Big-Bench Extra Hard)",
            "description": "Complex reasoning benchmark by Google DeepMind",
            "total_questions": bbeh_total(),
            "categories": bbeh_categories(),
            "type": "reasoning",
        })
    except Exception:
        pass

    return {"datasets": datasets}


@app.get("/api/lab/datasets/{dataset_id}/sample")
async def lab_dataset_sample(
    dataset_id: str,
    n: int = Query(default=5, ge=1, le=50),
    category: str | None = Query(default=None),
):
    """Get sample questions from a dataset (for preview in wizard)."""
    import random as _random

    if dataset_id == "simpleqa":
        items = load_simpleqa(n=None, topic_filter=category)
        rng = _random.Random(42)
        sample = rng.sample(items, min(n, len(items)))
        return [
            {"id": i, "question": item.problem, "expected": item.answer, "category": item.topic}
            for i, item in enumerate(sample)
        ]
    elif dataset_id == "bbeh":
        from regulus.data.bbeh import load_dataset as load_bbeh_ds
        items = load_bbeh_ds(n=None)
        rng = _random.Random(42)
        sample = rng.sample(items, min(n, len(items)))
        return [
            {"id": i, "question": item.problem[:300], "expected": item.answer, "category": "reasoning"}
            for i, item in enumerate(sample)
        ]
    else:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found")


@app.get("/api/lab/runs/{run_id}/results/passed")
async def lab_get_passed_results(run_id: int):
    """Get all passed results for a run."""
    db = get_lab_db()
    results = db.get_run_results_filtered(run_id, passed=True)
    return [r.to_dict() for r in results]


@app.get("/api/lab/runs/{run_id}/results/failed")
async def lab_get_failed_results(run_id: int):
    """Get all failed results for a run."""
    db = get_lab_db()
    results = db.get_run_results_filtered(run_id, passed=False)
    return [r.to_dict() for r in results]


class RetryRunRequest(BaseModel):
    name: str | None = None
    num_steps: int = Field(default=1, ge=1, le=100)
    provider: str | None = None
    concurrency: int = Field(default=5, ge=1, le=20)
    model_version: str = ""


@app.post("/api/lab/runs/{run_id}/retry-failed")
async def lab_retry_failed(run_id: int, request: RetryRunRequest):
    """Create a new run from failed results of an existing run."""
    db = get_lab_db()
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    failed = db.get_run_results_filtered(run_id, passed=False)
    if not failed:
        raise HTTPException(status_code=400, detail="No failed results to retry")

    runner = get_lab_runner()
    new_run = runner.create_run(
        name=request.name or f"Retry of run #{run_id}",
        total_questions=len(failed),
        num_steps=request.num_steps,
        dataset=run.dataset,
        provider=request.provider or run.provider,
        concurrency=request.concurrency,
        source_run_id=run_id,
        model_version=request.model_version or run.model_version or "",
    )

    return run_to_summary(new_run)


@app.get("/api/lab/runs/{run_id}/comparison/{source_run_id}")
async def lab_compare_runs(run_id: int, source_run_id: int):
    """
    Compare two runs by common questions.
    Returns fixed, still_failed, and regressions.
    """
    db = get_lab_db()

    current_results = db.get_all_results(run_id)
    source_results = db.get_all_results(source_run_id)

    if not current_results:
        raise HTTPException(status_code=404, detail=f"No results for run {run_id}")
    if not source_results:
        raise HTTPException(status_code=404, detail=f"No results for run {source_run_id}")

    source_map = {r.question: r for r in source_results}
    current_map = {r.question: r for r in current_results}

    common_questions = set(source_map.keys()) & set(current_map.keys())

    fixed = []
    still_failed = []
    regressions = []

    for q in common_questions:
        s = source_map[q]
        c = current_map[q]

        item = {
            "question": q,
            "source_answer": s.answer,
            "current_answer": c.answer,
            "source_passed": s.is_passed,
            "current_passed": c.is_passed,
            "source_failure_reason": s.failure_reason,
            "current_failure_reason": c.failure_reason,
        }

        if not s.is_passed and c.is_passed:
            fixed.append(item)
        elif not s.is_passed and not c.is_passed:
            still_failed.append(item)
        elif s.is_passed and not c.is_passed:
            regressions.append(item)

    return {
        "run_id": run_id,
        "source_run_id": source_run_id,
        "fixed": fixed,
        "still_failed": still_failed,
        "regressions": regressions,
        "summary": {
            "total_compared": len(common_questions),
            "fixed_count": len(fixed),
            "still_failed_count": len(still_failed),
            "regression_count": len(regressions),
        }
    }


def _classify_failure(failure_reason: str | None, result) -> str:
    """Classify a failure by pattern for error aggregation."""
    if not failure_reason:
        if not result.valid:
            return "INVALID_REASONING"
        if result.correct is False:
            return "INCORRECT_ANSWER"
        return "UNKNOWN"

    reason_lower = failure_reason.lower()

    if "d1" in reason_lower or "recognition" in reason_lower:
        return "D1_RECOGNITION_ERROR"
    elif "d2" in reason_lower or "clarification" in reason_lower:
        return "D2_CLARIFICATION_ERROR"
    elif "d3" in reason_lower or "framework" in reason_lower:
        return "D3_FRAMEWORK_ERROR"
    elif "d4" in reason_lower or "comparison" in reason_lower:
        return "D4_COMPARISON_ERROR"
    elif "d5" in reason_lower or "inference" in reason_lower:
        return "D5_INFERENCE_ERROR"
    elif "d6" in reason_lower or "reflection" in reason_lower:
        return "D6_REFLECTION_ERROR"
    elif "source" in reason_lower or "search" in reason_lower or "verif" in reason_lower:
        return "SOURCE_VERIFICATION_FAILED"
    elif "timeout" in reason_lower or "timed out" in reason_lower:
        return "TIMEOUT"
    elif "contradict" in reason_lower:
        return "SELF_CONTRADICTION"
    elif "hallucin" in reason_lower:
        return "HALLUCINATION"
    elif "error:" in reason_lower:
        return "RUNTIME_ERROR"

    return "OTHER: " + failure_reason[:50]


@app.get("/api/lab/runs/{run_id}/error-patterns")
async def lab_error_patterns(run_id: int):
    """Group failed results by error type for analysis."""
    db = get_lab_db()
    failed_results = db.get_run_results_filtered(run_id, passed=False)

    if not failed_results:
        return {"patterns": [], "total_failed": 0}

    pattern_map: dict[str, list] = {}

    for r in failed_results:
        pattern = _classify_failure(r.failure_reason, r)
        if pattern not in pattern_map:
            pattern_map[pattern] = []
        pattern_map[pattern].append({
            "result_id": r.id,
            "question": r.question[:100],
            "failure_reason": r.failure_reason,
            "time_seconds": r.time_seconds,
        })

    patterns = []
    for pattern_type, items in sorted(pattern_map.items(), key=lambda x: -len(x[1])):
        patterns.append({
            "type": pattern_type,
            "count": len(items),
            "percentage": round(len(items) / len(failed_results) * 100, 1),
            "questions": items,
        })

    return {
        "patterns": patterns,
        "total_failed": len(failed_results),
    }


# ============================================================================
# Archive & Leaderboard Endpoints
# ============================================================================

from regulus.api.routers.lab.teams import router as teams_router
from regulus.api.routers.lab.tests import router as tests_router
from regulus.api.routers.lab.benchmarks import router as benchmarks_router
from regulus.api.routers.lab.runs import router as runs_router
from regulus.api.routers.lab.results import router as results_router
from regulus.api.routers.lab.instructions import router as instructions_router
from regulus.api.routers.lab.paradigms import router as paradigms_router
from regulus.api.routers.lab.paradigm_config import router as paradigm_config_router
from regulus.api.routers.lab.instruction_sets import router as instruction_sets_router
from regulus.api.routers.lab.model_settings import router as model_settings_router

app.include_router(teams_router)
app.include_router(tests_router)
app.include_router(benchmarks_router)
app.include_router(runs_router)
app.include_router(results_router)
app.include_router(instructions_router)
app.include_router(paradigms_router)
app.include_router(paradigm_config_router)
app.include_router(instruction_sets_router)
app.include_router(model_settings_router)


from regulus.lab.archive import ArchiveManager

_archive_manager = None

def get_archive_manager() -> ArchiveManager:
    global _archive_manager
    if _archive_manager is None:
        _archive_manager = ArchiveManager()
    return _archive_manager


@app.post("/api/lab/runs/{run_id}/archive")
async def lab_archive_run(run_id: int):
    """Archive a completed run to filesystem."""
    db = get_lab_db()
    archive = get_archive_manager()
    try:
        result = archive.archive_run(db, run_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/lab/archive/{dataset}")
async def lab_list_archives(dataset: str):
    """List all archives for a dataset."""
    archive = get_archive_manager()
    return {"dataset": dataset, "archives": archive.list_archives(dataset)}


@app.get("/api/lab/archive/{dataset}/{folder}/{filename}")
async def lab_get_archive_file(dataset: str, folder: str, filename: str):
    """Download a file from archive."""
    from fastapi.responses import FileResponse
    archive = get_archive_manager()
    path = archive.get_archive_file(dataset, folder, filename)
    if not path:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)


@app.get("/api/lab/leaderboard/{dataset}")
async def lab_get_leaderboard(dataset: str):
    """Get leaderboard for a dataset."""
    archive = get_archive_manager()
    return archive.get_leaderboard(dataset)


@app.post("/api/lab/leaderboard/{dataset}/refresh")
async def lab_refresh_leaderboard(dataset: str):
    """Rebuild leaderboard from all archives."""
    archive = get_archive_manager()
    return archive.refresh_leaderboard(dataset)


# ============================================================================
# Run Stats Endpoint
# ============================================================================

@app.get("/api/lab/runs/{run_id}/stats")
async def lab_run_stats(run_id: int):
    """Aggregated statistics for a run (polled by UI or triggered on SSE events)."""
    db = get_lab_db()
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    results = db.get_all_results(run_id)

    total = len(results)
    passed = sum(1 for r in results if r.is_passed)
    failed = sum(1 for r in results if not r.is_passed)
    fixed = sum(1 for r in results if r.retry_status == "fixed")

    total_time = sum(r.time_seconds for r in results)
    total_input = sum(r.input_tokens for r in results)
    total_output = sum(r.output_tokens for r in results)

    accuracy = round(passed / total * 100, 1) if total > 0 else 0
    avg_time = round(total_time / total, 1) if total > 0 else 0

    # Cost estimate (Claude Sonnet pricing)
    cost = round((total_input * 3.0 + total_output * 15.0) / 1_000_000, 2)

    # ETA
    remaining = run.total_questions - total
    eta_seconds = round(remaining * avg_time) if avg_time > 0 else 0

    return {
        "run_id": run_id,
        "status": run.status.value,
        "total_questions": run.total_questions,
        "completed": total,
        "passed": passed,
        "failed": failed,
        "fixed": fixed,
        "accuracy": accuracy,
        "avg_time_seconds": avg_time,
        "total_time_seconds": round(total_time, 1),
        "cost_usd": cost,
        "tokens": {"input": total_input, "output": total_output},
        "eta_seconds": eta_seconds,
        "progress_pct": round(total / run.total_questions * 100, 1) if run.total_questions > 0 else 0,
    }


# ============================================================================
# Reports Endpoints
# ============================================================================

@app.get("/api/lab/reports")
async def lab_list_reports():
    """List all generated reports."""
    generator = get_report_generator()
    return generator.list_reports()


@app.get("/api/lab/reports/{filename}")
async def lab_get_report(filename: str):
    """Get report content by filename."""
    generator = get_report_generator()
    report = generator.get_report(filename)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {filename} not found")
    return report


# ============================================================================
# V2 Audit Pipeline Endpoints
# ============================================================================

class V2VerifyRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    reasoning_model: str = Field(default="deepseek", description="deepseek, claude-thinking, openai-reasoning")
    analyst_model: str = Field(default="gpt-4o-mini")

class V2AuditRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000)
    trace: str = Field(..., min_length=1, description="Reasoning trace to audit")
    answer: str = Field(..., min_length=1, description="Final answer to audit")
    trace_format: str = Field(default="full_cot", description="full_cot, summary, or none")


@app.post("/api/v2/verify")
async def v2_verify(request: V2VerifyRequest):
    """Run v2 pipeline: reasoning model + audit."""
    from regulus.reasoning.factory import get_provider
    from regulus.audit.orchestrator import AuditOrchestrator
    from regulus.audit.types import AuditConfig

    # Get reasoning provider
    reasoning_api_keys = {
        "deepseek": os.environ.get("DEEPSEEK_API_KEY", ""),
        "claude-thinking": os.environ.get("ANTHROPIC_API_KEY", ""),
        "openai-reasoning": os.environ.get("OPENAI_API_KEY", ""),
    }
    api_key = reasoning_api_keys.get(request.reasoning_model, "")
    if not api_key:
        raise HTTPException(status_code=400, detail=f"No API key for {request.reasoning_model}")

    reasoning_provider = get_provider(request.reasoning_model, api_key=api_key)

    # Audit LLM
    audit_api_key = os.environ.get("OPENAI_API_KEY", "")
    audit_llm = OpenAIClient(api_key=audit_api_key, model=request.analyst_model)

    orchestrator = AuditOrchestrator(
        reasoning_provider=reasoning_provider,
        audit_llm=audit_llm,
        config=AuditConfig(analyst_model=request.analyst_model),
    )

    result = await with_timeout(orchestrator.process_query(request.query), timeout_seconds=300)
    return result.to_dict()


@app.post("/api/v2/audit")
async def v2_audit(request: V2AuditRequest):
    """Audit-only: bring your own trace, get structural audit."""
    from regulus.reasoning.provider import TraceFormat
    from regulus.audit.auditor import Auditor

    trace_format_map = {
        "full_cot": TraceFormat.FULL_COT,
        "summary": TraceFormat.SUMMARY,
        "none": TraceFormat.NONE,
    }
    trace_format = trace_format_map.get(request.trace_format, TraceFormat.FULL_COT)

    audit_api_key = os.environ.get("OPENAI_API_KEY", "")
    audit_llm = OpenAIClient(api_key=audit_api_key, model="gpt-4o-mini")

    auditor = Auditor(audit_llm)
    result = await with_timeout(
        auditor.audit(
            trace=request.trace,
            answer=request.answer,
            query=request.query,
            trace_format=trace_format,
        ),
        timeout_seconds=120,
    )
    return result.to_dict()


@app.get("/api/v2/providers")
async def v2_list_providers():
    """List available reasoning providers and their trace formats."""
    return {
        "providers": [
            {
                "name": "deepseek",
                "display_name": "DeepSeek-R1",
                "trace_format": "full_cot",
                "description": "Full raw chain-of-thought via reasoning_content",
            },
            {
                "name": "claude-thinking",
                "display_name": "Claude Extended Thinking",
                "trace_format": "summary",
                "description": "Thinking block summaries (not full CoT)",
            },
            {
                "name": "openai-reasoning",
                "display_name": "OpenAI (Stub)",
                "trace_format": "none",
                "description": "Standard chat completion (no reasoning trace yet)",
            },
        ]
    }
