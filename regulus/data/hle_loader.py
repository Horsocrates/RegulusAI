"""HLE (Humanity's Last Exam) benchmark loader.

Downloads full dataset from HuggingFace (cais/hle), filters to text-only
questions (no images), and caches locally as JSON.

Cache: data/hle_cache/hle_full.json
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import List, Optional

from .base import BenchmarkLoader, BenchmarkExample, BenchmarkInfo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "hle_cache"
CACHE_FILE = CACHE_DIR / "hle_full.json"

HF_DATASET = "cais/hle"
HF_TOKEN = os.environ.get("HF_TOKEN", "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")


class HLELoader(BenchmarkLoader):
    """Loader for Humanity's Last Exam benchmark (full HuggingFace dataset)."""

    def info(self) -> BenchmarkInfo:
        data = self._ensure_cached()
        domains = sorted(set(q["category"] for q in data))
        return BenchmarkInfo(
            id="hle",
            name="Humanity's Last Exam",
            description="Expert-level questions spanning all academic disciplines (CAIS/Scale AI)",
            source="https://huggingface.co/datasets/cais/hle",
            total_examples=len(data),
            domains=domains,
            version="1.0",
        )

    def load_all(self, cache_dir: Optional[Path] = None) -> List[BenchmarkExample]:
        data = self._ensure_cached()
        return [self._to_example(q) for q in data]

    def load_domain(self, domain: str, cache_dir: Optional[Path] = None) -> List[BenchmarkExample]:
        data = self._ensure_cached()
        domain_qs = [q for q in data if q["category"] == domain]
        if not domain_qs:
            available = sorted(set(q["category"] for q in data))
            raise ValueError(
                f"No examples for domain '{domain}'. "
                f"Available: {', '.join(available)}"
            )
        return [self._to_example(q) for q in domain_qs]

    def load_by_ids(self, ids: List[str], cache_dir: Optional[Path] = None) -> List[BenchmarkExample]:
        all_examples = self.load_all(cache_dir)
        id_set = set(ids)
        return [ex for ex in all_examples if ex.id in id_set]

    # -- internal helpers -------------------------------------------------

    def _ensure_cached(self) -> list[dict]:
        """Load from cache or download from HuggingFace."""
        if CACHE_FILE.exists():
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return self._download_and_cache()

    def _download_and_cache(self) -> list[dict]:
        """Download full HLE from HuggingFace, filter text-only, cache as JSON."""
        logger.info("Downloading HLE dataset from HuggingFace...")
        try:
            from datasets import load_dataset
        except ImportError:
            raise RuntimeError(
                "HLE loader requires the 'datasets' package. "
                "Install with: pip install datasets"
            )

        ds = load_dataset(HF_DATASET, split="test", token=HF_TOKEN)

        # Filter: text-only (no image questions)
        items = []
        for row in ds:
            if row.get("image"):
                continue
            items.append({
                "id": row["id"],
                "question": row["question"],
                "answer": row["answer"],
                "answer_type": row.get("answer_type", ""),
                "category": row.get("category", "Other"),
                "raw_subject": row.get("raw_subject", ""),
            })

        logger.info("Downloaded %d text-only HLE questions", len(items))

        # Cache
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)

        return items

    @staticmethod
    def _to_example(q: dict) -> BenchmarkExample:
        return BenchmarkExample(
            id=q["id"],
            input=q["question"],
            target=q.get("answer", ""),
            domain=q.get("category", "Other"),
            metadata={
                "answer_type": q.get("answer_type", ""),
                "raw_subject": q.get("raw_subject", ""),
                "category": q.get("category", ""),
            },
        )
