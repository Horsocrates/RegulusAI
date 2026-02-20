"""Tests for Lab v2 Results & Analytics API endpoints."""

import csv
import io
import json
import os

import pytest
from fastapi.testclient import TestClient

from regulus.api.main import app
from regulus.api.models.lab import LabNewDB, QuestionResult, DomainOutputRecord


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path):
    """Give every test a clean database."""
    from regulus.api.routers.lab import teams as teams_mod
    from regulus.api.routers.lab import tests as tests_mod
    from regulus.api.routers.lab import runs as runs_mod
    from regulus.api.routers.lab import results as results_mod
    from regulus.api.routers.lab import training_export as training_export_mod

    # Disable rate limiter for tests
    old_val = os.environ.get("LAB_RATE_LIMIT_RPM")
    os.environ["LAB_RATE_LIMIT_RPM"] = "0"

    db = LabNewDB(db_path=tmp_path / "test.db")
    teams_mod._db = db
    tests_mod._db = db
    runs_mod._db = db
    results_mod._db = db
    training_export_mod._db = db
    yield db

    # Restore rate limiter setting
    if old_val is None:
        os.environ.pop("LAB_RATE_LIMIT_RPM", None)
    else:
        os.environ["LAB_RATE_LIMIT_RPM"] = old_val


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_team(client, name="Alpha Team"):
    return client.post("/api/lab/teams", json={
        "name": name,
        "team_lead_config": {
            "model": "gpt-4o-mini", "temperature": 0.3,
            "max_tokens": 4096, "instructions": "", "enabled": True,
        },
        "agents": {},
    }).json()


def _make_config(client, team_id):
    return client.post("/api/lab/tests", json={
        "name": "BBEH Test",
        "benchmark": "bbeh",
        "domains": ["boolean_expressions"],
        "question_count": 10,
        "questions_per_team": 4,
        "team_id": team_id,
        "judge_config": {"strict_mode": True},
    }).json()


def _make_run(client, config_id):
    return client.post(f"/api/lab/tests/{config_id}/run").json()


SKILL_TYPES = ["decomposition", "verification", "recall", "computation", "conceptual"]


def _add_results(db, run_id, count=5, domain="boolean_expressions"):
    """Insert fake question results directly into DB."""
    for i in range(count):
        db.create_question_result(QuestionResult(
            run_id=run_id,
            question_index=i,
            question_id=f"q-{i}",
            domain=domain,
            input_text=f"Question {i}?",
            team_index=i // 3,
            status="completed",
            final_answer=f"Answer {i}",
            judgment_verdict="correct" if i % 2 == 0 else "wrong",
            judgment_confidence=1.0,
            judgment_explanation="Test judgment",
            total_time_ms=1000 + i * 100,
            total_tokens_in=200 + i * 10,
            total_tokens_out=100 + i * 5,
            estimated_cost=0.01 + i * 0.001,
            skill_type=SKILL_TYPES[i % len(SKILL_TYPES)],
            skill_confidence=0.85,
        ))


# ===================================================================
# Run Stats
# ===================================================================


class TestRunStats:
    def test_stats_empty(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])

        r = client.get(f"/api/lab/v2/runs/{run['id']}/stats")
        assert r.status_code == 200
        stats = r.json()
        assert stats["completed_questions"] == 0
        assert stats["accuracy"] == 0.0

    def test_stats_with_results(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=6)

        r = client.get(f"/api/lab/v2/runs/{run['id']}/stats")
        assert r.status_code == 200
        stats = r.json()
        assert stats["completed_questions"] == 6
        # 0, 2, 4 are correct = 3 correct out of 6
        assert stats["correct_count"] == 3
        assert stats["wrong_count"] == 3

    def test_stats_404(self, client):
        r = client.get("/api/lab/v2/runs/nonexistent/stats")
        assert r.status_code == 404


# ===================================================================
# Domain Stats
# ===================================================================


