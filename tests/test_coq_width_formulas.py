"""
Cross-validation tests: verify Python implementations match Coq-proven width formulas.

Each test corresponds to a theorem in ToS-Coq/PInterval_Conv.v:
  - pi_affine_width:      width(BN(x)) == |scale| * width(x)
  - pi_conv_pixel_width:  width(conv) == weighted_width_sum
  - pi_conv_bn_relu_width_bound:
      width(relu(bn(conv(x)))) <= |bn_scale| * eps * ||kernel||_1
  - pi_relu_width_bound:  width(relu(x)) <= width(x)
  - pi_affine_correct:    bn(x) contains the true point output
  - pi_conv_pixel_correct: conv output contains true dot product + bias
"""

from __future__ import annotations

import numpy as np
import pytest

from regulus.nn.interval_tensor import IntervalTensor
from regulus.nn.layers import IntervalBatchNorm, IntervalReLU


class TestAffineWidth:
    """Mirrors pi_affine_width: width(affine(w,x,b)) == |w| * width(x)."""

    def test_positive_scale(self):
        scale = np.array([2.0, 0.5, 1.0])
        shift = np.array([1.0, -3.0, 0.0])
        bn = IntervalBatchNorm(scale, shift)
        x = IntervalTensor(np.array([-1.0, 0.0, 0.5]),
                           np.array([1.0, 0.5, 1.5]))
        y = bn(x)
        expected_width = np.abs(scale) * (x.hi - x.lo)
        np.testing.assert_allclose(y.hi - y.lo, expected_width, atol=1e-12)

    def test_negative_scale(self):
        scale = np.array([-3.0, -0.5])
        shift = np.array([0.0, 1.0])
        bn = IntervalBatchNorm(scale, shift)
        x = IntervalTensor(np.array([1.0, 2.0]), np.array([4.0, 5.0]))
        y = bn(x)
        expected_width = np.abs(scale) * (x.hi - x.lo)
        np.testing.assert_allclose(y.hi - y.lo, expected_width, atol=1e-12)

    def test_mixed_scale(self):
        scale = np.array([2.0, -1.5, 0.0, 0.7])
        shift = np.array([0.0, 0.0, 0.0, 0.0])
        bn = IntervalBatchNorm(scale, shift)
        x = IntervalTensor(np.array([-1.0, -2.0, 3.0, 0.0]),
                           np.array([1.0, 2.0, 5.0, 1.0]))
        y = bn(x)
        expected_width = np.abs(scale) * (x.hi - x.lo)
        np.testing.assert_allclose(y.hi - y.lo, expected_width, atol=1e-12)

    def test_shift_does_not_affect_width(self):
        """pi_point_width: shift contributes 0 width."""
        scale = np.array([1.5])
        x = IntervalTensor(np.array([0.0]), np.array([2.0]))
        y1 = IntervalBatchNorm(scale, np.array([0.0]))(x)
        y2 = IntervalBatchNorm(scale, np.array([100.0]))(x)
        np.testing.assert_allclose(y1.hi - y1.lo, y2.hi - y2.lo, atol=1e-12)


class TestAffineCorrectness:
    """Mirrors pi_affine_correct: x in I => w*x+b in affine(w,I,b)."""

    def test_containment(self):
        scale = np.array([2.0, -0.5])
        shift = np.array([1.0, 3.0])
        bn = IntervalBatchNorm(scale, shift)
        x = IntervalTensor(np.array([1.0, 2.0]), np.array([3.0, 5.0]))
        y = bn(x)
        # Check 100 random points
        rng = np.random.RandomState(42)
        for _ in range(100):
            v = x.lo + rng.random(2) * (x.hi - x.lo)
            result = scale * v + shift
            assert np.all(result >= y.lo - 1e-12), \
                f"Point {result} below lo {y.lo}"
            assert np.all(result <= y.hi + 1e-12), \
                f"Point {result} above hi {y.hi}"


