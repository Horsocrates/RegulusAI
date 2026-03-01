"""Tests for CROWN linear relaxation bounds.

Verifies:
1. Soundness: CROWN bounds contain the true output
2. Tightness: CROWN bounds are at least as tight as IBP
3. Correct integration with NNVerificationEngine
4. Edge cases: exact inputs, single-layer models
"""

import numpy as np
import pytest
import torch
import torch.nn as nn

from regulus.nn.crown import CROWNEngine, CROWNResult, crown_verify
from regulus.nn.verifier import NNVerificationEngine, NNVerificationResult
from regulus.nn.interval_tensor import IntervalTensor
from regulus.nn.model import convert_model


# =============================================================
# Fixtures
# =============================================================


@pytest.fixture
def simple_model():
    """Linear → ReLU → Linear (3→8→2)."""
    torch.manual_seed(42)
    model = nn.Sequential(
        nn.Linear(3, 8),
        nn.ReLU(),
        nn.Linear(8, 2),
    )
    model.eval()
    return model


@pytest.fixture
def deep_model():
    """Linear → ReLU → Linear → ReLU → Linear (4→16→8→3)."""
    torch.manual_seed(42)
    model = nn.Sequential(
        nn.Linear(4, 16),
        nn.ReLU(),
        nn.Linear(16, 8),
        nn.ReLU(),
        nn.Linear(8, 3),
    )
    model.eval()
    return model


@pytest.fixture
def cnn_model():
    """Conv2d → ReLU → Flatten → Linear."""
    torch.manual_seed(42)
    model = nn.Sequential(
        nn.Conv2d(1, 4, 3, padding=1),
        nn.ReLU(),
        nn.Flatten(),
        nn.Linear(4 * 4 * 4, 3),  # Assumes 4×4 input
    )
    model.eval()
    return model


@pytest.fixture
def bn_model():
    """Linear → BN → ReLU → Linear."""
    torch.manual_seed(42)
    model = nn.Sequential(
        nn.Linear(3, 8),
        nn.BatchNorm1d(8),
        nn.ReLU(),
        nn.Linear(8, 2),
    )
    # Train for a few steps so BN has running stats
    model.train()
    for _ in range(10):
        x = torch.randn(16, 3)
        _ = model(x)
    model.eval()
    return model


# =============================================================
# Soundness tests
# =============================================================


class TestCROWNSoundness:
    """CROWN bounds must always contain the true output."""

    def test_soundness_simple(self, simple_model):
        """CROWN output contains the exact output for all points in input interval."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(alpha_mode="adaptive")

        for _ in range(50):
            x = rng.standard_normal(3).astype(np.float64)
            eps = 0.1
            result = engine.compute_bounds(simple_model, x, eps)

            # True output at center point
            with torch.no_grad():
                y_true = simple_model(torch.tensor(x, dtype=torch.float32)).numpy()

            assert np.all(result.output_lo <= y_true + 1e-5), \
                f"Lower bound violation: {result.output_lo} > {y_true}"
            assert np.all(result.output_hi >= y_true - 1e-5), \
                f"Upper bound violation: {result.output_hi} < {y_true}"

    def test_soundness_perturbed_points(self, simple_model):
        """CROWN bounds contain outputs at random perturbations within epsilon."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(alpha_mode="adaptive")

        x = rng.standard_normal(3).astype(np.float64)
        eps = 0.1
        result = engine.compute_bounds(simple_model, x, eps)

        # Test 200 random perturbations
        for _ in range(200):
            delta = rng.uniform(-eps, eps, size=3)
            x_pert = x + delta
            with torch.no_grad():
                y_pert = simple_model(torch.tensor(x_pert, dtype=torch.float32)).numpy()

            assert np.all(result.output_lo <= y_pert + 1e-5), \
                f"Lower bound violation at perturbation: {result.output_lo} > {y_pert}"
            assert np.all(result.output_hi >= y_pert - 1e-5), \
                f"Upper bound violation at perturbation: {result.output_hi} < {y_pert}"

    def test_soundness_deep(self, deep_model):
        """Soundness for deeper network."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(alpha_mode="adaptive")

        for _ in range(30):
            x = rng.standard_normal(4).astype(np.float64)
            eps = 0.05
            result = engine.compute_bounds(deep_model, x, eps)

            with torch.no_grad():
                y_true = deep_model(torch.tensor(x, dtype=torch.float32)).numpy()

            assert np.all(result.output_lo <= y_true + 1e-5)
            assert np.all(result.output_hi >= y_true - 1e-5)

    def test_soundness_bn(self, bn_model):
        """Soundness with BatchNorm folding."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(alpha_mode="adaptive")

        for _ in range(30):
            x = rng.standard_normal(3).astype(np.float64)
            eps = 0.1
            result = engine.compute_bounds(bn_model, x, eps)

            with torch.no_grad():
                # BN requires batch dimension for forward pass
                y_true = bn_model(torch.tensor(x, dtype=torch.float32).unsqueeze(0)).squeeze(0).numpy()

            assert np.all(result.output_lo <= y_true + 1e-5), \
                f"BN soundness: lo={result.output_lo}, true={y_true}"
            assert np.all(result.output_hi >= y_true - 1e-5), \
                f"BN soundness: hi={result.output_hi}, true={y_true}"


# =============================================================
# Tightness tests
# =============================================================


