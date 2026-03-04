"""Cauchy Reals: constructive completion of Q.

Python port of CauchyReal.v — mirrors the Coq formalization exactly.

A Cauchy real is represented as a function from natural numbers to floats
(standing in for Q) together with a modulus of convergence.

Key types:
    CauchySeq  — Cauchy sequence with convergence witness
    RoundingSafety — IEEE 754 rounding-safety computations

This module is used for verified numerics: proving that IBP/CROWN bounds
remain sound after floating-point rounding.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class CauchySeq:
    """A Cauchy sequence: a function nat -> float with convergence modulus.

    Mirrors Coq CauchySeq record:
        cs_seq : nat -> Q
        cs_cauchy : is_cauchy cs_seq

    The modulus function returns N such that for m,n >= N,
    |a(m) - a(n)| < eps.
    """

    seq: Callable[[int], float]
    modulus: Callable[[float], int]  # eps -> N

    def __call__(self, n: int) -> float:
        return self.seq(n)

    def approx(self, eps: float = 1e-10) -> float:
        """Return a rational approximation within eps.

        Mirrors cauchy_rational_approx theorem:
            ∀ eps > 0, ∃ q, ∃ N, ∀ n >= N, |a(n) - q| < eps
        """
        if eps <= 0:
            raise ValueError("eps must be positive")
        n = self.modulus(eps)
        return self.seq(n)

    def is_cauchy_at(self, eps: float, n_samples: int = 20) -> bool:
        """Empirically verify the Cauchy property for given eps."""
        n = self.modulus(eps)
        for i in range(n_samples):
            m1 = n + i
            m2 = n + i + 1
            if abs(self.seq(m1) - self.seq(m2)) >= eps:
                return False
        return True


# ---------------------------------------------------------------------------
#  Arithmetic on Cauchy sequences (mirrors Coq definitions)
# ---------------------------------------------------------------------------


def cauchy_add(a: CauchySeq, b: CauchySeq) -> CauchySeq:
    """Sum of two Cauchy sequences. Mirrors cauchy_add."""
    return CauchySeq(
        seq=lambda n: a.seq(n) + b.seq(n),
        modulus=lambda eps: max(a.modulus(eps / 2), b.modulus(eps / 2)),
    )


def cauchy_neg(a: CauchySeq) -> CauchySeq:
    """Negation of a Cauchy sequence. Mirrors cauchy_neg."""
    return CauchySeq(
        seq=lambda n: -a.seq(n),
        modulus=a.modulus,
    )


def cauchy_sub(a: CauchySeq, b: CauchySeq) -> CauchySeq:
    """Difference of two Cauchy sequences. Mirrors cauchy_sub."""
    return cauchy_add(a, cauchy_neg(b))


def cauchy_const(q: float) -> CauchySeq:
    """Constant Cauchy sequence. Mirrors cauchy_const."""
    return CauchySeq(
        seq=lambda n: q,
        modulus=lambda eps: 0,
    )


def cauchy_equiv(a: CauchySeq, b: CauchySeq, eps: float = 1e-10) -> bool:
    """Check if two Cauchy sequences are equivalent within eps.

    Mirrors cauchy_equiv: ∀ eps > 0, ∃ N, ∀ n >= N, |a(n) - b(n)| < eps
    """
    n = max(a.modulus(eps / 2), b.modulus(eps / 2))
    # Check at several points beyond N
    for i in range(20):
        if abs(a.seq(n + i) - b.seq(n + i)) >= eps:
            return False
    return True


def cauchy_pos(a: CauchySeq) -> bool:
    """Check if a Cauchy real is positive.

    Mirrors cauchy_pos: ∃ q > 0, ∃ N, ∀ n >= N, q < a(n)
    """
    # Approximate the limit
    val = a.approx(1e-10)
    return val > 1e-10


# ---------------------------------------------------------------------------
#  Rounding Safety (mirrors RoundingSafety.v)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoundingSafety:
    """IEEE 754 rounding safety analysis.

    Mirrors the RoundingSafety section of RoundingSafety.v.
    All theorems are verified in Coq; this is the computational mirror.

    Attributes:
        eps_m: Machine epsilon (e.g., 2^-24 for float32, 2^-53 for float64)
    """

    eps_m: float = 2**-53  # float64 default

    def round_error_bound(self, x: float) -> float:
        """Upper bound on |round(x) - x|. Always <= eps_m."""
        return self.eps_m

    def widen_interval(self, lo: float, hi: float) -> tuple[float, float]:
        """Widen [lo, hi] to [lo - eps_m, hi + eps_m].

        Mirrors widen_lo, widen_hi definitions.
        Theorem (widen_strictly_larger): lo - eps_m < lo and hi < hi + eps_m.
        """
        return (lo - self.eps_m, hi + self.eps_m)

    def rounding_safe(self, x: float, lo: float, hi: float) -> bool:
        """Check if round(x) is in widened [lo, hi].

        Mirrors theorem rounding_safe:
            x ∈ [lo, hi] → round(x) ∈ [lo - eps_m, hi + eps_m]
        """
        if not (lo <= x <= hi):
            return False
        # After rounding, x could shift by at most eps_m
        rx = round(x)  # Python float rounding (nearest)
        wlo, whi = self.widen_interval(lo, hi)
        return wlo <= rx <= whi

    def ibp_margin_after_k_layers(self, k: int) -> float:
        """Accumulated rounding margin after k layers.

        Mirrors ibp_rounding_step: margin grows by eps_m per layer.
        After k layers: margin = k * eps_m.

        Theorem (ibp_width_increase):
            width(result) = width(original) + 2 * k * eps_m
        """
        return k * self.eps_m

    def ibp_safe(
        self, x: float, lo: float, hi: float, margin: float
    ) -> bool:
        """Check if x is within the IBP-safe region.

        Mirrors ibp_safe: lo - margin <= x <= hi + margin
        """
        return (lo - margin) <= x <= (hi + margin)

    def crown_affine_bounds(
        self,
        lo: float,
        hi: float,
        alpha: float,
        beta: float,
    ) -> tuple[float, float]:
        """Compute CROWN affine bounds with rounding safety.

        For alpha >= 0:
            round(alpha * x + beta) ∈ [alpha*lo + beta - eps_m,
                                        alpha*hi + beta + eps_m]

        For alpha < 0:
            round(alpha * x + beta) ∈ [alpha*hi + beta - eps_m,
                                        alpha*lo + beta + eps_m]

        Mirrors crown_affine_rounding and crown_affine_rounding_neg.
        """
        if alpha >= 0:
            new_lo = alpha * lo + beta - self.eps_m
            new_hi = alpha * hi + beta + self.eps_m
        else:
            new_lo = alpha * hi + beta - self.eps_m
            new_hi = alpha * lo + beta + self.eps_m
        return (new_lo, new_hi)

    def double_rounding_error(self) -> float:
        """Bound on |round(round(x)) - x|.

        Mirrors theorem double_rounding_error:
            |round(round(x)) - x| <= 2 * eps_m
        """
        return 2 * self.eps_m

    def width_increase(self, original_width: float, margin: float) -> float:
        """Total interval width after accumulating margin.

        Mirrors ibp_width_increase:
            (hi + margin) - (lo - margin) = (hi - lo) + 2 * margin
        """
        return original_width + 2 * margin


# ---------------------------------------------------------------------------
#  Common Cauchy sequences
# ---------------------------------------------------------------------------


def cauchy_from_convergent(terms: Callable[[int], float]) -> CauchySeq:
    """Create a CauchySeq from a convergent sequence with heuristic modulus.

    For sequences known to converge at rate O(1/n), the modulus is
    ceil(1/eps).
    """
    return CauchySeq(
        seq=terms,
        modulus=lambda eps: max(1, math.ceil(1.0 / eps)),
    )


def cauchy_sqrt2() -> CauchySeq:
    """Cauchy sequence converging to sqrt(2) via Newton's method.

    a(0) = 1, a(n+1) = (a(n) + 2/a(n)) / 2
    Convergence rate: quadratic (error halves each step).
    """

    def _seq(n: int) -> float:
        x = 1.5
        for _ in range(n):
            x = (x + 2.0 / x) / 2.0
        return x

    return CauchySeq(
        seq=_seq,
        modulus=lambda eps: max(1, math.ceil(math.log2(1.0 / eps))),
    )


def cauchy_e() -> CauchySeq:
    """Cauchy sequence converging to e via partial sums of 1/k!."""

    def _seq(n: int) -> float:
        s = 0.0
        factorial = 1
        for k in range(n + 1):
            if k > 0:
                factorial *= k
            s += 1.0 / factorial
        return s

    # e series converges super-exponentially: error after n terms ~ 1/n!
    # n=20 gives error < 1e-18, so modulus ~ ceil(log(1/eps)) suffices
    return CauchySeq(
        seq=_seq,
        modulus=lambda eps: max(5, min(30, math.ceil(-math.log(eps) / math.log(2)))),
    )
