"""
Verified Softmax Bounds — Python port of PInterval_Softmax.v.

Computes sound interval bounds for softmax(x)_i = f(x_i) / sum_j(f(x_j)),
parametric over any monotone-increasing strictly-positive function f.
For neural networks, instantiate f = math.exp.

The core technique is cross-multiplication: instead of proving
    f(lo) / D_lo  <=  f(x) / D_x
we prove the equivalent
    f(lo) * D_x   <=  f(x) * D_lo
which avoids division in the correctness argument.

Coq source: ToS-Coq/PInterval_Softmax.v
Coq theorems preserved:
    interval_softmax_lower_bound — cross-mul form: f(lo_i)*D_x <= f(x_i)*D_lo
    interval_softmax_upper_bound — cross-mul form: f(x_i)*D_hi <= f(hi_i)*D_x
    denom_positive               — denominator is strictly positive
    f_sum_monotone               — element-wise lo <= hi => f_sum(lo) <= f_sum(hi)
    f_sum_except_monotone        — same for f_sum_except
    softmax_cross_mul_lower      — nonneg cross-product inequality (lower)
    softmax_cross_mul_upper      — nonneg cross-product inequality (upper)
"""

from __future__ import annotations

from typing import Callable, List, Tuple


MonoPosFn = Callable[[float], float]


# ---------------------------------------------------------------------------
#  Summation helpers
# ---------------------------------------------------------------------------

def f_sum(xs: List[float], f: MonoPosFn) -> float:
    """Sum of f(x) for all x in xs.

    Corresponds to PInterval_Softmax.f_sum.
    """
    return sum(f(x) for x in xs)


def f_sum_except(
    xs: List[float], skip_idx: int, f: MonoPosFn,
) -> float:
    """Sum of f(x) for all x in xs, excluding index skip_idx.

    Corresponds to PInterval_Softmax.f_sum_except.
    """
    return sum(f(x) for i, x in enumerate(xs) if i != skip_idx)


# ---------------------------------------------------------------------------
#  Softmax bounds (single component)
# ---------------------------------------------------------------------------

def softmax_lower_bound(
    los: List[float],
    his: List[float],
    idx: int,
    f: MonoPosFn,
) -> float:
    """Lower bound for softmax component *idx*.

    Corresponds to PInterval_Softmax.interval_softmax_lower_bound.

    The bound is:  f(lo[idx]) / (f(lo[idx]) + f_sum_except(his, idx, f))

    Correctness (cross-multiplication form, no division needed for proof):
        f(lo_i) * (f(x_i) + S_except(xs))  <=  f(x_i) * (f(lo_i) + S_except(his))
    where S_except(ys) = sum_{j != i} f(ys_j).

    This holds because:
        - f monotone => f(lo_i) <= f(x_i)
        - f monotone => S_except(xs) <= S_except(his) for xs <= his element-wise
    """
    numerator = f(los[idx])
    denominator = numerator + f_sum_except(his, idx, f)
    if denominator <= 0:
        raise ValueError("Denominator non-positive — f must be strictly positive")
    return numerator / denominator


def softmax_upper_bound(
    los: List[float],
    his: List[float],
    idx: int,
    f: MonoPosFn,
) -> float:
    """Upper bound for softmax component *idx*.

    Corresponds to PInterval_Softmax.interval_softmax_upper_bound.

    The bound is:  f(hi[idx]) / (f(hi[idx]) + f_sum_except(los, idx, f))

    Correctness (cross-multiplication form):
        f(x_i) * (f(hi_i) + S_except(los))  <=  f(hi_i) * (f(x_i) + S_except(xs))
    """
    numerator = f(his[idx])
    denominator = numerator + f_sum_except(los, idx, f)
    if denominator <= 0:
        raise ValueError("Denominator non-positive — f must be strictly positive")
    return numerator / denominator


# ---------------------------------------------------------------------------
#  Full softmax interval
# ---------------------------------------------------------------------------

def interval_softmax(
    los: List[float],
    his: List[float],
    f: MonoPosFn,
) -> Tuple[List[float], List[float]]:
    """Sound interval bounds for all softmax components.

    Parameters
    ----------
    los : list[float]
        Lower bounds of input intervals.  len(los) == len(his).
    his : list[float]
        Upper bounds of input intervals.
    f : callable
        Monotone-increasing, strictly-positive function.
        For neural networks, use ``math.exp``.

    Returns
    -------
    (lower_bounds, upper_bounds) : tuple of lists
        For each index i:
            lower_bounds[i] <= softmax(x)_i <= upper_bounds[i]
        for all x with los[k] <= x[k] <= his[k].

    Note
    ----
    For numerical stability with ``math.exp``, the caller should apply
    a log-sum-exp shift *before* calling this function::

        shift = max(max(his), max(los))
        los_shifted = [lo - shift for lo in los]
        his_shifted = [hi - shift for hi in his]
        lb, ub = interval_softmax(los_shifted, his_shifted, math.exp)

    The shift cancels in the softmax ratio, so the bounds remain valid.
    """
    if len(los) != len(his):
        raise ValueError(
            f"los and his must have equal length, got {len(los)} vs {len(his)}"
        )
    n = len(los)
    lower_bounds: List[float] = []
    upper_bounds: List[float] = []
    for i in range(n):
        lower_bounds.append(softmax_lower_bound(los, his, i, f))
        upper_bounds.append(softmax_upper_bound(los, his, i, f))
    return lower_bounds, upper_bounds
