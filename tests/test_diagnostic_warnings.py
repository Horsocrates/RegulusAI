"""Tests for v1.0d diagnostic warnings computed from cross-domain signals."""

import pytest
from regulus.audit.auditor import compute_diagnostic_warnings
from regulus.audit.types import AuditResult, DomainAuditResult


def _make_audit(
    d1_depth=3, d2_depth=3, d5_cert="probabilistic",
    d6_genuine=True, d6_weight=65, d1_weight=70,
    d5_weight=75, d3_obj=None,
) -> AuditResult:
    """Helper to build a minimal AuditResult for testing."""
    domains = [
        DomainAuditResult(domain="D1", present=True, weight=d1_weight,
                          d1_depth=d1_depth, e_exists=True, r_exists=True,
                          rule_exists=True, s_exists=True),
        DomainAuditResult(domain="D2", present=True, weight=65,
                          d2_depth=d2_depth, e_exists=True, r_exists=True,
                          rule_exists=True, s_exists=True),
        DomainAuditResult(domain="D3", present=True, weight=60,
                          d3_objectivity_pass=d3_obj, e_exists=True, r_exists=True,
                          rule_exists=True, s_exists=True),
        DomainAuditResult(domain="D4", present=True, weight=65,
                          d4_aristotle_ok=True, e_exists=True, r_exists=True,
                          rule_exists=True, s_exists=True),
        DomainAuditResult(domain="D5", present=True, weight=d5_weight,
                          d5_certainty_type=d5_cert, e_exists=True, r_exists=True,
                          rule_exists=True, s_exists=True),
        DomainAuditResult(domain="D6", present=True, weight=d6_weight,
                          d6_genuine=d6_genuine, e_exists=True, r_exists=True,
                          rule_exists=True, s_exists=True),
    ]
    return AuditResult(domains=domains, overall_issues=[], parse_quality=0.8)


class TestCertDepthMismatch:
    def test_triggers_on_necessary_with_shallow_d1(self):
        audit = _make_audit(d1_depth=2, d5_cert="necessary")
        warnings = compute_diagnostic_warnings("What is X?", audit)
        assert any("CERT_DEPTH_MISMATCH" in w for w in warnings)

    def test_no_trigger_on_necessary_with_deep_d1(self):
        audit = _make_audit(d1_depth=3, d5_cert="necessary")
        warnings = compute_diagnostic_warnings("What is X?", audit)
        assert not any("CERT_DEPTH_MISMATCH" in w for w in warnings)

    def test_no_trigger_on_probabilistic(self):
        audit = _make_audit(d1_depth=1, d5_cert="probabilistic")
        warnings = compute_diagnostic_warnings("What is X?", audit)
        assert not any("CERT_DEPTH_MISMATCH" in w for w in warnings)


class TestProbabilisticOnDefinitive:
    def test_triggers_on_how_many(self):
        audit = _make_audit(d5_cert="probabilistic")
        warnings = compute_diagnostic_warnings("How many balls are there?", audit)
        assert any("PROBABILISTIC_ON_DEFINITIVE" in w for w in warnings)

    def test_triggers_on_which(self):
        audit = _make_audit(d5_cert="probabilistic")
        warnings = compute_diagnostic_warnings("Which player holds ball A?", audit)
        assert any("PROBABILISTIC_ON_DEFINITIVE" in w for w in warnings)

    def test_no_trigger_on_open_question(self):
        audit = _make_audit(d5_cert="probabilistic")
        warnings = compute_diagnostic_warnings("Tell me about climate change", audit)
        assert not any("PROBABILISTIC_ON_DEFINITIVE" in w for w in warnings)

    def test_no_trigger_on_necessary(self):
        audit = _make_audit(d5_cert="necessary")
        warnings = compute_diagnostic_warnings("How many balls?", audit)
        assert not any("PROBABILISTIC_ON_DEFINITIVE" in w for w in warnings)


class TestEvaluativeOnFactual:
    def test_triggers_on_calculate(self):
        audit = _make_audit(d5_cert="evaluative")
        warnings = compute_diagnostic_warnings("Calculate the total", audit)
        assert any("EVALUATIVE_ON_FACTUAL" in w for w in warnings)

    def test_triggers_on_count(self):
        audit = _make_audit(d5_cert="evaluative")
        warnings = compute_diagnostic_warnings("Count the number of items", audit)
        assert any("EVALUATIVE_ON_FACTUAL" in w for w in warnings)

    def test_no_trigger_on_opinion_question(self):
        audit = _make_audit(d5_cert="evaluative")
        warnings = compute_diagnostic_warnings("Is this a good approach?", audit)
        assert not any("EVALUATIVE_ON_FACTUAL" in w for w in warnings)


