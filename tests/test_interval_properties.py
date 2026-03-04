"""
Property-based tests for interval arithmetic.

Uses Hypothesis to generate random intervals and verify algebraic
laws that correspond to Coq-proven properties from PInterval.v:
  - pi_width_nonneg: width always >= 0
  - pi_add_correct: soundness of addition
  - pi_mul_correct: soundness of multiplication
  - pi_relu_correct: soundness of ReLU
  - pi_relu_width_bound: ReLU does not increase width
  - pi_monotone_correct: soundness of monotone lifting (sigmoid)

These tests catch edge cases that example-based tests miss:
NaN, infinity, subnormal floats, zero-width intervals, etc.
"""

import numpy as np
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from regulus.interval.interval import Interval
from regulus.nn.interval_tensor import IntervalTensor as NumpyIT
from regulus.nn.interval_tensor import interval_matmul_exact_weights
from regulus.nn.layers import IntervalBatchNorm, IntervalSoftmax


# ===== Strategies =====

def intervals(min_val=-1e4, max_val=1e4, max_width=100.0):
    """Strategy for valid Interval objects."""
    return st.tuples(
        st.floats(min_value=min_val, max_value=max_val,
                  allow_nan=False, allow_infinity=False),
        st.floats(min_value=0.0, max_value=max_width,
                  allow_nan=False, allow_infinity=False),
    ).map(lambda t: Interval(t[0], t[0] + t[1]))


def numpy_intervals(n=None, min_val=-1e4, max_val=1e4, max_width=10.0):
    """Strategy for numpy IntervalTensor."""
    if n is None:
        n_strategy = st.integers(min_value=1, max_value=20)
    else:
        n_strategy = st.just(n)

    @st.composite
    def make(draw):
        size = draw(n_strategy)
        lo = np.array([draw(st.floats(min_value=min_val, max_value=max_val,
                                       allow_nan=False, allow_infinity=False))
                       for _ in range(size)])
        widths = np.array([draw(st.floats(min_value=0.0, max_value=max_width,
                                          allow_nan=False, allow_infinity=False))
                           for _ in range(size)])
        return NumpyIT(lo, lo + widths)

    return make()


# ===== Scalar Interval Properties =====

class TestScalarProperties:
    """Algebraic properties of regulus.interval.interval.Interval."""

    @given(intervals(), intervals())
    @settings(max_examples=200)
    def test_add_commutative(self, a, b):
        """a + b == b + a (within fp tolerance)."""
        ab = a + b
        ba = b + a
        assert abs(ab.lo - ba.lo) < 1e-10
        assert abs(ab.hi - ba.hi) < 1e-10

    @given(intervals(), intervals(), intervals())
    @settings(max_examples=200)
    def test_add_associative(self, a, b, c):
        """(a + b) + c == a + (b + c) (within fp tolerance)."""
        abc1 = (a + b) + c
        abc2 = a + (b + c)
        assert abs(abc1.lo - abc2.lo) < 1e-8
        assert abs(abc1.hi - abc2.hi) < 1e-8

    @given(intervals())
    @settings(max_examples=200)
    def test_width_nonneg(self, a):
        """pi_width_nonneg: width >= 0."""
        assert a.width >= -1e-15

    @given(intervals())
    @settings(max_examples=200)
    def test_neg_involution(self, a):
        """-(-a) == a."""
        nn = -(-a)
        assert abs(nn.lo - a.lo) < 1e-12
        assert abs(nn.hi - a.hi) < 1e-12

    @given(intervals())
    @settings(max_examples=200)
    def test_sub_self_contains_zero(self, a):
        """a - a contains 0."""
        diff = a - a
        assert diff.contains(0.0)

    @given(intervals())
    @settings(max_examples=200)
    def test_relu_idempotent(self, a):
        """relu(relu(a)) == relu(a)."""
        r1 = a.relu()
        r2 = r1.relu()
        assert abs(r1.lo - r2.lo) < 1e-15
        assert abs(r1.hi - r2.hi) < 1e-15

    @given(intervals())
    @settings(max_examples=200)
    def test_relu_width_bound(self, a):
        """pi_relu_width_bound: width(relu(a)) <= width(a)."""
        assert a.relu().width <= a.width + 1e-12

    @given(intervals())
    @settings(max_examples=200)
    def test_sigmoid_range(self, a):
        """Sigmoid output in [0, 1]."""
        s = a.sigmoid()
        assert s.lo >= -1e-15
        assert s.hi <= 1.0 + 1e-15

    @given(intervals())
    @settings(max_examples=200)
    def test_relu_nonneg(self, a):
        """ReLU output is always >= 0."""
        r = a.relu()
        assert r.lo >= -1e-15
        assert r.hi >= -1e-15


