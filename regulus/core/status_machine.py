"""
Regulus AI - Status Machine Module
===================================

The Status Machine implements deterministic selection via L5 (Law of Order).

Five Statuses:
- PrimaryMax: The unique winner
- SecondaryMax: Valid alternative with equal weight
- HistoricalMax: Was Primary, now superseded
- Candidate: Valid but not maximum
- Invalid: Gate = 0 (hallucination)

L5-Resolution Rule:
1. Compare by W(e) descending
2. If W(e1) = W(e2), compare by legacy_idx ascending (earlier wins)

Verified Properties (from Coq):
- Uniqueness: Exactly one PrimaryMax per level
- Stability: Invalid cannot become PrimaryMax
- Diagnostic: Failed gate is identifiable
"""

from typing import List, Optional, Dict, Tuple
from .types import Node, Status, Policy, Diagnostic, IntegrityGate
from .weight import compare_weights


def compare_entities(e1: Node, e2: Node, policy: Policy = Policy.LEGACY_PRIORITY) -> int:
    """
    Compare two entities according to L5-Resolution.

    Algorithm:
    1. Compare by weight (higher wins)
    2. If tied, use policy:
       - LEGACY_PRIORITY: lower legacy_idx wins (earlier wins)
       - RECENCY_PRIORITY: higher legacy_idx wins (later wins)

    Returns:
        -1 if e1 < e2 (e2 wins)
         0 if e1 == e2 (tie - should not happen with unique legacy_idx)
         1 if e1 > e2 (e1 wins)
    """
    # Step 1: Compare weights
    weight_cmp = compare_weights(e1.final_weight, e2.final_weight)

    if weight_cmp != 0:
        return weight_cmp

    # Step 2: Weights equal - use policy for tie-breaking
    if policy == Policy.LEGACY_PRIORITY:
        # Lower legacy_idx wins (earlier is better)
        if e1.legacy_idx < e2.legacy_idx:
            return 1   # e1 wins (earlier)
        elif e1.legacy_idx > e2.legacy_idx:
            return -1  # e2 wins (earlier)
        else:
            return 0   # Same legacy_idx (shouldn't happen)

    else:  # RECENCY_PRIORITY
        # Higher legacy_idx wins (later is better)
        if e1.legacy_idx > e2.legacy_idx:
            return 1   # e1 wins (later)
        elif e1.legacy_idx < e2.legacy_idx:
            return -1  # e2 wins (later)
        else:
            return 0


def find_max_entity(
    nodes: List[Node],
    policy: Policy = Policy.LEGACY_PRIORITY,
    use_evt: bool = False,
) -> Optional[Node]:
    """
    Find the entity with maximum weight (PrimaryMax candidate).
    Uses L5-Resolution for tie-breaking.

    Only considers valid nodes (gate.is_valid == True).

    When *use_evt* is True, uses the Coq-verified ``argmax_idx`` from
    EVT_idx.v instead of the hand-written comparison loop.  This
    guarantees:
        - argmax_idx_bound:     returned index is valid
        - argmax_idx_maximizes: selected node has the highest weight

    L5 leftmost tie-breaking is achieved by sorting nodes in descending
    legacy_idx order before calling argmax_idx (which updates on ``<=``,
    giving the last equal index — the lowest legacy_idx after reversal).
    """
    valid_nodes = [n for n in nodes if n.gate and n.gate.is_valid]

    if not valid_nodes:
        return None

    if use_evt:
        from regulus.interval.evt import argmax_idx as evt_argmax_idx

        # Sort descending by legacy_idx so that argmax_idx's rightmost-
        # on-equal behaviour selects the node with the *lowest* legacy_idx
        # (L5 leftmost tie-breaking).
        sorted_nodes = sorted(valid_nodes, key=lambda n: -n.legacy_idx)
        idx = evt_argmax_idx(
            f=lambda x: x.final_weight,
            lst=sorted_nodes,
        )
        return sorted_nodes[idx]

    # Original implementation (preserved for backward compatibility)
    max_node = valid_nodes[0]
    for node in valid_nodes[1:]:
        if compare_entities(node, max_node, policy) > 0:
            max_node = node

    return max_node


def find_secondary_max(nodes: List[Node], primary: Node,
                        policy: Policy = Policy.LEGACY_PRIORITY) -> List[Node]:
    """
    Find all nodes with weight equal to PrimaryMax.
    These become SecondaryMax (valid alternatives).
    """
    if primary is None:
        return []

    secondary = []
    for node in nodes:
        if node.node_id == primary.node_id:
            continue
        if node.gate and node.gate.is_valid:
            if node.final_weight == primary.final_weight:
                secondary.append(node)

    return secondary


def find_historical_max(nodes: List[Node], entity_history: Dict[str, List[Node]]) -> List[Node]:
    """
    Find nodes that were PrimaryMax in earlier state but got superseded.

    A node is HistoricalMax if:
    - It was valid (gate passed)
    - Same entity_id has a newer node with higher weight
    """
    historical = []

    for entity_id, versions in entity_history.items():
        if len(versions) <= 1:
            continue

        # Sort by legacy_idx to get chronological order
        sorted_versions = sorted(versions, key=lambda n: n.legacy_idx)

        # Check if later version superseded earlier
        for i, old_node in enumerate(sorted_versions[:-1]):
            if old_node.gate and old_node.gate.is_valid:
                # Check if any later node has higher weight
                for new_node in sorted_versions[i+1:]:
                    if new_node.gate and new_node.gate.is_valid:
                        if new_node.final_weight > old_node.final_weight:
                            if old_node not in historical:
                                historical.append(old_node)
                            break

    return historical


