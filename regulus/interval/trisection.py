"""
Diagonal Trisection — Python port of ShrinkingIntervals_uncountable_ERR.v.

Constructs a real process (sequence of rational approximations) that is
guaranteed to differ from every element of a given enumeration.  This is
the computational heart of the nested-interval uncountability proof.

Key insight: trisection divides each interval into THREE equal parts and
selects the third that does NOT contain the enemy's approximation.  This
gives a structural gap of width/3 — unlike bisection, which can place the
enemy exactly at the midpoint.

Uses ``fractions.Fraction`` for exact arithmetic, matching the Coq
formalisation over Q.

Coq source: _tos_coq_clone/src/ShrinkingIntervals_uncountable_ERR.v
             (lines 2163-2700 for the trisection section)
Coq theorems preserved:
    trisect_left_width          — width == original_width / 3
    trisect_middle_width        — width == original_width / 3
    trisect_right_width         — width == original_width / 3
    trisect_step_nested         — later interval ⊆ earlier interval
    trisect_iter_v2_width       — width after n steps == initial_width / 3^n
    trisect_iter_v2_nested      — nesting over all steps
    smart_choice_excludes_conf  — chosen third excludes confidence interval
    diagonal_trisect_v2_differs — diagonal ≠ E(n) for all n  (separation)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from fractions import Fraction
from typing import Callable, Optional


# ---------------------------------------------------------------------------
#  Types
# ---------------------------------------------------------------------------

class TrisectChoice(Enum):
    """Which third of the interval to select.

    Corresponds to TrisectChoice inductive type in Coq.
    """
    LEFT = auto()
    MIDDLE = auto()
    RIGHT = auto()


@dataclass
class TrisectionState:
    """Interval state [left, right] for trisection.

    Corresponds to BisectionState record in Coq (reused for trisection).
    Uses Fraction for exact arithmetic.
    """
    left: Fraction
    right: Fraction

    @property
    def width(self) -> Fraction:
        """right - left.  Always >= 0 for valid states."""
        return self.right - self.left

    @property
    def midpoint(self) -> Fraction:
        """(left + right) / 2."""
        return (self.left + self.right) / 2


# ---------------------------------------------------------------------------
#  Trisection steps
# ---------------------------------------------------------------------------

def trisect_left(s: TrisectionState) -> TrisectionState:
    """Select the left third of the interval.

    Result: [left, left + width/3].
    Theorem: trisect_left_width — result width == width / 3.
    """
    w = s.width
    return TrisectionState(s.left, s.left + w / 3)


def trisect_middle(s: TrisectionState) -> TrisectionState:
    """Select the middle third of the interval.

    Result: [left + width/3, left + 2*width/3].
    Theorem: trisect_middle_width — result width == width / 3.
    """
    w = s.width
    return TrisectionState(s.left + w / 3, s.left + 2 * w / 3)


def trisect_right(s: TrisectionState) -> TrisectionState:
    """Select the right third of the interval.

    Result: [left + 2*width/3, right].
    Theorem: trisect_right_width — result width == width / 3.
    """
    w = s.width
    return TrisectionState(s.left + 2 * w / 3, s.right)


def trisect_step(
    choice: TrisectChoice, s: TrisectionState,
) -> TrisectionState:
    """Apply a trisection choice.

    Theorem: trisect_step_nested — result ⊆ s (left non-decreasing,
    right non-increasing).
    """
    if choice is TrisectChoice.LEFT:
        return trisect_left(s)
    elif choice is TrisectChoice.MIDDLE:
        return trisect_middle(s)
    else:
        return trisect_right(s)


# ---------------------------------------------------------------------------
#  Smart choice (excludes enemy's confidence interval)
# ---------------------------------------------------------------------------

def conf_below(approx: Fraction, delta: Fraction, boundary: Fraction) -> bool:
    """Is the confidence interval [approx-delta, approx+delta] entirely below boundary?

    Corresponds to conf_below in Coq.
    """
    return approx + delta < boundary


def conf_above(approx: Fraction, delta: Fraction, boundary: Fraction) -> bool:
    """Is the confidence interval entirely above boundary?

    Corresponds to conf_above in Coq.
    """
    return boundary < approx - delta


def smart_trisect_choice(
    s: TrisectionState, approx: Fraction, delta: Fraction,
) -> TrisectChoice:
    """Select the third that excludes the confidence interval [approx ± delta].

    Corresponds to smart_trisect_choice in Coq.

    Algorithm:
      - boundary1 = left + width/3   (end of left third)
      - boundary2 = left + 2*width/3 (end of middle third)
      - If confidence is entirely in left third → choose RIGHT
      - If confidence is entirely in right third → choose LEFT
      - Otherwise → choose RIGHT if confidence below boundary2, else LEFT

    Theorem: smart_choice_excludes_conf
        When 2*delta < width/3, the chosen third does not intersect
        [approx - delta, approx + delta].
    """
    w = s.width
    boundary1 = s.left + w / 3
    boundary2 = s.left + 2 * w / 3

    if conf_below(approx, delta, boundary1):
        return TrisectChoice.RIGHT
    if conf_above(approx, delta, boundary2):
        return TrisectChoice.LEFT
    if conf_below(approx, delta, boundary2):
        return TrisectChoice.RIGHT
    return TrisectChoice.LEFT


# ---------------------------------------------------------------------------
#  Synchronized parameters
# ---------------------------------------------------------------------------

def trisect_ref(n: int) -> int:
    """Synchronized reference index for step n.

    ref(n) = 48 * 3^n.

    This ensures that the Regular Cauchy bound at index ref equals
    the confidence radius delta:  2/ref = 1/(24*3^n) = delta(n).

    Corresponds to trisect_ref in Coq.
    """
    return 48 * (3 ** n)


def trisect_delta(n: int) -> Fraction:
    """Synchronized confidence radius for step n.

    delta(n) = 1 / (24 * 3^n).

    Corresponds to trisect_delta in Coq.
    """
    return Fraction(1, 24 * (3 ** n))


# ---------------------------------------------------------------------------
#  Trisection iteration
# ---------------------------------------------------------------------------

# An Enumeration maps step index n to a callable that, given a reference
# index ref, returns the rational approximation E(n)(ref) as a Fraction.
Enumeration = Callable[[int, int], Fraction]


def trisect_iter(
    E: Enumeration,
    initial: TrisectionState,
    n: int,
) -> TrisectionState:
    """N steps of smart trisection against enumeration E.

    At each step k (0 <= k < n):
        - Sample E(k) at synchronized index ref = 48 * 3^k
        - Compute confidence radius delta = 1/(24 * 3^k)
        - Choose the third that excludes E(k)'s confidence interval
        - Narrow the interval

    Theorem: trisect_iter_v2_width
        width after n steps == initial.width / 3^n.
    Theorem: trisect_iter_v2_nested
        For k <= m: interval(k) ⊇ interval(m).

    Parameters
    ----------
    E : callable(n, ref) -> Fraction
        Enumeration: E(n, ref) is the ref-th rational approximation of
        the n-th process.
    initial : TrisectionState
        Starting interval (typically [0, 1]).
    n : int
        Number of trisection steps.
    """
    state = initial
    for k in range(n):
        ref = trisect_ref(k)
        approx = E(k, ref)
        delta = trisect_delta(k)
        choice = smart_trisect_choice(state, approx, delta)
        state = trisect_step(choice, state)
    return state


def diagonal_trisect(
    E: Enumeration,
    initial: Optional[TrisectionState] = None,
    steps: int = 20,
) -> Callable[[int], Fraction]:
    """Construct a real process via diagonal trisection.

    Returns a function ``D(n)`` that gives the midpoint of the interval
    after n trisection steps.  D is a Cauchy process that differs from
    every E(k) by at least trisect_delta(k) / 2.

    Theorem: diagonal_trisect_v2_differs
        For all k: not_equiv(D, E(k)).

    Parameters
    ----------
    E : callable(n, ref) -> Fraction
        Enumeration of Cauchy processes.
    initial : TrisectionState or None
        Starting interval.  Default: [0, 1].
    steps : int
        Maximum number of precomputed steps.

    Returns
    -------
    D : callable(n) -> Fraction
        The diagonal process.  D(n) is the midpoint after n steps.
    """
    if initial is None:
        initial = TrisectionState(Fraction(0), Fraction(1))

    # Precompute states for efficiency
    states: list[TrisectionState] = [initial]
    state = initial
    for k in range(steps):
        ref = trisect_ref(k)
        approx = E(k, ref)
        delta = trisect_delta(k)
        choice = smart_trisect_choice(state, approx, delta)
        state = trisect_step(choice, state)
        states.append(state)

    def D(n: int) -> Fraction:
        """Midpoint of trisection interval after n steps."""
        if n < len(states):
            return states[n].midpoint
        # Extend on demand
        s = states[-1]
        for k in range(len(states) - 1, n):
            ref = trisect_ref(k)
            approx = E(k, ref)
            delta = trisect_delta(k)
            choice = smart_trisect_choice(s, approx, delta)
            s = trisect_step(choice, s)
            states.append(s)
        return s.midpoint

    return D
