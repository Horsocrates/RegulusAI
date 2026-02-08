"""
Regulus AI - MAS Task Table
============================

TaskTable, Component, and DomainOutput dataclasses for structured domain processing.
"""

import json
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from regulus.mas.types import Complexity, DomainStatus, TaskStatus


DOMAIN_CODES = ["D1", "D2", "D3", "D4", "D5", "D6"]


@dataclass
class DomainOutput:
    """Output from processing a single domain on a component."""
    domain: str = ""
    status: DomainStatus = DomainStatus.PENDING
    content: str = ""
    weight: int = 0
    e_exists: bool = False
    r_exists: bool = False
    rule_exists: bool = False
    s_exists: bool = False
    deps_declared: bool = False
    l1_l3_ok: bool = True
    l5_ok: bool = True
    issues: list[str] = field(default_factory=list)
    model_used: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    time_seconds: float = 0.0

    @property
    def gate_passed(self) -> bool:
        """ERRS ∧ deps ∧ levels ∧ order."""
        err = self.e_exists and self.r_exists and self.rule_exists and self.s_exists
        return err and self.deps_declared and self.l1_l3_ok and self.l5_ok

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "status": self.status.value,
            "content": self.content,
            "weight": self.weight,
            "e_exists": self.e_exists,
            "r_exists": self.r_exists,
            "rule_exists": self.rule_exists,
            "s_exists": self.s_exists,
            "deps_declared": self.deps_declared,
            "l1_l3_ok": self.l1_l3_ok,
            "l5_ok": self.l5_ok,
            "issues": self.issues,
            "model_used": self.model_used,
            "gate_passed": self.gate_passed,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "time_seconds": self.time_seconds,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DomainOutput":
        return cls(
            domain=d.get("domain", ""),
            status=DomainStatus(d.get("status", "pending")),
            content=d.get("content", ""),
            weight=d.get("weight", 0),
            e_exists=d.get("e_exists", False),
            r_exists=d.get("r_exists", False),
            rule_exists=d.get("rule_exists", False),
            s_exists=d.get("s_exists", False),
            deps_declared=d.get("deps_declared", False),
            l1_l3_ok=d.get("l1_l3_ok", True),
            l5_ok=d.get("l5_ok", True),
            issues=d.get("issues", []),
            model_used=d.get("model_used", ""),
            input_tokens=d.get("input_tokens", 0),
            output_tokens=d.get("output_tokens", 0),
            time_seconds=d.get("time_seconds", 0.0),
        )


@dataclass
class Component:
    """A component of a decomposed task, with domain outputs and optional children."""
    component_id: str = "C1"
    parent_id: Optional[str] = None
    description: str = ""
    domains: dict[str, DomainOutput] = field(default_factory=dict)
    children: list["Component"] = field(default_factory=list)

    @property
    def depth(self) -> int:
        """Depth from component_id string: C1=1, C1.1=2, C1.1.2=3."""
        return self.component_id.replace("C", "").count(".") + 1

    @property
    def total_weight(self) -> int:
        """Sum of weights from completed domain outputs."""
        return sum(
            d.weight for d in self.domains.values()
            if d.status == DomainStatus.COMPLETED
        )

    @property
    def all_gates_passed(self) -> bool:
        """All completed domains have their gates passed."""
        completed = [d for d in self.domains.values() if d.status == DomainStatus.COMPLETED]
        if not completed:
            return False
        return all(d.gate_passed for d in completed)

    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0

    def init_domains(self) -> None:
        """Create D1-D6 as PENDING domain outputs."""
        for code in DOMAIN_CODES:
            if code not in self.domains:
                self.domains[code] = DomainOutput(domain=code, status=DomainStatus.PENDING)

    def to_dict(self) -> dict:
        return {
            "component_id": self.component_id,
            "parent_id": self.parent_id,
            "description": self.description,
            "domains": {k: v.to_dict() for k, v in self.domains.items()},
            "children": [c.to_dict() for c in self.children],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Component":
        comp = cls(
            component_id=d.get("component_id", "C1"),
            parent_id=d.get("parent_id"),
            description=d.get("description", ""),
        )
        for k, v in d.get("domains", {}).items():
            comp.domains[k] = DomainOutput.from_dict(v)
        for child_d in d.get("children", []):
            comp.children.append(Component.from_dict(child_d))
        return comp


@dataclass
class TaskTable:
    """The central data structure for MAS pipeline execution."""
    query: str = ""
    complexity: Complexity = Complexity.EASY
    status: TaskStatus = TaskStatus.CREATED
    components: list[Component] = field(default_factory=list)
    answer: str = ""
    classification_reason: str = ""

    @property
    def all_components_flat(self) -> list[Component]:
        """BFS traversal returning all components."""
        result = []
        queue: deque[Component] = deque(self.components)
        while queue:
            comp = queue.popleft()
            result.append(comp)
            queue.extend(comp.children)
        return result

    @property
    def total_weight(self) -> int:
        """Sum of weights across leaf components."""
        return sum(c.total_weight for c in self.all_components_flat if c.is_leaf)

    @property
    def domains_summary(self) -> dict:
        """Average weight per domain across leaf components."""
        leaves = [c for c in self.all_components_flat if c.is_leaf]
        if not leaves:
            return {}
        summary: dict[str, list[int]] = {}
        for leaf in leaves:
            for code, dom in leaf.domains.items():
                if dom.status == DomainStatus.COMPLETED:
                    summary.setdefault(code, []).append(dom.weight)
        return {
            code: sum(ws) // len(ws)
            for code, ws in summary.items()
            if ws
        }

    @property
    def all_gates_passed(self) -> bool:
        """All leaf components have all gates passed."""
        leaves = [c for c in self.all_components_flat if c.is_leaf]
        if not leaves:
            return False
        return all(c.all_gates_passed for c in leaves)

    @property
    def total_input_tokens(self) -> int:
        return sum(
            d.input_tokens
            for c in self.all_components_flat
            for d in c.domains.values()
        )

    @property
    def total_output_tokens(self) -> int:
        return sum(
            d.output_tokens
            for c in self.all_components_flat
            for d in c.domains.values()
        )

    def to_json(self) -> str:
        data = {
            "query": self.query,
            "complexity": self.complexity.value,
            "status": self.status.value,
            "components": [c.to_dict() for c in self.components],
            "answer": self.answer,
            "classification_reason": self.classification_reason,
        }
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "TaskTable":
        data = json.loads(s)
        table = cls(
            query=data.get("query", ""),
            complexity=Complexity(data.get("complexity", "easy")),
            status=TaskStatus(data.get("status", "created")),
            answer=data.get("answer", ""),
            classification_reason=data.get("classification_reason", ""),
        )
        for comp_d in data.get("components", []):
            table.components.append(Component.from_dict(comp_d))
        return table
