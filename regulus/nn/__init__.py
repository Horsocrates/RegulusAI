"""
Regulus Neural Network — interval bound propagation.

Numpy-based IntervalTensor for efficient vectorized operations.
Every layer propagates intervals: if actual input is within [lo, hi],
actual output is guaranteed within the computed interval.
"""

from regulus.nn.interval_tensor import IntervalTensor, interval_matmul_exact_weights
from regulus.nn.layers import (
    IntervalLinear, IntervalReLU, IntervalSigmoid, IntervalSoftmax,
    IntervalBatchNorm, IntervalConv2d, IntervalFlatten, IntervalMaxPool2d,
)
from regulus.nn.model import IntervalSequential, convert_model
from regulus.nn.reanchor import ReanchoredIntervalModel
from regulus.nn.architectures import (
    ResBlock, IntervalResBlock,
    make_cifar_cnn_bn, ResNetCIFAR,
)

__all__ = [
    "IntervalTensor",
    "interval_matmul_exact_weights",
    "IntervalLinear",
    "IntervalReLU",
    "IntervalSigmoid",
    "IntervalSoftmax",
    "IntervalBatchNorm",
    "IntervalConv2d",
    "IntervalFlatten",
    "IntervalMaxPool2d",
    "IntervalSequential",
    "convert_model",
    "ReanchoredIntervalModel",
    "ResBlock",
    "IntervalResBlock",
    "make_cifar_cnn_bn",
    "ResNetCIFAR",
]
