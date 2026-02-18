"""
Lab v2 models — Teams, TestConfigs, TestRuns, QuestionResults.

Uses raw sqlite3 + dataclasses (same pattern as regulus/lab/models.py).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Model defaults & limits (used by ModelSettings cascade resolver)
# ---------------------------------------------------------------------------

MODEL_DEFAULTS: dict[str, dict] = {
    "opus-4.6":    {"context_window": 200000, "max_tokens": 64000, "thinking_enabled": True,  "thinking_budget": 10000, "interleaved_thinking": True,  "temperature": 1.0},
    "sonnet-4.5":  {"context_window": 200000, "max_tokens": 64000, "thinking_enabled": True,  "thinking_budget": 10000, "interleaved_thinking": True,  "temperature": 1.0},
    "haiku-4.5":   {"context_window": 200000, "max_tokens": 64000, "thinking_enabled": True,  "thinking_budget": 10000, "interleaved_thinking": False, "temperature": 1.0},
    "gpt-4o":      {"context_window": 128000, "max_tokens": 16384, "thinking_enabled": False, "thinking_budget": 0,     "interleaved_thinking": False, "temperature": 1.0},
    "o3-mini":     {"context_window": 128000, "max_tokens": 65536, "thinking_enabled": True,  "thinking_budget": 32000, "interleaved_thinking": False, "temperature": 1.0},
    "deepseek-r1": {"context_window": 64000,  "max_tokens": 32000, "thinking_enabled": True,  "thinking_budget": 16000, "interleaved_thinking": False, "temperature": 1.0},
}

MODEL_LIMITS: dict[str, dict] = {
    "opus-4.6":    {"name": "Claude Opus 4.6",  "maxContext": 200000, "maxOutput": 64000, "thinking": True, "interleaved": True,  "inputCost": 5, "outputCost": 25},
    "sonnet-4.5":  {"name": "Claude Sonnet 4.5", "maxContext": 200000, "maxOutput": 64000, "thinking": True, "interleaved": True,  "inputCost": 3, "outputCost": 15},
    "haiku-4.5":   {"name": "Claude Haiku 4.5",  "maxContext": 200000, "maxOutput": 64000, "thinking": True, "interleaved": True,  "inputCost": 1, "outputCost": 5},
    "gpt-4o":      {"name": "GPT-4o",            "maxContext": 128000, "maxOutput": 16384, "thinking": False, "interleaved": False, "inputCost": 2.5, "outputCost": 10},
    "o3-mini":     {"name": "o3-mini",            "maxContext": 128000, "maxOutput": 100000, "thinking": True, "interleaved": False, "inputCost": 1.1, "outputCost": 4.4},
    "deepseek-r1": {"name": "DeepSeek R1",       "maxContext": 64000,  "maxOutput": 32000, "thinking": True, "interleaved": False, "inputCost": 0.55, "outputCost": 2.19},
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Team:
    id: str = ""
    name: str = ""
    description: str = ""
    is_default: bool = False
    created_at: str = ""
    updated_at: str = ""
    team_lead_config: dict = field(default_factory=dict)
    agent_configs: dict = field(default_factory=dict)  # {d1: {...}, d2: {...}, ...}

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TestConfig:
    __test__ = False  # Not a pytest test class
    id: str = ""
    name: str = ""
    description: str = ""
    created_at: str = ""
    benchmark: str = "bbeh"
    domains: list[str] = field(default_factory=list)
    domain_limits: dict[str, int] = field(default_factory=dict)  # {domain: take_count}
    question_count: Optional[int] = None  # None = all
    question_ids: list[str] = field(default_factory=list)
    shuffle: bool = False
    questions_per_team: int = 4
    steps_count: int = 1
    team_id: str = ""
    auto_rotate_teams: bool = True
    judge_config: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParadigmInstructionSet:
    id: str = ""
    paradigm: str = ""         # "mathematical", "logical", etc.
    version: str = ""          # "v1", "v2.1"
    name: str = ""             # "Mathematical Strict v2"
    description: str = ""
    is_default: bool = False   # Default set for this paradigm
    created_at: str = ""
    updated_at: str = ""
    instructions: dict = field(default_factory=dict)  # {"team_lead": "...", "d1": "...", ...}

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TestRun:
    __test__ = False  # Not a pytest test class
    id: str = ""
    config_id: str = ""
    status: str = "pending"
    current_question_index: int = 0
    total_questions: int = 0
    current_team_index: int = 0
    current_step: int = 0
    started_at: Optional[str] = None
    paused_at: Optional[str] = None
    completed_at: Optional[str] = None
    teams_used: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QuestionResult:
    id: str = ""
    run_id: str = ""
    question_index: int = 0
    question_id: str = ""
    domain: str = ""
    input_text: str = ""
    team_index: int = 0
    status: str = "pending"
    agent_outputs: dict = field(default_factory=dict)
    final_answer: Optional[str] = None
    judgment_verdict: Optional[str] = None
    judgment_confidence: Optional[float] = None
    judgment_explanation: Optional[str] = None
    judged_at: Optional[str] = None
    total_time_ms: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    estimated_cost: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParadigmConfig:
    """A paradigm configuration for question classification and team routing."""
    id: str = ""              # e.g. "base", "compute"
    name: str = ""            # e.g. "BASE", "COMPUTE"
    label: str = ""           # e.g. "Default", "Computation"
    color: str = "#64748b"
    description: str = ""
    signals: list[str] = field(default_factory=list)
    active_roles: list[str] = field(default_factory=list)
    active_subprocesses: list[str] = field(default_factory=list)
    role_models: dict[str, str] = field(default_factory=dict)    # {role_id: model_id}
    role_instructions: dict[str, str] = field(default_factory=dict)  # {role_id: text}
    instruction_set_id: str = "default"  # links to instructions/{id}/ directory
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BenchmarkIndex:
    benchmark_id: str = ""
    status: str = "pending"  # pending, indexing, ready, error
    total_questions: int = 0
    domains: list[str] = field(default_factory=list)
    indexed_at: Optional[str] = None
    error_message: Optional[str] = None
    loader_version: str = ""


@dataclass
class BenchmarkQuestion:
    id: str = ""              # "{benchmark}:{question_id}"
    benchmark_id: str = ""
    question_id: str = ""     # Original ID from loader
    domain: str = ""
    input: str = ""           # Full question text
    target: str = ""          # Full expected answer
    target_hash: str = ""     # SHA256[:16] of target
    difficulty: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    metadata: dict = field(default_factory=dict)
    # Aggregated stats (updated after each attempt)
    total_attempts: int = 0
    correct_count: int = 0
    wrong_count: int = 0
    last_attempt_at: Optional[str] = None
    last_result: Optional[str] = None  # "correct" | "wrong"

    @property
    def input_preview(self) -> str:
        return self.input[:200]

    @property
    def target_short(self) -> str:
        return self.target[:100]

    @property
    def accuracy(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return self.correct_count / self.total_attempts

    @property
    def status(self) -> str:
        if self.total_attempts == 0:
            return "new"
        elif self.last_result == "correct":
            return "passed"
        else:
            return "failed"


@dataclass
class QuestionAttempt:
    id: str = ""
    question_id: str = ""      # FK benchmark_questions.id
    run_id: str = ""           # FK test_runs.id
    team_id: str = ""
    model_answer: str = ""
    judgment: str = ""         # "correct" | "wrong" | "partial"
    confidence: float = 0.0
    reasoning_log: dict = field(default_factory=dict)
    paradigm_used: Optional[str] = None
    time_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    attempted_at: str = ""
    analysis: Optional[str] = None
    failure_category: Optional[str] = None


@dataclass
class Analysis:
    id: str = ""
    question_result_id: str = ""
    status: str = "pending"  # pending, running, completed, error
    failure_category: Optional[str] = None
    root_cause: Optional[str] = None
    summary: Optional[str] = None
    recommendations: list[str] = field(default_factory=list)
    raw_output: Optional[str] = None
    model_used: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    created_at: str = ""
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ModelSettings:
    id: str = ""
    paradigm_id: str = ""    # "" = global
    role_id: str = ""        # "" = all roles
    model_id: str = ""
    context_window: int = 0  # 0 = use default
    max_tokens: int = 0
    thinking_enabled: bool = True
    thinking_budget: int = 0
    interleaved_thinking: bool = False
    temperature: float = 1.0
    created_at: str = ""
    updated_at: str = ""


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


class LabNewDB:
    """SQLite database for Lab v2 tables (teams, test_configs, etc.)."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent.parent / "data" / "lab_v2.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._create_tables()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _create_tables(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS teams (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                is_default INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                team_lead_config TEXT NOT NULL DEFAULT '{}',
                agent_configs TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS test_configs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                benchmark TEXT NOT NULL DEFAULT 'bbeh',
                domains TEXT NOT NULL DEFAULT '[]',
                domain_limits TEXT NOT NULL DEFAULT '{}',
                question_count INTEGER,
                question_ids TEXT NOT NULL DEFAULT '[]',
                shuffle INTEGER NOT NULL DEFAULT 0,
                questions_per_team INTEGER NOT NULL DEFAULT 4,
                steps_count INTEGER NOT NULL DEFAULT 1,
                team_id TEXT NOT NULL DEFAULT '',
                auto_rotate_teams INTEGER NOT NULL DEFAULT 1,
                judge_config TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS test_runs (
                id TEXT PRIMARY KEY,
                config_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                current_question_index INTEGER NOT NULL DEFAULT 0,
                total_questions INTEGER NOT NULL DEFAULT 0,
                current_team_index INTEGER NOT NULL DEFAULT 0,
                current_step INTEGER NOT NULL DEFAULT 0,
                started_at TEXT,
                paused_at TEXT,
                completed_at TEXT,
                teams_used TEXT NOT NULL DEFAULT '[]',
                FOREIGN KEY (config_id) REFERENCES test_configs(id)
            );

            CREATE TABLE IF NOT EXISTS question_results (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                question_index INTEGER NOT NULL,
                question_id TEXT NOT NULL,
                domain TEXT NOT NULL DEFAULT '',
                input_text TEXT NOT NULL DEFAULT '',
                team_index INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                agent_outputs TEXT NOT NULL DEFAULT '{}',
                final_answer TEXT,
                judgment_verdict TEXT,
                judgment_confidence REAL,
                judgment_explanation TEXT,
                judged_at TEXT,
                total_time_ms INTEGER NOT NULL DEFAULT 0,
                total_tokens_in INTEGER NOT NULL DEFAULT 0,
                total_tokens_out INTEGER NOT NULL DEFAULT 0,
                estimated_cost REAL NOT NULL DEFAULT 0.0,
                FOREIGN KEY (run_id) REFERENCES test_runs(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_test_runs_config_id ON test_runs(config_id);
            CREATE INDEX IF NOT EXISTS idx_question_results_run_id ON question_results(run_id);

            CREATE TABLE IF NOT EXISTS paradigm_instruction_sets (
                id TEXT PRIMARY KEY,
                paradigm TEXT NOT NULL,
                version TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                is_default INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                instructions TEXT NOT NULL DEFAULT '{}',
                UNIQUE(paradigm, version)
            );

            CREATE TABLE IF NOT EXISTS team_paradigm_configs (
                team_id TEXT NOT NULL,
                paradigm TEXT NOT NULL,
                instruction_set_id TEXT NOT NULL,
                PRIMARY KEY (team_id, paradigm),
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
                FOREIGN KEY (instruction_set_id) REFERENCES paradigm_instruction_sets(id)
            );

            CREATE TABLE IF NOT EXISTS paradigm_configs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                color TEXT NOT NULL DEFAULT '#64748b',
                description TEXT NOT NULL DEFAULT '',
                signals_json TEXT NOT NULL DEFAULT '[]',
                active_roles_json TEXT NOT NULL DEFAULT '[]',
                active_subprocesses_json TEXT NOT NULL DEFAULT '[]',
                role_models_json TEXT NOT NULL DEFAULT '{}',
                role_instructions_json TEXT NOT NULL DEFAULT '{}',
                instruction_set_id TEXT NOT NULL DEFAULT 'default',
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS benchmark_index (
                benchmark_id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'pending',
                total_questions INTEGER NOT NULL DEFAULT 0,
                domains_json TEXT NOT NULL DEFAULT '[]',
                indexed_at TEXT,
                error_message TEXT,
                loader_version TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS benchmark_questions (
                id TEXT PRIMARY KEY,
                benchmark_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                input TEXT NOT NULL DEFAULT '',
                target TEXT NOT NULL DEFAULT '',
                target_hash TEXT NOT NULL DEFAULT '',
                difficulty TEXT,
                tags_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                total_attempts INTEGER NOT NULL DEFAULT 0,
                correct_count INTEGER NOT NULL DEFAULT 0,
                wrong_count INTEGER NOT NULL DEFAULT 0,
                last_attempt_at TEXT,
                last_result TEXT,
                FOREIGN KEY (benchmark_id) REFERENCES benchmark_index(benchmark_id)
            );

            CREATE TABLE IF NOT EXISTS question_attempts (
                id TEXT PRIMARY KEY,
                question_id TEXT NOT NULL,
                run_id TEXT NOT NULL DEFAULT '',
                team_id TEXT NOT NULL DEFAULT '',
                model_answer TEXT NOT NULL DEFAULT '',
                judgment TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0.0,
                reasoning_log TEXT NOT NULL DEFAULT '{}',
                paradigm_used TEXT,
                time_ms INTEGER NOT NULL DEFAULT 0,
                tokens_in INTEGER NOT NULL DEFAULT 0,
                tokens_out INTEGER NOT NULL DEFAULT 0,
                cost REAL NOT NULL DEFAULT 0.0,
                attempted_at TEXT NOT NULL DEFAULT '',
                analysis TEXT,
                failure_category TEXT,
                FOREIGN KEY (question_id) REFERENCES benchmark_questions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_bq_benchmark ON benchmark_questions(benchmark_id);
            CREATE INDEX IF NOT EXISTS idx_bq_domain ON benchmark_questions(benchmark_id, domain);
            CREATE INDEX IF NOT EXISTS idx_bq_status ON benchmark_questions(last_result);
            CREATE INDEX IF NOT EXISTS idx_attempts_question ON question_attempts(question_id);
            CREATE INDEX IF NOT EXISTS idx_attempts_run ON question_attempts(run_id);
            CREATE INDEX IF NOT EXISTS idx_question_results_question_id ON question_results(question_id);

            CREATE TABLE IF NOT EXISTS paradigm_role_instructions (
                paradigm TEXT NOT NULL,
                role TEXT NOT NULL,
                instruction_set_id TEXT NOT NULL DEFAULT 'default',
                PRIMARY KEY (paradigm, role)
            );

            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                question_result_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                failure_category TEXT,
                root_cause TEXT,
                summary TEXT,
                recommendations_json TEXT NOT NULL DEFAULT '[]',
                raw_output TEXT,
                model_used TEXT NOT NULL DEFAULT '',
                tokens_in INTEGER NOT NULL DEFAULT 0,
                tokens_out INTEGER NOT NULL DEFAULT 0,
                cost REAL NOT NULL DEFAULT 0.0,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                error_message TEXT,
                FOREIGN KEY (question_result_id) REFERENCES question_results(id)
            );
            CREATE INDEX IF NOT EXISTS idx_analyses_qr ON analyses(question_result_id);

            CREATE TABLE IF NOT EXISTS model_settings (
                id TEXT PRIMARY KEY,
                paradigm_id TEXT NOT NULL DEFAULT '',
                role_id TEXT NOT NULL DEFAULT '',
                model_id TEXT NOT NULL,
                context_window INTEGER NOT NULL DEFAULT 0,
                max_tokens INTEGER NOT NULL DEFAULT 0,
                thinking_enabled INTEGER NOT NULL DEFAULT 1,
                thinking_budget INTEGER NOT NULL DEFAULT 0,
                interleaved_thinking INTEGER NOT NULL DEFAULT 0,
                temperature REAL NOT NULL DEFAULT 1.0,
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT '',
                UNIQUE(paradigm_id, role_id, model_id)
            );
        """)
        # Migration: add domain_limits column if missing (pre-existing DBs)
        try:
            conn.execute("SELECT domain_limits FROM test_configs LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute(
                "ALTER TABLE test_configs ADD COLUMN domain_limits TEXT NOT NULL DEFAULT '{}'"
            )
        # Migration: benchmark_questions schema v2 (full text + stats)
        try:
            conn.execute("SELECT input FROM benchmark_questions LIMIT 1")
        except sqlite3.OperationalError:
            # Old schema had input_preview/target_short — migrate to full text + stats
            for col, defn in [
                ("input", "TEXT NOT NULL DEFAULT ''"),
                ("target", "TEXT NOT NULL DEFAULT ''"),
                ("difficulty", "TEXT"),
                ("tags_json", "TEXT NOT NULL DEFAULT '[]'"),
                ("created_at", "TEXT NOT NULL DEFAULT ''"),
                ("total_attempts", "INTEGER NOT NULL DEFAULT 0"),
                ("correct_count", "INTEGER NOT NULL DEFAULT 0"),
                ("wrong_count", "INTEGER NOT NULL DEFAULT 0"),
                ("last_attempt_at", "TEXT"),
                ("last_result", "TEXT"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE benchmark_questions ADD COLUMN {col} {defn}")
                except sqlite3.OperationalError:
                    pass  # Column already exists
            # Copy old preview data into new columns if present
            try:
                conn.execute(
                    "UPDATE benchmark_questions SET input = input_preview, target = target_short "
                    "WHERE input = '' AND input_preview != ''"
                )
            except sqlite3.OperationalError:
                pass
        # Migration: add instruction_set_id to paradigm_configs if missing
        try:
            conn.execute("SELECT instruction_set_id FROM paradigm_configs LIMIT 1")
        except sqlite3.OperationalError:
            try:
                conn.execute(
                    "ALTER TABLE paradigm_configs ADD COLUMN instruction_set_id TEXT NOT NULL DEFAULT 'default'"
                )
            except sqlite3.OperationalError:
                pass
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Team CRUD
    # ------------------------------------------------------------------

    def create_team(self, team: Team) -> Team:
        now = datetime.now(timezone.utc).isoformat()
        if not team.id:
            team.id = str(uuid.uuid4())
        team.created_at = now
        team.updated_at = now

        conn = self._get_conn()
        conn.execute(
            """INSERT INTO teams
               (id, name, description, is_default, created_at, updated_at,
                team_lead_config, agent_configs)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                team.id,
                team.name,
                team.description,
                int(team.is_default),
                team.created_at,
                team.updated_at,
                json.dumps(team.team_lead_config),
                json.dumps(team.agent_configs),
            ),
        )
        conn.commit()
        conn.close()
        return team

    def get_team(self, team_id: str) -> Optional[Team]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_team(row)

    def list_teams(self) -> list[Team]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM teams ORDER BY created_at DESC"
        ).fetchall()
        conn.close()
        return [self._row_to_team(r) for r in rows]

    def update_team(self, team: Team) -> Team:
        team.updated_at = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        conn.execute(
            """UPDATE teams SET
                name = ?, description = ?, is_default = ?, updated_at = ?,
                team_lead_config = ?, agent_configs = ?
               WHERE id = ?""",
            (
                team.name,
                team.description,
                int(team.is_default),
                team.updated_at,
                json.dumps(team.team_lead_config),
                json.dumps(team.agent_configs),
                team.id,
            ),
        )
        conn.commit()
        conn.close()
        return team

    def delete_team(self, team_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted

    def set_default_team(self, team_id: str) -> None:
        """Set one team as default, unsetting all others."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        conn.execute(
            "UPDATE teams SET is_default = 0, updated_at = ? WHERE is_default = 1",
            (now,),
        )
        conn.execute(
            "UPDATE teams SET is_default = 1, updated_at = ? WHERE id = ?",
            (now, team_id),
        )
        conn.commit()
        conn.close()

    def clone_team(self, team_id: str, new_name: str) -> Optional[Team]:
        """Clone an existing team with a new name."""
        original = self.get_team(team_id)
        if not original:
            return None

        clone = Team(
            name=new_name,
            description=f"Clone of {original.name}",
            is_default=False,
            team_lead_config=dict(original.team_lead_config),
            agent_configs=dict(original.agent_configs),
        )
        return self.create_team(clone)

    # ------------------------------------------------------------------
    # TestConfig CRUD
    # ------------------------------------------------------------------

    def create_test_config(self, cfg: TestConfig) -> TestConfig:
        now = datetime.now(timezone.utc).isoformat()
        if not cfg.id:
            cfg.id = str(uuid.uuid4())
        cfg.created_at = now

        conn = self._get_conn()
        conn.execute(
            """INSERT INTO test_configs
               (id, name, description, created_at, benchmark, domains,
                domain_limits, question_count, question_ids, shuffle,
                questions_per_team, steps_count, team_id, auto_rotate_teams,
                judge_config)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                cfg.id,
                cfg.name,
                cfg.description,
                cfg.created_at,
                cfg.benchmark,
                json.dumps(cfg.domains),
                json.dumps(cfg.domain_limits),
                cfg.question_count,
                json.dumps(cfg.question_ids),
                int(cfg.shuffle),
                cfg.questions_per_team,
                cfg.steps_count,
                cfg.team_id,
                int(cfg.auto_rotate_teams),
                json.dumps(cfg.judge_config),
            ),
        )
        conn.commit()
        conn.close()
        return cfg

    def get_test_config(self, config_id: str) -> Optional[TestConfig]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM test_configs WHERE id = ?", (config_id,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_test_config(row)

    def list_test_configs(self) -> list[TestConfig]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM test_configs ORDER BY created_at DESC"
        ).fetchall()
        conn.close()
        return [self._row_to_test_config(r) for r in rows]

    def update_test_config(self, cfg: TestConfig) -> TestConfig:
        conn = self._get_conn()
        conn.execute(
            """UPDATE test_configs SET
                name = ?, description = ?, benchmark = ?, domains = ?,
                domain_limits = ?, question_count = ?, question_ids = ?,
                shuffle = ?, questions_per_team = ?, steps_count = ?,
                team_id = ?, auto_rotate_teams = ?, judge_config = ?
               WHERE id = ?""",
            (
                cfg.name,
                cfg.description,
                cfg.benchmark,
                json.dumps(cfg.domains),
                json.dumps(cfg.domain_limits),
                cfg.question_count,
                json.dumps(cfg.question_ids),
                int(cfg.shuffle),
                cfg.questions_per_team,
                cfg.steps_count,
                cfg.team_id,
                int(cfg.auto_rotate_teams),
                json.dumps(cfg.judge_config),
                cfg.id,
            ),
        )
        conn.commit()
        conn.close()
        return cfg

    def delete_test_config(self, config_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM test_configs WHERE id = ?", (config_id,)
        )
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted

    # ------------------------------------------------------------------
    # ParadigmInstructionSet CRUD
    # ------------------------------------------------------------------

    def create_instruction_set(self, s: ParadigmInstructionSet) -> ParadigmInstructionSet:
        now = datetime.now(timezone.utc).isoformat()
        if not s.id:
            s.id = str(uuid.uuid4())
        s.created_at = now
        s.updated_at = now

        conn = self._get_conn()
        conn.execute(
            """INSERT INTO paradigm_instruction_sets
               (id, paradigm, version, name, description, is_default,
                created_at, updated_at, instructions)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                s.id,
                s.paradigm,
                s.version,
                s.name,
                s.description,
                int(s.is_default),
                s.created_at,
                s.updated_at,
                json.dumps(s.instructions),
            ),
        )
        conn.commit()
        conn.close()
        return s

    def get_instruction_set(self, set_id: str) -> Optional[ParadigmInstructionSet]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM paradigm_instruction_sets WHERE id = ?", (set_id,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_instruction_set(row)

    def list_instruction_sets(self, paradigm: Optional[str] = None) -> list[ParadigmInstructionSet]:
        conn = self._get_conn()
        if paradigm:
            rows = conn.execute(
                "SELECT * FROM paradigm_instruction_sets WHERE paradigm = ? ORDER BY created_at DESC",
                (paradigm,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM paradigm_instruction_sets ORDER BY created_at DESC"
            ).fetchall()
        conn.close()
        return [self._row_to_instruction_set(r) for r in rows]

    def update_instruction_set(self, s: ParadigmInstructionSet) -> ParadigmInstructionSet:
        s.updated_at = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        conn.execute(
            """UPDATE paradigm_instruction_sets SET
                name = ?, description = ?, is_default = ?, updated_at = ?,
                instructions = ?
               WHERE id = ?""",
            (
                s.name,
                s.description,
                int(s.is_default),
                s.updated_at,
                json.dumps(s.instructions),
                s.id,
            ),
        )
        conn.commit()
        conn.close()
        return s

    def delete_instruction_set(self, set_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM paradigm_instruction_sets WHERE id = ?", (set_id,)
        )
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted

    def set_default_instruction_set(self, set_id: str) -> None:
        """Set one instruction set as default, unsetting others for the same paradigm."""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        # Get the paradigm for this set
        row = conn.execute(
            "SELECT paradigm FROM paradigm_instruction_sets WHERE id = ?", (set_id,)
        ).fetchone()
        if row:
            paradigm = row["paradigm"]
            conn.execute(
                "UPDATE paradigm_instruction_sets SET is_default = 0, updated_at = ? WHERE paradigm = ? AND is_default = 1",
                (now, paradigm),
            )
            conn.execute(
                "UPDATE paradigm_instruction_sets SET is_default = 1, updated_at = ? WHERE id = ?",
                (now, set_id),
            )
        conn.commit()
        conn.close()

    def clone_instruction_set(
        self, set_id: str, new_version: str, new_name: str
    ) -> Optional[ParadigmInstructionSet]:
        """Clone an existing instruction set with a new version and name."""
        original = self.get_instruction_set(set_id)
        if not original:
            return None

        clone = ParadigmInstructionSet(
            paradigm=original.paradigm,
            version=new_version,
            name=new_name,
            description=f"Clone of {original.name}",
            is_default=False,
            instructions=dict(original.instructions),
        )
        return self.create_instruction_set(clone)

    # ------------------------------------------------------------------
    # Team Paradigm Config CRUD
    # ------------------------------------------------------------------

    def get_team_paradigm_configs(self, team_id: str) -> dict[str, str]:
        """Return {paradigm: instruction_set_id} for a team."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT paradigm, instruction_set_id FROM team_paradigm_configs WHERE team_id = ?",
            (team_id,),
        ).fetchall()
        conn.close()
        return {row["paradigm"]: row["instruction_set_id"] for row in rows}

    def set_team_paradigm_config(self, team_id: str, paradigm: str, set_id: str) -> None:
        """Set a single paradigm config for a team."""
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO team_paradigm_configs (team_id, paradigm, instruction_set_id) VALUES (?, ?, ?)",
            (team_id, paradigm, set_id),
        )
        conn.commit()
        conn.close()

    def set_team_paradigm_configs(self, team_id: str, configs: dict[str, str]) -> None:
        """Bulk set paradigm configs for a team (replaces all)."""
        conn = self._get_conn()
        conn.execute("DELETE FROM team_paradigm_configs WHERE team_id = ?", (team_id,))
        for paradigm, set_id in configs.items():
            conn.execute(
                "INSERT INTO team_paradigm_configs (team_id, paradigm, instruction_set_id) VALUES (?, ?, ?)",
                (team_id, paradigm, set_id),
            )
        conn.commit()
        conn.close()

    def delete_team_paradigm_config(self, team_id: str, paradigm: str) -> None:
        """Delete a single paradigm config for a team."""
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM team_paradigm_configs WHERE team_id = ? AND paradigm = ?",
            (team_id, paradigm),
        )
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # TestRun CRUD
    # ------------------------------------------------------------------

    def create_test_run(self, run: TestRun) -> TestRun:
        if not run.id:
            run.id = str(uuid.uuid4())

        conn = self._get_conn()
        conn.execute(
            """INSERT INTO test_runs
               (id, config_id, status, current_question_index, total_questions,
                current_team_index, current_step, started_at, paused_at,
                completed_at, teams_used)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.id,
                run.config_id,
                run.status,
                run.current_question_index,
                run.total_questions,
                run.current_team_index,
                run.current_step,
                run.started_at,
                run.paused_at,
                run.completed_at,
                json.dumps(run.teams_used),
            ),
        )
        conn.commit()
        conn.close()
        return run

    def get_test_run(self, run_id: str) -> Optional[TestRun]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM test_runs WHERE id = ?", (run_id,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_test_run(row)

    def list_test_runs(self, config_id: Optional[str] = None) -> list[TestRun]:
        conn = self._get_conn()
        if config_id:
            rows = conn.execute(
                "SELECT * FROM test_runs WHERE config_id = ? ORDER BY started_at DESC",
                (config_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM test_runs ORDER BY started_at DESC"
            ).fetchall()
        conn.close()
        return [self._row_to_test_run(r) for r in rows]

    def update_test_run_status(self, run_id: str, status: str, **kwargs) -> Optional[TestRun]:
        """Update run status and optional fields (started_at, paused_at, completed_at, etc.)."""
        conn = self._get_conn()
        sets = ["status = ?"]
        vals: list = [status]
        for col in (
            "current_question_index",
            "total_questions",
            "current_team_index",
            "current_step",
            "started_at",
            "paused_at",
            "completed_at",
        ):
            if col in kwargs:
                sets.append(f"{col} = ?")
                vals.append(kwargs[col])
        if "teams_used" in kwargs:
            sets.append("teams_used = ?")
            vals.append(json.dumps(kwargs["teams_used"]))

        vals.append(run_id)
        conn.execute(
            f"UPDATE test_runs SET {', '.join(sets)} WHERE id = ?", vals
        )
        conn.commit()
        conn.close()
        return self.get_test_run(run_id)

    # ------------------------------------------------------------------
    # QuestionResult CRUD
    # ------------------------------------------------------------------

    def create_question_result(self, result: QuestionResult) -> QuestionResult:
        if not result.id:
            result.id = str(uuid.uuid4())

        conn = self._get_conn()
        conn.execute(
            """INSERT INTO question_results
               (id, run_id, question_index, question_id, domain, input_text,
                team_index, status, agent_outputs, final_answer,
                judgment_verdict, judgment_confidence, judgment_explanation,
                judged_at, total_time_ms, total_tokens_in, total_tokens_out,
                estimated_cost)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.id,
                result.run_id,
                result.question_index,
                result.question_id,
                result.domain,
                result.input_text,
                result.team_index,
                result.status,
                json.dumps(result.agent_outputs),
                result.final_answer,
                result.judgment_verdict,
                result.judgment_confidence,
                result.judgment_explanation,
                result.judged_at,
                result.total_time_ms,
                result.total_tokens_in,
                result.total_tokens_out,
                result.estimated_cost,
            ),
        )
        conn.commit()
        conn.close()
        return result

    def update_question_result(self, result_id: str, **kwargs) -> Optional[QuestionResult]:
        """Update specific fields on a question result."""
        conn = self._get_conn()
        sets = []
        vals: list = []
        for col, val in kwargs.items():
            if col == "agent_outputs":
                sets.append("agent_outputs = ?")
                vals.append(json.dumps(val))
            else:
                sets.append(f"{col} = ?")
                vals.append(val)

        if not sets:
            conn.close()
            return self.get_question_result(result_id)

        vals.append(result_id)
        conn.execute(
            f"UPDATE question_results SET {', '.join(sets)} WHERE id = ?", vals
        )
        conn.commit()
        conn.close()
        return self.get_question_result(result_id)

    def get_question_result(self, result_id: str) -> Optional[QuestionResult]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM question_results WHERE id = ?", (result_id,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_question_result(row)

    def list_question_results(
        self, run_id: str, status: Optional[str] = None,
        domain: Optional[str] = None, team_index: Optional[int] = None,
        limit: int = 100, offset: int = 0,
    ) -> list[QuestionResult]:
        conn = self._get_conn()
        query = "SELECT * FROM question_results WHERE run_id = ?"
        params: list = [run_id]

        if status:
            query += " AND status = ?"
            params.append(status)
        if domain:
            query += " AND domain = ?"
            params.append(domain)
        if team_index is not None:
            query += " AND team_index = ?"
            params.append(team_index)

        query += " ORDER BY question_index LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [self._row_to_question_result(r) for r in rows]

    def count_question_results(self, run_id: str, status: Optional[str] = None) -> int:
        conn = self._get_conn()
        if status:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM question_results WHERE run_id = ? AND status = ?",
                (run_id, status),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM question_results WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        conn.close()
        return row["cnt"]

    def list_all_results(
        self,
        verdict: Optional[str] = None,
        domain: Optional[str] = None,
        run_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[QuestionResult]:
        """List results across all runs with optional filters."""
        conn = self._get_conn()
        query = "SELECT * FROM question_results WHERE 1=1"
        params: list = []
        if verdict:
            query += " AND judgment_verdict = ?"
            params.append(verdict)
        if domain:
            query += " AND domain = ?"
            params.append(domain)
        if run_id:
            query += " AND run_id = ?"
            params.append(run_id)
        query += " ORDER BY rowid DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [self._row_to_question_result(r) for r in rows]

    def count_all_results(
        self,
        verdict: Optional[str] = None,
        domain: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> int:
        """Count results across all runs."""
        conn = self._get_conn()
        query = "SELECT COUNT(*) as cnt FROM question_results WHERE 1=1"
        params: list = []
        if verdict:
            query += " AND judgment_verdict = ?"
            params.append(verdict)
        if domain:
            query += " AND domain = ?"
            params.append(domain)
        if run_id:
            query += " AND run_id = ?"
            params.append(run_id)
        row = conn.execute(query, params).fetchone()
        conn.close()
        return row["cnt"]

    def get_results_stats(
        self,
        verdict: Optional[str] = None,
        domain: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> dict:
        """Aggregate stats for results across all runs."""
        conn = self._get_conn()
        where = "WHERE 1=1"
        params: list = []
        if verdict:
            where += " AND judgment_verdict = ?"
            params.append(verdict)
        if domain:
            where += " AND domain = ?"
            params.append(domain)
        if run_id:
            where += " AND run_id = ?"
            params.append(run_id)

        row = conn.execute(
            f"""SELECT
                COUNT(*) as total,
                SUM(CASE WHEN judgment_verdict = 'correct' THEN 1 ELSE 0 END) as correct,
                SUM(CASE WHEN judgment_verdict = 'wrong' THEN 1 ELSE 0 END) as wrong,
                SUM(CASE WHEN judgment_verdict = 'partial' THEN 1 ELSE 0 END) as partial,
                SUM(CASE WHEN judgment_verdict = 'error' THEN 1 ELSE 0 END) as error,
                SUM(CASE WHEN judgment_verdict IS NULL THEN 1 ELSE 0 END) as pending
            FROM question_results {where}""",
            params,
        ).fetchone()

        domains_rows = conn.execute(
            f"SELECT DISTINCT domain FROM question_results {where} ORDER BY domain",
            params,
        ).fetchall()

        run_rows = conn.execute(
            f"SELECT DISTINCT run_id FROM question_results {where} ORDER BY run_id",
            params,
        ).fetchall()

        conn.close()
        return {
            "total": row["total"],
            "correct": row["correct"],
            "wrong": row["wrong"],
            "partial": row["partial"],
            "error": row["error"],
            "pending": row["pending"],
            "domains": [r["domain"] for r in domains_rows],
            "run_ids": [r["run_id"] for r in run_rows],
        }

    def get_domain_breakdown(self) -> list[dict]:
        """Per-domain correct/total breakdown across all results."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT domain,
                      COUNT(*) as total,
                      SUM(CASE WHEN judgment_verdict = 'correct' THEN 1 ELSE 0 END) as correct
               FROM question_results
               WHERE judgment_verdict IS NOT NULL
               GROUP BY domain ORDER BY domain"""
        ).fetchall()
        conn.close()
        return [
            {"domain": r["domain"], "total": r["total"], "correct": r["correct"]}
            for r in rows
        ]

    def get_results_tree(self) -> list[dict]:
        """Return hierarchical tree: participant → domain → question counts.

        Groups runs by participant name (from teams_used JSON), then
        aggregates per-domain stats for each participant group.
        """
        conn = self._get_conn()
        # Get all runs with their teams_used metadata
        runs = conn.execute(
            "SELECT id, teams_used FROM test_runs WHERE config_id IS NOT NULL"
        ).fetchall()

        # Build run_id → participant mapping
        run_participant: dict[str, str] = {}
        participant_meta: dict[str, dict] = {}
        for r in runs:
            teams = json.loads(r["teams_used"])
            if not teams:
                continue
            meta = teams[0]
            participant = meta.get("participant", "unknown")
            run_participant[r["id"]] = participant
            if participant not in participant_meta:
                participant_meta[participant] = {
                    "name": meta.get("name", participant).split(" - ")[0],
                    "run_ids": [],
                }
            participant_meta[participant]["run_ids"].append(r["id"])

        # Aggregate per-participant per-domain
        results: dict[str, dict[str, dict]] = {}
        for run_id, participant in run_participant.items():
            rows = conn.execute(
                """SELECT domain,
                          COUNT(*) as total,
                          SUM(CASE WHEN judgment_verdict = 'correct' THEN 1 ELSE 0 END) as correct,
                          SUM(CASE WHEN judgment_verdict = 'wrong' THEN 1 ELSE 0 END) as wrong
                   FROM question_results
                   WHERE run_id = ?
                   GROUP BY domain ORDER BY domain""",
                (run_id,),
            ).fetchall()
            if participant not in results:
                results[participant] = {}
            for row in rows:
                d = row["domain"]
                if d not in results[participant]:
                    results[participant][d] = {"total": 0, "correct": 0, "wrong": 0}
                results[participant][d]["total"] += row["total"]
                results[participant][d]["correct"] += row["correct"]
                results[participant][d]["wrong"] += row["wrong"]

        conn.close()

        # Build tree output
        tree = []
        for participant in sorted(results.keys()):
            meta = participant_meta.get(participant, {"name": participant, "run_ids": []})
            domains = results[participant]
            p_total = sum(d["total"] for d in domains.values())
            p_correct = sum(d["correct"] for d in domains.values())
            tree.append({
                "participant": participant,
                "name": meta["name"],
                "run_ids": meta["run_ids"],
                "total": p_total,
                "correct": p_correct,
                "wrong": p_total - p_correct,
                "accuracy": round(p_correct / p_total, 4) if p_total else 0.0,
                "domains": [
                    {
                        "domain": d,
                        "total": s["total"],
                        "correct": s["correct"],
                        "wrong": s["wrong"],
                        "accuracy": round(s["correct"] / s["total"], 4) if s["total"] else 0.0,
                    }
                    for d, s in sorted(domains.items())
                ],
            })
        return tree

    # ------------------------------------------------------------------
    # ParadigmConfig CRUD
    # ------------------------------------------------------------------

    def upsert_paradigm_config(self, cfg: ParadigmConfig) -> ParadigmConfig:
        now = datetime.now(timezone.utc).isoformat()
        if not cfg.created_at:
            cfg.created_at = now
        cfg.updated_at = now

        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO paradigm_configs
               (id, name, label, color, description,
                signals_json, active_roles_json, active_subprocesses_json,
                role_models_json, role_instructions_json,
                instruction_set_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                cfg.id,
                cfg.name,
                cfg.label,
                cfg.color,
                cfg.description,
                json.dumps(cfg.signals),
                json.dumps(cfg.active_roles),
                json.dumps(cfg.active_subprocesses),
                json.dumps(cfg.role_models),
                json.dumps(cfg.role_instructions),
                cfg.instruction_set_id,
                cfg.created_at,
                cfg.updated_at,
            ),
        )
        conn.commit()
        conn.close()
        return cfg

    def get_paradigm_config(self, config_id: str) -> Optional[ParadigmConfig]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM paradigm_configs WHERE id = ?", (config_id,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_paradigm_config(row)

    def list_paradigm_configs(self) -> list[ParadigmConfig]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM paradigm_configs ORDER BY rowid"
        ).fetchall()
        conn.close()
        return [self._row_to_paradigm_config(r) for r in rows]

    def delete_paradigm_config(self, config_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM paradigm_configs WHERE id = ?", (config_id,)
        )
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted

    def seed_default_paradigm_configs(self) -> int:
        """Seed default paradigm configs if table is empty. Returns count inserted."""
        conn = self._get_conn()
        count = conn.execute("SELECT COUNT(*) as cnt FROM paradigm_configs").fetchone()["cnt"]
        conn.close()
        if count > 0:
            return 0

        from regulus.api.routers.lab.paradigm_config import DEFAULT_PARADIGM_CONFIGS
        inserted = 0
        for cfg_data in DEFAULT_PARADIGM_CONFIGS:
            cfg = ParadigmConfig(**cfg_data)
            self.upsert_paradigm_config(cfg)
            inserted += 1
        return inserted

    # ------------------------------------------------------------------
    # BenchmarkIndex CRUD
    # ------------------------------------------------------------------

    def upsert_benchmark_index(self, idx: BenchmarkIndex) -> BenchmarkIndex:
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO benchmark_index
               (benchmark_id, status, total_questions, domains_json,
                indexed_at, error_message, loader_version)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                idx.benchmark_id,
                idx.status,
                idx.total_questions,
                json.dumps(idx.domains),
                idx.indexed_at,
                idx.error_message,
                idx.loader_version,
            ),
        )
        conn.commit()
        conn.close()
        return idx

    def get_benchmark_index(self, benchmark_id: str) -> Optional[BenchmarkIndex]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM benchmark_index WHERE benchmark_id = ?", (benchmark_id,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_benchmark_index(row)

    def list_benchmark_indexes(self) -> list[BenchmarkIndex]:
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM benchmark_index ORDER BY indexed_at DESC").fetchall()
        conn.close()
        return [self._row_to_benchmark_index(r) for r in rows]

    def bulk_insert_benchmark_questions(self, questions: list[BenchmarkQuestion]) -> int:
        if not questions:
            return 0
        conn = self._get_conn()
        rows = [
            (
                q.id,
                q.benchmark_id,
                q.question_id,
                q.domain,
                q.input,
                q.target,
                q.target_hash,
                q.difficulty,
                json.dumps(q.tags),
                q.created_at,
                json.dumps(q.metadata),
                q.total_attempts,
                q.correct_count,
                q.wrong_count,
                q.last_attempt_at,
                q.last_result,
            )
            for q in questions
        ]
        conn.executemany(
            """INSERT OR IGNORE INTO benchmark_questions
               (id, benchmark_id, question_id, domain, input, target,
                target_hash, difficulty, tags_json, created_at, metadata_json,
                total_attempts, correct_count, wrong_count,
                last_attempt_at, last_result)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.commit()
        inserted = conn.total_changes
        conn.close()
        return inserted

    def get_benchmark_domain_counts(self, benchmark_id: str) -> list[tuple[str, int]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT domain, COUNT(*) as cnt FROM benchmark_questions WHERE benchmark_id = ? GROUP BY domain ORDER BY domain",
            (benchmark_id,),
        ).fetchall()
        conn.close()
        return [(row["domain"], row["cnt"]) for row in rows]

    def count_benchmark_questions(self, benchmark_id: str, domain: Optional[str] = None) -> int:
        conn = self._get_conn()
        if domain:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM benchmark_questions WHERE benchmark_id = ? AND domain = ?",
                (benchmark_id, domain),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM benchmark_questions WHERE benchmark_id = ?",
                (benchmark_id,),
            ).fetchone()
        conn.close()
        return row["cnt"]

    def list_benchmark_questions(
        self,
        benchmark_id: str,
        domain: Optional[str] = None,
        status: Optional[str] = None,
        has_result: Optional[bool] = None,
        verdict: Optional[str] = None,
        min_attempts: Optional[int] = None,
        max_accuracy: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[BenchmarkQuestion]:
        conn = self._get_conn()
        query = "SELECT bq.* FROM benchmark_questions bq WHERE bq.benchmark_id = ?"
        params: list = [benchmark_id]

        if domain:
            query += " AND bq.domain = ?"
            params.append(domain)

        # Native status filter (uses aggregated columns)
        if status == "new":
            query += " AND bq.total_attempts = 0"
        elif status == "passed":
            query += " AND bq.last_result = 'correct'"
        elif status == "failed":
            query += " AND bq.last_result = 'wrong'"

        # Legacy JOIN-based filters (fallback)
        if has_result is True:
            query += " AND bq.total_attempts > 0"
        elif has_result is False:
            query += " AND bq.total_attempts = 0"

        if verdict:
            query += " AND EXISTS (SELECT 1 FROM question_results qr WHERE qr.question_id = bq.question_id AND qr.judgment_verdict = ?)"
            params.append(verdict)

        if min_attempts is not None:
            query += " AND bq.total_attempts >= ?"
            params.append(min_attempts)

        if max_accuracy is not None:
            query += " AND bq.total_attempts > 0 AND (CAST(bq.correct_count AS REAL) / bq.total_attempts) <= ?"
            params.append(max_accuracy)

        query += " ORDER BY bq.domain, bq.question_id LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [self._row_to_benchmark_question(r) for r in rows]

    def delete_benchmark_questions(self, benchmark_id: str) -> int:
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM benchmark_questions WHERE benchmark_id = ?", (benchmark_id,)
        )
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        return deleted

    def get_benchmark_question(self, question_id: str) -> Optional[BenchmarkQuestion]:
        """Get a single question by its composite id (benchmark:question_id)."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM benchmark_questions WHERE id = ?", (question_id,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_benchmark_question(row)

    def get_benchmark_domain_stats(self, benchmark_id: str) -> list[dict]:
        """Get enriched domain stats with attempted/correct/accuracy."""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT domain,
                      COUNT(*) as total,
                      SUM(CASE WHEN total_attempts > 0 THEN 1 ELSE 0 END) as attempted,
                      SUM(correct_count) as correct,
                      SUM(wrong_count) as wrong,
                      SUM(CASE WHEN total_attempts = 0 THEN 1 ELSE 0 END) as new_count,
                      SUM(CASE WHEN last_result = 'wrong' THEN 1 ELSE 0 END) as failed_count
               FROM benchmark_questions
               WHERE benchmark_id = ?
               GROUP BY domain ORDER BY domain""",
            (benchmark_id,),
        ).fetchall()
        conn.close()
        results = []
        for r in rows:
            attempted = r["attempted"]
            correct = r["correct"]
            accuracy = (correct / attempted) if attempted > 0 else 0.0
            results.append({
                "domain": r["domain"],
                "total": r["total"],
                "attempted": attempted,
                "correct": correct,
                "wrong": r["wrong"],
                "accuracy": round(accuracy, 4),
                "new_count": r["new_count"],
                "failed_count": r["failed_count"],
            })
        return results

    # ------------------------------------------------------------------
    # QuestionAttempt CRUD
    # ------------------------------------------------------------------

    def record_attempt(self, attempt: QuestionAttempt) -> QuestionAttempt:
        """Record an attempt and update the question's aggregated stats."""
        if not attempt.id:
            attempt.id = str(uuid.uuid4())
        if not attempt.attempted_at:
            attempt.attempted_at = datetime.now(timezone.utc).isoformat()

        conn = self._get_conn()
        # 1. Insert attempt
        conn.execute(
            """INSERT INTO question_attempts
               (id, question_id, run_id, team_id, model_answer, judgment,
                confidence, reasoning_log, paradigm_used, time_ms,
                tokens_in, tokens_out, cost, attempted_at,
                analysis, failure_category)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                attempt.id,
                attempt.question_id,
                attempt.run_id,
                attempt.team_id,
                attempt.model_answer,
                attempt.judgment,
                attempt.confidence,
                json.dumps(attempt.reasoning_log),
                attempt.paradigm_used,
                attempt.time_ms,
                attempt.tokens_in,
                attempt.tokens_out,
                attempt.cost,
                attempt.attempted_at,
                attempt.analysis,
                attempt.failure_category,
            ),
        )
        # 2. Update question aggregated stats
        if attempt.judgment == "correct":
            conn.execute(
                """UPDATE benchmark_questions SET
                    total_attempts = total_attempts + 1,
                    correct_count = correct_count + 1,
                    last_attempt_at = ?,
                    last_result = 'correct'
                   WHERE id = ?""",
                (attempt.attempted_at, attempt.question_id),
            )
        else:
            conn.execute(
                """UPDATE benchmark_questions SET
                    total_attempts = total_attempts + 1,
                    wrong_count = wrong_count + 1,
                    last_attempt_at = ?,
                    last_result = 'wrong'
                   WHERE id = ?""",
                (attempt.attempted_at, attempt.question_id),
            )
        conn.commit()
        conn.close()
        return attempt

    def get_question_attempts(
        self,
        question_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[QuestionAttempt]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM question_attempts WHERE question_id = ? ORDER BY attempted_at DESC LIMIT ? OFFSET ?",
            (question_id, limit, offset),
        ).fetchall()
        conn.close()
        return [self._row_to_question_attempt(r) for r in rows]

    def list_attempts_for_run(self, run_id: str) -> list[QuestionAttempt]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM question_attempts WHERE run_id = ? ORDER BY attempted_at",
            (run_id,),
        ).fetchall()
        conn.close()
        return [self._row_to_question_attempt(r) for r in rows]

    def update_attempt_analysis(
        self, attempt_id: str, analysis: str, failure_category: Optional[str] = None
    ) -> Optional[QuestionAttempt]:
        conn = self._get_conn()
        conn.execute(
            "UPDATE question_attempts SET analysis = ?, failure_category = ? WHERE id = ?",
            (analysis, failure_category, attempt_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM question_attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_question_attempt(row)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_team(row: sqlite3.Row) -> Team:
        return Team(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            is_default=bool(row["is_default"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            team_lead_config=json.loads(row["team_lead_config"]),
            agent_configs=json.loads(row["agent_configs"]),
        )

    @staticmethod
    def _row_to_test_config(row: sqlite3.Row) -> TestConfig:
        return TestConfig(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
            benchmark=row["benchmark"],
            domains=json.loads(row["domains"]),
            domain_limits=json.loads(row["domain_limits"]) if row["domain_limits"] else {},
            question_count=row["question_count"],
            question_ids=json.loads(row["question_ids"]),
            shuffle=bool(row["shuffle"]),
            questions_per_team=row["questions_per_team"],
            steps_count=row["steps_count"],
            team_id=row["team_id"],
            auto_rotate_teams=bool(row["auto_rotate_teams"]),
            judge_config=json.loads(row["judge_config"]),
        )

    @staticmethod
    def _row_to_test_run(row: sqlite3.Row) -> TestRun:
        return TestRun(
            id=row["id"],
            config_id=row["config_id"],
            status=row["status"],
            current_question_index=row["current_question_index"],
            total_questions=row["total_questions"],
            current_team_index=row["current_team_index"],
            current_step=row["current_step"],
            started_at=row["started_at"],
            paused_at=row["paused_at"],
            completed_at=row["completed_at"],
            teams_used=json.loads(row["teams_used"]),
        )

    @staticmethod
    def _row_to_instruction_set(row: sqlite3.Row) -> ParadigmInstructionSet:
        return ParadigmInstructionSet(
            id=row["id"],
            paradigm=row["paradigm"],
            version=row["version"],
            name=row["name"],
            description=row["description"],
            is_default=bool(row["is_default"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            instructions=json.loads(row["instructions"]),
        )

    @staticmethod
    def _row_to_question_result(row: sqlite3.Row) -> QuestionResult:
        return QuestionResult(
            id=row["id"],
            run_id=row["run_id"],
            question_index=row["question_index"],
            question_id=row["question_id"],
            domain=row["domain"],
            input_text=row["input_text"],
            team_index=row["team_index"],
            status=row["status"],
            agent_outputs=json.loads(row["agent_outputs"]),
            final_answer=row["final_answer"],
            judgment_verdict=row["judgment_verdict"],
            judgment_confidence=row["judgment_confidence"],
            judgment_explanation=row["judgment_explanation"],
            judged_at=row["judged_at"],
            total_time_ms=row["total_time_ms"],
            total_tokens_in=row["total_tokens_in"],
            total_tokens_out=row["total_tokens_out"],
            estimated_cost=row["estimated_cost"],
        )

    @staticmethod
    def _row_to_paradigm_config(row: sqlite3.Row) -> ParadigmConfig:
        return ParadigmConfig(
            id=row["id"],
            name=row["name"],
            label=row["label"],
            color=row["color"],
            description=row["description"],
            signals=json.loads(row["signals_json"]),
            active_roles=json.loads(row["active_roles_json"]),
            active_subprocesses=json.loads(row["active_subprocesses_json"]),
            role_models=json.loads(row["role_models_json"]),
            role_instructions=json.loads(row["role_instructions_json"]),
            instruction_set_id=row["instruction_set_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_benchmark_index(row: sqlite3.Row) -> BenchmarkIndex:
        return BenchmarkIndex(
            benchmark_id=row["benchmark_id"],
            status=row["status"],
            total_questions=row["total_questions"],
            domains=json.loads(row["domains_json"]),
            indexed_at=row["indexed_at"],
            error_message=row["error_message"],
            loader_version=row["loader_version"],
        )

    @staticmethod
    def _row_to_benchmark_question(row: sqlite3.Row) -> BenchmarkQuestion:
        return BenchmarkQuestion(
            id=row["id"],
            benchmark_id=row["benchmark_id"],
            question_id=row["question_id"],
            domain=row["domain"],
            input=row["input"],
            target=row["target"],
            target_hash=row["target_hash"],
            difficulty=row["difficulty"],
            tags=json.loads(row["tags_json"]),
            created_at=row["created_at"],
            metadata=json.loads(row["metadata_json"]),
            total_attempts=row["total_attempts"],
            correct_count=row["correct_count"],
            wrong_count=row["wrong_count"],
            last_attempt_at=row["last_attempt_at"],
            last_result=row["last_result"],
        )

    @staticmethod
    def _row_to_question_attempt(row: sqlite3.Row) -> QuestionAttempt:
        return QuestionAttempt(
            id=row["id"],
            question_id=row["question_id"],
            run_id=row["run_id"],
            team_id=row["team_id"],
            model_answer=row["model_answer"],
            judgment=row["judgment"],
            confidence=row["confidence"],
            reasoning_log=json.loads(row["reasoning_log"]),
            paradigm_used=row["paradigm_used"],
            time_ms=row["time_ms"],
            tokens_in=row["tokens_in"],
            tokens_out=row["tokens_out"],
            cost=row["cost"],
            attempted_at=row["attempted_at"],
            analysis=row["analysis"],
            failure_category=row["failure_category"],
        )

    # ------------------------------------------------------------------
    # Analysis CRUD
    # ------------------------------------------------------------------

    def create_analysis(self, a: Analysis) -> Analysis:
        if not a.id:
            a.id = str(uuid.uuid4())
        if not a.created_at:
            a.created_at = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO analyses
               (id, question_result_id, status, failure_category, root_cause,
                summary, recommendations_json, raw_output, model_used,
                tokens_in, tokens_out, cost, created_at, completed_at, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                a.id, a.question_result_id, a.status, a.failure_category,
                a.root_cause, a.summary, json.dumps(a.recommendations),
                a.raw_output, a.model_used, a.tokens_in, a.tokens_out,
                a.cost, a.created_at, a.completed_at, a.error_message,
            ),
        )
        conn.commit()
        conn.close()
        return a

    def update_analysis(self, a: Analysis) -> Analysis:
        conn = self._get_conn()
        conn.execute(
            """UPDATE analyses SET
                status = ?, failure_category = ?, root_cause = ?,
                summary = ?, recommendations_json = ?, raw_output = ?,
                model_used = ?, tokens_in = ?, tokens_out = ?, cost = ?,
                completed_at = ?, error_message = ?
               WHERE id = ?""",
            (
                a.status, a.failure_category, a.root_cause,
                a.summary, json.dumps(a.recommendations), a.raw_output,
                a.model_used, a.tokens_in, a.tokens_out, a.cost,
                a.completed_at, a.error_message, a.id,
            ),
        )
        conn.commit()
        conn.close()
        return a

    def get_analysis(self, analysis_id: str) -> Optional[Analysis]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM analyses WHERE id = ?", (analysis_id,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_analysis(row)

    def get_analysis_for_result(self, question_result_id: str) -> Optional[Analysis]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM analyses WHERE question_result_id = ? ORDER BY created_at DESC LIMIT 1",
            (question_result_id,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_analysis(row)

    def get_analysis_stats(self) -> dict:
        conn = self._get_conn()
        total_row = conn.execute("SELECT COUNT(*) as cnt FROM analyses").fetchone()
        completed_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM analyses WHERE status = 'completed'"
        ).fetchone()
        cat_rows = conn.execute(
            """SELECT failure_category, COUNT(*) as cnt
               FROM analyses WHERE status = 'completed' AND failure_category IS NOT NULL
               GROUP BY failure_category ORDER BY cnt DESC"""
        ).fetchall()
        conn.close()
        return {
            "total": total_row["cnt"],
            "completed": completed_row["cnt"],
            "by_category": {r["failure_category"]: r["cnt"] for r in cat_rows},
        }

    @staticmethod
    def _row_to_analysis(row: sqlite3.Row) -> Analysis:
        return Analysis(
            id=row["id"],
            question_result_id=row["question_result_id"],
            status=row["status"],
            failure_category=row["failure_category"],
            root_cause=row["root_cause"],
            summary=row["summary"],
            recommendations=json.loads(row["recommendations_json"]),
            raw_output=row["raw_output"],
            model_used=row["model_used"],
            tokens_in=row["tokens_in"],
            tokens_out=row["tokens_out"],
            cost=row["cost"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            error_message=row["error_message"],
        )

    # ------------------------------------------------------------------
    # Paradigm Role Instructions (file-based instruction set selection)
    # ------------------------------------------------------------------

    def get_paradigm_role_instructions(self, paradigm: str) -> dict[str, str]:
        """Get {role: instruction_set_id} mapping for a paradigm."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT role, instruction_set_id FROM paradigm_role_instructions WHERE paradigm = ?",
            (paradigm,),
        ).fetchall()
        conn.close()
        return {row["role"]: row["instruction_set_id"] for row in rows}

    def set_paradigm_role_instructions(
        self, paradigm: str, configs: dict[str, str]
    ) -> None:
        """Upsert {role: instruction_set_id} for a paradigm."""
        conn = self._get_conn()
        # Delete existing rows for this paradigm, then insert new ones
        conn.execute(
            "DELETE FROM paradigm_role_instructions WHERE paradigm = ?",
            (paradigm,),
        )
        for role, set_id in configs.items():
            conn.execute(
                "INSERT INTO paradigm_role_instructions (paradigm, role, instruction_set_id) "
                "VALUES (?, ?, ?)",
                (paradigm, role, set_id),
            )
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # ModelSettings CRUD
    # ------------------------------------------------------------------

    def upsert_model_settings(self, s: ModelSettings) -> ModelSettings:
        now = datetime.now(timezone.utc).isoformat()
        if not s.id:
            s.id = str(uuid.uuid4())
        if not s.created_at:
            s.created_at = now
        s.updated_at = now

        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO model_settings
               (id, paradigm_id, role_id, model_id, context_window, max_tokens,
                thinking_enabled, thinking_budget, interleaved_thinking,
                temperature, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                s.id, s.paradigm_id, s.role_id, s.model_id,
                s.context_window, s.max_tokens,
                int(s.thinking_enabled), s.thinking_budget,
                int(s.interleaved_thinking), s.temperature,
                s.created_at, s.updated_at,
            ),
        )
        conn.commit()
        conn.close()
        return s

    def get_model_settings(
        self, paradigm_id: str, role_id: str, model_id: str
    ) -> Optional[ModelSettings]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM model_settings WHERE paradigm_id = ? AND role_id = ? AND model_id = ?",
            (paradigm_id, role_id, model_id),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return self._row_to_model_settings(row)

    def list_model_settings(
        self,
        paradigm_id: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> list[ModelSettings]:
        conn = self._get_conn()
        query = "SELECT * FROM model_settings WHERE 1=1"
        params: list = []
        if paradigm_id is not None:
            query += " AND paradigm_id = ?"
            params.append(paradigm_id)
        if model_id is not None:
            query += " AND model_id = ?"
            params.append(model_id)
        query += " ORDER BY paradigm_id, role_id, model_id"
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [self._row_to_model_settings(r) for r in rows]

    def delete_model_settings(self, settings_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM model_settings WHERE id = ?", (settings_id,)
        )
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted

    def resolve_model_settings(
        self, paradigm_id: str, role_id: str, model_id: str
    ) -> dict:
        """Cascade resolution: paradigm+role+model → paradigm+model → global+model → defaults."""
        # Try exact match: paradigm + role + model
        s = self.get_model_settings(paradigm_id, role_id, model_id)
        if s:
            return self._settings_to_dict(s, "paradigm+role")

        # Try paradigm + all roles + model
        s = self.get_model_settings(paradigm_id, "", model_id)
        if s:
            return self._settings_to_dict(s, "paradigm")

        # Try global + model
        s = self.get_model_settings("", "", model_id)
        if s:
            return self._settings_to_dict(s, "global")

        # Fall back to MODEL_DEFAULTS
        defaults = MODEL_DEFAULTS.get(model_id, MODEL_DEFAULTS.get("sonnet-4.5", {}))
        return {**defaults, "resolved_from": "defaults"}

    @staticmethod
    def _settings_to_dict(s: ModelSettings, resolved_from: str) -> dict:
        return {
            "context_window": s.context_window,
            "max_tokens": s.max_tokens,
            "thinking_enabled": s.thinking_enabled,
            "thinking_budget": s.thinking_budget,
            "interleaved_thinking": s.interleaved_thinking,
            "temperature": s.temperature,
            "resolved_from": resolved_from,
        }

    @staticmethod
    def _row_to_model_settings(row: sqlite3.Row) -> ModelSettings:
        return ModelSettings(
            id=row["id"],
            paradigm_id=row["paradigm_id"],
            role_id=row["role_id"],
            model_id=row["model_id"],
            context_window=row["context_window"],
            max_tokens=row["max_tokens"],
            thinking_enabled=bool(row["thinking_enabled"]),
            thinking_budget=row["thinking_budget"],
            interleaved_thinking=bool(row["interleaved_thinking"]),
            temperature=row["temperature"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
