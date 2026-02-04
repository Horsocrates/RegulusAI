"""
LogicGuard MVP - Test Suite
===========================

Tests for the Structural Guardrail implementation.

Verified Properties (from Coq):
1. Zero-Gate Law: G = 0 ⇒ W = 0
2. Uniqueness: |{e : PrimaryMax}| ≤ 1
3. Stability: Invalid cannot become PrimaryMax
"""

import pytest
import json
from logicguard import (
    LogicGuardEngine, verify_reasoning, quick_check,
    Node, Status, Policy, GateSignals, RawScores, IntegrityGate,
    compute_gate, compute_final_weight
)


# ============================================================
# Test Fixtures
# ============================================================

@pytest.fixture
def valid_tree():
    """A fully valid reasoning tree"""
    return {
        "reasoning_tree": [
            {
                "node_id": "root",
                "parent_id": None,
                "entity_id": "E_100",
                "content": "Define the problem",
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
                "content": "Clarify terms",
                "legacy_idx": 1,
                "gate_signals": {
                    "e_exists": True, "r_exists": True, "rule_exists": True,
                    "l1_l3_ok": True, "l5_ok": True
                },
                "raw_scores": {"struct_points": 10, "domain_points": 9, "current_domain": 2}
            },
            {
                "node_id": "step_2",
                "parent_id": "step_1",
                "entity_id": "E_102",
                "content": "Draw conclusion",
                "legacy_idx": 2,
                "gate_signals": {
                    "e_exists": True, "r_exists": True, "rule_exists": True,
                    "l1_l3_ok": True, "l5_ok": True
                },
                "raw_scores": {"struct_points": 10, "domain_points": 10, "current_domain": 5}
            }
        ]
    }


@pytest.fixture
def tree_with_invalid_node():
    """Tree with one invalid node (missing Rule)"""
    return {
        "reasoning_tree": [
            {
                "node_id": "root",
                "parent_id": None,
                "entity_id": "E_100",
                "content": "Valid start",
                "legacy_idx": 0,
                "gate_signals": {
                    "e_exists": True, "r_exists": True, "rule_exists": True,
                    "l1_l3_ok": True, "l5_ok": True
                },
                "raw_scores": {"struct_points": 10, "domain_points": 8, "current_domain": 1}
            },
            {
                "node_id": "invalid_step",
                "parent_id": "root",
                "entity_id": "E_101",
                "content": "Invalid: missing rule connection",
                "legacy_idx": 1,
                "gate_signals": {
                    "e_exists": True, "r_exists": True, "rule_exists": False,  # MISSING RULE
                    "l1_l3_ok": True, "l5_ok": True
                },
                "raw_scores": {"struct_points": 20, "domain_points": 15, "current_domain": 5}
            }
        ]
    }


@pytest.fixture
def tree_with_equal_weights():
    """Tree with two valid nodes of equal weight (tests L5 tie-breaking)"""
    return {
        "reasoning_tree": [
            {
                "node_id": "path_A",
                "parent_id": None,
                "entity_id": "E_A",
                "content": "Path A reasoning",
                "legacy_idx": 0,  # Earlier
                "gate_signals": {
                    "e_exists": True, "r_exists": True, "rule_exists": True,
                    "l1_l3_ok": True, "l5_ok": True
                },
                "raw_scores": {"struct_points": 10, "domain_points": 8, "current_domain": 3}
            },
            {
                "node_id": "path_B",
                "parent_id": None,
                "entity_id": "E_B",
                "content": "Path B reasoning",
                "legacy_idx": 1,  # Later
                "gate_signals": {
                    "e_exists": True, "r_exists": True, "rule_exists": True,
                    "l1_l3_ok": True, "l5_ok": True
                },
                "raw_scores": {"struct_points": 10, "domain_points": 8, "current_domain": 3}  # Same weight!
            }
        ]
    }


