"""
LogicGuard MVP - Main Engine
============================

The main entry point for reasoning tree verification.

Usage:
    from logicguard import LogicGuardEngine
    
    engine = LogicGuardEngine()
    result = engine.verify(json_tree)
    print(result.summary())

Architecture:
    Input JSON → Parse Nodes → Zero-Gate → Weight Calc → Status Machine → Diagnostics
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from .core import (
    Node, Status, Policy, Diagnostic, VerificationResult,
    compute_gate, compute_final_weight,
    get_diagnostic_code, get_diagnostic_reason,
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
        """
        Verify from JSON string.
        """
        data = json.loads(json_str)
        return self.verify(data)
    
    def verify_file(self, filepath: str) -> VerificationResult:
        """
        Verify from JSON file.
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        return self.verify(data)
    
    def _parse_nodes(self, data: Dict[str, Any]) -> List[Node]:
        """
        Parse JSON data into Node objects.
        """
        nodes_data = data.get("reasoning_tree", [])
        return [Node.from_dict(nd) for nd in nodes_data]
    
    def _build_parent_domains(self, nodes: List[Node]) -> Dict[str, Optional[int]]:
        """
        Build mapping from node_id to parent's domain (for sequence check).
        """
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
    """
    Verify from JSON string.
    """
    engine = LogicGuardEngine(policy)
    return engine.verify_json(json_str)


def quick_check(reasoning_tree: Dict[str, Any]) -> bool:
    """
    Quick boolean check: Is there a valid PrimaryMax?
    """
    result = verify_reasoning(reasoning_tree)
    return result.primary_max is not None


# ============================================================
# CLI Interface
# ============================================================

def main():
    """
    Command-line interface for LogicGuard.
    """
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m logicguard <json_file>")
        print("       python -m logicguard --example")
        sys.exit(1)
    
    if sys.argv[1] == "--example":
        # Run example
        example_tree = {
            "reasoning_tree": [
                {
                    "node_id": "root",
                    "parent_id": None,
                    "entity_id": "E_100",
                    "content": "Initial problem statement",
                    "legacy_idx": 0,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True, "rule_exists": True,
                        "l1_l3_ok": True, "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 10, "domain_points": 8, "current_domain": 1}
                },
                {
                    "node_id": "step_1",
                    "parent_id": "root",
                    "entity_id": "E_101",
                    "content": "Clarification of terms",
                    "legacy_idx": 1,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True, "rule_exists": True,
                        "l1_l3_ok": True, "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 8, "domain_points": 7, "current_domain": 2}
                },
                {
                    "node_id": "step_2_invalid",
                    "parent_id": "step_1",
                    "entity_id": "E_102",
                    "content": "Invalid inference (missing rule)",
                    "legacy_idx": 2,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True, "rule_exists": False,
                        "l1_l3_ok": True, "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 5, "domain_points": 10, "current_domain": 5}
                }
            ]
        }
        
        print("Running example verification...")
        print("=" * 60)
        result = verify_reasoning(example_tree)
        print(result.summary())
        
        # Run property verifications
        print("\n" + "=" * 60)
        print("PROPERTY VERIFICATIONS (Coq-proven):")
        print("=" * 60)
        engine = LogicGuardEngine()
        verifications = engine.run_verifications(result.nodes)
        for prop, (passed, msg) in verifications.items():
            status = "✓" if passed else "✗"
            print(f"  [{status}] {prop}: {msg}")
    
    else:
        # Verify file
        filepath = sys.argv[1]
        try:
            result = verify_json(open(filepath).read())
            print(result.summary())
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
