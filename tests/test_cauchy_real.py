"""Tests for Cauchy real numbers and rounding safety.

Mirrors Coq theorems from CauchyReal.v and RoundingSafety.v.

Tests:
    - Cauchy sequence construction and approximation
    - Arithmetic operations (add, neg, sub, const)
    - Equivalence relation (refl, sym, trans)
    - Ordering and positivity
    - Rounding safety (interval widening, IBP margin, CROWN bounds)
    - Double rounding error bound
"""

from __future__ import annotations

import math

import pytest

from regulus.interval.cauchy_real import (
    CauchySeq,
    RoundingSafety,
    cauchy_add,
    cauchy_const,
    cauchy_e,
    cauchy_equiv,
    cauchy_from_convergent,
    cauchy_neg,
    cauchy_pos,
    cauchy_sqrt2,
    cauchy_sub,
)


# ---------------------------------------------------------------------------
#  Test Cauchy sequences
# ---------------------------------------------------------------------------


class TestCauchySeq:
    """Test CauchySeq construction and basic properties."""

    def test_const_sequence(self):
        """Constant sequence has exact value at all indices."""
        c = cauchy_const(3.14)
        assert c(0) == pytest.approx(3.14)
        assert c(100) == pytest.approx(3.14)
        assert c(1000) == pytest.approx(3.14)

    def test_const_approx(self):
        """Constant sequence approximation is exact."""
        c = cauchy_const(2.718)
        assert c.approx(1e-15) == pytest.approx(2.718)

    def test_sqrt2_converges(self):
        """sqrt(2) Cauchy sequence converges."""
        s = cauchy_sqrt2()
        val = s.approx(1e-10)
        assert val == pytest.approx(math.sqrt(2), abs=1e-8)

    def test_e_converges(self):
        """e Cauchy sequence converges."""
        e = cauchy_e()
        val = e.approx(1e-10)
        assert val == pytest.approx(math.e, abs=1e-6)

    def test_cauchy_property(self):
        """Cauchy property holds empirically."""
        c = cauchy_const(1.0)
        assert c.is_cauchy_at(0.01)

    def test_sqrt2_cauchy(self):
        """sqrt(2) sequence satisfies Cauchy property."""
        s = cauchy_sqrt2()
        assert s.is_cauchy_at(1e-6)

    def test_approx_raises_on_nonpositive_eps(self):
        """approx raises ValueError for eps <= 0."""
        c = cauchy_const(1.0)
        with pytest.raises(ValueError):
            c.approx(0)
        with pytest.raises(ValueError):
            c.approx(-1)


# ---------------------------------------------------------------------------
#  Test arithmetic (mirrors Coq: cauchy_add, cauchy_neg, etc.)
# ---------------------------------------------------------------------------


class TestCauchyArithmetic:
    """Test arithmetic operations on Cauchy sequences."""

    def test_add_constants(self):
        """cauchy_add of constants gives sum. Mirrors cauchy_add_is_cauchy."""
        a = cauchy_const(3.0)
        b = cauchy_const(4.0)
        s = cauchy_add(a, b)
        assert s.approx() == pytest.approx(7.0)

    def test_neg_constant(self):
        """cauchy_neg of constant gives negation. Mirrors cauchy_neg_is_cauchy."""
        a = cauchy_const(5.0)
        n = cauchy_neg(a)
        assert n.approx() == pytest.approx(-5.0)

    def test_sub_constants(self):
        """cauchy_sub of constants gives difference."""
        a = cauchy_const(10.0)
        b = cauchy_const(3.0)
        d = cauchy_sub(a, b)
        assert d.approx() == pytest.approx(7.0)

    def test_add_sqrt2_neg_sqrt2(self):
        """a + (-a) ≈ 0. Mirrors cauchy_add_neg_r."""
        a = cauchy_sqrt2()
        z = cauchy_add(a, cauchy_neg(a))
        assert z.approx() == pytest.approx(0.0, abs=1e-8)

    def test_add_comm(self):
        """a + b ≈ b + a. Mirrors cauchy_add_comm."""
        a = cauchy_const(2.5)
        b = cauchy_const(3.7)
        ab = cauchy_add(a, b)
        ba = cauchy_add(b, a)
        assert cauchy_equiv(ab, ba)

    def test_add_assoc(self):
        """(a+b)+c ≈ a+(b+c). Mirrors cauchy_add_assoc."""
        a = cauchy_const(1.0)
        b = cauchy_const(2.0)
        c = cauchy_const(3.0)
        lhs = cauchy_add(cauchy_add(a, b), c)
        rhs = cauchy_add(a, cauchy_add(b, c))
        assert cauchy_equiv(lhs, rhs)

    def test_add_zero_identity(self):
        """a + 0 ≈ a. Mirrors cauchy_add_zero_r."""
        a = cauchy_const(42.0)
        az = cauchy_add(a, cauchy_const(0.0))
        assert cauchy_equiv(az, a)


