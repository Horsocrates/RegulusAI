"""
Regulus AI - Trisection Optimizer
==================================

Interval-narrowing optimizer that reduces the candidate set by repeatedly
splitting nodes into thirds and selecting the best-weighted group.

Algorithm:
    1. Filter valid nodes (gate.is_valid), sort by legacy_idx
    2. While len(candidates) >= 3 and iterations < max:
       - Split into thirds: [:n//3], [n//3:2*n//3], [2*n//3:]
       - Aggregate weight per group (sum of final_weight)
       - Select best group; tie-break: LEFT for LEGACY, RIGHT for RECENCY
       - Track width / delta convergence
    3. Return TrisectionState with final candidate set

The optimizer does NOT modify node weights or statuses. It selects a subset
of candidates that the Status Machine can then rank independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Dict, Callable, Any, TypeVar

from .types import Node, Policy

T = TypeVar('T')


class TrisectChoice(Enum):
    """Which third was selected in a trisection step."""
    LEFT = auto()
    MIDDLE = auto()
    RIGHT = auto()


@dataclass
class TrisectionState:
    """Snapshot of the optimizer state after convergence."""
    candidates: List[Node]
    iterations: int
    width: float
    delta: float
    history: List[TrisectChoice] = field(default_factory=list)

    @property
    def converged(self) -> bool:
        """True if the candidate set was reduced to fewer than 3 nodes."""
        return len(self.candidates) < 3

    def summary(self) -> str:
        n = len(self.candidates)
        ids = [c.node_id for c in self.candidates]
        choices = [c.name for c in self.history]
        return (
            f"Trisection: {self.iterations} iterations, "
            f"{n} candidate(s) remaining {ids}, "
            f"width={self.width:.4f}, delta={self.delta:.4f}, "
            f"path={choices}"
        )


def _aggregate_weight(group: List[Node]) -> int:
    """Sum final_weight of all nodes in a group."""
    return sum(n.final_weight for n in group)


def _split_thirds(nodes: List[Node]) -> tuple[List[Node], List[Node], List[Node]]:
    """
    Split a sorted list into three groups.

    For n nodes:
      left   = nodes[:n//3]
      middle = nodes[n//3 : 2*n//3]
      right  = nodes[2*n//3:]

    Remainder nodes go to the right group (last slice takes the rest).
    """
    n = len(nodes)
    t = n // 3
    left = nodes[:t]
    middle = nodes[t:2 * t]
    right = nodes[2 * t:]
    return left, middle, right


class TrisectionOptimizer:
    """
    Trisection-based candidate narrowing.

    Repeatedly splits the valid candidate set into thirds, picks the
    group with the highest aggregate weight, and narrows until fewer
    than 3 candidates remain or max_iterations is reached.

    Args:
        policy: Tie-breaking policy (affects which group wins on equal weight)
        max_iterations: Maximum number of trisection rounds
    """

    def __init__(
        self,
        policy: Policy = Policy.LEGACY_PRIORITY,
        max_iterations: int = 20,
    ):
        self.policy = policy
        self.max_iterations = max_iterations

    def optimize(self, nodes: List[Node]) -> TrisectionState:
        """
        Run trisection optimization on a list of nodes.

        Filters to valid nodes, sorts by legacy_idx, then iteratively
        narrows the candidate set.

        Returns:
            TrisectionState with the final candidate subset.
        """
        # Filter valid nodes and sort by legacy_idx
        candidates = sorted(
            [n for n in nodes if n.gate and n.gate.is_valid],
            key=lambda n: n.legacy_idx,
        )

        width = 1.0
        delta = 1.0
        history: list[TrisectChoice] = []
        iterations = 0

        while len(candidates) >= 3 and iterations < self.max_iterations:
            left, middle, right = _split_thirds(candidates)

            w_left = _aggregate_weight(left)
            w_middle = _aggregate_weight(middle)
            w_right = _aggregate_weight(right)

            choice, candidates = self._select_best(
                left, w_left, middle, w_middle, right, w_right,
            )

            history.append(choice)
            iterations += 1
            delta = width - width / 3
            width /= 3

        return TrisectionState(
            candidates=candidates,
            iterations=iterations,
            width=width,
            delta=delta,
            history=history,
        )

    def _select_best(
        self,
        left: List[Node], w_left: int,
        middle: List[Node], w_middle: int,
        right: List[Node], w_right: int,
    ) -> tuple[TrisectChoice, List[Node]]:
        """
        Select the group with the highest aggregate weight.

        Tie-breaking:
          - LEGACY_PRIORITY  -> prefer LEFT  (earlier nodes)
          - RECENCY_PRIORITY -> prefer RIGHT (later nodes)
        """
        max_w = max(w_left, w_middle, w_right)

        # Collect groups that tie at max weight
        tied: list[tuple[TrisectChoice, List[Node]]] = []
        if w_left == max_w:
            tied.append((TrisectChoice.LEFT, left))
        if w_middle == max_w:
            tied.append((TrisectChoice.MIDDLE, middle))
        if w_right == max_w:
            tied.append((TrisectChoice.RIGHT, right))

        if len(tied) == 1:
            return tied[0]

        # Tie-break by policy
        if self.policy == Policy.LEGACY_PRIORITY:
            return tied[0]   # LEFT-most among tied
        else:
            return tied[-1]  # RIGHT-most among tied


# ============================================================
# Socratic Trisection — Two-Level Selection
# ============================================================

@dataclass
class TrisectionResult:
    """Result of a single trisection step."""
    winner: List[Any]           # Winning candidates (nodes or branches)
    eliminated: List[Any]       # Excluded candidates
    choice: TrisectChoice       # Which third won
    weights: Dict[TrisectChoice, float]  # Weight per third
    iteration: int


@dataclass
class SocraticTrisectionState:
    """Full state tracking for Socratic trisection."""
    # Intra-domain results (domain_name → selected version)
    domain_selections: Dict[str, Node] = field(default_factory=dict)
    # Branch results (if branching occurred)
    branch_results: List[TrisectionResult] = field(default_factory=list)
    # Intra-domain trisection results
    domain_trisection_results: Dict[str, TrisectionResult] = field(default_factory=dict)
    # Final result
    final_result: Optional[TrisectionResult] = None
    # Total iterations across all levels
    total_iterations: int = 0
    # Branches explored (1 if no branching)
    branches_explored: int = 1

    def summary(self) -> str:
        domain_count = len(self.domain_selections)
        branch_count = self.branches_explored
        return (
            f"SocraticTrisection: {self.total_iterations} iterations, "
            f"{domain_count} domains selected, {branch_count} branch(es) explored"
        )


class SocraticTrisection:
    """
    Two-level trisection integrated with Socratic Pipeline.

    Level 1 (intra-domain): Select best probe version within a domain.
        When a domain generates multiple versions via probing, trisection
        selects the structurally strongest version, not just the last one.

    Level 2 (cross-branch): Select best reasoning branch when D3 generates
        multiple frameworks. Each framework spawns a complete D4→D5→D6 chain,
        and trisection selects the best overall branch.

    Mathematical foundation: ShrinkingIntervals_uncountable_ERR.v
        - Width shrinks by factor 3 per iteration
        - L5 leftmost tie-breaking ensures determinism
        - Convergence guaranteed (candidates → 1)

    L5 Leftmost Principle (from L5_LEFTMOST_DEDUCTION.md):
        When multiple candidates share equal weight, the earliest position
        (lowest index) wins. This is not a heuristic — it is the L5-canonical
        method for resolving ambiguity.
    """

    def __init__(self, policy: Policy = Policy.LEGACY_PRIORITY):
        self.policy = policy
        self._state = SocraticTrisectionState()

    @property
    def state(self) -> SocraticTrisectionState:
        """Get the current trisection state."""
        return self._state

    def reset(self) -> None:
        """Reset state for a new query."""
        self._state = SocraticTrisectionState()

    # ----------------------------------------------------------
    # Level 1: Intra-Domain Selection
    # ----------------------------------------------------------

    def select_best_version(
        self,
        versions: List[Node],
        domain: str = "",
    ) -> Node:
        """
        Given multiple probe versions of a single domain,
        select the structurally strongest.

        Args:
            versions: List of Node versions for the same domain
            domain: Domain identifier (for state tracking)

        Returns:
            The selected best Node

        Rules:
            - Gate-failed nodes are EXCLUDED (not penalized)
            - If len(valid) < 3: return highest-weight (L5 leftmost on tie)
            - If len(valid) >= 3: apply trisection

        L5 Guarantee: Deterministic output for same input.
        """
        # Filter to only gate-passing versions
        valid = [v for v in versions if v.gate and v.gate.is_valid]

        if not valid:
            # No valid versions — return last version as fallback
            return versions[-1] if versions else None

        if len(valid) == 1:
            selected = valid[0]
        elif len(valid) == 2:
            # Two versions: return higher weight, L5 leftmost on tie
            selected = self._select_by_weight(valid)
        else:
            # Three or more: apply trisection
            selected, result = self._trisect_nodes(valid)
            if domain:
                self._state.domain_trisection_results[domain] = result
                self._state.total_iterations += result.iteration

        if domain:
            self._state.domain_selections[domain] = selected

        return selected

    def _select_by_weight(self, nodes: List[Node]) -> Node:
        """
        Select node with highest weight. L5 leftmost on tie.

        Nodes are assumed to be sorted by legacy_idx (creation order).
        """
        if not nodes:
            return None

        # Sort by legacy_idx to ensure L5 ordering
        sorted_nodes = sorted(nodes, key=lambda n: n.legacy_idx)

        max_weight = max(n.final_weight for n in sorted_nodes)
        # Return first (leftmost) node with max weight
        for n in sorted_nodes:
            if n.final_weight == max_weight:
                return n

        return sorted_nodes[0]

    def _trisect_nodes(
        self,
        nodes: List[Node],
    ) -> tuple[Node, TrisectionResult]:
        """
        Apply trisection to select best node from 3+ candidates.

        Returns (selected_node, trisection_result)
        """
        # Sort by legacy_idx for consistent ordering
        candidates = sorted(nodes, key=lambda n: n.legacy_idx)
        iteration = 0

        while len(candidates) >= 3:
            left, middle, right = _split_thirds(candidates)

            w_left = _aggregate_weight(left)
            w_middle = _aggregate_weight(middle)
            w_right = _aggregate_weight(right)

            weights = {
                TrisectChoice.LEFT: w_left,
                TrisectChoice.MIDDLE: w_middle,
                TrisectChoice.RIGHT: w_right,
            }

            # Select best group
            max_w = max(w_left, w_middle, w_right)
            if w_left == max_w:
                choice, candidates = TrisectChoice.LEFT, left
                eliminated = middle + right
            elif w_middle == max_w:
                choice, candidates = TrisectChoice.MIDDLE, middle
                eliminated = left + right
            else:
                choice, candidates = TrisectChoice.RIGHT, right
                eliminated = left + middle

            # L5 tie-breaking: if multiple groups tie, select leftmost
            tied_count = sum(1 for w in [w_left, w_middle, w_right] if w == max_w)
            if tied_count > 1:
                # Prefer LEFT (L5 leftmost)
                if w_left == max_w:
                    choice, candidates = TrisectChoice.LEFT, left
                    eliminated = middle + right
                elif w_middle == max_w:
                    choice, candidates = TrisectChoice.MIDDLE, middle
                    eliminated = left + right

            iteration += 1

        # Final selection from remaining candidates
        selected = self._select_by_weight(candidates)

        result = TrisectionResult(
            winner=candidates,
            eliminated=[],  # Not tracked per iteration
            choice=choice if iteration > 0 else TrisectChoice.LEFT,
            weights=weights if iteration > 0 else {},
            iteration=iteration,
        )

        return selected, result

    # ----------------------------------------------------------
    # Level 2: Cross-Branch Selection
    # ----------------------------------------------------------

    def select_best_branch(
        self,
        branches: List[List[Node]],
    ) -> List[Node]:
        """
        Given multiple complete reasoning branches (each is D3→D4→D5→D6),
        select the best branch using trisection on aggregate weights.

        Args:
            branches: List of branches, where each branch is a list of Nodes

        Returns:
            The selected best branch (list of Nodes)

        Rules:
            - Each branch is scored by sum of node weights (valid nodes only)
            - Branches with all-invalid nodes are excluded
            - Trisection divides branches into thirds, selects highest-weight third
            - L5: leftmost branch wins on tie

        Example:
            Branch A: D3_a → D4_a → D5_a → D6_a (total = 180)
            Branch B: D3_b → D4_b → D5_b → D6_b (total = 220)
            Branch C: D3_c → D4_c → D5_c → D6_c (total = 195)
            → Branch B selected
        """
        if not branches:
            return []

        self._state.branches_explored = len(branches)

        if len(branches) == 1:
            return branches[0]

        # Compute aggregate weight per branch (valid nodes only)
        def branch_weight(branch: List[Node]) -> float:
            return sum(
                n.final_weight for n in branch
                if n.gate and n.gate.is_valid
            )

        # Filter out branches with zero weight (all invalid)
        valid_branches = [b for b in branches if branch_weight(b) > 0]

        if not valid_branches:
            # All branches invalid — return first as fallback
            return branches[0]

        if len(valid_branches) == 1:
            return valid_branches[0]

        if len(valid_branches) == 2:
            # Two branches: return heavier, L5 leftmost on tie
            w0 = branch_weight(valid_branches[0])
            w1 = branch_weight(valid_branches[1])
            if w0 >= w1:  # L5: >= means leftmost wins on tie
                return valid_branches[0]
            return valid_branches[1]

        # Three or more: apply trisection
        selected, result = self._trisect_branches(valid_branches, branch_weight)
        self._state.branch_results.append(result)
        self._state.total_iterations += result.iteration

        return selected

    def _trisect_branches(
        self,
        branches: List[List[Node]],
        weight_fn: Callable[[List[Node]], float],
    ) -> tuple[List[Node], TrisectionResult]:
        """
        Apply trisection to select best branch from 3+ candidates.

        Returns (selected_branch, trisection_result)
        """
        candidates = list(branches)  # Preserve order (L5)
        iteration = 0
        last_weights = {}
        last_choice = TrisectChoice.LEFT

        while len(candidates) >= 3:
            n = len(candidates)
            t = n // 3

            left = candidates[:t]
            middle = candidates[t:2*t]
            right = candidates[2*t:]

            # Aggregate weight per group
            w_left = sum(weight_fn(b) for b in left)
            w_middle = sum(weight_fn(b) for b in middle)
            w_right = sum(weight_fn(b) for b in right)

            last_weights = {
                TrisectChoice.LEFT: w_left,
                TrisectChoice.MIDDLE: w_middle,
                TrisectChoice.RIGHT: w_right,
            }

            max_w = max(w_left, w_middle, w_right)

            # Select best group with L5 tie-breaking (prefer LEFT)
            if w_left >= w_middle and w_left >= w_right:
                last_choice, candidates = TrisectChoice.LEFT, left
                eliminated = middle + right
            elif w_middle >= w_right:
                last_choice, candidates = TrisectChoice.MIDDLE, middle
                eliminated = left + right
            else:
                last_choice, candidates = TrisectChoice.RIGHT, right
                eliminated = left + middle

            iteration += 1

        # Final selection from remaining candidates
        if len(candidates) == 1:
            selected = candidates[0]
        else:
            # 2 candidates: pick heavier, L5 leftmost on tie
            w0 = weight_fn(candidates[0])
            w1 = weight_fn(candidates[1]) if len(candidates) > 1 else 0
            selected = candidates[0] if w0 >= w1 else candidates[1]

        result = TrisectionResult(
            winner=candidates,
            eliminated=[],
            choice=last_choice,
            weights=last_weights,
            iteration=iteration,
        )

        return selected, result

    # ----------------------------------------------------------
    # Convenience: Full Socratic Selection
    # ----------------------------------------------------------

    def finalize(self) -> SocraticTrisectionState:
        """
        Finalize and return the complete trisection state.

        Call this after all domain and branch selections are complete.
        """
        return self._state
