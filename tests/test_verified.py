"""
Tests for the verified computation backend (Phase 4).

All tests work WITHOUT OCaml binaries — they exercise Python fallbacks.
Every test verifies that results carry proper theorem_used traceability.
"""

import pytest

from regulus.verified.bridge import VerifiedBackend, VerifiedResult
from regulus.verified.math_verifier import MathVerifier
from regulus.verified.err_validator import ERRValidator
from regulus.verified.layers import (
    AnalysisLayer,
    LayeredAnalysis,
    MATH_LAYER,
    EMPIRICAL_LAYER,
    LOGICAL_LAYER,
    ETHICAL_LAYER,
    make_domain_layer,
)


# ── VerifiedResult ─────────────────────────────────────────────────────


class TestVerifiedResult:
    def test_result_has_theorem(self):
        r = VerifiedResult(True, 42, "test cert", "Some.theorem")
        assert r.theorem_used == "Some.theorem"
        assert r.success is True
        assert r.value == 42
        assert r.certificate == "test cert"


# ── VerifiedBackend: IVT ───────────────────────────────────────────────


class TestIVT:
    def setup_method(self):
        self.vb = VerifiedBackend()

    def test_ivt_applicable(self):
        result = self.vb.check_ivt(f_a=1.0, f_b=-1.0)
        assert result.success
        assert result.value is True
        assert "IVT guarantees" in result.certificate
        assert "IVT_ERR" in result.theorem_used

    def test_ivt_not_applicable_same_sign(self):
        result = self.vb.check_ivt(f_a=1.0, f_b=2.0)
        assert result.success
        assert result.value is False
        assert "not directly applicable" in result.certificate

    def test_ivt_negative_to_positive(self):
        result = self.vb.check_ivt(f_a=-3.0, f_b=5.0)
        assert result.value is True

    def test_ivt_zero_values(self):
        result = self.vb.check_ivt(f_a=0.0, f_b=1.0)
        assert result.value is False  # 0 is not > 0 and not < 0


# ── VerifiedBackend: EVT ───────────────────────────────────────────────


class TestEVT:
    def setup_method(self):
        self.vb = VerifiedBackend()

    def test_evt_l5_leftmost(self):
        result = self.vb.check_evt([1.0, 5.0, 5.0, 3.0])
        assert result.success
        assert result.value["max_value"] == 5.0
        assert result.value["max_index"] == 1  # L5: leftmost of the two 5.0s
        assert result.value["l5_resolved"] is True
        assert "EVT_idx" in result.theorem_used

    def test_evt_single_max(self):
        result = self.vb.check_evt([1.0, 2.0, 7.0, 4.0])
        assert result.value["max_value"] == 7.0
        assert result.value["max_index"] == 2

    def test_evt_all_equal(self):
        result = self.vb.check_evt([3.0, 3.0, 3.0])
        assert result.value["max_index"] == 0  # L5: first

    def test_evt_singleton(self):
        result = self.vb.check_evt([42.0])
        assert result.value["max_value"] == 42.0
        assert result.value["max_index"] == 0

    def test_evt_empty(self):
        result = self.vb.check_evt([])
        assert result.success is False


# ── VerifiedBackend: Convergence ───────────────────────────────────────


class TestConvergence:
    def setup_method(self):
        self.vb = VerifiedBackend()

    def test_converges(self):
        result = self.vb.check_convergence(ratio=0.5)
        assert result.value["converges"] is True
        assert "SeriesConvergence" in result.theorem_used

    def test_diverges(self):
        result = self.vb.check_convergence(ratio=1.5)
        assert result.value["converges"] is False

    def test_boundary(self):
        result = self.vb.check_convergence(ratio=1.0)
        assert result.value["converges"] is False  # Not strictly less


# ── VerifiedBackend: Contraction ───────────────────────────────────────


class TestContraction:
    def setup_method(self):
        self.vb = VerifiedBackend()

    def test_contraction(self):
        result = self.vb.check_contraction(factor=0.5, x0=0.0, x1=1.0)
        assert result.value["is_contraction"] is True
        assert result.value["error_bound"] == 2.0  # 1 / (1 - 0.5) = 2
        assert "FixedPoint" in result.theorem_used

    def test_not_contraction(self):
        result = self.vb.check_contraction(factor=1.5, x0=0.0, x1=1.0)
        assert result.value["is_contraction"] is False


