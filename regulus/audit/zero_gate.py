"""
Regulus AI - Audit Zero-Gate
==============================

Adapts the core Zero-Gate mechanism for the audit context.
Wraps core/zero_gate.py functions — reuses, does not duplicate.
"""

from regulus.core.types import GateSignals, IntegrityGate
from regulus.core.zero_gate import check_err_gate, check_deps_gate, check_levels_gate, check_order_gate
from regulus.audit.types import DomainAuditResult, AuditResult, AuditConfig


def compute_audit_gate(domain_result: DomainAuditResult) -> IntegrityGate:
    """
    Compute the integrity gate for a single domain audit result.

    Reuses core zero_gate functions with signals derived from audit output.
    """
    signals = GateSignals(
        e_exists=domain_result.e_exists,
        r_exists=domain_result.r_exists,
        rule_exists=domain_result.rule_exists,
        s_exists=domain_result.s_exists,
        deps_declared=domain_result.deps_declared,
        l1_l3_ok=domain_result.l1_l3_ok,
        l5_ok=domain_result.l5_ok,
    )

    domain_num = int(domain_result.domain[1:])  # "D3" -> 3

    err_ok, _ = check_err_gate(signals)
    deps_ok, _ = check_deps_gate(signals)
    levels_ok, _ = check_levels_gate(signals)
    order_ok, _ = check_order_gate(signals, domain_num)

    return IntegrityGate(
        err_complete=err_ok,
        deps_valid=deps_ok,
        levels_valid=levels_ok,
        order_valid=order_ok,
    )


def compute_audit_total_gate(result: AuditResult, config: AuditConfig) -> bool:
    """
    Compute the total gate for an audit result using configurable thresholds.

    Returns True if the audit passes all configured checks.
    """
    return config.is_passing(result)
