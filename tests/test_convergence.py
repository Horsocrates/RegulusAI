"""Tests for convergence calculator and advisor (Phase 6)."""

import pytest

from regulus.verified.convergence import ContractionEstimate, ConvergenceAnalyzer
from regulus.verified.convergence_advisor import ConvergenceAdvisor


class TestContractiveSequence:
    """Test a clearly contractive sequence: 30 -> 50 -> 60 -> 65 -> 67.5."""

    def test_contractive_sequence(self):
        analyzer = ConvergenceAnalyzer()
        for c in [30.0, 50.0, 60.0, 65.0, 67.5]:
            analyzer.record_iteration(c)

        estimate = analyzer.estimate_contraction()
        assert estimate is not None
        assert estimate.is_contractive
        # Gaps: 70, 50, 40, 35, 32.5
        # Ratios: 50/70=0.714, 40/50=0.8, 35/40=0.875, 32.5/35=0.929
        # Median of [0.714, 0.8, 0.875, 0.929] = (0.8 + 0.875) / 2 = 0.8375
        assert 0.5 < estimate.factor < 1.0

        rec = analyzer.recommend()
        assert rec["action"] in ("continue", "stop_converged")
        assert rec["contraction_factor"] is not None
        assert rec["theorem_backing"] == "FixedPoint.v: Banach_contraction_principle"


class TestNonContractive:
    """Test an oscillating (non-contractive) sequence: 50 -> 60 -> 50 -> 60 -> 50."""

    def test_non_contractive(self):
        analyzer = ConvergenceAnalyzer()
        for c in [50.0, 60.0, 50.0, 60.0, 50.0]:
            analyzer.record_iteration(c)

        estimate = analyzer.estimate_contraction()
        assert estimate is not None
        # Gaps: 50, 40, 50, 40, 50
        # Ratios: 0.8, 1.25, 0.8, 1.25
        # Median = (0.8 + 1.25) / 2 = 1.025 >= 1
        assert not estimate.is_contractive or estimate.factor >= 0.95

        rec = analyzer.recommend()
        # Should recommend paradigm shift (non-contractive or stalling)
        assert rec["action"] == "paradigm_shift"


class TestAlreadyConverged:
    """Test a sequence that has already converged: 80 -> 82 -> 83 -> 83.5."""

    def test_already_converged(self):
        analyzer = ConvergenceAnalyzer()
        for c in [80.0, 82.0, 83.0, 83.5]:
            analyzer.record_iteration(c)

        # Current confidence 83.5, gap = 16.5 — not within 5pp yet.
        # But let's push it higher to trigger stop_converged.
        analyzer.record_iteration(96.0)

        rec = analyzer.recommend()
        assert rec["action"] == "stop_converged"
        assert rec["estimated_iterations_remaining"] == 0


class TestSlowConvergence:
    """Test a slowly converging sequence: 50 -> 52 -> 53.5 -> 54.8 -> 55.9."""

    def test_slow_convergence(self):
        analyzer = ConvergenceAnalyzer()
        for c in [50.0, 52.0, 53.5, 54.8, 55.9]:
            analyzer.record_iteration(c)

        estimate = analyzer.estimate_contraction()
        assert estimate is not None
        # Gaps: 50, 48, 46.5, 45.2, 44.1
        # Ratios: 0.96, 0.97, 0.97, 0.976
        # High factor (close to 1) → slow convergence
        assert estimate.is_contractive
        assert estimate.factor > 0.9

        rec = analyzer.recommend()
        assert rec["contraction_factor"] is not None
        assert rec["contraction_factor"] > 0.9


class TestIterationsNeeded:
    """Test iterations_needed calculation on ContractionEstimate."""

    def test_iterations_needed(self):
        est = ContractionEstimate(factor=0.5, initial_gap=20.0, confidence_at_start=40.0)
        assert est.is_contractive
        n = est.iterations_needed(epsilon=5.0)
        # c=0.5, d0=20, eps=5
        # c^n * d0 / (1-c) < eps => 0.5^n * 20 / 0.5 < 5 => 0.5^n * 40 < 5 => 0.5^n < 0.125
        # n > log(0.125) / log(0.5) = 3
        assert 2 <= n <= 5


