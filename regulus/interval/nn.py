"""
Interval neural network layers.

Propagate intervals through standard neural network operations:
  IntervalLinear: y = Wx + b with interval arithmetic
  IntervalReLU: element-wise max(0, x)
  IntervalSequential: chain of layers
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from regulus.interval.interval import Interval
from regulus.interval.interval_tensor import IntervalTensor


class IntervalLayer(ABC):
    """Base class for interval-propagating layers."""

    @abstractmethod
    def forward(self, x: IntervalTensor) -> IntervalTensor:
        ...

    def __call__(self, x: IntervalTensor) -> IntervalTensor:
        return self.forward(x)


class IntervalLinear(IntervalLayer):
    """Interval-propagating linear layer: y_i = sum_j(W_ij * x_j) + b_i.

    Each weight W_ij is a point (no uncertainty in weights).
    Input x_j is an Interval. Output y_i is an Interval computed via
    interval arithmetic (pi_mul + pi_add).

    This is sound: if actual input is anywhere in x, actual output
    is guaranteed to be within the computed interval.
    """

    def __init__(self, weights: Sequence[Sequence[float]], biases: Sequence[float]) -> None:
        self.weights = [list(row) for row in weights]
        self.biases = list(biases)
        self.out_features = len(biases)
        self.in_features = len(weights[0]) if weights else 0

    def forward(self, x: IntervalTensor) -> IntervalTensor:
        assert len(x) == self.in_features, (
            f"Input size mismatch: got {len(x)}, expected {self.in_features}"
        )
        outputs: list[Interval] = []
        for i in range(self.out_features):
            # y_i = sum_j(W_ij * x_j) + b_i
            acc = Interval.point(self.biases[i])
            for j in range(self.in_features):
                w = self.weights[i][j]
                acc = acc + (x[j] * w)
            outputs.append(acc)
        return IntervalTensor(outputs)


class IntervalReLU(IntervalLayer):
    """Element-wise ReLU: max(0, x).

    Corresponds to pi_relu from PInterval.v.
    [a,b] -> [max(0,a), max(0,b)].
    """

    def forward(self, x: IntervalTensor) -> IntervalTensor:
        return x.relu()


class IntervalSequential(IntervalLayer):
    """Sequential chain of interval layers."""

    def __init__(self, *layers: IntervalLayer) -> None:
        self.layers = list(layers)

    def forward(self, x: IntervalTensor) -> IntervalTensor:
        for layer in self.layers:
            x = layer.forward(x)
        return x

    def __repr__(self) -> str:
        lines = [f"  ({i}): {type(layer).__name__}" for i, layer in enumerate(self.layers)]
        return "IntervalSequential(\n" + "\n".join(lines) + "\n)"
