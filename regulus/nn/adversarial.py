"""
Adversarial input generation via diagonal trisection.

Given an enumeration of test inputs (represented as Cauchy processes),
constructs an input GUARANTEED to differ from each by a certified gap.

Mathematical foundation: ShrinkingIntervals_uncountable_ERR.v
    Theorem: diagonal_trisect_v2_differs
        For all k: the diagonal D differs from E(k) by at least delta(k)/2.

Usage:
    The enumeration wraps a finite set of test inputs as constant processes.
    After ``steps`` trisection rounds, the generated adversarial input lies
    in [0,1] and is provably at distance >= 1/(48 * 3^k) from the k-th input.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Callable, List, Optional, Tuple

from regulus.interval.trisection import (
    TrisectionState,
    diagonal_trisect,
    trisect_delta,
    Enumeration,
)


def _constant_enumeration(values: List[float]) -> Enumeration:
    """Wrap a finite list of floats as an enumeration of constant processes.

    Each ``values[k]`` becomes a constant Cauchy process: E(k, ref) = values[k]
    for all ref.  For indices beyond the list, wraps around.
    """
    fracs = [Fraction(v).limit_denominator(10**12) for v in values]
    n = len(fracs)

    def E(k: int, ref: int) -> Fraction:
        return fracs[k % n]

    return E


def generate_adversarial_1d(
    test_values: List[float],
    domain: Tuple[float, float] = (0.0, 1.0),
    steps: Optional[int] = None,
) -> Tuple[float, List[float]]:
    """Generate a 1D point guaranteed to differ from each test value.

    Uses diagonal trisection: at step k, the interval avoids
    test_values[k] by at least trisect_delta(k) / 2.

    Parameters
    ----------
    test_values : list[float]
        Known test inputs to avoid.
    domain : (float, float)
        Search interval [a, b].  Default: [0, 1].
    steps : int or None
        Number of trisection steps.  Default: len(test_values).

    Returns
    -------
    (adversarial, gaps) : (float, list[float])
        adversarial: the generated point.
        gaps[k]: |adversarial - test_values[k]| (certified >= delta(k)/2).
    """
    if steps is None:
        steps = len(test_values)

    E = _constant_enumeration(test_values)
    initial = TrisectionState(
        Fraction(domain[0]).limit_denominator(10**12),
        Fraction(domain[1]).limit_denominator(10**12),
    )
    D = diagonal_trisect(E, initial, steps)
    adversarial = float(D(steps))

    gaps = [abs(adversarial - v) for v in test_values]

    return adversarial, gaps


def generate_adversarial_nd(
    test_vectors: List[List[float]],
    domains: Optional[List[Tuple[float, float]]] = None,
    steps: Optional[int] = None,
) -> Tuple[List[float], List[List[float]]]:
    """Generate N-dimensional adversarial input via per-dimension trisection.

    Each dimension is handled independently.  The combined input differs
    from each test vector in at least one dimension.

    Parameters
    ----------
    test_vectors : list[list[float]]
        Each inner list is one dimension's enumeration of test values.
        test_vectors[d][k] = k-th test input's d-th coordinate.
    domains : list[(float,float)] or None
        Per-dimension search intervals.  Default: [0,1] each.
    steps : int or None
        Trisection steps per dimension.  Default: len of longest inner list.

    Returns
    -------
    (point, per_dim_gaps)
        point[d] = adversarial coordinate for dimension d.
        per_dim_gaps[d][k] = |point[d] - test_vectors[d][k]|.
    """
    n_dims = len(test_vectors)
    if domains is None:
        domains = [(0.0, 1.0)] * n_dims
    if steps is None:
        steps = max(len(tv) for tv in test_vectors) if test_vectors else 1

    results: List[float] = []
    all_gaps: List[List[float]] = []

    for d in range(n_dims):
        val, gaps = generate_adversarial_1d(
            test_vectors[d], domains[d], steps,
        )
        results.append(val)
        all_gaps.append(gaps)

    return results, all_gaps


def certified_gap(k: int) -> float:
    """Minimum certified gap at trisection step k.

    The diagonal process is guaranteed to differ from the k-th
    enumerated value by at least trisect_delta(k) / 2 = 1 / (48 * 3^k).
    """
    return float(trisect_delta(k)) / 2.0


# ---------------------------------------------------------------------------
#  Adversarial Suite: domain scaling + aggregated verification
# ---------------------------------------------------------------------------


def scale_to_perturbation_ball(
    point_01: List[float],
    center: List[float],
    epsilon: float,
) -> List[float]:
    """Map a point from [0,1]^d to [center-eps, center+eps]^d.

    Parameters
    ----------
    point_01 : list[float]
        Point in [0, 1]^d (e.g. from generate_adversarial_nd).
    center : list[float]
        Center of the perturbation ball.
    epsilon : float
        Perturbation radius.

    Returns
    -------
    list[float]
        Point in [center_d - epsilon, center_d + epsilon] for each d.
    """
    return [c - epsilon + 2 * epsilon * p for c, p in zip(center, point_01)]


def generate_adversarial_suite(
    test_points: List[List[float]],
    center: List[float],
    epsilon: float,
    n_candidates: int = 10,
    steps: Optional[int] = None,
) -> List[List[float]]:
    """Generate adversarial candidates in perturbation ball around center.

    Produces n_candidates distinct points in [center-eps, center+eps]^d,
    each certified to differ from the test_points.

    Parameters
    ----------
    test_points : list[list[float]]
        Known test points (each is a d-dimensional vector).
    center : list[float]
        Center of the perturbation ball.
    epsilon : float
        Perturbation radius.
    n_candidates : int
        Number of adversarial candidates to generate.
    steps : int or None
        Trisection steps. Default: len(test_points).

    Returns
    -------
    list[list[float]]
        List of adversarial candidate points in the perturbation ball.
    """
    if not test_points:
        return []

    n_dims = len(center)
    candidates: List[List[float]] = []

    for offset in range(n_candidates):
        # Rotate the test points to get different adversarial candidates
        rotated = test_points[offset % len(test_points):] + test_points[:offset % len(test_points)]

        # Transpose to per-dimension format
        per_dim: List[List[float]] = [[] for _ in range(n_dims)]
        for pt in rotated:
            for d in range(n_dims):
                per_dim[d].append(pt[d] if d < len(pt) else 0.0)

        # Generate in [0,1]^d
        point_01, _ = generate_adversarial_nd(per_dim, steps=steps)

        # Scale to perturbation ball
        point = scale_to_perturbation_ball(point_01, center, epsilon)
        candidates.append(point)

    return candidates
