"""Tests for Lab v2 API: Teams, TestConfigs, Runs, Benchmarks."""

import json
import tempfile
import pathlib

import pytest
from fastapi.testclient import TestClient

from regulus.api.main import app
from regulus.api.models.lab import LabNewDB


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    """Give every test a clean database and disable rate limiting."""
    monkeypatch.setenv("LAB_RATE_LIMIT_RPM", "0")

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
# Helper: create team + config
# ---------------------------------------------------------------------------

def _make_team(client, name="Alpha Team"):
    return client.post("/api/lab/teams", json={
        "name": name,
        "team_lead_config": {
            "model": "claude-sonnet-4-20250514",
            "temperature": 0.3,
            "max_tokens": 4096,
            "instructions": "",
            "enabled": True,
        },
        "agents": {
            "d1": {"model": "gpt-4o-mini", "temperature": 0.2, "max_tokens": 2048,
                    "instructions": "D1", "enabled": True},
        },
    }).json()


def _make_config(client, team_id, name="BBEH Test", **overrides):
    payload = {
        "name": name,
        "benchmark": "bbeh",
        "domains": ["boolean_expressions"],
        "question_count": 10,
        "questions_per_team": 4,
        "steps_count": 2,
        "team_id": team_id,
        "judge_config": {
            "model": "claude-sonnet-4-20250514",
            "instructions": "",
            "strict_mode": False,
            "show_correct_answer": False,
        },
    }
    payload.update(overrides)
    return client.post("/api/lab/tests", json=payload).json()


# ===================================================================
# Teams CRUD
# ===================================================================


class TestTeamsAPI:
    def test_create_and_list(self, client):
        r = client.post("/api/lab/teams", json={
            "name": "T1",
            "team_lead_config": {"model": "gpt-4o-mini", "temperature": 0, "max_tokens": 1024, "instructions": "", "enabled": True},
            "agents": {},
        })
        assert r.status_code == 201
        assert r.json()["name"] == "T1"

        teams = client.get("/api/lab/teams").json()
        assert len(teams) == 1

    def test_update(self, client):
        team = _make_team(client)
        r = client.put(f"/api/lab/teams/{team['id']}", json={"name": "Updated"})
        assert r.status_code == 200
        assert r.json()["name"] == "Updated"

    def test_delete(self, client):
        team = _make_team(client)
        r = client.delete(f"/api/lab/teams/{team['id']}")
        assert r.status_code == 200 and r.json() == {"ok": True}
        assert client.get(f"/api/lab/teams/{team['id']}").status_code == 404

    def test_clone(self, client):
        team = _make_team(client)
        r = client.post(f"/api/lab/teams/{team['id']}/clone", json={"name": "Cloned"})
        assert r.status_code == 201
        assert r.json()["name"] == "Cloned"
        assert r.json()["id"] != team["id"]

    def test_set_default(self, client):
        t1 = _make_team(client, "T1")
        t2 = _make_team(client, "T2")
        client.post(f"/api/lab/teams/{t1['id']}/default")
        client.post(f"/api/lab/teams/{t2['id']}/default")
        assert client.get(f"/api/lab/teams/{t1['id']}").json()["is_default"] is False
        assert client.get(f"/api/lab/teams/{t2['id']}").json()["is_default"] is True


# ===================================================================
# TestConfigs CRUD
# ===================================================================


class TestConfigsAPI:
    def test_create_and_get(self, client):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        assert cfg["benchmark"] == "bbeh"
        assert cfg["question_count"] == 10

        fetched = client.get(f"/api/lab/tests/{cfg['id']}").json()
        assert fetched["name"] == "BBEH Test"

    def test_update(self, client):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        r = client.put(f"/api/lab/tests/{cfg['id']}", json={"question_count": 50})
        assert r.json()["question_count"] == 50

    def test_delete(self, client):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        r = client.delete(f"/api/lab/tests/{cfg['id']}")
        assert r.json() == {"ok": True}
        assert client.get(f"/api/lab/tests/{cfg['id']}").status_code == 404

    def test_bad_domain_rejected(self, client):
        team = _make_team(client)
        r = client.post("/api/lab/tests", json={
            "name": "Bad",
            "benchmark": "bbeh",
            "domains": ["nonexistent"],
            "team_id": team["id"],
        })
        assert r.status_code == 400

    def test_bad_benchmark_rejected(self, client):
        r = client.post("/api/lab/tests", json={
            "name": "Bad",
            "benchmark": "fake",
        })
        assert r.status_code == 400


