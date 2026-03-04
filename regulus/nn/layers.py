"""
Interval neural network layers.

Propagate IntervalTensors through standard NN operations:
  IntervalLinear:    y = Wx + b  with interval arithmetic
  IntervalReLU:      element-wise max(0, x)
  IntervalSigmoid:   element-wise sigma(x)
  IntervalSoftmax:   conservative interval softmax bounds
  IntervalBatchNorm: affine transform (eval mode) with interval bounds
  IntervalConv2d:    convolution via positive/negative weight decomposition
  IntervalFlatten:   reshape preserving bounds
  IntervalMaxPool2d: monotone pooling
"""

from __future__ import annotations

import numpy as np

from regulus.nn.interval_tensor import IntervalTensor, interval_matmul_exact_weights


class IntervalLinear:
    """Interval analogue of torch.nn.Linear.

    Weights are exact (from a trained model).
    Input is IntervalTensor, output is IntervalTensor.
    Output width reflects how uncertainty propagates through this layer.
    """

    def __init__(self, weight: np.ndarray, bias: np.ndarray | None = None) -> None:
        self.weight = np.asarray(weight, dtype=np.float64)  # (out, in)
        self.bias = np.asarray(bias, dtype=np.float64) if bias is not None else None

    @classmethod
    def from_torch(cls, layer) -> IntervalLinear:
        """Convert from a PyTorch nn.Linear layer."""
        weight = layer.weight.detach().cpu().numpy()
        bias = layer.bias.detach().cpu().numpy() if layer.bias is not None else None
        return cls(weight, bias)

    def fold_bn(self, bn: IntervalBatchNorm) -> IntervalLinear:
        """Fold a BatchNorm1d affine transform into this Linear layer.

        BN computes: y = scale * (Wx + b) + shift
                       = (scale * W)x + (scale * b + shift)

        Eliminates the BN layer from the propagation chain.
        Mathematically identical output, one fewer pos/neg decomposition.
        """
        scale = bn.scale  # (out_features,)
        shift = bn.shift  # (out_features,)

        new_weight = scale[:, np.newaxis] * self.weight  # (out,1) * (out,in)
        old_bias = self.bias if self.bias is not None else np.zeros(self.weight.shape[0])
        new_bias = scale * old_bias + shift

        return IntervalLinear(new_weight, new_bias)

    def __call__(self, x: IntervalTensor) -> IntervalTensor:
        result = interval_matmul_exact_weights(self.weight, x)
        if self.bias is not None:
            result = IntervalTensor(result.lo + self.bias, result.hi + self.bias)
        return result


class IntervalReLU:
    """Interval ReLU: max(0, x).

    ReLU is monotone -> [max(0,lo), max(0,hi)].
    This SHRINKS intervals (when lo < 0 < hi, lower bound rises to 0).
    ReLU fights interval blowup.
    """

    def __call__(self, x: IntervalTensor) -> IntervalTensor:
        return x.relu()


class IntervalSigmoid:
    """Interval sigmoid.

    Sigmoid is monotone -> [sig(lo), sig(hi)].
    Compresses to [0,1] -> also fights blowup.
    """

    def __call__(self, x: IntervalTensor) -> IntervalTensor:
        return x.sigmoid()


class IntervalTanh:
    """Interval tanh.

    Tanh is monotone increasing -> [tanh(lo), tanh(hi)].
    Compresses to [-1,1] -> fights blowup.
    Coq backing: pi_monotone_correct (PInterval.v:612).
    """

    def __call__(self, x: IntervalTensor) -> IntervalTensor:
        return x.tanh()


class IntervalGELU:
    """Interval GELU -- CONSERVATIVE bounds.

    GELU(x) = x * Phi(x) is not monotone everywhere.
    Has a global minimum at x* ~ -0.1685.
    Uses min/max of boundary evaluations plus the global minimum
    when the interval crosses the critical point.
    """

    def __call__(self, x: IntervalTensor) -> IntervalTensor:
        return x.gelu()


