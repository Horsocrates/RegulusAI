"""Benchmark question indexer — loads all questions into DB for fast lookups."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

from regulus.api.models.lab import BenchmarkIndex, BenchmarkQuestion, LabNewDB
from regulus.data.bbeh import get_loader

logger = logging.getLogger(__name__)


class BenchmarkIndexer:
    """Load all benchmark questions into benchmark_questions table."""

    def __init__(self, db: LabNewDB):
        self.db = db

    def index_benchmark(self, benchmark_id: str, force: bool = False) -> BenchmarkIndex:
        """Load ALL questions via loader.load_all(), insert into benchmark_questions.

        Returns the updated BenchmarkIndex.
        """
        existing = self.db.get_benchmark_index(benchmark_id)
        if existing and existing.status == "ready" and not force:
            return existing

        # Mark as indexing
        idx = BenchmarkIndex(
            benchmark_id=benchmark_id,
            status="indexing",
            total_questions=0,
            domains=[],
            loader_version="1.0",
        )
        self.db.upsert_benchmark_index(idx)

        try:
            loader = get_loader(benchmark_id)

            # Delete old questions for re-index
            self.db.delete_benchmark_questions(benchmark_id)

            # Load all examples
            examples = loader.load_all()
            now = datetime.now(timezone.utc).isoformat()

            # Build BenchmarkQuestion records with full text
            questions = []
            for ex in examples:
                target_hash = hashlib.sha256(ex.target.encode()).hexdigest()[:16]
                questions.append(BenchmarkQuestion(
                    id=f"{benchmark_id}:{ex.id}",
                    benchmark_id=benchmark_id,
                    question_id=ex.id,
                    domain=ex.domain,
                    input=ex.input,
                    target=ex.target,
                    target_hash=target_hash,
                    difficulty=ex.metadata.get("difficulty"),
                    tags=ex.metadata.get("tags", []),
                    created_at=now,
                    metadata=ex.metadata,
                ))

            self.db.bulk_insert_benchmark_questions(questions)

            # Collect unique domains
            domains = sorted(set(ex.domain for ex in examples))

            idx.status = "ready"
            idx.total_questions = len(questions)
            idx.domains = domains
            idx.indexed_at = now
            idx.error_message = None
            self.db.upsert_benchmark_index(idx)

            logger.info(
                "Indexed %s: %d questions across %d domains",
                benchmark_id, len(questions), len(domains),
            )
            return idx

        except Exception as e:
            logger.error("Failed to index %s: %s", benchmark_id, e)
            idx.status = "error"
            idx.error_message = str(e)
            self.db.upsert_benchmark_index(idx)
            return idx
