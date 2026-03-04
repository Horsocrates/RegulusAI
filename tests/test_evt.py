"""Tests for regulus.interval.evt — Coq-verified argmax (EVT_idx.v)."""

import math
import pytest
from regulus.interval.evt import (
    argmax_idx, find_max_idx_acc, grid_list, grid_point,
    argmax_on_grid, max_on_grid, sup_process, argmax_process,
)


# ===================================================================
#  Grid construction
# ===================================================================

class TestGridConstruction:
    def test_grid_point_endpoints(self):
        """grid_point(a,b,n,0) == a, grid_point(a,b,n,n) == b."""
        assert grid_point(1.0, 5.0, 10, 0) == pytest.approx(1.0)
        assert grid_point(1.0, 5.0, 10, 10) == pytest.approx(5.0)

    def test_grid_point_midpoint(self):
        """grid_point(0,1,2,1) == 0.5."""
        assert grid_point(0.0, 1.0, 2, 1) == pytest.approx(0.5)

    def test_grid_list_length(self):
        """grid_list has n+1 elements."""
        for n in [1, 5, 10, 100]:
            assert len(grid_list(0.0, 1.0, n)) == n + 1

    def test_grid_points_in_interval(self):
        """All grid points lie in [a, b]."""
        pts = grid_list(-2.0, 3.0, 50)
        for p in pts:
            assert -2.0 <= p <= 3.0

    def test_grid_invalid_n(self):
        with pytest.raises(ValueError):
            grid_point(0.0, 1.0, 0, 0)


# ===================================================================
#  Argmax
# ===================================================================

class TestArgmax:
    def test_argmax_idx_bound(self):
        """argmax_idx_bound: result < len(lst)."""
        for n in [1, 5, 20, 100]:
            lst = list(range(n))
            idx = argmax_idx(lambda x: x, lst)
            assert 0 <= idx < n

    def test_argmax_idx_maximizes(self):
        """argmax_idx_maximizes: f(lst[result]) >= f(lst[k]) for all k."""
        lst = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0]
        idx = argmax_idx(lambda x: x, lst)
        max_val = lst[idx]
        for v in lst:
            assert max_val >= v

    def test_argmax_single_element(self):
        """Single element list returns index 0."""
        assert argmax_idx(lambda x: x, [42.0]) == 0

    def test_argmax_empty(self):
        """Empty list returns 0."""
        assert argmax_idx(lambda x: x, []) == 0

    def test_argmax_with_function(self):
        """argmax over -x^2 finds point closest to zero."""
        lst = [-3.0, -1.0, 0.5, 2.0, 4.0]
        idx = argmax_idx(lambda x: -(x ** 2), lst)
        assert lst[idx] == pytest.approx(0.5)

    def test_argmax_negative_function(self):
        """Works correctly with all-negative function values."""
        lst = [1.0, 2.0, 3.0, 4.0, 5.0]
        idx = argmax_idx(lambda x: -x, lst)
        assert lst[idx] == pytest.approx(1.0)  # -1 is the max of {-1,-2,-3,-4,-5}

    def test_argmax_tie_behavior(self):
        """On tie (<=), accumulator updates — last equal index wins."""
        lst = [1.0, 3.0, 3.0, 2.0]
        idx = argmax_idx(lambda x: x, lst)
        # With <=, both indices 1 and 2 have value 3.0
        # Accumulator updates on equal → index 2 wins (last equal)
        assert idx == 2
        assert lst[idx] == 3.0


# ===================================================================
#  Grid-based extremum
# ===================================================================

class TestMaxOnGrid:
    def test_max_on_grid_attained(self):
        """max_on_grid_attained: result == f(argmax_on_grid)."""
        f = lambda x: math.sin(x)
        for n in [10, 100]:
            m = max_on_grid(f, 0.0, math.pi, n)
            a = argmax_on_grid(f, 0.0, math.pi, n)
            assert m == pytest.approx(f(a))

    def test_grid_value_le_max(self):
        """grid_value_le_max: f(grid[k]) <= max_on_grid for all k."""
        f = lambda x: x * (1 - x)
        n = 100
        m = max_on_grid(f, 0.0, 1.0, n)
        for pt in grid_list(0.0, 1.0, n):
            assert f(pt) <= m + 1e-15


# ===================================================================
#  Supremum process
# ===================================================================

class TestSupProcess:
    def test_sup_process_improves_with_refinement(self):
        """sup_process approaches true max as n increases."""
        f = lambda x: -(x - 0.7) ** 2
        true_max = f(0.7)  # = 0.0
        # Error should decrease with refinement (grid spacing ~ 1/n)
        err_10 = abs(sup_process(f, 0.0, 1.0, 10) - true_max)
        err_100 = abs(sup_process(f, 0.0, 1.0, 100) - true_max)
        err_1000 = abs(sup_process(f, 0.0, 1.0, 1000) - true_max)
        assert err_100 < err_10
        assert err_1000 < err_100

    def test_sup_process_convergence(self):
        """sup_process_is_Cauchy: |sup(m) - sup(n)| -> 0."""
        f = lambda x: -(x - 0.3) ** 2
        true_max = f(0.3)
        # At n=1000, should be very close
        val = sup_process(f, 0.0, 1.0, 1000)
        assert abs(val - true_max) < 1e-5

    def test_evt_strong_process(self):
        """EVT_strong_process: sup_process == f(argmax_process)."""
        f = lambda x: math.cos(x)
        for n in [5, 50, 200]:
            s = sup_process(f, 0.0, 2 * math.pi, n)
            a = argmax_process(f, 0.0, 2 * math.pi, n)
            assert s == pytest.approx(f(a))