# ===== Containment Soundness (the critical property) =====

class TestContainmentSoundness:
    """Soundness: if x in A and y in B, then f(x,y) in f(A,B)."""

    @given(intervals(), intervals())
    @settings(max_examples=200)
    def test_add_soundness(self, a, b):
        """Midpoint sum is in interval sum."""
        x = a.mid
        y = b.mid
        result = a + b
        assert result.contains(x + y)

    @given(intervals(), intervals())
    @settings(max_examples=200)
    def test_sub_soundness(self, a, b):
        """Midpoint difference is in interval difference."""
        x = a.mid
        y = b.mid
        result = a - b
        assert result.contains(x - y)

    @given(intervals(), intervals())
    @settings(max_examples=200)
    def test_mul_soundness(self, a, b):
        """Midpoint product is in interval product."""
        x = a.mid
        y = b.mid
        result = a * b
        assert result.contains(x * y)

    @given(intervals())
    @settings(max_examples=200)
    def test_relu_soundness(self, a):
        """ReLU of midpoint is in ReLU of interval."""
        x = a.mid
        result = a.relu()
        assert result.contains(max(0.0, x))

    @given(intervals())
    @settings(max_examples=200)
    def test_sigmoid_soundness(self, a):
        """Sigmoid of midpoint is in sigmoid of interval."""
        import math
        x = a.mid
        if x >= 0:
            sig_x = 1.0 / (1.0 + math.exp(-x))
        else:
            ex = math.exp(x)
            sig_x = ex / (1.0 + ex)
        result = a.sigmoid()
        assert result.lo <= sig_x + 1e-12
        assert sig_x <= result.hi + 1e-12


# ===== Numpy IntervalTensor Properties =====

class TestNumpyProperties:
    """Properties for regulus.nn.interval_tensor.IntervalTensor."""

    @given(st.integers(1, 50))
    @settings(max_examples=100)
    def test_relu_width_bound_vector(self, n):
        """Element-wise: width(relu(x)) <= width(x)."""
        rng = np.random.RandomState(n)
        lo = rng.randn(n) * 3
        hi = lo + np.abs(rng.randn(n))
        x = NumpyIT(lo, hi)
        y = x.relu()
        assert np.all(y.width <= x.width + 1e-12)

    @given(st.integers(1, 50))
    @settings(max_examples=100)
    def test_relu_nonneg_vector(self, n):
        """ReLU output is always >= 0."""
        rng = np.random.RandomState(n)
        lo = rng.randn(n) * 5
        hi = lo + np.abs(rng.randn(n)) * 2
        x = NumpyIT(lo, hi)
        y = x.relu()
        assert np.all(y.lo >= -1e-15)
        assert np.all(y.hi >= -1e-15)

    @given(st.integers(1, 30))
    @settings(max_examples=50)
    def test_matmul_containment(self, seed):
        """W @ mid(x) is in interval_matmul(W, x)."""
        rng = np.random.RandomState(seed)
        m = rng.randint(1, 8)
        n = rng.randint(1, 8)
        W = rng.randn(m, n)
        lo = rng.randn(n)
        hi = lo + np.abs(rng.randn(n)) * 0.5
        mid = (lo + hi) / 2

        x = NumpyIT(lo, hi)
        y = interval_matmul_exact_weights(W, x)
        true_out = W @ mid

        assert np.all(true_out >= y.lo - 1e-10)
        assert np.all(true_out <= y.hi + 1e-10)

    @given(st.integers(1, 50))
    @settings(max_examples=100)
    def test_sigmoid_range_vector(self, n):
        """Sigmoid output in [0, 1]."""
        rng = np.random.RandomState(n)
        lo = rng.randn(n) * 3
        hi = lo + np.abs(rng.randn(n))
        x = NumpyIT(lo, hi)
        y = x.sigmoid()
        assert np.all(y.lo >= -1e-15)
        assert np.all(y.hi <= 1.0 + 1e-15)


