"""
Regulus AI - Main Engine
========================

The main entry point for reasoning tree verification.

Usage:
    from regulus.core import LogicGuardEngine, verify_reasoning

    engine = LogicGuardEngine()
    result = engine.verify(json_tree)
    print(result.summary())

Architecture:
    Input JSON → Parse Nodes → Zero-Gate → Weight Calc → Status Machine → Diagnostics
"""

import json
from typing import Dict, List, Any, Optional

from .types import Node, Status, Policy, Diagnostic, VerificationResult
from .zero_gate import compute_gate, get_diagnostic_code, get_diagnostic_reason
from .weight import compute_final_weight
from .status_machine import (
    assign_all_statuses, find_max_entity, find_secondary_max,
    find_historical_max, build_entity_history,
    create_diagnostic, run_all_verifications
)


class LogicGuardEngine:
    """
    The main LogicGuard verification engine.

    Implements the Structural Guardrail from Article 8:
    - Zero-Gate: Annihilates structurally invalid reasoning
    - Status Machine: L5-Resolution for deterministic selection
    - Diagnostic Map: Pinpoints exactly which gate failed
    """

    def __init__(self, policy: Policy = Policy.LEGACY_PRIORITY):
        """
        Initialize engine with tie-breaking policy.

        Args:
            policy: LEGACY_PRIORITY (default, L5-compliant) or RECENCY_PRIORITY
        """
        self.policy = policy

    def verify(self, reasoning_tree: Dict[str, Any]) -> VerificationResult:
        """
        Verify a reasoning tree and return diagnostic results.

        Args:
            reasoning_tree: JSON dict with "reasoning_tree" key containing node list

        Returns:
            VerificationResult with all diagnostics
        """
        # Step 1: Parse nodes
        nodes = self._parse_nodes(reasoning_tree)

        # Step 2: Build parent-child relationships for domain sequence check
        parent_domains = self._build_parent_domains(nodes)

        # Step 3: Compute gates and weights for all nodes
        for node in nodes:
            parent_domain = parent_domains.get(node.node_id)
            node.gate = compute_gate(node, parent_domain)
            node.final_weight = compute_final_weight(node, node.gate)

        # Step 4: Assign statuses via Status Machine
        nodes = assign_all_statuses(nodes, self.policy)

        # Step 5: Generate diagnostics
        diagnostics = []
        for node in nodes:
            code = get_diagnostic_code(node, parent_domains.get(node.node_id))
            reason = get_diagnostic_reason(code)
            diag = create_diagnostic(node, code, reason)
            diagnostics.append(diag)

        # Step 6: Collect results by status
        primary = find_max_entity(nodes, self.policy)
        secondary = find_secondary_max(nodes, primary, self.policy) if primary else []
        entity_history = build_entity_history(nodes)
        historical = find_historical_max(nodes, entity_history)
        invalid_count = sum(1 for n in nodes if n.status == Status.INVALID)

        return VerificationResult(
            nodes=nodes,
            diagnostics=diagnostics,
            primary_max=primary,
            secondary_max=secondary,
            historical_max=historical,
            invalid_count=invalid_count
        )

    def verify_json(self, json_str: str) -> VerificationResult:
        """Verify from JSON string."""
        data = json.loads(json_str)
        return self.verify(data)

    def verify_file(self, filepath: str) -> VerificationResult:
        """Verify from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return self.verify(data)

    def _parse_nodes(self, data: Dict[str, Any]) -> List[Node]:
        """Parse JSON data into Node objects."""
        nodes_data = data.get("reasoning_tree", [])
        return [Node.from_dict(nd) for nd in nodes_data]

    def _build_parent_domains(self, nodes: List[Node]) -> Dict[str, Optional[int]]:
        """Build mapping from node_id to parent's domain (for sequence check)."""
        node_map = {n.node_id: n for n in nodes}
        parent_domains = {}

        for node in nodes:
            if node.parent_id and node.parent_id in node_map:
                parent = node_map[node.parent_id]
                parent_domains[node.node_id] = parent.raw_scores.current_domain
            else:
                parent_domains[node.node_id] = None

        return parent_domains

    def run_verifications(self, nodes: List[Node]) -> Dict[str, tuple]:
        """
        Run Coq-proven property verifications.
        Returns dict of {property_name: (passed, message)}
        """
        return run_all_verifications(nodes)


# ============================================================
# Convenience Functions
# ============================================================

def verify_reasoning(reasoning_tree: Dict[str, Any],
                      policy: Policy = Policy.LEGACY_PRIORITY) -> VerificationResult:
    """
    Quick verification function.

    Usage:
        result = verify_reasoning(json_data)
        print(result.summary())
    """
    engine = LogicGuardEngine(policy)
    return engine.verify(reasoning_tree)


def verify_json(json_str: str,
                policy: Policy = Policy.LEGACY_PRIORITY) -> VerificationResult:
    """Verify from JSON string."""
    engine = LogicGuardEngine(policy)
    return engine.verify_json(json_str)


def quick_check(reasoning_tree: Dict[str, Any]) -> bool:
    """Quick boolean check: Is there a valid PrimaryMax?"""
    result = verify_reasoning(reasoning_tree)
    return result.primary_max is not None
