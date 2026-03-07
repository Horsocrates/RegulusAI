"""
Tests for verified_pipeline.py — Verified D1-D6 Pipeline v2.

Tests validate that Python implementation mirrors Coq-proven properties:
  - ASK validation (ask_erfragte_valid, ask_has_sub_questions)
  - Gate validation (gate_pass_all_four)
  - Reflect validation (reflect_class_i_valid, reflect_class_ii_valid)
  - Pipeline execution (run_pipeline_bounded, run_pipeline_converged)
  - Paradigm shift (shift_preserves_erfragte, shift_bumps_complexity)
  - Error taxonomy (catches_empty_*, catches_no_*)
"""

import pytest

from regulus.verified.verified_pipeline import (
    BoundaryAudit,
    CertaintyDegree,
    D6AskOutput,
    D6ReflectFull,
    ERRChainCheck,
    GateVerdict,
    PipelineCertificate,
    QuickGate,
    ReturnAssessment,
    ReturnType,
    VerifiedAnswer,
    VerifiedPipeline,
    VerifiedPipelineConfig,
    validate_ask,
    validate_gate,
    validate_reflect,
)


# ═══════════════════════════════════
# SECTION A: D6-ASK VALIDATION
# ═══════════════════════════════════

class TestAskValidation:
    """Tests mirroring DomainValidation.v Section G-H (#15-16)."""

    def test_valid_ask(self):
        """Valid ASK passes validation."""
        ask = D6AskOutput(
            gefragte="topic", befragte="source", erfragte="text",
            sub_questions=["q1"], serves_root=[("q1", True)],
            composition_test=True, traps=[], format_required="text",
        )
        valid, violations = validate_ask(ask)
        assert valid
        assert violations == []

    def test_ask_no_erfragte(self):
        """Catches no erfragte — mirrors catches_no_erfragte (DV #31)."""
        ask = D6AskOutput(
            gefragte="topic", befragte="source", erfragte="",
            sub_questions=["q1"], serves_root=[("q1", True)],
            composition_test=True, traps=[], format_required="text",
        )
        valid, violations = validate_ask(ask)
        assert not valid
        assert any("erfragte" in v for v in violations)

    def test_ask_no_sub_questions(self):
        """Catches no sub-questions — mirrors ask_has_sub_questions (DV #16)."""
        ask = D6AskOutput(
            gefragte="topic", befragte="source", erfragte="text",
            sub_questions=[], serves_root=[],
            composition_test=True, traps=[], format_required="text",
        )
        valid, violations = validate_ask(ask)
        assert not valid
        assert any("sub-question" in v for v in violations)

    def test_ask_serves_root_violation(self):
        """Sub-question doesn't serve root."""
        ask = D6AskOutput(
            gefragte="topic", befragte="source", erfragte="text",
            sub_questions=["q1", "q2"],
            serves_root=[("q1", True), ("q2", False)],
            composition_test=True, traps=[], format_required="text",
        )
        valid, violations = validate_ask(ask)
        assert not valid
        assert any("serve root" in v for v in violations)


# ═══════════════════════════════════
# SECTION B: QUICK GATE VALIDATION
# ═══════════════════════════════════

