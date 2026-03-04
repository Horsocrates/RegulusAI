"""
Regulus AI - Socratic Trisection Tests
=======================================

Tests for SocraticTrisection: two-level selection integrating with Socratic Pipeline.

Level 1 (intra-domain): Selecting best version within a domain
Level 2 (cross-branch): Selecting best reasoning branch

Mathematical foundation: ShrinkingIntervals_uncountable_ERR.v
L5 Leftmost principle: L5_LEFTMOST_DEDUCTION.md
"""

import pytest
from regulus.core.types import Node, GateSignals, RawScores, IntegrityGate, Policy
from regulus.core.optimizer import (
    SocraticTrisection,
    SocraticTrisectionState,
    TrisectionResult,
    TrisectChoice,
)


# ============================================================
# Helpers
# ============================================================

def _make_node(
    idx: int,
    weight: int = 10,
    valid: bool = True,
    domain: str = "D1",
) -> Node:
    """Create a minimal node for trisection tests."""
    node = Node(
        node_id=f"{domain}_v{idx}",
        parent_id=None,
        entity_id=f"E_{domain}_{idx}",
        content=f"Node {domain} version {idx}",
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


def _make_branch(branch_id: int, weights: list[int]) -> list[Node]:
    """Create a branch (D3→D4→D5→D6) with specified weights."""
    domains = ["D3", "D4", "D5", "D6"]
    branch = []
    for i, (domain, weight) in enumerate(zip(domains, weights)):
        node = _make_node(idx=branch_id, weight=weight, domain=domain)
        node.node_id = f"{domain}_b{branch_id}"
        node.entity_id = f"E_{domain}_b{branch_id}"
        branch.append(node)
    return branch


# ============================================================
# TestIntraDomainSelection (Level 1)
# ============================================================

class TestIntraDomainSelection:
    """Level 1: selecting best version within a domain."""

    def test_single_version_returns_it(self):
        """One version → return it, no trisection needed."""
        versions = [_make_node(0, weight=50)]
        trisect = SocraticTrisection()
        selected = trisect.select_best_version(versions, domain="D1")
        assert selected == versions[0]
        assert trisect.state.total_iterations == 0

    def test_two_versions_returns_heavier(self):
        """Two versions → return higher weight, L5 leftmost on tie."""
        versions = [_make_node(0, weight=40), _make_node(1, weight=60)]
        trisect = SocraticTrisection()
        selected = trisect.select_best_version(versions, domain="D1")
        assert selected == versions[1]
        assert selected.final_weight == 60

    def test_two_versions_tie_returns_leftmost(self):
        """Two versions with same weight → L5 leftmost (v0) wins."""
        versions = [_make_node(0, weight=50), _make_node(1, weight=50)]
        trisect = SocraticTrisection()
        selected = trisect.select_best_version(versions, domain="D1")
        assert selected == versions[0]
        assert selected.legacy_idx == 0

    def test_three_versions_trisects(self):
        """Three versions → actual trisection applied."""
        versions = [
            _make_node(0, weight=30),
            _make_node(1, weight=60),
            _make_node(2, weight=45),
        ]
        trisect = SocraticTrisection()
        selected = trisect.select_best_version(versions, domain="D1")
        # Highest weight version should win
        assert selected == versions[1]
        assert selected.final_weight == 60

    def test_l5_leftmost_on_tie(self):
        """Equal weights → leftmost version wins (L5)."""
        versions = [
            _make_node(0, weight=50),
            _make_node(1, weight=50),
            _make_node(2, weight=50),
        ]
        trisect = SocraticTrisection(policy=Policy.LEGACY_PRIORITY)
        selected = trisect.select_best_version(versions, domain="D1")
        # L5: leftmost wins on tie
        assert selected.legacy_idx == 0

    def test_invalid_gate_excluded(self):
        """Versions with failed gates are never considered."""
        versions = [
            _make_node(0, weight=100, valid=False),  # Invalid - excluded
            _make_node(1, weight=30, valid=True),
            _make_node(2, weight=40, valid=True),
        ]
        trisect = SocraticTrisection()
        selected = trisect.select_best_version(versions, domain="D1")
        # v0 excluded (invalid), so v2 wins (higher weight among valid)
        assert selected == versions[2]
        assert selected.final_weight == 40

    def test_all_invalid_returns_last_fallback(self):
        """All versions invalid → returns last version as fallback."""
        versions = [
            _make_node(0, weight=100, valid=False),
            _make_node(1, weight=200, valid=False),
        ]
        trisect = SocraticTrisection()
        selected = trisect.select_best_version(versions, domain="D1")
        # Fallback: return last version
        assert selected == versions[-1]

    def test_domain_tracked_in_state(self):
        """Selected version is tracked in trisection state."""
        versions = [_make_node(0, weight=50), _make_node(1, weight=60)]
        trisect = SocraticTrisection()
        selected = trisect.select_best_version(versions, domain="D3")
        state = trisect.finalize()
        assert "D3" in state.domain_selections
        assert state.domain_selections["D3"] == selected

    def test_nine_versions_converges(self):
        """Nine versions → trisection converges through multiple iterations."""
        versions = [_make_node(i, weight=10 + i * 5) for i in range(9)]
        trisect = SocraticTrisection()
        selected = trisect.select_best_version(versions, domain="D2")
        # Highest weight (v8 with weight=50) should win
        assert selected == versions[8]
        # State should track iterations
        state = trisect.finalize()
        assert state.total_iterations >= 1


# ============================================================
# TestCrossBranchSelection (Level 2)
# ============================================================

class TestCrossBranchSelection:
    """Level 2: selecting best branch."""

    def test_single_branch_returns_it(self):
        """Single branch → return it, no selection needed."""
        branch = _make_branch(0, [50, 60, 70, 40])
        trisect = SocraticTrisection()
        selected = trisect.select_best_branch([branch])
        assert selected == branch

    def test_two_branches_returns_heavier(self):
        """Two branches → return higher aggregate weight."""
        branch_a = _make_branch(0, [50, 50, 50, 50])  # Total = 200
        branch_b = _make_branch(1, [60, 70, 80, 90])  # Total = 300
        trisect = SocraticTrisection()
        selected = trisect.select_best_branch([branch_a, branch_b])
        assert selected == branch_b

    def test_two_branches_tie_returns_leftmost(self):
        """Two branches with same weight → L5 leftmost wins."""
        branch_a = _make_branch(0, [50, 50, 50, 50])  # Total = 200
        branch_b = _make_branch(1, [50, 50, 50, 50])  # Total = 200
        trisect = SocraticTrisection()
        selected = trisect.select_best_branch([branch_a, branch_b])
        # L5: first branch wins on tie
        assert selected == branch_a

    def test_three_branches_selects_heaviest(self):
        """Three branches → trisection selects highest aggregate weight."""
        branch_a = _make_branch(0, [40, 40, 40, 40])  # Total = 160
        branch_b = _make_branch(1, [80, 80, 80, 80])  # Total = 320
        branch_c = _make_branch(2, [50, 50, 50, 50])  # Total = 200
        trisect = SocraticTrisection()
        selected = trisect.select_best_branch([branch_a, branch_b, branch_c])
        assert selected == branch_b

    def test_branch_weight_is_sum_of_valid_nodes(self):
        """Branch weight = sum of valid node weights only."""
        # Branch with one invalid node
        branch = _make_branch(0, [50, 60, 70, 40])
        branch[1].gate = IntegrityGate(
            err_complete=False, deps_valid=False,
            levels_valid=False, order_valid=False,
        )  # Make D4 invalid
        branch[1].final_weight = 1000  # High weight but invalid

        # Branch with all valid nodes
        branch_b = _make_branch(1, [50, 50, 50, 50])  # Total = 200

        trisect = SocraticTrisection()
        selected = trisect.select_best_branch([branch, branch_b])
        # Branch A valid weight = 50 + 70 + 40 = 160 (D4 excluded)
        # Branch B weight = 200
        # Branch B should win
        assert selected == branch_b

    def test_l5_leftmost_branch_on_tie(self):
        """Equal branch weights → first branch wins (L5)."""
        branches = [
            _make_branch(0, [50, 50, 50, 50]),
            _make_branch(1, [50, 50, 50, 50]),
            _make_branch(2, [50, 50, 50, 50]),
        ]
        trisect = SocraticTrisection(policy=Policy.LEGACY_PRIORITY)
        selected = trisect.select_best_branch(branches)
        # L5: first branch wins
        assert selected == branches[0]

    def test_branches_explored_tracked(self):
        """Number of branches explored is tracked in state."""
        branches = [
            _make_branch(0, [40, 40, 40, 40]),
            _make_branch(1, [60, 60, 60, 60]),
            _make_branch(2, [50, 50, 50, 50]),
        ]
        trisect = SocraticTrisection()
        trisect.select_best_branch(branches)
        state = trisect.finalize()
        assert state.branches_explored == 3

    def test_empty_branches_returns_empty(self):
        """Empty branch list → return empty list."""
        trisect = SocraticTrisection()
        selected = trisect.select_best_branch([])
        assert selected == []

    def test_all_invalid_branches_returns_first(self):
        """All branches with zero valid weight → return first as fallback."""
        branch_a = _make_branch(0, [50, 50, 50, 50])
        branch_b = _make_branch(1, [60, 60, 60, 60])
        # Make all nodes invalid
        for node in branch_a + branch_b:
            node.gate = IntegrityGate(
                err_complete=False, deps_valid=False,
                levels_valid=False, order_valid=False,
            )

        trisect = SocraticTrisection()
        selected = trisect.select_best_branch([branch_a, branch_b])
        # Fallback: return first branch
        assert selected == branch_a


# ============================================================
# TestCoqAnalogy
# ============================================================

class TestCoqAnalogy:
    """Verify the algorithm matches Coq trisection properties."""

    def test_width_shrinks_by_third(self):
        """After each step, candidate set ~ 1/3 of previous."""
        # 27 versions → should take ~3 iterations to converge
        versions = [_make_node(i, weight=10 + i) for i in range(27)]
        trisect = SocraticTrisection()
        selected = trisect.select_best_version(versions, domain="D1")
        state = trisect.finalize()
        # Should converge (highest weight wins)
        assert selected == versions[26]  # Highest weight
        # Multiple iterations should occur
        assert state.total_iterations >= 1

    def test_convergence(self):
        """Repeated trisection → single candidate emerges."""
        versions = [_make_node(i, weight=100 - i) for i in range(9)]
        trisect = SocraticTrisection()
        selected = trisect.select_best_version(versions, domain="D1")
        # First version has highest weight (100)
        assert selected == versions[0]
        assert selected.final_weight == 100

    def test_determinism(self):
        """Same input → same output always (L5 guarantee)."""
        versions = [_make_node(i, weight=50) for i in range(9)]

        trisect1 = SocraticTrisection(policy=Policy.LEGACY_PRIORITY)
        r1 = trisect1.select_best_version(versions[:], domain="D1")

        trisect2 = SocraticTrisection(policy=Policy.LEGACY_PRIORITY)
        r2 = trisect2.select_best_version(versions[:], domain="D1")

        assert r1.node_id == r2.node_id
        assert r1.legacy_idx == r2.legacy_idx

    def test_gate_zero_means_annihilation(self):
        """Gate=0 → node excluded entirely, not just penalized."""
        versions = [
            _make_node(0, weight=1000, valid=False),  # High weight but invalid
            _make_node(1, weight=10, valid=True),     # Low weight but valid
        ]
        trisect = SocraticTrisection()
        selected = trisect.select_best_version(versions, domain="D1")
        # Invalid node excluded (annihilation), valid node wins
        assert selected == versions[1]
        assert selected.final_weight == 10


# ============================================================
# TestStateTracking
# ============================================================

class TestStateTracking:
    """Tests for SocraticTrisectionState tracking."""

    def test_reset_clears_state(self):
        """reset() clears all state for new query."""
        trisect = SocraticTrisection()

        # First query
        versions = [_make_node(0, weight=50), _make_node(1, weight=60)]
        trisect.select_best_version(versions, domain="D1")
        assert len(trisect.state.domain_selections) == 1

        # Reset
        trisect.reset()
        assert len(trisect.state.domain_selections) == 0
        assert trisect.state.total_iterations == 0

    def test_finalize_returns_complete_state(self):
        """finalize() returns complete state with all tracking."""
        trisect = SocraticTrisection()

        # Process multiple domains
        for domain in ["D1", "D2", "D3"]:
            versions = [_make_node(i, weight=40 + i * 10) for i in range(3)]
            trisect.select_best_version(versions, domain=domain)

        state = trisect.finalize()
        assert len(state.domain_selections) == 3
        assert "D1" in state.domain_selections
        assert "D2" in state.domain_selections
        assert "D3" in state.domain_selections

    def test_summary_output(self):
        """State summary includes key metrics."""
        trisect = SocraticTrisection()
        versions = [_make_node(i, weight=50) for i in range(3)]
        trisect.select_best_version(versions, domain="D1")

        state = trisect.finalize()
        summary = state.summary()
        assert "SocraticTrisection" in summary
        assert "iterations" in summary
        assert "domains" in summary


# ============================================================
# TestPolicyBehavior
# ============================================================

class TestPolicyBehavior:
    """Tests for policy-based tie-breaking."""

    def test_legacy_priority_prefers_left(self):
        """LEGACY_PRIORITY: leftmost group wins on tie."""
        versions = [_make_node(i, weight=50) for i in range(9)]
        trisect = SocraticTrisection(policy=Policy.LEGACY_PRIORITY)
        selected = trisect.select_best_version(versions, domain="D1")
        # Should select from left group (lowest indices)
        assert selected.legacy_idx < 3  # Left third

    def test_recency_priority_still_l5_for_versions(self):
        """
        For intra-domain selection, L5 leftmost always applies.
        RECENCY_PRIORITY only affects cross-branch selection in Status Machine.
        """
        versions = [_make_node(i, weight=50) for i in range(9)]
        trisect = SocraticTrisection(policy=Policy.RECENCY_PRIORITY)
        selected = trisect.select_best_version(versions, domain="D1")
        # L5 leftmost still applies
        assert selected.legacy_idx < 3