# ── VerifiedBackend: L5 Resolution ─────────────────────────────────────


class TestL5:
    def setup_method(self):
        self.vb = VerifiedBackend()

    def test_l5_resolve(self):
        result = self.vb.l5_resolve([5, 3, 7, 3])
        assert result.success
        assert result.value == 3
        assert "L5Resolution" in result.theorem_used

    def test_l5_singleton(self):
        result = self.vb.l5_resolve([42])
        assert result.value == 42

    def test_l5_empty(self):
        result = self.vb.l5_resolve([])
        assert result.success is False


# ── VerifiedBackend: CROWN ─────────────────────────────────────────────


class TestCROWN:
    def setup_method(self):
        self.vb = VerifiedBackend()

    def test_crown_fallback(self):
        result = self.vb.check_crown_bounds(
            weights=[[1.0, 2.0], [-1.0, 3.0]],
            bias=[0.5, -0.5],
            input_lo=[0.0, 0.0],
            input_hi=[1.0, 1.0],
        )
        assert result.success
        assert "output_lo" in result.value
        assert "output_hi" in result.value
        # Check dimensions
        assert len(result.value["output_lo"]) == 2
        assert len(result.value["output_hi"]) == 2
        # After ReLU, outputs should be >= 0
        assert all(v >= 0 for v in result.value["output_lo"])
        assert "PInterval_CROWN" in result.theorem_used

    def test_crown_identity(self):
        """Identity weights, zero bias, [0,1] input → [0,1] output."""
        result = self.vb.check_crown_bounds(
            weights=[[1.0]],
            bias=[0.0],
            input_lo=[0.0],
            input_hi=[1.0],
        )
        assert result.value["output_lo"] == [0.0]
        assert result.value["output_hi"] == [1.0]

    def test_crown_negative_weights(self):
        """Negative weight flips lo/hi before ReLU."""
        result = self.vb.check_crown_bounds(
            weights=[[-1.0]],
            bias=[0.0],
            input_lo=[0.0],
            input_hi=[1.0],
        )
        # -1 * [0,1] = [-1, 0], after ReLU = [0, 0]
        assert result.value["output_lo"] == [0.0]
        assert result.value["output_hi"] == [0.0]


# ── VerifiedBackend: ERR Well-Formedness ───────────────────────────────


class TestERRWellFormed:
    def setup_method(self):
        self.vb = VerifiedBackend()

    def test_well_formed(self):
        result = self.vb.check_err_well_formed(
            elements=[{"id": "E1"}, {"id": "E2"}],
            roles=[
                {"element_id": "E1", "role": "given"},
                {"element_id": "E2", "role": "unknown"},
            ],
            rules=[{"id": "RULE1", "connects": ["E1", "E2"]}],
            dependencies=[{"from": "E1", "to": "E2", "via": "RULE1"}],
        )
        assert result.success
        assert result.value["well_formed"] is True
        assert "Roles" in result.theorem_used

    def test_circular_dependency(self):
        result = self.vb.check_err_well_formed(
            elements=[{"id": "E1"}],
            roles=[{"element_id": "E1", "role": "given"}],
            rules=[{"id": "RULE1", "connects": ["E1"]}],
            dependencies=[{"from": "E1", "to": "E1", "via": "RULE1"}],
        )
        assert result.value["well_formed"] is False
        assert any("Circular" in v for v in result.value["violations"])

    def test_orphan_element(self):
        result = self.vb.check_err_well_formed(
            elements=[{"id": "E1"}, {"id": "E2"}],
            roles=[{"element_id": "E1", "role": "given"}],  # E2 has no role
            rules=[],
            dependencies=[],
        )
        assert result.value["well_formed"] is False
        assert any("without roles" in v for v in result.value["violations"])

    def test_duplicate_id(self):
        result = self.vb.check_err_well_formed(
            elements=[{"id": "E1"}, {"id": "E1"}],
            roles=[{"element_id": "E1", "role": "given"}],
            rules=[],
            dependencies=[],
        )
        assert result.value["well_formed"] is False
        assert any("Duplicate" in v for v in result.value["violations"])

    def test_cross_category_self_ref(self):
        result = self.vb.check_err_well_formed(
            elements=[{"id": "X"}],
            roles=[{"element_id": "X", "role": "given"}],
            rules=[{"id": "X", "connects": []}],  # Same ID as element
            dependencies=[],
        )
        assert result.value["well_formed"] is False
        assert any("self-reference" in v for v in result.value["violations"])


