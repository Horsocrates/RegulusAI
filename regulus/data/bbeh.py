"""
BBEH (Big-Bench Extra Hard) Dataset Loader
============================================

Loads reasoning benchmark from Google DeepMind's BBEH dataset.
https://github.com/google-deepmind/bbeh

BBEH tests complex reasoning abilities across 23 tasks:
- Logic puzzles, Boolean expressions, Causal understanding
- Multi-step arithmetic, Temporal reasoning, and more.
"""

from __future__ import annotations

import json
import random
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .base import BenchmarkLoader, BenchmarkExample, BenchmarkInfo

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "bbeh_cache"

BBEH_BASE_URL = "https://raw.githubusercontent.com/google-deepmind/bbeh/main/bbeh"
BBEH_MINI_URL = f"{BBEH_BASE_URL}/mini/data.json"

BBEH_TASKS = [
    "boardgame_qa",
    "boolean_expressions",
    "buggy_tables",
    "causal_understanding",
    "disambiguation_qa",
    "dyck_languages",
    "geometric_shapes",
    "hyperbaton",
    "linguini",
    "movie_recommendation",
    "multistep_arithmetic",
    "nycc",
    "object_counting",
    "object_properties",
    "sarc_triples",
    "shuffled_objects",
    "spatial_reasoning",
    "sportqa",
    "temporal_sequence",
    "time_arithmetic",
    "web_of_lies",
    "word_sorting",
    "zebra_puzzles",
]

# ---------------------------------------------------------------------------
# BBEHLoader (new BenchmarkLoader interface)
# ---------------------------------------------------------------------------