class IntervalELU:
    """Interval ELU.

    ELU(x) = x if x >= 0, alpha*(exp(x)-1) if x < 0.
    Monotone increasing -> [elu(lo), elu(hi)].
    Coq backing: pi_monotone_correct (PInterval.v:612).
    """

    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = alpha

    def __call__(self, x: IntervalTensor) -> IntervalTensor:
        return x.elu(self.alpha)


class IntervalSoftmax:
    """Interval softmax — VERIFIED bounds.

    Uses Coq-verified cross-multiplication bounds from PInterval_Softmax.v.
    Parametric over monotone positive f; instantiated with exp for NN use.

    For class i:
    - Lower: f(lo_i) / (f(lo_i) + sum_{j!=i} f(hi_j))
    - Upper: f(hi_i) / (f(hi_i) + sum_{j!=i} f(lo_j))

    Coq theorems:
        interval_softmax_lower_bound — cross-mul: f(lo)*D_x <= f(x)*D_lo
        interval_softmax_upper_bound — cross-mul: f(x)*D_hi <= f(hi)*D_x
    """

    def __call__(self, x: IntervalTensor) -> IntervalTensor:
        import math
        from regulus.interval.softmax import interval_softmax

        n = x.lo.shape[0]

        # Numerical stability: log-sum-exp shift
        # The shift cancels in the softmax ratio, so bounds remain valid.
        shift = float(max(np.max(x.hi), np.max(x.lo)))
        los_shifted = [float(x.lo[i]) - shift for i in range(n)]
        his_shifted = [float(x.hi[i]) - shift for i in range(n)]

        result_lo_list, result_hi_list = interval_softmax(
            los_shifted, his_shifted, f=math.exp,
        )

        result_lo = np.clip(np.array(result_lo_list), 0.0, 1.0)
        result_hi = np.clip(np.array(result_hi_list), 0.0, 1.0)

        return IntervalTensor(result_lo, result_hi)


# =============================================================
# CNN layers (Step 9)
# =============================================================


class IntervalBatchNorm:
    """Interval propagation through BatchNorm (eval mode).

    In eval mode, BN is an element-wise affine transform:
        y = scale * x + shift
    where:
        scale = gamma / sqrt(running_var + eps)
        shift = beta - scale * running_mean

    P4 insight: BatchNorm is a "normalization step" -- an act of
    determining the current state. It re-centers and re-scales
    activations, which SHRINKS interval widths when |scale| < 1
    (i.e., when running_var > gamma^2, which is typical).

    This is architectural re-anchoring: the network itself performs
    the "observation" that process-based propagation does manually.
    """

    def __init__(self, scale: np.ndarray, shift: np.ndarray,
                 n_dims: int = 1) -> None:
        self.scale = np.asarray(scale, dtype=np.float64)  # (C,)
        self.shift = np.asarray(shift, dtype=np.float64)  # (C,)
        self.n_dims = n_dims  # 1 for BN1d, 2 for BN2d

    @classmethod
    def from_torch(cls, layer) -> IntervalBatchNorm:
        """Convert from a PyTorch BatchNorm1d or BatchNorm2d layer."""
        import torch.nn as nn

        gamma = layer.weight.detach().cpu().numpy().astype(np.float64)
        beta = layer.bias.detach().cpu().numpy().astype(np.float64)
        running_mean = layer.running_mean.detach().cpu().numpy().astype(np.float64)
        running_var = layer.running_var.detach().cpu().numpy().astype(np.float64)
        eps = layer.eps

        scale = gamma / np.sqrt(running_var + eps)
        shift = beta - scale * running_mean

        n_dims = 2 if isinstance(layer, nn.BatchNorm2d) else 1
        return cls(scale, shift, n_dims)

    def __call__(self, x: IntervalTensor) -> IntervalTensor:
        scale = self.scale
        shift = self.shift

        # Reshape for broadcasting: (C,) -> (C,1,1) for 3D input (C,H,W)
        if x.lo.ndim == 3 and scale.ndim == 1:
            scale = scale[:, np.newaxis, np.newaxis]
            shift = shift[:, np.newaxis, np.newaxis]

        # Positive/negative decomposition (same pattern as interval_matmul)
        scale_pos = np.maximum(scale, 0.0)
        scale_neg = np.minimum(scale, 0.0)

        new_lo = scale_pos * x.lo + scale_neg * x.hi + shift
        new_hi = scale_pos * x.hi + scale_neg * x.lo + shift

        return IntervalTensor(new_lo, new_hi)