class TestConvPixelWidth:
    """Mirrors pi_conv_pixel_width:
    width(conv_pixel) == weighted_width_sum(kernel, patch)."""

    def _weighted_width_sum(self, ws, patch_lo, patch_hi):
        """Compute sum(|w_i| * width(patch_i))."""
        widths = patch_hi - patch_lo
        return np.sum(np.abs(ws) * widths)

    def test_1d_conv_pixel(self):
        """Single conv output pixel = dot(kernel, patch) + bias."""
        kernel = np.array([0.5, -0.3, 0.8])
        bias = 0.1
        patch_lo = np.array([1.0, 2.0, 3.0])
        patch_hi = np.array([1.5, 2.5, 3.5])

        # Compute interval output using pos/neg decomposition
        k_pos = np.maximum(kernel, 0)
        k_neg = np.minimum(kernel, 0)
        out_lo = np.dot(k_pos, patch_lo) + np.dot(k_neg, patch_hi) + bias
        out_hi = np.dot(k_pos, patch_hi) + np.dot(k_neg, patch_lo) + bias

        out_width = out_hi - out_lo
        expected_width = self._weighted_width_sum(kernel, patch_lo, patch_hi)
        np.testing.assert_allclose(out_width, expected_width, atol=1e-12)

    def test_zero_kernel(self):
        """Zero kernel produces zero output width."""
        kernel = np.array([0.0, 0.0, 0.0])
        patch_lo = np.array([1.0, 2.0, 3.0])
        patch_hi = np.array([2.0, 3.0, 4.0])

        k_pos = np.maximum(kernel, 0)
        k_neg = np.minimum(kernel, 0)
        out_lo = np.dot(k_pos, patch_lo) + np.dot(k_neg, patch_hi)
        out_hi = np.dot(k_pos, patch_hi) + np.dot(k_neg, patch_lo)

        assert abs(out_hi - out_lo) < 1e-12

    def test_uniform_width_bound(self):
        """pi_conv_pixel_width_uniform_bound:
        if all widths <= eps, then output width <= eps * l1_norm(kernel)."""
        kernel = np.array([1.0, -2.0, 0.5, -0.3])
        eps = 0.1
        n = len(kernel)
        rng = np.random.RandomState(42)
        centers = rng.randn(n)
        widths = rng.random(n) * eps  # all widths <= eps
        patch_lo = centers - widths / 2
        patch_hi = centers + widths / 2

        k_pos = np.maximum(kernel, 0)
        k_neg = np.minimum(kernel, 0)
        out_lo = np.dot(k_pos, patch_lo) + np.dot(k_neg, patch_hi)
        out_hi = np.dot(k_pos, patch_hi) + np.dot(k_neg, patch_lo)

        out_width = out_hi - out_lo
        l1_norm = np.sum(np.abs(kernel))
        assert out_width <= eps * l1_norm + 1e-12, \
            f"Width {out_width} > eps * l1_norm = {eps * l1_norm}"


class TestConvPixelCorrectness:
    """Mirrors pi_conv_pixel_correct: dot(ws, vs) + b in conv_pixel(ws, patch, b)."""

    def test_containment(self):
        kernel = np.array([0.5, -0.3, 0.8, -1.2])
        bias = 0.5
        rng = np.random.RandomState(42)
        patch_lo = rng.randn(4)
        patch_hi = patch_lo + rng.random(4) * 0.5

        k_pos = np.maximum(kernel, 0)
        k_neg = np.minimum(kernel, 0)
        out_lo = np.dot(k_pos, patch_lo) + np.dot(k_neg, patch_hi) + bias
        out_hi = np.dot(k_pos, patch_hi) + np.dot(k_neg, patch_lo) + bias

        for _ in range(200):
            v = patch_lo + rng.random(4) * (patch_hi - patch_lo)
            result = np.dot(kernel, v) + bias
            assert result >= out_lo - 1e-10, \
                f"Point {result} < lo {out_lo}"
            assert result <= out_hi + 1e-10, \
                f"Point {result} > hi {out_hi}"


