"""Tests for regulus.interval — mirrors Coq PInterval.v correctness lemmas."""

import math
import pytest

from regulus.interval.interval import Interval
from regulus.interval.interval_tensor import IntervalTensor
from regulus.interval.nn import IntervalLinear, IntervalReLU, IntervalSequential
from regulus.interval.bisection import bisection_iter, bisection_process, find_root


# ===== Interval construction =====

class TestIntervalConstruction:
    def test_valid_interval(self):
        iv = Interval(1.0, 2.0)
        assert iv.lo == 1.0
        assert iv.hi == 2.0

    def test_point_interval(self):
        iv = Interval.point(3.14)
        assert iv.lo == iv.hi == 3.14

    def test_pm_interval(self):
        iv = Interval.pm(1.0, 0.1)
        assert abs(iv.lo - 0.9) < 1e-10
        assert abs(iv.hi - 1.1) < 1e-10

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="invariant"):
            Interval(2.0, 1.0)


# ===== Interval arithmetic — correspond to pi_*_correct =====

class TestIntervalArithmetic:
    def test_add(self):
        """pi_add_correct: x in I, y in J => x+y in I+J."""
        a = Interval(1.0, 2.0)
        b = Interval(3.0, 5.0)
        c = a + b
        assert c.lo == 4.0
        assert c.hi == 7.0
        # Verify containment for sample points
        for x in [1.0, 1.5, 2.0]:
            for y in [3.0, 4.0, 5.0]:
                assert c.contains(x + y)

    def test_neg(self):
        """pi_neg_correct: x in I => -x in -I."""
        a = Interval(1.0, 3.0)
        b = -a
        assert b.lo == -3.0
        assert b.hi == -1.0

    def test_sub(self):
        """pi_sub_correct: x in I, y in J => x-y in I-J."""
        a = Interval(3.0, 5.0)
        b = Interval(1.0, 2.0)
        c = a - b
        assert c.lo == 1.0  # 3 - 2
        assert c.hi == 4.0  # 5 - 1

    def test_mul_positive(self):
        """pi_mul_correct: positive intervals."""
        a = Interval(2.0, 3.0)
        b = Interval(4.0, 5.0)
        c = a * b
        assert c.lo == 8.0
        assert c.hi == 15.0

    def test_mul_mixed_signs(self):
        """pi_mul_correct: mixed sign intervals."""
        a = Interval(-2.0, 3.0)
        b = Interval(-1.0, 4.0)
        c = a * b
        # products: (-2)*(-1)=2, (-2)*4=-8, 3*(-1)=-3, 3*4=12
        assert c.lo == -8.0
        assert c.hi == 12.0

    def test_mul_scalar(self):
        a = Interval(1.0, 3.0)
        assert (a * 2).lo == 2.0
        assert (a * 2).hi == 6.0
        assert (a * -1).lo == -3.0
        assert (a * -1).hi == -1.0

    def test_relu_positive(self):
        """pi_relu_correct: all positive."""
        a = Interval(1.0, 3.0)
        assert a.relu() == Interval(1.0, 3.0)

    def test_relu_negative(self):
        """pi_relu_correct: all negative."""
        a = Interval(-3.0, -1.0)
        assert a.relu() == Interval(0.0, 0.0)

    def test_relu_crossing(self):
        """pi_relu_correct: crosses zero."""
        a = Interval(-2.0, 3.0)
        r = a.relu()
        assert r.lo == 0.0
        assert r.hi == 3.0

    def test_abs_positive(self):
        """pi_abs_correct: all positive."""
        a = Interval(1.0, 3.0)
        assert abs(a) == Interval(1.0, 3.0)

    def test_abs_negative(self):
        """pi_abs_correct: all negative."""
        a = Interval(-3.0, -1.0)
        assert abs(a) == Interval(1.0, 3.0)

    def test_abs_crossing(self):
        """pi_abs_correct: crosses zero."""
        a = Interval(-2.0, 3.0)
        r = abs(a)
        assert r.lo == 0.0
        assert r.hi == 3.0

    def test_overlaps(self):
        """pi_overlaps_correct."""
        a = Interval(1.0, 3.0)
        b = Interval(2.0, 4.0)
        c = Interval(4.0, 5.0)
        assert a.overlaps(b) is True
        assert a.overlaps(c) is False
        assert b.overlaps(c) is True  # touching at 4.0

    def test_div_positive(self):
        """pi_div_correct: positive intervals."""
        a = Interval(6.0, 12.0)
        b = Interval(2.0, 3.0)
        c = a / b
        assert c.lo == 2.0   # 6/3
        assert c.hi == 6.0   # 12/2

    def test_div_negative_divisor(self):
        """pi_div_correct: negative divisor."""
        a = Interval(2.0, 4.0)
        b = Interval(-3.0, -1.0)
        c = a / b
        assert c.lo == -4.0  # 4/(-1)
        assert c.hi == pytest.approx(-2/3)  # 2/(-3)

    def test_div_zero_raises(self):
        """Division by interval containing 0 raises."""
        a = Interval(1.0, 2.0)
        b = Interval(-1.0, 1.0)
        with pytest.raises(ZeroDivisionError, match="contains zero"):
            a / b

    def test_div_scalar(self):
        """Division by scalar."""
        a = Interval(4.0, 8.0)
        c = a / 2
        assert c.lo == 2.0
        assert c.hi == 4.0

    def test_monotone_sqrt(self):
        """pi_monotone_correct: sqrt is monotone increasing on [1,4]."""
        a = Interval(1.0, 4.0)
        c = a.monotone(math.sqrt)
        assert c.lo == pytest.approx(1.0)
        assert c.hi == pytest.approx(2.0)

    def test_sigmoid(self):
        """Sigmoid via pi_monotone_correct."""
        a = Interval(-2.0, 2.0)
        c = a.sigmoid()
        assert c.lo == pytest.approx(1.0 / (1 + math.exp(2)))
        assert c.hi == pytest.approx(1.0 / (1 + math.exp(-2)))
        # sigma(0) = 0.5 should be contained
        assert c.contains(0.5)

    def test_antitone(self):
        """pi_antitone_correct: 1/x is decreasing on [1,4]."""
        a = Interval(1.0, 4.0)
        c = a.antitone(lambda x: 1.0 / x)
        assert c.lo == pytest.approx(0.25)
        assert c.hi == pytest.approx(1.0)