class TestDomainStats:
    def test_domain_breakdown(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])

        # Add results from two domains
        for i in range(3):
            _fresh_db.create_question_result(QuestionResult(
                run_id=run["id"], question_index=i, question_id=f"q-{i}",
                domain="boolean_expressions", status="completed",
                judgment_verdict="correct",
                total_time_ms=1000, total_tokens_in=100, total_tokens_out=50,
                estimated_cost=0.01,
            ))
        for i in range(3, 5):
            _fresh_db.create_question_result(QuestionResult(
                run_id=run["id"], question_index=i, question_id=f"q-{i}",
                domain="navigate", status="completed",
                judgment_verdict="wrong",
                total_time_ms=2000, total_tokens_in=200, total_tokens_out=100,
                estimated_cost=0.02,
            ))

        r = client.get(f"/api/lab/v2/runs/{run['id']}/stats/domains")
        assert r.status_code == 200
        domains = r.json()
        assert len(domains) == 2
        # Sorted by accuracy (worst first)
        assert domains[0]["domain"] == "navigate"
        assert domains[0]["accuracy"] == 0.0
        assert domains[1]["domain"] == "boolean_expressions"
        assert domains[1]["accuracy"] == 1.0


# ===================================================================
# Team Stats
# ===================================================================


class TestTeamStats:
    def test_team_breakdown(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=6)

        r = client.get(f"/api/lab/v2/runs/{run['id']}/stats/teams")
        assert r.status_code == 200
        teams = r.json()
        assert len(teams) == 2  # team_index 0 and 1


# ===================================================================
# Question Detail
# ===================================================================


class TestQuestionDetail:
    def test_get_question(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=3)

        r = client.get(f"/api/lab/v2/runs/{run['id']}/question/1")
        assert r.status_code == 200
        q = r.json()
        assert q["question_index"] == 1
        assert q["question_id"] == "q-1"

    def test_question_not_found(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])

        r = client.get(f"/api/lab/v2/runs/{run['id']}/question/99")
        assert r.status_code == 404

    def test_question_includes_full_text(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=1)

        r = client.get(f"/api/lab/v2/runs/{run['id']}/question/0")
        q = r.json()
        assert "input_text" in q
        assert "agent_outputs" in q


# ===================================================================
# Export
# ===================================================================


class TestExport:
    def test_export_json(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=3)

        r = client.get(f"/api/lab/v2/runs/{run['id']}/export?format=json")
        assert r.status_code == 200
        assert "application/json" in r.headers["content-type"]
        data = r.json()
        assert "metrics" in data
        assert "results" in data
        assert len(data["results"]) == 3

    def test_export_csv(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=3)

        r = client.get(f"/api/lab/v2/runs/{run['id']}/export?format=csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]

        # Parse CSV
        reader = csv.reader(io.StringIO(r.text))
        rows = list(reader)
        assert len(rows) == 4  # header + 3 data rows
        assert rows[0][0] == "question_index"

    def test_export_default_json(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])

        r = client.get(f"/api/lab/v2/runs/{run['id']}/export")
        assert r.status_code == 200
        data = r.json()
        assert data["results"] == []

    def test_export_404(self, client):
        r = client.get("/api/lab/v2/runs/nonexistent/export?format=json")
        assert r.status_code == 404

    def test_export_has_filename(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])

        r = client.get(f"/api/lab/v2/runs/{run['id']}/export?format=csv")
        assert "filename" in r.headers.get("content-disposition", "")


# ===================================================================
# Analysis Report
# ===================================================================


class TestAnalysisReport:
    def test_report_empty(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])

        r = client.get(f"/api/lab/v2/runs/{run['id']}/report")
        assert r.status_code == 200
        report = r.json()
        assert report["run_id"] == run["id"]
        # total_questions comes from the run config (10), not from results count
        assert report["summary"]["total_questions"] == 10
        assert report["failure_patterns"] == []

    def test_report_with_results(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=6)

        r = client.get(f"/api/lab/v2/runs/{run['id']}/report")
        assert r.status_code == 200
        report = r.json()
        assert report["summary"]["correct"] == 3
        assert report["summary"]["wrong"] == 3
        assert len(report["domain_analysis"]) >= 1
        assert "recommendations" in report

    def test_report_404(self, client):
        r = client.get("/api/lab/v2/runs/nonexistent/report")
        assert r.status_code == 404

    def test_report_has_generated_at(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])

        r = client.get(f"/api/lab/v2/runs/{run['id']}/report")
        report = r.json()
        assert "generated_at" in report
        assert report["generated_at"]  # non-empty


# ===================================================================
# Dashboard
# ===================================================================


