"""
Regulus AI - Zero-Gate Module
=============================

The Zero-Gate Mechanism: G(e) = ⟨g_ERR, g_Levels, g_Order⟩

Key Property: If ANY gate fails, weight = 0 (ANNIHILATION, not penalty)

This is the "structural impossibility" principle from Article 8:
- We don't ask AI to be honest
- We make dishonesty structurally impossible through G_total

Gate Components:
1. g_ERR: E/R/R structure complete (Element + Role + Rule)
2. g_Levels: L1-L3 hierarchy respected (no self-reference loops)
3. g_Order: L5 Law of Order (D1→D6 sequence respected)
"""

from typing import Optional, Tuple
from .types import Node, GateSignals, IntegrityGate, Domain


def check_err_gate(signals: GateSignals) -> Tuple[bool, Optional[str]]:
    """
    Check ERR (Element/Role/Rule) structural completeness.

    The Structural Trinity must be complete:
    - Element: Concrete identifiable object present
    - Role: Functional purpose defined
    - Rule: Logical connection specified

    Returns:
        (gate_passed, diagnostic_code)
    """
    if not signals.e_exists:
        return False, "ERR_E"  # Element missing - "ghost thought"

    if not signals.r_exists:
        return False, "ERR_R"  # Role missing - "purposeless element"

    if not signals.rule_exists:
        return False, "ERR_RULE"  # Rule missing - "blind connection"

    return True, None


def check_levels_gate(signals: GateSignals) -> Tuple[bool, Optional[str]]:
    """
    Check L1-L3 hierarchy is respected.

    The Hierarchy Principle: Operations at level N apply only to
    entities at level N-1. Self-application is structurally incoherent.

    This blocks all self-referential paradoxes.

    Returns:
        (gate_passed, diagnostic_code)
    """
    if not signals.l1_l3_ok:
        return False, "LEVELS_LOOP"  # Hierarchical loop detected

    return True, None


def check_order_gate(signals: GateSignals, current_domain: int,
                      parent_domain: Optional[int] = None) -> Tuple[bool, Optional[str]]:
    """
    Check L5 Law of Order is respected.

    Reasoning must traverse D1→D6 in sequence. "Logical jumps"
    (e.g., claiming D5:Inference without passing D2:Clarification)
    are structural violations.

    Args:
        signals: Gate signals including l5_ok flag
        current_domain: Domain index (1-6) of this node
        parent_domain: Domain index of parent node (for sequence check)

    Returns:
        (gate_passed, diagnostic_code)
    """
    # Basic L5 signal check
    if not signals.l5_ok:
        return False, f"ORDER_D{current_domain}"

    # Domain sequence check: current >= parent (no backward jumps)
    if parent_domain is not None:
        if current_domain < parent_domain:
            return False, f"ORDER_BACKWARD_D{parent_domain}_to_D{current_domain}"

    return True, None


def compute_gate(node: Node, parent_domain: Optional[int] = None) -> IntegrityGate:
    """
    Compute the full Integrity Gate for a node.

    G(e) = ⟨g_ERR, g_Levels, g_Order⟩
    G_total = g_ERR ∧ g_Levels ∧ g_Order

    Args:
        node: The reasoning node to check
        parent_domain: Domain of parent node (for sequence validation)

    Returns:
        IntegrityGate with all three components set
    """
    signals = node.gate_signals
    current_domain = node.raw_scores.current_domain

    # Check each gate
    err_ok, err_code = check_err_gate(signals)
    levels_ok, levels_code = check_levels_gate(signals)
    order_ok, order_code = check_order_gate(signals, current_domain, parent_domain)

    return IntegrityGate(
        err_complete=err_ok,
        levels_valid=levels_ok,
        order_valid=order_ok
    )


def get_failed_gate(gate: IntegrityGate) -> Optional[int]:
    """
    Identify which gate failed (for diagnostic purposes).

    Returns:
        1 if ERR failed, 2 if Levels failed, 3 if Order failed, None if all passed
    """
    if not gate.err_complete:
        return 1
    if not gate.levels_valid:
        return 2
    if not gate.order_valid:
        return 3
    return None


def get_diagnostic_code(node: Node, parent_domain: Optional[int] = None) -> Optional[str]:
    """
    Get detailed diagnostic code for a node's gate failure.

    Returns codes like:
    - ERR_E: Element missing
    - ERR_R: Role missing
    - ERR_RULE: Rule missing
    - LEVELS_LOOP: Hierarchical loop
    - ORDER_D5: Order violation at Domain 5
    """
    signals = node.gate_signals
    current_domain = node.raw_scores.current_domain

    # Check ERR first
    err_ok, err_code = check_err_gate(signals)
    if not err_ok:
        return err_code

    # Then Levels
    levels_ok, levels_code = check_levels_gate(signals)
    if not levels_ok:
        return levels_code

    # Then Order
    order_ok, order_code = check_order_gate(signals, current_domain, parent_domain)
    if not order_ok:
        return order_code

    return None  # All gates passed


def get_diagnostic_reason(code: Optional[str]) -> str:
    """
    Convert diagnostic code to human-readable explanation.
    """
    if code is None:
        return "All structural checks passed"

    reasons = {
        # ERR failures
        "ERR_E": "Element missing: No identifiable object in reasoning step",
        "ERR_R": "Role missing: Element has no defined functional purpose",
        "ERR_RULE": "Rule missing: No logical connection between roles",

        # Levels failures
        "LEVELS_LOOP": "Hierarchical loop: Self-referential structure detected (L1-L3 violation)",
    }

    if code in reasons:
        return reasons[code]

    if code.startswith("ORDER_D"):
        domain_num = code.split("D")[-1]
        return f"Order violation at Domain {domain_num}: Sequence D1→D6 not respected"

    if code.startswith("ORDER_BACKWARD"):
        return f"Backward domain jump: Reasoning moved backwards in D1→D6 sequence"

    if code.startswith("ORDER_SKIP"):
        return f"Domain skip: Reasoning jumped over required domains"

    return f"Unknown violation: {code}"


# ============================================================
# ZERO-GATE LAW: The fundamental property
# ============================================================

def apply_zero_gate(gate: IntegrityGate, base_weight: int) -> int:
    """
    Apply the Zero-Gate Law: If G_total = 0, then W = 0

    This is the "Law of Zero" from the specification:
    - If ANY structural check fails, weight is ANNIHILATED (not reduced)
    - This makes hallucinations structurally impossible to propagate

    Args:
        gate: The computed IntegrityGate
        base_weight: S_struct + S_domain

    Returns:
        Final weight: base_weight if gate valid, 0 otherwise
    """
    if gate.is_valid:
        return base_weight
    else:
        return 0  # ANNIHILATION - the Zero-Gate fires


# ============================================================
# Verified Property (from Coq)
# ============================================================

def zero_gate_zero_weight(gate: IntegrityGate, weight: int) -> bool:
    """
    Verified property: G = 0 ⇒ W = 0

    This is a runtime check of the Coq-proven theorem.
    In production, this is guaranteed by construction.
    """
    if not gate.is_valid:
        return weight == 0
    return True  # If gate is valid, any weight is allowed
