"""
Regulus AI - Data Module
=========================

Benchmark dataset loaders.
"""

from .simpleqa import SimpleQAItem, load_dataset, get_topics
from .base import BenchmarkLoader, BenchmarkExample, BenchmarkInfo
from .bbeh import BBEHLoader, BENCHMARK_REGISTRY, get_loader
from .simpleqa_loader import SimpleQALoader

__all__ = [
    "SimpleQAItem",
    "load_dataset",
    "get_topics",
    "BenchmarkLoader",
    "BenchmarkExample",
    "BenchmarkInfo",
    "BBEHLoader",
    "SimpleQALoader",
    "BENCHMARK_REGISTRY",
    "get_loader",
]
