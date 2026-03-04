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


# ---------------------------------------------------------------------------
#  Bridge: predict block factors from interval model
# ---------------------------------------------------------------------------

def predict_block_factors(
    interval_blocks: list,
) -> List[LayerSpec]:
    """Inspect IntervalSequential blocks and predict width amplification factors.

    For each block, estimates the worst-case width factor from the layer
    weights:
      - IntervalLinear: factor = max row L1-norm (spectral-like bound)
      - IntervalConv2d: factor = max over output channels of L1-norm of kernel
      - IntervalBatchNorm: factor = max(|scale|)
      - IntervalReLU / IntervalSigmoid / IntervalTanh: factor = 1.0 (monotone)
      - IntervalFlatten / IntervalMaxPool2d / IntervalAvgPool2d: factor = 1.0
      - IntervalSoftmax: factor = 1.0 (output in [0,1])

    The block factor is the product of individual layer factors.

    This feeds into chain_width_product and reanchored_depth_independent
    (PInterval_Composition.v) for adaptive reanchoring control.

    Parameters
    ----------
    interval_blocks : list of IntervalSequential
        Blocks from ReanchoredIntervalModel.interval_blocks.

    Returns
    -------
    list of LayerSpec
        One LayerSpec per block with the predicted amplification factor.
    """
    import numpy as np

    specs: List[LayerSpec] = []
    for block in interval_blocks:
        block_factor = 1.0
        layers = block.layers if hasattr(block, 'layers') else [block]

        for layer in layers:
            # Use duck-typing for robustness (works with mocks and subclasses)
            layer_type = type(layer).__name__

            if hasattr(layer, 'weight') and hasattr(layer, 'bias'):
                w = np.abs(layer.weight)
                if w.ndim == 2:
                    # Linear layer: max row L1-norm
                    # max_i sum_j |W[i,j]|
                    # This is the exact worst-case width amplification for
                    # the positive/negative weight decomposition
                    factor = float(np.max(np.sum(w, axis=1)))
                    block_factor *= factor
                elif w.ndim == 4:
                    # Conv2d layer: max output-channel L1-norm of kernel
                    # (C_out, C_in, kH, kW)
                    per_channel = np.sum(w, axis=(1, 2, 3))  # (C_out,)
                    factor = float(np.max(per_channel))
                    block_factor *= factor
                else:
                    block_factor *= 1.0

            elif hasattr(layer, 'weight') and not hasattr(layer, 'bias'):
                # Weight-only layer (e.g. mock Linear without bias)
                w = np.abs(layer.weight)
                if w.ndim == 2:
                    factor = float(np.max(np.sum(w, axis=1)))
                    block_factor *= factor
                elif w.ndim == 4:
                    per_channel = np.sum(w, axis=(1, 2, 3))
                    factor = float(np.max(per_channel))
                    block_factor *= factor
                else:
                    block_factor *= 1.0

            elif hasattr(layer, 'scale') and hasattr(layer, 'shift'):
                # BatchNorm: factor = max(|scale|)
                factor = float(np.max(np.abs(layer.scale)))
                block_factor *= factor

            elif "ResBlock" in layer_type:
                # ResBlock: x + f(x) → width(relu(x + f(x))) ≤ w(x) + w(f(x))
                # Conservative: treat as factor 2 (skip adds f-path width)
                block_factor *= 2.0

            else:
                # Activations (ReLU, Sigmoid, Tanh, GELU, ELU, Softmax),
                # Flatten, MaxPool, AvgPool: factor ≤ 1
                block_factor *= 1.0

        specs.append(LayerSpec(max(block_factor, 1e-15)))

    return specs


def predict_optimal_eps(
    layer_specs: List[LayerSpec],
    block_index: int,
    target_output_width: float,
) -> float:
    """Predict optimal reanchor eps for a given block.

    Using chain_width_product: output_width = product(remaining_factors) * 2*eps.
    Solving for eps: eps = target_output_width / (2 * remaining_factor_product).

    This implements the key idea: use composition theorem predictions
    to allocate per-block reanchor eps adaptively.

    Parameters
    ----------
    layer_specs : list of LayerSpec
        Per-block factors from predict_block_factors().
    block_index : int
        Current block index (reanchor happens AFTER this block).
    target_output_width : float
        Desired output width at end of chain.

    Returns
    -------
    float
        Optimal reanchor eps (half-width).
    """
    # Remaining blocks are [block_index+1, ..., n-1]
    remaining = layer_specs[block_index + 1:]
    remaining_product = factor_product(remaining)

    if remaining_product < 1e-15:
        return target_output_width / 2.0

    # reanchored_depth_independent: output <= remaining_product * 2 * eps
    # Solve: eps = target / (2 * remaining_product)
    return target_output_width / (2.0 * remaining_product)