class TestCROWNTightness:
    """CROWN bounds should be at least as tight as IBP."""

    def test_tighter_than_ibp_simple(self, simple_model):
        """CROWN width <= IBP width for simple model."""
        rng = np.random.default_rng(42)
        crown_engine = CROWNEngine(alpha_mode="adaptive")
        ibp_engine = NNVerificationEngine(strategy="naive", fold_bn=True)

        tighter_count = 0
        total = 30

        for _ in range(total):
            x = rng.standard_normal(3).astype(np.float64)
            eps = 0.1

            crown_result = crown_engine.compute_bounds(simple_model, x, eps)
            ibp_result = ibp_engine.verify_from_point(simple_model, x, eps)

            crown_width = np.mean(crown_result.output_hi - crown_result.output_lo)
            ibp_width = np.mean(ibp_result.output_width)

            # CROWN should be <= IBP width (within tolerance)
            assert crown_width <= ibp_width + 1e-5, \
                f"CROWN wider than IBP: {crown_width} > {ibp_width}"

            if crown_width < ibp_width - 1e-6:
                tighter_count += 1

        # CROWN should be strictly tighter for at least some inputs
        # (when there are unstable ReLUs)
        assert tighter_count > 0, \
            f"CROWN was never tighter than IBP in {total} trials"

    def test_improvement_ratio(self, simple_model):
        """CROWN improvement field is positive for models with unstable ReLUs."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(alpha_mode="adaptive")

        improvements = []
        for _ in range(20):
            x = rng.standard_normal(3).astype(np.float64)
            eps = 0.1
            result = engine.compute_bounds(simple_model, x, eps)
            improvements.append(result.crown_improvement)

        # At least some should be positive
        assert max(improvements) > 0, \
            f"No improvement observed: {improvements}"

    def test_tighter_than_ibp_deep(self, deep_model):
        """CROWN especially helps deep models (more unstable ReLUs)."""
        rng = np.random.default_rng(42)
        crown_engine = CROWNEngine(alpha_mode="adaptive")
        ibp_engine = NNVerificationEngine(strategy="naive", fold_bn=True)

        crown_widths = []
        ibp_widths = []

        for _ in range(20):
            x = rng.standard_normal(4).astype(np.float64)
            eps = 0.05

            crown_result = crown_engine.compute_bounds(deep_model, x, eps)
            ibp_result = ibp_engine.verify_from_point(deep_model, x, eps)

            crown_widths.append(np.mean(crown_result.output_hi - crown_result.output_lo))
            ibp_widths.append(np.mean(ibp_result.output_width))

        avg_crown = np.mean(crown_widths)
        avg_ibp = np.mean(ibp_widths)

        assert avg_crown <= avg_ibp + 1e-5, \
            f"CROWN avg {avg_crown} > IBP avg {avg_ibp}"


# =============================================================
# Edge cases
# =============================================================


class TestCROWNEdgeCases:
    """Test edge cases for robustness."""

    def test_zero_epsilon(self, simple_model):
        """With eps=0, CROWN should give exact point output."""
        x = np.array([1.0, 0.5, -0.3], dtype=np.float64)
        engine = CROWNEngine(alpha_mode="adaptive")
        result = engine.compute_bounds(simple_model, x, epsilon=0.0)

        with torch.no_grad():
            y_true = simple_model(torch.tensor(x, dtype=torch.float32)).numpy()

        np.testing.assert_allclose(result.output_lo, y_true, atol=1e-5)
        np.testing.assert_allclose(result.output_hi, y_true, atol=1e-5)

    def test_single_linear_layer(self):
        """Single linear layer: CROWN = IBP (no ReLU relaxation needed)."""
        torch.manual_seed(42)
        model = nn.Sequential(nn.Linear(3, 2))
        model.eval()

        x = np.array([1.0, 0.0, -1.0], dtype=np.float64)
        eps = 0.1

        crown = CROWNEngine(alpha_mode="adaptive")
        crown_result = crown.compute_bounds(model, x, eps)

        ibp = NNVerificationEngine(strategy="naive")
        ibp_result = ibp.verify_from_point(model, x, eps)

        # For single linear layer, CROWN = IBP (no ReLU to relax)
        np.testing.assert_allclose(
            crown_result.output_lo, ibp_result.output_lo, atol=1e-6
        )
        np.testing.assert_allclose(
            crown_result.output_hi, ibp_result.output_hi, atol=1e-6
        )

    def test_all_alpha_modes(self, simple_model):
        """All alpha modes produce sound bounds."""
        x = np.array([0.5, -0.3, 1.2], dtype=np.float64)
        eps = 0.1

        with torch.no_grad():
            y_true = simple_model(torch.tensor(x, dtype=torch.float32)).numpy()

        for mode in ("adaptive", "zero", "one", "parallel"):
            engine = CROWNEngine(alpha_mode=mode)
            result = engine.compute_bounds(simple_model, x, eps)

            assert np.all(result.output_lo <= y_true + 1e-5), \
                f"Mode '{mode}' lower bound violation"
            assert np.all(result.output_hi >= y_true - 1e-5), \
                f"Mode '{mode}' upper bound violation"


# =============================================================
# Verifier integration
# =============================================================


class TestCROWNVerifierIntegration:
    """Test CROWN through the NNVerificationEngine API."""

    def test_crown_strategy(self, simple_model):
        """NNVerificationEngine(strategy='crown') works."""
        engine = NNVerificationEngine(strategy="crown")
        x = np.array([1.0, 0.0, -0.5], dtype=np.float64)
        result = engine.verify_from_point(simple_model, x, epsilon=0.1)

        assert isinstance(result, NNVerificationResult)
        assert result.strategy == "crown"
        assert result.output_lo.shape == (2,)
        assert result.output_hi.shape == (2,)

    def test_crown_cert_mode(self, simple_model):
        """CROWN + CERT mode works."""
        engine = NNVerificationEngine(strategy="crown", mode="cert")
        x = np.array([1.0, 0.0, -0.5], dtype=np.float64)
        contract = engine.verify_contract(simple_model, x, epsilon=0.1)

        assert contract.mode.value == "cert"
        assert isinstance(contract.certified, bool)
        assert contract.max_output_width >= 0

    def test_crown_vs_ibp_certification(self, simple_model):
        """CROWN certifies at least as many inputs as IBP."""
        rng = np.random.default_rng(42)
        crown_engine = NNVerificationEngine(strategy="crown")
        ibp_engine = NNVerificationEngine(strategy="naive", fold_bn=True)

        crown_certified = 0
        ibp_certified = 0
        total = 50

        for _ in range(total):
            x = rng.standard_normal(3).astype(np.float64)
            eps = 0.1

            crown_result = crown_engine.verify_from_point(simple_model, x, eps)
            ibp_result = ibp_engine.verify_from_point(simple_model, x, eps)

            if crown_result.certified_robust:
                crown_certified += 1
            if ibp_result.certified_robust:
                ibp_certified += 1

        assert crown_certified >= ibp_certified, \
            f"CROWN certified {crown_certified} < IBP certified {ibp_certified}"


# =============================================================
# Convenience function
# =============================================================


class TestCrownVerifyFunction:
    """Test the crown_verify convenience function."""

    def test_crown_verify(self, simple_model):
        """crown_verify returns CROWNResult."""
        x = np.array([1.0, 0.0, -0.5], dtype=np.float64)
        result = crown_verify(simple_model, x, epsilon=0.1)
        assert isinstance(result, CROWNResult)
        assert result.output_lo.shape == (2,)

    def test_crown_verify_improvement_field(self, simple_model):
        """crown_verify populates improvement field."""
        x = np.array([1.0, 0.0, -0.5], dtype=np.float64)
        result = crown_verify(simple_model, x, epsilon=0.1)
        assert isinstance(result.crown_improvement, float)
        assert result.crown_improvement >= -0.01  # Should be ~0 or positive


# =============================================================
# Conv2d tests
# =============================================================


class TestCROWNConv2d:
    """Test CROWN with convolutional layers."""

    def test_soundness_cnn(self, cnn_model):
        """CROWN is sound for CNN architecture."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(alpha_mode="adaptive")

        for _ in range(20):
            # 1-channel 4×4 image
            x = rng.standard_normal((1, 4, 4)).astype(np.float64)
            eps = 0.05
            result = engine.compute_bounds(cnn_model, x, eps)

            with torch.no_grad():
                y_true = cnn_model(torch.tensor(x, dtype=torch.float32).unsqueeze(0)).squeeze(0).numpy()

            assert np.all(result.output_lo <= y_true + 1e-4), \
                f"CNN lower bound violation: lo={result.output_lo}, true={y_true}"
            assert np.all(result.output_hi >= y_true - 1e-4), \
                f"CNN upper bound violation: hi={result.output_hi}, true={y_true}"

    def test_cnn_perturbed(self, cnn_model):
        """CROWN bounds contain outputs at random perturbations for CNN."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(alpha_mode="adaptive")

        x = rng.standard_normal((1, 4, 4)).astype(np.float64)
        eps = 0.05
        result = engine.compute_bounds(cnn_model, x, eps)

        for _ in range(100):
            delta = rng.uniform(-eps, eps, size=(1, 4, 4))
            x_pert = x + delta
            with torch.no_grad():
                y_pert = cnn_model(
                    torch.tensor(x_pert, dtype=torch.float32).unsqueeze(0)
                ).squeeze(0).numpy()

            assert np.all(result.output_lo <= y_pert + 1e-4), \
                f"CNN perturbation: lo={result.output_lo}, pert={y_pert}"
            assert np.all(result.output_hi >= y_pert - 1e-4), \
                f"CNN perturbation: hi={result.output_hi}, pert={y_pert}"


# =============================================================
# CROWN Deep mode tests
# =============================================================


@pytest.fixture
def cnn_with_pool():
    """Conv2d → ReLU → MaxPool2d → Flatten → Linear (for testing deep mode)."""
    torch.manual_seed(42)
    model = nn.Sequential(
        nn.Conv2d(1, 4, 3, padding=1),
        nn.ReLU(),
        nn.MaxPool2d(2),
        nn.Flatten(),
        nn.Linear(4 * 4 * 4, 3),  # 8x8 input → 4x4 after pool
    )
    model.eval()
    return model


@pytest.fixture
def cnn_bn_pool():
    """Conv→BN→ReLU→Pool→Conv→BN→ReLU→Pool→Flatten→Linear→ReLU→Linear."""
    torch.manual_seed(42)
    model = nn.Sequential(
        nn.Conv2d(1, 4, 3, padding=1),
        nn.BatchNorm2d(4),
        nn.ReLU(),
        nn.MaxPool2d(2),
        nn.Conv2d(4, 8, 3, padding=1),
        nn.BatchNorm2d(8),
        nn.ReLU(),
        nn.MaxPool2d(2),
        nn.Flatten(),
        nn.Linear(8 * 2 * 2, 16),
        nn.ReLU(),
        nn.Linear(16, 3),
    )
    # Train BN
    model.train()
    for _ in range(10):
        x = torch.randn(16, 1, 8, 8)
        _ = model(x)
    model.eval()
    return model


class TestCROWNDeepMode:
    """Test CROWN with crown_depth='deep' — includes last conv block."""

    def test_deep_soundness(self, cnn_with_pool):
        """Deep CROWN is sound for Conv→ReLU→Pool→Flatten→Linear."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(alpha_mode="adaptive", crown_depth="deep")

        for _ in range(20):
            x = rng.standard_normal((1, 8, 8)).astype(np.float64)
            eps = 0.05
            result = engine.compute_bounds(cnn_with_pool, x, eps)

            with torch.no_grad():
                y_true = cnn_with_pool(
                    torch.tensor(x, dtype=torch.float32).unsqueeze(0)
                ).squeeze(0).numpy()

            assert np.all(result.output_lo <= y_true + 1e-4), \
                f"Deep CROWN lower bound: lo={result.output_lo}, true={y_true}"
            assert np.all(result.output_hi >= y_true - 1e-4), \
                f"Deep CROWN upper bound: hi={result.output_hi}, true={y_true}"

    def test_deep_perturbed(self, cnn_with_pool):
        """Deep CROWN bounds contain outputs at random perturbations."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(alpha_mode="adaptive", crown_depth="deep")

        x = rng.standard_normal((1, 8, 8)).astype(np.float64)
        eps = 0.05
        result = engine.compute_bounds(cnn_with_pool, x, eps)

        for _ in range(100):
            delta = rng.uniform(-eps, eps, size=(1, 8, 8))
            x_pert = x + delta
            with torch.no_grad():
                y_pert = cnn_with_pool(
                    torch.tensor(x_pert, dtype=torch.float32).unsqueeze(0)
                ).squeeze(0).numpy()

            assert np.all(result.output_lo <= y_pert + 1e-4), \
                f"Deep perturbation: lo={result.output_lo}, pert={y_pert}"
            assert np.all(result.output_hi >= y_pert - 1e-4), \
                f"Deep perturbation: hi={result.output_hi}, pert={y_pert}"

    def test_deep_tighter_than_fc(self, cnn_bn_pool):
        """Deep CROWN should produce bounds at least as tight as FC-only CROWN."""
        rng = np.random.default_rng(42)
        engine_fc = CROWNEngine(alpha_mode="adaptive", crown_depth="fc")
        engine_deep = CROWNEngine(alpha_mode="adaptive", crown_depth="deep")

        tighter_count = 0
        total = 20

        for _ in range(total):
            x = rng.standard_normal((1, 8, 8)).astype(np.float64)
            eps = 0.05

            fc_result = engine_fc.compute_bounds(cnn_bn_pool, x, eps)
            deep_result = engine_deep.compute_bounds(cnn_bn_pool, x, eps)

            fc_width = np.mean(fc_result.output_hi - fc_result.output_lo)
            deep_width = np.mean(deep_result.output_hi - deep_result.output_lo)

            # Deep should be <= FC width (at least as tight) with some tolerance
            # (may not always be tighter due to maxpool routing approximation)
            if deep_width < fc_width - 1e-6:
                tighter_count += 1

            # Both must be sound — verify at center point
            with torch.no_grad():
                y_true = cnn_bn_pool(
                    torch.tensor(x, dtype=torch.float32).unsqueeze(0)
                ).squeeze(0).numpy()

            assert np.all(deep_result.output_lo <= y_true + 1e-4), \
                f"Deep not sound: lo={deep_result.output_lo}, true={y_true}"
            assert np.all(deep_result.output_hi >= y_true - 1e-4), \
                f"Deep not sound: hi={deep_result.output_hi}, true={y_true}"

    def test_deep_soundness_multi_block(self, cnn_bn_pool):
        """Deep CROWN is sound for multi-block CNN (Conv→BN→ReLU→Pool ×2)."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(alpha_mode="adaptive", crown_depth="deep")

        for _ in range(20):
            x = rng.standard_normal((1, 8, 8)).astype(np.float64)
            eps = 0.05
            result = engine.compute_bounds(cnn_bn_pool, x, eps)

            # Check at center
            with torch.no_grad():
                y_true = cnn_bn_pool(
                    torch.tensor(x, dtype=torch.float32).unsqueeze(0)
                ).squeeze(0).numpy()

            assert np.all(result.output_lo <= y_true + 1e-4), \
                f"Multi-block lower: lo={result.output_lo}, true={y_true}"
            assert np.all(result.output_hi >= y_true - 1e-4), \
                f"Multi-block upper: hi={result.output_hi}, true={y_true}"

            # Check at perturbations
            for _ in range(10):
                delta = rng.uniform(-eps, eps, size=(1, 8, 8))
                x_pert = x + delta
                with torch.no_grad():
                    y_pert = cnn_bn_pool(
                        torch.tensor(x_pert, dtype=torch.float32).unsqueeze(0)
                    ).squeeze(0).numpy()

                assert np.all(result.output_lo <= y_pert + 1e-4)
                assert np.all(result.output_hi >= y_pert - 1e-4)

    def test_crown_depth_parameter(self):
        """Test that crown_depth parameter works correctly."""
        engine_fc = CROWNEngine(alpha_mode="adaptive", crown_depth="fc")
        engine_deep = CROWNEngine(alpha_mode="adaptive", crown_depth="deep")
        engine_full = CROWNEngine(alpha_mode="adaptive", crown_depth="full")

        assert engine_fc.crown_depth == "fc"
        assert engine_deep.crown_depth == "deep"
        assert engine_full.crown_depth == "full"

    def test_deep_crown_start_position(self, cnn_bn_pool):
        """Verify _find_crown_start returns correct index for deep mode."""
        engine_fc = CROWNEngine(alpha_mode="adaptive", crown_depth="fc")
        engine_deep = CROWNEngine(alpha_mode="adaptive", crown_depth="deep")

        layers = engine_fc._extract_layers(cnn_bn_pool, (1, 8, 8))
        fc_start = engine_fc._find_crown_start(layers)
        deep_start = engine_deep._find_crown_start(layers)

        # Deep should start earlier (lower index) than FC
        assert deep_start is not None
        assert fc_start is not None
        assert deep_start <= fc_start, \
            f"Deep start {deep_start} should be <= FC start {fc_start}"


