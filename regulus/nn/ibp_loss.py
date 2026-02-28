"""
Differentiable IBP (Interval Bound Propagation) training loss.

Implements a fully differentiable interval forward pass through PyTorch
Sequential models, enabling proper IBP training where gradients flow
through interval bounds back to model weights.

Reference: Gowal et al. (2019) "Scalable Verified Training for Provably
Robust Image Classifiers" — the standard approach for certified training.

Key functions:
    ibp_forward(model, x_lo, x_hi) -> (out_lo, out_hi)
        Propagates interval [x_lo, x_hi] through model.
        All operations are standard PyTorch ops → fully differentiable.

    ibp_worst_case_loss(out_lo, out_hi, labels) -> scalar loss
        Constructs worst-case logits and computes cross-entropy.

    ibp_margin_loss(out_lo, out_hi, labels, target_margin) -> (loss, margin)
        Margin regularization to prevent collapse.

    ibp_combined_loss(model, images, labels, epsilon, lam) -> scalar loss
        Complete (1-λ)*clean + λ*ibp loss for training.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


def _ibp_linear(
    x_lo: torch.Tensor,
    x_hi: torch.Tensor,
    weight: torch.Tensor,
    bias: torch.Tensor | None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Interval propagation through a linear layer.

    Given input interval [x_lo, x_hi] and weight matrix W:
        W_pos = max(W, 0),  W_neg = min(W, 0)
        out_lo = x_lo @ W_pos^T + x_hi @ W_neg^T + b
        out_hi = x_hi @ W_pos^T + x_lo @ W_neg^T + b
    """
    W_pos = torch.clamp(weight, min=0)
    W_neg = torch.clamp(weight, max=0)

    out_lo = F.linear(x_lo, W_pos) + F.linear(x_hi, W_neg)
    out_hi = F.linear(x_hi, W_pos) + F.linear(x_lo, W_neg)

    if bias is not None:
        out_lo = out_lo + bias
        out_hi = out_hi + bias

    return out_lo, out_hi


def _ibp_conv2d(
    x_lo: torch.Tensor,
    x_hi: torch.Tensor,
    weight: torch.Tensor,
    bias: torch.Tensor | None,
    stride: tuple[int, ...],
    padding: tuple[int, ...],
) -> tuple[torch.Tensor, torch.Tensor]:
    """Interval propagation through a Conv2d layer.

    Same positive/negative weight decomposition as linear.
    """
    W_pos = torch.clamp(weight, min=0)
    W_neg = torch.clamp(weight, max=0)

    out_lo = (
        F.conv2d(x_lo, W_pos, bias=None, stride=stride, padding=padding)
        + F.conv2d(x_hi, W_neg, bias=None, stride=stride, padding=padding)
    )
    out_hi = (
        F.conv2d(x_hi, W_pos, bias=None, stride=stride, padding=padding)
        + F.conv2d(x_lo, W_neg, bias=None, stride=stride, padding=padding)
    )

    if bias is not None:
        # bias shape: (C_out,) → broadcast as (1, C_out, 1, 1)
        b = bias.view(1, -1, 1, 1)
        out_lo = out_lo + b
        out_hi = out_hi + b

    return out_lo, out_hi


