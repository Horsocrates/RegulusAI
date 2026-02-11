"""Tests for Lab v2 Test Executor."""

import asyncio
import pytest
from unittest.mock import MagicMock

from regulus.api.models.lab import LabNewDB, Team, TestConfig, TestRun, QuestionResult
from regulus.data.base import BenchmarkExample, BenchmarkInfo
from regulus.lab.executor import TestExecutor, ExecutionEvent


@pytest.fixture
def db(tmp_path):
    """Fresh database for each test."""
    return LabNewDB(db_path=tmp_path / "test.db")


@pytest.fixture
def team(db):
    """Create a test team."""
    return db.create_team(Team(
        name="Test Team",
        team_lead_config={"model": "gpt-4o-mini", "temperature": 0.3},
        agent_configs={},
    ))


@pytest.fixture
def config(db, team):
    """Create a test config."""
    return db.create_test_config(TestConfig(
        name="Test Config",
        benchmark="bbeh",
        domains=["boolean_expressions"],
        question_count=5,
        questions_per_team=3,
        team_id=team.id,
        judge_config={"strict_mode": True},
    ))


@pytest.fixture
def run(db, config):
    """Create a pending test run."""
    return db.create_test_run(TestRun(
        config_id=config.id,
        status="pending",
        total_questions=5,
    ))


# ===================================================================
# QuestionResult CRUD (DB layer)
# ===================================================================


class TestQuestionResultCRUD:
    def test_create_and_get(self, db, run):
        result = db.create_question_result(QuestionResult(
            run_id=run.id,
            question_index=0,
            question_id="q1",
            domain="boolean_expressions",
            input_text="What is True and False?",
            team_index=0,
            status="completed",
            final_answer="False",
            judgment_verdict="correct",
            judgment_confidence=1.0,
            judgment_explanation="Exact match",
            total_time_ms=1500,
            total_tokens_in=200,
            total_tokens_out=50,
            estimated_cost=0.001,
        ))
        assert result.id != ""

        fetched = db.get_question_result(result.id)
        assert fetched is not None
        assert fetched.question_id == "q1"
        assert fetched.judgment_verdict == "correct"

    def test_list_results(self, db, run):
        for i in range(3):
            db.create_question_result(QuestionResult(
                run_id=run.id,
                question_index=i,
                question_id=f"q{i}",
                domain="boolean_expressions",
                status="completed",
            ))

        results = db.list_question_results(run.id)
        assert len(results) == 3
        assert results[0].question_index == 0

    def test_list_results_filter_status(self, db, run):
        db.create_question_result(QuestionResult(
            run_id=run.id, question_index=0, question_id="q0",
            status="completed",
        ))
        db.create_question_result(QuestionResult(
            run_id=run.id, question_index=1, question_id="q1",
            status="error",
        ))

        completed = db.list_question_results(run.id, status="completed")
        assert len(completed) == 1
        errors = db.list_question_results(run.id, status="error")
        assert len(errors) == 1

    def test_list_results_filter_domain(self, db, run):
        db.create_question_result(QuestionResult(
            run_id=run.id, question_index=0, question_id="q0",
            domain="boolean_expressions", status="completed",
        ))
        db.create_question_result(QuestionResult(
            run_id=run.id, question_index=1, question_id="q1",
            domain="navigate", status="completed",
        ))

        results = db.list_question_results(run.id, domain="navigate")
        assert len(results) == 1
        assert results[0].domain == "navigate"

    def test_list_results_filter_team_index(self, db, run):
        db.create_question_result(QuestionResult(
            run_id=run.id, question_index=0, question_id="q0",
            team_index=0, status="completed",
        ))
        db.create_question_result(QuestionResult(
            run_id=run.id, question_index=1, question_id="q1",
            team_index=1, status="completed",
        ))

        results = db.list_question_results(run.id, team_index=0)
        assert len(results) == 1
        assert results[0].team_index == 0

    def test_list_results_pagination(self, db, run):
        for i in range(10):
            db.create_question_result(QuestionResult(
                run_id=run.id, question_index=i, question_id=f"q{i}",
                status="completed",
            ))

        page1 = db.list_question_results(run.id, limit=3, offset=0)
        assert len(page1) == 3
        assert page1[0].question_index == 0

        page2 = db.list_question_results(run.id, limit=3, offset=3)
        assert len(page2) == 3
        assert page2[0].question_index == 3

    def test_count_results(self, db, run):
        for i in range(5):
            db.create_question_result(QuestionResult(
                run_id=run.id, question_index=i, question_id=f"q{i}",
                status="completed" if i < 3 else "error",
            ))

        assert db.count_question_results(run.id) == 5
        assert db.count_question_results(run.id, status="completed") == 3
        assert db.count_question_results(run.id, status="error") == 2

    def test_update_result(self, db, run):
        result = db.create_question_result(QuestionResult(
            run_id=run.id, question_index=0, question_id="q0",
            status="pending",
        ))

        updated = db.update_question_result(
            result.id,
            status="completed",
            final_answer="42",
            judgment_verdict="correct",
        )
        assert updated.status == "completed"
        assert updated.final_answer == "42"
        assert updated.judgment_verdict == "correct"

    def test_get_nonexistent_result(self, db):
        assert db.get_question_result("nonexistent") is None


# ===================================================================
# ExecutionEvent
# ===================================================================


class TestExecutionEvent:
    def test_creation(self):
        event = ExecutionEvent(
            type="question_complete",
            run_id="run-1",
            question_index=5,
            total_questions=10,
            team_index=1,
            data={"verdict": "correct"},
        )
        assert event.type == "question_complete"
        assert event.data["verdict"] == "correct"

    def test_default_data(self):
        event = ExecutionEvent(type="run_start")
        assert event.data == {}
        assert event.run_id == ""


