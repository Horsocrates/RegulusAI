"""
Benchmark Loader ABC and shared data types.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class BenchmarkInfo:
    """Benchmark metadata."""
    id: str
    name: str
    description: str
    source: str
    total_examples: int
    domains: List[str]
    version: str


@dataclass
class BenchmarkExample:
    """Universal benchmark example structure."""
    id: str
    input: str
    target: str
    domain: str
    metadata: dict = field(default_factory=dict)


class BenchmarkLoader(ABC):
    """Base class for benchmark loaders."""

    @abstractmethod
    def info(self) -> BenchmarkInfo:
        """Return benchmark metadata."""
        ...

    @abstractmethod
    def load_all(self, cache_dir: Optional[Path] = None) -> List[BenchmarkExample]:
        """Load all examples."""
        ...

    @abstractmethod
    def load_domain(self, domain: str, cache_dir: Optional[Path] = None) -> List[BenchmarkExample]:
        """Load examples for specific domain."""
        ...

    @abstractmethod
    def load_by_ids(self, ids: List[str], cache_dir: Optional[Path] = None) -> List[BenchmarkExample]:
        """Load specific examples by ID."""
        ...

    def load_sample(
        self,
        n: int,
        domains: Optional[List[str]] = None,
        shuffle: bool = True,
        seed: int = 42,
        cache_dir: Optional[Path] = None,
    ) -> List[BenchmarkExample]:
        """Load random sample of n examples."""
        import random

        if domains:
            examples = []
            for domain in domains:
                examples.extend(self.load_domain(domain, cache_dir))
        else:
            examples = self.load_all(cache_dir)

        if shuffle:
            rng = random.Random(seed)
            rng.shuffle(examples)

        return examples[:n]
