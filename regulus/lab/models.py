"""SQLite models for Lab module persistence."""

import sqlite3
import json
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional


class RunStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Result:
    """Single question result."""
    id: int = 0
    step_id: int = 0
    question: str = ""
    expected: str = ""
    answer: Optional[str] = None
    valid: bool = False
    correct: Optional[bool] = None
    informative: Optional[bool] = None
    judge_reason: Optional[str] = None
    failure_reason: Optional[str] = None
    corrections: int = 0
    time_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def is_passed(self) -> bool:
        """Result passes if it is valid and judged correct."""
        return self.valid and self.correct is True


@dataclass
class Step:
    """A step (chunk) of questions in a run."""
    id: int = 0
    run_id: int = 0
    step_number: int = 0
    status: StepStatus = StepStatus.PENDING
    questions_start: int = 0
    questions_end: int = 0
    valid_count: int = 0
    correct_count: int = 0
    total_time: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    results: list[Result] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["results"] = [r.to_dict() for r in self.results]
        return d

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class Run:
    """A complete benchmark run with multiple steps."""
    id: int = 0
    name: str = ""
    dataset: str = "simpleqa"
    provider: str = "claude"
    total_questions: int = 0
    num_steps: int = 0
    concurrency: int = 5
    status: RunStatus = RunStatus.CREATED
    current_step: int = 0
    valid_count: int = 0
    correct_count: int = 0
    total_time: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    source_run_id: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""
    steps: list[Step] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["steps"] = [s.to_dict() for s in self.steps]
        return d

    @property
    def completed_questions(self) -> int:
        return sum(
            s.questions_end - s.questions_start
            for s in self.steps
            if s.status == StepStatus.COMPLETED
        )

    @property
    def progress_percent(self) -> float:
        if self.total_questions == 0:
            return 0.0
        return (self.completed_questions / self.total_questions) * 100

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def avg_input_tokens_per_question(self) -> float:
        if self.completed_questions == 0:
            return 0.0
        return self.input_tokens / self.completed_questions

    @property
    def avg_output_tokens_per_question(self) -> float:
        if self.completed_questions == 0:
            return 0.0
        return self.output_tokens / self.completed_questions


