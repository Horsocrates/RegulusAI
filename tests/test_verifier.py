"""
Tests for NNVerificationEngine.

Tests:
1. Basic MLP verification → valid result shape
2. CNN+BN verification → valid 10-class output
3. Certified detection → clear separation → certified=True
4. Not certified → overlapping bounds → certified=False
5. Reanchored strategy → valid result with narrower bounds
6. Width tracking → layer_widths populated correctly
7. verify_from_point convenience method
8. Summary and width_report formatting
"""

import numpy as np
import pytest
import torch
import torch.nn as nn

from regulus.nn.verifier import (
    NNVerificationEngine, NNVerificationResult,
    VerificationMode, VerificationContract,
)
from regulus.nn.interval_tensor import IntervalTensor


class TestNNVerificationEngine:
    """Tests for the NNVerificationEngine."""

    def _make_simple_mlp(self, in_dim=4, hidden=8, out_dim=3):
        """Create a simple MLP for testing."""
        model = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, out_dim),
        )
        model.eval()
        return model

    def _make_deep_mlp(self, in_dim=4, hidden=8, out_dim=3, depth=5):
        """Create a deeper MLP for testing width blowup."""
        layers = []
        prev = in_dim
        for _ in range(depth):
            layers.append(nn.Linear(prev, hidden))
            layers.append(nn.ReLU())
            prev = hidden
        layers.append(nn.Linear(hidden, out_dim))
        model = nn.Sequential(*layers)
        model.eval()
        return model

    def test_basic_mlp(self):
        """Simple MLP verification produces valid result shape."""
        model = self._make_simple_mlp(in_dim=4, out_dim=3)
        engine = NNVerificationEngine(strategy="naive")

        x = np.random.randn(4)
        result = engine.verify_from_point(model, x, epsilon=0.01)

        assert isinstance(result, NNVerificationResult)
        assert result.output_lo.shape == (3,)
        assert result.output_hi.shape == (3,)
        assert result.output_width.shape == (3,)
        assert np.all(result.output_lo <= result.output_hi + 1e-12)
        assert 0 <= result.predicted_class < 3
        assert isinstance(result.certified_robust, bool)
        assert result.strategy == "naive"
        assert result.input_eps == pytest.approx(0.01, abs=1e-6)

    def test_cnn_bn(self):
        """CNN+BN model verification produces valid result."""
        from regulus.nn.architectures import make_cifar_cnn_bn

        model = make_cifar_cnn_bn()  # 3x32x32 input, 10 classes
        model.eval()
        engine = NNVerificationEngine(strategy="naive")

        # CIFAR-like input: 3x32x32
        x = np.random.randn(3, 32, 32) * 0.1
        it = IntervalTensor.from_uncertainty(x, 0.001)
        result = engine.verify(model, it)

        assert result.output_lo.shape == (10,)
        assert result.output_hi.shape == (10,)
        assert np.all(result.output_lo <= result.output_hi + 1e-12)
        assert 0 <= result.predicted_class < 10

    def test_certified_detection(self):
        """With very small epsilon, verification should certify robustness."""
        model = self._make_simple_mlp(in_dim=4, out_dim=3)
        engine = NNVerificationEngine(strategy="naive")

        # Use a very small epsilon so bounds don't overlap
        x = np.random.randn(4)
        result = engine.verify_from_point(model, x, epsilon=1e-8)

        # With tiny epsilon, output intervals should be nearly point-like
        assert np.max(result.output_width) < 1e-4
        # Almost certainly certified (bounds won't overlap with point-like intervals)
        assert result.certified_robust is True
        assert result.margin > 0

    def test_not_certified_large_eps(self):
        """With large epsilon, bounds should overlap → not certified."""
        model = self._make_simple_mlp(in_dim=4, out_dim=3)
        engine = NNVerificationEngine(strategy="naive")

        # Use a very large epsilon so bounds definitely overlap
        x = np.zeros(4)
        result = engine.verify_from_point(model, x, epsilon=100.0)

        # With huge epsilon, intervals blow up → classes overlap
        assert result.certified_robust is False

    def test_reanchored_midpoint_strategy(self):
        """Reanchored midpoint strategy produces valid result with controlled width."""
        model = self._make_deep_mlp(depth=5)
        engine_reanchor = NNVerificationEngine(
            strategy="midpoint",
            reanchor_eps=0.001,
            block_size=1,
        )

        x = np.random.randn(4)
        eps = 0.01

        result_reanchor = engine_reanchor.verify_from_point(model, x, eps)

        # Produces valid result
        assert result_reanchor.output_lo.shape == (3,)
        assert np.all(result_reanchor.output_lo <= result_reanchor.output_hi + 1e-12)

        # Width is bounded (reanchoring controls blowup)
        # With reanchor_eps=0.001, output width stays bounded regardless of depth
        assert np.max(result_reanchor.output_width) < 10.0  # sanity bound

        assert result_reanchor.strategy == "midpoint"

    def test_reanchored_adaptive_strategy(self):
        """Adaptive strategy produces valid result."""
        model = self._make_deep_mlp(depth=3)
        engine = NNVerificationEngine(
            strategy="adaptive",
            reanchor_eps=0.001,
            adaptive_threshold=0.5,
        )

        x = np.random.randn(4)
        result = engine.verify_from_point(model, x, epsilon=0.01)

        assert isinstance(result, NNVerificationResult)
        assert result.strategy == "adaptive"
        assert np.all(result.output_lo <= result.output_hi + 1e-12)

    def test_reanchored_proportional_strategy(self):
        """Proportional strategy produces valid result."""
        model = self._make_deep_mlp(depth=3)
        engine = NNVerificationEngine(strategy="proportional")

        x = np.random.randn(4)
        result = engine.verify_from_point(model, x, epsilon=0.01)

        assert isinstance(result, NNVerificationResult)
        assert result.strategy == "proportional"
        assert np.all(result.output_lo <= result.output_hi + 1e-12)

    def test_hybrid_strategy(self):
        """Hybrid strategy produces valid result."""
        model = self._make_deep_mlp(depth=3)
        engine = NNVerificationEngine(
            strategy="hybrid",
            adaptive_threshold=10.0,
        )

        x = np.random.randn(4)
        result = engine.verify_from_point(model, x, epsilon=0.01)

        assert isinstance(result, NNVerificationResult)
        assert result.strategy == "hybrid"

    def test_width_tracking_naive(self):
        """Naive strategy populates layer_widths correctly."""
        model = self._make_simple_mlp(in_dim=4, hidden=8, out_dim=3)
        engine = NNVerificationEngine(strategy="naive")

        x = np.random.randn(4)
        result = engine.verify_from_point(model, x, epsilon=0.01)

        # IntervalSequential tracks layer_widths: [input, after_layer1, ..., output]
        assert len(result.layer_widths) > 0
        # All widths should be non-negative
        assert all(w >= 0 for w in result.layer_widths)

    def test_width_tracking_reanchored(self):
        """Reanchored strategy populates block_widths correctly."""
        model = self._make_deep_mlp(depth=3)
        engine = NNVerificationEngine(
            strategy="midpoint",
            block_size=1,
        )

        x = np.random.randn(4)
        result = engine.verify_from_point(model, x, epsilon=0.01)

        # ReanchoredIntervalModel has block_widths
        assert len(result.layer_widths) > 0
        assert all(w >= 0 for w in result.layer_widths)

    def test_timing(self):
        """Verify timing is captured."""
        model = self._make_simple_mlp()
        engine = NNVerificationEngine(strategy="naive")

        x = np.random.randn(4)
        result = engine.verify_from_point(model, x, epsilon=0.01)

        assert result.conversion_time_ms >= 0
        assert result.propagation_time_ms >= 0

    def test_soundness_containment(self):
        """Core IBP soundness: point output is within interval bounds."""
        model = self._make_simple_mlp(in_dim=4, out_dim=3)
        model.eval()
        engine = NNVerificationEngine(strategy="naive")

        x = np.random.randn(4)
        eps = 0.01
        result = engine.verify_from_point(model, x, epsilon=eps)

        # Point forward pass at center
        with torch.no_grad():
            x_torch = torch.tensor(x, dtype=torch.float32)
            point_output = model(x_torch).numpy()

        # Point output must be within [lo, hi] bounds (with tolerance)
        assert np.all(point_output >= result.output_lo - 1e-6), (
            f"Point output {point_output} below lo {result.output_lo}"
        )
        assert np.all(point_output <= result.output_hi + 1e-6), (
            f"Point output {point_output} above hi {result.output_hi}"
        )

    def test_soundness_perturbed_samples(self):
        """Multiple perturbed samples stay within IBP bounds."""
        model = self._make_simple_mlp(in_dim=4, out_dim=3)
        model.eval()
        engine = NNVerificationEngine(strategy="naive")

        x = np.random.randn(4)
        eps = 0.05
        result = engine.verify_from_point(model, x, epsilon=eps)

        # Try 50 random perturbations within epsilon ball
        for _ in range(50):
            delta = np.random.uniform(-eps, eps, size=4)
            x_pert = x + delta
            with torch.no_grad():
                out = model(torch.tensor(x_pert, dtype=torch.float32)).numpy()
            assert np.all(out >= result.output_lo - 1e-5), (
                f"Perturbed output {out} below lo {result.output_lo}"
            )
            assert np.all(out <= result.output_hi + 1e-5), (
                f"Perturbed output {out} above hi {result.output_hi}"
            )

    def test_invalid_strategy(self):
        """Invalid strategy raises ValueError."""
        with pytest.raises(ValueError, match="Unknown strategy"):
            NNVerificationEngine(strategy="invalid_strategy")