# ===== Bisection — corresponds to IVT.v =====

class TestBisection:
    def test_sqrt2(self):
        """bisection_iter on f(x) = x^2 - 2 in [1,2] -> sqrt(2)."""
        f = lambda x: x * x - 2.0
        state = bisection_iter(f, 1.0, 2.0, 53)
        mid = (state.left + state.right) / 2.0
        assert abs(mid - math.sqrt(2)) < 1e-14
        # Width should be (2-1)/2^53
        assert state.right - state.left < 1e-15

    def test_bisection_process(self):
        """bisection_process gives midpoints converging to root."""
        f = lambda x: x * x - 2.0
        for n in [10, 20, 30]:
            mid = bisection_process(f, 1.0, 2.0, n)
            assert abs(mid - math.sqrt(2)) < 1.0 / (2 ** n)

    def test_find_root_flipped(self):
        """find_root handles f(a) > 0, f(b) < 0."""
        f = lambda x: 2.0 - x * x  # positive at 1, negative at 2
        state = find_root(f, 1.0, 2.0)
        mid = (state.left + state.right) / 2.0
        assert abs(mid - math.sqrt(2)) < 1e-14

    def test_width_halves(self):
        """Coq-proven: width(n) = (b-a) / 2^n."""
        f = lambda x: x - 0.7
        for n in range(20):
            state = bisection_iter(f, 0.0, 1.0, n)
            expected_width = 1.0 / (2 ** n)
            actual_width = state.right - state.left
            assert abs(actual_width - expected_width) < 1e-12


# ===== Neural network layers =====

class TestIntervalNN:
    def test_linear_identity(self):
        """Linear with identity weights propagates intervals."""
        layer = IntervalLinear(
            weights=[[1.0, 0.0], [0.0, 1.0]],
            biases=[0.0, 0.0],
        )
        x = IntervalTensor([[1.0, 2.0], [3.0, 4.0]])
        y = layer(x)
        assert y[0].lo == 1.0
        assert y[0].hi == 2.0
        assert y[1].lo == 3.0
        assert y[1].hi == 4.0

    def test_linear_scaling(self):
        layer = IntervalLinear(weights=[[2.0]], biases=[1.0])
        x = IntervalTensor([[1.0, 3.0]])
        y = layer(x)
        assert y[0].lo == 3.0  # 2*1 + 1
        assert y[0].hi == 7.0  # 2*3 + 1

    def test_relu_layer(self):
        layer = IntervalReLU()
        x = IntervalTensor([[-2.0, 3.0], [1.0, 5.0]])
        y = layer(x)
        assert y[0].lo == 0.0
        assert y[0].hi == 3.0
        assert y[1].lo == 1.0

    def test_sequential(self):
        model = IntervalSequential(
            IntervalLinear([[2.0, -1.0]], [0.5]),
            IntervalReLU(),
        )
        x = IntervalTensor([[1.0, 2.0], [0.0, 1.0]])
        y = model(x)
        # output = relu(2*[1,2] + (-1)*[0,1] + 0.5)
        # = relu([2,4] + [-1,0] + [0.5,0.5])
        # = relu([1.5, 4.5])
        # = [1.5, 4.5]
        assert y[0].lo == 1.5
        assert y[0].hi == 4.5


# ===== IntervalTensor =====

class TestIntervalTensor:
    def test_from_pairs(self):
        t = IntervalTensor([[1, 2], [3, 4]])
        assert len(t) == 2
        assert t[0].lo == 1.0

    def test_from_point(self):
        t = IntervalTensor.from_point([1.0, 2.0, 3.0])
        assert len(t) == 3
        assert t[0].lo == t[0].hi == 1.0

    def test_from_pm(self):
        t = IntervalTensor.from_pm([1.0, 2.0], radius=0.1)
        assert abs(t[0].lo - 0.9) < 1e-10
        assert abs(t[1].hi - 2.1) < 1e-10

    def test_any_overlap(self):
        t1 = IntervalTensor([[0, 1], [2, 3]])
        assert t1.any_overlap() is False
        t2 = IntervalTensor([[0, 2], [1, 3]])
        assert t2.any_overlap() is True

    def test_dot(self):
        t = IntervalTensor([[1, 2], [3, 4]])
        result = t.dot([1.0, 1.0])
        assert result.lo == 4.0
        assert result.hi == 6.0
