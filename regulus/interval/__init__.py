"""
Regulus Interval Arithmetic — Python prototype.

Functionally identical to verified Coq PInterval.v.
Every operation here corresponds to a Coq-proven lemma.

P4 Philosophy: An interval IS the number at the current step
of the process of determination.
"""

from regulus.interval.interval import Interval
from regulus.interval.interval_tensor import IntervalTensor
from regulus.interval.nn import IntervalLinear, IntervalReLU, IntervalSequential
from regulus.interval.convert import convert_model
from regulus.interval.bisection import bisection_iter, bisection_process

__all__ = [
    "Interval",
    "IntervalTensor",
    "IntervalLinear",
    "IntervalReLU",
    "IntervalSequential",
    "convert_model",
    "bisection_iter",
    "bisection_process",
]