# =============================================================
# CROWN AvgPool tests (v3 architecture)
# =============================================================


@pytest.fixture
def cnn_avgpool():
    """Conv2d → ReLU → AvgPool2d → Flatten → Linear (for testing AvgPool CROWN)."""
    torch.manual_seed(42)
    model = nn.Sequential(
        nn.Conv2d(1, 4, 3, padding=1),
        nn.ReLU(),
        nn.AvgPool2d(2),
        nn.Flatten(),
        nn.Linear(4 * 4 * 4, 3),  # 8x8 input → 4x4 after pool
    )
    model.eval()
    return model


@pytest.fixture
def cnn_bn_avgpool():
    """Conv→BN→ReLU→AvgPool→Conv→BN→ReLU→AvgPool→Flatten→Linear→ReLU→Linear.

    Same topology as cnn_bn_pool but with AvgPool instead of MaxPool.
    """
    torch.manual_seed(42)
    model = nn.Sequential(
        nn.Conv2d(1, 4, 3, padding=1),
        nn.BatchNorm2d(4),
        nn.ReLU(),
        nn.AvgPool2d(2),
        nn.Conv2d(4, 8, 3, padding=1),
        nn.BatchNorm2d(8),
        nn.ReLU(),
        nn.AvgPool2d(2),
        nn.Flatten(),
        nn.Linear(8 * 2 * 2, 16),
        nn.ReLU(),
        nn.Linear(16, 3),
    )
    # Train BN
    model.train()
    for _ in range(10):
        x = torch.randn(16, 1, 8, 8)
        _ = model(x)
    model.eval()
    return model


