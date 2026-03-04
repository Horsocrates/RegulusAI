"""Tests for regulus.interval.trisection — ShrinkingIntervals_uncountable_ERR.v."""

import pytest
from fractions import Fraction
from regulus.interval.trisection import (
    TrisectChoice, TrisectionState,
    trisect_left, trisect_middle, trisect_right, trisect_step,
    conf_below, conf_above, smart_trisect_choice,
    trisect_ref, trisect_delta,
    trisect_iter, diagonal_trisect,
)


# ===================================================================
#  Trisection steps
# ===================================================================

class TestTrisectStep:
    def test_trisect_left_width(self):
        """trisect_left_width: width == original / 3."""
        s = TrisectionState(Fraction(0), Fraction(1))
        result = trisect_left(s)
        assert result.width == Fraction(1, 3)

    def test_trisect_middle_width(self):
        """trisect_middle_width: width == original / 3."""
        s = TrisectionState(Fraction(0), Fraction(1))
        result = trisect_middle(s)
        assert result.width == Fraction(1, 3)

    def test_trisect_right_width(self):
        """trisect_right_width: width == original / 3."""
        s = TrisectionState(Fraction(0), Fraction(1))
        result = trisect_right(s)
        assert result.width == Fraction(1, 3)

    def test_trisect_step_nested(self):
        """trisect_step_nested: result ⊆ original for all choices."""
        s = TrisectionState(Fraction(1, 4), Fraction(3, 4))
        for choice in TrisectChoice:
            result = trisect_step(choice, s)
            assert result.left >= s.left
            assert result.right <= s.right

    def test_trisect_preserves_validity(self):
        """All trisection results have left <= right."""
        s = TrisectionState(Fraction(0), Fraction(1))
        for choice in TrisectChoice:
            result = trisect_step(choice, s)
            assert result.left <= result.right

    def test_trisect_covers_interval(self):
        """Three thirds cover the entire original interval."""
        s = TrisectionState(Fraction(0), Fraction(1))
        l = trisect_left(s)
        m = trisect_middle(s)
        r = trisect_right(s)
        # Left end of left == original left
        assert l.left == s.left
        # Right end of right == original right
        assert r.right == s.right
        # They chain: l.right == m.left, m.right == r.left
        assert l.right == m.left
        assert m.right == r.left


# ===================================================================
#  Smart choice
# ===================================================================

class TestSmartChoice:
    def test_conf_below(self):
        """conf_below: approx + delta < boundary."""
        assert conf_below(Fraction(1, 10), Fraction(1, 100), Fraction(1, 5))
        assert not conf_below(Fraction(1, 4), Fraction(1, 10), Fraction(1, 5))

    def test_conf_above(self):
        """conf_above: boundary < approx - delta."""
        assert conf_above(Fraction(9, 10), Fraction(1, 100), Fraction(1, 2))
        assert not conf_above(Fraction(1, 2), Fraction(1, 10), Fraction(1, 2))

    def test_smart_excludes_confidence(self):
        """smart_choice_excludes_confidence: chosen third doesn't contain enemy."""
        s = TrisectionState(Fraction(0), Fraction(1))
        # Enemy at 0.1 ± 0.01 → entirely in left third [0, 1/3]
        choice = smart_trisect_choice(s, Fraction(1, 10), Fraction(1, 100))
        result = trisect_step(choice, s)
        # Enemy's confidence interval should not overlap with chosen third
        enemy_lo = Fraction(1, 10) - Fraction(1, 100)
        enemy_hi = Fraction(1, 10) + Fraction(1, 100)
        # Result should be the right third [2/3, 1] or middle [1/3, 2/3]
        assert result.left >= enemy_hi or result.right <= enemy_lo

    def test_smart_choice_enemy_in_right(self):
        """Enemy in right third → choose LEFT."""
        s = TrisectionState(Fraction(0), Fraction(1))
        # Enemy at 0.9 ± 0.01
        choice = smart_trisect_choice(s, Fraction(9, 10), Fraction(1, 100))
        assert choice == TrisectChoice.LEFT


# ===================================================================
#  Synchronized parameters
# ===================================================================

class TestSynchronizedParams:
    def test_trisect_ref(self):
        """ref(n) = 48 * 3^n."""
        assert trisect_ref(0) == 48
        assert trisect_ref(1) == 144
        assert trisect_ref(2) == 432

    def test_trisect_delta(self):
        """delta(n) = 1/(24*3^n)."""
        assert trisect_delta(0) == Fraction(1, 24)
        assert trisect_delta(1) == Fraction(1, 72)
        assert trisect_delta(2) == Fraction(1, 216)

    def test_sync_relationship(self):
        """2/ref(n) == delta(n): synchronization holds."""
        for n in range(10):
            ref = trisect_ref(n)
            delta = trisect_delta(n)
            assert Fraction(2, ref) == delta


# ===================================================================
#  Trisection iteration
# ===================================================================

class TestTrisectIter:
    def test_iter_width(self):
        """trisect_iter_v2_width: width after n steps == 1/3^n."""
        N = 10
        values = [Fraction(k + 1, N + 2) for k in range(N)]

        def E(k, ref):
            return values[k % N]

        initial = TrisectionState(Fraction(0), Fraction(1))
        for n in range(1, 8):
            state = trisect_iter(E, initial, n)
            expected_width = Fraction(1, 3 ** n)
            assert state.width == expected_width

    def test_iter_nested(self):
        """trisect_iter_v2_nested: later iterations ⊆ earlier."""
        N = 5
        values = [Fraction(k, N + 1) for k in range(1, N + 1)]

        def E(k, ref):
            return values[k % N]

        initial = TrisectionState(Fraction(0), Fraction(1))
        prev = initial
        for n in range(1, 6):
            curr = trisect_iter(E, initial, n)
            assert curr.left >= prev.left
            assert curr.right <= prev.right
            prev = curr


# ===================================================================
#  Diagonal construction
# ===================================================================

class TestDiagonalTrisect:
    def test_separation(self):
        """diagonal_trisect_v2_differs: D differs from each E(k) by >= delta(k)/2."""
        N = 10
        values = [Fraction(k + 1, N + 2) for k in range(N)]

        def E(k, ref):
            return values[k % N]

        D = diagonal_trisect(E, steps=N)
        d_val = D(N)

        for k in range(N):
            gap = abs(d_val - values[k])
            min_gap = trisect_delta(k) / 2
            assert gap >= min_gap, (
                f"Step {k}: gap={float(gap):.2e} < min_gap={float(min_gap):.2e}"
            )

    def test_convergence(self):
        """Midpoint process converges: D(n) and D(n+1) get closer."""
        values = [Fraction(k, 20) for k in range(1, 16)]

        def E(k, ref):
            return values[k % len(values)]

        D = diagonal_trisect(E, steps=15)
        for n in range(5, 14):
            gap = abs(D(n + 1) - D(n))
            # Gap should be at most width(n)/2 = 1/(2*3^n)
            assert gap <= Fraction(1, 2 * 3**n)

    def test_in_unit_interval(self):
        """Diagonal stays in [0, 1]."""
        values = [Fraction(k, 10) for k in range(1, 10)]

        def E(k, ref):
            return values[k % len(values)]

        D = diagonal_trisect(E, steps=10)
        for n in range(11):
            val = D(n)
            assert Fraction(0) <= val <= Fraction(1)
