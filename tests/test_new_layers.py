"""Tests for CNN interval layers: BatchNorm, Conv2d, Flatten, MaxPool2d, ResBlock."""

import numpy as np
import pytest
import torch
import torch.nn as nn

from regulus.nn.interval_tensor import IntervalTensor


# ============================================================
# IntervalBatchNorm
# ============================================================

class TestIntervalBatchNorm:

    def test_valid_output(self):
        """Output intervals must have lo <= hi."""
        from regulus.nn.layers import IntervalBatchNorm
        bn = nn.BatchNorm1d(4)
        bn.eval()
        bn(torch.randn(10, 4))  # init running stats
        ibn = IntervalBatchNorm.from_torch(bn)
        x = IntervalTensor(np.array([-1.0, 0.0, 0.5, 1.0]),
                           np.array([-0.5, 0.5, 1.0, 1.5]))
        y = ibn(x)
        assert np.all(y.lo <= y.hi + 1e-12)

    def test_contains_point(self):
        """Point evaluation must lie within the interval output."""
        from regulus.nn.layers import IntervalBatchNorm
        bn = nn.BatchNorm1d(4)
        bn.eval()
        bn(torch.randn(10, 4))
        ibn = IntervalBatchNorm.from_torch(bn)

        center = np.array([0.0, 0.5, 1.0, -0.5])
        x_interval = IntervalTensor.from_uncertainty(center, 0.1)
        y = ibn(x_interval)

        bn.eval()
        with torch.no_grad():
            point_out = bn(torch.tensor(center, dtype=torch.float32).unsqueeze(0))
            point_out = point_out.squeeze(0).numpy().astype(np.float64)

        assert np.all(point_out >= y.lo - 1e-6)
        assert np.all(point_out <= y.hi + 1e-6)

    def test_width_shrinks_when_var_large(self):
        """BN with large running_var and gamma=1 should shrink intervals."""
        from regulus.nn.layers import IntervalBatchNorm
        # scale = gamma / sqrt(var + eps) -- large var -> small scale -> shrink
        scale = np.array([0.1, 0.1])
        shift = np.array([0.0, 0.0])
        ibn = IntervalBatchNorm(scale, shift)
        x = IntervalTensor(np.array([-1.0, -1.0]), np.array([1.0, 1.0]))
        y = ibn(x)
        assert y.mean_width() < x.mean_width()

    def test_2d_shape(self):
        """BN2d with (C,H,W) input should produce (C,H,W) output."""
        from regulus.nn.layers import IntervalBatchNorm
        bn = nn.BatchNorm2d(3)
        bn.eval()
        bn(torch.randn(5, 3, 4, 4))
        ibn = IntervalBatchNorm.from_torch(bn)

        np.random.seed(42)
        lo = np.random.randn(3, 4, 4)
        hi = lo + 0.2
        x = IntervalTensor(lo, hi)
        y = ibn(x)
        assert y.shape == (3, 4, 4)
        assert np.all(y.lo <= y.hi + 1e-12)

    def test_negative_scale(self):
        """Negative scale should swap lo and hi."""
        from regulus.nn.layers import IntervalBatchNorm
        scale = np.array([-2.0])
        shift = np.array([0.0])
        ibn = IntervalBatchNorm(scale, shift)
        x = IntervalTensor(np.array([1.0]), np.array([3.0]))
        y = ibn(x)
        # scale=-2: lo = -2*3 = -6, hi = -2*1 = -2
        assert y.lo[0] == pytest.approx(-6.0)
        assert y.hi[0] == pytest.approx(-2.0)


# ============================================================
# IntervalConv2d
# ============================================================

class TestIntervalConv2d:

    def test_valid_output(self):
        """Output intervals must have lo <= hi."""
        from regulus.nn.layers import IntervalConv2d
        torch.manual_seed(42)
        conv = nn.Conv2d(1, 4, 3, padding=1)
        iconv = IntervalConv2d.from_torch(conv)

        np.random.seed(42)
        lo = np.random.randn(1, 8, 8)
        hi = lo + 0.2
        x = IntervalTensor(lo, hi)
        y = iconv(x)
        assert np.all(y.lo <= y.hi + 1e-6)

    def test_contains_point(self):
        """Point evaluation must lie within interval output."""
        from regulus.nn.layers import IntervalConv2d
        torch.manual_seed(42)
        conv = nn.Conv2d(1, 4, 3, padding=1)
        iconv = IntervalConv2d.from_torch(conv)

        np.random.seed(42)
        center = np.random.randn(1, 8, 8)
        x_interval = IntervalTensor.from_uncertainty(center, 0.05)
        y = iconv(x_interval)

        conv.eval()
        with torch.no_grad():
            pt = conv(torch.tensor(center, dtype=torch.float32).unsqueeze(0))
            point_out = pt.squeeze(0).numpy().astype(np.float64)

        assert np.all(point_out >= y.lo - 1e-4)
        assert np.all(point_out <= y.hi + 1e-4)

    def test_output_shape(self):
        """Output shape should match PyTorch conv output shape."""
        from regulus.nn.layers import IntervalConv2d
        conv = nn.Conv2d(1, 16, 3, padding=1)
        iconv = IntervalConv2d.from_torch(conv)

        x = IntervalTensor(np.zeros((1, 28, 28)), np.ones((1, 28, 28)) * 0.01)
        y = iconv(x)
        assert y.shape == (16, 28, 28)

    def test_positive_width(self):
        """All output widths must be non-negative."""
        from regulus.nn.layers import IntervalConv2d
        torch.manual_seed(42)
        conv = nn.Conv2d(3, 8, 3, padding=1)
        iconv = IntervalConv2d.from_torch(conv)

        np.random.seed(42)
        lo = np.random.randn(3, 6, 6)
        x = IntervalTensor(lo, lo + 0.1)
        y = iconv(x)
        assert np.all(y.width >= -1e-10)


# ============================================================
# IntervalFlatten
# ============================================================

class TestIntervalFlatten:

    def test_preserves_bounds(self):
        """Flatten should not change any values, only shape."""
        from regulus.nn.layers import IntervalFlatten
        flat = IntervalFlatten()
        lo = np.array([[[1.0, 2.0], [3.0, 4.0]]])  # (1, 2, 2)
        hi = lo + 0.5
        x = IntervalTensor(lo, hi)
        y = flat(x)
        np.testing.assert_array_equal(y.lo, lo.flatten())
        np.testing.assert_array_equal(y.hi, hi.flatten())

    def test_correct_shape(self):
        """Output should be 1D with product of input dims elements."""
        from regulus.nn.layers import IntervalFlatten
        flat = IntervalFlatten()
        x = IntervalTensor(np.zeros((3, 7, 7)), np.ones((3, 7, 7)) * 0.01)
        y = flat(x)
        assert y.shape == (147,)


# ============================================================
# IntervalMaxPool2d
# ============================================================

class TestIntervalMaxPool2d:

    def test_valid_output(self):
        """Output intervals must have lo <= hi."""
        from regulus.nn.layers import IntervalMaxPool2d
        pool = nn.MaxPool2d(2)
        ipool = IntervalMaxPool2d.from_torch(pool)

        np.random.seed(42)
        lo = np.random.randn(4, 8, 8)
        x = IntervalTensor(lo, lo + 0.3)
        y = ipool(x)
        assert np.all(y.lo <= y.hi + 1e-10)

    def test_contains_point(self):
        """Point evaluation must lie within interval output."""
        from regulus.nn.layers import IntervalMaxPool2d
        import torch.nn.functional as F

        pool = nn.MaxPool2d(2)
        ipool = IntervalMaxPool2d.from_torch(pool)

        np.random.seed(42)
        center = np.random.randn(4, 8, 8).astype(np.float64)
        x_interval = IntervalTensor.from_uncertainty(center, 0.05)
        y = ipool(x_interval)

        with torch.no_grad():
            point_out = F.max_pool2d(
                torch.tensor(center).unsqueeze(0), 2
            ).squeeze(0).numpy()

        assert np.all(point_out >= y.lo - 1e-6)
        assert np.all(point_out <= y.hi + 1e-6)

    def test_output_shape(self):
        """MaxPool2d(2) should halve spatial dims."""
        from regulus.nn.layers import IntervalMaxPool2d
        ipool = IntervalMaxPool2d(kernel_size=2, stride=2)
        x = IntervalTensor(np.zeros((4, 8, 8)), np.ones((4, 8, 8)) * 0.01)
        y = ipool(x)
        assert y.shape == (4, 4, 4)


# ============================================================
# Integration tests
# ============================================================

class TestIntegration:

    def test_cnn_forward(self):
        """Full CNN+BN forward should produce shape (10,) with valid intervals."""
        from regulus.nn.architectures import make_cnn_bn
        from regulus.nn.model import convert_model

        torch.manual_seed(42)
        model = make_cnn_bn()
        model.eval()
        model(torch.randn(2, 1, 28, 28))  # init BN stats

        imodel = convert_model(model)
        np.random.seed(42)
        x = IntervalTensor.from_uncertainty(np.random.randn(1, 28, 28) * 0.1, 0.01)
        y = imodel(x)
        assert y.shape == (10,)
        assert np.all(y.lo <= y.hi + 1e-6)

    def test_resblock_forward(self):
        """ResBlock should preserve shape and produce valid intervals."""
        from regulus.nn.architectures import ResBlock, IntervalResBlock

        torch.manual_seed(42)
        block = ResBlock(8)
        block.eval()
        block(torch.randn(2, 8, 4, 4))  # init BN stats

        iblock = IntervalResBlock.from_torch(block)
        np.random.seed(42)
        x = IntervalTensor.from_uncertainty(np.random.randn(8, 4, 4) * 0.1, 0.01)
        y = iblock(x)
        assert y.shape == (8, 4, 4)
        assert np.all(y.lo <= y.hi + 1e-6)

    def test_resnet_convert(self):
        """ResNetMNIST should convert and produce shape (10,) output."""
        from regulus.nn.architectures import ResNetMNIST
        from regulus.nn.model import convert_model

        torch.manual_seed(42)
        model = ResNetMNIST()
        model.eval()
        model(torch.randn(2, 1, 28, 28))  # init BN stats

        imodel = convert_model(model)
        np.random.seed(42)
        x = IntervalTensor.from_uncertainty(np.random.randn(1, 28, 28) * 0.1, 0.01)
        y = imodel(x)
        assert y.shape == (10,)
        assert np.all(y.lo <= y.hi + 1e-6)

    def test_existing_mlp_still_works(self):
        """Regression: existing MLP convert_model should still work."""
        from regulus.nn.model import convert_model

        model = nn.Sequential(
            nn.Linear(10, 5), nn.ReLU(),
            nn.Linear(5, 3),
        )
        imodel = convert_model(model)
        np.random.seed(42)
        x = IntervalTensor.from_uncertainty(np.random.randn(10), 0.01)
        y = imodel(x)
        assert y.shape == (3,)
        assert np.all(y.lo <= y.hi + 1e-6)


# ============================================================
# ResBlock Soundness (Coq-backed: pi_residual_correct,
#                     pi_resblock_width_bound)
# ============================================================

class TestResBlockSoundness:
    """Verify ResBlock interval propagation matches Coq-proven properties.

    Coq theorems (PInterval_Composition.v, Section 6):
      - pi_residual_correct: containment of x + f(x)
      - pi_residual_width: width(residual) = width(input) + width(sub)
      - pi_resblock_width_bound: width(relu(residual)) ≤ width(input) + width(sub)
      - pi_resblock_width_with_factor: width bound with explicit factor
    """

    def test_resblock_containment_soundness(self):
        """Point evaluations must lie within interval bounds (50 random points).

        Coq backing: pi_residual_correct + pi_relu_correct.
        """
        from regulus.nn.architectures import ResBlock, IntervalResBlock

        torch.manual_seed(42)
        block = ResBlock(4)
        block.eval()
        block(torch.randn(2, 4, 4, 4))  # init BN stats

        iblock = IntervalResBlock.from_torch(block)

        eps = 0.01
        rng = np.random.RandomState(42)
        center = rng.randn(4, 4, 4).astype(np.float64) * 0.1
        x_interval = IntervalTensor.from_uncertainty(center, eps)
        y_interval = iblock(x_interval)

        violations = 0
        for trial in range(50):
            # Sample a random point inside the input interval
            t = rng.uniform(0, 1, size=center.shape)
            point = x_interval.lo + t * (x_interval.hi - x_interval.lo)

            with torch.no_grad():
                pt_tensor = torch.tensor(point, dtype=torch.float32).unsqueeze(0)
                pt_out = block(pt_tensor).squeeze(0).numpy().astype(np.float64)

            lo_ok = np.all(pt_out >= y_interval.lo - 1e-5)
            hi_ok = np.all(pt_out <= y_interval.hi + 1e-5)
            if not (lo_ok and hi_ok):
                violations += 1

        assert violations == 0, f"Containment violated in {violations}/50 trials"

    def test_resblock_width_additive(self):
        """Width(output) ≤ width(input) + width(sub_network_output).

        Coq backing: pi_resblock_width_bound.
        The ResBlock applies relu(x + g(x)), and:
          width(relu(x + g(x))) ≤ width(x + g(x)) = width(x) + width(g(x))
        """
        from regulus.nn.architectures import ResBlock, IntervalResBlock

        torch.manual_seed(123)
        block = ResBlock(4)
        block.eval()
        block(torch.randn(2, 4, 4, 4))  # init BN stats

        iblock = IntervalResBlock.from_torch(block)

        np.random.seed(123)
        center = np.random.randn(4, 4, 4).astype(np.float64) * 0.1
        eps = 0.02
        x_interval = IntervalTensor.from_uncertainty(center, eps)

        # Compute sub-network output (inner path g(x)) separately
        g = x_interval
        for layer in iblock.inner_layers:
            g = layer(g)

        # The residual sum before relu: x + g(x)
        summed = IntervalTensor(x_interval.lo + g.lo, x_interval.hi + g.hi)

        # Final output: relu(x + g(x))
        y = summed.relu()

        # Verify: width(y) <= width(x) + width(g) elementwise
        input_width = x_interval.width
        sub_width = g.width
        output_width = y.width

        assert np.all(output_width <= input_width + sub_width + 1e-10), (
            f"Width bound violated: max excess = "
            f"{np.max(output_width - input_width - sub_width)}"
        )

    def test_resblock_relu_doesnt_increase_width(self):
        """relu doesn't increase width of the residual sum.

        Coq backing: pi_relu_width_bound.
        """
        from regulus.nn.architectures import ResBlock, IntervalResBlock

        torch.manual_seed(99)
        block = ResBlock(4)
        block.eval()
        block(torch.randn(2, 4, 4, 4))  # init BN stats

        iblock = IntervalResBlock.from_torch(block)

        np.random.seed(99)
        center = np.random.randn(4, 4, 4).astype(np.float64) * 0.1
        x_interval = IntervalTensor.from_uncertainty(center, 0.01)

        # Compute inner path
        g = x_interval
        for layer in iblock.inner_layers:
            g = layer(g)

        # Residual sum
        summed = IntervalTensor(x_interval.lo + g.lo, x_interval.hi + g.hi)

        # Apply relu
        after_relu = summed.relu()

        # width(relu(z)) <= width(z)
        assert np.all(after_relu.width <= summed.width + 1e-10)

    def test_resblock_factor_formula(self):
        """If width(g(x)) ≤ f * width(x), then width(resblock) ≤ (1+f) * width(x).

        Coq backing: pi_resblock_width_with_factor.
        """
        from regulus.nn.architectures import ResBlock, IntervalResBlock

        torch.manual_seed(77)
        block = ResBlock(4)
        block.eval()
        block(torch.randn(2, 4, 4, 4))

        iblock = IntervalResBlock.from_torch(block)

        np.random.seed(77)
        center = np.random.randn(4, 4, 4).astype(np.float64) * 0.1
        eps = 0.01
        x_interval = IntervalTensor.from_uncertainty(center, eps)

        # Compute inner path g(x)
        g = x_interval
        for layer in iblock.inner_layers:
            g = layer(g)

        # Compute empirical factor: max(width(g(x)) / width(x))
        input_width = x_interval.width
        sub_width = g.width
        # Avoid division by zero
        nonzero = input_width > 1e-15
        if np.any(nonzero):
            f_factor = np.max(sub_width[nonzero] / input_width[nonzero])
        else:
            f_factor = 0.0

        # Compute full output
        y = iblock(x_interval)
        output_width = y.width

        # Verify: width(output) <= (1 + f_factor) * width(input) + tolerance
        bound = (1 + f_factor) * input_width
        assert np.all(output_width <= bound + 1e-10), (
            f"Factor bound violated: max excess = "
            f"{np.max(output_width - bound)}"
        )


# ============================================================
# IntervalTanh (Coq: pi_monotone_correct)
# ============================================================

class TestIntervalTanh:

    def test_containment_soundness(self):
        """Random points within input must produce outputs within bounds."""
        from regulus.nn.layers import IntervalTanh
        itanh = IntervalTanh()
        rng = np.random.RandomState(42)
        violations = 0
        for _ in range(50):
            center = rng.randn(20) * 2.0
            eps = rng.uniform(0.01, 0.5)
            x = IntervalTensor.from_uncertainty(center, eps)
            y = itanh(x)
            # Sample random point in interval
            t = rng.uniform(0, 1, size=center.shape)
            point = x.lo + t * (x.hi - x.lo)
            expected = np.tanh(point)
            if not (np.all(expected >= y.lo - 1e-10) and np.all(expected <= y.hi + 1e-10)):
                violations += 1
        assert violations == 0, f"Containment violated in {violations}/50 trials"

    def test_valid_output(self):
        """Output intervals must have lo <= hi."""
        x = IntervalTensor(np.array([-3.0, -1.0, 0.0, 1.0]),
                           np.array([-1.0,  1.0, 2.0, 5.0]))
        y = x.tanh()
        assert np.all(y.lo <= y.hi + 1e-12)

    def test_point_exactness(self):
        """Point intervals: tanh([a,a]) = [tanh(a), tanh(a)]."""
        vals = np.array([0.0, 1.0, -1.0, 5.0, -5.0])
        x = IntervalTensor.from_exact(vals)
        y = x.tanh()
        np.testing.assert_allclose(y.lo, np.tanh(vals), atol=1e-12)
        np.testing.assert_allclose(y.hi, np.tanh(vals), atol=1e-12)

    def test_width_contraction(self):
        """Tanh is Lipschitz-1: width(tanh(I)) <= width(I)."""
        rng = np.random.RandomState(42)
        for _ in range(20):
            lo = rng.randn(10) * 3.0
            hi = lo + rng.uniform(0.01, 2.0, size=10)
            x = IntervalTensor(lo, hi)
            y = x.tanh()
            assert np.all(y.width <= x.width + 1e-10)

    def test_output_in_minus1_1(self):
        """Tanh output must be in [-1, 1]."""
        x = IntervalTensor(np.array([-100.0, 0.0]), np.array([100.0, 50.0]))
        y = x.tanh()
        assert np.all(y.lo >= -1.0 - 1e-10)
        assert np.all(y.hi <= 1.0 + 1e-10)

    def test_convert_model_with_tanh(self):
        """convert_model should handle nn.Tanh."""
        from regulus.nn.model import convert_model
        model = nn.Sequential(nn.Linear(10, 5), nn.Tanh(), nn.Linear(5, 3))
        imodel = convert_model(model)
        x = IntervalTensor.from_uncertainty(np.random.randn(10), 0.01)
        y = imodel(x)
        assert y.shape == (3,)
        assert np.all(y.lo <= y.hi + 1e-6)


# ============================================================
# IntervalGELU (conservative bounds, non-monotone)
# ============================================================

class TestIntervalGELU:

    def test_containment_soundness(self):
        """Random points within input must produce outputs within bounds."""
        from math import erf as _erf
        import math
        from regulus.nn.layers import IntervalGELU
        igelu = IntervalGELU()
        rng = np.random.RandomState(42)

        def _np_gelu(x):
            _verf = np.vectorize(lambda v: _erf(v / math.sqrt(2.0)))
            return 0.5 * x * (1.0 + _verf(x))

        violations = 0
        for _ in range(100):
            center = rng.randn(20) * 2.0
            eps = rng.uniform(0.01, 0.5)
            x = IntervalTensor.from_uncertainty(center, eps)
            y = igelu(x)
            # Sample random point
            t = rng.uniform(0, 1, size=center.shape)
            point = x.lo + t * (x.hi - x.lo)
            expected = _np_gelu(point)
            lo_ok = np.all(expected >= y.lo - 1e-8)
            hi_ok = np.all(expected <= y.hi + 1e-8)
            if not (lo_ok and hi_ok):
                violations += 1
        assert violations == 0, f"GELU containment violated in {violations}/100 trials"

    def test_valid_output(self):
        """Output intervals must have lo <= hi."""
        x = IntervalTensor(np.array([-3.0, -1.0, -0.2, 0.0, 1.0]),
                           np.array([-0.5,  1.0,  0.5, 2.0, 5.0]))
        y = x.gelu()
        assert np.all(y.lo <= y.hi + 1e-10)

    def test_point_exactness(self):
        """Point intervals: gelu([a,a]) ~ [gelu(a), gelu(a)]."""
        from math import erf as _erf
        import math
        vals = np.array([0.0, 1.0, -1.0, 2.0, -0.5])
        x = IntervalTensor.from_exact(vals)
        y = x.gelu()
        expected = np.array([0.5 * v * (1.0 + _erf(v / math.sqrt(2.0))) for v in vals])
        np.testing.assert_allclose(y.lo, expected, atol=1e-10)
        np.testing.assert_allclose(y.hi, expected, atol=1e-10)

    def test_non_monotone_region(self):
        """Interval crossing GELU minimum must include negative values."""
        x = IntervalTensor(np.array([-1.0]), np.array([1.0]))
        y = x.gelu()
        assert y.lo[0] < 0, "Must include GELU minimum (negative)"
        assert y.hi[0] > 0, "Must include positive region"

    def test_monotone_positive_region(self):
        """Fully positive interval: GELU is monotone, tight bounds."""
        x = IntervalTensor(np.array([1.0]), np.array([2.0]))
        y = x.gelu()
        from math import erf as _erf
        import math
        g1 = 0.5 * 1.0 * (1.0 + _erf(1.0 / math.sqrt(2.0)))
        g2 = 0.5 * 2.0 * (1.0 + _erf(2.0 / math.sqrt(2.0)))
        assert abs(y.lo[0] - g1) < 1e-10
        assert abs(y.hi[0] - g2) < 1e-10

    def test_convert_model_with_gelu(self):
        """convert_model should handle nn.GELU."""
        from regulus.nn.model import convert_model
        model = nn.Sequential(nn.Linear(10, 5), nn.GELU(), nn.Linear(5, 3))
        imodel = convert_model(model)
        x = IntervalTensor.from_uncertainty(np.random.randn(10), 0.01)
        y = imodel(x)
        assert y.shape == (3,)
        assert np.all(y.lo <= y.hi + 1e-6)


# ============================================================
# IntervalELU (Coq: pi_monotone_correct)
# ============================================================

class TestIntervalELU:

    def test_containment_soundness(self):
        """Random points within input must produce outputs within bounds."""
        from regulus.nn.layers import IntervalELU
        ielu = IntervalELU(alpha=1.0)
        rng = np.random.RandomState(42)

        def _np_elu(x, alpha=1.0):
            return np.where(x >= 0, x, alpha * (np.exp(x) - 1.0))

        violations = 0
        for _ in range(50):
            center = rng.randn(20) * 2.0
            eps = rng.uniform(0.01, 0.5)
            x = IntervalTensor.from_uncertainty(center, eps)
            y = ielu(x)
            t = rng.uniform(0, 1, size=center.shape)
            point = x.lo + t * (x.hi - x.lo)
            expected = _np_elu(point)
            lo_ok = np.all(expected >= y.lo - 1e-10)
            hi_ok = np.all(expected <= y.hi + 1e-10)
            if not (lo_ok and hi_ok):
                violations += 1
        assert violations == 0, f"ELU containment violated in {violations}/50 trials"

    def test_valid_output(self):
        """Output intervals must have lo <= hi."""
        x = IntervalTensor(np.array([-3.0, -1.0, 0.0, 1.0]),
                           np.array([-1.0,  1.0, 2.0, 5.0]))
        y = x.elu()
        assert np.all(y.lo <= y.hi + 1e-12)

    def test_point_exactness(self):
        """Point intervals: elu([a,a]) = [elu(a), elu(a)]."""
        vals = np.array([0.0, 1.0, -1.0, 3.0, -3.0])
        x = IntervalTensor.from_exact(vals)
        y = x.elu()
        expected = np.where(vals >= 0, vals, np.exp(vals) - 1.0)
        np.testing.assert_allclose(y.lo, expected, atol=1e-10)
        np.testing.assert_allclose(y.hi, expected, atol=1e-10)

    def test_custom_alpha(self):
        """ELU with alpha=2.0 should scale negative region."""
        from regulus.nn.layers import IntervalELU
        ielu = IntervalELU(alpha=2.0)
        x = IntervalTensor(np.array([-2.0]), np.array([-1.0]))
        y = ielu(x)
        expected_lo = 2.0 * (np.exp(-2.0) - 1.0)
        expected_hi = 2.0 * (np.exp(-1.0) - 1.0)
        assert abs(y.lo[0] - expected_lo) < 1e-10
        assert abs(y.hi[0] - expected_hi) < 1e-10

    def test_positive_region_identity(self):
        """ELU is identity for positive inputs."""
        x = IntervalTensor(np.array([1.0, 2.0]), np.array([3.0, 4.0]))
        y = x.elu()
        np.testing.assert_allclose(y.lo, x.lo, atol=1e-12)
        np.testing.assert_allclose(y.hi, x.hi, atol=1e-12)

    def test_convert_model_with_elu(self):
        """convert_model should handle nn.ELU."""
        from regulus.nn.model import convert_model
        model = nn.Sequential(nn.Linear(10, 5), nn.ELU(), nn.Linear(5, 3))
        imodel = convert_model(model)
        x = IntervalTensor.from_uncertainty(np.random.randn(10), 0.01)
        y = imodel(x)
        assert y.shape == (3,)
        assert np.all(y.lo <= y.hi + 1e-6)