class BBEHLoader(BenchmarkLoader):
    """Loader for BIG-Bench Extra Hard benchmark (23 per-domain tasks)."""

    def info(self) -> BenchmarkInfo:
        return BenchmarkInfo(
            id="bbeh",
            name="BIG-Bench Extra Hard",
            description="Challenging reasoning benchmark from Google DeepMind",
            source="https://github.com/google-deepmind/bbeh",
            total_examples=4520,  # 23 tasks, ~200 each (disambiguation_qa has 120)
            domains=list(BBEH_TASKS),
            version="1.0",
        )

    # -- load_all ---------------------------------------------------------

    def load_all(self, cache_dir: Optional[Path] = None) -> List[BenchmarkExample]:
        cache_dir = cache_dir or CACHE_DIR
        examples: list[BenchmarkExample] = []
        for task in BBEH_TASKS:
            examples.extend(self.load_domain(task, cache_dir))
        return examples

    # -- load_domain ------------------------------------------------------

    def load_domain(
        self, domain: str, cache_dir: Optional[Path] = None
    ) -> List[BenchmarkExample]:
        if domain not in BBEH_TASKS:
            raise ValueError(
                f"Unknown BBEH domain: {domain}. "
                f"Valid domains: {', '.join(BBEH_TASKS)}"
            )

        cache_dir = cache_dir or CACHE_DIR
        data = self._fetch_task(domain, cache_dir)

        examples: list[BenchmarkExample] = []
        for i, item in enumerate(data.get("examples", [])):
            examples.append(
                BenchmarkExample(
                    id=f"{domain}_{i:04d}",
                    input=item["input"],
                    target=item["target"],
                    domain=domain,
                    metadata={"task": domain, "index": i},
                )
            )
        return examples

    # -- load_by_ids ------------------------------------------------------

    def load_by_ids(
        self, ids: List[str], cache_dir: Optional[Path] = None
    ) -> List[BenchmarkExample]:
        cache_dir = cache_dir or CACHE_DIR
        # Parse IDs to determine which domains to load
        domains_needed: set[str] = set()
        for example_id in ids:
            # IDs look like "boolean_expressions_0003"
            parts = example_id.rsplit("_", 1)
            if len(parts) == 2:
                domains_needed.add(parts[0])

        all_examples: list[BenchmarkExample] = []
        for domain in domains_needed:
            if domain in BBEH_TASKS:
                all_examples.extend(self.load_domain(domain, cache_dir))

        id_set = set(ids)
        return [ex for ex in all_examples if ex.id in id_set]

    # -- internal helpers -------------------------------------------------

    def _fetch_task(self, task: str, cache_dir: Path) -> dict:
        """Fetch a single task JSON, using cache when available."""
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{task}.json"

        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

        data = self._download(
            f"{BBEH_BASE_URL}/benchmark_tasks/bbeh_{task}/task.json"
        )

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        return data

    @staticmethod
    def _download(url: str) -> dict:
        req = urllib.request.Request(url, headers={"User-Agent": "RegulusAI/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())


# ---------------------------------------------------------------------------
# Benchmark registry & factory
# ---------------------------------------------------------------------------

BENCHMARK_REGISTRY: dict[str, type[BenchmarkLoader] | None] = {
    "bbeh": BBEHLoader,
    "simpleqa": None,  # lazy import to avoid circular/heavy imports at module level
    "hle": None,       # lazy import
}


def _ensure_registry():
    """Lazily populate registry entries that use deferred imports."""
    if BENCHMARK_REGISTRY.get("simpleqa") is None:
        from .simpleqa_loader import SimpleQALoader
        BENCHMARK_REGISTRY["simpleqa"] = SimpleQALoader
    if BENCHMARK_REGISTRY.get("hle") is None:
        from .hle_loader import HLELoader
        BENCHMARK_REGISTRY["hle"] = HLELoader


def get_loader(benchmark_id: str) -> BenchmarkLoader:
    """Get loader for benchmark by ID."""
    _ensure_registry()
    if benchmark_id not in BENCHMARK_REGISTRY:
        raise ValueError(
            f"Unknown benchmark: {benchmark_id}. "
            f"Available: {', '.join(BENCHMARK_REGISTRY)}"
        )
    return BENCHMARK_REGISTRY[benchmark_id]()


# ---------------------------------------------------------------------------
# Backward-compatible API (used by regulus/lab/runner.py, regulus/api/main.py)
# ---------------------------------------------------------------------------


@dataclass
class BBEHItem:
    """Single BBEH benchmark item (legacy format)."""
    input: str
    target: str

    @property
    def problem(self) -> str:
        return self.input

    @property
    def answer(self) -> str:
        return self.target


def _load_from_cache() -> Optional[dict]:
    cache_file = CACHE_DIR / "mini.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _save_to_cache(data: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / "mini.json"
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def load_bbeh_mini(n: Optional[int] = None, seed: int = 42) -> List[BBEHItem]:
    """
    Load BBEH mini benchmark (460 examples from all tasks).

    Args:
        n: Number of examples to return. None = all.
        seed: Random seed for sampling (if n < total).

    Returns:
        List of BBEHItem objects.
    """
    data = _load_from_cache()

    if data is None:
        print("[BBEH] Downloading mini dataset...")
        req = urllib.request.Request(
            BBEH_MINI_URL, headers={"User-Agent": "RegulusAI/1.0"}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
        _save_to_cache(data)
        print(f"[BBEH] Downloaded and cached {len(data['examples'])} examples")

    examples = data["examples"]
    items = [BBEHItem(input=ex["input"], target=ex["target"]) for ex in examples]

    if n is not None and n < len(items):
        rng = random.Random(seed)
        items = rng.sample(items, n)

    return items


def load_dataset(
    n: Optional[int] = None, seed: int = 42, exclude_tables: bool = False
) -> List[BBEHItem]:
    """
    Unified interface matching simpleqa.load_dataset().

    Args:
        n: Number of examples to return. None = all.
        seed: Random seed for sampling.
        exclude_tables: If True, exclude buggy_tables tasks.

    Returns:
        List of BBEHItem objects.
    """
    items = load_bbeh_mini(n=None, seed=seed)

    if exclude_tables:
        items = [
            item for item in items if not item.input.startswith("I have a table with")
        ]

    if n is not None and n < len(items):
        rng = random.Random(seed)
        items = rng.sample(items, n)

    return items


def total_count() -> int:
    """Return total number of questions in dataset."""
    return len(load_dataset())


def get_categories() -> list[str]:
    """Return list of task categories (BBEH is a single combined mini set)."""
    return ["reasoning"]


if __name__ == "__main__":
    items = load_dataset(n=5)
    print(f"Loaded {len(items)} items")
    for i, item in enumerate(items):
        print(f"\n[{i}] Input: {item.input[:80]}...")
        print(f"    Target: {item.target}")