class TestDashboard:
    def test_dashboard_empty(self, client, _fresh_db):
        r = client.get("/api/lab/v2/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert data["total_runs"] == 0
        assert data["overall_accuracy"] == 0.0

    def test_dashboard_with_runs(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=4)

        r = client.get("/api/lab/v2/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert data["total_runs"] == 1
        assert data["total_questions_answered"] == 4
        assert data["total_correct"] == 2  # indices 0, 2 are correct
        assert data["total_wrong"] == 2
        assert data["total_cost"] > 0

    def test_dashboard_multiple_runs(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run1 = _make_run(client, cfg["id"])
        run2 = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run1["id"], count=2)
        _add_results(_fresh_db, run2["id"], count=3)

        r = client.get("/api/lab/v2/dashboard")
        data = r.json()
        assert data["total_runs"] == 2
        assert data["total_questions_answered"] == 5


# ===================================================================
# Paginated Results (cross-run)
# ===================================================================


class TestPaginatedResults:
    def test_empty(self, client, _fresh_db):
        r = client.get("/api/lab/v2/results")
        assert r.status_code == 200
        data = r.json()
        assert data["results"] == []
        assert data["total"] == 0

    def test_with_results(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=5)

        r = client.get("/api/lab/v2/results")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 5
        assert len(data["results"]) == 5

    def test_pagination(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=10)

        r = client.get("/api/lab/v2/results?limit=3&offset=0")
        data = r.json()
        assert len(data["results"]) == 3
        assert data["total"] == 10
        assert data["limit"] == 3
        assert data["offset"] == 0

    def test_filter_by_verdict(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=6)

        r = client.get("/api/lab/v2/results?verdict=correct")
        data = r.json()
        # indices 0,2,4 are correct
        assert data["total"] == 3
        assert all(r["judgment_verdict"] == "correct" for r in data["results"])

    def test_filter_by_domain(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=3, domain="math")
        _add_results(_fresh_db, run["id"], count=2, domain="logic")

        r = client.get("/api/lab/v2/results?domain=math")
        data = r.json()
        assert data["total"] == 3

    def test_cross_run_results(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run1 = _make_run(client, cfg["id"])
        run2 = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run1["id"], count=3)
        _add_results(_fresh_db, run2["id"], count=4)

        r = client.get("/api/lab/v2/results")
        data = r.json()
        assert data["total"] == 7


# ===================================================================
# Skill Type Classification
# ===================================================================


class TestSkillType:
    def test_filter_by_skill_type(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=10)

        r = client.get("/api/lab/v2/results?skill_type=computation")
        data = r.json()
        # indices 3, 8 are "computation" (i % 5 == 3)
        assert data["total"] == 2
        assert all(
            item["skill_type"] == "computation" for item in data["results"]
        )

    def test_stats_include_skill_breakdown(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=5)

        r = client.get("/api/lab/v2/results/stats")
        assert r.status_code == 200
        stats = r.json()
        assert "by_skill_type" in stats
        assert "skill_types" in stats
        assert len(stats["skill_types"]) == 5
        assert "decomposition" in stats["by_skill_type"]
        assert stats["by_skill_type"]["decomposition"]["total"] == 1

    def test_update_skill_type(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=1)

        # Get the result id
        r = client.get("/api/lab/v2/results")
        result_id = r.json()["results"][0]["id"]

        # PATCH skill_type
        r = client.patch(
            f"/api/lab/v2/results/{result_id}/skill-type",
            json={"skill_type": "verification", "skill_confidence": 0.95},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["skill_type"] == "verification"
        assert data["skill_confidence"] == 0.95

    def test_skill_type_in_export(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=3)

        r = client.get(f"/api/lab/v2/runs/{run['id']}/export?format=csv")
        assert r.status_code == 200
        reader = csv.reader(io.StringIO(r.text))
        rows = list(reader)
        header = rows[0]
        assert "skill_type" in header
        assert "skill_confidence" in header
        # Data rows should have skill_type values
        skill_type_idx = header.index("skill_type")
        assert rows[1][skill_type_idx] != ""

    def test_skill_type_in_json_export(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=2)

        r = client.get(f"/api/lab/v2/runs/{run['id']}/export?format=json")
        data = r.json()
        assert "skill_type" in data["results"][0]
        assert data["results"][0]["skill_type"] is not None

    def test_question_detail_includes_skill_type(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=1)

        r = client.get(f"/api/lab/v2/runs/{run['id']}/question/0")
        assert r.status_code == 200
        q = r.json()
        assert "skill_type" in q
        assert q["skill_type"] == "decomposition"
        assert q["skill_confidence"] == 0.85


# ===================================================================
# Instruction Resolution
# ===================================================================


class TestInstructionResolution:
    def test_instruction_resolution_in_result(self, client, _fresh_db):
        """instruction_resolution field stored and returned."""
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])

        trace = json.dumps({"d1": [{"level": "skill", "path": "_skill/decomposition/d1-recognize.md", "hit": True}]})
        _fresh_db.create_question_result(QuestionResult(
            run_id=run["id"],
            question_index=0,
            question_id="q-0",
            domain="test",
            input_text="Test?",
            status="completed",
            final_answer="42",
            judgment_verdict="correct",
            skill_type="decomposition",
            instruction_resolution=trace,
        ))

        r = client.get("/api/lab/v2/results")
        data = r.json()
        assert data["total"] == 1
        item = data["results"][0]
        assert item["instruction_resolution"] == trace

    def test_instruction_resolution_in_question_detail(self, client, _fresh_db):
        """instruction_resolution shows in question detail endpoint."""
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])

        trace = json.dumps({"d4": [{"level": "default", "path": "default/d4-compare.md", "hit": True}]})
        _fresh_db.create_question_result(QuestionResult(
            run_id=run["id"],
            question_index=0,
            question_id="q-0",
            domain="test",
            input_text="Test?",
            status="completed",
            instruction_resolution=trace,
        ))

        r = client.get(f"/api/lab/v2/runs/{run['id']}/question/0")
        assert r.status_code == 200
        q = r.json()
        assert "instruction_resolution" in q
        assert q["instruction_resolution"] == trace

    def test_instruction_resolution_in_export(self, client, _fresh_db):
        """instruction_resolution appears in CSV export."""
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])

        trace = json.dumps({"d1": [{"level": "default", "path": "default/d1-recognize.md", "hit": True}]})
        _fresh_db.create_question_result(QuestionResult(
            run_id=run["id"],
            question_index=0,
            question_id="q-0",
            domain="test",
            input_text="Test?",
            status="completed",
            instruction_resolution=trace,
        ))

        r = client.get(f"/api/lab/v2/runs/{run['id']}/export?format=csv")
        assert r.status_code == 200
        reader = csv.reader(io.StringIO(r.text))
        rows = list(reader)
        header = rows[0]
        assert "instruction_resolution" in header

    def test_instruction_resolution_null_by_default(self, client, _fresh_db):
        """Results without instruction_resolution have null."""
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=1)

        r = client.get("/api/lab/v2/results")
        item = r.json()["results"][0]
        assert item["instruction_resolution"] is None

    def test_resolve_preview_endpoint(self, client):
        """GET /resolve-preview returns resolution for all roles."""
        r = client.get("/api/lab/instruction-sets/resolve-preview?set_id=default")
        assert r.status_code == 200
        data = r.json()
        assert "roles" in data
        assert "levels" in data
        assert "set_id" in data
        assert data["set_id"] == "default"
        # Should have entries for each role
        assert "d1" in data["roles"]
        assert "team_lead" in data["roles"]
        assert "resolved_level" in data["roles"]["d1"]
        assert "trace" in data["roles"]["d1"]

    def test_resolve_preview_with_skill_type(self, client):
        """Resolve preview with skill_type shows skill levels in trace."""
        r = client.get(
            "/api/lab/instruction-sets/resolve-preview"
            "?set_id=default&skill_type=decomposition"
        )
        assert r.status_code == 200
        data = r.json()
        assert data["skill_type"] == "decomposition"
        # d1 trace should include skill-level lookups
        d1_trace = data["roles"]["d1"]["trace"]
        levels = [step["level"] for step in d1_trace]
        assert "skill" in levels or "default_skill" in levels or "default" in levels


