"""
Regulus AI - MAS Types
=======================

Enums, config, and response types for the Multi-Agent Structured pipeline.
"""

import json
from dataclasses import dataclass, field
from enum import Enum


class Complexity(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class DomainStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskStatus(str, Enum):
    CREATED = "created"
    CLASSIFYING = "classifying"
    DECOMPOSING = "decomposing"
    PROCESSING = "processing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class MASConfig:
    """Configuration for the MAS pipeline."""
    min_domains: int = 4
    weight_threshold: int = 60
    err_required: bool = True
    max_corrections: int = 2
    max_decomposition_depth: int = 3
    default_model: str = "gpt-4o-mini"
    reasoning_model: str = "deepseek"
    domain_timeout_seconds: float = 30.0

    def is_passing(self, total_weight: int, domains_present: int, all_gates_passed: bool) -> bool:
        """Check if results meet all configured thresholds."""
        if domains_present < self.min_domains:
            return False
        if total_weight < self.weight_threshold:
            return False
        if self.err_required and not all_gates_passed:
            return False
        return True


@dataclass
class MASResponse:
    """Final response from the MAS pipeline."""
    query: str = ""
    answer: str = ""
    valid: bool = False
    complexity: str = ""
    components_count: int = 0
    task_table_json: str = ""
    audit_summary: dict = field(default_factory=dict)
    corrections: int = 0
    time_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def reasoning_json(self) -> str:
        """Serialize MAS trail for LabDB compatibility."""
        data = {
            "version": "3.0",
            "pipeline": "mas",
            "complexity": self.complexity,
            "components_count": self.components_count,
            "corrections": self.corrections,
            "audit_summary": self.audit_summary,
            "task_table": self.task_table_json,
        }
        return json.dumps(data, ensure_ascii=False)