@pytest.fixture
def tree_all_invalid():
    """Tree where all nodes are invalid"""
    return {
        "reasoning_tree": [
            {
                "node_id": "bad_1",
                "parent_id": None,
                "entity_id": "E_1",
                "content": "Missing element",
                "legacy_idx": 0,
                "gate_signals": {
                    "e_exists": False, "r_exists": True, "rule_exists": True,
                    "l1_l3_ok": True, "l5_ok": True
                },
                "raw_scores": {"struct_points": 10, "domain_points": 10, "current_domain": 5}
            },
            {
                "node_id": "bad_2",
                "parent_id": "bad_1",
                "entity_id": "E_2",
                "content": "Level violation",
                "legacy_idx": 1,
                "gate_signals": {
                    "e_exists": True, "r_exists": True, "rule_exists": True,
                    "l1_l3_ok": False, "l5_ok": True
                },
                "raw_scores": {"struct_points": 10, "domain_points": 10, "current_domain": 5}
            }
        ]
    }


# ============================================================
# Zero-Gate Tests
# ============================================================

class TestZeroGate:
    """Tests for the Zero-Gate mechanism"""
    
    def test_zero_gate_fires_on_missing_element(self):
        """Missing Element should trigger Zero-Gate"""
        signals = GateSignals(e_exists=False, r_exists=True, rule_exists=True)
        node = Node(
            node_id="test", parent_id=None, entity_id="E1",
            content="", legacy_idx=0,
            gate_signals=signals,
            raw_scores=RawScores(struct_points=100, domain_points=100, current_domain=5)
        )
        
        gate = compute_gate(node)
        assert not gate.err_complete
        assert not gate.is_valid
        
        weight = compute_final_weight(node, gate)
        assert weight == 0  # ANNIHILATED
    
    def test_zero_gate_fires_on_missing_role(self):
        """Missing Role should trigger Zero-Gate"""
        signals = GateSignals(e_exists=True, r_exists=False, rule_exists=True)
        node = Node(
            node_id="test", parent_id=None, entity_id="E1",
            content="", legacy_idx=0,
            gate_signals=signals,
            raw_scores=RawScores(struct_points=100, domain_points=100, current_domain=5)
        )
        
        gate = compute_gate(node)
        assert not gate.err_complete
        
        weight = compute_final_weight(node, gate)
        assert weight == 0
    
    def test_zero_gate_fires_on_missing_rule(self):
        """Missing Rule should trigger Zero-Gate"""
        signals = GateSignals(e_exists=True, r_exists=True, rule_exists=False)
        node = Node(
            node_id="test", parent_id=None, entity_id="E1",
            content="", legacy_idx=0,
            gate_signals=signals,
            raw_scores=RawScores(struct_points=100, domain_points=100, current_domain=5)
        )
        
        gate = compute_gate(node)
        weight = compute_final_weight(node, gate)
        assert weight == 0
    
    def test_zero_gate_fires_on_level_violation(self):
        """L1-L3 violation should trigger Zero-Gate"""
        signals = GateSignals(
            e_exists=True, r_exists=True, rule_exists=True,
            l1_l3_ok=False, l5_ok=True
        )
        node = Node(
            node_id="test", parent_id=None, entity_id="E1",
            content="", legacy_idx=0,
            gate_signals=signals,
            raw_scores=RawScores(struct_points=100, domain_points=100, current_domain=5)
        )
        
        gate = compute_gate(node)
        assert not gate.levels_valid
        
        weight = compute_final_weight(node, gate)
        assert weight == 0
    
    def test_zero_gate_fires_on_order_violation(self):
        """L5 violation should trigger Zero-Gate"""
        signals = GateSignals(
            e_exists=True, r_exists=True, rule_exists=True,
            l1_l3_ok=True, l5_ok=False
        )
        node = Node(
            node_id="test", parent_id=None, entity_id="E1",
            content="", legacy_idx=0,
            gate_signals=signals,
            raw_scores=RawScores(struct_points=100, domain_points=100, current_domain=5)
        )
        
        gate = compute_gate(node)
        assert not gate.order_valid
        
        weight = compute_final_weight(node, gate)
        assert weight == 0
    
    def test_valid_gate_passes(self):
        """All valid signals should pass gate"""
        signals = GateSignals(
            e_exists=True, r_exists=True, rule_exists=True,
            l1_l3_ok=True, l5_ok=True
        )
        node = Node(
            node_id="test", parent_id=None, entity_id="E1",
            content="", legacy_idx=0,
            gate_signals=signals,
            raw_scores=RawScores(struct_points=10, domain_points=8, current_domain=3)
        )
        
        gate = compute_gate(node)
        assert gate.is_valid
        
        weight = compute_final_weight(node, gate)
        assert weight > 0  # Should have non-zero weight
        assert weight == 10 + (3 * 10 + 8)  # struct + domain


