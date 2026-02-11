"""Tests for rate limiting middleware and structured error codes."""

import os
import pytest
from fastapi.testclient import TestClient

from regulus.api.main import app
from regulus.api.errors import LabErrorCode, lab_error
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


# ===================================================================
# Structured Error Codes
# ===================================================================


class TestLabError:
    def test_default_status_and_message(self):
        exc = lab_error(LabErrorCode.TEAM_NOT_FOUND, id="abc-123")
        assert exc.status_code == 404
        assert exc.detail["code"] == "LAB_002"
        assert "abc-123" in exc.detail["message"]

    def test_status_override(self):
        exc = lab_error(LabErrorCode.BENCHMARK_LOAD_FAILED, status_code=502, detail="timeout")
        assert exc.status_code == 502
        assert exc.detail["code"] == "LAB_003"
        assert "timeout" in exc.detail["message"]

    def test_config_not_found(self):
        exc = lab_error(LabErrorCode.CONFIG_NOT_FOUND, id="xyz")
        assert exc.status_code == 404
        assert exc.detail["code"] == "LAB_001"

    def test_run_not_found(self):
        exc = lab_error(LabErrorCode.RUN_NOT_FOUND, id="r123")
        assert exc.status_code == 404
        assert exc.detail["code"] == "LAB_011"

    def test_invalid_run_status(self):
        exc = lab_error(LabErrorCode.INVALID_RUN_STATUS, expected="pending", actual="cancelled")
        assert exc.status_code == 400
        assert "pending" in exc.detail["message"]
        assert "cancelled" in exc.detail["message"]

    def test_unknown_code_fallback(self):
        exc = lab_error("UNKNOWN_CODE")
        assert exc.status_code == 500
        assert exc.detail["code"] == "UNKNOWN_CODE"


class TestStructuredErrorResponses:
    """Verify actual API endpoints return structured error bodies."""

    def test_team_not_found_structured(self, client):
        r = client.get("/api/lab/teams/nonexistent-id")
        assert r.status_code == 404
        body = r.json()["detail"]
        assert body["code"] == "LAB_002"
        assert "nonexistent-id" in body["message"]

    def test_config_not_found_structured(self, client):
        r = client.get("/api/lab/tests/nonexistent-id")
        assert r.status_code == 404
        body = r.json()["detail"]
        assert body["code"] == "LAB_001"

    def test_run_not_found_structured(self, client):
        r = client.get("/api/lab/v2/runs/nonexistent-id")
        assert r.status_code == 404
        body = r.json()["detail"]
        assert body["code"] == "LAB_011"

    def test_invalid_run_status_structured(self, client):
        """Stop a cancelled run → should get LAB_012."""
        # Create a run, cancel it, try to cancel again
        team = client.post("/api/lab/teams", json={
            "name": "T",
            "team_lead_config": {"model": "m", "temperature": 0, "max_tokens": 1024, "instructions": "", "enabled": True},
            "agents": {},
        }).json()
        cfg = client.post("/api/lab/tests", json={
            "name": "C",
            "benchmark": "bbeh",
            "domains": ["boolean_expressions"],
            "team_id": team["id"],
        }).json()
        run = client.post(f"/api/lab/tests/{cfg['id']}/run").json()
        client.post(f"/api/lab/v2/runs/{run['id']}/stop")
        r = client.post(f"/api/lab/v2/runs/{run['id']}/stop")
        assert r.status_code == 400
        body = r.json()["detail"]
        assert body["code"] == "LAB_012"


# ===================================================================
# Rate Limiting Middleware
# ===================================================================


class TestRateLimiter:
    def test_disabled_when_env_zero(self, client, monkeypatch):
        """With LAB_RATE_LIMIT_RPM=0, no requests should be rate limited."""
        monkeypatch.setenv("LAB_RATE_LIMIT_RPM", "0")
        for _ in range(100):
            r = client.get("/api/lab/teams")
            assert r.status_code == 200

    def test_enabled_returns_429(self, monkeypatch):
        """With a very low RPM, rapid requests should hit 429."""
        monkeypatch.delenv("LAB_RATE_LIMIT_RPM", raising=False)

        from regulus.api.rate_limit import RateLimitMiddleware
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.add_middleware(RateLimitMiddleware, rpm=2, burst=0)

        @test_app.get("/api/lab/test")
        async def _test_endpoint():
            return {"ok": True}

        c = TestClient(test_app)
        # First 2 should pass
        assert c.get("/api/lab/test").status_code == 200
        assert c.get("/api/lab/test").status_code == 200
        # Third should be rate limited
        r = c.get("/api/lab/test")
        assert r.status_code == 429
        body = r.json()
        assert body["detail"]["code"] == "LAB_009"
        assert "Retry-After" in r.headers

    def test_non_lab_endpoints_not_limited(self, monkeypatch):
        """Non-lab endpoints should never be rate limited."""
        monkeypatch.delenv("LAB_RATE_LIMIT_RPM", raising=False)

        from regulus.api.rate_limit import RateLimitMiddleware
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.add_middleware(RateLimitMiddleware, rpm=1, burst=0)

        @test_app.get("/api/health")
        async def _health():
            return {"ok": True}

        c = TestClient(test_app)
        for _ in range(10):
            assert c.get("/api/health").status_code == 200

    def test_sse_streams_not_limited(self, monkeypatch):
        """SSE stream endpoints should bypass rate limiting."""
        monkeypatch.delenv("LAB_RATE_LIMIT_RPM", raising=False)

        from regulus.api.rate_limit import RateLimitMiddleware
        from fastapi import FastAPI
        from starlette.responses import StreamingResponse

        test_app = FastAPI()
        test_app.add_middleware(RateLimitMiddleware, rpm=1, burst=0)

        @test_app.get("/api/lab/v2/runs/123/stream")
        async def _stream():
            return StreamingResponse(iter(["data: ok\n\n"]), media_type="text/event-stream")

        c = TestClient(test_app)
        for _ in range(5):
            assert c.get("/api/lab/v2/runs/123/stream").status_code == 200

    def test_burst_allowance(self, monkeypatch):
        """Burst should allow extra requests above RPM."""
        monkeypatch.delenv("LAB_RATE_LIMIT_RPM", raising=False)

        from regulus.api.rate_limit import RateLimitMiddleware
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.add_middleware(RateLimitMiddleware, rpm=2, burst=3)

        @test_app.get("/api/lab/test")
        async def _test_endpoint():
            return {"ok": True}

        c = TestClient(test_app)
        # RPM=2, burst=3 → should allow 5 requests
        for i in range(5):
            assert c.get("/api/lab/test").status_code == 200, f"Request {i+1} should pass"
        # 6th should be rate limited
        assert c.get("/api/lab/test").status_code == 429