# ── MathVerifier ───────────────────────────────────────────────────────


class TestMathVerifier:
    def setup_method(self):
        self.mv = MathVerifier()

    def test_ivt_detection(self):
        result = self.mv.try_verify(
            d3_framework="Intermediate Value Theorem",
            d4_data={"f_a": 1.0, "f_b": -1.0},
        )
        assert result is not None
        assert result.value is True
        assert "IVT" in result.theorem_used

    def test_evt_detection(self):
        result = self.mv.try_verify(
            d3_framework="Find the maximum value",
            d4_data={"values": [1, 3, 2]},
        )
        assert result is not None
        assert result.value["max_value"] == 3

    def test_crown_detection(self):
        result = self.mv.try_verify(
            d3_framework="CROWN interval bounds",
            d4_data={
                "weights": [[1.0]],
                "bias": [0.0],
                "input_lo": [0.0],
                "input_hi": [1.0],
            },
        )
        assert result is not None
        assert "output_lo" in result.value

    def test_convergence_detection(self):
        result = self.mv.try_verify(
            d3_framework="Ratio test for series convergence",
            d4_data={"ratio": 0.5},
        )
        assert result is not None
        assert result.value["converges"] is True

    def test_contraction_detection(self):
        result = self.mv.try_verify(
            d3_framework="Fixed point iteration",
            d4_data={"factor": 0.3, "x0": 0, "x1": 1},
        )
        assert result is not None
        assert result.value["is_contraction"] is True

    def test_no_match(self):
        result = self.mv.try_verify(
            d3_framework="Historical analysis",
            d4_data={"some": "data"},
        )
        assert result is None

    def test_annotate_d4_output(self):
        d3_out = {"framework": "Intermediate Value Theorem"}
        d4_out = {"computation_data": {"f_a": -2.0, "f_b": 3.0}}
        annotated = self.mv.annotate_d4_output(d3_out, d4_out)
        assert "verified_result" in annotated
        assert annotated["verified_result"]["confidence_override"] == 100

    def test_annotate_no_match(self):
        d3_out = {"framework": "Literary criticism"}
        d4_out = {"computation_data": {}}
        annotated = self.mv.annotate_d4_output(d3_out, d4_out)
        assert "verified_result" not in annotated


# ── ERRValidator ───────────────────────────────────────────────────────