# ===================================================================
# TestExecutor initialization
# ===================================================================


class TestExecutorInit:
    def test_creation(self, db):
        executor = TestExecutor(db)
        assert executor.concurrency == 3
        assert executor._stop_requested is False

    def test_custom_concurrency(self, db):
        executor = TestExecutor(db, concurrency=10)
        assert executor.concurrency == 10

    def test_request_stop(self, db):
        executor = TestExecutor(db)
        executor.request_stop()
        assert executor._stop_requested is True


# ===================================================================
# Executor._load_questions (via internal method, mocked loader)
# ===================================================================


def _make_examples(n, domain="test_domain"):
    """Create N fake BenchmarkExamples."""
    return [
        BenchmarkExample(
            id=f"{domain}_{i}",
            input=f"Question {i}",
            target=f"Answer {i}",
            domain=domain,
        )
        for i in range(n)
    ]


def _mock_loader(examples_per_domain=20, domains=None):
    """Create a mock BenchmarkLoader."""
    if domains is None:
        domains = ["boolean_expressions", "navigate"]
    all_examples = []
    for d in domains:
        all_examples.extend(_make_examples(examples_per_domain, domain=d))

    loader = MagicMock()
    loader.info.return_value = BenchmarkInfo(
        id="mock", name="Mock", description="", source="",
        total_examples=len(all_examples), domains=domains, version="1.0",
    )
    loader.load_all.return_value = list(all_examples)
    loader.load_domain.side_effect = lambda d, **kw: [
        e for e in all_examples if e.domain == d
    ]
    loader.load_by_ids.side_effect = lambda ids, **kw: [
        e for e in all_examples if e.id in ids
    ]
    return loader


class TestLoadQuestions:
    def test_load_with_count(self, db, config):
        executor = TestExecutor(db)
        loader = _mock_loader(examples_per_domain=20, domains=["boolean_expressions"])
        questions = executor._load_questions(loader, config)
        assert len(questions) == config.question_count

    def test_load_with_domains(self, db, team):
        cfg = db.create_test_config(TestConfig(
            name="Domain test",
            benchmark="bbeh",
            domains=["boolean_expressions"],
            question_count=3,
            team_id=team.id,
        ))
        executor = TestExecutor(db)
        loader = _mock_loader(examples_per_domain=20, domains=["boolean_expressions", "navigate"])
        questions = executor._load_questions(loader, cfg)
        assert len(questions) == 3
        assert all(q.domain == "boolean_expressions" for q in questions)

    def test_load_with_shuffle(self, db, team):
        cfg = db.create_test_config(TestConfig(
            name="Shuffle test",
            benchmark="bbeh",
            domains=["boolean_expressions"],
            question_count=10,
            shuffle=True,
            team_id=team.id,
        ))
        executor = TestExecutor(db)
        loader = _mock_loader(examples_per_domain=20, domains=["boolean_expressions"])
        q_shuffled = executor._load_questions(loader, cfg)
        assert len(q_shuffled) == 10

    def test_load_all_when_no_domains(self, db, team):
        cfg = db.create_test_config(TestConfig(
            name="All domains",
            benchmark="bbeh",
            domains=[],
            question_count=5,
            team_id=team.id,
        ))
        executor = TestExecutor(db)
        loader = _mock_loader(examples_per_domain=10, domains=["a", "b"])
        questions = executor._load_questions(loader, cfg)
        assert len(questions) == 5
        loader.load_all.assert_called_once()

    def test_load_by_ids(self, db, team):
        cfg = db.create_test_config(TestConfig(
            name="By IDs",
            benchmark="bbeh",
            question_ids=["boolean_expressions_0", "boolean_expressions_1"],
            team_id=team.id,
        ))
        executor = TestExecutor(db)
        loader = _mock_loader(examples_per_domain=20, domains=["boolean_expressions"])
        questions = executor._load_questions(loader, cfg)
        assert len(questions) == 2


# ===================================================================
# Executor.execute — error cases (no LLM calls)
# ===================================================================


class TestExecutorErrorCases:
    @pytest.mark.asyncio
    async def test_execute_missing_run(self, db):
        executor = TestExecutor(db)
        events = []
        async for event in executor.execute("nonexistent"):
            events.append(event)
        assert len(events) == 1
        assert events[0].type == "error"

    @pytest.mark.asyncio
    async def test_execute_missing_config(self, db, team):
        # Create config and run, then break the FK reference by updating
        # the run's config_id directly (bypass FK check)
        cfg = db.create_test_config(TestConfig(
            name="Temp", benchmark="bbeh", team_id=team.id,
        ))
        run = db.create_test_run(TestRun(
            config_id=cfg.id, status="pending",
        ))
        # Directly break the reference (disable FK checks temporarily)
        conn = db._get_conn()
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("UPDATE test_runs SET config_id = ? WHERE id = ?",
                      ("nonexistent", run.id))
        conn.commit()
        conn.close()

        executor = TestExecutor(db)
        events = []
        async for event in executor.execute(run.id):
            events.append(event)
        assert len(events) == 1
        assert events[0].type == "error"

    @pytest.mark.asyncio
    async def test_execute_bad_benchmark(self, db, team):
        cfg = db.create_test_config(TestConfig(
            name="Bad benchmark",
            benchmark="nonexistent",
            team_id=team.id,
        ))
        run = db.create_test_run(TestRun(
            config_id=cfg.id,
            status="pending",
        ))
        executor = TestExecutor(db)
        events = []
        async for event in executor.execute(run.id):
            events.append(event)
        assert events[-1].type == "error"
