"""
IntervalSequential model and PyTorch conversion.

convert_model() takes a trained PyTorch model and produces
an IntervalSequential that propagates intervals through the same layers.

Supported: Linear, ReLU, Sigmoid, Conv2d, BatchNorm1d/2d,
           Flatten, MaxPool2d, Sequential (recursive), ResBlock.
"""

from __future__ import annotations

from regulus.nn.interval_tensor import IntervalTensor
from regulus.nn.layers import IntervalLinear, IntervalReLU, IntervalSigmoid


class IntervalSequential:
    """Interval analogue of torch.nn.Sequential.

    Propagates IntervalTensor through a chain of layers.
    Tracks interval widths at each step (for analysis).
    """

    def __init__(self, layers: list) -> None:
        self.layers = layers
        self.layer_widths: list[float] = []

    def __call__(self, x: IntervalTensor) -> IntervalTensor:
        self.layer_widths = [x.mean_width()]
        for layer in self.layers:
            x = layer(x)
            self.layer_widths.append(x.mean_width())
        return x

    def width_report(self) -> str:
        """Report of interval blowup across layers."""
        lines = ["Layer  | Mean Width | Ratio"]
        lines.append("-------|------------|------")
        for i, w in enumerate(self.layer_widths):
            ratio = w / self.layer_widths[0] if self.layer_widths[0] > 0 else float("inf")
            label = "Input " if i == 0 else f"Layer{i}"
            lines.append(f"{label} | {w:.6f}   | {ratio:.2f}x")
        return "\n".join(lines)


def convert_model(torch_model) -> IntervalSequential:
    """Convert a PyTorch model to IntervalSequential.

    Supported layers: Linear, ReLU, Sigmoid, Conv2d, BatchNorm1d/2d,
                      Flatten, MaxPool2d, Sequential (recursive), ResBlock.
    Unsupported layers raise ValueError.
    """
    import torch.nn as nn
    from regulus.nn.layers import (
        IntervalBatchNorm, IntervalConv2d, IntervalFlatten, IntervalMaxPool2d,
    )
    # Lazy import to avoid circular dependency (architectures imports from layers)
    from regulus.nn.architectures import ResBlock, IntervalResBlock

    interval_layers = []

    for _name, layer in torch_model.named_children():
        if isinstance(layer, nn.Linear):
            interval_layers.append(IntervalLinear.from_torch(layer))
        elif isinstance(layer, nn.ReLU):
            interval_layers.append(IntervalReLU())
        elif isinstance(layer, nn.Sigmoid):
            interval_layers.append(IntervalSigmoid())
        elif isinstance(layer, nn.Conv2d):
            interval_layers.append(IntervalConv2d.from_torch(layer))
        elif isinstance(layer, (nn.BatchNorm1d, nn.BatchNorm2d)):
            interval_layers.append(IntervalBatchNorm.from_torch(layer))
        elif isinstance(layer, nn.Flatten):
            interval_layers.append(IntervalFlatten())
        elif isinstance(layer, nn.MaxPool2d):
            interval_layers.append(IntervalMaxPool2d.from_torch(layer))
        elif isinstance(layer, nn.Sequential):
            # Recursive: flatten children of nested Sequential
            sub = convert_model(layer)
            interval_layers.extend(sub.layers)
        elif isinstance(layer, ResBlock):
            interval_layers.append(IntervalResBlock.from_torch(layer))
        else:
            raise ValueError(
                f"Unsupported layer type: {type(layer).__name__}. "
                f"Supported: Linear, ReLU, Sigmoid, Conv2d, BatchNorm1d/2d, "
                f"Flatten, MaxPool2d, Sequential, ResBlock"
            )

    return IntervalSequential(interval_layers)
