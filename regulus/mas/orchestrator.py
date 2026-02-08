"""
Regulus AI - MAS Orchestrator
==============================

Main pipeline: classify -> decompose -> process domains -> verify.

Phase 1 heuristics (no LLM calls for classify/decompose):
- Classify: word-count heuristic
- Decompose: single component C1
- Process: sequential D1-D6 via workers (mock or LLM)
- Verify: D5 answer as final answer
"""

import time
from typing import Callable, Optional

from regulus.mas.types import Complexity, DomainStatus, TaskStatus, MASConfig, MASResponse
from regulus.mas.table import TaskTable, Component, DomainOutput, DOMAIN_CODES
from regulus.mas.contracts import (
    DomainInput, D1Input, D2Input, D3Input, D4Input, D5Input, D6Input,
)
from regulus.mas.workers import DomainWorker, MockWorker
from regulus.mas.routing import RoutingConfig


class MASOrchestrator:
    """
    Multi-Agent Structured pipeline orchestrator.

    Uses the same callback signatures as AuditOrchestrator for
    seamless integration with SSE streaming in the lab runner and API.
    """

    def __init__(
        self,
        llm_client=None,
        config: Optional[MASConfig] = None,
        routing: Optional[RoutingConfig] = None,
        workers: Optional[dict[str, DomainWorker]] = None,
        on_domain_start: Optional[Callable] = None,
        on_domain_complete: Optional[Callable] = None,
        on_correction: Optional[Callable] = None,
    ):
        self.llm_client = llm_client
        self.config = config or MASConfig()
        self.routing = routing or RoutingConfig.default()

        # Workers: either provided or create MockWorkers as fallback
        if workers is not None:
            self.workers = workers
        else:
            self.workers = {
                code: MockWorker(domain_code=code)
                for code in DOMAIN_CODES
            }

        self._on_domain_start = on_domain_start
        self._on_domain_complete = on_domain_complete
        self._on_correction = on_correction

    async def process_query(self, query: str) -> MASResponse:
        """Run the full MAS pipeline."""
        start_time = time.time()

        table = TaskTable(query=query, status=TaskStatus.CREATED)

        # Step 1: Classify
        table = await self._classify(table)

        # Step 2: Decompose
        table = await self._decompose(table)

        # Step 3: Process domains
        table = await self._process_domains(table)

        # Step 4: Verify and build answer
        table = await self._verify_and_answer(table)

        elapsed = time.time() - start_time

        # Build audit summary
        leaves = [c for c in table.all_components_flat if c.is_leaf]
        domains_present = 0
        if leaves:
            domains_present = sum(
                1 for code in DOMAIN_CODES
                if any(
                    code in c.domains and c.domains[code].status == DomainStatus.COMPLETED
                    for c in leaves
                )
            )

        audit_summary = {
            "total_weight": table.total_weight,
            "all_gates_passed": table.all_gates_passed,
            "domains_present": domains_present,
            "domains_summary": table.domains_summary,
        }

        valid = self.config.is_passing(
            total_weight=table.total_weight,
            domains_present=domains_present,
            all_gates_passed=table.all_gates_passed,
        )

        return MASResponse(
            query=query,
            answer=table.answer,
            valid=valid,
            complexity=table.complexity.value,
            components_count=len(table.all_components_flat),
            task_table_json=table.to_json(),
            audit_summary=audit_summary,
            corrections=0,
            time_seconds=elapsed,
            input_tokens=table.total_input_tokens,
            output_tokens=table.total_output_tokens,
        )

    async def _classify(self, table: TaskTable) -> TaskTable:
        """Step 1: Classify query complexity via word-count heuristic."""
        table.status = TaskStatus.CLASSIFYING
        self._emit_domain_start("CLASSIFY", "Complexity Classification")

        word_count = len(table.query.split())
        if word_count <= 15:
            table.complexity = Complexity.EASY
            table.classification_reason = f"word_count={word_count} <= 15"
        elif word_count <= 50:
            table.complexity = Complexity.MEDIUM
            table.classification_reason = f"word_count={word_count} <= 50"
        else:
            table.complexity = Complexity.HARD
            table.classification_reason = f"word_count={word_count} > 50"

        self._emit_domain_complete("CLASSIFY", {
            "complexity": table.complexity.value,
            "reason": table.classification_reason,
        })

        return table

    async def _decompose(self, table: TaskTable) -> TaskTable:
        """Step 2: Decompose into components. Phase 1: single component C1."""
        table.status = TaskStatus.DECOMPOSING
        self._emit_domain_start("DECOMPOSE", "Task Decomposition")

        comp = Component(
            component_id="C1",
            description=table.query,
        )
        comp.init_domains()
        table.components = [comp]

        self._emit_domain_complete("DECOMPOSE", {
            "components": 1,
            "depth": 1,
        })

        return table

    async def _process_domains(self, table: TaskTable) -> TaskTable:
        """Step 3: Process D1-D6 sequentially for each leaf component."""
        table.status = TaskStatus.PROCESSING

        for comp in table.all_components_flat:
            if not comp.is_leaf:
                continue

            prior_domains: dict = {}
            typed_outputs: dict = {}

            for code in DOMAIN_CODES:
                worker = self.workers.get(code)
                if not worker:
                    continue

                model = self.routing.get_model(table.complexity.value, code)

                # Build typed domain input from prior typed outputs
                domain_input = self._build_domain_input(
                    code, table.query, comp, prior_domains, typed_outputs,
                )

                domain_name = {
                    "D1": "Recognition", "D2": "Clarification",
                    "D3": "Framework Selection", "D4": "Comparison",
                    "D5": "Inference", "D6": "Reflection",
                }.get(code, code)

                self._emit_domain_start(code, domain_name)

                # Mark as running
                if code in comp.domains:
                    comp.domains[code].status = DomainStatus.RUNNING

                # Process
                output = await worker.process(comp, domain_input, model)
                comp.domains[code] = output

                # Track DomainOutput for fallback
                prior_domains[code] = output

                # Track typed output for domain chaining
                if hasattr(output, '_typed_output') and output._typed_output is not None:
                    typed_outputs[code] = output._typed_output

                self._emit_domain_complete(code, {
                    "weight": output.weight,
                    "gate": 1 if output.gate_passed else 0,
                    "component": comp.component_id,
                    "model": output.model_used,
                    "time_ms": int(output.time_seconds * 1000),
                })

        return table

    async def _verify_and_answer(self, table: TaskTable) -> TaskTable:
        """Step 4: Extract answer from D5 output."""
        table.status = TaskStatus.VERIFYING
        self._emit_domain_start("VERIFY", "Answer Verification")

        # Try to get answer from typed D5 output first, fall back to content
        for comp in table.all_components_flat:
            if comp.is_leaf and "D5" in comp.domains:
                d5 = comp.domains["D5"]
                if d5.status == DomainStatus.COMPLETED:
                    # Prefer typed output's answer field
                    if hasattr(d5, '_typed_output') and d5._typed_output is not None:
                        typed_d5 = d5._typed_output
                        table.answer = getattr(typed_d5, 'answer', '') or d5.content
                    else:
                        table.answer = d5.content
                    break

        table.status = TaskStatus.COMPLETED

        self._emit_domain_complete("VERIFY", {
            "has_answer": bool(table.answer),
            "total_weight": table.total_weight,
            "all_gates_passed": table.all_gates_passed,
        })

        return table

    def _build_domain_input(
        self,
        domain_code: str,
        query: str,
        component: Component,
        prior_domains: dict,
        typed_outputs: dict,
    ) -> DomainInput:
        """Build the typed domain input from prior domain outputs.

        Uses typed outputs (D*Output attached via ._typed_output) for
        structured field extraction. Falls back gracefully when typed
        outputs aren't available (e.g., MockWorker).
        """
        base = dict(
            query=query,
            goal=query,  # Phase 1: goal = query
            component_id=component.component_id,
            component_description=component.description,
            prior_domains=prior_domains,
        )

        if domain_code == "D1":
            return D1Input(**base)

        elif domain_code == "D2":
            typed_d1 = typed_outputs.get("D1")
            components = getattr(typed_d1, 'components', []) if typed_d1 else []
            return D2Input(**base, components=components)

        elif domain_code == "D3":
            typed_d2 = typed_outputs.get("D2")
            typed_d1 = typed_outputs.get("D1")
            # Prefer D2 enriched components, fall back to D1
            components = (
                getattr(typed_d2, 'components', []) if typed_d2
                else getattr(typed_d1, 'components', []) if typed_d1
                else []
            )
            return D3Input(**base, components=components)

        elif domain_code == "D4":
            typed_d2 = typed_outputs.get("D2")
            typed_d1 = typed_outputs.get("D1")
            typed_d3 = typed_outputs.get("D3")
            components = (
                getattr(typed_d2, 'components', []) if typed_d2
                else getattr(typed_d1, 'components', []) if typed_d1
                else []
            )
            framework = getattr(typed_d3, 'framework', {}) if typed_d3 else {}
            return D4Input(**base, components=components, framework=framework)

        elif domain_code == "D5":
            typed_d4 = typed_outputs.get("D4")
            typed_d3 = typed_outputs.get("D3")
            comparisons = getattr(typed_d4, 'comparisons', []) if typed_d4 else []
            framework = getattr(typed_d3, 'framework', {}) if typed_d3 else {}
            return D5Input(**base, comparisons=comparisons, framework=framework)

        elif domain_code == "D6":
            typed_d5 = typed_outputs.get("D5")
            conclusion = getattr(typed_d5, 'conclusion', {}) if typed_d5 else {}
            # Build table summary from prior domain content
            summary_parts = []
            for d_code in ["D1", "D2", "D3", "D4", "D5"]:
                d_out = prior_domains.get(d_code)
                if d_out and d_out.status == DomainStatus.COMPLETED:
                    summary_parts.append(f"{d_code}: {d_out.content}")
            table_summary = "\n".join(summary_parts)
            return D6Input(**base, conclusion=conclusion, table_summary=table_summary)

        else:
            return DomainInput(**base)

    # Callback helpers (same signatures as AuditOrchestrator)

    def _emit_domain_start(self, domain: str, domain_name: str):
        if self._on_domain_start:
            self._on_domain_start(domain, domain_name)

    def _emit_domain_complete(self, domain: str, result_dict: dict):
        if self._on_domain_complete:
            self._on_domain_complete(domain, result_dict)

    def _emit_correction(self, domain: str, attempt: int, violation: str, fix_summary: str):
        if self._on_correction:
            self._on_correction(domain, attempt, violation, fix_summary)