class TestGateValidation:
    """Tests mirroring DomainValidation.v Section H (#14)."""

    def test_gate_pass_all_four(self):
        """Gate PASS requires all 4 checks — mirrors gate_pass_all_four."""
        gate = QuickGate(
            domain=1, alignment=True, coverage=True,
            consistency=True, confidence_matches=True,
            verdict=GateVerdict.PASS,
        )
        valid, violations = validate_gate(gate)
        assert valid

    def test_gate_pass_missing_alignment(self):
        """PASS with alignment=false is invalid."""
        gate = QuickGate(
            domain=1, alignment=False, coverage=True,
            consistency=True, confidence_matches=True,
            verdict=GateVerdict.PASS,
        )
        valid, violations = validate_gate(gate)
        assert not valid
        assert any("alignment" in v for v in violations)

    def test_gate_iterate_needs_feedback(self):
        """ITERATE verdict requires feedback."""
        gate = QuickGate(
            domain=2, alignment=True, coverage=False,
            consistency=True, confidence_matches=True,
            verdict=GateVerdict.ITERATE,
            feedback=[],
        )
        valid, violations = validate_gate(gate)
        assert not valid
        assert any("feedback" in v for v in violations)

    def test_gate_iterate_with_feedback(self):
        """ITERATE with feedback is valid."""
        gate = QuickGate(
            domain=2, alignment=True, coverage=False,
            consistency=True, confidence_matches=True,
            verdict=GateVerdict.ITERATE,
            feedback=["coverage gap"],
        )
        valid, violations = validate_gate(gate)
        assert valid

    def test_gate_escalate_always_valid(self):
        """ESCALATE is always valid (no constraints)."""
        gate = QuickGate(
            domain=3, alignment=False, coverage=False,
            consistency=False, confidence_matches=False,
            verdict=GateVerdict.ESCALATE,
        )
        valid, violations = validate_gate(gate)
        assert valid


# ═══════════════════════════════════
# SECTION C: D6-REFLECT FULL VALIDATION
# ═══════════════════════════════════

class TestReflectValidation:
    """Tests mirroring DomainValidation.v Section H (#17-20)."""

    def _make_valid_reflect(self) -> D6ReflectFull:
        return D6ReflectFull(
            class_i_conclusive="conclusion",
            perceptive="insight",
            procedural="method",
            err_chain=ERRChainCheck(
                elements_consistent=True,
                dependencies_acyclic=True,
                status_transitions_justified=True,
                no_level_violations=True,
            ),
            scope_fails_when="adversarial input",
            adjustment_reason="evidence-based",
            adjusted_confidence=75.0,
        )

    def test_valid_reflect(self):
        """Valid reflect passes."""
        rf = self._make_valid_reflect()
        valid, violations = validate_reflect(rf)
        assert valid

    def test_reflect_no_class_i(self):
        """Catches missing Class I — mirrors reflect_class_i_valid."""
        rf = self._make_valid_reflect()
        rf.class_i_conclusive = ""
        valid, violations = validate_reflect(rf)
        assert not valid
        assert any("Class I" in v for v in violations)

    def test_reflect_insufficient_class_ii(self):
        """Catches < 2 Class II — mirrors reflect_class_ii_valid."""
        rf = self._make_valid_reflect()
        rf.perceptive = None
        rf.procedural = None
        rf.perspectival = None
        rf.fundamental = None
        valid, violations = validate_reflect(rf)
        assert not valid
        assert any("Class II" in v for v in violations)

    def test_reflect_err_chain_failure(self):
        """Catches ERR chain failure — mirrors reflect_err_chain_valid."""
        rf = self._make_valid_reflect()
        rf.err_chain = ERRChainCheck(
            elements_consistent=False,
            dependencies_acyclic=True,
            status_transitions_justified=True,
            no_level_violations=True,
        )
        valid, violations = validate_reflect(rf)
        assert not valid
        assert any("elements inconsistent" in v for v in violations)

    def test_reflect_no_limitations(self):
        """Catches generic limitations — mirrors reflect_limitations_valid."""
        rf = self._make_valid_reflect()
        rf.scope_fails_when = ""
        valid, violations = validate_reflect(rf)
        assert not valid
        assert any("scope_fails_when" in v for v in violations)

    def test_class_ii_count(self):
        """Class II count correctly counts non-empty fields."""
        rf = D6ReflectFull(
            class_i_conclusive="x",
            perceptive="a",
            procedural="b",
            perspectival=None,
            fundamental="d",
        )
        assert rf.class_ii_count == 3

    def test_boundary_audit(self):
        """Boundary audit correctness."""
        ba = BoundaryAudit(required=True, proof_type_valid=True,
                           no_unstated_assumptions=True,
                           counterexample_addressed=False)
        assert not ba.passed

        ba2 = BoundaryAudit(required=False)
        assert ba2.passed


# ═══════════════════════════════════
# SECTION D: PIPELINE EXECUTION
# ═══════════════════════════════════