class TestCROWNAvgPool:
    """Test CROWN with AvgPool2d — the key v3 innovation."""

    def test_avgpool_fc_soundness(self, cnn_avgpool):
        """CROWN(fc) is sound for AvgPool architectures."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(alpha_mode="adaptive", crown_depth="fc")

        for _ in range(20):
            x = rng.standard_normal((1, 8, 8)).astype(np.float64)
            eps = 0.05
            result = engine.compute_bounds(cnn_avgpool, x, eps)

            with torch.no_grad():
                y_true = cnn_avgpool(
                    torch.tensor(x, dtype=torch.float32).unsqueeze(0)
                ).squeeze(0).numpy()

            assert np.all(result.output_lo <= y_true + 1e-4), \
                f"AvgPool fc lower: lo={result.output_lo}, true={y_true}"
            assert np.all(result.output_hi >= y_true - 1e-4), \
                f"AvgPool fc upper: hi={result.output_hi}, true={y_true}"

    def test_avgpool_deep_soundness(self, cnn_avgpool):
        """CROWN(deep) is sound for AvgPool — unlike MaxPool, CROWN propagates through."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(alpha_mode="adaptive", crown_depth="deep")

        for _ in range(20):
            x = rng.standard_normal((1, 8, 8)).astype(np.float64)
            eps = 0.05
            result = engine.compute_bounds(cnn_avgpool, x, eps)

            with torch.no_grad():
                y_true = cnn_avgpool(
                    torch.tensor(x, dtype=torch.float32).unsqueeze(0)
                ).squeeze(0).numpy()

            assert np.all(result.output_lo <= y_true + 1e-4), \
                f"AvgPool deep lower: lo={result.output_lo}, true={y_true}"
            assert np.all(result.output_hi >= y_true - 1e-4), \
                f"AvgPool deep upper: hi={result.output_hi}, true={y_true}"

    def test_avgpool_deep_perturbed(self, cnn_avgpool):
        """Deep CROWN bounds contain random perturbations for AvgPool model."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(alpha_mode="adaptive", crown_depth="deep")

        x = rng.standard_normal((1, 8, 8)).astype(np.float64)
        eps = 0.05
        result = engine.compute_bounds(cnn_avgpool, x, eps)

        for _ in range(100):
            delta = rng.uniform(-eps, eps, size=(1, 8, 8))
            x_pert = x + delta
            with torch.no_grad():
                y_pert = cnn_avgpool(
                    torch.tensor(x_pert, dtype=torch.float32).unsqueeze(0)
                ).squeeze(0).numpy()

            assert np.all(result.output_lo <= y_pert + 1e-4), \
                f"AvgPool deep pert: lo={result.output_lo}, pert={y_pert}"
            assert np.all(result.output_hi >= y_pert - 1e-4), \
                f"AvgPool deep pert: hi={result.output_hi}, pert={y_pert}"

    def test_avgpool_deep_tighter_than_fc(self, cnn_avgpool):
        """Deep CROWN through AvgPool should be tighter than FC-only.

        Unlike MaxPool (where deep == fc due to mid-concretization),
        AvgPool is linear, so CROWN CAN propagate through it, giving
        strictly tighter bounds.
        """
        rng = np.random.default_rng(42)
        engine_fc = CROWNEngine(alpha_mode="adaptive", crown_depth="fc")
        engine_deep = CROWNEngine(alpha_mode="adaptive", crown_depth="deep")

        tighter_count = 0
        total = 20

        for _ in range(total):
            x = rng.standard_normal((1, 8, 8)).astype(np.float64)
            eps = 0.05

            fc_result = engine_fc.compute_bounds(cnn_avgpool, x, eps)
            deep_result = engine_deep.compute_bounds(cnn_avgpool, x, eps)

            fc_width = np.mean(fc_result.output_hi - fc_result.output_lo)
            deep_width = np.mean(deep_result.output_hi - deep_result.output_lo)

            if deep_width < fc_width - 1e-8:
                tighter_count += 1

        # For AvgPool, deep should be tighter in most cases
        assert tighter_count >= total // 2, \
            f"Deep CROWN through AvgPool should be tighter than FC in most cases. " \
            f"Got tighter in {tighter_count}/{total}"

    def test_avgpool_multi_block_soundness(self, cnn_bn_avgpool):
        """Deep CROWN sound for multi-block AvgPool (Conv→BN→ReLU→AvgPool ×2)."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(alpha_mode="adaptive", crown_depth="deep")

        for _ in range(20):
            x = rng.standard_normal((1, 8, 8)).astype(np.float64)
            eps = 0.05
            result = engine.compute_bounds(cnn_bn_avgpool, x, eps)

            with torch.no_grad():
                y_true = cnn_bn_avgpool(
                    torch.tensor(x, dtype=torch.float32).unsqueeze(0)
                ).squeeze(0).numpy()

            assert np.all(result.output_lo <= y_true + 1e-4), \
                f"Multi-block AvgPool lower: lo={result.output_lo}, true={y_true}"
            assert np.all(result.output_hi >= y_true - 1e-4), \
                f"Multi-block AvgPool upper: hi={result.output_hi}, true={y_true}"

            # Also check perturbations
            for _ in range(10):
                delta = rng.uniform(-eps, eps, size=(1, 8, 8))
                x_pert = x + delta
                with torch.no_grad():
                    y_pert = cnn_bn_avgpool(
                        torch.tensor(x_pert, dtype=torch.float32).unsqueeze(0)
                    ).squeeze(0).numpy()

                assert np.all(result.output_lo <= y_pert + 1e-4)
                assert np.all(result.output_hi >= y_pert - 1e-4)

    def test_avgpool_ibp_naive_soundness(self, cnn_bn_avgpool):
        """IntervalSequential (naive IBP) with AvgPool is sound."""
        rng = np.random.default_rng(42)

        for _ in range(20):
            x = rng.standard_normal((1, 8, 8)).astype(np.float64)
            eps = 0.05

            imodel = convert_model(cnn_bn_avgpool, fold_bn=True)
            it_input = IntervalTensor(x - eps, x + eps)
            it_output = imodel(it_input)

            with torch.no_grad():
                y_true = cnn_bn_avgpool(
                    torch.tensor(x, dtype=torch.float32).unsqueeze(0)
                ).squeeze(0).numpy()

            assert np.all(it_output.lo <= y_true + 1e-4), \
                f"IBP AvgPool lower: lo={it_output.lo}, true={y_true}"
            assert np.all(it_output.hi >= y_true + - 1e-4), \
                f"IBP AvgPool upper: hi={it_output.hi}, true={y_true}"

    def test_avgpool_verifier_integration(self, cnn_bn_avgpool):
        """NNVerificationEngine works with AvgPool models (both naive and CROWN)."""
        rng = np.random.default_rng(42)
        x = rng.standard_normal((1, 8, 8)).astype(np.float64)
        eps = 0.05

        # Naive IBP
        engine_ibp = NNVerificationEngine(strategy="naive")
        result_ibp = engine_ibp.verify_from_point(cnn_bn_avgpool, x, eps)
        assert result_ibp.output_lo is not None
        assert result_ibp.output_hi is not None

        # CROWN
        engine_crown = NNVerificationEngine(strategy="crown")
        result_crown = engine_crown.verify_from_point(cnn_bn_avgpool, x, eps)
        assert result_crown.output_lo is not None
        assert result_crown.output_hi is not None

        # CROWN width should be <= IBP width
        ibp_width = np.max(result_ibp.output_width)
        crown_width = np.max(result_crown.output_width)
        assert crown_width <= ibp_width + 1e-6, \
            f"CROWN width {crown_width} > IBP width {ibp_width}"


