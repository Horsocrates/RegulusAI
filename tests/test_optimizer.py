"""
Regulus AI - Trisection Optimizer Tests
========================================

Tests for TrisectionOptimizer: division, tie-breaking, convergence, aggregation.
"""

import pytest
from regulus.core.types import Node, GateSignals, RawScores, IntegrityGate, Policy
from regulus.core.optimizer import (
    TrisectionOptimizer,
    TrisectionState,
    TrisectChoice,
    _split_thirds,
    _aggregate_weight,
)


# ============================================================
# Helpers
# ============================================================

def _make_node(
    idx: int,
    weight: int = 10,
    valid: bool = True,
) -> Node:
    """Create a minimal node for optimizer tests."""
    node = Node(
        node_id=f"n_{idx}",
        parent_id=None,
        entity_id=f"E_{idx}",
        content=f"Node {idx}",
        legacy_idx=idx,
        gate_signals=GateSignals(
            e_exists=True, r_exists=True, rule_exists=True,
            l1_l3_ok=True, l5_ok=True,
        ),
        raw_scores=RawScores(struct_points=5, domain_points=5, current_domain=1),
    )
    node.gate = IntegrityGate(
        err_complete=valid,
        deps_valid=valid,
        levels_valid=valid,
        order_valid=valid,
    )
    node.final_weight = weight
    return node


# ============================================================
# TestTrisectionDivision
# ============================================================

class TestTrisectionDivision:
    """Tests for splitting nodes into thirds."""

    def test_split_6_nodes(self):
        """6 nodes split evenly: 2-2-2."""
        nodes = [_make_node(i) for i in range(6)]
        left, middle, right = _split_thirds(nodes)
        assert len(left) == 2
        assert len(middle) == 2
        assert len(right) == 2

    def test_split_9_nodes(self):
        """9 nodes split evenly: 3-3-3."""
        nodes = [_make_node(i) for i in range(9)]
        left, middle, right = _split_thirds(nodes)
        assert len(left) == 3
        assert len(middle) == 3
        assert len(right) == 3

    def test_split_7_nodes_remainder(self):
        """7 nodes: 2-2-3 (remainder goes to right)."""
        nodes = [_make_node(i) for i in range(7)]
        left, middle, right = _split_thirds(nodes)
        assert len(left) == 2
        assert len(middle) == 2
        assert len(right) == 3
        # Verify all nodes accounted for
        assert len(left) + len(middle) + len(right) == 7

    def test_split_4_nodes_remainder(self):
        """4 nodes: 1-1-2 (remainder goes to right)."""
        nodes = [_make_node(i) for i in range(4)]
        left, middle, right = _split_thirds(nodes)
        assert len(left) == 1
        assert len(middle) == 1
        assert len(right) == 2

    def test_split_preserves_order(self):
        """Nodes stay in their original order within each group."""
        nodes = [_make_node(i) for i in range(9)]
        left, middle, right = _split_thirds(nodes)
        assert [n.legacy_idx for n in left] == [0, 1, 2]
        assert [n.legacy_idx for n in middle] == [3, 4, 5]
        assert [n.legacy_idx for n in right] == [6, 7, 8]


# ============================================================
# TestL5Resolution (tie-breaking)
# ============================================================

class TestL5Resolution:
    """Tests for policy-based tie-breaking in trisection."""

    def test_legacy_prefers_left(self):
        """LEGACY_PRIORITY: when all groups tie, LEFT wins."""
        nodes = [_make_node(i, weight=10) for i in range(9)]
        opt = TrisectionOptimizer(policy=Policy.LEGACY_PRIORITY)
        state = opt.optimize(nodes)
        # First choice should be LEFT
        assert state.history[0] == TrisectChoice.LEFT

    def test_recency_prefers_right(self):
        """RECENCY_PRIORITY: when all groups tie, RIGHT wins."""
        nodes = [_make_node(i, weight=10) for i in range(9)]
        opt = TrisectionOptimizer(policy=Policy.RECENCY_PRIORITY)
        state = opt.optimize(nodes)
        # First choice should be RIGHT
        assert state.history[0] == TrisectChoice.RIGHT

    def test_highest_weight_wins_regardless_of_policy(self):
        """The group with highest aggregate weight always wins, no tie-break needed."""
        # Middle group has higher weights
        nodes = []
        for i in range(9):
            w = 100 if 3 <= i <= 5 else 10
            nodes.append(_make_node(i, weight=w))
        opt = TrisectionOptimizer(policy=Policy.LEGACY_PRIORITY)
        state = opt.optimize(nodes)
        assert state.history[0] == TrisectChoice.MIDDLE


# ============================================================
# TestConvergence
# ============================================================

