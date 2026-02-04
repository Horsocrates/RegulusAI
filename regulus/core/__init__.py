"""
Regulus AI - Core Module
========================

Re-exports all core types and functions for convenient access.

Usage:
    from regulus.core import LogicGuardEngine, verify_reasoning, Node, Status
"""

from .types import (
    Domain, Status, Policy,
    GateSignals, RawScores, IntegrityGate,
    Node, Diagnostic, VerificationResult,
)

from .zero_gate import (
    check_err_gate, check_levels_gate, check_order_gate,
    compute_gate, get_failed_gate,
    get_diagnostic_code, get_diagnostic_reason,
    apply_zero_gate, zero_gate_zero_weight,
)

from .weight import (
    compute_struct_score, compute_domain_score,
    compute_base_weight, compute_final_weight,
    compare_weights, is_refinement, is_strict_improvement,
    weight_breakdown,
)

from .status_machine import (
    compare_entities, find_max_entity, find_secondary_max,
    find_historical_max, build_entity_history,
    assign_status, assign_all_statuses,
    verify_uniqueness, verify_stability, verify_zero_gate_law,
    run_all_verifications, create_diagnostic,
)

from .engine import (
    LogicGuardEngine,
    verify_reasoning, verify_json, quick_check,
)

from .optimizer import (
    TrisectionOptimizer, TrisectionState, TrisectChoice,
)

__all__ = [
    # Types
    'Domain', 'Status', 'Policy',
    'GateSignals', 'RawScores', 'IntegrityGate',
    'Node', 'Diagnostic', 'VerificationResult',
    # Engine
    'LogicGuardEngine', 'verify_reasoning', 'verify_json', 'quick_check',
    # Zero-Gate
    'compute_gate', 'get_failed_gate',
    'get_diagnostic_code', 'get_diagnostic_reason',
    'apply_zero_gate', 'zero_gate_zero_weight',
    # Weight
    'compute_struct_score', 'compute_domain_score',
    'compute_base_weight', 'compute_final_weight',
    'compare_weights', 'weight_breakdown',
    # Status Machine
    'compare_entities', 'find_max_entity',
    'assign_status', 'assign_all_statuses',
    'run_all_verifications', 'create_diagnostic',
    # Optimizer
    'TrisectionOptimizer', 'TrisectionState', 'TrisectChoice',
]