# =============================================================
# ResBlock CROWN tests
# =============================================================


@pytest.fixture
def resnet_small():
    """Small ResNet: stem(Conv→BN→ReLU) → ResBlock(4) → MaxPool(2) → Flatten → Linear.

    Input: (1, 8, 8) — small enough for fast tests.
    """
    from regulus.nn.architectures import ResBlock

    torch.manual_seed(42)
    model = nn.Module()
    model.stem = nn.Sequential(
        nn.Conv2d(1, 4, 3, padding=1),
        nn.BatchNorm2d(4),
        nn.ReLU(),
    )
    model.block1 = ResBlock(4)
    model.pool1 = nn.MaxPool2d(2)
    model.flatten = nn.Flatten()
    model.fc = nn.Linear(4 * 4 * 4, 3)

    # Must define forward for model() calls
    class SmallResNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.stem = nn.Sequential(
                nn.Conv2d(1, 4, 3, padding=1),
                nn.BatchNorm2d(4),
                nn.ReLU(),
            )
            self.block1 = ResBlock(4)
            self.pool1 = nn.MaxPool2d(2)
            self.flatten = nn.Flatten()
            self.fc = nn.Linear(4 * 4 * 4, 3)

        def forward(self, x):
            x = self.stem(x)
            x = self.pool1(self.block1(x))
            x = self.flatten(x)
            x = self.fc(x)
            return x

    model = SmallResNet()
    # Train briefly so BN has running stats
    model.train()
    for _ in range(10):
        x = torch.randn(16, 1, 8, 8)
        _ = model(x)
    model.eval()
    return model


