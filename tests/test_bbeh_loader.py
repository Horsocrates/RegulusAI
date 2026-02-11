"""
Tests for the new BBEHLoader and benchmark infrastructure.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from regulus.data.base import BenchmarkLoader, BenchmarkExample, BenchmarkInfo
from regulus.data.bbeh import (
    BBEHLoader,
    BBEHItem,
    BBEH_TASKS,
    BENCHMARK_REGISTRY,
    get_loader,
    load_dataset,
    load_bbeh_mini,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_TASK_DATA = {
    "examples": [
        {"input": f"Question {i}", "target": f"Answer {i}"}
        for i in range(5)
    ]
}


@pytest.fixture
def tmp_cache(tmp_path):
    """Provide a temp cache directory."""
    return tmp_path / "bbeh_cache"


@pytest.fixture
def loader():
    return BBEHLoader()


@pytest.fixture
def cached_domain(tmp_cache):
    """Pre-cache boolean_expressions task data."""
    tmp_cache.mkdir(parents=True, exist_ok=True)
    cache_file = tmp_cache / "boolean_expressions.json"
    cache_file.write_text(json.dumps(FAKE_TASK_DATA))
    return tmp_cache


# ---------------------------------------------------------------------------
# BBEHLoader.info()
# ---------------------------------------------------------------------------


class TestBBEHLoaderInfo:
    def test_returns_benchmark_info(self, loader):
        info = loader.info()
        assert isinstance(info, BenchmarkInfo)
        assert info.id == "bbeh"
        assert info.name == "BIG-Bench Extra Hard"
        assert info.total_examples == 4520
        assert len(info.domains) == 23
        assert "boolean_expressions" in info.domains
        assert "zebra_puzzles" in info.domains


# ---------------------------------------------------------------------------
# BBEHLoader.load_domain()
# ---------------------------------------------------------------------------


class TestBBEHLoaderDomain:
    def test_load_domain_from_cache(self, loader, cached_domain):
        examples = loader.load_domain("boolean_expressions", cache_dir=cached_domain)
        assert len(examples) == 5
        assert all(isinstance(e, BenchmarkExample) for e in examples)
        assert examples[0].id == "boolean_expressions_0000"
        assert examples[0].input == "Question 0"
        assert examples[0].target == "Answer 0"
        assert examples[0].domain == "boolean_expressions"

    def test_load_domain_unknown_raises(self, loader, tmp_cache):
        with pytest.raises(ValueError, match="Unknown BBEH domain"):
            loader.load_domain("nonexistent_domain", cache_dir=tmp_cache)

    def test_load_domain_downloads_and_caches(self, loader, tmp_cache):
        """When cache miss, download from URL and save to cache."""
        with patch.object(BBEHLoader, "_download", return_value=FAKE_TASK_DATA) as mock_dl:
            examples = loader.load_domain("boolean_expressions", cache_dir=tmp_cache)

        mock_dl.assert_called_once()
        assert len(examples) == 5
        # File should now be cached
        assert (tmp_cache / "boolean_expressions.json").exists()

    def test_load_domain_uses_cache_on_second_call(self, loader, tmp_cache):
        """Second call should use cache (no download)."""
        with patch.object(BBEHLoader, "_download", return_value=FAKE_TASK_DATA):
            loader.load_domain("boolean_expressions", cache_dir=tmp_cache)

        # Second call — no download
        with patch.object(BBEHLoader, "_download") as mock_dl:
            examples = loader.load_domain("boolean_expressions", cache_dir=tmp_cache)

        mock_dl.assert_not_called()
        assert len(examples) == 5


# ---------------------------------------------------------------------------
# BBEHLoader.load_by_ids()
# ---------------------------------------------------------------------------


class TestBBEHLoaderByIds:
    def test_load_by_ids_filters(self, loader, cached_domain):
        target_ids = ["boolean_expressions_0001", "boolean_expressions_0003"]
        results = loader.load_by_ids(target_ids, cache_dir=cached_domain)
        assert len(results) == 2
        assert {r.id for r in results} == set(target_ids)

    def test_load_by_ids_empty(self, loader, cached_domain):
        results = loader.load_by_ids([], cache_dir=cached_domain)
        assert results == []

    def test_load_by_ids_unknown_domain_skipped(self, loader, cached_domain):
        results = loader.load_by_ids(["fake_domain_0001"], cache_dir=cached_domain)
        assert results == []


# ---------------------------------------------------------------------------
# BBEHLoader.load_all()
# ---------------------------------------------------------------------------


class TestBBEHLoaderAll:
    def test_load_all_iterates_all_tasks(self, loader, tmp_cache):
        """load_all should call load_domain for each of the 23 tasks."""
        with patch.object(loader, "load_domain", return_value=[]) as mock_ld:
            loader.load_all(cache_dir=tmp_cache)

        assert mock_ld.call_count == len(BBEH_TASKS)
        called_domains = [call.args[0] for call in mock_ld.call_args_list]
        assert called_domains == BBEH_TASKS


# ---------------------------------------------------------------------------
# get_loader() factory
# ---------------------------------------------------------------------------


class TestGetLoader:
    def test_get_loader_bbeh(self):
        loader = get_loader("bbeh")
        assert isinstance(loader, BBEHLoader)

    def test_get_loader_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown benchmark"):
            get_loader("nonexistent_benchmark")


# ---------------------------------------------------------------------------
# BENCHMARK_REGISTRY
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_bbeh_in_registry(self):
        assert "bbeh" in BENCHMARK_REGISTRY
        assert BENCHMARK_REGISTRY["bbeh"] is BBEHLoader


# ---------------------------------------------------------------------------
# Backward compat: load_dataset(), load_bbeh_mini(), BBEHItem
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    def test_bbeh_item_properties(self):
        item = BBEHItem(input="Q", target="A")
        assert item.problem == "Q"
        assert item.answer == "A"

    def test_load_dataset_with_mock(self):
        """load_dataset still works and returns BBEHItem list."""
        fake_data = {
            "examples": [
                {"input": f"Q{i}", "target": f"A{i}"} for i in range(10)
            ]
        }
        with patch("regulus.data.bbeh._load_from_cache", return_value=fake_data):
            items = load_dataset(n=5)

        assert len(items) == 5
        assert all(isinstance(i, BBEHItem) for i in items)

    def test_load_bbeh_mini_with_mock(self):
        fake_data = {
            "examples": [
                {"input": f"Q{i}", "target": f"A{i}"} for i in range(20)
            ]
        }
        with patch("regulus.data.bbeh._load_from_cache", return_value=fake_data):
            items = load_bbeh_mini(n=3)

        assert len(items) == 3

    def test_load_dataset_exclude_tables(self):
        fake_data = {
            "examples": [
                {"input": "I have a table with foo", "target": "42"},
                {"input": "Normal question", "target": "yes"},
            ]
        }
        with patch("regulus.data.bbeh._load_from_cache", return_value=fake_data):
            items = load_dataset(exclude_tables=True)

        assert len(items) == 1
        assert items[0].input == "Normal question"


# ---------------------------------------------------------------------------
# load_sample (inherited from BenchmarkLoader)
# ---------------------------------------------------------------------------


class TestLoadSample:
    def test_load_sample_uses_domains(self, loader, cached_domain):
        examples = loader.load_sample(
            n=3,
            domains=["boolean_expressions"],
            cache_dir=cached_domain,
        )
        assert len(examples) == 3
        assert all(e.domain == "boolean_expressions" for e in examples)

    def test_load_sample_respects_n(self, loader, cached_domain):
        examples = loader.load_sample(n=2, cache_dir=cached_domain, domains=["boolean_expressions"])
        assert len(examples) == 2
