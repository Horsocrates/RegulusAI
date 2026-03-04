"""Tests for regulus.interval.softmax — PInterval_Softmax.v."""

import math
import random
import pytest
from regulus.interval.softmax import (
    f_sum, f_sum_except,
    softmax_lower_bound, softmax_upper_bound,
    interval_softmax,
)


# ===================================================================
#  f_sum helpers
# ===================================================================

class TestFSum:
    def test_f_sum_basic(self):
        """Sum of exp over small list."""
        xs = [0.0, 1.0, 2.0]
        result = f_sum(xs, math.exp)
        expected = math.exp(0) + math.exp(1) + math.exp(2)
        assert result == pytest.approx(expected)

    def test_f_sum_empty(self):
        assert f_sum([], math.exp) == pytest.approx(0.0)

    def test_f_sum_except_skips_index(self):
        """Correct index is skipped."""
        xs = [1.0, 2.0, 3.0]
        # Skip index 1 → sum exp(1) + exp(3)
        result = f_sum_except(xs, 1, math.exp)
        expected = math.exp(1.0) + math.exp(3.0)
        assert result == pytest.approx(expected)

    def test_f_sum_except_first(self):
        xs = [10.0, 20.0, 30.0]
        result = f_sum_except(xs, 0, math.exp)
        expected = math.exp(20.0) + math.exp(30.0)
        assert result == pytest.approx(expected)

    def test_f_sum_monotone(self):
        """f_sum_monotone: element-wise lo <= hi implies f_sum(lo) <= f_sum(hi)."""
        los = [0.0, 1.0, 2.0]
        his = [0.5, 1.5, 2.5]
        assert f_sum(los, math.exp) <= f_sum(his, math.exp)


# ===================================================================
#  Softmax bounds
# ===================================================================

class TestSoftmaxBounds:
    def test_lower_bound_soundness(self):
        """interval_softmax_lower_bound: lb <= actual softmax for sample points."""
        los = [0.0, 1.0, -1.0]
        his = [0.5, 1.5, -0.5]
        # Sample a point in [lo, hi]
        xs = [0.25, 1.25, -0.75]
        exp_xs = [math.exp(x) for x in xs]
        denom = sum(exp_xs)
        for i in range(3):
            lb = softmax_lower_bound(los, his, i, math.exp)
            actual = exp_xs[i] / denom
            assert lb <= actual + 1e-12

    def test_upper_bound_soundness(self):
        """interval_softmax_upper_bound: actual softmax <= ub."""
        los = [0.0, 1.0, -1.0]
        his = [0.5, 1.5, -0.5]
        xs = [0.25, 1.25, -0.75]
        exp_xs = [math.exp(x) for x in xs]
        denom = sum(exp_xs)
        for i in range(3):
            ub = softmax_upper_bound(los, his, i, math.exp)
            actual = exp_xs[i] / denom
            assert actual <= ub + 1e-12

    def test_bounds_in_01(self):
        """softmax_bound_le_one_cross: bounds in (0, 1)."""
        los = [-2.0, -1.0, 0.0, 1.0]
        his = [-1.0, 0.0, 1.0, 2.0]
        lbs, ubs = interval_softmax(los, his, math.exp)
        for i in range(4):
            assert 0.0 <= lbs[i] <= 1.0
            assert 0.0 <= ubs[i] <= 1.0
            assert lbs[i] <= ubs[i] + 1e-12

    def test_cross_multiplication_form(self):
        """softmax_cross_mul_lower: f(lo)*D_x <= f(x)*D_lo."""
        los = [0.0, 1.0]
        his = [0.5, 1.5]
        xs = [0.3, 1.2]
        f = math.exp
        for i in range(2):
            f_lo_i = f(los[i])
            f_x_i = f(xs[i])
            s_except_xs = sum(f(xs[j]) for j in range(2) if j != i)
            s_except_his = sum(f(his[j]) for j in range(2) if j != i)
            # Cross-mul: f(lo_i) * (f(x_i) + S_xs) <= f(x_i) * (f(lo_i) + S_his)
            lhs = f_lo_i * (f_x_i + s_except_xs)
            rhs = f_x_i * (f_lo_i + s_except_his)
            assert lhs <= rhs + 1e-10

    def test_interval_softmax_complete(self):
        """interval_softmax: all bounds sound on random data."""
        random.seed(123)
        for _ in range(100):
            n = random.randint(2, 8)
            centers = [random.uniform(-3, 3) for _ in range(n)]
            hw = [random.uniform(0.01, 0.5) for _ in range(n)]
            los = [c - h for c, h in zip(centers, hw)]
            his = [c + h for c, h in zip(centers, hw)]

            # Shift for stability
            shift = max(his)
            los_s = [lo - shift for lo in los]
            his_s = [hi - shift for hi in his]

            lbs, ubs = interval_softmax(los_s, his_s, math.exp)

            # Sample and check containment
            xs = [random.uniform(lo, hi) for lo, hi in zip(los, his)]
            xs_s = [x - shift for x in xs]
            exp_xs = [math.exp(x) for x in xs_s]
            denom = sum(exp_xs)
            for i in range(n):
                actual = exp_xs[i] / denom
                assert lbs[i] <= actual + 1e-10, f"lb[{i}]={lbs[i]} > actual={actual}"
                assert actual <= ubs[i] + 1e-10, f"actual={actual} > ub[{i}]={ubs[i]}"

    def test_numerical_stability_large_inputs(self):
        """Log-sum-exp shift prevents overflow with large inputs."""
        los = [500.0, 501.0]
        his = [502.0, 503.0]
        # Without shift, exp(503) would overflow
        shift = max(his)
        los_s = [lo - shift for lo in los]
        his_s = [hi - shift for hi in his]
        lbs, ubs = interval_softmax(los_s, his_s, math.exp)
        for i in range(2):
            assert 0.0 <= lbs[i] <= 1.0
            assert 0.0 <= ubs[i] <= 1.0

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            interval_softmax([1.0, 2.0], [3.0], math.exp)
