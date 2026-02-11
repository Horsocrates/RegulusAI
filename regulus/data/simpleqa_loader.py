"""SimpleQA benchmark loader adapter.

Wraps the existing simpleqa.py into the BenchmarkLoader ABC so it can
be registered in BENCHMARK_REGISTRY alongside BBEHLoader.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .base import BenchmarkLoader, BenchmarkExample, BenchmarkInfo
from .simpleqa import (
    SimpleQAItem,
    download_dataset,
    load_dataset as _load_raw,
    get_categories,
)


class SimpleQALoader(BenchmarkLoader):
    """BenchmarkLoader adapter for OpenAI SimpleQA dataset."""

    def info(self) -> BenchmarkInfo:
        return BenchmarkInfo(
            id="simpleqa",
            name="SimpleQA",
            description="OpenAI SimpleQA — short factual Q&A pairs across diverse topics.",
            source="https://openaipublic.blob.core.windows.net/simple-evals/simple_qa_test_set.csv",
            total_examples=4326,  # known dataset size
            domains=get_categories(),
            version="1.0",
        )

    def load_all(self, cache_dir: Optional[Path] = None) -> List[BenchmarkExample]:
        items = _load_raw()
        return [self._to_example(i, item) for i, item in enumerate(items)]

    def load_domain(self, domain: str, cache_dir: Optional[Path] = None) -> List[BenchmarkExample]:
        items = _load_raw(topic_filter=domain)
        if not items:
            available = get_categories()
            raise ValueError(
                f"No examples found for domain '{domain}'. "
                f"Available: {', '.join(available[:10])}"
            )
        return [self._to_example(i, item) for i, item in enumerate(items)]

    def load_by_ids(self, ids: List[str], cache_dir: Optional[Path] = None) -> List[BenchmarkExample]:
        all_examples = self.load_all(cache_dir)
        id_set = set(ids)
        return [ex for ex in all_examples if ex.id in id_set]

    @staticmethod
    def _to_example(index: int, item: SimpleQAItem) -> BenchmarkExample:
        return BenchmarkExample(
            id=f"simpleqa-{index}",
            input=item.problem,
            target=item.answer,
            domain=item.topic or "Unknown",
            metadata={"topic": item.topic},
        )
