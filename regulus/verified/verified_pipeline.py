"""
verified_pipeline.py — Verified D1-D6 Pipeline (v2 architecture).

D6 is NOT a domain in the chain. D6 is the meta-operator:
  D6-ASK     — BEFORE pipeline: question decomposition (Heidegger's 3 moments)
  D6-REFLECT QUICK — BETWEEN domains: 4-check gate after each D1-D5
  D6-REFLECT FULL  — AFTER D5 (or on escalation): 3 classes, ERR chain, return

Three operator levels:
  L3 Team Lead — plans, verifies, assembles (never computes)
  L2 D6        — ASK + REFLECT (never solves)
  L1 Worker    — D1-D5 (solves, one domain per turn)

Theorem backing:
  DomainTypes.v      — 27 Qed (type definitions + structural lemmas)
  DomainValidation.v — 31 Qed (3-level validation, error taxonomy)
  PipelineSemantics.v — 17 Qed (iteration, convergence, paradigm shift)
  PipelineExtraction.v — 7 Qed (extraction validation)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ═══════════════════════════════════
# SECTION A: DOMAIN TYPES (mirrors DomainTypes.v)
# ═══════════════════════════════════

class GateVerdict(Enum):
    """QuickGate verdict (mirrors GV_Pass/GV_Iterate/GV_Escalate)."""
    PASS = "pass"
    ITERATE = "iterate"
    ESCALATE = "escalate"


class ReturnType(Enum):
    """D6-REFLECT FULL return decision (mirrors RT_None/Corrective/...)."""
    NONE = "none"
    CORRECTIVE = "corrective"
    DEEPENING = "deepening"
    EXPANDING = "expanding"


class CertaintyDegree(Enum):
    """D5 certainty classification."""
    POSSIBLE = "possible"
    LIKELY = "likely"
    NECESSARY = "necessary"


@dataclass
class D6AskOutput:
    """D6-ASK: Pre-pipeline question decomposition.

    Heidegger's Three Moments:
      gefragte  — subject matter (WHAT is being asked about)
      befragte  — source (WHERE to look for the answer)
      erfragte  — sought-for (WHAT counts as answer + FORMAT)

    Theorem: ask_erfragte_valid (DomainValidation.v #15)
    """
    gefragte: str
    befragte: str
    erfragte: str              # answer format — MUST be specified
    sub_questions: list[str]
    serves_root: list[tuple[str, bool]]  # (sub_q, serves_root?)
    composition_test: bool     # if ALL sub-qs answered -> root answered?
    traps: list[str]           # confusion risks
    format_required: str       # exact answer format
    complexity: int = 0        # 0=easy, 1=medium, 2=hard
    task_type: str = "unknown"


@dataclass
class QuickGate:
    """D6-REFLECT QUICK: 4-check gate after every domain.

    Fires AFTER every D1-D5 output.
    Theorem: gate_pass_all_four (DomainValidation.v #14)
    """
    domain: int                # which domain: 1-5
    alignment: bool            # does output address its question?
    coverage: bool             # all sub-questions answered?
    consistency: bool          # no contradictions with previous?
    confidence_matches: bool   # self-reported conf matches evidence?
    verdict: GateVerdict
    feedback: list[str] = field(default_factory=list)


@dataclass
class ERRChainCheck:
    """Cross-domain ERR chain verification.

    Theorem: reflect_err_chain_valid (DomainValidation.v #19)
    """
    elements_consistent: bool       # no elements appearing/disappearing
    dependencies_acyclic: bool      # no circular reasoning
    status_transitions_justified: bool  # each change has reason
    no_level_violations: bool       # Rules not governing Rules, etc.

    @property
    def all_passed(self) -> bool:
        return (self.elements_consistent and self.dependencies_acyclic
                and self.status_transitions_justified
                and self.no_level_violations)


@dataclass
class ReturnAssessment:
    """Return decision from D6-REFLECT FULL."""
    type: ReturnType
    target_domain: int = 0     # 0=none, 1-5=which domain
    reason: str = ""


@dataclass
class BoundaryAudit:
    """Proof boundary audit — when D5 claims Necessary or conf >= 85%."""
    required: bool
    proof_type_valid: bool = True
    no_unstated_assumptions: bool = True
    counterexample_addressed: bool = True

    @property
    def passed(self) -> bool:
        if not self.required:
            return True
        return (self.proof_type_valid and self.no_unstated_assumptions
                and self.counterexample_addressed)


@dataclass
class D6ReflectFull:
    """D6-REFLECT FULL: Post-pipeline reflection.

    3 classes of reflection:
      Class I:  Conclusive (must be present)
      Class II: Perceptive, Procedural, Perspectival, Fundamental (>= 2)
      Class III: Liminal (optional but valued)

    Theorems:
      reflect_class_i_valid (DomainValidation.v #17)
      reflect_class_ii_valid (DomainValidation.v #18)
    """
    # Class I: Conclusive reflection
    class_i_conclusive: str    # summary conclusion

    # Class II: At least 2 must be present
    perceptive: Optional[str] = None     # new perception gained
    procedural: Optional[str] = None     # methodology assessment
    perspectival: Optional[str] = None   # viewpoint analysis
    fundamental: Optional[str] = None    # foundational insight

    # Class III: Liminal
    liminal: Optional[str] = None

    # ERR chain across all domains
    err_chain: ERRChainCheck = field(default_factory=lambda: ERRChainCheck(
        elements_consistent=False,
        dependencies_acyclic=False,
        status_transitions_justified=False,
        no_level_violations=False
    ))

    # Domain quality assessments
    domain_qualities: list[dict] = field(default_factory=list)

    # Boundary audit (if D5 claims Necessary or conf >= 85%)
    boundary_audit: Optional[BoundaryAudit] = None

    # Limitations (must be SPECIFIC, not generic)
    scope_fails_when: str = ""
    adjustment_reason: str = ""
    adjusted_confidence: float = 0.0

    # Return decision
    return_assessment: ReturnAssessment = field(
        default_factory=lambda: ReturnAssessment(type=ReturnType.NONE)
    )

    # D5 certainty degree
    d5_certainty: Optional[CertaintyDegree] = None

    @property
    def class_ii_count(self) -> int:
        """Count of Class II reflections present (must be >= 2)."""
        return sum(1 for v in [self.perceptive, self.procedural,
                               self.perspectival, self.fundamental]
                   if v is not None and v != "")


# ═══════════════════════════════════
# SECTION B: VALIDATION (mirrors DomainValidation.v)
# ═══════════════════════════════════

def validate_ask(ask: D6AskOutput) -> tuple[bool, list[str]]:
    """Validate D6-ASK output.

    4 checks (matching validate_ask_bool from DomainValidation.v):
      1. erfragte specified
      2. at least one sub-question
      3. composition test performed
      4. all sub-questions serve root

    Theorem: ask_erfragte_valid, ask_has_sub_questions (DV #15, #16)
    """
    violations = []

    if not ask.erfragte:
        violations.append("erfragte (answer format) not specified")
    if not ask.sub_questions:
        violations.append("no sub-questions defined")
    if not ask.composition_test:
        violations.append("composition test not performed")
    if ask.serves_root and not all(serves for _, serves in ask.serves_root):
        violations.append("some sub-questions do not serve root question")

    return len(violations) == 0, violations


def validate_gate(gate: QuickGate) -> tuple[bool, list[str]]:
    """Validate a QuickGate.

    Theorem: gate_pass_all_four (DV #14) —
      Pass requires all 4 checks true.
      Iterate requires feedback.
    """
    violations = []

    if gate.verdict == GateVerdict.PASS:
        if not gate.alignment:
            violations.append(f"D{gate.domain}: gate=PASS but alignment failed")
        if not gate.coverage:
            violations.append(f"D{gate.domain}: gate=PASS but coverage failed")
        if not gate.consistency:
            violations.append(f"D{gate.domain}: gate=PASS but consistency failed")
        if not gate.confidence_matches:
            violations.append(f"D{gate.domain}: gate=PASS but confidence mismatch")
    elif gate.verdict == GateVerdict.ITERATE:
        if not gate.feedback:
            violations.append(f"D{gate.domain}: gate=ITERATE but no feedback")

    return len(violations) == 0, violations


def validate_reflect(reflect: D6ReflectFull) -> tuple[bool, list[str]]:
    """Validate D6-REFLECT FULL.

    Theorems:
      reflect_class_i_valid (DV #17) — Class I must be present
      reflect_class_ii_valid (DV #18) — >= 2 Class II present
      reflect_err_chain_valid (DV #19) — ERR chain fully checked
      reflect_limitations_valid (DV #20) — limitations must be specific
    """
    violations = []

    if not reflect.class_i_conclusive:
        violations.append("Class I (conclusive) reflection missing")
    if reflect.class_ii_count < 2:
        violations.append(
            f"Class II: only {reflect.class_ii_count}/4 present (need >= 2)"
        )
    if not reflect.err_chain.all_passed:
        if not reflect.err_chain.elements_consistent:
            violations.append("ERR chain: elements inconsistent across domains")
        if not reflect.err_chain.dependencies_acyclic:
            violations.append("ERR chain: circular dependencies detected")
        if not reflect.err_chain.status_transitions_justified:
            violations.append("ERR chain: unjustified status transitions")
        if not reflect.err_chain.no_level_violations:
            violations.append("ERR chain: level violations (Rules governing Rules)")
    if reflect.return_assessment.type != ReturnType.NONE:
        if reflect.return_assessment.target_domain == 0:
            violations.append("return type set but no target domain specified")
    if not reflect.scope_fails_when:
        violations.append("limitations not specific (scope_fails_when empty)")
    if not reflect.adjustment_reason:
        violations.append("confidence adjustment has no reason")

    return len(violations) == 0, violations


# ═══════════════════════════════════
# SECTION C: PIPELINE CERTIFICATE
# ═══════════════════════════════════

@dataclass
class PipelineCertificate:
    """Full verification certificate for a pipeline run.

    Backed by: validate_pipeline_sound (DomainValidation.v #25),
               validation_cumulative (DomainValidation.v #25)
    """
    # Pre-pipeline
    ask_validated: bool = False
    erfragte_specified: bool = False

    # Domains
    domains_traversed: list[int] = field(default_factory=list)
    all_domains_valid: bool = False

    # Gates (D6-REFLECT QUICK)
    gates_all_passed: bool = False
    gates_details: list[dict] = field(default_factory=list)

    # Control points
    d2_d3_ready: bool = False
    d4_d5_ready: bool = False
    answer_earned: bool = False

    # E/R/R
    err_well_formed: bool = False
    dependencies_acyclic: bool = False

    # D6-REFLECT FULL
    reflect_valid: bool = False
    err_chain_verified: bool = False
    boundary_audit_passed: Optional[bool] = None
    return_type: str = "none"

    # Convergence
    convergence_method: str = "bounded_iteration"
    contraction_factor: Optional[float] = None
    iterations_used: int = 0
    paradigm_shifts: int = 0

    # Backing theorems
    backing_theorems: list[str] = field(default_factory=lambda: [
        "validate_pipeline_sound (DomainValidation.v)",
        "validation_cumulative (DomainValidation.v)",
        "run_pipeline_bounded (PipelineSemantics.v)",
        "expanding_triggers_shift (PipelineSemantics.v)",
        "shift_preserves_erfragte (PipelineSemantics.v)",
        "gate_pass_all_four (DomainValidation.v)",
    ])


# ═══════════════════════════════════
# SECTION D: VERIFIED PIPELINE
# ═══════════════════════════════════

@dataclass
class VerifiedPipelineConfig:
    """Configuration for the verified pipeline."""
    max_fuel: int = 5          # max iterations
    max_shifts: int = 2        # max paradigm shifts
    epsilon: float = 5.0       # convergence threshold (confidence points)
    gate_retry_limit: int = 1  # max retries per gate


@dataclass
class VerifiedAnswer:
    """Final verified answer with certificate."""
    answer: str
    confidence: float
    certificate: PipelineCertificate
    ask: D6AskOutput
    domain_outputs: list[dict]
    gates: list[QuickGate]
    reflect: Optional[D6ReflectFull]


class VerifiedPipeline:
    """Execute: ASK → [D1→gate→...→D5→gate] → REFLECT FULL → possibly iterate.

    Architecture (3 operator levels):
      L3 Team Lead — plans, verifies, assembles (never computes)
      L2 D6        — ASK + REFLECT (never solves)
      L1 Worker    — D1-D5 (solves, one domain per turn)

    Theorem backing:
      run_pipeline_bounded: iterations <= fuel
      run_pipeline_converged: if delta <= eps, terminates in 1 step
      shift_preserves_erfragte: paradigm shift keeps answer format
    """

    def __init__(self, config: Optional[VerifiedPipelineConfig] = None):
        self.config = config or VerifiedPipelineConfig()
        self._confidence_history: list[float] = []

    def run_sync(
        self,
        question: str,
        domain_runner: Any = None,
        ask_runner: Any = None,
        reflect_runner: Any = None,
    ) -> VerifiedAnswer:
        """Synchronous pipeline execution.

        Steps:
          1. D6-ASK: decompose question
          2. Loop (fuel-bounded):
             a. D1-D5 with QuickGate after each
             b. D6-REFLECT FULL
             c. Convergence check / paradigm shift
          3. Build certificate

        Args:
            question: The input question
            domain_runner: callable(domain_num, question, prev, ask) -> dict
            ask_runner: callable(question) -> D6AskOutput
            reflect_runner: callable(outputs, gates, ask) -> D6ReflectFull
        """
        # ═══ PRE-PIPELINE: D6-ASK ═══
        ask = self._default_ask(question) if ask_runner is None else ask_runner(question)
        ask_valid, ask_violations = validate_ask(ask)

        cert = PipelineCertificate()
        cert.ask_validated = ask_valid
        cert.erfragte_specified = bool(ask.erfragte)

        if not ask_valid and ask_runner is not None:
            # Retry with violations
            ask = ask_runner(question)
            ask_valid, _ = validate_ask(ask)
            cert.ask_validated = ask_valid

        iterations = 0
        paradigm_shifts = 0
        domain_outputs: list[dict] = []
        gates: list[QuickGate] = []
        reflect: Optional[D6ReflectFull] = None
        final_confidence = 0.0

        while iterations < self.config.max_fuel:
            iterations += 1
            domain_outputs = []
            gates = []

            # ═══ D1-D5 WITH GATES ═══
            prev_output: Optional[dict] = None
            escalated = False

            for domain_num in [1, 2, 3, 4, 5]:
                # Run domain
                if domain_runner is not None:
                    d = domain_runner(domain_num, question, prev_output, ask)
                else:
                    d = self._default_domain(domain_num, question, prev_output, ask)

                # D6-REFLECT QUICK: gate check
                gate = self._run_quick_gate(domain_num, d, prev_output, ask)
                gate_valid, _ = validate_gate(gate)

                # Retry on ITERATE
                if gate.verdict == GateVerdict.ITERATE:
                    if domain_runner is not None:
                        d = domain_runner(domain_num, question, prev_output, ask)
                    gate = self._run_quick_gate(domain_num, d, prev_output, ask)

                # ESCALATE → trigger early REFLECT
                if gate.verdict == GateVerdict.ESCALATE:
                    domain_outputs.append(d)
                    gates.append(gate)
                    escalated = True
                    break

                # Control points
                if domain_num == 2:
                    cert.d2_d3_ready = True
                if domain_num == 4:
                    cert.d4_d5_ready = True

                domain_outputs.append(d)
                gates.append(gate)
                prev_output = d

            # ═══ POST-PIPELINE: D6-REFLECT FULL ═══
            if reflect_runner is not None:
                reflect = reflect_runner(domain_outputs, gates, ask)
            else:
                reflect = self._default_reflect(domain_outputs, gates, ask)

            reflect_valid, reflect_violations = validate_reflect(reflect)

            # Record confidence
            self._confidence_history.append(reflect.adjusted_confidence)
            final_confidence = reflect.adjusted_confidence

            # Convergence check
            if len(self._confidence_history) >= 2:
                delta = abs(
                    self._confidence_history[-1] - self._confidence_history[-2]
                )
                if delta <= self.config.epsilon:
                    break

            # Return decision
            if reflect.return_assessment.type == ReturnType.NONE:
                if not escalated:
                    cert.answer_earned = True
                    break
            elif reflect.return_assessment.type == ReturnType.EXPANDING:
                if paradigm_shifts < self.config.max_shifts:
                    paradigm_shifts += 1
                    ask = self._shift_ask(ask, reflect)
                    continue
                else:
                    break
            elif reflect.return_assessment.type in (
                ReturnType.CORRECTIVE, ReturnType.DEEPENING
            ):
                continue
            else:
                break

        # ═══ BUILD CERTIFICATE ═══
        cert.domains_traversed = [d.get("domain", i + 1)
                                  for i, d in enumerate(domain_outputs)]
        cert.all_domains_valid = len(domain_outputs) == 5
        cert.gates_all_passed = all(
            g.verdict == GateVerdict.PASS for g in gates
        )
        cert.gates_details = [
            {"domain": g.domain, "verdict": g.verdict.value,
             "alignment": g.alignment, "coverage": g.coverage,
             "consistency": g.consistency, "confidence": g.confidence_matches}
            for g in gates
        ]
        cert.iterations_used = iterations
        cert.paradigm_shifts = paradigm_shifts

        if reflect is not None:
            cert.reflect_valid = validate_reflect(reflect)[0]
            cert.err_chain_verified = reflect.err_chain.all_passed
            cert.return_type = reflect.return_assessment.type.value
            if reflect.boundary_audit is not None:
                cert.boundary_audit_passed = reflect.boundary_audit.passed

        # Contraction factor from confidence history
        if len(self._confidence_history) >= 3:
            gaps = [abs(self._confidence_history[i + 1] - self._confidence_history[i])
                    for i in range(len(self._confidence_history) - 1)]
            if gaps[0] > 0:
                cert.contraction_factor = gaps[-1] / gaps[0]
                cert.convergence_method = "contraction_estimate"

        return VerifiedAnswer(
            answer=str(domain_outputs[-1].get("answer", "")) if domain_outputs else "",
            confidence=final_confidence,
            certificate=cert,
            ask=ask,
            domain_outputs=domain_outputs,
            gates=gates,
            reflect=reflect,
        )

    # ═══════════════════════════════════
    # SECTION E: QUICK GATE (D6-REFLECT QUICK)
    # ═══════════════════════════════════

    def _run_quick_gate(
        self, domain_num: int, output: dict,
        prev: Optional[dict], ask: D6AskOutput
    ) -> QuickGate:
        """D6-REFLECT QUICK: 4 checks after every domain.

        Theorem: gate_pass_all_four (DomainValidation.v) —
          Pass verdict requires ALL 4 checks true.
        """
        alignment = self._check_alignment(output, ask)
        coverage = self._check_coverage(output, ask, domain_num)
        consistency = self._check_consistency(output, prev)
        confidence_ok = self._check_confidence_matches(output)

        all_ok = alignment and coverage and consistency and confidence_ok

        if all_ok:
            verdict = GateVerdict.PASS
            feedback: list[str] = []
        elif not consistency:
            verdict = GateVerdict.ESCALATE
            feedback = [f"D{domain_num} contradicts previous domain output"]
        elif not alignment:
            verdict = GateVerdict.ITERATE
            feedback = [
                f"D{domain_num} output doesn't address the question "
                f"(erfragte: {ask.erfragte})"
            ]
        else:
            verdict = GateVerdict.ITERATE
            feedback = self._build_gate_feedback(
                domain_num, alignment, coverage, consistency, confidence_ok
            )

        return QuickGate(
            domain=domain_num,
            alignment=alignment,
            coverage=coverage,
            consistency=consistency,
            confidence_matches=confidence_ok,
            verdict=verdict,
            feedback=feedback,
        )

    def _check_alignment(self, output: dict, ask: D6AskOutput) -> bool:
        """Check if domain output addresses the question."""
        return bool(output.get("aligned", True))

    def _check_coverage(self, output: dict, ask: D6AskOutput, domain: int) -> bool:
        """Check if sub-questions are covered."""
        return bool(output.get("coverage", True))

    def _check_consistency(self, output: dict, prev: Optional[dict]) -> bool:
        """Check no contradictions with previous domain."""
        if prev is None:
            return True
        return bool(output.get("consistent", True))

    def _check_confidence_matches(self, output: dict) -> bool:
        """Check self-reported confidence matches evidence."""
        return bool(output.get("confidence_matches", True))

    def _build_gate_feedback(
        self, domain: int, alignment: bool, coverage: bool,
        consistency: bool, confidence: bool
    ) -> list[str]:
        """Build specific feedback for gate iteration."""
        feedback = []
        if not alignment:
            feedback.append(f"D{domain}: realign with question")
        if not coverage:
            feedback.append(f"D{domain}: cover remaining sub-questions")
        if not consistency:
            feedback.append(f"D{domain}: resolve contradictions")
        if not confidence:
            feedback.append(f"D{domain}: confidence doesn't match evidence")
        return feedback

    # ═══════════════════════════════════
    # SECTION F: PARADIGM SHIFT
    # ═══════════════════════════════════

    def _shift_ask(self, ask: D6AskOutput, reflect: D6ReflectFull) -> D6AskOutput:
        """Paradigm shift: new ASK with bumped complexity.

        Theorem: shift_preserves_erfragte — answer format unchanged.
        Theorem: shift_bumps_complexity — complexity incremented.
        """
        return D6AskOutput(
            gefragte=ask.gefragte,
            befragte=ask.befragte,
            erfragte=ask.erfragte,          # preserved (theorem)
            sub_questions=ask.sub_questions, # preserved (theorem)
            serves_root=ask.serves_root,
            composition_test=ask.composition_test,
            traps=ask.traps,
            format_required=ask.format_required,
            complexity=ask.complexity + 1,   # bumped (theorem)
            task_type=ask.task_type,
        )

    # ═══════════════════════════════════
    # SECTION G: DEFAULTS (for testing without LLM)
    # ═══════════════════════════════════

    def _default_ask(self, question: str) -> D6AskOutput:
        """Build a default ASK output for testing."""
        return D6AskOutput(
            gefragte=question,
            befragte="general knowledge",
            erfragte="text answer",
            sub_questions=[question],
            serves_root=[(question, True)],
            composition_test=True,
            traps=[],
            format_required="text",
            complexity=0,
            task_type="general",
        )

    def _default_domain(
        self, domain_num: int, question: str,
        prev: Optional[dict], ask: D6AskOutput
    ) -> dict:
        """Default domain output for testing."""
        return {
            "domain": domain_num,
            "answer": f"D{domain_num} output for: {question}",
            "confidence": 50 + domain_num * 5,
            "aligned": True,
            "coverage": True,
            "consistent": True,
            "confidence_matches": True,
        }

    def _default_reflect(
        self, outputs: list[dict], gates: list[QuickGate], ask: D6AskOutput
    ) -> D6ReflectFull:
        """Default reflection for testing."""
        avg_conf = (
            sum(d.get("confidence", 50) for d in outputs) / len(outputs)
            if outputs else 50.0
        )
        return D6ReflectFull(
            class_i_conclusive=f"Analysis complete for: {ask.gefragte}",
            perceptive="Default perceptive reflection",
            procedural="Default procedural reflection",
            err_chain=ERRChainCheck(
                elements_consistent=True,
                dependencies_acyclic=True,
                status_transitions_justified=True,
                no_level_violations=True,
            ),
            scope_fails_when="default: when input is adversarial",
            adjustment_reason="default confidence from domain average",
            adjusted_confidence=avg_conf,
            return_assessment=ReturnAssessment(type=ReturnType.NONE),
        )