# ============================================================
# Status Machine Tests
# ============================================================

class TestStatusMachine:
    """Tests for the Status Machine"""
    
    def test_uniqueness_single_primary(self, valid_tree):
        """Exactly one PrimaryMax should exist"""
        result = verify_reasoning(valid_tree)
        
        primary_count = sum(1 for n in result.nodes if n.status == Status.PRIMARY_MAX)
        assert primary_count == 1
    
    def test_stability_invalid_not_primary(self, tree_with_invalid_node):
        """Invalid node cannot be PrimaryMax"""
        result = verify_reasoning(tree_with_invalid_node)
        
        for node in result.nodes:
            if node.status == Status.PRIMARY_MAX:
                assert node.gate.is_valid
    
    def test_l5_resolution_legacy_priority(self, tree_with_equal_weights):
        """With equal weights, earlier node wins (Legacy Priority)"""
        result = verify_reasoning(tree_with_equal_weights, Policy.LEGACY_PRIORITY)
        
        assert result.primary_max is not None
        assert result.primary_max.legacy_idx == 0  # Earlier wins
        assert result.primary_max.node_id == "path_A"
    
    def test_l5_resolution_recency_priority(self, tree_with_equal_weights):
        """With Recency Priority, later node wins"""
        result = verify_reasoning(tree_with_equal_weights, Policy.RECENCY_PRIORITY)
        
        assert result.primary_max is not None
        assert result.primary_max.legacy_idx == 1  # Later wins
        assert result.primary_max.node_id == "path_B"
    
    def test_secondary_max_on_tie(self, tree_with_equal_weights):
        """Equal weight nodes get SecondaryMax status"""
        result = verify_reasoning(tree_with_equal_weights)
        
        assert len(result.secondary_max) == 1
        assert result.secondary_max[0].node_id == "path_B"
    
    def test_no_primary_when_all_invalid(self, tree_all_invalid):
        """No PrimaryMax when all nodes are invalid"""
        result = verify_reasoning(tree_all_invalid)
        
        assert result.primary_max is None
        assert result.invalid_count == 2


# ============================================================
# Verified Properties Tests
# ============================================================

class TestVerifiedProperties:
    """Tests that verify Coq-proven properties at runtime"""
    
    def test_zero_gate_law(self, tree_with_invalid_node):
        """G = 0 ⇒ W = 0"""
        result = verify_reasoning(tree_with_invalid_node)
        engine = LogicGuardEngine()
        verifications = engine.run_verifications(result.nodes)
        
        passed, msg = verifications["zero_gate_law"]
        assert passed, msg
    
    def test_uniqueness_property(self, valid_tree):
        """|{e : PrimaryMax}| ≤ 1"""
        result = verify_reasoning(valid_tree)
        engine = LogicGuardEngine()
        verifications = engine.run_verifications(result.nodes)
        
        passed, msg = verifications["uniqueness"]
        assert passed, msg
    
    def test_stability_property(self, tree_with_invalid_node):
        """Invalid cannot become PrimaryMax"""
        result = verify_reasoning(tree_with_invalid_node)
        engine = LogicGuardEngine()
        verifications = engine.run_verifications(result.nodes)
        
        passed, msg = verifications["stability"]
        assert passed, msg


# ============================================================
# Weight Calculation Tests
# ============================================================