class IntervalConv2d:
    """Interval propagation through Conv2d.

    Uses the positive/negative weight decomposition with
    torch.nn.functional.conv2d for the actual convolution math.

    For interval [lo, hi] with weight split W = W_pos + W_neg:
        output_lo = conv(lo, W_pos) + conv(hi, W_neg) + bias
        output_hi = conv(hi, W_pos) + conv(lo, W_neg) + bias

    Input: IntervalTensor shape (C_in, H, W)
    Output: IntervalTensor shape (C_out, H_out, W_out)
    """

    def __init__(self, weight: np.ndarray, bias: np.ndarray | None,
                 stride: int = 1, padding: int = 0) -> None:
        self.weight = np.asarray(weight, dtype=np.float64)  # (C_out, C_in, kH, kW)
        self.bias = np.asarray(bias, dtype=np.float64) if bias is not None else None
        self.stride = stride
        self.padding = padding

    @classmethod
    def from_torch(cls, layer) -> IntervalConv2d:
        """Convert from a PyTorch nn.Conv2d layer."""
        weight = layer.weight.detach().cpu().numpy().astype(np.float64)
        bias = (layer.bias.detach().cpu().numpy().astype(np.float64)
                if layer.bias is not None else None)
        stride = layer.stride[0] if isinstance(layer.stride, tuple) else layer.stride
        padding = layer.padding[0] if isinstance(layer.padding, tuple) else layer.padding
        return cls(weight, bias, stride, padding)

    def fold_bn(self, bn: IntervalBatchNorm) -> IntervalConv2d:
        """Fold a BatchNorm2d affine transform into this Conv2d layer.

        BN computes per-channel: y_c = scale_c * conv_c(x) + shift_c

        New weight[c] = scale[c] * old_weight[c]
        New bias[c]   = scale[c] * old_bias[c] + shift[c]

        Eliminates the BN layer from the propagation chain.
        """
        scale = bn.scale  # (C_out,)
        shift = bn.shift  # (C_out,)

        # weight shape: (C_out, C_in, kH, kW)
        new_weight = scale[:, np.newaxis, np.newaxis, np.newaxis] * self.weight
        old_bias = self.bias if self.bias is not None else np.zeros(self.weight.shape[0])
        new_bias = scale * old_bias + shift

        return IntervalConv2d(new_weight, new_bias, self.stride, self.padding)

    def __call__(self, x: IntervalTensor) -> IntervalTensor:
        import torch
        import torch.nn.functional as F

        W = torch.tensor(self.weight, dtype=torch.float64)
        W_pos = torch.clamp(W, min=0.0)
        W_neg = torch.clamp(W, max=0.0)

        # Unsqueeze batch dim: (C,H,W) -> (1,C,H,W)
        lo_t = torch.tensor(x.lo, dtype=torch.float64).unsqueeze(0)
        hi_t = torch.tensor(x.hi, dtype=torch.float64).unsqueeze(0)

        out_lo = (F.conv2d(lo_t, W_pos, stride=self.stride, padding=self.padding)
                  + F.conv2d(hi_t, W_neg, stride=self.stride, padding=self.padding))
        out_hi = (F.conv2d(hi_t, W_pos, stride=self.stride, padding=self.padding)
                  + F.conv2d(lo_t, W_neg, stride=self.stride, padding=self.padding))

        if self.bias is not None:
            bias_t = torch.tensor(self.bias, dtype=torch.float64).view(1, -1, 1, 1)
            out_lo = out_lo + bias_t
            out_hi = out_hi + bias_t

        # Remove batch dim: (1,C_out,H_out,W_out) -> (C_out,H_out,W_out)
        return IntervalTensor(
            out_lo.squeeze(0).numpy(),
            out_hi.squeeze(0).numpy(),
        )


