"""
Regulus AI - Data Module
=========================

Benchmark dataset loaders.
"""

from .simpleqa import SimpleQAItem, load_dataset, get_topics

__all__ = ["SimpleQAItem", "load_dataset", "get_topics"]
