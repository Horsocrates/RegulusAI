"""
Regulus AI - MAS Domain Workers
================================

Abstract worker interface and mock implementation for testing.
"""

from abc import ABC, abstractmethod
from typing import Optional

from regulus.mas.types import DomainStatus
from regulus.mas.table import Component, DomainOutput
from regulus.mas.contracts import DomainInput


class DomainWorker(ABC):
    """Abstract base class for domain-specific workers."""

    @property
    @abstractmethod
    def domain_code(self) -> str:
        """Domain identifier (e.g. 'D1', 'D2')."""
        ...

    @abstractmethod
    async def process(
        self,
        component: Component,
        domain_input: DomainInput,
        model: str,
    ) -> DomainOutput:
        """
        Process a domain for a component.

        Args:
            component: The component being processed.
            domain_input: Typed input for this domain.
            model: Model identifier to use.

        Returns:
            DomainOutput with results.
        """
        ...


class MockWorker(DomainWorker):
    """Mock worker for testing — returns configurable results."""

    def __init__(
        self,
        domain_code: str,
        weight: int = 75,
        gate_pass: bool = True,
        content: str = "Mock content",
        call_tracker: Optional[list] = None,
    ):
        self._domain_code = domain_code
        self._weight = weight
        self._gate_pass = gate_pass
        self._content = content
        self._calls = call_tracker if call_tracker is not None else []

    @property
    def domain_code(self) -> str:
        return self._domain_code

    async def process(
        self,
        component: Component,
        domain_input: DomainInput,
        model: str,
    ) -> DomainOutput:
        self._calls.append({
            "domain": self._domain_code,
            "component_id": component.component_id,
            "model": model,
        })
        return DomainOutput(
            domain=self._domain_code,
            status=DomainStatus.COMPLETED,
            content=self._content,
            weight=self._weight,
            e_exists=self._gate_pass,
            r_exists=self._gate_pass,
            rule_exists=self._gate_pass,
            s_exists=self._gate_pass,
            deps_declared=self._gate_pass,
            l1_l3_ok=self._gate_pass,
            l5_ok=self._gate_pass,
            issues=[],
            model_used=model,
            input_tokens=50,
            output_tokens=100,
            time_seconds=0.1,
        )