class TestWeightCalculation:
    """Tests for weight calculation"""
    
    def test_weight_formula(self):
        """W = G × (S_struct + S_domain) where S_domain = domain*10 + quality"""
        signals = GateSignals(
            e_exists=True, r_exists=True, rule_exists=True,
            l1_l3_ok=True, l5_ok=True
        )
        raw = RawScores(struct_points=15, domain_points=7, current_domain=4)
        node = Node(
            node_id="test", parent_id=None, entity_id="E1",
            content="", legacy_idx=0,
            gate_signals=signals,
            raw_scores=raw
        )
        
        gate = compute_gate(node)
        weight = compute_final_weight(node, gate)
        
        # S_struct = 15
        # S_domain = 4*10 + 7 = 47
        # W = 1 × (15 + 47) = 62
        assert weight == 62
    
    def test_higher_domain_higher_weight(self):
        """Higher domain index should yield higher weight"""
        signals = GateSignals(
            e_exists=True, r_exists=True, rule_exists=True,
            l1_l3_ok=True, l5_ok=True
        )
        
        # Domain 2
        node_d2 = Node(
            node_id="d2", parent_id=None, entity_id="E1",
            content="", legacy_idx=0,
            gate_signals=signals,
            raw_scores=RawScores(struct_points=10, domain_points=5, current_domain=2)
        )
        
        # Domain 5
        node_d5 = Node(
            node_id="d5", parent_id=None, entity_id="E2",
            content="", legacy_idx=1,
            gate_signals=signals,
            raw_scores=RawScores(struct_points=10, domain_points=5, current_domain=5)
        )
        
        w_d2 = compute_final_weight(node_d2, compute_gate(node_d2))
        w_d5 = compute_final_weight(node_d5, compute_gate(node_d5))
        
        assert w_d5 > w_d2


# ============================================================
# Diagnostic Tests
# ============================================================

class TestDiagnostics:
    """Tests for diagnostic generation"""
    
    def test_diagnostic_code_generated(self, tree_with_invalid_node):
        """Invalid nodes should have diagnostic codes"""
        result = verify_reasoning(tree_with_invalid_node)
        
        invalid_diag = next(d for d in result.diagnostics if d.status == Status.INVALID)
        assert invalid_diag.diagnostic_code is not None
        assert invalid_diag.diagnostic_code == "ERR_RULE"
    
    def test_valid_nodes_no_diagnostic_code(self, valid_tree):
        """Valid nodes should have no diagnostic code"""
        result = verify_reasoning(valid_tree)
        
        for diag in result.diagnostics:
            if diag.status != Status.INVALID:
                assert diag.diagnostic_code is None


# ============================================================
# Integration Tests
# ============================================================

class TestIntegration:
    """End-to-end integration tests"""
    
    def test_full_verification_flow(self, valid_tree):
        """Complete verification should work end-to-end"""
        engine = LogicGuardEngine()
        result = engine.verify(valid_tree)
        
        assert result.primary_max is not None
        assert result.invalid_count == 0
        assert len(result.diagnostics) == 3
    
    def test_json_parsing(self):
        """Should correctly parse JSON input"""
        json_str = json.dumps({
            "reasoning_tree": [
                {
                    "node_id": "root",
                    "parent_id": None,
                    "entity_id": "E_100",
                    "content": "Test",
                    "legacy_idx": 0,
                    "gate_signals": {
                        "e_exists": True, "r_exists": True, "rule_exists": True,
                        "l1_l3_ok": True, "l5_ok": True
                    },
                    "raw_scores": {"struct_points": 10, "domain_points": 8, "current_domain": 1}
                }
            ]
        })
        
        engine = LogicGuardEngine()
        result = engine.verify_json(json_str)
        
        assert len(result.nodes) == 1
    
    def test_quick_check(self, valid_tree, tree_all_invalid):
        """quick_check should return correct boolean"""
        assert quick_check(valid_tree) == True
        assert quick_check(tree_all_invalid) == False


# ============================================================
# Run Tests
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