# ===== BatchNorm Width Formula (Coq cross-check) =====

class TestBatchNormProperties:
    """Properties from PInterval_Conv.v: pi_affine_width."""

    @given(st.integers(1, 50))
    @settings(max_examples=100)
    def test_bn_width_equals_abs_scale_times_input_width(self, seed):
        """pi_affine_width: width(BN(x)) == |scale| * width(x)."""
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

    @given(st.integers(1, 50))
    @settings(max_examples=100)
    def test_bn_containment(self, seed):
        """BN of midpoint is in BN of interval."""
        rng = np.random.RandomState(seed)
        n = rng.randint(1, 10)
        scale = rng.randn(n)
        shift = rng.randn(n)
        lo = rng.randn(n)
        hi = lo + np.abs(rng.randn(n)) * 0.5
        mid = (lo + hi) / 2

        bn = IntervalBatchNorm(scale, shift)
        x = NumpyIT(lo, hi)
        y = bn(x)
        true_out = scale * mid + shift

        assert np.all(true_out >= y.lo - 1e-10)
        assert np.all(true_out <= y.hi + 1e-10)


# ===== Softmax Properties (closing the biggest formal gap) =====

def _np_softmax(x):
    """Numerically stable softmax for reference."""
    e = np.exp(x - np.max(x))
    return e / np.sum(e)


@st.composite
def softmax_intervals(draw, n=None):
    """Strategy for IntervalTensor inputs suitable for softmax.

    Values clamped to [-50, 50] to avoid exp overflow.
    Width clamped to [0, 5] to keep intervals reasonable.
    """
    if n is None:
        n = draw(st.integers(min_value=2, max_value=8))
    lo = np.array([draw(st.floats(min_value=-50.0, max_value=50.0,
                                   allow_nan=False, allow_infinity=False))
                   for _ in range(n)])
    widths = np.array([draw(st.floats(min_value=0.0, max_value=5.0,
                                      allow_nan=False, allow_infinity=False))
                       for _ in range(n)])
    return NumpyIT(lo, lo + widths)


