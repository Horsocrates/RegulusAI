"""
LogicGuard MVP - Weight Calculation Module
==========================================

Weight Formula: W(e) = G_total × (S_struct + S_domain)

Where:
- G_total: Zero-Gate (0 or 1)
- S_struct: Structural completeness (ERR points)
- S_domain: Procedural progress (domain traversal)

Scoring Rules (from Gemini spec):
- S_struct = points_E + points_R + points_Rule
- S_domain = current_domain_index × 10 + domain_quality_score
"""

from typing import Optional
from .types import Node, RawScores, IntegrityGate
from .zero_gate import apply_zero_gate


def compute_struct_score(raw_scores: RawScores) -> int:
    """
    Compute S_struct: Structural completeness score.
    
    In MVP, this is simply the struct_points from input.
    In future, this could be computed from individual E/R/R scores.
    
    Formula: S_struct = points_E + points_R + points_Rule
    (Pre-computed as struct_points in input)
    """
    return raw_scores.struct_points


def compute_domain_score(raw_scores: RawScores) -> int:
    """
    Compute S_domain: Procedural progress score.
    
    Formula: S_domain = current_domain_index × 10 + domain_quality_score
    
    Rationale: 
    - Higher domain = further progression through D1→D6 sequence
    - Multiplier (10) ensures domain progression dominates
    - Quality score differentiates within same domain
    """
    domain_idx = raw_scores.current_domain  # 1-6
    quality = raw_scores.domain_points
    
    return (domain_idx * 10) + quality


def compute_base_weight(raw_scores: RawScores) -> int:
    """
    Compute base weight before Zero-Gate application.
    
    W_base = S_struct + S_domain
    """
    s_struct = compute_struct_score(raw_scores)
    s_domain = compute_domain_score(raw_scores)
    
    return s_struct + s_domain


def compute_final_weight(node: Node, gate: IntegrityGate) -> int:
    """
    Compute final weight with Zero-Gate applied.
    
    W(e) = G_total × (S_struct + S_domain)
    
    If G_total = 0 (any gate failed), W = 0 (annihilation)
    """
    base_weight = compute_base_weight(node.raw_scores)
    return apply_zero_gate(gate, base_weight)


# ============================================================
# Weight Comparison (for Status Machine)
# ============================================================

def compare_weights(w1: int, w2: int) -> int:
    """
    Compare two weights.
    
    Returns:
        -1 if w1 < w2
         0 if w1 == w2
         1 if w1 > w2
    """
    if w1 < w2:
        return -1
    elif w1 > w2:
        return 1
    else:
        return 0


def is_refinement(old_node: Node, new_node: Node) -> bool:
    """
    Check if new_node is a valid refinement of old_node.
    
    Refinement conditions (from spec):
    1. Same entity_id (same reasoning chain)
    2. New node passes Zero-Gate (G_total = 1)
    3. New weight >= old weight (non-decreasing)
    
    Returns:
        True if new_node is a valid refinement
    """
    # Condition 1: Same entity
    if new_node.entity_id != old_node.entity_id:
        return False
    
    # Condition 2: New node is valid
    if new_node.gate is None or not new_node.gate.is_valid:
        return False
    
    # Condition 3: Weight non-decreasing
    if new_node.final_weight < old_node.final_weight:
        return False
    
    return True


def is_strict_improvement(old_node: Node, new_node: Node) -> bool:
    """
    Check if new_node strictly improves on old_node.
    
    Strict improvement (from spec - Refinement Rule):
    - G_total(new) = 1 AND W(new) > W(old)
    
    We prefer newer only if STRUCTURALLY SUPERIOR,
    not just because it's new (Law of Sufficient Reason L4).
    """
    if not is_refinement(old_node, new_node):
        return False
    
    return new_node.final_weight > old_node.final_weight


# ============================================================
# Weight Analysis Utilities
# ============================================================

def weight_breakdown(node: Node) -> dict:
    """
    Return detailed breakdown of weight calculation.
    Useful for debugging and diagnostics.
    """
    s_struct = compute_struct_score(node.raw_scores)
    s_domain = compute_domain_score(node.raw_scores)
    base = s_struct + s_domain
    
    gate_valid = node.gate.is_valid if node.gate else False
    final = node.final_weight
    
    return {
        "node_id": node.node_id,
        "S_struct": s_struct,
        "S_domain": s_domain,
        "base_weight": base,
        "gate_valid": gate_valid,
        "final_weight": final,
        "formula": f"W = {1 if gate_valid else 0} × ({s_struct} + {s_domain}) = {final}"
    }