class TestPipelineExecution:
    """Tests mirroring PipelineSemantics.v Section F-G."""

    def test_pipeline_runs_with_defaults(self):
        """Pipeline runs to completion with default runners."""
        pipeline = VerifiedPipeline()
        result = pipeline.run_sync("What is 2+2?")
        assert isinstance(result, VerifiedAnswer)
        assert result.confidence > 0
        assert result.certificate.ask_validated
        assert len(result.gates) == 5

    def test_pipeline_bounded(self):
        """Iterations <= max_fuel — mirrors run_pipeline_bounded."""
        config = VerifiedPipelineConfig(max_fuel=3)
        pipeline = VerifiedPipeline(config)
        result = pipeline.run_sync("test")
        assert result.certificate.iterations_used <= 3

    def test_pipeline_traverses_all_domains(self):
        """All 5 domains traversed — mirrors validation_cumulative."""
        pipeline = VerifiedPipeline()
        result = pipeline.run_sync("test")
        assert result.certificate.domains_traversed == [1, 2, 3, 4, 5]

    def test_pipeline_gates_all_passed(self):
        """Default pipeline has all gates passing."""
        pipeline = VerifiedPipeline()
        result = pipeline.run_sync("test")
        assert result.certificate.gates_all_passed

    def test_pipeline_control_points(self):
        """Control points set — mirrors pipeline_implies_controls."""
        pipeline = VerifiedPipeline()
        result = pipeline.run_sync("test")
        assert result.certificate.d2_d3_ready
        assert result.certificate.d4_d5_ready

    def test_pipeline_answer_earned(self):
        """Answer earned with valid pipeline — mirrors valid_pipeline_answer_earned."""
        pipeline = VerifiedPipeline()
        result = pipeline.run_sync("test")
        assert result.certificate.answer_earned

    def test_pipeline_reflect_valid(self):
        """Reflect is valid — mirrors pipeline_implies_reflect."""
        pipeline = VerifiedPipeline()
        result = pipeline.run_sync("test")
        assert result.certificate.reflect_valid

    def test_pipeline_certificate_has_theorems(self):
        """Certificate lists backing theorems."""
        pipeline = VerifiedPipeline()
        result = pipeline.run_sync("test")
        assert len(result.certificate.backing_theorems) >= 5


# ═══════════════════════════════════
# SECTION E: PARADIGM SHIFT
# ═══════════════════════════════════