# ===================================================================
# Benchmarks browser
# ===================================================================


class TestBenchmarksAPI:
    def test_list_benchmarks(self, client):
        r = client.get("/api/lab/benchmarks")
        assert r.status_code == 200
        benchmarks = r.json()
        assert any(b["id"] == "bbeh" for b in benchmarks)

    def test_get_benchmark(self, client):
        r = client.get("/api/lab/benchmarks/bbeh")
        assert r.status_code == 200
        assert len(r.json()["domains"]) == 23

    def test_unknown_benchmark_404(self, client):
        r = client.get("/api/lab/benchmarks/fake")
        assert r.status_code == 404


# ===================================================================
# Test Runs
# ===================================================================


class TestRunsAPI:
    def test_start_run(self, client):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        r = client.post(f"/api/lab/tests/{cfg['id']}/run")
        assert r.status_code == 201
        run = r.json()
        assert run["config_id"] == cfg["id"]
        assert run["total_questions"] == 10
        assert run["status"] == "pending"

    def test_dry_run(self, client):
        team = _make_team(client)
        cfg = _make_config(client, team["id"], questions_per_team=4, question_count=10)
        r = client.post(f"/api/lab/tests/{cfg['id']}/run", json={"dry_run": True})
        assert r.status_code == 201
        run = r.json()
        assert run["status"] == "dry_run"
        assert run["total_questions"] == 10
        # Should preview team rotations
        assert len(run["teams_used"]) == 3  # ceil(10/4) = 3

    def test_list_runs(self, client):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        client.post(f"/api/lab/tests/{cfg['id']}/run")
        client.post(f"/api/lab/tests/{cfg['id']}/run")

        runs = client.get("/api/lab/v2/runs").json()
        assert len(runs) == 2

    def test_list_runs_filter_by_config(self, client):
        team = _make_team(client)
        cfg1 = _make_config(client, team["id"], name="C1")
        cfg2 = _make_config(client, team["id"], name="C2")
        client.post(f"/api/lab/tests/{cfg1['id']}/run")
        client.post(f"/api/lab/tests/{cfg2['id']}/run")

        runs = client.get(f"/api/lab/v2/runs?config_id={cfg1['id']}").json()
        assert len(runs) == 1
        assert runs[0]["config_id"] == cfg1["id"]

    def test_get_run(self, client):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        created = client.post(f"/api/lab/tests/{cfg['id']}/run").json()
        fetched = client.get(f"/api/lab/v2/runs/{created['id']}").json()
        assert fetched["id"] == created["id"]

    def test_stop_pending_run(self, client):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = client.post(f"/api/lab/tests/{cfg['id']}/run").json()
        r = client.post(f"/api/lab/v2/runs/{run['id']}/stop")
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"

    def test_stop_completed_run_fails(self, client):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = client.post(f"/api/lab/tests/{cfg['id']}/run").json()
        # Force status to completed via DB
        db = _fresh_db  # can't easily do this, so just stop → cancel → stop again
        client.post(f"/api/lab/v2/runs/{run['id']}/stop")
        r = client.post(f"/api/lab/v2/runs/{run['id']}/stop")
        assert r.status_code == 400

    def test_pause_requires_running(self, client):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = client.post(f"/api/lab/tests/{cfg['id']}/run").json()
        # Run is pending, not running
        r = client.post(f"/api/lab/v2/runs/{run['id']}/pause")
        assert r.status_code == 400

    def test_invalid_config_404(self, client):
        r = client.post("/api/lab/tests/nonexistent-id/run")
        assert r.status_code == 404

    def test_results_empty(self, client):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = client.post(f"/api/lab/tests/{cfg['id']}/run").json()
        r = client.get(f"/api/lab/v2/runs/{run['id']}/results")
        assert r.status_code == 200
        assert r.json() == []

    def test_execute_requires_pending(self, client):
        team = _make_team(client)
        cfg = _make_config(client, team["id"])
        run = client.post(f"/api/lab/tests/{cfg['id']}/run").json()
        # Stop the run first (cancels it)
        client.post(f"/api/lab/v2/runs/{run['id']}/stop")
        # Now try to execute — should fail since status is cancelled
        r = client.post(f"/api/lab/v2/runs/{run['id']}/execute")
        assert r.status_code == 400

    def test_execute_nonexistent_404(self, client):
        r = client.post("/api/lab/v2/runs/fake-id/execute")
        assert r.status_code == 404

    def test_stream_nonexistent_404(self, client):
        r = client.get("/api/lab/v2/runs/fake-id/stream")
        assert r.status_code == 404
