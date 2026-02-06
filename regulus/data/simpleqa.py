"""SimpleQA dataset loader for Regulus benchmarking."""

import csv
import random
from pathlib import Path
from dataclasses import dataclass

import requests

SIMPLEQA_URL = "https://openaipublic.blob.core.windows.net/simple-evals/simple_qa_test_set.csv"
CACHE_PATH = Path(__file__).parent / "simple_qa_test_set.csv"


@dataclass
class SimpleQAItem:
    problem: str
    answer: str
    topic: str  # extracted from metadata


def download_dataset() -> Path:
    """Download SimpleQA CSV if not cached locally."""
    if CACHE_PATH.exists():
        return CACHE_PATH
    print(f"Downloading SimpleQA dataset...")
    response = requests.get(SIMPLEQA_URL)
    response.raise_for_status()
    CACHE_PATH.write_text(response.text, encoding="utf-8")
    print(f"Saved to {CACHE_PATH} ({len(response.text)} bytes)")
    return CACHE_PATH


def load_dataset(
    n: int | None = None,
    seed: int = 42,
    topic_filter: str | None = None,
) -> list[SimpleQAItem]:
    """Load SimpleQA dataset.

    Args:
        n: Number of items to sample (None = all)
        seed: Random seed for reproducibility
        topic_filter: Filter by topic substring (e.g. "Science")
    """
    path = download_dataset()

    items = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # metadata contains topic info as JSON string
            topic = ""
            try:
                import json
                meta = json.loads(row.get("metadata", "{}"))
                topic = meta.get("topic", "")
            except (json.JSONDecodeError, TypeError):
                pass

            item = SimpleQAItem(
                problem=row["problem"],
                answer=row["answer"],
                topic=topic,
            )

            if topic_filter and topic_filter.lower() not in topic.lower():
                continue

            items.append(item)

    if n is not None:
        rng = random.Random(seed)
        items = rng.sample(items, min(n, len(items)))

    return items


def get_topics() -> dict[str, int]:
    """Get distribution of topics in dataset."""
    items = load_dataset()
    topics: dict[str, int] = {}
    for item in items:
        t = item.topic or "Unknown"
        topics[t] = topics.get(t, 0) + 1
    return dict(sorted(topics.items(), key=lambda x: -x[1]))