class TestNNVerificationResult:
    """Tests for NNVerificationResult formatting."""

    def _make_result(self, certified=True):
        """Create a sample result for formatting tests."""
        return NNVerificationResult(
            output_lo=np.array([0.1, -0.2, 0.3]),
            output_hi=np.array([0.5, 0.1, 0.8]),
            output_width=np.array([0.4, 0.3, 0.5]),
            predicted_class=2,
            certified_robust=certified,
            margin=0.1,
            layer_widths=[0.02, 0.05, 0.12, 0.40],
            input_eps=0.01,
            conversion_time_ms=1.5,
            propagation_time_ms=3.2,
            strategy="naive",
        )

    def test_summary_certified(self):
        """Summary shows CERTIFIED for certified result."""
        result = self._make_result(certified=True)
        summary = result.summary()
        assert "CERTIFIED" in summary
        assert "Predicted class: 2" in summary
        assert "naive" in summary

    def test_summary_not_certified(self):
        """Summary shows NOT CERTIFIED for non-certified result."""
        result = self._make_result(certified=False)
        summary = result.summary()
        assert "NOT CERTIFIED" in summary

    def test_width_report(self):
        """Width report shows per-layer widths."""
        result = self._make_result()
        report = result.width_report()
        assert "Layer" in report
        assert "Input" in report
        assert "Ratio" in report

    def test_width_report_empty(self):
        """Width report handles no layer data."""
        result = self._make_result()
        result.layer_widths = []
        report = result.width_report()
        assert "No layer width data" in report


