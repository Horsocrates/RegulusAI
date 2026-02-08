"""
Regulus AI - MAS (Multi-Agent Structured) Pipeline
====================================================

Structured domain-based reasoning with per-domain workers.
"""

from regulus.mas.types import (
    Complexity,
    DomainStatus,
    TaskStatus,
    MASConfig,
    MASResponse,
)
from regulus.mas.table import (
    DomainOutput,
    Component,
    TaskTable,
)
from regulus.mas.contracts import (
    DomainInput,
    D1Input, D1Output,
    D2Input, D2Output,
    D3Input, D3Output,
    D4Input, D4Output,
    D5Input, D5Output,
    D6Input, D6Output,
    DOMAIN_INPUT_TYPES,
    DOMAIN_OUTPUT_TYPES,
)
from regulus.mas.workers import DomainWorker, MockWorker
from regulus.mas.routing import DomainRoute, RoutingConfig
from regulus.mas.orchestrator import MASOrchestrator
from regulus.mas.llm_worker import LLMWorker, WorkerError
from regulus.mas.worker_factory import (
    MODEL_REGISTRY,
    create_worker,
    create_workers_from_routing,
    clear_client_cache,
)
from regulus.mas.prompts import DOMAIN_PROMPTS

__all__ = [
    "Complexity", "DomainStatus", "TaskStatus",
    "MASConfig", "MASResponse",
    "DomainOutput", "Component", "TaskTable",
    "DomainInput",
    "D1Input", "D1Output",
    "D2Input", "D2Output",
    "D3Input", "D3Output",
    "D4Input", "D4Output",
    "D5Input", "D5Output",
    "D6Input", "D6Output",
    "DOMAIN_INPUT_TYPES", "DOMAIN_OUTPUT_TYPES",
    "DomainWorker", "MockWorker",
    "DomainRoute", "RoutingConfig",
    "MASOrchestrator",
    "LLMWorker", "WorkerError",
    "MODEL_REGISTRY", "create_worker", "create_workers_from_routing", "clear_client_cache",
    "DOMAIN_PROMPTS",
]
