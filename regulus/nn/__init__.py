"""
Regulus Neural Network — interval bound propagation.

Numpy-based IntervalTensor for efficient vectorized operations.
Every layer propagates intervals: if actual input is within [lo, hi],
actual output is guaranteed within the computed interval.
"""

from regulus.nn.interval_tensor import IntervalTensor, interval_matmul_exact_weights
from regulus.nn.layers import (
    IntervalLinear, IntervalReLU, IntervalSigmoid, IntervalSoftmax,
    IntervalTanh, IntervalGELU, IntervalELU,
    IntervalBatchNorm, IntervalConv2d, IntervalFlatten, IntervalMaxPool2d,
)
from regulus.nn.model import IntervalSequential, convert_model
from regulus.nn.reanchor import ReanchoredIntervalModel
from regulus.nn.architectures import (
    ResBlock, IntervalResBlock,
    make_cifar_cnn_bn, ResNetCIFAR,
    make_cnn_bn_v2,
)
from regulus.nn.verifier import VerificationMode, VerificationContract
from regulus.nn.crown import CROWNEngine, CROWNResult, crown_verify

__all__ = [
    "IntervalTensor",
    "interval_matmul_exact_weights",
    "IntervalLinear",
    "IntervalReLU",
    "IntervalSigmoid",
    "IntervalSoftmax",
    "IntervalTanh",
    "IntervalGELU",
    "IntervalELU",
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
    "VerificationMode",
    "VerificationContract",
    "CROWNEngine",
    "CROWNResult",
    "crown_verify",
]
