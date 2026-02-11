"""Tests for Lab Benchmarks API endpoints."""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from regulus.api.main import app
from regulus.data.base import BenchmarkExample, BenchmarkInfo


@pytest.fixture
def client():
    return TestClient(app)


def _mock_info():
    return BenchmarkInfo(
        id="test-bench",
        name="Test Benchmark",
        description="A test benchmark",
        source="https://example.com",
        total_examples=100,
        domains=["math", "logic"],
        version="1.0",
    )


def _mock_examples(domain="math", count=3):
    return [
        BenchmarkExample(
            id=f"{domain}-{i}",
            input=f"Question {i} about {domain}?",
            target=f"Answer {i}",
            domain=domain,
        )
        for i in range(count)
    ]


def _mock_loader():
    loader = MagicMock()
    loader.info.return_value = _mock_info()
    loader.load_domain.side_effect = lambda d, **kw: _mock_examples(d)
    loader.load_sample.side_effect = lambda n, domains=None, **kw: _mock_examples("math", n)
    return loader


# ===================================================================
# List benchmarks
# ===================================================================


class TestListBenchmarks:
    def test_list_returns_benchmarks(self, client):
        """List endpoint returns at least BBEH."""
        r = client.get("/api/lab/benchmarks")
        assert r.status_code == 200
        benchmarks = r.json()
        assert isinstance(benchmarks, list)
        ids = [b["id"] for b in benchmarks]
        assert "bbeh" in ids

    def test_list_includes_simpleqa(self, client):
        """After registry init, simpleqa should appear."""
        r = client.get("/api/lab/benchmarks")
        assert r.status_code == 200
        ids = [b["id"] for b in r.json()]
        assert "simpleqa" in ids

    def test_benchmark_summary_fields(self, client):
        """Each summary has required fields."""
        r = client.get("/api/lab/benchmarks")
        for b in r.json():
            assert "id" in b
            assert "name" in b
            assert "description" in b
            assert "total_examples" in b
            assert "domains_count" in b
            assert "version" in b


# ===================================================================
# Get benchmark detail
# ===================================================================


class TestGetBenchmark:
    def test_get_bbeh(self, client):
        r = client.get("/api/lab/benchmarks/bbeh")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == "bbeh"
        assert "domains" in data
        assert len(data["domains"]) > 0

    def test_get_simpleqa(self, client):
        r = client.get("/api/lab/benchmarks/simpleqa")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == "simpleqa"
        assert "domains" in data

    def test_get_nonexistent(self, client):
        r = client.get("/api/lab/benchmarks/nonexistent")
        assert r.status_code == 404


# ===================================================================
# Get domains
# ===================================================================


class TestGetDomains:
    @patch("regulus.api.routers.lab.benchmarks.get_loader")
    def test_domains_list(self, mock_get_loader, client):
        mock_get_loader.return_value = _mock_loader()
        r = client.get("/api/lab/benchmarks/test-bench/domains")
        assert r.status_code == 200
        domains = r.json()
        assert len(domains) == 2
        names = [d["name"] for d in domains]
        assert "math" in names
        assert "logic" in names

    def test_domains_404(self, client):
        r = client.get("/api/lab/benchmarks/nonexistent/domains")
        assert r.status_code == 404


# ===================================================================
# Sample questions
# ===================================================================


class TestSampleQuestions:
    @patch("regulus.api.routers.lab.benchmarks.get_loader")
    def test_sample_default(self, mock_get_loader, client):
        mock_get_loader.return_value = _mock_loader()
        r = client.get("/api/lab/benchmarks/test-bench/sample")
        assert r.status_code == 200
        samples = r.json()
        assert len(samples) == 5
        for s in samples:
            assert "id" in s
            assert "input" in s
            assert "target" in s
            assert "domain" in s

    @patch("regulus.api.routers.lab.benchmarks.get_loader")
    def test_sample_custom_count(self, mock_get_loader, client):
        mock_get_loader.return_value = _mock_loader()
        r = client.get("/api/lab/benchmarks/test-bench/sample?n=3")
        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_sample_404(self, client):
        r = client.get("/api/lab/benchmarks/nonexistent/sample")
        assert r.status_code == 404


# ===================================================================
# Load benchmark
# ===================================================================


class TestLoadBenchmark:
    @patch("regulus.api.routers.lab.benchmarks.get_loader")
    def test_load_success(self, mock_get_loader, client):
        loader = _mock_loader()
        loader.load_all.return_value = _mock_examples("math", 10)
        mock_get_loader.return_value = loader
        r = client.post("/api/lab/benchmarks/test-bench/load")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["loaded_examples"] == 10
        assert data["benchmark_id"] == "test-bench"

    def test_load_404(self, client):
        r = client.post("/api/lab/benchmarks/nonexistent/load")
        assert r.status_code == 404

    @patch("regulus.api.routers.lab.benchmarks.get_loader")
    def test_load_failure(self, mock_get_loader, client):
        loader = _mock_loader()
        loader.load_all.side_effect = RuntimeError("Download failed")
        mock_get_loader.return_value = loader
        r = client.post("/api/lab/benchmarks/test-bench/load")
        assert r.status_code == 502
