"""
Lab v2 Test Executor — runs benchmark tests with team rotation.

Integrates:
- BenchmarkLoader (question loading)
- TeamRotationManager (fresh contexts per N questions)
- SocraticOrchestrator / AuditOrchestrator (reasoning)
- Judge (strict or semantic evaluation)
- LabNewDB (result persistence)
- SSE progress events (via callback)
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncGenerator, Callable, Optional

from regulus.api.models.lab import (
    LabNewDB, TestConfig, TestRun, QuestionResult, Team, DomainOutputRecord,
)
from regulus.data.base import BenchmarkExample
from regulus.data.bbeh import get_loader
from regulus.lab.rotation import TeamRotationManager
from regulus.lab.judge_v2 import StrictJudge, SemanticJudge, create_judge, JudgmentResult
from regulus.lab.costs import calculate_cost


# ---------------------------------------------------------------------------
# Progress events (emitted via callback or SSE)
# ---------------------------------------------------------------------------


@dataclass
class ExecutionEvent:
    """Progress event emitted during test execution."""
    type: str  # "run_start", "question_start", "question_complete",
               # "team_rotation", "judgment", "run_complete", "error"
    run_id: str = ""
    question_index: int = 0
    total_questions: int = 0
    team_index: int = 0
    data: dict = field(default_factory=dict)


@dataclass
class OrchestratorOutput:
    """Full output from orchestrator including domain data for training export."""
    answer: str
    tokens_in: int
    tokens_out: int
    agent_outputs: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


class TestExecutor:
    __test__ = False  # Not a pytest test class
    """Executes benchmark tests with team rotation and judging.

    Usage:
        executor = TestExecutor(db)
        async for event in executor.execute(run_id):
            # stream events to SSE
            yield event
    """

    def __init__(self, db: LabNewDB, concurrency: int = 3):
        self.db = db
        self.concurrency = concurrency
        self._stop_requested = False

    def request_stop(self):
        """Request graceful stop of execution."""
        self._stop_requested = True

    async def execute(self, run_id: str) -> AsyncGenerator[ExecutionEvent, None]:
        """Execute a test run, yielding progress events.

        Loads config + team from DB, creates rotation manager, processes
        questions with concurrency, judges results, and stores everything.
        """
        self._stop_requested = False

        # Load run + config
        run = self.db.get_test_run(run_id)
        if not run:
            yield ExecutionEvent(type="error", run_id=run_id, data={"message": f"Run {run_id} not found"})
            return

        cfg = self.db.get_test_config(run.config_id)
        if not cfg:
            yield ExecutionEvent(type="error", run_id=run_id, data={"message": f"Config {run.config_id} not found"})
            return

        team = self.db.get_team(cfg.team_id) if cfg.team_id else None

        # Load benchmark questions
        try:
            loader = get_loader(cfg.benchmark)
        except ValueError as e:
            yield ExecutionEvent(type="error", run_id=run_id, data={"message": str(e)})
            return

        questions = self._load_questions(loader, cfg)
        total = len(questions)

        if total == 0:
            yield ExecutionEvent(type="error", run_id=run_id, data={"message": "No questions loaded"})
            return

        # Set up rotation
        rotation = TeamRotationManager(
            base_team_id=cfg.team_id,
            questions_per_team=cfg.questions_per_team,
            total_questions=total,
        )

        # Set up judge
        judge = create_judge(cfg.judge_config)

        # Update run status to running
        self.db.update_test_run_status(
            run_id, "running",
            total_questions=total,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        yield ExecutionEvent(
            type="run_start",
            run_id=run_id,
            total_questions=total,
            data={
                "benchmark": cfg.benchmark,
                "domains": cfg.domains,
                "total_teams": rotation.total_teams_needed,
            },
        )

        # Process questions
        completed = 0
        correct = 0
        semaphore = asyncio.Semaphore(self.concurrency)
        queue: asyncio.Queue[ExecutionEvent] = asyncio.Queue()

        async def process_question(idx: int, question: BenchmarkExample):
            async with semaphore:
                if self._stop_requested:
                    return

                team_inst = rotation.get_team_for_question(idx)

                # Emit team rotation event if new team
                if rotation.should_rotate(idx):
                    await queue.put(ExecutionEvent(
                        type="team_rotation",
                        run_id=run_id,
                        question_index=idx,
                        team_index=team_inst.index,
                        data={
                            "team_index": team_inst.index,
                            "question_range": list(team_inst.question_range),
                        },
                    ))

                await queue.put(ExecutionEvent(
                    type="question_start",
                    run_id=run_id,
                    question_index=idx,
                    total_questions=total,
                    team_index=team_inst.index,
                    data={
                        "question_id": question.id,
                        "domain": question.domain,
                        "input_preview": question.input[:200],
                    },
                ))

                start_time = time.time()
                try:
                    orch_output = await self._run_orchestrator(
                        question, team, cfg
                    )
                    elapsed_ms = int((time.time() - start_time) * 1000)

                    # Judge
                    judgment = self._judge_answer(
                        judge, orch_output.answer, question.target, question.input
                    )

                    # Cost
                    provider = self._guess_provider(team)
                    cost_est = calculate_cost(orch_output.tokens_in, orch_output.tokens_out, provider)

                    # Build result
                    result = QuestionResult(
                        run_id=run_id,
                        question_index=idx,
                        question_id=question.id,
                        domain=question.domain,
                        input_text=question.input,
                        team_index=team_inst.index,
                        status="completed",
                        final_answer=orch_output.answer,
                        agent_outputs=orch_output.agent_outputs,
                        correct_answer=question.target,
                        judgment_verdict=judgment.verdict,
                        judgment_confidence=judgment.confidence,
                        judgment_explanation=judgment.explanation,
                        judged_at=judgment.judged_at,
                        total_time_ms=elapsed_ms,
                        total_tokens_in=orch_output.tokens_in,
                        total_tokens_out=orch_output.tokens_out,
                        estimated_cost=cost_est.total_cost,
                    )
                except Exception as e:
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    orch_output = None
                    result = QuestionResult(
                        run_id=run_id,
                        question_index=idx,
                        question_id=question.id,
                        domain=question.domain,
                        input_text=question.input,
                        team_index=team_inst.index,
                        status="error",
                        final_answer=None,
                        correct_answer=question.target,
                        judgment_verdict="error",
                        judgment_explanation=f"Execution error: {e}",
                        total_time_ms=elapsed_ms,
                    )

                # Persist
                self.db.create_question_result(result)

                # Save domain output records for training export
                if orch_output and orch_output.agent_outputs.get("domains"):
                    domain_records = []
                    pipeline = orch_output.agent_outputs.get("pipeline", "audit")
                    for d_name, d_data in orch_output.agent_outputs["domains"].items():
                        domain_records.append(DomainOutputRecord(
                            domain=d_name,
                            pipeline=pipeline,
                            content=d_data.get("segment_summary", ""),
                            weight=d_data.get("weight", 0),
                            gate_passed=d_data.get("gate_passed", False),
                            issues_json=json.dumps(d_data.get("issues", [])),
                        ))
                    if domain_records:
                        self.db.create_domain_outputs(result.id, domain_records)

                await queue.put(ExecutionEvent(
                    type="question_complete",
                    run_id=run_id,
                    question_index=idx,
                    total_questions=total,
                    team_index=team_inst.index,
                    data={
                        "question_id": question.id,
                        "domain": question.domain,
                        "verdict": result.judgment_verdict,
                        "answer_preview": (result.final_answer or "")[:200],
                        "time_ms": result.total_time_ms,
                        "tokens_in": result.total_tokens_in,
                        "tokens_out": result.total_tokens_out,
                        "cost": result.estimated_cost,
                    },
                ))

        # Launch all question tasks
        tasks = [
            asyncio.create_task(process_question(i, q))
            for i, q in enumerate(questions)
        ]

        # Sentinel to signal completion
        done = False

        async def wait_for_tasks():
            nonlocal done
            await asyncio.gather(*tasks, return_exceptions=True)
            done = True
            await queue.put(None)  # sentinel

        waiter = asyncio.create_task(wait_for_tasks())

        # Yield events as they come in
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                if done:
                    break
                continue

            if event is None:
                break

            yield event

            if event.type == "question_complete":
                completed += 1
                if event.data.get("verdict") == "correct":
                    correct += 1
                # Update run progress
                self.db.update_test_run_status(
                    run_id, "running",
                    current_question_index=completed,
                    current_team_index=rotation.get_team_index_for_question(
                        max(0, completed - 1)
                    ),
                    teams_used=rotation.get_teams_used(),
                )

        await waiter  # ensure cleanup

        # Finalize
        now = datetime.now(timezone.utc).isoformat()
        final_status = "cancelled" if self._stop_requested else "completed"
        self.db.update_test_run_status(
            run_id, final_status,
            completed_at=now,
            current_question_index=completed,
            teams_used=rotation.get_teams_used(),
        )

        yield ExecutionEvent(
            type="run_complete",
            run_id=run_id,
            total_questions=total,
            data={
                "status": final_status,
                "completed": completed,
                "correct": correct,
                "accuracy": round(correct / completed * 100, 1) if completed else 0,
                "teams_used": len(rotation.teams),
            },
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_questions(
        self, loader, cfg: TestConfig
    ) -> list[BenchmarkExample]:
        """Load and filter questions based on config."""
        if cfg.question_ids:
            return loader.load_by_ids(cfg.question_ids)

        # Load from specified domains or all, applying per-domain limits
        if cfg.domains:
            questions = []
            for domain in cfg.domains:
                domain_qs = loader.load_domain(domain)
                limit = cfg.domain_limits.get(domain) if cfg.domain_limits else None
                if limit is not None and limit < len(domain_qs):
                    domain_qs = domain_qs[:limit]
                questions.extend(domain_qs)
        else:
            questions = loader.load_all()

        # Shuffle if requested
        if cfg.shuffle:
            import random
            random.seed(42)
            random.shuffle(questions)

        # Limit count (global cap, applied after per-domain limits)
        if cfg.question_count and cfg.question_count < len(questions):
            questions = questions[:cfg.question_count]

        return questions

    async def _run_orchestrator(
        self,
        question: BenchmarkExample,
        team: Optional[Team],
        cfg: TestConfig,
    ) -> OrchestratorOutput:
        """Run the reasoning orchestrator on a question.

        Returns OrchestratorOutput with answer, tokens, and full domain data.
        """
        # Determine which orchestrator to use based on team config
        # Default: use AuditOrchestrator (v2) if available, else SocraticOrchestrator
        try:
            from regulus.audit.orchestrator import AuditOrchestrator
            from regulus.audit.types import AuditConfig, V2Response
            from regulus.reasoning.factory import get_provider as get_reasoning_provider
            from regulus.llm.openai import OpenAIClient

            # Use DeepSeek by default if key available, else OpenAI reasoning
            reasoning_model = "deepseek"
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")
            if not api_key:
                reasoning_model = "openai-reasoning"
                api_key = os.environ.get("OPENAI_API_KEY", "")

            reasoning_provider = get_reasoning_provider(reasoning_model, api_key=api_key)
            audit_llm = OpenAIClient(
                api_key=os.environ.get("OPENAI_API_KEY", ""),
                model="gpt-4o-mini",
            )

            orchestrator = AuditOrchestrator(
                reasoning_provider=reasoning_provider,
                audit_llm=audit_llm,
                config=AuditConfig(),
            )

            output: V2Response = await orchestrator.process_query(question.input)

            # Build agent_outputs from V2Response
            agent_outputs: dict = {
                "pipeline": "audit",
                "version": "2.0",
                "reasoning_model": output.reasoning_model,
                "trace_format": output.trace_format,
                "thinking": output.thinking[:50000] if output.thinking else None,
                "corrections": len(output.corrections),
                "audit_rounds": output.audit_rounds,
                "valid": output.valid,
                "domains": {},
            }
            if output.final_audit:
                for da in output.final_audit.domains:
                    agent_outputs["domains"][da.domain] = {
                        "present": da.present,
                        "weight": da.weight,
                        "gate_passed": da.gate_passed,
                        "issues": da.issues,
                        "segment_summary": da.segment_summary,
                        "e_exists": da.e_exists,
                        "r_exists": da.r_exists,
                        "rule_exists": da.rule_exists,
                        "s_exists": da.s_exists,
                        "d1_depth": da.d1_depth,
                        "d2_depth": da.d2_depth,
                        "d3_objectivity_pass": da.d3_objectivity_pass,
                        "d4_aristotle_ok": da.d4_aristotle_ok,
                        "d5_certainty_type": da.d5_certainty_type,
                        "d6_genuine": da.d6_genuine,
                    }

            return OrchestratorOutput(
                answer=output.answer or "",
                tokens_in=output.input_tokens,
                tokens_out=output.output_tokens,
                agent_outputs=agent_outputs,
            )
        except Exception:
            # Fallback: use SocraticOrchestrator
            from regulus.orchestrator import SocraticOrchestrator
            from regulus.llm.hybrid import HybridClient

            api_key = os.environ.get("OPENAI_API_KEY", "")
            llm_client = HybridClient(api_key=api_key)
            orchestrator = SocraticOrchestrator(llm_client=llm_client)

            output = await orchestrator.process_query(question.input)
            # Estimate tokens
            tokens_in = len(question.input) // 4 + 2000
            tokens_out = len(output.final_answer or "") // 4 + 3000

            # Build agent_outputs from MAS pipeline
            agent_outputs: dict = {
                "pipeline": "mas",
                "version": "1.0",
            }
            if hasattr(output, 'task_table_json') and output.task_table_json:
                try:
                    agent_outputs["task_table"] = json.loads(output.task_table_json)
                except (json.JSONDecodeError, TypeError):
                    agent_outputs["task_table"] = str(output.task_table_json)

            return OrchestratorOutput(
                answer=output.final_answer or "",
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                agent_outputs=agent_outputs,
            )

    def _judge_answer(
        self,
        judge: StrictJudge | SemanticJudge,
        model_answer: Optional[str],
        expected_answer: str,
        question: str,
    ) -> JudgmentResult:
        """Run judge evaluation."""
        if not model_answer:
            return JudgmentResult(
                verdict="wrong",
                confidence=1.0,
                explanation="No answer produced",
                judge_model="none",
                judged_at=datetime.now(timezone.utc).isoformat(),
            )

        if isinstance(judge, StrictJudge):
            return judge.evaluate(model_answer, expected_answer, question)
        else:
            return judge.evaluate(model_answer, expected_answer, question)

    @staticmethod
    def _guess_provider(team: Optional[Team]) -> str:
        """Guess LLM provider from team config for cost estimation."""
        if not team or not team.team_lead_config:
            return "openai"
        model = team.team_lead_config.get("model", "")
        if "claude" in model or "anthropic" in model:
            return "claude"
        return "openai"
