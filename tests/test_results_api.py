"""Tests for Lab v2 Results & Analytics API endpoints."""

import csv
import io
import json

import pytest
from fastapi.testclient import TestClient

from regulus.api.main import app
from regulus.api.models.lab import LabNewDB, QuestionResult


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path):
    """Give every test a clean database."""
    from regulus.api.routers.lab import teams as teams_mod
    from regulus.api.routers.lab import tests as tests_mod
    from regulus.api.routers.lab import runs as runs_mod
    from regulus.api.routers.lab import results as results_mod

    db = LabNewDB(db_path=tmp_path / "test.db")
    teams_mod._db = db
    tests_mod._db = db
    runs_mod._db = db
    results_mod._db = db
    yield db


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