# ---------------------------------------------------------------------------
#  Test equivalence relation (mirrors Coq: cauchy_equiv_refl/sym/trans)
# ---------------------------------------------------------------------------


class TestCauchyEquiv:
    """Test equivalence relation properties."""

    def test_refl(self):
        """a ≈ a. Mirrors cauchy_equiv_refl."""
        a = cauchy_sqrt2()
        assert cauchy_equiv(a, a)

    def test_sym(self):
        """a ≈ b → b ≈ a. Mirrors cauchy_equiv_sym."""
        a = cauchy_const(1.0)
        b = cauchy_const(1.0)
        assert cauchy_equiv(a, b)
        assert cauchy_equiv(b, a)

    def test_trans(self):
        """a ≈ b ∧ b ≈ c → a ≈ c. Mirrors cauchy_equiv_trans."""
        a = cauchy_const(5.0)
        b = cauchy_const(5.0)
        c = cauchy_const(5.0)
        assert cauchy_equiv(a, b)
        assert cauchy_equiv(b, c)
        assert cauchy_equiv(a, c)

    def test_not_equiv_different(self):
        """Different constants are not equivalent."""
        a = cauchy_const(1.0)
        b = cauchy_const(2.0)
        assert not cauchy_equiv(a, b, eps=0.5)


# ---------------------------------------------------------------------------
#  Test ordering (mirrors Coq: cauchy_pos, cauchy_const_lt)
# ---------------------------------------------------------------------------


class TestCauchyOrdering:
    """Test ordering properties."""

    def test_positive_constant(self):
        """Positive constant is positive. Mirrors cauchy_const_lt."""
        a = cauchy_const(1.0)
        assert cauchy_pos(a)

    def test_zero_not_positive(self):
        """Zero is not positive. Mirrors cauchy_pos_not_zero contrapositive."""
        z = cauchy_const(0.0)
        assert not cauchy_pos(z)

    def test_negative_not_positive(self):
        """Negative constant is not positive."""
        a = cauchy_const(-1.0)
        assert not cauchy_pos(a)

    def test_sub_positive_when_ordered(self):
        """q - p > 0 when q > p. Mirrors cauchy_const_lt."""
        p = cauchy_const(2.0)
        q = cauchy_const(5.0)
        d = cauchy_sub(q, p)
        assert cauchy_pos(d)


# ---------------------------------------------------------------------------
#  Test rounding safety (mirrors RoundingSafety.v)
# ---------------------------------------------------------------------------


