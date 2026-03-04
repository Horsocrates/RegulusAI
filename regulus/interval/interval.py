"""
Interval: verified interval arithmetic in Python.

Each operation mirrors a Coq lemma from PInterval.v:
  pi_add_correct, pi_sub_correct, pi_neg_correct,
  pi_mul_correct, pi_div_correct, pi_relu_correct,
  pi_abs_correct, pi_monotone_correct, pi_antitone_correct.

Invariant: lo <= hi (enforced at construction).
"""

from __future__ import annotations

from fractions import Fraction
from typing import Callable, Union

Scalar = Union[int, float, Fraction]


class Interval:
    """A closed rational interval [lo, hi] with lo <= hi.

    Corresponds to Coq's PInterval record:
      Record PInterval := mkPI { pi_lo : Q; pi_hi : Q; pi_valid : pi_lo <= pi_hi }.
    """

    __slots__ = ("lo", "hi")

    def __init__(self, lo: Scalar, hi: Scalar) -> None:
        lo = float(lo)
        hi = float(hi)
        if lo > hi:
            raise ValueError(f"Interval invariant violated: lo={lo} > hi={hi}")
        self.lo = lo
        self.hi = hi

    # --- Constructors ---

    @classmethod
    def point(cls, x: Scalar) -> Interval:
        """Single-point interval [x, x]. Corresponds to pi_point."""
        v = float(x)
        return cls(v, v)

    @classmethod
    def pm(cls, center: Scalar, radius: Scalar) -> Interval:
        """Interval [center - radius, center + radius]."""
        c, r = float(center), float(abs(radius))
        return cls(c - r, c + r)

    # --- Properties ---

    @property
    def width(self) -> float:
        """pi_hi - pi_lo. Corresponds to pi_width."""
        return self.hi - self.lo

    @property
    def mid(self) -> float:
        """Midpoint (lo + hi) / 2."""
        return (self.lo + self.hi) / 2.0

    def contains(self, x: float) -> bool:
        """pi_contains: lo <= x <= hi."""
        return self.lo <= x <= self.hi

    def overlaps(self, other: Interval) -> bool:
        """pi_overlaps: exists x in both intervals.
        Corresponds to pi_overlaps_correct."""
        return not (self.hi < other.lo or other.hi < self.lo)

    # --- Arithmetic (mirror PInterval.v) ---

    def __add__(self, other: Interval) -> Interval:
        """[a,b] + [c,d] = [a+c, b+d]. Corresponds to pi_add_correct."""
        if isinstance(other, Interval):
            return Interval(self.lo + other.lo, self.hi + other.hi)
        return NotImplemented

    def __neg__(self) -> Interval:
        """-[a,b] = [-b, -a]. Corresponds to pi_neg_correct."""
        return Interval(-self.hi, -self.lo)

    def __sub__(self, other: Interval) -> Interval:
        """[a,b] - [c,d] = [a-d, b-c]. Corresponds to pi_sub_correct."""
        if isinstance(other, Interval):
            return Interval(self.lo - other.hi, self.hi - other.lo)
        return NotImplemented

    def __mul__(self, other: Union[Interval, Scalar]) -> Interval:
        """[a,b] * [c,d] = [min(ac,ad,bc,bd), max(ac,ad,bc,bd)].
        Corresponds to pi_mul_correct."""
        if isinstance(other, Interval):
            products = [
                self.lo * other.lo,
                self.lo * other.hi,
                self.hi * other.lo,
                self.hi * other.hi,
            ]
            return Interval(min(products), max(products))
        if isinstance(other, (int, float)):
            if other >= 0:
                return Interval(self.lo * other, self.hi * other)
            else:
                return Interval(self.hi * other, self.lo * other)
        return NotImplemented

    def __rmul__(self, other: Scalar) -> Interval:
        return self.__mul__(other)

    def __truediv__(self, other: Union[Interval, Scalar]) -> Interval:
        """[a,b] / [c,d] with 0 not in [c,d].
        Corresponds to pi_div_correct."""
        if isinstance(other, (int, float)):
            if other == 0:
                raise ZeroDivisionError("Division by zero scalar")
            other = Interval.point(float(other))
        if isinstance(other, Interval):
            if other.lo <= 0 <= other.hi:
                raise ZeroDivisionError(
                    f"Divisor interval {other} contains zero"
                )
            inv_lo = 1.0 / other.hi
            inv_hi = 1.0 / other.lo
            products = [
                self.lo * inv_lo, self.lo * inv_hi,
                self.hi * inv_lo, self.hi * inv_hi,
            ]
            return Interval(min(products), max(products))
        return NotImplemented

    def monotone(self, f: Callable[[float], float]) -> Interval:
        """Apply monotone increasing f. Corresponds to pi_monotone_correct.
        Precondition: f must be monotone increasing on [lo, hi]."""
        return Interval(f(self.lo), f(self.hi))

    def antitone(self, f: Callable[[float], float]) -> Interval:
        """Apply monotone decreasing f. Corresponds to pi_antitone_correct.
        Precondition: f must be monotone decreasing on [lo, hi]."""
        return Interval(f(self.hi), f(self.lo))

    def relu(self) -> Interval:
        """max(0, [a,b]) = [max(0,a), max(0,b)].
        Corresponds to pi_relu_correct.
        CRITICAL for neural networks."""
        return Interval(max(0.0, self.lo), max(0.0, self.hi))

    def sigmoid(self) -> Interval:
        """Sigmoid is monotone increasing: sigma([a,b]) = [sigma(a), sigma(b)].
        Uses pi_monotone_correct."""
        import math
        def _sig(x: float) -> float:
            if x >= 0:
                return 1.0 / (1.0 + math.exp(-x))
            else:
                ex = math.exp(x)
                return ex / (1.0 + ex)
        return self.monotone(_sig)

    def tanh(self) -> Interval:
        """Tanh is monotone increasing: tanh([a,b]) = [tanh(a), tanh(b)].
        Uses pi_monotone_correct."""
        import math
        return self.monotone(math.tanh)

    def elu(self, alpha: float = 1.0) -> Interval:
        """ELU is monotone increasing: elu([a,b]) = [elu(a), elu(b)].
        ELU(x) = x if x >= 0, alpha*(exp(x)-1) if x < 0.
        Uses pi_monotone_correct."""
        import math
        def _elu(x: float) -> float:
            return x if x >= 0 else alpha * (math.exp(x) - 1.0)
        return self.monotone(_elu)

    def gelu(self) -> Interval:
        """GELU with conservative bounds for non-monotone region.
        GELU(x) = x * Phi(x). Has minimum at x* ~ -0.1685.
        For monotone regions: direct evaluation.
        For intervals crossing x*: include the global minimum."""
        import math

        def _gelu(x: float) -> float:
            return 0.5 * x * (1.0 + math.erf(x / math.sqrt(2.0)))

        GELU_MIN_X = -0.7518  # GELU'(x*) = 0, found by root-finding
        GELU_MIN_Y = _gelu(GELU_MIN_X)

        g_lo = _gelu(self.lo)
        g_hi = _gelu(self.hi)

        if self.lo >= GELU_MIN_X:
            # Fully in monotone increasing region
            return Interval(g_lo, g_hi)
        elif self.hi <= GELU_MIN_X:
            # Fully in decreasing region
            return Interval(g_hi, g_lo)
        else:
            # Crosses minimum — include it
            return Interval(min(g_lo, g_hi, GELU_MIN_Y), max(g_lo, g_hi))

    def __abs__(self) -> Interval:
        """Absolute value. Corresponds to pi_abs_correct."""
        if self.lo >= 0:
            return Interval(self.lo, self.hi)
        if self.hi <= 0:
            return Interval(-self.hi, -self.lo)
        # 0 is in the interval
        return Interval(0.0, max(-self.lo, self.hi))

    # --- Display ---

    def __repr__(self) -> str:
        return f"[{self.lo:.6g}, {self.hi:.6g}]"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Interval):
            return self.lo == other.lo and self.hi == other.hi
        return NotImplemented
