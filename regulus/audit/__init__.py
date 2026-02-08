"""
Regulus AI - Audit Pipeline (v2)
=================================

Audits reasoning traces from dedicated reasoning models instead of
generating reasoning from scratch. Uses a single LLM call to parse,
map to domains, and check structural gates.
"""

from .types import (
    TraceSegment,
    ParsedTrace,
    DomainAuditResult,
    AuditResult,
    AuditConfig,
    CorrectionFeedback,
    V2Response,
)

__all__ = [
    "TraceSegment",
    "ParsedTrace",
    "DomainAuditResult",
    "AuditResult",
    "AuditConfig",
    "CorrectionFeedback",
    "V2Response",
]
