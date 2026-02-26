"""
IntervalTensor: tensors of intervals for neural network propagation.

Each element is an Interval [lo, hi]. Operations propagate bounds
through the network, giving guaranteed output ranges.
"""

from __future__ import annotations

from typing import Sequence, Union

from regulus.interval.interval import Interval, Scalar


class IntervalTensor:
    """1D vector of Intervals. Used as input/output for interval neural nets.

    Example:
        x = IntervalTensor([[0.71, 0.75], [0.28, 0.32]])
        # Two features with uncertainty bounds
    """

    __slots__ = ("_data",)

    def __init__(self, data: Union[Sequence[Interval], Sequence[Sequence[float]]]) -> None:
        intervals: list[Interval] = []
        for item in data:
            if isinstance(item, Interval):
                intervals.append(item)
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                intervals.append(Interval(item[0], item[1]))
            else:
                raise TypeError(f"Expected Interval or [lo, hi] pair, got {type(item)}")
        self._data = intervals

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, idx: int) -> Interval:
        return self._data[idx]

    def __repr__(self) -> str:
        return f"IntervalTensor({self._data})"

    @classmethod
    def from_point(cls, values: Sequence[float]) -> IntervalTensor:
        """Create tensor of point intervals (no uncertainty)."""
        return cls([Interval.point(v) for v in values])

    @classmethod
    def from_pm(cls, centers: Sequence[float], radius: float) -> IntervalTensor:
        """Create tensor with uniform perturbation radius."""
        return cls([Interval.pm(c, radius) for c in centers])

    def add(self, other: IntervalTensor) -> IntervalTensor:
        """Element-wise addition."""
        assert len(self) == len(other)
        return IntervalTensor([a + b for a, b in zip(self._data, other._data)])

    def scale(self, k: float) -> IntervalTensor:
        """Scalar multiplication."""
        return IntervalTensor([k * iv for iv in self._data])

    def relu(self) -> IntervalTensor:
        """Element-wise ReLU. Corresponds to pi_relu on each element."""
        return IntervalTensor([iv.relu() for iv in self._data])

    def dot(self, weights: Sequence[float]) -> Interval:
        """Dot product: sum(w_i * x_i). Used in IntervalLinear."""
        assert len(weights) == len(self._data)
        result = Interval.point(0.0)
        for w, iv in zip(weights, self._data):
            result = result + (iv * w)
        return result

    def any_overlap(self) -> bool:
        """Check if any pair of intervals overlaps (for classification)."""
        for i in range(len(self._data)):
            for j in range(i + 1, len(self._data)):
                if self._data[i].overlaps(self._data[j]):
                    return True
        return False

    @property
    def data(self) -> list[Interval]:
        return list(self._data)