# ===================================================================
# Correct Answer
# ===================================================================


class TestCorrectAnswer:
    def test_correct_answer_stored(self, client, _fresh_db):
        """correct_answer is stored and returned."""
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])

        _fresh_db.create_question_result(QuestionResult(
            run_id=run["id"],
            question_index=0,
            question_id="q-0",
            domain="test",
            input_text="What is 2+2?",
            status="completed",
            final_answer="4",
            correct_answer="4",
            judgment_verdict="correct",
        ))

        r = client.get("/api/lab/v2/results")
        data = r.json()
        assert data["total"] == 1
        assert data["results"][0]["correct_answer"] == "4"

    def test_correct_answer_in_question_detail(self, client, _fresh_db):
        """correct_answer appears in question detail endpoint."""
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])

        _fresh_db.create_question_result(QuestionResult(
            run_id=run["id"],
            question_index=0,
            question_id="q-0",
            domain="test",
            input_text="What is 2+2?",
            status="completed",
            final_answer="5",
            correct_answer="4",
            judgment_verdict="wrong",
        ))

        r = client.get(f"/api/lab/v2/runs/{run['id']}/question/0")
        assert r.status_code == 200
        q = r.json()
        assert q["correct_answer"] == "4"

    def test_correct_answer_null_by_default(self, client, _fresh_db):
        """Results without correct_answer have null."""
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_results(_fresh_db, run["id"], count=1)

        r = client.get("/api/lab/v2/results")
        item = r.json()["results"][0]
        assert item["correct_answer"] is None

    def test_correct_answer_in_json_export(self, client, _fresh_db):
        """correct_answer appears in JSON export."""
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])

        _fresh_db.create_question_result(QuestionResult(
            run_id=run["id"],
            question_index=0,
            question_id="q-0",
            domain="test",
            input_text="Test?",
            status="completed",
            correct_answer="42",
        ))

        r = client.get(f"/api/lab/v2/runs/{run['id']}/export?format=json")
        data = r.json()
        assert data["results"][0]["correct_answer"] == "42"

    def test_correct_answer_in_csv_export(self, client, _fresh_db):
        """correct_answer appears in CSV export."""
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])

        _fresh_db.create_question_result(QuestionResult(
            run_id=run["id"],
            question_index=0,
            question_id="q-0",
            domain="test",
            input_text="Test?",
            status="completed",
            correct_answer="42",
        ))

        r = client.get(f"/api/lab/v2/runs/{run['id']}/export?format=csv")
        reader = csv.reader(io.StringIO(r.text))
        rows = list(reader)
        header = rows[0]
        assert "correct_answer" in header


