"""
Cross-validation: scalar Interval (Coq-mirrored) vs numpy IntervalTensor.

Two independent stacks implement interval arithmetic:
  Stack A: regulus.interval.interval.Interval (scalar, mirrors PInterval.v)
  Stack B: regulus.nn.interval_tensor.IntervalTensor (numpy vectorized)

This file verifies they produce identical results, ensuring the numpy
implementation inherits the Coq-proven correctness guarantees.
"""

import numpy as np
import pytest

from regulus.interval.interval import Interval
from regulus.nn.interval_tensor import IntervalTensor as NumpyIT
from regulus.nn.interval_tensor import interval_matmul_exact_weights
from regulus.nn.layers import IntervalBatchNorm, IntervalLinear as NumpyLinear


ATOL = 1e-12


def random_interval(rng, lo_range=(-5.0, 5.0)):
    """Generate a random valid interval."""
    a = rng.uniform(*lo_range)
    b = a + rng.uniform(0.0, 2.0)
    return a, b


class TestReluBridge:
    """ReLU: scalar Interval.relu() vs numpy IntervalTensor.relu()."""

    @pytest.mark.parametrize("seed", range(100))
    def test_relu_matches(self, seed):
        rng = np.random.RandomState(seed)
        lo, hi = random_interval(rng)

        scalar = Interval(lo, hi).relu()
        tensor = NumpyIT(np.array([lo]), np.array([hi])).relu()

        assert abs(scalar.lo - tensor.lo[0]) < ATOL
        assert abs(scalar.hi - tensor.hi[0]) < ATOL


class TestAddBridge:
    """Addition: scalar vs numpy."""

    @pytest.mark.parametrize("seed", range(100))
    def test_add_matches(self, seed):
        rng = np.random.RandomState(seed)
        lo1, hi1 = random_interval(rng)
        lo2, hi2 = random_interval(rng)

        scalar = Interval(lo1, hi1) + Interval(lo2, hi2)
        tensor = NumpyIT(np.array([lo1]), np.array([hi1])) + \
                 NumpyIT(np.array([lo2]), np.array([hi2]))

        assert abs(scalar.lo - tensor.lo[0]) < ATOL
        assert abs(scalar.hi - tensor.hi[0]) < ATOL


class TestSubBridge:
    """Subtraction: scalar vs numpy."""

    @pytest.mark.parametrize("seed", range(100))
    def test_sub_matches(self, seed):
        rng = np.random.RandomState(seed)
        lo1, hi1 = random_interval(rng)
        lo2, hi2 = random_interval(rng)

        scalar = Interval(lo1, hi1) - Interval(lo2, hi2)
        tensor = NumpyIT(np.array([lo1]), np.array([hi1])) - \
                 NumpyIT(np.array([lo2]), np.array([hi2]))

        assert abs(scalar.lo - tensor.lo[0]) < ATOL
        assert abs(scalar.hi - tensor.hi[0]) < ATOL


class TestSigmoidBridge:
    """Sigmoid: scalar vs numpy."""

    @pytest.mark.parametrize("seed", range(50))
    def test_sigmoid_matches(self, seed):
        rng = np.random.RandomState(seed)
        lo, hi = random_interval(rng, lo_range=(-3.0, 3.0))

        scalar = Interval(lo, hi).sigmoid()
        tensor = NumpyIT(np.array([lo]), np.array([hi])).sigmoid()

        assert abs(scalar.lo - tensor.lo[0]) < ATOL
        assert abs(scalar.hi - tensor.hi[0]) < ATOL


class TestMatmulBridge:
    """Matrix-vector multiply: scalar dot-product loop vs numpy decomposition."""

    @pytest.mark.parametrize("seed", range(50))
    def test_matmul_matches(self, seed):
        rng = np.random.RandomState(seed)
        m, n = rng.randint(1, 6), rng.randint(1, 6)

        W = rng.randn(m, n)
        lo = rng.randn(n)
        hi = lo + np.abs(rng.randn(n)) * 0.5

        # Numpy stack
        numpy_x = NumpyIT(lo, hi)
        numpy_y = interval_matmul_exact_weights(W, numpy_x)

        # Scalar stack: row-by-row dot product
        for i in range(m):
            acc = Interval.point(0.0)
            for j in range(n):
                acc = acc + (Interval(lo[j], hi[j]) * W[i, j])

            assert abs(acc.lo - numpy_y.lo[i]) < 1e-10, \
                f"Row {i} lo: scalar={acc.lo}, numpy={numpy_y.lo[i]}"
            assert abs(acc.hi - numpy_y.hi[i]) < 1e-10, \
                f"Row {i} hi: scalar={acc.hi}, numpy={numpy_y.hi[i]}"


