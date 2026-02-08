"""
Regulus AI - Audit Orchestrator (v2)
======================================

Main pipeline: reason → audit → correct loop.

Architecture:
  Query → [Reasoning Model thinks] → Trace → [Analyst LLM audits] → Answer

2 LLM calls minimum (reason + audit), up to 2*max_corrections more if
the audit fails and corrections improve the weight.
"""

import time
from typing import Callable, Optional

from regulus.reasoning.provider import ReasoningProvider, TraceFormat
from regulus.llm.client import LLMClient
from regulus.audit.types import AuditConfig, AuditResult, CorrectionFeedback, V2Response
from regulus.audit.auditor import Auditor
from regulus.audit.d1_validator import D1Validator, D1ValidationResult
from regulus.audit.feedback import FeedbackGenerator


class AuditOrchestrator:
    """
    v2 pipeline orchestrator: reason → audit → correct loop.

    Uses the same callback signatures as SocraticOrchestrator for
    seamless integration with SSE streaming in the lab runner and API.
    """

    def __init__(
        self,
        reasoning_provider: ReasoningProvider,
        audit_llm: LLMClient,
        config: Optional[AuditConfig] = None,
        on_domain_start: Optional[Callable] = None,
        on_domain_complete: Optional[Callable] = None,
        on_correction: Optional[Callable] = None,
    ):
        self.reasoning_provider = reasoning_provider
        self.auditor = Auditor(audit_llm)
        self.d1_validator = D1Validator(audit_llm)
        self.config = config or AuditConfig()
        self.feedback_gen = FeedbackGenerator(self.config)

        self._on_domain_start = on_domain_start
        self._on_domain_complete = on_domain_complete
        self._on_correction = on_correction

    async def process_query(self, query: str) -> V2Response:
        """
        Run the full v2 pipeline: reason → audit → correct loop.

        Returns V2Response with the final answer and full audit trail.
        """
        start_time = time.time()
        total_input_tokens = 0
        total_output_tokens = 0
        all_audits: list[AuditResult] = []
        corrections: list[CorrectionFeedback] = []
        best_weight = -1

        # Phase 1: Initial reasoning
        self._emit_domain_start("REASON", self.reasoning_provider.name)

        reasoning_result = await self.reasoning_provider.reason(query)
        total_input_tokens += reasoning_result.input_tokens
        total_output_tokens += reasoning_result.output_tokens

        self._emit_domain_complete("REASON", {
            "model": reasoning_result.model,
            "trace_format": reasoning_result.trace_format.value,
            "has_trace": reasoning_result.has_trace,
            "time_ms": int(reasoning_result.time_seconds * 1000),
        })

        current_answer = reasoning_result.answer
        current_thinking = reasoning_result.thinking
        current_trace_format = reasoning_result.trace_format

        # Correction loop
        for round_num in range(self.config.max_corrections + 1):
            # Phase 2: Audit
            audit = await self.auditor.audit(
                trace=current_thinking,
                answer=current_answer,
                query=query,
                trace_format=current_trace_format,
            )
            total_input_tokens += audit.input_tokens
            total_output_tokens += audit.output_tokens
            all_audits.append(audit)

            # D1 external validation (first round only, when D1 looks suspicious)
            if round_num == 0:
                d1 = next((d for d in audit.domains if d.domain == "D1"), None)
                if d1 and d1.present and (d1.d1_depth is not None and d1.d1_depth < 3 or d1.weight < 60):
                    self._emit_domain_start("D1_VAL", "D1 External Validation")
                    d1_val = await self.d1_validator.validate(
                        query=query,
                        d1_segment=d1.segment_summary,
                        answer=current_answer,
                    )
                    total_input_tokens += d1_val.input_tokens
                    total_output_tokens += d1_val.output_tokens

                    # Apply D1 validator findings
                    if not d1_val.is_faithful:
                        if d1_val.recommended_weight is not None:
                            d1.weight = min(d1.weight, d1_val.recommended_weight)
                        if d1_val.recommended_depth is not None:
                            d1.d1_depth = min(d1.d1_depth or 4, d1_val.recommended_depth)
                        d1.issues.extend(d1_val.issues)
                        if d1_val.is_critical_failure:
                            audit.overall_issues.append(
                                f"D1 CRITICAL: fidelity={d1_val.fidelity:.2f} — {d1_val.explanation}"
                            )

                    self._emit_domain_complete("D1_VAL", {
                        "fidelity": d1_val.fidelity,
                        "faithful": d1_val.is_faithful,
                        "issues": len(d1_val.issues),
                        "time_ms": 0,
                    })

            # Emit per-domain SSE events
            for d in audit.domains:
                domain_name = {
                    "D1": "Recognition", "D2": "Clarification", "D3": "Framework Selection",
                    "D4": "Comparison", "D5": "Inference", "D6": "Reflection",
                }.get(d.domain, d.domain)

                self._emit_domain_start(d.domain, domain_name)
                self._emit_domain_complete(d.domain, {
                    "weight": d.weight,
                    "gate": 1 if d.gate_passed else 0,
                    "present": d.present,
                    "content_summary": d.segment_summary[:200],
                    "time_ms": 0,
                })

            # Check if audit passes
            if self.config.is_passing(audit):
                break

            # Check if weight improved (early abort if not)
            current_weight = audit.total_weight
            if current_weight <= best_weight and round_num > 0:
                # Correction didn't improve — abort
                self._emit_correction(
                    "AUDIT", round_num,
                    "NO_IMPROVEMENT",
                    f"Weight {current_weight} <= previous best {best_weight}, aborting corrections",
                )
                break

            best_weight = max(best_weight, current_weight)

            # Generate correction feedback (if we have remaining rounds)
            if round_num >= self.config.max_corrections:
                break

            feedback = self.feedback_gen.generate(audit, query, round_num + 1)
            if feedback is None:
                break  # Audit actually passes

            corrections.append(feedback)

            self._emit_correction(
                "AUDIT", round_num + 1,
                ", ".join(audit.failed_gates) or "COVERAGE",
                f"Missing: {', '.join(audit.domains_missing)}; Issues: {len(feedback.issues)}",
            )

            # Re-reason with correction feedback
            self._emit_domain_start("REASON", f"{self.reasoning_provider.name} (correction {round_num + 1})")

            corrected = await self.reasoning_provider.reason(
                feedback.prompt,
                system="You are re-reasoning about a question. Address all structural issues listed.",
            )
            total_input_tokens += corrected.input_tokens
            total_output_tokens += corrected.output_tokens

            self._emit_domain_complete("REASON", {
                "model": corrected.model,
                "correction_round": round_num + 1,
                "time_ms": int(corrected.time_seconds * 1000),
            })

            current_answer = corrected.answer
            current_thinking = corrected.thinking
            current_trace_format = corrected.trace_format

            # Clear audit cache since trace changed
            self.auditor.clear_cache()

        elapsed = time.time() - start_time
        final_audit = all_audits[-1] if all_audits else None

        return V2Response(
            query=query,
            answer=current_answer,
            valid=self.config.is_passing(final_audit) if final_audit else False,
            thinking=current_thinking,
            trace_format=current_trace_format.value if isinstance(current_trace_format, TraceFormat) else str(current_trace_format),
            reasoning_model=reasoning_result.model,
            audit_rounds=len(all_audits),
            corrections=corrections,
            final_audit=final_audit,
            all_audits=all_audits,
            time_seconds=elapsed,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
        )

    # Callback helpers (same signatures as SocraticOrchestrator)

    def _emit_domain_start(self, domain: str, domain_name: str):
        if self._on_domain_start:
            self._on_domain_start(domain, domain_name)

    def _emit_domain_complete(self, domain: str, result_dict: dict):
        if self._on_domain_complete:
            self._on_domain_complete(domain, result_dict)

    def _emit_correction(self, domain: str, attempt: int, violation: str, fix_summary: str):
        if self._on_correction:
            self._on_correction(domain, attempt, violation, fix_summary)