# ===================================================================
# Domain Outputs
# ===================================================================


class TestDomainOutputs:
    def test_create_and_get_domain_outputs(self, _fresh_db):
        """Domain outputs can be created and retrieved."""
        team_data = {"name": "Test", "team_lead_config": {}, "agent_configs": {}}
        from regulus.api.models.lab import Team, TestConfig, TestRun
        team = _fresh_db.create_team(Team(name="T"))
        cfg = _fresh_db.create_test_config(TestConfig(name="C", team_id=team.id))
        run = _fresh_db.create_test_run(TestRun(config_id=cfg.id))

        qr = _fresh_db.create_question_result(QuestionResult(
            run_id=run.id,
            question_index=0,
            question_id="q-0",
            domain="test",
            input_text="Test?",
            status="completed",
        ))

        records = [
            DomainOutputRecord(domain="D1", pipeline="audit", weight=85, gate_passed=True, content="Recognition ok"),
            DomainOutputRecord(domain="D2", pipeline="audit", weight=70, gate_passed=True, content="Clarification ok"),
            DomainOutputRecord(domain="D3", pipeline="audit", weight=0, gate_passed=False, issues_json='["Missing framework"]'),
        ]
        _fresh_db.create_domain_outputs(qr.id, records)

        outputs = _fresh_db.get_domain_outputs(qr.id)
        assert len(outputs) == 3
        assert outputs[0].domain == "D1"
        assert outputs[0].weight == 85
        assert outputs[0].gate_passed is True
        assert outputs[2].domain == "D3"
        assert outputs[2].gate_passed is False

    def test_domain_outputs_empty(self, _fresh_db):
        """No domain outputs returns empty list."""
        outputs = _fresh_db.get_domain_outputs("nonexistent")
        assert outputs == []


# ===================================================================
# Training Export
# ===================================================================


AGENT_OUTPUTS_WITH_DOMAINS = {
    "pipeline": "audit",
    "version": "2.0",
    "reasoning_model": "deepseek",
    "thinking": "Let me think about this...",
    "domains": {
        "D1": {"present": True, "weight": 85, "gate_passed": True, "issues": []},
        "D2": {"present": True, "weight": 70, "gate_passed": True, "issues": []},
    },
}


