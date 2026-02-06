"""
Regulus AI
==========

Deterministic reasoning verification for Large Language Models.

Based on Article 8: "The Structural Guardrail" from the Theory of Systems.

Usage:
    from regulus import LogicGuardEngine, verify_reasoning

    engine = LogicGuardEngine()
    result = engine.verify(json_tree)
    print(result.summary())
"""

__version__ = "1.0a"
__author__ = "Horsocrates"

from .core import (
    # Types
    Domain, Status, Policy,
    GateSignals, RawScores, IntegrityGate,
    Node, Diagnostic, VerificationResult,
    # Engine
    LogicGuardEngine, verify_reasoning, verify_json, quick_check,
    # Core functions
    compute_gate, compute_final_weight,
    assign_all_statuses, create_diagnostic,
    run_all_verifications,
    # Optimizer (legacy)
    TrisectionOptimizer, TrisectionState, TrisectChoice,
    # Socratic Trisection (v2)
    SocraticTrisection, SocraticTrisectionState, TrisectionResult,
)

from .orchestrator import (
    Orchestrator, VerifiedResponse, CorrectionAttempt,
    SocraticOrchestrator, SocraticResponse,
)

from .core.domains import (
    DOMAIN_ORDER, DomainPassRecord, ProbeRecord,
)

__all__ = [
    '__version__', '__author__',
    # Engine
    'LogicGuardEngine', 'verify_reasoning', 'verify_json', 'quick_check',
    # Orchestrator (legacy)
    'Orchestrator', 'VerifiedResponse', 'CorrectionAttempt',
    # Socratic Orchestrator (v2)
    'SocraticOrchestrator', 'SocraticResponse',
    'DOMAIN_ORDER', 'DomainPassRecord', 'ProbeRecord',
    # Types
    'Domain', 'Status', 'Policy',
    'GateSignals', 'RawScores', 'IntegrityGate',
    'Node', 'Diagnostic', 'VerificationResult',
    # Core functions
    'compute_gate', 'compute_final_weight',
    'assign_all_statuses', 'create_diagnostic',
    # Optimizer (legacy)
    'TrisectionOptimizer', 'TrisectionState', 'TrisectChoice',
    # Socratic Trisection (v2)
    'SocraticTrisection', 'SocraticTrisectionState', 'TrisectionResult',
]
