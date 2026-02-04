"""
Regulus AI - TruthfulQA Dataset Loader
========================================

Downloads and parses the TruthfulQA benchmark (817 adversarial questions
designed to elicit false answers from language models).

Reference: Lin, Hilton, Evans (2022) "TruthfulQA: Measuring How Models
Mimic Human Falsehoods" https://arxiv.org/abs/2109.07958

Categories with high hallucination rates:
    Misconceptions, Conspiracies, Superstitions, Paranormal,
    Indexical Error: Identity, Distraction, Finance, Health, Law
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import httpx

TRUTHFULQA_URL = (
    "https://raw.githubusercontent.com/sylinrl/TruthfulQA/main/TruthfulQA.csv"
)


@dataclass
class TruthfulQAItem:
    """A single TruthfulQA benchmark question."""
    category: str
    question: str
    best_answer: str
    correct_answers: List[str]
    incorrect_answers: List[str]
    source: str

    @property
    def difficulty(self) -> int:
        """Proxy for difficulty: more incorrect answers = harder for LLMs."""
        return len(self.incorrect_answers)


class TruthfulQADataset:
    """
    Load and query the TruthfulQA benchmark (817 adversarial questions).

    Usage:
        ds = TruthfulQADataset()
        ds.load()
        misconceptions = ds.by_category("Misconceptions")
        hardest = ds.hardest(10)
    """

    def __init__(self, cache_dir: Path = Path("data")) -> None:
        self.cache_dir = cache_dir
        self.cache_path = cache_dir / "TruthfulQA.csv"
        self.items: List[TruthfulQAItem] = []

    # ----------------------------------------------------------
    # Download & parse
    # ----------------------------------------------------------

    def download(self) -> Path:
        """Download dataset CSV if not already cached."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if not self.cache_path.exists():
            response = httpx.get(TRUTHFULQA_URL, follow_redirects=True)
            response.raise_for_status()
            self.cache_path.write_bytes(response.content)
        return self.cache_path

    def load(self) -> List[TruthfulQAItem]:
        """Download (if needed) and parse the CSV into TruthfulQAItem list."""
        self.download()
        self.items = []

        with open(self.cache_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                correct_raw = row.get("Correct Answers", "")
                incorrect_raw = row.get("Incorrect Answers", "")

                self.items.append(TruthfulQAItem(
                    category=row.get("Category", "").strip(),
                    question=row.get("Question", "").strip(),
                    best_answer=row.get("Best Answer", "").strip(),
                    correct_answers=_split_answers(correct_raw),
                    incorrect_answers=_split_answers(incorrect_raw),
                    source=row.get("Source", "").strip(),
                ))

        return self.items

    # ----------------------------------------------------------
    # Query helpers
    # ----------------------------------------------------------

    def by_category(self, category: str) -> List[TruthfulQAItem]:
        """Filter items whose category contains the given substring (case-insensitive)."""
        cat_lower = category.lower()
        return [item for item in self.items if cat_lower in item.category.lower()]

    def hardest(self, n: int = 10) -> List[TruthfulQAItem]:
        """Return the n items with the most incorrect answers (hardest for LLMs)."""
        return sorted(
            self.items,
            key=lambda x: x.difficulty,
            reverse=True,
        )[:n]

    def categories(self) -> List[str]:
        """Return sorted list of unique categories in the dataset."""
        return sorted({item.category for item in self.items})

    def sample(self, n: int = 5, category: str | None = None) -> List[TruthfulQAItem]:
        """Return the first n items, optionally filtered by category."""
        pool = self.by_category(category) if category else self.items
        return pool[:n]


def _split_answers(raw: str) -> List[str]:
    """Split semicolon-separated answer strings, stripping whitespace."""
    if not raw.strip():
        return []
    return [a.strip() for a in raw.split(";") if a.strip()]