def _add_training_results(db, run_id, count=3):
    """Insert results with agent_outputs for training export tests."""
    for i in range(count):
        db.create_question_result(QuestionResult(
            run_id=run_id,
            question_index=i,
            question_id=f"q-{i}",
            domain="test",
            input_text=f"Question {i}?",
            status="completed",
            final_answer=f"Answer {i}",
            correct_answer=f"Expected {i}",
            judgment_verdict="correct" if i % 2 == 0 else "wrong",
            judgment_confidence=1.0,
            total_time_ms=1000,
            total_tokens_in=200,
            total_tokens_out=100,
            estimated_cost=0.01,
            skill_type="decomposition",
            agent_outputs=AGENT_OUTPUTS_WITH_DOMAINS,
        ))


class TestTrainingExport:
    def test_training_stats_empty(self, client, _fresh_db):
        r = client.get("/api/lab/v2/export/training-stats")
        assert r.status_code == 200
        data = r.json()
        assert data["total_results"] == 0
        assert data["with_agent_outputs"] == 0

    def test_training_stats_with_data(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_training_results(_fresh_db, run["id"], count=4)

        r = client.get("/api/lab/v2/export/training-stats")
        assert r.status_code == 200
        data = r.json()
        assert data["total_results"] == 4
        assert data["with_agent_outputs"] == 4
        # indices 0, 2 are correct
        assert data["correct_with_outputs"] == 2

    def test_export_jsonl(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_training_results(_fresh_db, run["id"], count=3)

        r = client.get("/api/lab/v2/export/training-data?format=jsonl")
        assert r.status_code == 200
        lines = r.text.strip().split("\n")
        assert len(lines) == 3

        # Each line should be valid JSON
        for line in lines:
            obj = json.loads(line)
            assert "messages" in obj
            assert "metadata" in obj
            assert len(obj["messages"]) == 3
            assert obj["messages"][0]["role"] == "system"
            assert obj["messages"][1]["role"] == "user"
            assert obj["messages"][2]["role"] == "assistant"

    def test_export_csv(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_training_results(_fresh_db, run["id"], count=2)

        r = client.get("/api/lab/v2/export/training-data?format=csv")
        assert r.status_code == 200
        reader = csv.reader(io.StringIO(r.text))
        rows = list(reader)
        header = rows[0]
        assert "question_id" in header
        assert "correct_answer" in header
        assert "d1_weight" in header
        assert "d6_gate" in header
        assert len(rows) == 3  # header + 2 data rows

    def test_export_json(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_training_results(_fresh_db, run["id"], count=2)

        r = client.get("/api/lab/v2/export/training-data?format=json")
        assert r.status_code == 200
        data = r.json()
        assert data["export_format"] == "training_data"
        assert data["total_records"] == 2
        assert len(data["records"]) == 2
        assert data["records"][0]["correct_answer"] is not None
        assert "domains" in data["records"][0]

    def test_export_filter_by_verdict(self, client, _fresh_db):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_training_results(_fresh_db, run["id"], count=4)

        r = client.get("/api/lab/v2/export/training-data?format=json&verdict=correct")
        data = r.json()
        # indices 0, 2 are correct
        assert data["total_records"] == 2

    def test_export_only_logged_results(self, client, _fresh_db):
        """Export only returns results with agent_outputs."""
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])

        # Add one with agent_outputs
        _add_training_results(_fresh_db, run["id"], count=1)
        # Add one without agent_outputs
        _add_results(_fresh_db, run["id"], count=1)

        r = client.get("/api/lab/v2/export/training-data?format=json")
        data = r.json()
        assert data["total_records"] == 1

    def test_export_jsonl_includes_thinking(self, client, _fresh_db):
        """JSONL export includes thinking traces when requested."""
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_training_results(_fresh_db, run["id"], count=1)

        r = client.get("/api/lab/v2/export/training-data?format=jsonl&include_thinking=true")
        obj = json.loads(r.text.strip())
        assert "<thinking>" in obj["messages"][2]["content"]

    def test_export_jsonl_excludes_thinking(self, client, _fresh_db):
        """JSONL export excludes thinking traces when not requested."""
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = _make_run(client, cfg["id"])
        _add_training_results(_fresh_db, run["id"], count=1)

        r = client.get("/api/lab/v2/export/training-data?format=jsonl&include_thinking=false")
        obj = json.loads(r.text.strip())
        assert "<thinking>" not in obj["messages"][2]["content"]