class TestParadigmShift:
    """Tests mirroring PipelineSemantics.v Section H (#9-12)."""

    def test_shift_preserves_erfragte(self):
        """Shift keeps erfragte — mirrors shift_preserves_erfragte."""
        pipeline = VerifiedPipeline()
        ask = D6AskOutput(
            gefragte="topic", befragte="source", erfragte="exact_format",
            sub_questions=["q1"], serves_root=[("q1", True)],
            composition_test=True, traps=[], format_required="text",
        )
        reflect = D6ReflectFull(
            class_i_conclusive="x",
            perceptive="a", procedural="b",
            err_chain=ERRChainCheck(True, True, True, True),
            scope_fails_when="x", adjustment_reason="x",
            adjusted_confidence=50.0,
            return_assessment=ReturnAssessment(type=ReturnType.EXPANDING),
        )
        shifted = pipeline._shift_ask(ask, reflect)
        assert shifted.erfragte == ask.erfragte

    def test_shift_bumps_complexity(self):
        """Shift increments complexity — mirrors shift_bumps_complexity."""
        pipeline = VerifiedPipeline()
        ask = D6AskOutput(
            gefragte="topic", befragte="source", erfragte="text",
            sub_questions=["q1"], serves_root=[("q1", True)],
            composition_test=True, traps=[], format_required="text",
            complexity=0,
        )
        reflect = D6ReflectFull(
            class_i_conclusive="x",
            perceptive="a", procedural="b",
            err_chain=ERRChainCheck(True, True, True, True),
            scope_fails_when="x", adjustment_reason="x",
        )
        shifted = pipeline._shift_ask(ask, reflect)
        assert shifted.complexity == 1

    def test_shift_preserves_sub_questions(self):
        """Shift preserves sub-questions — mirrors shift_preserves_sub_questions."""
        pipeline = VerifiedPipeline()
        ask = D6AskOutput(
            gefragte="topic", befragte="source", erfragte="text",
            sub_questions=["q1", "q2", "q3"],
            serves_root=[("q1", True), ("q2", True), ("q3", True)],
            composition_test=True, traps=[], format_required="text",
        )
        reflect = D6ReflectFull(
            class_i_conclusive="x",
            perceptive="a", procedural="b",
            err_chain=ERRChainCheck(True, True, True, True),
            scope_fails_when="x", adjustment_reason="x",
        )
        shifted = pipeline._shift_ask(ask, reflect)
        assert shifted.sub_questions == ask.sub_questions

    def test_expanding_triggers_paradigm_shift(self):
        """RT_Expanding triggers paradigm shift — mirrors expanding_triggers_shift."""
        config = VerifiedPipelineConfig(max_fuel=5, max_shifts=2)
        iterations = [0]

        def domain_runner(domain_num, q, prev, ask):
            return {
                "domain": domain_num,
                "answer": f"D{domain_num}",
                "confidence": 50 + domain_num * 5 + iterations[0] * 10,
                "aligned": True, "coverage": True,
                "consistent": True, "confidence_matches": True,
            }

        call_count = [0]

        def reflect_runner(outputs, gates, ask):
            call_count[0] += 1
            iterations[0] += 1
            if call_count[0] <= 2:
                return D6ReflectFull(
                    class_i_conclusive="need shift",
                    perceptive="a", procedural="b",
                    err_chain=ERRChainCheck(True, True, True, True),
                    scope_fails_when="x", adjustment_reason="x",
                    adjusted_confidence=40.0 + call_count[0] * 10,
                    return_assessment=ReturnAssessment(
                        type=ReturnType.EXPANDING, target_domain=3, reason="stall"
                    ),
                )
            else:
                return D6ReflectFull(
                    class_i_conclusive="done",
                    perceptive="a", procedural="b",
                    err_chain=ERRChainCheck(True, True, True, True),
                    scope_fails_when="x", adjustment_reason="x",
                    adjusted_confidence=90.0,
                    return_assessment=ReturnAssessment(type=ReturnType.NONE),
                )

        pipeline = VerifiedPipeline(config)
        result = pipeline.run_sync(
            "test", domain_runner=domain_runner, reflect_runner=reflect_runner
        )
        assert result.certificate.paradigm_shifts >= 1


# ═══════════════════════════════════
# SECTION F: GATE EARLY TERMINATION
# ═══════════════════════════════════

class TestGateEarlyTermination:
    """Tests mirroring PipelineSemantics.v Section I (#13-15)."""

    def test_escalation_stops_pipeline(self):
        """Gate escalation stops at failing domain."""
        def domain_runner(domain_num, q, prev, ask):
            consistent = domain_num != 3  # D3 contradicts D2
            return {
                "domain": domain_num,
                "answer": f"D{domain_num}",
                "confidence": 50,
                "aligned": True, "coverage": True,
                "consistent": consistent,
                "confidence_matches": True,
            }

        pipeline = VerifiedPipeline()
        result = pipeline.run_sync("test", domain_runner=domain_runner)
        # D3 gate should escalate, so we won't have all 5 domains
        assert len(result.domain_outputs) < 5

    def test_gate_failure_recorded(self):
        """Failing gate is recorded in certificate."""
        def domain_runner(domain_num, q, prev, ask):
            return {
                "domain": domain_num,
                "answer": f"D{domain_num}",
                "confidence": 50,
                "aligned": domain_num != 2,  # D2 misaligned
                "coverage": True,
                "consistent": True,
                "confidence_matches": True,
            }

        pipeline = VerifiedPipeline()
        result = pipeline.run_sync("test", domain_runner=domain_runner)
        # Should have at least one non-PASS gate
        assert not result.certificate.gates_all_passed