def _ibp_batchnorm(
    x_lo: torch.Tensor,
    x_hi: torch.Tensor,
    layer: nn.BatchNorm2d | nn.BatchNorm1d,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Interval propagation through BatchNorm in eval mode.

    BN in eval mode is affine: y = scale * x + shift
    where scale = gamma / sqrt(running_var + eps)
          shift = beta - scale * running_mean

    For interval arithmetic with mixed-sign scale:
        scale_pos = max(scale, 0)
        scale_neg = min(scale, 0)
        out_lo = scale_pos * x_lo + scale_neg * x_hi + shift
        out_hi = scale_pos * x_hi + scale_neg * x_lo + shift
    """
    gamma = layer.weight           # (C,)
    beta = layer.bias              # (C,)
    mean = layer.running_mean      # (C,)
    var = layer.running_var        # (C,)
    eps = layer.eps

    scale = gamma / torch.sqrt(var + eps)
    shift = beta - scale * mean

    scale_pos = torch.clamp(scale, min=0)
    scale_neg = torch.clamp(scale, max=0)

    is_2d = isinstance(layer, nn.BatchNorm2d)
    if is_2d:
        # Reshape for broadcasting: (C,) → (1, C, 1, 1)
        scale_pos = scale_pos.view(1, -1, 1, 1)
        scale_neg = scale_neg.view(1, -1, 1, 1)
        shift = shift.view(1, -1, 1, 1)
    else:
        # (C,) → (1, C)
        scale_pos = scale_pos.view(1, -1)
        scale_neg = scale_neg.view(1, -1)
        shift = shift.view(1, -1)

    out_lo = scale_pos * x_lo + scale_neg * x_hi + shift
    out_hi = scale_pos * x_hi + scale_neg * x_lo + shift

    return out_lo, out_hi


def ibp_forward(
    model: nn.Module,
    x_lo: torch.Tensor,
    x_hi: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Propagate interval [x_lo, x_hi] through a Sequential model.

    All operations use standard PyTorch ops, so gradients flow through
    model.parameters() → enables proper IBP training.

    The model MUST be in eval() mode (for correct BatchNorm behavior).

    Args:
        model: nn.Sequential (or any iterable of nn.Module layers)
        x_lo: Lower bounds, shape (batch, ...)
        x_hi: Upper bounds, shape (batch, ...)

    Returns:
        (out_lo, out_hi): Output interval bounds
    """
    lo, hi = x_lo, x_hi

    for layer in model.modules():
        # Skip container modules — only process leaf layers
        if isinstance(layer, (nn.Sequential, nn.Module)) and len(list(layer.children())) > 0:
            continue

        if isinstance(layer, nn.Linear):
            lo, hi = _ibp_linear(lo, hi, layer.weight, layer.bias)

        elif isinstance(layer, nn.Conv2d):
            lo, hi = _ibp_conv2d(
                lo, hi, layer.weight, layer.bias,
                stride=layer.stride, padding=layer.padding,
            )

        elif isinstance(layer, (nn.BatchNorm2d, nn.BatchNorm1d)):
            lo, hi = _ibp_batchnorm(lo, hi, layer)

        elif isinstance(layer, nn.ReLU):
            lo = torch.clamp(lo, min=0)
            hi = torch.clamp(hi, min=0)

        elif isinstance(layer, nn.AvgPool2d):
            ks = layer.kernel_size
            st = layer.stride if layer.stride is not None else ks
            pad = layer.padding if layer.padding is not None else 0
            lo = F.avg_pool2d(lo, ks, stride=st, padding=pad)
            hi = F.avg_pool2d(hi, ks, stride=st, padding=pad)

        elif isinstance(layer, nn.MaxPool2d):
            ks = layer.kernel_size
            st = layer.stride if layer.stride is not None else ks
            pad = layer.padding if layer.padding is not None else 0
            lo = F.max_pool2d(lo, ks, stride=st, padding=pad)
            hi = F.max_pool2d(hi, ks, stride=st, padding=pad)

        elif isinstance(layer, nn.Flatten):
            lo = lo.flatten(layer.start_dim, layer.end_dim)
            hi = hi.flatten(layer.start_dim, layer.end_dim)

        else:
            raise NotImplementedError(
                f"ibp_forward: unsupported layer type {type(layer).__name__}. "
                f"Supported: Linear, Conv2d, BatchNorm, ReLU, AvgPool2d, MaxPool2d, Flatten."
            )

    return lo, hi


def ibp_worst_case_loss(
    out_lo: torch.Tensor,
    out_hi: torch.Tensor,
    labels: torch.Tensor,
) -> torch.Tensor:
    """Compute worst-case cross-entropy loss from interval bounds.

    For each sample, construct worst-case logits:
        z_worst[y]   = out_lo[y]   (true class at its LOWER bound)
        z_worst[c!=y] = out_hi[c]  (competing classes at their UPPER bound)

    This is the tightest sound loss: if the model is certified at these
    logits, it's certified for ALL points in the input interval.

    Args:
        out_lo: Lower bounds on output logits, shape (batch, num_classes)
        out_hi: Upper bounds on output logits, shape (batch, num_classes)
        labels: True labels, shape (batch,)

    Returns:
        Scalar cross-entropy loss on worst-case logits
    """
    batch_size, num_classes = out_lo.shape

    # Start with upper bounds (worst case for all classes)
    z_worst = out_hi.clone()

    # For the true class, use the lower bound (worst case for true class)
    batch_idx = torch.arange(batch_size, device=out_lo.device)
    z_worst[batch_idx, labels] = out_lo[batch_idx, labels]

    return F.cross_entropy(z_worst, labels)


def ibp_margin_loss(
    out_lo: torch.Tensor,
    out_hi: torch.Tensor,
    labels: torch.Tensor,
    target_margin: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Margin regularization loss to prevent collapse during IBP training.

    Penalizes when the worst-case margin (gap between true class lower bound
    and best competing class upper bound) is too small. This prevents the
    model from collapsing to constant output to trivially minimize IBP loss.

    margin_i = out_lo[i, y_i] - max_{c != y_i} out_hi[i, c]
    loss = mean(max(0, target_margin - margin_i))

    Args:
        out_lo: Lower bounds on output logits, shape (batch, num_classes)
        out_hi: Upper bounds on output logits, shape (batch, num_classes)
        labels: True labels, shape (batch,)
        target_margin: Desired minimum margin (default: 1.0)

    Returns:
        (margin_loss, avg_margin): Scalar loss and average margin for logging
    """
    batch_size, num_classes = out_lo.shape
    device = out_lo.device

    # True class lower bound: out_lo[i, y_i]
    batch_idx = torch.arange(batch_size, device=device)
    true_lo = out_lo[batch_idx, labels]  # (batch,)

    # Best competing class upper bound: max_{c != y_i} out_hi[i, c]
    # Mask out true class by setting it to -inf
    masked_hi = out_hi.clone()
    masked_hi[batch_idx, labels] = float("-inf")
    best_competing_hi = masked_hi.max(dim=1).values  # (batch,)

    # Margin: positive means certified, negative means not
    margin = true_lo - best_competing_hi  # (batch,)

    # Hinge loss: penalize when margin < target
    margin_loss = torch.clamp(target_margin - margin, min=0).mean()

    avg_margin = margin.mean()

    return margin_loss, avg_margin


def ibp_combined_loss(
    model: nn.Module,
    images: torch.Tensor,
    labels: torch.Tensor,
    epsilon: float,
    lam: float,
    criterion: nn.Module | None = None,
) -> tuple[torch.Tensor, dict]:
    """Compute combined (1-λ)*clean + λ*IBP loss.

    Handles the train/eval mode switching for BatchNorm:
    1. Clean forward in train mode (updates BN running stats)
    2. IBP forward in eval mode (uses frozen BN stats)

    Args:
        model: PyTorch model (nn.Sequential)
        images: Input batch, shape (batch, C, H, W)
        labels: True labels, shape (batch,)
        epsilon: Perturbation radius in tensor (normalized) space
        lam: IBP loss weight in [0, 1]. lam=0 → pure clean, lam=1 → pure IBP
        criterion: Loss function for clean forward (default: CrossEntropyLoss)

    Returns:
        (total_loss, info_dict) where info_dict contains diagnostics
    """
    if criterion is None:
        criterion = nn.CrossEntropyLoss()

    # 1. Clean forward pass (train mode — updates BN stats)
    model.train()
    clean_out = model(images)
    loss_clean = criterion(clean_out, labels)

    # Clean accuracy for logging
    with torch.no_grad():
        _, predicted = clean_out.max(1)
        clean_correct = predicted.eq(labels).sum().item()

    if lam == 0.0:
        return loss_clean, {
            "loss_clean": loss_clean.item(),
            "loss_ibp": 0.0,
            "loss_total": loss_clean.item(),
            "clean_correct": clean_correct,
            "ibp_width": 0.0,
        }

    # 2. IBP forward pass (eval mode — frozen BN)
    model.eval()

    x_lo = images - epsilon
    x_hi = images + epsilon

    out_lo, out_hi = ibp_forward(model, x_lo, x_hi)
    loss_ibp = ibp_worst_case_loss(out_lo, out_hi, labels)

    # Restore train mode
    model.train()

    # 3. Combined loss
    total_loss = (1.0 - lam) * loss_clean + lam * loss_ibp

    # Diagnostics
    with torch.no_grad():
        widths = (out_hi - out_lo)
        avg_width = widths.mean().item()
        max_width = widths.max().item()

    return total_loss, {
        "loss_clean": loss_clean.item(),
        "loss_ibp": loss_ibp.item(),
        "loss_total": total_loss.item(),
        "clean_correct": clean_correct,
        "ibp_width": avg_width,
        "ibp_max_width": max_width,
    }