class TestConvergence:
    """Tests for iteration and convergence behavior."""

    def test_27_nodes_converge_in_3_iterations(self):
        """27 equal-weight nodes → 3 → 1 group in exactly 3 iterations (LEGACY: always LEFT)."""
        nodes = [_make_node(i, weight=10) for i in range(27)]
        opt = TrisectionOptimizer(policy=Policy.LEGACY_PRIORITY)
        state = opt.optimize(nodes)
        assert state.iterations == 3
        assert len(state.candidates) == 1

    def test_small_tree_under_3_no_iteration(self):
        """Fewer than 3 valid nodes -> no iteration needed."""
        nodes = [_make_node(0, weight=10), _make_node(1, weight=20)]
        opt = TrisectionOptimizer()
        state = opt.optimize(nodes)
        assert state.iterations == 0
        assert len(state.candidates) == 2

    def test_single_node_no_iteration(self):
        """Single node -> no iteration."""
        nodes = [_make_node(0)]
        opt = TrisectionOptimizer()
        state = opt.optimize(nodes)
        assert state.iterations == 0
        assert len(state.candidates) == 1

    def test_max_iterations_respected(self):
        """Optimizer stops after max_iterations even if not converged."""
        nodes = [_make_node(i, weight=10) for i in range(1000)]
        opt = TrisectionOptimizer(policy=Policy.LEGACY_PRIORITY, max_iterations=2)
        state = opt.optimize(nodes)
        assert state.iterations == 2

    def test_width_decreases(self):
        """Width should be (1/3)^iterations after convergence."""
        nodes = [_make_node(i, weight=10) for i in range(27)]
        opt = TrisectionOptimizer(policy=Policy.LEGACY_PRIORITY)
        state = opt.optimize(nodes)
        expected_width = (1 / 3) ** 3
        assert abs(state.width - expected_width) < 1e-9

    def test_converged_property(self):
        """TrisectionState.converged is True when fewer than 3 candidates remain."""
        nodes = [_make_node(i, weight=10) for i in range(9)]
        opt = TrisectionOptimizer(policy=Policy.LEGACY_PRIORITY)
        state = opt.optimize(nodes)
        assert state.converged is True

    def test_not_converged_with_max_iterations(self):
        """With max_iterations=1 on 27 nodes, we still have 9 candidates."""
        nodes = [_make_node(i, weight=10) for i in range(27)]
        opt = TrisectionOptimizer(policy=Policy.LEGACY_PRIORITY, max_iterations=1)
        state = opt.optimize(nodes)
        assert state.converged is False
        assert len(state.candidates) == 9


# ============================================================
# TestWeightAggregation
# ============================================================

class TestWeightAggregation:
    """Tests for weight aggregation and invalid-node filtering."""

    def test_aggregate_weight_sum(self):
        """Aggregate weight = sum of final_weight for all nodes."""
        nodes = [_make_node(0, weight=10), _make_node(1, weight=20), _make_node(2, weight=30)]
        assert _aggregate_weight(nodes) == 60

    def test_aggregate_weight_empty(self):
        """Empty list -> aggregate weight = 0."""
        assert _aggregate_weight([]) == 0

    def test_invalid_nodes_filtered_before_optimize(self):
        """Invalid nodes are excluded from the candidate set."""
        nodes = [
            _make_node(0, weight=100, valid=True),
            _make_node(1, weight=200, valid=False),  # invalid
            _make_node(2, weight=50, valid=True),
        ]
        opt = TrisectionOptimizer()
        state = opt.optimize(nodes)
        # Only 2 valid nodes -> no trisection (< 3)
        assert len(state.candidates) == 2
        assert state.iterations == 0
        # Invalid node not in candidates
        ids = [n.node_id for n in state.candidates]
        assert "n_1" not in ids

    def test_all_invalid_returns_empty(self):
        """All invalid nodes -> empty candidate set."""
        nodes = [_make_node(i, valid=False) for i in range(5)]
        opt = TrisectionOptimizer()
        state = opt.optimize(nodes)
        assert len(state.candidates) == 0
        assert state.iterations == 0

    def test_no_nodes_returns_empty(self):
        """Empty input -> empty candidate set."""
        opt = TrisectionOptimizer()
        state = opt.optimize([])
        assert len(state.candidates) == 0
        assert state.iterations == 0


# ============================================================
# TestSummary
# ============================================================

class TestSummary:
    """Tests for TrisectionState.summary()."""

    def test_summary_format(self):
        """Summary string includes iteration count and candidate IDs."""
        nodes = [_make_node(i, weight=10) for i in range(9)]
        opt = TrisectionOptimizer(policy=Policy.LEGACY_PRIORITY)
        state = opt.optimize(nodes)
        s = state.summary()
        assert "Trisection:" in s
        assert "iterations" in s
        assert "candidate" in s
