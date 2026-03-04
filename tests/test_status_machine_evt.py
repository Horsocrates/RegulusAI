"""Tests for EVT_idx wiring into status_machine.py."""

import pytest
from regulus.core.types import (
    Node, Status, Policy, GateSignals, IntegrityGate, RawScores,
)
from regulus.core.status_machine import find_max_entity


def _make_node(node_id: str, weight: float, legacy_idx: int, valid: bool = True) -> Node:
    """Helper: create a Node with given weight and gate validity."""
    signals = GateSignals(
        e_exists=valid, r_exists=valid, rule_exists=valid,
        s_exists=valid, deps_declared=valid,
        l1_l3_ok=valid, l5_ok=valid,
    )
    gate = IntegrityGate(
        err_complete=valid,
        deps_valid=valid,
        levels_valid=valid,
        order_valid=valid,
    )
    node = Node(
        node_id=node_id,
        parent_id=None,
        entity_id=f"entity_{node_id}",
        content=f"content_{node_id}",
        legacy_idx=legacy_idx,
        gate_signals=signals,
        raw_scores=RawScores(struct_points=0, domain_points=0, current_domain=1),
    )
    node.gate = gate
    node.final_weight = weight
    node.status = Status.CANDIDATE
    return node


class TestEVTArgmaxWiring:
    def test_evt_matches_original_clear_winner(self):
        """EVT argmax selects same PrimaryMax as original for unambiguous cases."""
        nodes = [
            _make_node("A", weight=10.0, legacy_idx=0),
            _make_node("B", weight=20.0, legacy_idx=1),
            _make_node("C", weight=15.0, legacy_idx=2),
        ]
        original = find_max_entity(nodes, use_evt=False)
        evt_result = find_max_entity(nodes, use_evt=True)
        assert original.node_id == evt_result.node_id == "B"

    def test_evt_leftmost_tiebreak(self):
        """EVT with reverse sort gives L5 leftmost on tie (lowest legacy_idx)."""
        nodes = [
            _make_node("A", weight=10.0, legacy_idx=0),
            _make_node("B", weight=10.0, legacy_idx=1),
            _make_node("C", weight=10.0, legacy_idx=2),
        ]
        # Original: LEGACY_PRIORITY → lowest legacy_idx wins → A
        original = find_max_entity(nodes, policy=Policy.LEGACY_PRIORITY, use_evt=False)
        assert original.node_id == "A"

        # EVT: sorted desc by legacy_idx, rightmost-on-equal → picks lowest idx → A
        evt_result = find_max_entity(nodes, use_evt=True)
        assert evt_result.node_id == "A"

    def test_evt_respects_gate_filtering(self):
        """Invalid nodes excluded before EVT argmax."""
        nodes = [
            _make_node("A", weight=100.0, legacy_idx=0, valid=False),
            _make_node("B", weight=5.0, legacy_idx=1, valid=True),
        ]
        result = find_max_entity(nodes, use_evt=True)
        assert result.node_id == "B"

    def test_evt_no_valid_nodes(self):
        """Returns None when all nodes are invalid."""
        nodes = [
            _make_node("A", weight=10.0, legacy_idx=0, valid=False),
        ]
        assert find_max_entity(nodes, use_evt=True) is None

    def test_evt_single_valid(self):
        """Single valid node is returned."""
        nodes = [_make_node("A", weight=7.0, legacy_idx=0)]
        result = find_max_entity(nodes, use_evt=True)
        assert result.node_id == "A"