class TestReluWidthBound:
    """Mirrors pi_relu_width_bound: width(relu(x)) <= width(x)."""

    def test_mixed_intervals(self):
        x = IntervalTensor(np.array([-2.0, -1.0, 0.0, 1.0, -3.0]),
                           np.array([3.0, 0.0, 2.0, 4.0, -1.0]))
        y = x.relu()
        x_width = x.hi - x.lo
        y_width = y.hi - y.lo
        assert np.all(y_width <= x_width + 1e-12), \
            f"ReLU increased width: {y_width} > {x_width}"

    def test_all_positive(self):
        """When all positive, relu is identity: width unchanged."""
        x = IntervalTensor(np.array([1.0, 2.0]), np.array([3.0, 5.0]))
        y = x.relu()
        np.testing.assert_allclose(y.hi - y.lo, x.hi - x.lo, atol=1e-12)

    def test_all_negative(self):
        """When all negative, relu collapses to [0,0]: width = 0."""
        x = IntervalTensor(np.array([-3.0, -5.0]), np.array([-1.0, -2.0]))
        y = x.relu()
        np.testing.assert_allclose(y.hi - y.lo, 0.0, atol=1e-12)


class TestConvBnReluChain:
    """Mirrors pi_conv_bn_relu_width_bound:
    width(relu(bn(conv(x)))) <= |bn_scale| * eps * ||kernel||_1."""

    def test_chain_bound(self):
        """End-to-end: conv pixel -> bn -> relu, check width bound."""
        kernel = np.array([0.5, -0.3, 0.8, -1.2, 0.4])
        conv_bias = 0.1
        bn_scale = np.array([0.7])
        bn_shift = np.array([-0.2])
        eps = 0.1

        # Create patch with widths <= eps
        rng = np.random.RandomState(42)
        n = len(kernel)
        centers = rng.randn(n)
        widths = rng.random(n) * eps
        patch_lo = centers - widths / 2
        patch_hi = centers + widths / 2

        # Conv pixel
        k_pos = np.maximum(kernel, 0)
        k_neg = np.minimum(kernel, 0)
        conv_lo = np.dot(k_pos, patch_lo) + np.dot(k_neg, patch_hi) + conv_bias
        conv_hi = np.dot(k_pos, patch_hi) + np.dot(k_neg, patch_lo) + conv_bias

        # BN (affine)
        s = bn_scale[0]
        b = bn_shift[0]
        if s >= 0:
            bn_lo = s * conv_lo + b
            bn_hi = s * conv_hi + b
        else:
            bn_lo = s * conv_hi + b
            bn_hi = s * conv_lo + b

        # ReLU
        relu_lo = max(0.0, bn_lo)
        relu_hi = max(0.0, bn_hi)

        out_width = relu_hi - relu_lo
        l1_norm = np.sum(np.abs(kernel))
        bound = abs(s) * eps * l1_norm

        assert out_width <= bound + 1e-10, \
            f"Width {out_width} > bound {bound}"

    def test_chain_bound_negative_scale(self):
        """BN with negative scale (flips bounds)."""
        kernel = np.array([1.0, -0.5, 0.3])
        conv_bias = 0.0
        bn_scale_val = -2.0
        bn_shift_val = 1.0
        eps = 0.05

        n = len(kernel)
        rng = np.random.RandomState(123)
        centers = rng.randn(n) * 0.5
        widths = np.full(n, eps)
        patch_lo = centers - widths / 2
        patch_hi = centers + widths / 2

        k_pos = np.maximum(kernel, 0)
        k_neg = np.minimum(kernel, 0)
        conv_lo = np.dot(k_pos, patch_lo) + np.dot(k_neg, patch_hi) + conv_bias
        conv_hi = np.dot(k_pos, patch_hi) + np.dot(k_neg, patch_lo) + conv_bias

        # Negative scale flips
        bn_lo = bn_scale_val * conv_hi + bn_shift_val
        bn_hi = bn_scale_val * conv_lo + bn_shift_val

        relu_lo = max(0.0, bn_lo)
        relu_hi = max(0.0, bn_hi)

        out_width = relu_hi - relu_lo
        l1_norm = np.sum(np.abs(kernel))
        bound = abs(bn_scale_val) * eps * l1_norm

        assert out_width <= bound + 1e-10, \
            f"Width {out_width} > bound {bound}"
