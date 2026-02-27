"""
CNN architectures for interval propagation experiments.

Defines both PyTorch modules and their interval counterparts:
  ResBlock / IntervalResBlock  -- residual block with skip connection
  make_mlp()                   -- MLP baseline
  make_cnn_bn()                -- CNN with BatchNorm (MNIST)
  ResNetMNIST                  -- ResNet-like architecture (MNIST)
  make_cifar_cnn_bn()          -- CNN with BatchNorm (CIFAR-10)
  ResNetCIFAR                  -- ResNet-like architecture (CIFAR-10)
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

from regulus.nn.interval_tensor import IntervalTensor


# =============================================================
# ResBlock (PyTorch)
# =============================================================


class ResBlock(nn.Module):
    """Residual block: y = relu(x + conv->bn->relu->conv->bn(x)).

    Preserves spatial dimensions (same padding).
    Channel count stays constant.
    """

    def __init__(self, channels: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn1 = nn.BatchNorm2d(channels)
        self.relu1 = nn.ReLU()
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn2 = nn.BatchNorm2d(channels)
        self.relu_out = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        out = self.relu1(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        return self.relu_out(out + residual)


# =============================================================
# IntervalResBlock (Interval)
# =============================================================


class IntervalResBlock:
    """Interval propagation through a ResBlock.

    f(x) = relu(g(x) + x) where g = conv1->bn1->relu->conv2->bn2

    Steps:
      1. Save input interval x
      2. Propagate through inner path: g(x)
      3. Add residual: [x.lo + g.lo, x.hi + g.hi]
      4. Apply ReLU

    Width: width(output) <= width(x) + width(g(x))
    Key insight: if g learns small updates (which training encourages),
    then width(g(x)) is small and the residual connection preserves
    the input interval's tightness.
    """

    def __init__(self, inner_layers: list) -> None:
        self.inner_layers = inner_layers

    @classmethod
    def from_torch(cls, block: ResBlock) -> IntervalResBlock:
        """Convert a PyTorch ResBlock to interval version."""
        from regulus.nn.layers import IntervalConv2d, IntervalBatchNorm, IntervalReLU

        inner = [
            IntervalConv2d.from_torch(block.conv1),
            IntervalBatchNorm.from_torch(block.bn1),
            IntervalReLU(),
            IntervalConv2d.from_torch(block.conv2),
            IntervalBatchNorm.from_torch(block.bn2),
        ]
        return cls(inner)

    def __call__(self, x: IntervalTensor) -> IntervalTensor:
        # Propagate through inner path g(x)
        g = x
        for layer in self.inner_layers:
            g = layer(g)

        # Add residual: x + g(x)
        summed = IntervalTensor(x.lo + g.lo, x.hi + g.hi)

        # Apply ReLU
        return summed.relu()


# =============================================================
# Architecture factories
# =============================================================


def make_mlp() -> nn.Sequential:
    """MLP baseline: 784->256->128->64->10."""
    return nn.Sequential(
        nn.Linear(784, 256), nn.ReLU(),
        nn.Linear(256, 128), nn.ReLU(),
        nn.Linear(128, 64), nn.ReLU(),
        nn.Linear(64, 10),
    )


def make_cnn_bn() -> nn.Sequential:
    """CNN with BatchNorm: Conv->BN->ReLU->Pool x2 + FC layers.

    Architecture:
      Conv2d(1,16,3,pad=1) -> BN2d(16) -> ReLU -> MaxPool(2)   [28->14]
      Conv2d(16,32,3,pad=1) -> BN2d(32) -> ReLU -> MaxPool(2)  [14->7]
      Flatten -> Linear(1568,128) -> ReLU -> Linear(128,10)
    """
    return nn.Sequential(
        nn.Conv2d(1, 16, 3, padding=1),
        nn.BatchNorm2d(16),
        nn.ReLU(),
        nn.MaxPool2d(2),
        nn.Conv2d(16, 32, 3, padding=1),
        nn.BatchNorm2d(32),
        nn.ReLU(),
        nn.MaxPool2d(2),
        nn.Flatten(),
        nn.Linear(1568, 128),
        nn.ReLU(),
        nn.Linear(128, 10),
    )


def make_cnn_bn_v2() -> nn.Sequential:
    """CNN v2: strided conv instead of MaxPool for tighter IBP bounds.

    MaxPool is a source of bound looseness — IBP training can't compress it.
    Strided conv has learnable weights that IBP training CAN compress.

    Key design: use kernel=2, stride=2, no padding — this is the direct
    analog to MaxPool(2): non-overlapping 2x2 windows, but with learnable
    weights. NO extra BN/ReLU after strided conv — same number of
    activation layers as v1 to avoid bound blowup.

    Architecture:
      Conv2d(1,16,3,pad=1) -> BN2d(16) -> ReLU -> Conv2d(16,16,2,stride=2)  [28->14]
      Conv2d(16,32,3,pad=1) -> BN2d(32) -> ReLU -> Conv2d(32,32,2,stride=2) [14->7]
      Flatten -> Linear(1568,128) -> ReLU -> Linear(128,10)

    Same layer count, activation count, and spatial dims as v1.
    """
    return nn.Sequential(
        nn.Conv2d(1, 16, 3, padding=1),
        nn.BatchNorm2d(16),
        nn.ReLU(),
        nn.Conv2d(16, 16, 2, stride=2),  # replaces MaxPool2d(2): 2x2 no-overlap
        nn.Conv2d(16, 32, 3, padding=1),
        nn.BatchNorm2d(32),
        nn.ReLU(),
        nn.Conv2d(32, 32, 2, stride=2),  # replaces MaxPool2d(2): 2x2 no-overlap
        nn.Flatten(),
        nn.Linear(1568, 128),
        nn.ReLU(),
        nn.Linear(128, 10),
    )


class ResNetMNIST(nn.Module):
    """ResNet-like architecture for MNIST.

    Architecture:
      Conv2d(1,32,3,pad=1) -> BN2d(32) -> ReLU          [stem]
      ResBlock(32) -> MaxPool(2)                           [28->14]
      ResBlock(32) -> MaxPool(2)                           [14->7]
      Flatten -> Linear(1568,10)
    """

    def __init__(self) -> None:
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
        )
        self.block1 = ResBlock(32)
        self.pool1 = nn.MaxPool2d(2)
        self.block2 = ResBlock(32)
        self.pool2 = nn.MaxPool2d(2)
        self.flatten = nn.Flatten()
        self.fc = nn.Linear(1568, 10)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.stem(x)
        x = self.pool1(self.block1(x))
        x = self.pool2(self.block2(x))
        x = self.flatten(x)
        x = self.fc(x)
        return x


# =============================================================
# CIFAR-10 architectures (3x32x32 input, 10 classes)
# =============================================================


def make_cifar_cnn_bn() -> nn.Sequential:
    """CNN with BatchNorm for CIFAR-10: 3x32x32 input, 10 classes.

    Architecture:
      Conv2d(3,32,3,pad=1) -> BN2d(32) -> ReLU ->
      Conv2d(32,32,3,pad=1) -> BN2d(32) -> ReLU -> MaxPool(2)  [32->16]
      Conv2d(32,64,3,pad=1) -> BN2d(64) -> ReLU ->
      Conv2d(64,64,3,pad=1) -> BN2d(64) -> ReLU -> MaxPool(2)  [16->8]
      Flatten -> Linear(4096,256) -> ReLU -> Linear(256,10)
    """
    return nn.Sequential(
        nn.Conv2d(3, 32, 3, padding=1),
        nn.BatchNorm2d(32),
        nn.ReLU(),
        nn.Conv2d(32, 32, 3, padding=1),
        nn.BatchNorm2d(32),
        nn.ReLU(),
        nn.MaxPool2d(2),
        nn.Conv2d(32, 64, 3, padding=1),
        nn.BatchNorm2d(64),
        nn.ReLU(),
        nn.Conv2d(64, 64, 3, padding=1),
        nn.BatchNorm2d(64),
        nn.ReLU(),
        nn.MaxPool2d(2),
        nn.Flatten(),
        nn.Linear(64 * 8 * 8, 256),
        nn.ReLU(),
        nn.Linear(256, 10),
    )


class ResNetCIFAR(nn.Module):
    """ResNet-like architecture for CIFAR-10: 3x32x32 input, 10 classes.

    Architecture:
      stem: Conv2d(3,32,3,pad=1) -> BN2d(32) -> ReLU
      ResBlock(32) -> MaxPool(2)                     [32->16]
      expand: Conv2d(32,64,1) -> BN2d(64) -> ReLU   [channel expand]
      ResBlock(64) -> MaxPool(2)                     [16->8]
      Flatten -> Linear(4096,10)
    """

    def __init__(self) -> None:
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
        )
        self.block1 = ResBlock(32)
        self.pool1 = nn.MaxPool2d(2)
        self.expand = nn.Sequential(
            nn.Conv2d(32, 64, 1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
        )
        self.block2 = ResBlock(64)
        self.pool2 = nn.MaxPool2d(2)
        self.flatten = nn.Flatten()
        self.fc = nn.Linear(64 * 8 * 8, 10)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.stem(x)
        x = self.pool1(self.block1(x))
        x = self.expand(x)
        x = self.pool2(self.block2(x))
        x = self.flatten(x)
        x = self.fc(x)
        return x