class TestDepthRegression:
    def test_triggers_when_d1_exceeds_d2(self):
        audit = _make_audit(d1_depth=4, d2_depth=2)
        warnings = compute_diagnostic_warnings("query", audit)
        assert any("DEPTH_REGRESSION" in w for w in warnings)

    def test_no_trigger_when_equal(self):
        audit = _make_audit(d1_depth=3, d2_depth=3)
        warnings = compute_diagnostic_warnings("query", audit)
        assert not any("DEPTH_REGRESSION" in w for w in warnings)

    def test_no_trigger_when_d2_higher(self):
        audit = _make_audit(d1_depth=2, d2_depth=3)
        warnings = compute_diagnostic_warnings("query", audit)
        assert not any("DEPTH_REGRESSION" in w for w in warnings)


class TestShallowButPassing:
    def test_triggers_on_high_weight_low_depth(self):
        audit = _make_audit(d1_depth=2, d2_depth=2)
        for d in audit.domains:
            d.weight = 70  # total=420
        warnings = compute_diagnostic_warnings("query", audit)
        assert any("SHALLOW_BUT_PASSING" in w for w in warnings)

    def test_no_trigger_on_deep(self):
        audit = _make_audit(d1_depth=3, d2_depth=3)
        for d in audit.domains:
            d.weight = 70
        warnings = compute_diagnostic_warnings("query", audit)
        assert not any("SHALLOW_BUT_PASSING" in w for w in warnings)

    def test_no_trigger_on_low_weight(self):
        audit = _make_audit(d1_depth=2, d2_depth=2)
        for d in audit.domains:
            d.weight = 50  # total=300
        warnings = compute_diagnostic_warnings("query", audit)
        assert not any("SHALLOW_BUT_PASSING" in w for w in warnings)


class TestUnmarkedCertainty:
    def test_triggers_on_unmarked(self):
        audit = _make_audit(d5_cert="unmarked")
        warnings = compute_diagnostic_warnings("query", audit)
        assert any("UNMARKED_CERTAINTY" in w for w in warnings)

    def test_no_trigger_on_marked(self):
        audit = _make_audit(d5_cert="probabilistic")
        warnings = compute_diagnostic_warnings("query", audit)
        assert not any("UNMARKED_CERTAINTY" in w for w in warnings)


class TestTrivialReflection:
    def test_triggers_on_low_weight_genuine(self):
        audit = _make_audit(d6_genuine=True, d6_weight=40)
        warnings = compute_diagnostic_warnings("query", audit)
        assert any("TRIVIAL_REFLECTION" in w for w in warnings)

    def test_no_trigger_on_high_weight(self):
        audit = _make_audit(d6_genuine=True, d6_weight=65)
        warnings = compute_diagnostic_warnings("query", audit)
        assert not any("TRIVIAL_REFLECTION" in w for w in warnings)

    def test_no_trigger_on_not_genuine(self):
        audit = _make_audit(d6_genuine=False, d6_weight=30)
        warnings = compute_diagnostic_warnings("query", audit)
        assert not any("TRIVIAL_REFLECTION" in w for w in warnings)


class TestMultipleWarnings:
    def test_can_fire_multiple(self):
        """A single question can trigger multiple diagnostic warnings."""
        audit = _make_audit(d1_depth=1, d2_depth=1, d5_cert="unmarked",
                            d6_genuine=True, d6_weight=30)
        for d in audit.domains:
            d.weight = 70  # total=420
        # Restore D6 weight to trigger TRIVIAL_REFLECTION
        audit.domains[5].weight = 30  # total now = 70*5 + 30 = 380 < 400
        # Bump others to compensate so total >= 400
        audit.domains[0].weight = 80  # total = 80+70+70+70+70+30 = 390, still < 400
        audit.domains[1].weight = 80  # total = 80+80+70+70+70+30 = 400
        warnings = compute_diagnostic_warnings("Calculate the value", audit)
        types = [w.split(" — ")[0] for w in warnings]
        assert "DIAG:UNMARKED_CERTAINTY" in types
        assert "DIAG:SHALLOW_BUT_PASSING" in types
        assert "DIAG:TRIVIAL_REFLECTION" in types

    def test_no_warnings_on_healthy_trace(self):
        """A well-scored trace should generate zero warnings."""
        audit = _make_audit(d1_depth=3, d2_depth=3, d5_cert="probabilistic",
                            d6_genuine=True, d6_weight=65)
        warnings = compute_diagnostic_warnings("Explain quantum entanglement", audit)
        assert len(warnings) == 0

    def test_all_warnings_prefixed_with_diag(self):
        """Every warning must start with DIAG:."""
        audit = _make_audit(d1_depth=1, d2_depth=1, d5_cert="unmarked",
                            d6_genuine=True, d6_weight=30)
        for d in audit.domains:
            d.weight = 70
        warnings = compute_diagnostic_warnings("How many items?", audit)
        for w in warnings:
            assert w.startswith("DIAG:"), f"Warning not prefixed: {w}"