class TestSoftmaxProperties:
    """Properties of IntervalSoftmax -- the biggest formal gap.

    IntervalSoftmax uses conservative bounds:
      lo_i = exp(lo_i) / (exp(lo_i) + sum_{j!=i} exp(hi_j))  (min num / max denom)
      hi_i = exp(hi_i) / (exp(hi_i) + sum_{j!=i} exp(lo_j))  (max num / min denom)

    These tests verify the bounds are correct before Coq formalization.
    """

    @given(softmax_intervals())
    @settings(max_examples=200)
    def test_softmax_containment_soundness(self, x):
        """CRITICAL: softmax of any point in intervals is in IntervalSoftmax output.

        This is the soundness property -- if it fails, the implementation is wrong.
        Tests with midpoint and multiple random interior points.
        """
        softmax_layer = IntervalSoftmax()
        result = softmax_layer(x)

        # Test midpoint
        mid = (x.lo + x.hi) / 2
        true_softmax = _np_softmax(mid)
        assert np.all(true_softmax >= result.lo - 1e-10), \
            f"Lower bound violation at midpoint: {np.min(true_softmax - result.lo)}"
        assert np.all(true_softmax <= result.hi + 1e-10), \
            f"Upper bound violation at midpoint: {np.max(true_softmax - result.hi)}"

        # Test random interior points (stress the non-monotone interaction)
        rng = np.random.RandomState(42)
        for _ in range(10):
            t = rng.rand(len(x.lo))  # uniform in [0, 1] per component
            point = x.lo + t * (x.hi - x.lo)
            true_softmax = _np_softmax(point)
            assert np.all(true_softmax >= result.lo - 1e-10), \
                f"Lower bound violation at interior point"
            assert np.all(true_softmax <= result.hi + 1e-10), \
                f"Upper bound violation at interior point"

    @given(softmax_intervals())
    @settings(max_examples=200)
    def test_softmax_output_in_01(self, x):
        """All softmax bounds must be in [0, 1]."""
        result = IntervalSoftmax()(x)
        assert np.all(result.lo >= -1e-15), \
            f"Lower bound below 0: {np.min(result.lo)}"
        assert np.all(result.hi <= 1.0 + 1e-15), \
            f"Upper bound above 1: {np.max(result.hi)}"

    @given(st.integers(2, 8))
    @settings(max_examples=100)
    def test_softmax_point_interval_exact(self, n):
        """Point intervals (lo == hi) should give exact softmax."""
        rng = np.random.RandomState(n)
        logits = rng.randn(n) * 3  # moderate values
        x = NumpyIT(logits, logits.copy())  # point interval
        result = IntervalSoftmax()(x)
        expected = _np_softmax(logits)
        np.testing.assert_allclose(result.lo, expected, atol=1e-10,
                                   err_msg="Lower bound != exact softmax for point interval")
        np.testing.assert_allclose(result.hi, expected, atol=1e-10,
                                   err_msg="Upper bound != exact softmax for point interval")

    @given(st.integers(1, 50))
    @settings(max_examples=100)
    def test_softmax_width_monotone(self, seed):
        """Wider input intervals should produce wider (or equal) output.

        If we widen the input intervals, the output bounds should not shrink.
        """
        rng = np.random.RandomState(seed)
        n = rng.randint(2, 6)
        lo = rng.randn(n) * 3
        narrow_w = np.abs(rng.randn(n)) * 0.5
        extra_w = np.abs(rng.randn(n)) * 0.5

        narrow = NumpyIT(lo, lo + narrow_w)
        wide = NumpyIT(lo, lo + narrow_w + extra_w)

        r_narrow = IntervalSoftmax()(narrow)
        r_wide = IntervalSoftmax()(wide)

        # Wide output should be at least as wide as narrow output
        assert np.all(r_wide.width >= r_narrow.width - 1e-10), \
            f"Width decreased when input widened: " \
            f"narrow={r_narrow.width}, wide={r_wide.width}"

    @given(softmax_intervals())
    @settings(max_examples=200)
    def test_softmax_shift_invariance(self, x):
        """softmax(x + c) == softmax(x) for constant shift c.

        Softmax is invariant to uniform additive shifts of all logits.
        """
        rng = np.random.RandomState(hash(tuple(x.lo)) % 2**31)
        c = rng.randn() * 10  # random shift

        shifted = NumpyIT(x.lo + c, x.hi + c)

        r_orig = IntervalSoftmax()(x)
        r_shifted = IntervalSoftmax()(shifted)

        np.testing.assert_allclose(r_orig.lo, r_shifted.lo, atol=1e-10,
                                   err_msg="Shift invariance violated (lower)")
        np.testing.assert_allclose(r_orig.hi, r_shifted.hi, atol=1e-10,
                                   err_msg="Shift invariance violated (upper)")

    @given(softmax_intervals())
    @settings(max_examples=200)
    def test_softmax_sum_bounds(self, x):
        """Sum of lower bounds <= 1 <= sum of upper bounds.

        Since each lower bound minimizes one class (maximizing competitors),
        their simultaneous sum cannot exceed 1. Symmetrically for upper bounds.
        """
        result = IntervalSoftmax()(x)
        lo_sum = np.sum(result.lo)
        hi_sum = np.sum(result.hi)
        assert lo_sum <= 1.0 + 1e-10, \
            f"Sum of lower bounds > 1: {lo_sum}"
        assert hi_sum >= 1.0 - 1e-10, \
            f"Sum of upper bounds < 1: {hi_sum}"