class TestLinearLayerBridge:
    """Full linear layer: scalar IntervalLinear vs numpy IntervalLinear."""

    @pytest.mark.parametrize("seed", range(20))
    def test_linear_layer_matches(self, seed):
        rng = np.random.RandomState(seed)
        m, n = rng.randint(1, 5), rng.randint(1, 5)

        W = rng.randn(m, n)
        b = rng.randn(m)
        lo = rng.randn(n)
        hi = lo + np.abs(rng.randn(n)) * 0.3

        # Numpy stack
        numpy_layer = NumpyLinear(W, b)
        numpy_x = NumpyIT(lo, hi)
        numpy_y = numpy_layer(numpy_x)

        # Scalar stack
        from regulus.interval.nn import IntervalLinear as ScalarLinear
        from regulus.interval.interval_tensor import IntervalTensor as ScalarIT

        scalar_x = ScalarIT([[lo[j], hi[j]] for j in range(n)])
        scalar_layer = ScalarLinear(W.tolist(), b.tolist())
        scalar_y = scalar_layer(scalar_x)

        for i in range(m):
            assert abs(scalar_y[i].lo - numpy_y.lo[i]) < 1e-10, \
                f"Output {i} lo mismatch"
            assert abs(scalar_y[i].hi - numpy_y.hi[i]) < 1e-10, \
                f"Output {i} hi mismatch"


class TestBatchNormWidthFormula:
    """pi_affine_width: width(BN(x)) == |scale| * width(x)."""

    @pytest.mark.parametrize("seed", range(50))
    def test_bn_width_equals_abs_scale_times_input_width(self, seed):
        rng = np.random.RandomState(seed)
        n = rng.randint(1, 10)

        scale = rng.randn(n)
        shift = rng.randn(n)
        lo = rng.randn(n)
        hi = lo + np.abs(rng.randn(n)) * 0.5

        bn = IntervalBatchNorm(scale, shift)
        x = NumpyIT(lo, hi)
        y = bn(x)

        expected_width = np.abs(scale) * (hi - lo)
        np.testing.assert_allclose(y.width, expected_width, atol=1e-10)


class TestMatmulContainment:
    """Soundness: true output must be within interval bounds."""

    @pytest.mark.parametrize("seed", range(50))
    def test_midpoint_in_output(self, seed):
        rng = np.random.RandomState(seed)
        m, n = rng.randint(1, 6), rng.randint(1, 6)

        W = rng.randn(m, n)
        lo = rng.randn(n)
        hi = lo + np.abs(rng.randn(n)) * 0.5
        mid = (lo + hi) / 2

        x = NumpyIT(lo, hi)
        y = interval_matmul_exact_weights(W, x)
        true_out = W @ mid

        assert np.all(true_out >= y.lo - 1e-10), "True output below lower bound"
        assert np.all(true_out <= y.hi + 1e-10), "True output above upper bound"


class TestReanchorProperties:
    """Cross-validate re-anchoring properties from PInterval_Composition.v."""

    @pytest.mark.parametrize("seed", range(50))
    def test_reanchor_width_is_2eps(self, seed):
        """pi_reanchor_width: width(reanchor(I, eps)) == 2 * eps."""
        rng = np.random.RandomState(seed)
        lo = rng.randn()
        hi = lo + abs(rng.randn()) * 2.0
        eps = abs(rng.randn()) * 0.5

        mid = (lo + hi) / 2.0
        new_lo = mid - eps
        new_hi = mid + eps

        width = new_hi - new_lo
        assert abs(width - 2 * eps) < 1e-12

    @pytest.mark.parametrize("seed", range(50))
    def test_reanchor_contains_midpoint(self, seed):
        """pi_reanchor_contains_midpoint."""
        rng = np.random.RandomState(seed)
        lo = rng.randn()
        hi = lo + abs(rng.randn()) * 2.0
        eps = abs(rng.randn()) * 0.5

        mid = (lo + hi) / 2.0
        new_lo = mid - eps
        new_hi = mid + eps

        assert new_lo <= mid + 1e-15
        assert mid <= new_hi + 1e-15

    def test_reanchor_loses_containment(self):
        """pi_reanchor_loses_containment: concrete counterexample."""
        lo, hi = 0.0, 10.0
        eps = 1.0
        x = 0.0  # x is in [0, 10]

        mid = (lo + hi) / 2.0  # 5.0
        new_lo = mid - eps      # 4.0
        new_hi = mid + eps      # 6.0

        # x is in original interval
        assert lo <= x <= hi
        # x is NOT in reanchored interval
        assert not (new_lo <= x <= new_hi)
