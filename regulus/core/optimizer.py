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
from typing import List, Optional

from .types import Node, Policy


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