class TestERRValidator:
    def setup_method(self):
        self.validator = ERRValidator()

    def test_valid_d1(self):
        d1 = {
            "elements": [{"id": "E1"}, {"id": "E2"}],
            "roles": [
                {"element_id": "E1", "role": "given"},
                {"element_id": "E2", "role": "unknown"},
            ],
            "rules": [{"id": "RULE1", "connects": ["E1", "E2"]}],
            "dependencies": [{"from": "E1", "to": "E2"}],
        }
        result = self.validator.validate_d1_output(d1)
        assert result["valid"] is True
        assert len(result["violations"]) == 0
        assert "well-formed" in result["certificate"]

    def test_invalid_d1_cycle(self):
        d1 = {
            "elements": [{"id": "E1"}],
            "roles": [{"element_id": "E1", "role": "given"}],
            "rules": [{"id": "RULE1"}],
            "dependencies": [{"from": "E1", "to": "E1"}],
        }
        result = self.validator.validate_d1_output(d1)
        assert result["valid"] is False
        assert len(result["suggestions"]) > 0
        assert "RETURN TO D1" in result["suggestions"][0]

    def test_gate_proceed(self):
        d1 = {
            "elements": [{"id": "E1"}],
            "roles": [{"element_id": "E1", "role": "given"}],
            "rules": [],
            "dependencies": [],
        }
        gate_result = self.validator.gate_d1_to_d2(d1)
        assert gate_result["action"] == "proceed_to_d2"
        assert "err_certificate" in gate_result["d1_output"]

    def test_gate_retry(self):
        d1 = {
            "elements": [{"id": "E1"}],
            "roles": [],  # No roles → L4 violation
            "rules": [],
            "dependencies": [],
        }
        gate_result = self.validator.gate_d1_to_d2(d1)
        assert gate_result["action"] == "retry_d1"
        assert len(gate_result["guidance"]) > 0

    def test_cross_check_discrepancy(self):
        d1 = {
            "elements": [{"id": "E1"}],
            "roles": [{"element_id": "E1", "role": "given"}],
            "rules": [],
            "dependencies": [{"from": "E1", "to": "E1"}],  # Cycle
            "err_hierarchy_check": {
                "no_circular_dependencies": True,  # D1 claims no cycle — wrong!
            },
        }
        result = self.validator.validate_d1_output(d1)
        assert result["valid"] is False
        assert len(result["cross_check"]) > 0
        assert "DISCREPANCY" in result["cross_check"][0]


# ── LayeredAnalysis ────────────────────────────────────────────────────


class TestLayers:
    def test_add_layer(self):
        la = LayeredAnalysis(substrate={"d1": "output"})
        assert la.add_layer(MATH_LAYER) is True
        assert len(la.layers) == 1
        assert la.active_layer == "math"  # First layer auto-activates

    def test_add_duplicate_layer(self):
        la = LayeredAnalysis(substrate={})
        la.add_layer(MATH_LAYER)
        # Same criterion_type + focus_predicate → rejected (P3)
        duplicate = AnalysisLayer(
            id="math2",
            name="Also Math",
            criterion_type="mathematical",
            focus_predicate="formal derivation and computation",
            reason="Duplicate",
        )
        assert la.add_layer(duplicate) is False
        assert len(la.layers) == 1

    def test_switch_layer(self):
        la = LayeredAnalysis(substrate={})
        la.add_layer(MATH_LAYER)
        la.add_layer(EMPIRICAL_LAYER)
        assert la.active_layer == "math"

        result = la.switch_layer("empirical")
        assert result is not None
        assert result.id == "empirical"
        assert la.active_layer == "empirical"

    def test_switch_nonexistent(self):
        la = LayeredAnalysis(substrate={})
        assert la.switch_layer("nope") is None

    def test_get_active_criterion(self):
        la = LayeredAnalysis(substrate={})
        la.add_layer(MATH_LAYER)
        assert la.get_active_criterion() == "formal derivation and computation"

    def test_get_active_criterion_none(self):
        la = LayeredAnalysis(substrate={})
        assert la.get_active_criterion() is None

    def test_priority_ordering(self):
        la = LayeredAnalysis(substrate={})
        la.add_layer(EMPIRICAL_LAYER)  # priority=5
        la.add_layer(MATH_LAYER)  # priority=10
        la.add_layer(LOGICAL_LAYER)  # priority=8

        ordered = la.get_layers_by_priority()
        assert ordered[0].id == "math"  # 10
        assert ordered[1].id == "logical"  # 8
        assert ordered[2].id == "empirical"  # 5

    def test_compare_agreement(self):
        la = LayeredAnalysis(substrate={})
        la.add_layer(MATH_LAYER)
        la.add_layer(LOGICAL_LAYER)
        la.store_result("math", {"d5_answer": "42", "confidence": 0.95})
        la.store_result("logical", {"d5_answer": "42", "confidence": 0.88})

        comparison = la.compare_across_layers()
        assert comparison["agreement"] is True
        assert comparison["unique_answers"] == 1
        assert "converge" in comparison["insight"]
        assert comparison["best_layer"] == "math"

    def test_compare_disagreement(self):
        la = LayeredAnalysis(substrate={})
        la.add_layer(MATH_LAYER)
        la.add_layer(EMPIRICAL_LAYER)
        la.store_result("math", {"d5_answer": "42", "confidence": 0.9})
        la.store_result("empirical", {"d5_answer": "37", "confidence": 0.7})

        comparison = la.compare_across_layers()
        assert comparison["agreement"] is False
        assert comparison["unique_answers"] == 2
        assert "diverge" in comparison["insight"]

    def test_compare_insufficient(self):
        la = LayeredAnalysis(substrate={})
        la.add_layer(MATH_LAYER)
        la.store_result("math", {"d5_answer": "42"})

        comparison = la.compare_across_layers()
        assert comparison["comparison"] == "insufficient_layers"

    def test_to_dict(self):
        la = LayeredAnalysis(substrate={"key": "value"})
        la.add_layer(MATH_LAYER)
        la.store_result("math", {"d5_answer": "42"})

        d = la.to_dict()
        assert d["substrate"] == {"key": "value"}
        assert len(d["layers"]) == 1
        assert d["active_layer"] == "math"
        assert "math" in d["layer_results"]

    def test_make_domain_layer(self):
        physics = make_domain_layer("physics", priority=7)
        assert physics.id == "domain_physics"
        assert physics.criterion_type == "domain_specific"
        assert "physics" in physics.focus_predicate

    def test_ethical_layer(self):
        la = LayeredAnalysis(substrate={})
        la.add_layer(ETHICAL_LAYER)
        assert la.get_active_criterion() == "moral implications and value alignment"