class IntervalFlatten:
    """Flatten spatial dimensions. Trivial for intervals -- only reshapes."""

    def __call__(self, x: IntervalTensor) -> IntervalTensor:
        return IntervalTensor(x.lo.flatten(), x.hi.flatten())


class IntervalMaxPool2d:
    """Interval propagation through MaxPool2d.

    MaxPool is monotone: larger input -> larger output.
    So [max_pool(lo), max_pool(hi)] gives exact interval bounds.
    """

    def __init__(self, kernel_size: int, stride: int | None = None,
                 padding: int = 0) -> None:
        self.kernel_size = kernel_size
        self.stride = stride if stride is not None else kernel_size
        self.padding = padding

    @classmethod
    def from_torch(cls, layer) -> IntervalMaxPool2d:
        """Convert from a PyTorch nn.MaxPool2d layer."""
        ks = layer.kernel_size if isinstance(layer.kernel_size, int) else layer.kernel_size[0]
        stride = layer.stride if isinstance(layer.stride, int) else layer.stride[0]
        padding = layer.padding if isinstance(layer.padding, int) else layer.padding[0]
        return cls(ks, stride, padding)

    def __call__(self, x: IntervalTensor) -> IntervalTensor:
        import torch
        import torch.nn.functional as F

        lo_t = torch.tensor(x.lo, dtype=torch.float64).unsqueeze(0)
        hi_t = torch.tensor(x.hi, dtype=torch.float64).unsqueeze(0)

        out_lo = F.max_pool2d(lo_t, self.kernel_size, self.stride, self.padding)
        out_hi = F.max_pool2d(hi_t, self.kernel_size, self.stride, self.padding)

        return IntervalTensor(
            out_lo.squeeze(0).numpy(),
            out_hi.squeeze(0).numpy(),
        )


class IntervalAvgPool2d:
    """Interval propagation through AvgPool2d.

    AvgPool is a LINEAR operation: each output is the mean of k² inputs.
    Since all weights are positive (1/k²), AvgPool is monotone:
        [avg_pool(lo), avg_pool(hi)] gives exact interval bounds.

    Unlike MaxPool, AvgPool preserves CROWN backward-propagation because
    it has a fixed, known Jacobian (no routing ambiguity).
    """

    def __init__(self, kernel_size: int, stride: int | None = None,
                 padding: int = 0) -> None:
        self.kernel_size = kernel_size
        self.stride = stride if stride is not None else kernel_size
        self.padding = padding

    @classmethod
    def from_torch(cls, layer) -> IntervalAvgPool2d:
        """Convert from a PyTorch nn.AvgPool2d layer."""
        ks = layer.kernel_size if isinstance(layer.kernel_size, int) else layer.kernel_size[0]
        stride = layer.stride if isinstance(layer.stride, int) else layer.stride[0]
        padding = layer.padding if isinstance(layer.padding, int) else layer.padding[0]
        return cls(ks, stride, padding)

    def __call__(self, x: IntervalTensor) -> IntervalTensor:
        import torch
        import torch.nn.functional as F

        lo_t = torch.tensor(x.lo, dtype=torch.float64).unsqueeze(0)
        hi_t = torch.tensor(x.hi, dtype=torch.float64).unsqueeze(0)

        out_lo = F.avg_pool2d(lo_t, self.kernel_size, self.stride, self.padding)
        out_hi = F.avg_pool2d(hi_t, self.kernel_size, self.stride, self.padding)

        return IntervalTensor(
            out_lo.squeeze(0).numpy(),
            out_hi.squeeze(0).numpy(),
        )
