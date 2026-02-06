"""Lab runner for stepped benchmark execution."""

import asyncio
import os
import time
import traceback
from datetime import datetime
from typing import AsyncGenerator, Callable, Optional
from dataclasses import dataclass, field

from regulus.lab.models import (
    LabDB, Run, Step, Result, RunStatus, StepStatus
)
from regulus.lab.costs import estimate_run_cost, calculate_cost
from regulus.data.simpleqa import load_dataset as load_simpleqa, SimpleQAItem
from regulus.data.bbeh import load_dataset as load_bbeh, BBEHItem
from regulus.orchestrator import SocraticOrchestrator
from regulus.judge import CrossJudge
from regulus.llm.claude import ClaudeClient
from regulus.llm.openai import OpenAIClient


def estimate_tokens_from_text(text: str) -> int:
    """Estimate token count from text (rough: ~4 chars per token)."""
    if not text:
        return 0
    return len(text) // 4


@dataclass
class ReasoningEvent:
    """Reasoning step from an agent."""
    type: str = "reasoning"
    agent_id: int = 0
    domain: str = ""
    content: str = ""
    question: str = ""


@dataclass
class DomainEvent:
    """Domain-level event for SSE streaming."""
    type: str  # "domain_start", "domain_complete", "correction", "judge_result"
    agent_id: int = 0
    question_index: int = 0
    domain: str = ""
    data: dict = field(default_factory=dict)


@dataclass
class StepProgress:
    """Progress update during step execution."""
    type: str  # "start", "progress", "complete", "error", "reasoning", "phase",
               # "domain_start", "domain_complete", "correction", "judge_result"
    step_number: int
    question_index: int = 0
    total_in_step: int = 0
    result: Optional[Result] = None
    error: Optional[str] = None
    # For reasoning events
    agent_id: int = 0
    domain: str = ""
    content: str = ""
    question: str = ""
    phase: str = ""  # "reasoning", "synthesizing", "judging"
    # For domain events
    event_data: Optional[dict] = None


def compute_retry_statuses(db: LabDB, retry_run_id: int):
    """
    Compare results of a retry run with its source run.
    Sets retry_status on each result:
    - "fixed": source=fail, retry=pass
    - "still_failed": source=fail, retry=fail
    """
    retry_run = db.get_run(retry_run_id)
    if not retry_run or not retry_run.source_run_id:
        return

    source_results = db.get_all_results(retry_run.source_run_id)
    retry_results = db.get_all_results(retry_run_id)

    source_map = {r.question: r for r in source_results}

    for r in retry_results:
        source = source_map.get(r.question)
        if not source:
            continue

        if not source.is_passed and r.is_passed:
            db.update_result_retry_status(r.id, "fixed")
        elif not source.is_passed and not r.is_passed:
            db.update_result_retry_status(r.id, "still_failed")


