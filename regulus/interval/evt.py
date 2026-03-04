"""
Verified Argmax and Extremum — Python port of EVT_idx.v.

Implements grid-based argmax with deterministic tie-breaking and
supremum process for function extremization.

Coq source: _tos_coq_clone/src/EVT_idx.v
Coq theorems preserved:
    argmax_idx_bound       — result < len(lst)
    argmax_idx_maximizes   — f(lst[result]) >= f(lst[k]) for all k
    max_on_grid_attained   — max_on_grid == f(argmax_on_grid)
    grid_value_le_max      — f(grid[k]) <= max_on_grid for all k
    sup_process_is_Cauchy  — refinement sequence converges
    EVT_strong_process     — sup_process(n) == f(argmax_process(n))
"""

from __future__ import annotations

from typing import Callable, List

ScalarFn = Callable[[float], float]


# ---------------------------------------------------------------------------
#  Grid construction
# ---------------------------------------------------------------------------

def grid_point(a: float, b: float, n: int, k: int) -> float:
    """k-th point of an (n+1)-point grid on [a, b].

    Corresponds to EVT_idx.grid_point.
    Theorem: grid_point(a,b,n,0) == a, grid_point(a,b,n,n) == b.
    """
    if n <= 0:
        raise ValueError("Grid resolution n must be > 0")
    return a + k * (b - a) / n


def grid_list(a: float, b: float, n: int) -> List[float]:
    """List of n+1 evenly spaced points in [a, b].

    Corresponds to EVT_idx.grid_list.
    """
    if n <= 0:
        raise ValueError("Grid resolution n must be > 0")
    return [a + k * (b - a) / n for k in range(n + 1)]


# ---------------------------------------------------------------------------
#  Verified argmax
# ---------------------------------------------------------------------------

def find_max_idx_acc(
    f: ScalarFn,
    lst: List[float],
    curr_idx: int,
    best_idx: int,
    best_val: float,
) -> int:
    """Accumulator-based argmax traversal.

    Corresponds to EVT_idx.find_max_idx_acc.

    Uses ``<=`` comparison (Coq: Qle_bool): when f(x) equals best_val,
    the accumulator updates to the current index.  Since traversal is
    left-to-right, the *last* index with the maximum value wins.
    """
    for i, x in enumerate(lst):
        fx = f(x)
        if best_val <= fx:          # Matches Coq's Qle_bool
            best_idx = curr_idx + i
            best_val = fx
    return best_idx


def argmax_idx(f: ScalarFn, lst: List[float], default: float = 0.0) -> int:
    """Index of the maximizer of f over lst.

    Corresponds to EVT_idx.argmax_idx.

    Theorem: argmax_idx_bound   — result < len(lst)
    Theorem: argmax_idx_maximizes — f(lst[result]) >= f(lst[k]) for all k

    Parameters
    ----------
    f : callable
        Evaluation function.
    lst : list
        Non-empty list of candidate values.
    default : float
        Unused (present for Coq signature compatibility).

    Returns
    -------
    int
        Index into *lst* of the element where f is maximized.
    """
    if not lst:
        return 0
    return find_max_idx_acc(f, lst[1:], 1, 0, f(lst[0]))


# ---------------------------------------------------------------------------
#  Grid-based extremum
# ---------------------------------------------------------------------------

def argmax_on_grid(f: ScalarFn, a: float, b: float, n: int) -> float:
    """Value at which f is maximized on an (n+1)-point grid over [a, b].

    Corresponds to EVT_idx.argmax_on_grid.
    """
    pts = grid_list(a, b, n)
    idx = argmax_idx(f, pts)
    return pts[idx]


def max_on_grid(f: ScalarFn, a: float, b: float, n: int) -> float:
    """Maximum value of f on an (n+1)-point grid over [a, b].

    Corresponds to EVT_idx.max_on_grid.
    Theorem: max_on_grid_attained — result == f(argmax_on_grid(f,a,b,n)).
    """
    return f(argmax_on_grid(f, a, b, n))


def sup_process(f: ScalarFn, a: float, b: float, n: int) -> float:
    """Supremum approximation at refinement level n.

    Corresponds to EVT_idx.sup_process.
    Returns max_on_grid(f, a, b, n+1) — grid with n+2 points.

    Theorem: sup_process_is_Cauchy — the sequence converges as n → ∞.
    Theorem: EVT_strong_process — sup_process(n) == f(argmax_process(n)).
    """
    return max_on_grid(f, a, b, n + 1)


def argmax_process(f: ScalarFn, a: float, b: float, n: int) -> float:
    """Approximate maximizer at refinement level n.

    Corresponds to EVT_idx.argmax_process.
    """
    return argmax_on_grid(f, a, b, n + 1)
