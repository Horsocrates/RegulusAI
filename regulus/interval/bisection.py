"""
Bisection algorithm — Python mirror of IVT.v extraction.

Corresponds to:
  bisection_step  : ContinuousFunction -> BisectionState -> BisectionState
  bisection_iter  : ContinuousFunction -> BisectionState -> nat -> BisectionState
  bisection_process : ContinuousFunction -> Q -> Q -> RealProcess

Coq-proven properties preserved here:
  - Width halves each step: width(n) = (b-a) / 2^n
  - Nested: left endpoints non-decreasing, right endpoints non-increasing
  - Sign preservation (weak): f(left) <= 0, f(right) >= 0
  - Cauchy: the midpoint process is Cauchy
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class BisectionState:
    """Corresponds to Coq's BisectionState record."""

    left: float
    right: float


def bisection_step(f: Callable[[float], float], s: BisectionState) -> BisectionState:
    """One step of bisection. Corresponds to IVT.bisection_step.

    Uses decidable comparison (f(mid) < 0), not classical logic.
    """
    mid = (s.left + s.right) / 2.0
    if f(mid) < 0:
        return BisectionState(left=mid, right=s.right)
    else:
        return BisectionState(left=s.left, right=mid)


def bisection_iter(
    f: Callable[[float], float], a: float, b: float, n: int
) -> BisectionState:
    """N steps of bisection. Corresponds to IVT.bisection_iter.

    Returns the interval [left, right] after n bisection steps.
    Width = (b - a) / 2^n.
    """
    state = BisectionState(left=a, right=b)
    for _ in range(n):
        state = bisection_step(f, state)
    return state


def bisection_process(
    f: Callable[[float], float], a: float, b: float, n: int
) -> float:
    """Midpoint of bisection after n steps. Corresponds to IVT.bisection_process.

    This is the RealProcess: nat -> Q.
    """
    s = bisection_iter(f, a, b, n)
    return (s.left + s.right) / 2.0


def find_root(
    f: Callable[[float], float],
    a: float,
    b: float,
    steps: int = 53,
) -> BisectionState:
    """Find a root of f in [a, b] using verified bisection.

    Preconditions (from IVT_process):
      - a < b
      - f uniformly continuous on [a, b]
      - f(a) < 0 < f(b)  (or f(a) > 0 > f(b), handled by sign flip)

    Returns interval containing root. Width = (b-a) / 2^steps.
    53 steps gives ~machine epsilon for float64.
    """
    if f(a) > 0 and f(b) < 0:
        # Flip: negate f to satisfy f(a) < 0 < f(b)
        return bisection_iter(lambda x: -f(x), a, b, steps)

    if not (f(a) <= 0 <= f(b)):
        raise ValueError(
            f"Precondition violated: need f(a) <= 0 <= f(b), "
            f"got f({a})={f(a)}, f({b})={f(b)}"
        )

    return bisection_iter(f, a, b, steps)