# =============================================================
# I3: Verification Modes + Contract
# =============================================================


class TestVerificationMode:
    """Tests for VerificationMode enum and mode validation."""

    def test_cert_mode_enum(self):
        """VerificationMode.CERT should exist with value 'cert'."""
        assert VerificationMode.CERT.value == "cert"

    def test_uq_mode_enum(self):
        """VerificationMode.UQ should exist with value 'uq'."""
        assert VerificationMode.UQ.value == "uq"

    def test_cert_naive_valid(self):
        """CERT + naive is a valid combination."""
        engine = NNVerificationEngine(mode="cert", strategy="naive")
        assert engine.mode == VerificationMode.CERT
        assert engine.strategy == "naive"

    def test_cert_midpoint_raises(self):
        """CERT + midpoint should raise ValueError."""
        with pytest.raises(ValueError, match="CERT mode requires naive"):
            NNVerificationEngine(mode="cert", strategy="midpoint")

    def test_cert_proportional_raises(self):
        """CERT + proportional should raise ValueError."""
        with pytest.raises(ValueError, match="CERT mode requires naive"):
            NNVerificationEngine(mode="cert", strategy="proportional")

    def test_uq_naive_raises(self):
        """UQ + naive should raise ValueError."""
        with pytest.raises(ValueError, match="UQ mode requires a reanchored"):
            NNVerificationEngine(mode="uq", strategy="naive")

    def test_uq_proportional_valid(self):
        """UQ + proportional is a valid combination."""
        engine = NNVerificationEngine(mode="uq", strategy="proportional")
        assert engine.mode == VerificationMode.UQ
        assert engine.strategy == "proportional"

    def test_uq_midpoint_valid(self):
        """UQ + midpoint is a valid combination."""
        engine = NNVerificationEngine(mode="uq", strategy="midpoint")
        assert engine.mode == VerificationMode.UQ

    def test_uq_adaptive_valid(self):
        """UQ + adaptive is a valid combination."""
        engine = NNVerificationEngine(mode="uq", strategy="adaptive")
        assert engine.mode == VerificationMode.UQ

    def test_uq_hybrid_valid(self):
        """UQ + hybrid is a valid combination."""
        engine = NNVerificationEngine(mode="uq", strategy="hybrid")
        assert engine.mode == VerificationMode.UQ

    def test_invalid_mode_raises(self):
        """Invalid mode string should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown mode"):
            NNVerificationEngine(mode="invalid_mode")

    def test_backward_compat_no_mode(self):
        """Legacy: NNVerificationEngine(strategy='naive') still works."""
        engine = NNVerificationEngine(strategy="naive")
        assert engine.mode is None
        assert engine.strategy == "naive"

    def test_backward_compat_midpoint(self):
        """Legacy: NNVerificationEngine(strategy='midpoint') still works."""
        engine = NNVerificationEngine(strategy="midpoint")
        assert engine.mode is None
        assert engine.strategy == "midpoint"


class TestVerificationContract:
    """Tests for VerificationContract and verify_contract()."""

    def _make_simple_mlp(self, in_dim=4, hidden=8, out_dim=3):
        model = nn.Sequential(
            nn.Linear(in_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, out_dim),
        )
        model.eval()
        return model

    def test_cert_contract_certified(self):
        """CERT mode with tiny epsilon should produce certified=True, risk=0.0."""
        torch.manual_seed(42)
        model = self._make_simple_mlp()
        engine = NNVerificationEngine(mode="cert", strategy="naive")

        x = np.random.randn(4)
        contract = engine.verify_contract(model, x, epsilon=1e-8)

        assert isinstance(contract, VerificationContract)
        assert contract.mode == VerificationMode.CERT
        assert contract.certified is True
        assert contract.risk == 0.0
        assert contract.margin > 0

    def test_cert_contract_not_certified(self):
        """CERT mode with huge epsilon should produce certified=False, risk=1.0."""
        torch.manual_seed(42)
        model = self._make_simple_mlp()
        engine = NNVerificationEngine(mode="cert", strategy="naive")

        x = np.zeros(4)
        contract = engine.verify_contract(model, x, epsilon=100.0)

        assert contract.mode == VerificationMode.CERT
        assert contract.certified is False
        assert contract.risk == 1.0

    def test_uq_contract_never_certified(self):
        """UQ mode should never certify, even with tiny epsilon."""
        torch.manual_seed(42)
        model = self._make_simple_mlp()
        engine = NNVerificationEngine(
            mode="uq", strategy="proportional",
            reanchor_eps=0.001,
        )

        x = np.random.randn(4)
        contract = engine.verify_contract(model, x, epsilon=1e-8)

        assert contract.mode == VerificationMode.UQ
        assert contract.certified is False
        # Risk should be low (small width relative to margin)
        assert 0.0 <= contract.risk <= 1.0

    def test_uq_risk_proportional(self):
        """UQ risk should increase with wider bounds."""
        torch.manual_seed(42)
        model = self._make_simple_mlp()
        engine = NNVerificationEngine(
            mode="uq", strategy="proportional",
        )

        x = np.random.randn(4)

        contract_small = engine.verify_contract(model, x, epsilon=0.001)
        contract_big = engine.verify_contract(model, x, epsilon=0.1)

        # Larger epsilon → wider bounds → higher risk
        assert contract_big.risk >= contract_small.risk

    def test_contract_fields_typed(self):
        """VerificationContract fields should have correct types."""
        torch.manual_seed(42)
        model = self._make_simple_mlp()
        engine = NNVerificationEngine(mode="cert", strategy="naive")

        x = np.random.randn(4)
        contract = engine.verify_contract(model, x, epsilon=0.01)

        assert isinstance(contract.mode, VerificationMode)
        assert isinstance(contract.predicted_class, int)
        assert isinstance(contract.certified, bool)
        assert isinstance(contract.margin, float)
        assert isinstance(contract.max_output_width, float)
        assert isinstance(contract.risk, float)
        assert isinstance(contract.output_bounds, tuple)
        assert len(contract.output_bounds) == 2
        assert isinstance(contract.output_bounds[0], np.ndarray)
        assert isinstance(contract.output_bounds[1], np.ndarray)
        assert isinstance(contract.per_layer_widths, list)
        assert isinstance(contract.total_time_ms, float)
        assert isinstance(contract.metadata, dict)
        assert contract.logic_guard_gate is None

    def test_contract_summary_cert(self):
        """Contract summary should indicate CERTIFICATION mode."""
        torch.manual_seed(42)
        model = self._make_simple_mlp()
        engine = NNVerificationEngine(mode="cert", strategy="naive")

        x = np.random.randn(4)
        contract = engine.verify_contract(model, x, epsilon=1e-8)

        summary = contract.summary()
        assert "CERTIFICATION" in summary
        assert "CERTIFIED" in summary

    def test_contract_summary_uq(self):
        """Contract summary should indicate UQ mode."""
        torch.manual_seed(42)
        model = self._make_simple_mlp()
        engine = NNVerificationEngine(mode="uq", strategy="proportional")

        x = np.random.randn(4)
        contract = engine.verify_contract(model, x, epsilon=0.01)

        summary = contract.summary()
        assert "UQ" in summary
        assert "Risk Signal" in summary

    def test_verify_contract_requires_mode(self):
        """verify_contract without mode should raise ValueError."""
        model = self._make_simple_mlp()
        engine = NNVerificationEngine(strategy="naive")  # no mode

        x = np.random.randn(4)
        with pytest.raises(ValueError, match="requires mode"):
            engine.verify_contract(model, x, epsilon=0.01)

    def test_contract_metadata(self):
        """Contract metadata should contain strategy details."""
        torch.manual_seed(42)
        model = self._make_simple_mlp()
        engine = NNVerificationEngine(mode="cert", strategy="naive", fold_bn=True)

        x = np.random.randn(4)
        contract = engine.verify_contract(model, x, epsilon=0.01)

        assert contract.metadata["strategy"] == "naive"
        assert contract.metadata["fold_bn"] is True

    def test_logic_guard_gate_default_none(self):
        """logic_guard_gate should default to None."""
        torch.manual_seed(42)
        model = self._make_simple_mlp()
        engine = NNVerificationEngine(mode="cert", strategy="naive")

        x = np.random.randn(4)
        contract = engine.verify_contract(model, x, epsilon=0.01)

        assert contract.logic_guard_gate is None

    def test_logic_guard_gate_settable(self):
        """logic_guard_gate should be settable after creation."""
        contract = VerificationContract(
            mode=VerificationMode.CERT,
            predicted_class=0,
            certified=True,
            margin=0.5,
            max_output_width=0.1,
            risk=0.0,
            output_bounds=(np.array([0.1]), np.array([0.2])),
            per_layer_widths=[0.01, 0.05],
            total_time_ms=1.0,
        )
        assert contract.logic_guard_gate is None

        contract.logic_guard_gate = True
        assert contract.logic_guard_gate is True

        summary = contract.summary()
        assert "LogicGuard gate" in summary
        assert "PASS" in summary
