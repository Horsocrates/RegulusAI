"""
IBP-aware training utilities.

IntervalTensor is pure numpy — no autograd. We use a hybrid approach:
- Compute IBP bounds in torch.no_grad() (no gradient through intervals)
- Add margin penalty + weight norm regularization (differentiable)
- Training encourages models whose weights produce tighter IBP bounds

Components:
  EpsilonSchedule:         Linear ramp from small ε to target ε (or flat)
  LambdaSchedule:          Linear ramp for IBP loss weight (0 → λ_max)
  compute_ibp_margin:      Run IBP on batch samples, return mean margin
  ibp_margin_penalty:      Penalty when margin is below target
  weight_norm_regularizer: L2 norm of all weight matrices (differentiable)
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

from regulus.nn.interval_tensor import IntervalTensor
from regulus.nn.verifier import NNVerificationEngine


class EpsilonSchedule:
    """Epsilon schedule: flat or linear ramp with warmup.

    Modes:
    - flat: epsilon = eps_end from step 0 (eps_start ignored)
    - ramp (default): warmup at eps_start, then linear ramp to eps_end

    Args:
        eps_start: Initial epsilon (small, for easy margin). Ignored if flat=True.
        eps_end: Target epsilon (larger, for practical certification)
        total_steps: Total number of training steps (batches)
        warmup_fraction: Fraction of steps for warmup (default 0.1)
        flat: If True, use eps_end from step 0 (no ramp)
    """

    def __init__(
        self,
        eps_start: float = 0.0001,
        eps_end: float = 0.01,
        total_steps: int = 1000,
        warmup_fraction: float = 0.1,
        flat: bool = False,
    ) -> None:
        self.eps_start = eps_start
        self.eps_end = eps_end
        self.total_steps = total_steps
        self.warmup_steps = int(total_steps * warmup_fraction)
        self.flat = flat

    def __call__(self, step: int) -> float:
        """Get epsilon for current step."""
        if self.flat:
            return self.eps_end
        if step < self.warmup_steps:
            return self.eps_start
        if step >= self.total_steps:
            return self.eps_end
        # Linear ramp after warmup
        ramp_steps = self.total_steps - self.warmup_steps
        progress = (step - self.warmup_steps) / max(ramp_steps, 1)
        return self.eps_start + (self.eps_end - self.eps_start) * progress

    @property
    def warmup_end_step(self) -> int:
        return 0 if self.flat else self.warmup_steps


class LambdaSchedule:
    """Linear ramp for IBP loss weight: 0 → lambda_max.

    Addresses the key insight from experiment v1: instead of ramping epsilon
    (which causes the model to overfit to small ε), keep epsilon flat at target
    and gradually increase the IBP loss pressure.

    Args:
        lambda_max: Maximum IBP loss weight (reached at ramp_end)
        total_steps: Total training steps
        ramp_fraction: Fraction of steps over which to ramp (default 0.5)
        warmup_fraction: Fraction of steps with lambda=0 (clean training, default 0.0)
    """

    def __init__(
        self,
        lambda_max: float = 1.0,
        total_steps: int = 1000,
        ramp_fraction: float = 0.5,
        warmup_fraction: float = 0.0,
    ) -> None:
        self.lambda_max = lambda_max
        self.total_steps = total_steps
        self.warmup_steps = int(total_steps * warmup_fraction)
        self.ramp_steps = int(total_steps * ramp_fraction)
        self.ramp_end = self.warmup_steps + self.ramp_steps

    def __call__(self, step: int) -> float:
        """Get lambda for current step."""
        if step < self.warmup_steps:
            return 0.0
        if step >= self.ramp_end:
            return self.lambda_max
        # Linear ramp
        progress = (step - self.warmup_steps) / max(self.ramp_steps, 1)
        return self.lambda_max * progress


def compute_ibp_margin(
    model: nn.Module,
    images: torch.Tensor,
    labels: torch.Tensor,
    epsilon: float,
    architecture: str = "cnn_bn",
    n_samples: int = 4,
    strategy: str = "naive",
    fold_bn: bool = True,
) -> float:
    """Compute mean IBP margin on a subsample of the batch.

    Runs IBP verification on n_samples images from the batch (in no_grad)
    and returns the mean margin. Positive margin = certified for that image.

    Args:
        model: PyTorch model (will be temporarily set to eval mode).
        images: Batch of images (B, C, H, W) or (B, D) for MLP.
        labels: Batch of integer labels (B,).
        epsilon: Perturbation radius in tensor space.
        architecture: "mlp" or "cnn_bn" (determines input handling).
        n_samples: Number of images to check from the batch.
        strategy: Verification strategy.
        fold_bn: Whether to fold BN layers.

    Returns:
        Mean margin (float). Positive = good, negative = bounds overlap.
    """
    was_training = model.training
    model.eval()

    engine = NNVerificationEngine(strategy=strategy, fold_bn=fold_bn)
    margins = []

    n = min(n_samples, images.size(0))
    for i in range(n):
        img_np = images[i].detach().cpu().numpy().astype(np.float64)
        if architecture == "mlp":
            img_np = img_np.flatten()
        label = int(labels[i].item())

        with torch.no_grad():
            result = engine.verify_from_point(model, img_np, epsilon, true_label=label)
        margins.append(result.margin)

    if was_training:
        model.train()

    return float(np.mean(margins)) if margins else 0.0


def ibp_margin_penalty(margin: float, target_margin: float = 0.1) -> float:
    """Penalty when IBP margin is below target.

    Returns max(0, target - margin). Used as a loss term:
    - margin >= target → penalty = 0 (good)
    - margin < target → penalty = target - margin (push to improve)

    This value is NOT differentiable (computed in no_grad).
    It serves as a scalar multiplier for the weight regularization term.

    Args:
        margin: Mean IBP margin from compute_ibp_margin.
        target_margin: Desired margin threshold.

    Returns:
        Non-negative penalty value.
    """
    return max(0.0, target_margin - margin)


def weight_norm_regularizer(model: nn.Module) -> torch.Tensor:
    """L2 norm of all weight matrices in the model.

    This IS differentiable — gradients flow back through weights.
    Smaller weight norms → smaller interval blowup in IBP.

    The intuition: IBP width at each layer ≈ ||W|| * input_width.
    Penalizing ||W||_F across all layers encourages tighter bounds.

    Args:
        model: PyTorch model with parameters.

    Returns:
        Scalar torch.Tensor (sum of squared Frobenius norms).
    """
    reg = torch.tensor(0.0, requires_grad=True)
    for name, param in model.named_parameters():
        if "weight" in name and param.dim() >= 2:
            reg = reg + torch.sum(param ** 2)
    return reg