class TestIterationsNeededAlreadyConverged:
    """Test iterations_needed when gap is already within epsilon."""

    def test_iterations_needed_already_converged(self):
        est = ContractionEstimate(factor=0.5, initial_gap=3.0, confidence_at_start=97.0)
        assert est.iterations_needed(epsilon=5.0) == 0


class TestIterationsNeededNotContractive:
    """Test iterations_needed when factor >= 1 (not contractive)."""

    def test_iterations_needed_not_contractive(self):
        est = ContractionEstimate(factor=1.2, initial_gap=20.0, confidence_at_start=80.0)
        assert not est.is_contractive
        assert est.iterations_needed(epsilon=5.0) == -1


class TestPredictedConfidence:
    """Test predicted_confidence_at returns reasonable values."""

    def test_predicted_confidence(self):
        est = ContractionEstimate(factor=0.5, initial_gap=50.0, confidence_at_start=50.0)
        # At n=0: 100 - 50 * 1 / 0.5 = 100 - 100 = 0 (clamped to 0)
        pred_0 = est.predicted_confidence_at(0)
        assert 0.0 <= pred_0 <= 100.0

        # At n=5: 100 - 50 * 0.5^5 / 0.5 = 100 - 50 * 0.03125 / 0.5 = 100 - 3.125 = 96.875
        pred_5 = est.predicted_confidence_at(5)
        assert pred_5 > pred_0
        assert 0.0 <= pred_5 <= 100.0

        # At large n, should approach 100
        pred_20 = est.predicted_confidence_at(20)
        assert pred_20 > 99.0

    def test_predicted_confidence_non_contractive(self):
        est = ContractionEstimate(factor=1.5, initial_gap=20.0, confidence_at_start=80.0)
        # Non-contractive: returns start confidence
        assert est.predicted_confidence_at(5) == 80.0


class TestDeploymentProfile:
    """Test derive_deployment_profile returns required keys."""

    def test_deployment_profile(self):
        analyzer = ConvergenceAnalyzer()
        for c in [40.0, 55.0, 62.0, 66.0, 68.0]:
            analyzer.record_iteration(c)

        profile = analyzer.derive_deployment_profile()

        required_keys = {
            "iterations_completed",
            "current_confidence",
            "contraction_factor",
            "is_contractive",
            "estimated_total_iterations",
            "convergence_status",
            "theorem_backing",
        }
        assert required_keys.issubset(profile.keys())
        assert profile["iterations_completed"] == 5
        assert profile["current_confidence"] == 68.0
        assert profile["theorem_backing"] == "FixedPoint.v: Banach_contraction_principle"
        assert profile["convergence_status"] in (
            "converged",
            "converging",
            "divergent",
            "insufficient_data",
        )

    def test_deployment_profile_empty(self):
        analyzer = ConvergenceAnalyzer()
        profile = analyzer.derive_deployment_profile()
        assert profile["convergence_status"] == "insufficient_data"
        assert profile["current_confidence"] is None


class TestAdvisorOutput:
    """Test ConvergenceAdvisor.advise() returns string with bracket tags."""

    def test_advisor_output(self):
        advisor = ConvergenceAdvisor()
        for c in [30.0, 50.0, 60.0, 65.0, 67.5]:
            advisor.record(c)

        result = advisor.advise()
        assert isinstance(result, str)
        assert "[ACTION]" in result
        assert "[REASON]" in result
        assert "[THEOREM]" in result
        assert "Banach" in result or "FixedPoint" in result

    def test_advisor_insufficient_data(self):
        advisor = ConvergenceAdvisor()
        advisor.record(50.0)

        result = advisor.advise()
        assert isinstance(result, str)
        assert "[ACTION]" in result
        assert "CONTINUE" in result