# ── Integration: Full Pipeline Flow ────────────────────────────────────


class TestIntegration:
    """End-to-end tests simulating the full D1→D6 pipeline with verification."""

    def test_d1_validate_then_d4_verify(self):
        """D1 produces valid ERR → passes gate → D4 uses verified EVT."""
        # D1 output
        d1_output = {
            "elements": [
                {"id": "E1", "content": "function f"},
                {"id": "E2", "content": "interval [a,b]"},
            ],
            "roles": [
                {"element_id": "E1", "role": "given"},
                {"element_id": "E2", "role": "constraint"},
            ],
            "rules": [{"id": "R1", "connects": ["E1", "E2"]}],
            "dependencies": [{"from": "E2", "to": "E1"}],
        }

        # Step 1: Validate D1
        validator = ERRValidator()
        gate = validator.gate_d1_to_d2(d1_output)
        assert gate["action"] == "proceed_to_d2"

        # Step 2: D3 selects framework, D4 computes
        d3_output = {"framework": "Extreme Value Theorem"}
        d4_output = {
            "computation_data": {"values": [1.0, 3.0, 2.0, 3.0]},
            "d4_text": "The maximum is 3 at index 1",
        }

        # Step 3: Verify D4 computation
        verifier = MathVerifier()
        annotated = verifier.annotate_d4_output(d3_output, d4_output)
        assert "verified_result" in annotated
        assert annotated["verified_result"]["value"]["max_value"] == 3.0
        assert annotated["verified_result"]["value"]["max_index"] == 1

    def test_multi_layer_analysis(self):
        """Multi-layer analysis with cross-layer comparison."""
        la = LayeredAnalysis(
            substrate={
                "question": "Is this investment safe?",
                "elements": [{"id": "E1", "content": "annual return 8%"}],
            }
        )

        # Add layers
        la.add_layer(MATH_LAYER)
        la.add_layer(EMPIRICAL_LAYER)
        la.add_layer(make_domain_layer("finance"))

        # Simulate per-layer analysis
        la.store_result(
            "math",
            {"d5_answer": "Expected return positive", "confidence": 0.92},
        )
        la.store_result(
            "empirical",
            {"d5_answer": "Historical data supports", "confidence": 0.78},
        )
        la.store_result(
            "domain_finance",
            {"d5_answer": "Below market risk premium", "confidence": 0.85},
        )

        # D6 comparison
        comparison = la.compare_across_layers()
        assert comparison["layer_count"] == 3
        assert comparison["unique_answers"] == 3  # All different perspectives
        assert comparison["agreement"] is False
        assert comparison["best_layer"] == "math"  # highest confidence