def build_entity_history(nodes: List[Node]) -> Dict[str, List[Node]]:
    """
    Group nodes by entity_id to track refinement chains.
    """
    history: Dict[str, List[Node]] = {}

    for node in nodes:
        if node.entity_id not in history:
            history[node.entity_id] = []
        history[node.entity_id].append(node)

    return history


def assign_status(node: Node, nodes: List[Node],
                   policy: Policy = Policy.LEGACY_PRIORITY,
                   entity_history: Optional[Dict[str, List[Node]]] = None) -> Status:
    """
    Assign status to a single node based on its position in the ranking.

    Status Assignment Logic:
    1. If gate invalid → Invalid
    2. If highest weight (with L5 tie-breaking) → PrimaryMax
    3. If equal weight to Primary → SecondaryMax
    4. If was Primary but superseded → HistoricalMax
    5. Otherwise → Candidate
    """
    # Rule 1: Invalid if gate failed
    if node.gate is None or not node.gate.is_valid:
        return Status.INVALID

    # Find the primary
    primary = find_max_entity(nodes, policy)

    if primary is None:
        # No valid nodes - shouldn't happen if this node is valid
        return Status.CANDIDATE

    # Rule 2: Check if this is PrimaryMax
    if node.node_id == primary.node_id:
        return Status.PRIMARY_MAX

    # Rule 3: Check if SecondaryMax (equal weight to primary)
    if node.final_weight == primary.final_weight:
        return Status.SECONDARY_MAX

    # Rule 4: Check if HistoricalMax
    if entity_history is not None:
        historical = find_historical_max(nodes, entity_history)
        if node in historical:
            return Status.HISTORICAL_MAX

    # Rule 5: Default to Candidate
    return Status.CANDIDATE


def assign_all_statuses(nodes: List[Node],
                         policy: Policy = Policy.LEGACY_PRIORITY) -> List[Node]:
    """
    Assign statuses to all nodes in a reasoning tree.
    Modifies nodes in-place and returns them.
    """
    entity_history = build_entity_history(nodes)

    for node in nodes:
        node.status = assign_status(node, nodes, policy, entity_history)

    return nodes


# ============================================================
# Verified Properties (Runtime Checks)
# ============================================================

def verify_uniqueness(nodes: List[Node]) -> Tuple[bool, str]:
    """
    Verify: At most one PrimaryMax exists.

    This is the Coq-proven uniqueness theorem.
    """
    primary_count = sum(1 for n in nodes if n.status == Status.PRIMARY_MAX)

    if primary_count <= 1:
        return True, f"Uniqueness verified: {primary_count} PrimaryMax"
    else:
        return False, f"Uniqueness VIOLATED: {primary_count} PrimaryMax found!"


def verify_stability(nodes: List[Node]) -> Tuple[bool, str]:
    """
    Verify: Invalid cannot become PrimaryMax.

    This is the Coq-proven stability theorem.
    """
    for node in nodes:
        if node.gate is None or not node.gate.is_valid:
            if node.status == Status.PRIMARY_MAX:
                return False, f"Stability VIOLATED: Invalid node {node.node_id} is PrimaryMax!"

    return True, "Stability verified: No invalid node is PrimaryMax"


def verify_zero_gate_law(nodes: List[Node]) -> Tuple[bool, str]:
    """
    Verify: G = 0 ⇒ W = 0

    The fundamental Zero-Gate property.
    """
    for node in nodes:
        if node.gate and not node.gate.is_valid:
            if node.final_weight != 0:
                return False, f"Zero-Gate Law VIOLATED: Node {node.node_id} has gate=0 but weight={node.final_weight}!"

    return True, "Zero-Gate Law verified: All invalid nodes have weight=0"


def run_all_verifications(nodes: List[Node]) -> Dict[str, Tuple[bool, str]]:
    """
    Run all Coq-proven property verifications.
    """
    return {
        "uniqueness": verify_uniqueness(nodes),
        "stability": verify_stability(nodes),
        "zero_gate_law": verify_zero_gate_law(nodes)
    }


# ============================================================
# Diagnostic Generation
# ============================================================

def create_diagnostic(node: Node, diagnostic_code: Optional[str] = None,
                       reason: Optional[str] = None) -> Diagnostic:
    """
    Create a Diagnostic object for a node.
    """
    gate_vector = node.gate.to_dict() if node.gate else {
        "ERR": "N/A", "Levels": "N/A", "Order": "N/A", "G_total": False
    }

    return Diagnostic(
        node_id=node.node_id,
        entity_id=node.entity_id,
        status=node.status,
        gate_vector=gate_vector,
        final_weight=node.final_weight,
        diagnostic_code=diagnostic_code,
        reason=reason
    )