class TestRoundingSafety:
    """Test rounding safety analysis."""

    def setup_method(self):
        self.rs = RoundingSafety(eps_m=1e-7)  # Approximate float32

    def test_widen_interval(self):
        """Widening adds eps_m on both sides. Mirrors widen_lo, widen_hi."""
        lo, hi = self.rs.widen_interval(1.0, 2.0)
        assert lo == pytest.approx(1.0 - 1e-7)
        assert hi == pytest.approx(2.0 + 1e-7)

    def test_widen_strictly_larger(self):
        """Widened interval is strictly larger. Mirrors widen_strictly_larger."""
        wlo, whi = self.rs.widen_interval(1.0, 2.0)
        assert wlo < 1.0
        assert whi > 2.0

    def test_rounding_safe_inside(self):
        """Value inside interval is rounding-safe. Mirrors rounding_safe."""
        assert self.rs.rounding_safe(1.5, 1.0, 2.0)

    def test_rounding_safe_at_boundary(self):
        """Value at boundary is rounding-safe."""
        assert self.rs.rounding_safe(1.0, 1.0, 2.0)
        assert self.rs.rounding_safe(2.0, 1.0, 2.0)

    def test_rounding_not_safe_outside(self):
        """Value outside interval is not safe."""
        assert not self.rs.rounding_safe(3.0, 1.0, 2.0)

    def test_ibp_margin_base(self):
        """0 layers = 0 margin. Mirrors ibp_rounding_base."""
        assert self.rs.ibp_margin_after_k_layers(0) == 0.0

    def test_ibp_margin_step(self):
        """Each layer adds eps_m. Mirrors ibp_rounding_step."""
        assert self.rs.ibp_margin_after_k_layers(1) == pytest.approx(1e-7)
        assert self.rs.ibp_margin_after_k_layers(10) == pytest.approx(1e-6)

    def test_ibp_safe(self):
        """IBP safety check. Mirrors ibp_safe."""
        margin = self.rs.ibp_margin_after_k_layers(5)
        assert self.rs.ibp_safe(1.0, 1.0, 2.0, margin)
        assert self.rs.ibp_safe(1.0 - margin, 1.0, 2.0, margin)
        assert not self.rs.ibp_safe(0.0, 1.0, 2.0, margin)

    def test_crown_affine_positive_alpha(self):
        """CROWN with positive slope. Mirrors crown_affine_rounding."""
        lo, hi = self.rs.crown_affine_bounds(1.0, 2.0, alpha=0.5, beta=1.0)
        # alpha * lo + beta - eps_m, alpha * hi + beta + eps_m
        assert lo == pytest.approx(0.5 * 1.0 + 1.0 - 1e-7)
        assert hi == pytest.approx(0.5 * 2.0 + 1.0 + 1e-7)

    def test_crown_affine_negative_alpha(self):
        """CROWN with negative slope. Mirrors crown_affine_rounding_neg."""
        lo, hi = self.rs.crown_affine_bounds(1.0, 2.0, alpha=-0.5, beta=1.0)
        # alpha * hi + beta - eps_m, alpha * lo + beta + eps_m
        assert lo == pytest.approx(-0.5 * 2.0 + 1.0 - 1e-7)
        assert hi == pytest.approx(-0.5 * 1.0 + 1.0 + 1e-7)

    def test_double_rounding_error(self):
        """Double rounding error bounded by 2*eps_m. Mirrors double_rounding_error."""
        assert self.rs.double_rounding_error() == pytest.approx(2e-7)

    def test_width_increase(self):
        """Width increase formula. Mirrors ibp_width_increase."""
        assert self.rs.width_increase(1.0, 0.0) == pytest.approx(1.0)
        assert self.rs.width_increase(1.0, 0.5) == pytest.approx(2.0)
        assert self.rs.width_increase(1.0, 1e-6) == pytest.approx(1.0 + 2e-6)

    def test_float64_default(self):
        """Default eps_m is float64 machine epsilon."""
        rs = RoundingSafety()
        assert rs.eps_m == pytest.approx(2**-53)


# ---------------------------------------------------------------------------
#  Test from_convergent helper
# ---------------------------------------------------------------------------


class TestFromConvergent:
    """Test cauchy_from_convergent helper."""

    def test_harmonic_partial_sums(self):
        """Partial sums of 1/n^2 converge."""

        def _seq(n):
            return sum(1.0 / k**2 for k in range(1, n + 1)) if n > 0 else 0.0

        c = cauchy_from_convergent(_seq)
        val = c.approx(1e-6)
        assert val == pytest.approx(math.pi**2 / 6, abs=0.01)
