"""
Regulus AI - Audit Types
=========================

Data types for the v2 audit pipeline. All dataclasses, no logic.
"""

import json
from dataclasses import dataclass, field
from typing import Optional

from regulus.core.types import IntegrityGate


@dataclass
class TraceSegment:
    """A segment of reasoning trace mapped to a domain."""
    domain: str  # "D1" .. "D6"
    content: str = ""
    summary: str = ""


@dataclass
class ParsedTrace:
    """Parsed reasoning trace with domain-mapped segments."""
    segments: list[TraceSegment] = field(default_factory=list)
    parse_quality: float = 0.0  # 0.0-1.0, how well the trace mapped to domains

    @property
    def domains_present(self) -> list[str]:
        return [s.domain for s in self.segments]

    @property
    def domains_missing(self) -> list[str]:
        all_domains = ["D1", "D2", "D3", "D4", "D5", "D6"]
        return [d for d in all_domains if d not in self.domains_present]


@dataclass
class DomainAuditResult:
    """Audit result for a single domain."""
    domain: str  # "D1" .. "D6"
    present: bool = False
    e_exists: bool = False
    r_exists: bool = False
    rule_exists: bool = False
    s_exists: bool = False
    deps_declared: bool = False
    l1_l3_ok: bool = True
    l5_ok: bool = True
    issues: list[str] = field(default_factory=list)
    weight: int = 0
    segment_summary: str = ""
    # Domain-specific fields (v1.0a)
    d1_depth: Optional[int] = None       # 1-4: Data/Info/Qualities/Characteristics
    d2_depth: Optional[int] = None       # 1-4: Nominal/Operational/Structural/Essential
    d3_objectivity_pass: Optional[bool] = None  # Framework permits any result?
    d4_aristotle_ok: Optional[bool] = None      # Aristotle's 3 rules respected?
    d5_certainty_type: Optional[str] = None     # necessary/probabilistic/evaluative/unmarked
    d6_genuine: Optional[bool] = None           # Reflection adds beyond D5?

    @property
    def gate(self) -> IntegrityGate:
        # D3 objectivity failure is a Zero-Gate: if objectivity fails, ERR is incomplete
        err = self.e_exists and self.r_exists and self.rule_exists and self.s_exists
        if self.d3_objectivity_pass is False:
            err = False
        return IntegrityGate(
            err_complete=err,
            deps_valid=self.deps_declared,
            levels_valid=self.l1_l3_ok,
            order_valid=self.l5_ok,
        )

    @property
    def gate_passed(self) -> bool:
        return self.gate.is_valid


@dataclass
class AuditResult:
    """Complete audit result across all domains."""
    domains: list[DomainAuditResult] = field(default_factory=list)
    overall_issues: list[str] = field(default_factory=list)
    violation_patterns: list[str] = field(default_factory=list)
    parse_quality: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_weight(self) -> int:
        return sum(d.weight for d in self.domains)

    @property
    def max_possible_weight(self) -> int:
        return len(self.domains) * 100

    @property
    def domains_present(self) -> list[str]:
        return [d.domain for d in self.domains if d.present]

    @property
    def domains_missing(self) -> list[str]:
        present = set(self.domains_present)
        return [f"D{i}" for i in range(1, 7) if f"D{i}" not in present]

    @property
    def failed_gates(self) -> list[str]:
        return [d.domain for d in self.domains if d.present and not d.gate_passed]

    @property
    def all_gates_passed(self) -> bool:
        return len(self.failed_gates) == 0

    def to_dict(self) -> dict:
        return {
            "domains": [
                {
                    "domain": d.domain,
                    "present": d.present,
                    "e_exists": d.e_exists,
                    "r_exists": d.r_exists,
                    "rule_exists": d.rule_exists,
                    "s_exists": d.s_exists,
                    "deps_declared": d.deps_declared,
                    "l1_l3_ok": d.l1_l3_ok,
                    "l5_ok": d.l5_ok,
                    "issues": d.issues,
                    "weight": d.weight,
                    "gate_passed": d.gate_passed,
                    "segment_summary": d.segment_summary,
                    # v1.0a domain-specific signals
                    "d1_depth": d.d1_depth,
                    "d2_depth": d.d2_depth,
                    "d3_objectivity_pass": d.d3_objectivity_pass,
                    "d4_aristotle_ok": d.d4_aristotle_ok,
                    "d5_certainty_type": d.d5_certainty_type,
                    "d6_genuine": d.d6_genuine,
                }
                for d in self.domains
            ],
            "violation_patterns": getattr(self, 'violation_patterns', []),
            "overall_issues": self.overall_issues,
            "parse_quality": self.parse_quality,
            "total_weight": self.total_weight,
            "domains_present": self.domains_present,
            "domains_missing": self.domains_missing,
            "failed_gates": self.failed_gates,
            "all_gates_passed": self.all_gates_passed,
        }


    # Critical violation patterns that cause automatic failure
CRITICAL_VIOLATIONS = {
    "ORDER_INVERSION",
    "RATIONALIZATION",
    "CONCLUSION_BEFORE_EVIDENCE",
}


@dataclass
class AuditConfig:
    """Configuration for audit thresholds."""
    min_domains: int = 4
    weight_threshold: int = 60
    err_required: bool = True
    max_corrections: int = 2
    analyst_model: str = "gpt-4o-mini"
    analyst_provider: str = "openai"

    def is_passing(self, result: AuditResult) -> bool:
        """Check if an audit result meets all configured thresholds."""
        if len(result.domains_present) < self.min_domains:
            return False
        if result.total_weight < self.weight_threshold:
            return False
        if self.err_required and not result.all_gates_passed:
            return False
        # Critical violation patterns cause automatic failure
        if result.violation_patterns:
            if set(result.violation_patterns) & CRITICAL_VIOLATIONS:
                return False
        return True


@dataclass
class CorrectionFeedback:
    """Targeted correction prompt for the reasoning model."""
    prompt: str = ""
    failed_domains: list[str] = field(default_factory=list)
    failed_gates: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    round_number: int = 0


@dataclass
class V2Response:
    """Final response from the v2 audit pipeline."""
    query: str = ""
    answer: str = ""
    valid: bool = False
    thinking: str = ""
    trace_format: str = "none"
    reasoning_model: str = ""
    audit_rounds: int = 0
    corrections: list[CorrectionFeedback] = field(default_factory=list)
    final_audit: Optional[AuditResult] = None
    all_audits: list[AuditResult] = field(default_factory=list)
    time_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def reasoning_json(self) -> str:
        """Serialize audit trail for LabDB compatibility."""
        data = {
            "version": "2.0",
            "reasoning_model": self.reasoning_model,
            "trace_format": self.trace_format,
            "audit_rounds": self.audit_rounds,
            "corrections": len(self.corrections),
            "final_audit": self.final_audit.to_dict() if self.final_audit else None,
            "audits": [a.to_dict() for a in self.all_audits],
        }
        return json.dumps(data, ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "answer": self.answer,
            "valid": self.valid,
            "reasoning_model": self.reasoning_model,
            "trace_format": self.trace_format,
            "audit_rounds": self.audit_rounds,
            "corrections": len(self.corrections),
            "final_audit": self.final_audit.to_dict() if self.final_audit else None,
            "time_seconds": self.time_seconds,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }
