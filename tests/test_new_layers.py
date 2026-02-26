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
