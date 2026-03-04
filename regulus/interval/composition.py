"""
Interval Composition — Python port of PInterval_Composition.v.

Re-anchoring, MaxPool, ResBlock (skip connection), and chain width
analysis for layer-by-layer interval propagation in neural networks.

Coq source: ToS-Coq/PInterval_Composition.v
Coq theorems preserved:
    pi_reanchor_width               — width(reanchor(I, eps)) == 2*eps
    pi_reanchor_contains_midpoint   — midpoint(I) in reanchor(I, eps)
    pi_reanchor_loses_containment   — WARNING: not all x in I are in reanchor
    pi_max_pair_correct             — max(x,y) in pi_max_pair(I,J)
    pi_max_pair_width               — width <= max(width_I, width_J)
    pi_residual_correct             — x + f(x) in pi_residual(I, F)
    pi_resblock_width_bound         — width(relu(residual)) <= w_I + w_F
    chain_width_product             — chain_width == factor_product * input_width
    reanchored_depth_independent    — final_width <= last_factor * 2*eps
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from typing import List

from regulus.interval.interval import Interval


# ---------------------------------------------------------------------------
#  Re-anchoring
# ---------------------------------------------------------------------------

def pi_midpoint(I: Interval) -> float:
    """Midpoint (lo + hi) / 2.

    Corresponds to PInterval_Composition.pi_midpoint.
    """
    return (I.lo + I.hi) / 2.0


def pi_reanchor(I: Interval, eps: float) -> Interval:
    """Collapse interval to [midpoint - eps, midpoint + eps].

    Corresponds to PInterval_Composition.pi_reanchor.

    Theorem: pi_reanchor_width — width == 2 * eps.
    Theorem: pi_reanchor_contains_midpoint — midpoint(I) is contained.

    WARNING (Coq-proven, pi_reanchor_loses_containment):
        Re-anchoring is LOSSY — it does NOT preserve interval containment.
        Counterexample: I=[0,10], eps=1 → reanchor=[4,6], loses x=0.

    Parameters
    ----------
    I : Interval
        Source interval.
    eps : float
        Half-width of result (must be >= 0).
    """
    if eps < 0:
        raise ValueError(f"eps must be >= 0, got {eps}")
    mid = pi_midpoint(I)
    return Interval(mid - eps, mid + eps)


# ---------------------------------------------------------------------------
#  MaxPool (pi_max_pair)
# ---------------------------------------------------------------------------

def pi_max_pair(I: Interval, J: Interval) -> Interval:
    """Element-wise max of two intervals: [max(lo), max(hi)].

    Corresponds to PInterval_Composition.pi_max_pair.

    Theorem: pi_max_pair_correct
        If x in I and y in J, then max(x, y) in pi_max_pair(I, J).
    Theorem: pi_max_pair_width
        width(result) <= max(width(I), width(J)).
    """
    return Interval(max(I.lo, J.lo), max(I.hi, J.hi))


def pi_max_fold(intervals: List[Interval]) -> Interval:
    """MaxPool over a list of intervals.

    Corresponds to PInterval_Composition.pi_max_fold.
    Applies pi_max_pair pairwise from left to right.
    """
    if not intervals:
        raise ValueError("Cannot fold max over empty list")
    return reduce(pi_max_pair, intervals)


# ---------------------------------------------------------------------------
#  ResBlock / Skip Connection
# ---------------------------------------------------------------------------

def pi_residual(x_interval: Interval, f_interval: Interval) -> Interval:
    """Skip connection: interval for x + f(x).

    Corresponds to PInterval_Composition.pi_residual.
    Defined as pi_add(x_interval, f_interval).

    Theorem: pi_residual_correct
        If x in x_interval and f(x) in f_interval,
        then x + f(x) in pi_residual(x_interval, f_interval).
    """
    return x_interval + f_interval


def pi_resblock_width_bound(
    input_width: float, subnet_width: float,
) -> float:
    """Upper bound on ReLU(residual) output width.

    Theorem: pi_resblock_width_bound
        width(relu(x + f(x))) <= width(x) + width(f(x)).

    In practice relu can only shrink the interval, so this is a safe
    upper bound.
    """
    return input_width + subnet_width


# ---------------------------------------------------------------------------
#  Chain width analysis
# ---------------------------------------------------------------------------

@dataclass
class LayerSpec:
    """Single-layer width amplification factor.

    Corresponds to PInterval_Composition.LayerSpec record.
    ``factor`` is the multiplicative width blowup of one layer (>= 0).
    """

    factor: float

    def __post_init__(self) -> None:
        if self.factor < 0:
            raise ValueError(
                f"Layer factor must be >= 0, got {self.factor}"
            )


def chain_width(layers: List[LayerSpec], input_width: float) -> float:
    """Output width after passing through a chain of layers.

    Corresponds to PInterval_Composition.chain_width.

    Theorem: chain_width_product
        chain_width(layers, w) == factor_product(layers) * w.
    """
    w = input_width
    for layer in layers:
        w = layer.factor * w
    return w


def factor_product(layers: List[LayerSpec]) -> float:
    """Product of all layer factors.

    Corresponds to PInterval_Composition.factor_product.
    """
    result = 1.0
    for layer in layers:
        result *= layer.factor
    return result


def reanchored_chain_width(
    layers: List[LayerSpec], eps: float,
) -> float:
    """Width after re-anchoring then passing through layers.

    Re-anchoring produces width 2*eps (pi_reanchor_width),
    then each layer multiplies by its factor.

    Theorem: reanchored_depth_independent
        For a single trailing layer with factor f:
        result <= f * 2 * eps,  independent of prior depth.
    """
    return chain_width(layers, 2.0 * eps)


def conv_bn_relu_factor(
    bn_scale: float, conv_weight_l1: float,
) -> float:
    """Width factor for a Conv-BN-ReLU block.

    factor = |bn_scale| * L1_norm(conv_weights).
    ReLU factor is 1 (width cannot increase through ReLU).

    Corresponds to PInterval_Composition.conv_bn_relu_spec.
    """
    return abs(bn_scale) * conv_weight_l1
