"""
IntervalTensor: numpy-based tensors of intervals.

Each element is an interval [lo, hi]. Two parallel numpy arrays
(lo_array, hi_array) of the same shape. Vectorized for efficiency.

Mirrors PInterval.v operations at the tensor level.
"""

from __future__ import annotations

import numpy as np


class IntervalTensor:
    """Tensor where each element is an interval [lo, hi].

    Storage: two numpy arrays (lo, hi) of the same shape.
    This is far more efficient than an array of Interval objects.
    """

    __slots__ = ("lo", "hi")

    def __init__(self, lo: np.ndarray, hi: np.ndarray) -> None:
        lo = np.asarray(lo, dtype=np.float64)
        hi = np.asarray(hi, dtype=np.float64)
        assert lo.shape == hi.shape, f"Shape mismatch: {lo.shape} vs {hi.shape}"
        assert np.all(lo <= hi + 1e-12), "Interval invariant violated: lo > hi"
        self.lo = lo
        self.hi = hi

    @staticmethod
    def from_exact(values: np.ndarray) -> IntervalTensor:
        """Point intervals (zero uncertainty)."""
        v = np.asarray(values, dtype=np.float64)
        return IntervalTensor(v.copy(), v.copy())

    @staticmethod
    def from_uncertainty(values: np.ndarray, eps: float) -> IntervalTensor:
        """Values +/- epsilon."""
        v = np.asarray(values, dtype=np.float64)
        return IntervalTensor(v - abs(eps), v + abs(eps))

    @property
    def shape(self) -> tuple:
        return self.lo.shape

    @property
    def width(self) -> np.ndarray:
        """Width of each interval."""
        return self.hi - self.lo

    @property
    def midpoint(self) -> np.ndarray:
        return (self.lo + self.hi) / 2

    def max_width(self) -> float:
        return float(np.max(self.width))

    def mean_width(self) -> float:
        return float(np.mean(self.width))

    # --- Diagnostics ---

    def unstable_relu_count(self) -> int:
        """Count elements where interval straddles zero: lo < 0 < hi.

        These are 'unstable' ReLU neurons — IBP cannot determine
        whether they activate. Primary driver of interval blowup.
        Stable neurons (fully positive or fully negative) cause no blowup.
        """
        return int(np.sum((self.lo < 0) & (self.hi > 0)))

    def stability_ratio(self) -> float:
        """Fraction of elements that are ReLU-stable (not straddling zero).

        1.0 = all stable (best case), 0.0 = all unstable (worst case).
        """
        total = self.lo.size
        if total == 0:
            return 1.0
        return 1.0 - self.unstable_relu_count() / total

    def width_percentiles(
        self, percentiles: tuple[int, ...] = (50, 90, 95, 99, 100)
    ) -> dict[int, float]:
        """Width percentiles across all elements.

        Helps distinguish uniform blowup from a few 'runaway' neurons.
        """
        w = self.width.flatten()
        return {p: float(np.percentile(w, p)) for p in percentiles}

    # --- Arithmetic ---

    def __add__(self, other: IntervalTensor) -> IntervalTensor:
        return IntervalTensor(self.lo + other.lo, self.hi + other.hi)

    def __sub__(self, other: IntervalTensor) -> IntervalTensor:
        return IntervalTensor(self.lo - other.hi, self.hi - other.lo)

    def relu(self) -> IntervalTensor:
        """Element-wise ReLU. Mirrors pi_relu."""
        return IntervalTensor(
            np.maximum(0.0, self.lo),
            np.maximum(0.0, self.hi),
        )

    def sigmoid(self) -> IntervalTensor:
        """Element-wise sigmoid. Monotone increasing -> [sig(lo), sig(hi)].
        Mirrors pi_monotone applied with sigmoid."""
        def _sig(x: np.ndarray) -> np.ndarray:
            return np.where(
                x >= 0,
                1.0 / (1.0 + np.exp(-x)),
                np.exp(x) / (1.0 + np.exp(x)),
            )
        return IntervalTensor(_sig(self.lo), _sig(self.hi))

    def tanh(self) -> IntervalTensor:
        """Element-wise tanh. Monotone increasing -> [tanh(lo), tanh(hi)].
        Mirrors pi_monotone applied with tanh. Coq: pi_monotone_correct."""
        return IntervalTensor(np.tanh(self.lo), np.tanh(self.hi))

    def elu(self, alpha: float = 1.0) -> IntervalTensor:
        """Element-wise ELU. Monotone increasing -> [elu(lo), elu(hi)].
        ELU(x) = x if x >= 0, alpha*(exp(x)-1) if x < 0.
        Coq: pi_monotone_correct."""
        def _elu(x: np.ndarray) -> np.ndarray:
            return np.where(x >= 0, x, alpha * (np.exp(x) - 1.0))
        return IntervalTensor(_elu(self.lo), _elu(self.hi))

    def gelu(self) -> IntervalTensor:
        """Element-wise GELU with conservative bounds.

        GELU(x) = x * Phi(x) is NOT globally monotone.
        Has minimum at x* ~ -0.1685 where GELU(x*) ~ -0.0170.

        For each element:
        - If interval fully right of x*: monotone, [gelu(lo), gelu(hi)]
        - If interval fully left of x*: decreasing, [gelu(hi), gelu(lo)]
        - If crosses x*: lo = min(gelu(lo), gelu(hi), GELU_MIN_Y)
        """
        from math import erf as _scalar_erf

        def _gelu(x: np.ndarray) -> np.ndarray:
            # Use vectorized erf via numpy approximation:
            # erf(x) can be computed from tanh approximation for speed,
            # but for soundness use exact math.erf via vectorize
            _verf = np.vectorize(_scalar_erf)
            return 0.5 * x * (1.0 + _verf(x / np.sqrt(2.0)))

        GELU_MIN_X = -0.7518  # GELU'(x*) = 0, found by root-finding
        GELU_MIN_Y = 0.5 * GELU_MIN_X * (1.0 + _scalar_erf(GELU_MIN_X / np.sqrt(2.0)))

        g_lo = _gelu(self.lo)
        g_hi = _gelu(self.hi)

        # Classification per element
        monotone_right = self.lo >= GELU_MIN_X
        monotone_left = self.hi <= GELU_MIN_X
        crosses = ~monotone_right & ~monotone_left

        out_lo = np.where(
            monotone_right, g_lo,
            np.where(monotone_left, g_hi,
                     np.minimum(np.minimum(g_lo, g_hi), GELU_MIN_Y)))
        out_hi = np.where(
            monotone_left, g_lo,
            np.maximum(g_lo, g_hi))

        return IntervalTensor(out_lo, out_hi)

    def __repr__(self) -> str:
        if self.lo.size <= 6:
            pairs = [f"[{l:.4f}, {h:.4f}]" for l, h in zip(self.lo.flat, self.hi.flat)]
            return f"IntervalTensor({', '.join(pairs)})"
        return f"IntervalTensor(shape={self.shape}, mean_width={self.mean_width():.6f})"


def interval_matmul_exact_weights(W: np.ndarray, vec: IntervalTensor) -> IntervalTensor:
    """Matrix multiply with EXACT (non-interval) weights.

    This is the main case: model weights are fixed floats,
    intervals only in inputs and intermediate computations.

    Efficient formula:
        lo = W_pos @ v.lo + W_neg @ v.hi
        hi = W_pos @ v.hi + W_neg @ v.lo
    where W_pos = max(W, 0), W_neg = min(W, 0).

    Mirrors pi_dot from PInterval.v.
    """
    W_pos = np.maximum(W, 0.0)
    W_neg = np.minimum(W, 0.0)

    new_lo = W_pos @ vec.lo + W_neg @ vec.hi
    new_hi = W_pos @ vec.hi + W_neg @ vec.lo

    return IntervalTensor(new_lo, new_hi)