class LabRunner:
    """Runs stepped benchmark tests with persistence."""

    def __init__(self, db: Optional[LabDB] = None):
        self.db = db or LabDB()
        self._stop_requested = False

    def create_run(
        self,
        name: str,
        total_questions: int,
        num_steps: int,
        dataset: str = "simpleqa",
        provider: str = "claude",
        concurrency: int = 5,
        source_run_id: Optional[int] = None,
        model_version: str = "",
    ) -> Run:
        """Create a new run."""
        return self.db.create_run(
            name=name,
            total_questions=total_questions,
            num_steps=num_steps,
            dataset=dataset,
            provider=provider,
            concurrency=concurrency,
            source_run_id=source_run_id,
            model_version=model_version,
        )

    def get_run(self, run_id: int) -> Optional[Run]:
        """Get run details."""
        return self.db.get_run(run_id)

    def list_runs(self, limit: int = 50) -> list[Run]:
        """List recent runs."""
        return self.db.list_runs(limit)

    def request_stop(self):
        """Request graceful stop of current execution."""
        self._stop_requested = True

    async def run_step(
        self,
        run_id: int,
        step_number: Optional[int] = None,
        on_progress: Optional[Callable[[StepProgress], None]] = None,
    ) -> Step:
        """
        Execute a single step of a run.

        If step_number is None, runs the next pending step.
        """
        self._stop_requested = False
        run = self.db.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        # Find the step to run
        if step_number is None:
            step = next(
                (s for s in run.steps if s.status == StepStatus.PENDING),
                None
            )
        else:
            step = next(
                (s for s in run.steps if s.step_number == step_number),
                None
            )

        if not step:
            raise ValueError(f"No pending step found for run {run_id}")

        # Allow running steps to be reset if they got stuck (no results and been running > 5 min)
        if step.status == StepStatus.RUNNING:
            # Check if step has any results - if not, it's likely stuck
            step_results = self.db.get_step_results(step.id)
            if len(step_results) == 0:
                print(f"[Runner] Step {step.step_number} is stuck in RUNNING with no results, resetting to PENDING")
                self.db.update_step_status(step.id, StepStatus.PENDING)
                step.status = StepStatus.PENDING
            else:
                raise ValueError(f"Step {step.step_number} is already running with {len(step_results)} results")
        elif step.status not in (StepStatus.PENDING, StepStatus.FAILED):
            raise ValueError(f"Step {step.step_number} is not pending (status: {step.status})")

        # Load dataset
        if run.dataset == "simpleqa":
            all_items = load_simpleqa(n=run.total_questions, seed=42)
        elif run.dataset == "bbeh":
            all_items = load_bbeh(n=run.total_questions, seed=42)
        else:
            raise ValueError(f"Unknown dataset: {run.dataset}")

        # Get questions for this step
        step_items = all_items[step.questions_start:step.questions_end]
        total_in_step = len(step_items)

        # Update statuses
        self.db.update_run_status(run_id, RunStatus.RUNNING, step.step_number)
        self.db.update_step_status(step.id, StepStatus.RUNNING)

        if on_progress:
            on_progress(StepProgress(
                type="start",
                step_number=step.step_number,
                total_in_step=total_in_step,
            ))

        # Initialize LLM client based on provider
        if run.provider == "claude":
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            print(f"[Runner] Using Claude, API key: {'SET' if api_key else 'MISSING!'}")
            llm_client = ClaudeClient(api_key=api_key)
        else:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            print(f"[Runner] Using OpenAI, API key: {'SET' if api_key else 'MISSING!'}")
            llm_client = OpenAIClient(api_key=api_key)

        # Initialize components
        print(f"[Runner] Initializing components...")
        judge = CrossJudge()
        print(f"[Runner] Components initialized, processing {len(step_items)} questions...")

        valid_count = 0
        correct_count = 0
        step_time = 0.0
        step_input_tokens = 0
        step_output_tokens = 0

        # Process questions with concurrency
        semaphore = asyncio.Semaphore(run.concurrency)

        async def process_question(idx: int, item: SimpleQAItem) -> Result:
            async with semaphore:
                if self._stop_requested:
                    return None

                start_time = time.time()
                agent_id = idx + 1  # 1-based agent IDs
                print(f"[Runner] Processing question {idx}: {item.problem[:50]}...")

                try:
                    # Create orchestrator callbacks for domain events
                    def _on_domain_start(domain: str, domain_name: str):
                        if on_progress:
                            on_progress(StepProgress(
                                type="domain_start",
                                step_number=step.step_number,
                                question_index=idx,
                                agent_id=agent_id,
                                domain=domain,
                                event_data={
                                    "question_index": idx,
                                    "agent_id": agent_id,
                                    "domain": domain,
                                    "domain_name": domain_name,
                                },
                            ))

                    def _on_domain_complete(domain: str, result_dict: dict):
                        if on_progress:
                            on_progress(StepProgress(
                                type="domain_complete",
                                step_number=step.step_number,
                                question_index=idx,
                                agent_id=agent_id,
                                domain=domain,
                                event_data={
                                    "question_index": idx,
                                    "agent_id": agent_id,
                                    "domain": domain,
                                    **result_dict,
                                },
                            ))

                    def _on_correction(domain: str, attempt: int, violation: str, fix_summary: str):
                        if on_progress:
                            on_progress(StepProgress(
                                type="correction",
                                step_number=step.step_number,
                                question_index=idx,
                                agent_id=agent_id,
                                domain=domain,
                                event_data={
                                    "question_index": idx,
                                    "agent_id": agent_id,
                                    "domain": domain,
                                    "attempt": attempt,
                                    "violation": violation,
                                    "fix_prompt_summary": fix_summary,
                                },
                            ))

                    # Create per-question orchestrator with callbacks
                    q_orchestrator = SocraticOrchestrator(
                        llm_client=llm_client,
                        on_domain_start=_on_domain_start,
                        on_domain_complete=_on_domain_complete,
                        on_correction=_on_correction,
                    )

                    # Run orchestrator
                    output = await q_orchestrator.process_query(item.problem)
                    elapsed = time.time() - start_time
                    print(f"[Runner] Question {idx} completed in {elapsed:.1f}s, valid={output.is_valid}")

                    # Judge evaluation
                    judge_result = None
                    if output.final_answer:
                        prov = "anthropic" if run.provider == "claude" else "openai"
                        eval_result = judge.evaluate(
                            question=item.problem,
                            reference=item.answer,
                            answer=output.final_answer,
                            answer_provider=prov,
                        )
                        is_truthful = eval_result.get("truthful", False)
                        is_informative = eval_result.get("informative", False)
                        judge_result = type("JudgeResult", (), {
                            "correct": is_truthful and is_informative,
                            "informative": is_informative,
                            "reason": eval_result.get("truth_reason", ""),
                        })()

                        # Emit judge_result event
                        if on_progress:
                            on_progress(StepProgress(
                                type="judge_result",
                                step_number=step.step_number,
                                question_index=idx,
                                agent_id=agent_id,
                                event_data={
                                    "question_index": idx,
                                    "agent_id": agent_id,
                                    "truthful": 1 if is_truthful else 0,
                                    "informative": 1 if is_informative else 0,
                                    "correct": is_truthful and is_informative,
                                    "judge_reason": eval_result.get("truth_reason", ""),
                                },
                            ))

                    # Estimate tokens
                    input_tokens = estimate_tokens_from_text(item.problem) + 2000
                    output_tokens = estimate_tokens_from_text(output.final_answer or "") + 3000

                    # Extract reasoning steps for display
                    reasoning_steps = []
                    for rstep in getattr(output, 'reasoning_steps', []):
                        reasoning_steps.append({
                            "domain": rstep.get("domain", ""),
                            "content": rstep.get("content", "")[:500],
                        })

                    # Determine failure reason
                    failure_reason = None
                    is_correct = judge_result.correct if judge_result else None
                    if not output.is_valid:
                        failure_reason = "INVALID_REASONING"
                    elif judge_result and not judge_result.correct:
                        failure_reason = judge_result.reason or "INCORRECT_ANSWER"

                    result = Result(
                        question=item.problem,
                        expected=item.answer,
                        answer=output.final_answer,
                        valid=output.is_valid,
                        correct=is_correct,
                        informative=judge_result.informative if judge_result else None,
                        judge_reason=judge_result.reason if judge_result else None,
                        failure_reason=failure_reason,
                        corrections=output.total_corrections,
                        time_seconds=elapsed,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )
                    result._reasoning_steps = reasoning_steps
                    result._agent_id = agent_id
                except Exception as e:
                    elapsed = time.time() - start_time
                    print(f"[Runner] ERROR processing question {idx}: {e}")
                    traceback.print_exc()
                    result = Result(
                        question=item.problem,
                        expected=item.answer,
                        answer=None,
                        valid=False,
                        correct=False,
                        judge_reason=f"Error: {str(e)}",
                        failure_reason=f"ERROR: {str(e)}",
                        time_seconds=elapsed,
                        input_tokens=500,
                        output_tokens=100,
                    )
                    result._reasoning_steps = []
                    result._agent_id = agent_id

                return result

        # Run all questions in parallel batches
        results = []
        tasks = [process_question(i, item) for i, item in enumerate(step_items)]

        for i, coro in enumerate(asyncio.as_completed(tasks)):
            if self._stop_requested:
                break

            result = await coro
            if result is None:
                continue

            results.append(result)

            # Save to DB
            self.db.add_result(step.id, result)

            if result.valid:
                valid_count += 1
            if result.correct:
                correct_count += 1
            step_time += result.time_seconds
            step_input_tokens += result.input_tokens
            step_output_tokens += result.output_tokens

            if on_progress:
                progress = StepProgress(
                    type="progress",
                    step_number=step.step_number,
                    question_index=len(results),
                    total_in_step=total_in_step,
                    result=result,
                    agent_id=getattr(result, '_agent_id', 0),
                )
                # Attach reasoning steps (not in dataclass to keep it clean)
                progress._reasoning_steps = getattr(result, '_reasoning_steps', [])
                on_progress(progress)

        # Update step stats
        self.db.update_step_stats(
            step.id, valid_count, correct_count, step_time,
            step_input_tokens, step_output_tokens
        )

        if self._stop_requested:
            self.db.update_step_status(step.id, StepStatus.FAILED)
            self.db.update_run_status(run_id, RunStatus.PAUSED)
        else:
            self.db.update_step_status(step.id, StepStatus.COMPLETED)

            # Check if all steps complete
            updated_run = self.db.get_run(run_id)
            all_complete = all(
                s.status == StepStatus.COMPLETED for s in updated_run.steps
            )

            if all_complete:
                self.db.update_run_status(run_id, RunStatus.COMPLETED)
                # Compute retry statuses if this is a retry run
                if updated_run.source_run_id:
                    compute_retry_statuses(self.db, run_id)
            else:
                self.db.update_run_status(run_id, RunStatus.PAUSED)

        # Update run aggregate stats
        updated_run = self.db.get_run(run_id)
        total_valid = sum(s.valid_count for s in updated_run.steps)
        total_correct = sum(s.correct_count for s in updated_run.steps)
        total_time = sum(s.total_time for s in updated_run.steps)
        total_input_tokens = sum(s.input_tokens for s in updated_run.steps)
        total_output_tokens = sum(s.output_tokens for s in updated_run.steps)
        # Count completed questions from finished steps
        total_completed = sum(
            s.questions_end - s.questions_start
            for s in updated_run.steps
            if s.status in (StepStatus.COMPLETED, StepStatus.FAILED)
        )
        self.db.update_run_stats(
            run_id, total_valid, total_correct, total_time,
            total_input_tokens, total_output_tokens,
            completed_questions=total_completed,
        )

        if on_progress:
            on_progress(StepProgress(
                type="complete",
                step_number=step.step_number,
                question_index=len(results),
                total_in_step=total_in_step,
            ))

        return self.db.get_step(step.id)

    async def stream_step(
        self,
        run_id: int,
        step_number: Optional[int] = None,
    ) -> AsyncGenerator[StepProgress, None]:
        """
        Stream step execution progress.

        Yields StepProgress events as the step runs.
        """
        queue = asyncio.Queue()

        def on_progress(progress: StepProgress):
            queue.put_nowait(progress)

        # Start execution in background
        task = asyncio.create_task(
            self.run_step(run_id, step_number, on_progress)
        )

        try:
            while True:
                try:
                    progress = await asyncio.wait_for(queue.get(), timeout=0.5)
                    yield progress
                    if progress.type in ("complete", "error"):
                        break
                except asyncio.TimeoutError:
                    if task.done():
                        # Drain remaining items
                        while not queue.empty():
                            yield queue.get_nowait()
                        break
        finally:
            if not task.done():
                self._stop_requested = True
                await task

    async def run_all_steps(
        self,
        run_id: int,
        on_progress: Optional[Callable[[StepProgress], None]] = None,
    ) -> Run:
        """
        Run all pending steps sequentially.

        Useful for running a complete test in one go.
        """
        self._stop_requested = False
        run = self.db.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        pending_steps = [s for s in run.steps if s.status == StepStatus.PENDING]

        for step in pending_steps:
            if self._stop_requested:
                break
            await self.run_step(run_id, step.step_number, on_progress)

        return self.db.get_run(run_id)
