"""
BBEH (Big-Bench Extra Hard) Dataset Loader
============================================

Loads reasoning benchmark from Google DeepMind's BBEH dataset.
https://github.com/google-deepmind/bbeh

BBEH tests complex reasoning abilities:
- Logic puzzles
- Boolean expressions
- Causal understanding
- Multi-step arithmetic
- Temporal reasoning
- And more...
"""

from __future__ import annotations

import json
import random
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

# Cache directory for downloaded data
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "bbeh_cache"

BBEH_MINI_URL = "https://raw.githubusercontent.com/google-deepmind/bbeh/main/bbeh/mini/data.json"


@dataclass
class BBEHItem:
    """Single BBEH benchmark item."""
    input: str  # The problem/question
    target: str  # Expected answer

    @property
    def problem(self) -> str:
        """Alias for input to match SimpleQA interface."""
        return self.input

    @property
    def answer(self) -> str:
        """Alias for target to match SimpleQA interface."""
        return self.target


def _load_from_cache() -> Optional[dict]:
    """Load cached BBEH data if available."""
    cache_file = CACHE_DIR / "mini.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _save_to_cache(data: dict):
    """Save BBEH data to cache."""
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
    # Try cache first
    data = _load_from_cache()

    if data is None:
        # Download from GitHub
        print("[BBEH] Downloading mini dataset...")
        req = urllib.request.Request(
            BBEH_MINI_URL,
            headers={"User-Agent": "RegulusAI/1.0"}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
        _save_to_cache(data)
        print(f"[BBEH] Downloaded and cached {len(data['examples'])} examples")

    examples = data["examples"]

    # Convert to BBEHItem objects
    items = [
        BBEHItem(input=ex["input"], target=ex["target"])
        for ex in examples
    ]

    # Sample if n specified
    if n is not None and n < len(items):
        rng = random.Random(seed)
        items = rng.sample(items, n)

    return items


def load_dataset(
    n: Optional[int] = None,
    seed: int = 42,
    exclude_tables: bool = False
) -> List[BBEHItem]:
    """
    Unified interface matching simpleqa.load_dataset().

    Args:
        n: Number of examples to return. None = all.
        seed: Random seed for sampling.
        exclude_tables: If True, exclude buggy_tables tasks (require precise calculations).

    Returns:
        List of BBEHItem objects.
    """
    items = load_bbeh_mini(n=None, seed=seed)  # Load all first

    if exclude_tables:
        # Filter out buggy_tables tasks (they start with "I have a table with")
        items = [
            item for item in items
            if not item.input.startswith("I have a table with")
        ]

    # Sample if n specified
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
    # Test loading
    items = load_dataset(n=5)
    print(f"Loaded {len(items)} items")
    for i, item in enumerate(items):
        print(f"\n[{i}] Input: {item.input[:80]}...")
        print(f"    Target: {item.target}")