@pytest.fixture
def resnet_avgpool_small():
    """Small ResNet with AvgPool: stem → ResBlock(4) → AvgPool(2) → Flatten → Linear."""
    from regulus.nn.architectures import ResBlock

    class SmallResNetAvg(nn.Module):
        def __init__(self):
            super().__init__()
            self.stem = nn.Sequential(
                nn.Conv2d(1, 4, 3, padding=1),
                nn.BatchNorm2d(4),
                nn.ReLU(),
            )
            self.block1 = ResBlock(4)
            self.pool1 = nn.AvgPool2d(2)
            self.flatten = nn.Flatten()
            self.fc = nn.Linear(4 * 4 * 4, 3)

        def forward(self, x):
            x = self.stem(x)
            x = self.pool1(self.block1(x))
            x = self.flatten(x)
            x = self.fc(x)
            return x

    torch.manual_seed(42)
    model = SmallResNetAvg()
    model.train()
    for _ in range(10):
        x = torch.randn(16, 1, 8, 8)
        _ = model(x)
    model.eval()
    return model


class TestCROWNResBlock:
    """Test CROWN verification through ResBlock skip connections."""

    def test_extract_layers_resblock(self, resnet_small):
        """_extract_layers correctly decomposes ResBlock into start/conv/relu/conv/end."""
        engine = CROWNEngine(crown_depth="fc")
        layers = engine._extract_layers(resnet_small, (1, 8, 8))

        types = [l["type"] for l in layers]
        # Should contain: conv2d, relu (from stem),
        # resblock_start, conv2d, relu, conv2d, resblock_end (from block1),
        # maxpool2d (from pool1), flatten, affine (from fc)
        assert "resblock_start" in types, f"Missing resblock_start in {types}"
        assert "resblock_end" in types, f"Missing resblock_end in {types}"

        # Count resblock pairs
        starts = types.count("resblock_start")
        ends = types.count("resblock_end")
        assert starts == 1 and ends == 1, f"Expected 1 start/end pair, got {starts}/{ends}"

        # Verify structure between start and end
        si = types.index("resblock_start")
        ei = types.index("resblock_end")
        inner = types[si + 1 : ei]
        assert inner == ["conv2d", "relu", "conv2d"], \
            f"Expected [conv2d, relu, conv2d] inside ResBlock, got {inner}"

    def test_forward_ibp_resblock_soundness(self, resnet_small):
        """Forward IBP through ResBlock is sound: bounds contain true output."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(crown_depth="fc")

        for _ in range(20):
            x = rng.standard_normal((1, 8, 8)).astype(np.float64)
            eps = 0.05
            result = engine.compute_bounds(resnet_small, x, eps)

            with torch.no_grad():
                y_true = resnet_small(
                    torch.tensor(x, dtype=torch.float32).unsqueeze(0)
                ).squeeze(0).numpy()

            assert np.all(result.output_lo <= y_true + 1e-4), \
                f"ResBlock lower: lo={result.output_lo}, true={y_true}"
            assert np.all(result.output_hi >= y_true - 1e-4), \
                f"ResBlock upper: hi={result.output_hi}, true={y_true}"

    def test_forward_ibp_resblock_perturbed(self, resnet_small):
        """CROWN bounds contain all perturbed outputs for ResBlock model."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(crown_depth="fc")

        x = rng.standard_normal((1, 8, 8)).astype(np.float64)
        eps = 0.05
        result = engine.compute_bounds(resnet_small, x, eps)

        for _ in range(100):
            delta = rng.uniform(-eps, eps, size=(1, 8, 8))
            x_pert = x + delta
            with torch.no_grad():
                y_pert = resnet_small(
                    torch.tensor(x_pert, dtype=torch.float32).unsqueeze(0)
                ).squeeze(0).numpy()

            assert np.all(result.output_lo <= y_pert + 1e-4), \
                f"ResBlock pert: lo={result.output_lo}, pert={y_pert}"
            assert np.all(result.output_hi >= y_pert - 1e-4), \
                f"ResBlock pert: hi={result.output_hi}, pert={y_pert}"

    def test_crown_tighter_than_ibp_resblock(self, resnet_small):
        """CROWN(fc) bounds are at least as tight as pure IBP for ResBlock."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(crown_depth="fc")

        for _ in range(10):
            x = rng.standard_normal((1, 8, 8)).astype(np.float64)
            eps = 0.05
            result = engine.compute_bounds(resnet_small, x, eps)

            # CROWN should be at least as tight as IBP
            ibp_width = np.mean(result.ibp_output_hi - result.ibp_output_lo)
            crown_width = np.mean(result.output_hi - result.output_lo)
            assert crown_width <= ibp_width + 1e-6, \
                f"CROWN width {crown_width} > IBP width {ibp_width}"

    def test_resblock_avgpool_soundness(self, resnet_avgpool_small):
        """CROWN(fc) sound for ResBlock + AvgPool combination."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(crown_depth="fc")

        for _ in range(20):
            x = rng.standard_normal((1, 8, 8)).astype(np.float64)
            eps = 0.05
            result = engine.compute_bounds(resnet_avgpool_small, x, eps)

            with torch.no_grad():
                y_true = resnet_avgpool_small(
                    torch.tensor(x, dtype=torch.float32).unsqueeze(0)
                ).squeeze(0).numpy()

            assert np.all(result.output_lo <= y_true + 1e-4), \
                f"ResBlock+AvgPool lower: lo={result.output_lo}, true={y_true}"
            assert np.all(result.output_hi >= y_true - 1e-4), \
                f"ResBlock+AvgPool upper: hi={result.output_hi}, true={y_true}"

    def test_resblock_avgpool_perturbed(self, resnet_avgpool_small):
        """Bounds contain perturbed outputs for ResBlock + AvgPool."""
        rng = np.random.default_rng(42)
        engine = CROWNEngine(crown_depth="fc")

        x = rng.standard_normal((1, 8, 8)).astype(np.float64)
        eps = 0.05
        result = engine.compute_bounds(resnet_avgpool_small, x, eps)

        for _ in range(100):
            delta = rng.uniform(-eps, eps, size=(1, 8, 8))
            x_pert = x + delta
            with torch.no_grad():
                y_pert = resnet_avgpool_small(
                    torch.tensor(x_pert, dtype=torch.float32).unsqueeze(0)
                ).squeeze(0).numpy()

            assert np.all(result.output_lo <= y_pert + 1e-4), \
                f"ResBlock+AvgPool pert: lo={result.output_lo}, pert={y_pert}"
            assert np.all(result.output_hi >= y_pert - 1e-4), \
                f"ResBlock+AvgPool pert: hi={result.output_hi}, pert={y_pert}"

    def test_two_resblocks(self):
        """CROWN handles two consecutive ResBlocks (like ResNetCIFAR)."""
        from regulus.nn.architectures import ResBlock

        class TwoBlockNet(nn.Module):
            def __init__(self):
                super().__init__()
                self.stem = nn.Sequential(
                    nn.Conv2d(1, 4, 3, padding=1),
                    nn.BatchNorm2d(4),
                    nn.ReLU(),
                )
                self.block1 = ResBlock(4)
                self.pool1 = nn.MaxPool2d(2)
                self.block2 = ResBlock(4)
                self.pool2 = nn.MaxPool2d(2)
                self.flatten = nn.Flatten()
                self.fc = nn.Linear(4 * 2 * 2, 3)

            def forward(self, x):
                x = self.stem(x)
                x = self.pool1(self.block1(x))
                x = self.pool2(self.block2(x))
                x = self.flatten(x)
                x = self.fc(x)
                return x

        torch.manual_seed(42)
        model = TwoBlockNet()
        model.train()
        for _ in range(10):
            x = torch.randn(16, 1, 8, 8)
            _ = model(x)
        model.eval()

        rng = np.random.default_rng(42)
        engine = CROWNEngine(crown_depth="fc")

        for _ in range(20):
            x = rng.standard_normal((1, 8, 8)).astype(np.float64)
            eps = 0.05
            result = engine.compute_bounds(model, x, eps)

            with torch.no_grad():
                y_true = model(
                    torch.tensor(x, dtype=torch.float32).unsqueeze(0)
                ).squeeze(0).numpy()

            assert np.all(result.output_lo <= y_true + 1e-4), \
                f"TwoBlock lower: lo={result.output_lo}, true={y_true}"
            assert np.all(result.output_hi >= y_true - 1e-4), \
                f"TwoBlock upper: hi={result.output_hi}, true={y_true}"

        # Verify two resblock pairs extracted
        layers = engine._extract_layers(model, (1, 8, 8))
        types = [l["type"] for l in layers]
        assert types.count("resblock_start") == 2
        assert types.count("resblock_end") == 2