class LabDB:
    """SQLite database for Lab persistence."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "data" / "lab.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                dataset TEXT NOT NULL DEFAULT 'simpleqa',
                provider TEXT NOT NULL DEFAULT 'claude',
                total_questions INTEGER NOT NULL,
                num_steps INTEGER NOT NULL,
                concurrency INTEGER NOT NULL DEFAULT 5,
                status TEXT NOT NULL DEFAULT 'created',
                current_step INTEGER NOT NULL DEFAULT 0,
                valid_count INTEGER NOT NULL DEFAULT 0,
                correct_count INTEGER NOT NULL DEFAULT 0,
                total_time REAL NOT NULL DEFAULT 0.0,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                step_number INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                questions_start INTEGER NOT NULL,
                questions_end INTEGER NOT NULL,
                valid_count INTEGER NOT NULL DEFAULT 0,
                correct_count INTEGER NOT NULL DEFAULT 0,
                total_time REAL NOT NULL DEFAULT 0.0,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                started_at TEXT,
                completed_at TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                step_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                expected TEXT NOT NULL,
                answer TEXT,
                valid INTEGER NOT NULL DEFAULT 0,
                correct INTEGER,
                informative INTEGER,
                judge_reason TEXT,
                corrections INTEGER NOT NULL DEFAULT 0,
                time_seconds REAL NOT NULL DEFAULT 0.0,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (step_id) REFERENCES steps(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_steps_run_id ON steps(run_id);
            CREATE INDEX IF NOT EXISTS idx_results_step_id ON results(step_id);
        """)

        # Migration: add token columns if they don't exist
        try:
            conn.execute("ALTER TABLE runs ADD COLUMN input_tokens INTEGER NOT NULL DEFAULT 0")
        except:
            pass
        try:
            conn.execute("ALTER TABLE runs ADD COLUMN output_tokens INTEGER NOT NULL DEFAULT 0")
        except:
            pass
        try:
            conn.execute("ALTER TABLE steps ADD COLUMN input_tokens INTEGER NOT NULL DEFAULT 0")
        except:
            pass
        try:
            conn.execute("ALTER TABLE steps ADD COLUMN output_tokens INTEGER NOT NULL DEFAULT 0")
        except:
            pass
        try:
            conn.execute("ALTER TABLE results ADD COLUMN input_tokens INTEGER NOT NULL DEFAULT 0")
        except:
            pass
        try:
            conn.execute("ALTER TABLE results ADD COLUMN output_tokens INTEGER NOT NULL DEFAULT 0")
        except:
            pass
        try:
            conn.execute("ALTER TABLE results ADD COLUMN failure_reason TEXT")
        except:
            pass
        try:
            conn.execute("ALTER TABLE runs ADD COLUMN source_run_id INTEGER")
        except:
            pass
        conn.commit()
        conn.close()

    def create_run(
        self,
        name: str,
        total_questions: int,
        num_steps: int,
        dataset: str = "simpleqa",
        provider: str = "claude",
        concurrency: int = 5,
        source_run_id: Optional[int] = None,
    ) -> Run:
        """Create a new run with steps."""
        # Cap num_steps at total_questions (1 question per step max)
        num_steps = min(max(1, num_steps), total_questions)

        now = datetime.utcnow().isoformat()
        conn = self._get_conn()
        cursor = conn.cursor()

        # Create run
        cursor.execute("""
            INSERT INTO runs (name, dataset, provider, total_questions, num_steps,
                              concurrency, status, current_step, source_run_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
        """, (name, dataset, provider, total_questions, num_steps, concurrency,
              RunStatus.CREATED.value, source_run_id, now, now))
        run_id = cursor.lastrowid

        # Calculate questions per step
        questions_per_step = total_questions // num_steps
        remainder = total_questions % num_steps

        # Create steps
        start = 0
        for i in range(num_steps):
            # Distribute remainder across first steps
            end = start + questions_per_step + (1 if i < remainder else 0)
            cursor.execute("""
                INSERT INTO steps (run_id, step_number, status, questions_start, questions_end)
                VALUES (?, ?, ?, ?, ?)
            """, (run_id, i + 1, StepStatus.PENDING.value, start, end))
            start = end

        conn.commit()
        conn.close()

        return self.get_run(run_id)

    def get_run(self, run_id: int) -> Optional[Run]:
        """Get a run with all its steps and results."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        run = Run(
            id=row["id"],
            name=row["name"],
            dataset=row["dataset"],
            provider=row["provider"],
            total_questions=row["total_questions"],
            num_steps=row["num_steps"],
            concurrency=row["concurrency"],
            status=RunStatus(row["status"]),
            current_step=row["current_step"],
            valid_count=row["valid_count"],
            correct_count=row["correct_count"],
            total_time=row["total_time"],
            input_tokens=row["input_tokens"] if "input_tokens" in row.keys() else 0,
            output_tokens=row["output_tokens"] if "output_tokens" in row.keys() else 0,
            source_run_id=row["source_run_id"] if "source_run_id" in row.keys() else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

        # Load steps
        cursor.execute(
            "SELECT * FROM steps WHERE run_id = ? ORDER BY step_number",
            (run_id,)
        )
        for step_row in cursor.fetchall():
            step = Step(
                id=step_row["id"],
                run_id=step_row["run_id"],
                step_number=step_row["step_number"],
                status=StepStatus(step_row["status"]),
                questions_start=step_row["questions_start"],
                questions_end=step_row["questions_end"],
                valid_count=step_row["valid_count"],
                correct_count=step_row["correct_count"],
                total_time=step_row["total_time"],
                input_tokens=step_row["input_tokens"] if "input_tokens" in step_row.keys() else 0,
                output_tokens=step_row["output_tokens"] if "output_tokens" in step_row.keys() else 0,
                started_at=step_row["started_at"],
                completed_at=step_row["completed_at"],
            )

            # Load results for this step
            cursor.execute(
                "SELECT * FROM results WHERE step_id = ? ORDER BY id",
                (step.id,)
            )
            for res_row in cursor.fetchall():
                step.results.append(self._row_to_result(res_row))

            run.steps.append(step)

        conn.close()
        return run

    def list_runs(self, limit: int = 50) -> list[Run]:
        """List recent runs (without full results)."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        runs = []
        for row in cursor.fetchall():
            keys = row.keys()
            runs.append(Run(
                id=row["id"],
                name=row["name"],
                dataset=row["dataset"],
                provider=row["provider"],
                total_questions=row["total_questions"],
                num_steps=row["num_steps"],
                concurrency=row["concurrency"],
                status=RunStatus(row["status"]),
                current_step=row["current_step"],
                valid_count=row["valid_count"],
                correct_count=row["correct_count"],
                total_time=row["total_time"],
                input_tokens=row["input_tokens"] if "input_tokens" in keys else 0,
                output_tokens=row["output_tokens"] if "output_tokens" in keys else 0,
                source_run_id=row["source_run_id"] if "source_run_id" in keys else None,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            ))

        conn.close()
        return runs

    def update_run_status(self, run_id: int, status: RunStatus, current_step: int = None):
        """Update run status."""
        conn = self._get_conn()
        now = datetime.utcnow().isoformat()

        if current_step is not None:
            conn.execute(
                "UPDATE runs SET status = ?, current_step = ?, updated_at = ? WHERE id = ?",
                (status.value, current_step, now, run_id)
            )
        else:
            conn.execute(
                "UPDATE runs SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, now, run_id)
            )

        conn.commit()
        conn.close()

    def update_run_stats(
        self,
        run_id: int,
        valid_count: int,
        correct_count: int,
        total_time: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ):
        """Update run aggregate stats."""
        conn = self._get_conn()
        now = datetime.utcnow().isoformat()
        conn.execute(
            """UPDATE runs SET valid_count = ?, correct_count = ?, total_time = ?,
               input_tokens = ?, output_tokens = ?, updated_at = ? WHERE id = ?""",
            (valid_count, correct_count, total_time, input_tokens, output_tokens, now, run_id)
        )
        conn.commit()
        conn.close()

    def update_step_status(self, step_id: int, status: StepStatus):
        """Update step status."""
        conn = self._get_conn()
        now = datetime.utcnow().isoformat()

        if status == StepStatus.RUNNING:
            conn.execute(
                "UPDATE steps SET status = ?, started_at = ? WHERE id = ?",
                (status.value, now, step_id)
            )
        elif status == StepStatus.COMPLETED:
            conn.execute(
                "UPDATE steps SET status = ?, completed_at = ? WHERE id = ?",
                (status.value, now, step_id)
            )
        else:
            conn.execute(
                "UPDATE steps SET status = ? WHERE id = ?",
                (status.value, step_id)
            )

        conn.commit()
        conn.close()

    def update_step_stats(
        self,
        step_id: int,
        valid_count: int,
        correct_count: int,
        total_time: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ):
        """Update step stats."""
        conn = self._get_conn()
        conn.execute(
            """UPDATE steps SET valid_count = ?, correct_count = ?, total_time = ?,
               input_tokens = ?, output_tokens = ? WHERE id = ?""",
            (valid_count, correct_count, total_time, input_tokens, output_tokens, step_id)
        )
        conn.commit()
        conn.close()

    def _row_to_result(self, row) -> Result:
        """Convert a database row to a Result object."""
        keys = row.keys()
        return Result(
            id=row["id"],
            step_id=row["step_id"],
            question=row["question"],
            expected=row["expected"],
            answer=row["answer"],
            valid=bool(row["valid"]),
            correct=bool(row["correct"]) if row["correct"] is not None else None,
            informative=bool(row["informative"]) if row["informative"] is not None else None,
            judge_reason=row["judge_reason"],
            failure_reason=row["failure_reason"] if "failure_reason" in keys else None,
            corrections=row["corrections"],
            time_seconds=row["time_seconds"],
            input_tokens=row["input_tokens"] if "input_tokens" in keys else 0,
            output_tokens=row["output_tokens"] if "output_tokens" in keys else 0,
            created_at=row["created_at"],
        )

    def add_result(self, step_id: int, result: Result) -> int:
        """Add a result to a step."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT INTO results (step_id, question, expected, answer, valid, correct,
                                 informative, judge_reason, failure_reason, corrections,
                                 time_seconds, input_tokens, output_tokens, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            step_id,
            result.question,
            result.expected,
            result.answer,
            int(result.valid),
            int(result.correct) if result.correct is not None else None,
            int(result.informative) if result.informative is not None else None,
            result.judge_reason,
            result.failure_reason,
            result.corrections,
            result.time_seconds,
            result.input_tokens,
            result.output_tokens,
            now,
        ))

        result_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return result_id

    def get_step_results(self, step_id: int) -> list[Result]:
        """Get all results for a step."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM results WHERE step_id = ? ORDER BY id",
            (step_id,)
        )
        results = [self._row_to_result(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_all_results(self, run_id: int) -> list[Result]:
        """Get all results for a run across all steps."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.* FROM results r
            JOIN steps s ON r.step_id = s.id
            WHERE s.run_id = ?
            ORDER BY r.id
        """, (run_id,))
        results = [self._row_to_result(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_run_results_filtered(self, run_id: int, passed: Optional[bool] = None) -> list[Result]:
        """Get results for a run, optionally filtered by pass/fail status."""
        all_results = self.get_all_results(run_id)
        if passed is None:
            return all_results
        return [r for r in all_results if r.is_passed == passed]

    def delete_run(self, run_id: int):
        """Delete a run and all its data."""
        conn = self._get_conn()
        # SQLite cascade should handle steps and results
        conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        conn.commit()
        conn.close()

    def update_run_concurrency(self, run_id: int, concurrency: int):
        """Update run concurrency setting."""
        conn = self._get_conn()
        now = datetime.utcnow().isoformat()
        conn.execute(
            "UPDATE runs SET concurrency = ?, updated_at = ? WHERE id = ?",
            (concurrency, now, run_id)
        )
        conn.commit()
        conn.close()

    def resplit_pending_steps(self, run_id: int, new_num_steps: int) -> Run:
        """
        Re-split remaining (pending) questions into a new number of steps.
        Completed steps are preserved.
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # Get current run
        run = self.get_run(run_id)
        if not run:
            conn.close()
            raise ValueError(f"Run {run_id} not found")

        # Find completed and pending steps
        completed_steps = [s for s in run.steps if s.status == StepStatus.COMPLETED]
        pending_steps = [s for s in run.steps if s.status == StepStatus.PENDING]

        if not pending_steps:
            conn.close()
            return run  # Nothing to resplit

        # Calculate remaining questions
        if completed_steps:
            questions_done = max(s.questions_end for s in completed_steps)
        else:
            questions_done = 0

        remaining_questions = run.total_questions - questions_done

        # Cap new_num_steps
        new_num_steps = min(max(1, new_num_steps), remaining_questions)

        # Delete pending steps
        for step in pending_steps:
            cursor.execute("DELETE FROM steps WHERE id = ?", (step.id,))

        # Calculate new step numbers (continue from last completed)
        last_step_num = max((s.step_number for s in completed_steps), default=0)

        # Create new pending steps
        questions_per_step = remaining_questions // new_num_steps
        remainder = remaining_questions % new_num_steps

        start = questions_done
        for i in range(new_num_steps):
            end = start + questions_per_step + (1 if i < remainder else 0)
            cursor.execute("""
                INSERT INTO steps (run_id, step_number, status, questions_start, questions_end)
                VALUES (?, ?, ?, ?, ?)
            """, (run_id, last_step_num + i + 1, StepStatus.PENDING.value, start, end))
            start = end

        # Update run's num_steps to reflect total
        total_steps = len(completed_steps) + new_num_steps
        now = datetime.utcnow().isoformat()
        cursor.execute(
            "UPDATE runs SET num_steps = ?, updated_at = ? WHERE id = ?",
            (total_steps, now, run_id)
        )

        conn.commit()
        conn.close()

        return self.get_run(run_id)

    def get_step(self, step_id: int) -> Optional[Step]:
        """Get a single step with its results."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM steps WHERE id = ?", (step_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        step = Step(
            id=row["id"],
            run_id=row["run_id"],
            step_number=row["step_number"],
            status=StepStatus(row["status"]),
            questions_start=row["questions_start"],
            questions_end=row["questions_end"],
            valid_count=row["valid_count"],
            correct_count=row["correct_count"],
            total_time=row["total_time"],
            input_tokens=row["input_tokens"] if "input_tokens" in row.keys() else 0,
            output_tokens=row["output_tokens"] if "output_tokens" in row.keys() else 0,
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )

        cursor.execute(
            "SELECT * FROM results WHERE step_id = ? ORDER BY id",
            (step_id,)
        )
        for res_row in cursor.fetchall():
            step.results.append(self._row_to_result(res_row))

        conn.close()
        return step
