"""
IntervalSequential model and PyTorch conversion.

convert_model() takes a trained PyTorch model and produces
an IntervalSequential that propagates intervals through the same layers.

Supported: Linear, ReLU, Sigmoid, Tanh, GELU, ELU, Softmax, Conv2d,
           BatchNorm1d/2d, Flatten, MaxPool2d, AvgPool2d, Sequential
           (recursive), ResBlock.
"""

from __future__ import annotations

from regulus.nn.interval_tensor import IntervalTensor
from regulus.nn.layers import (
    IntervalLinear, IntervalReLU, IntervalSigmoid,
    IntervalTanh, IntervalGELU, IntervalELU,
    IntervalSoftmax,
)


class IntervalSequential:
    """Interval analogue of torch.nn.Sequential.

    Propagates IntervalTensor through a chain of layers.
    Tracks interval widths and per-layer diagnostics at each step.
    """

    def __init__(self, layers: list) -> None:
        self.layers = layers
        self.layer_widths: list[float] = []
        self.layer_diagnostics: list[dict] = []

    def __call__(self, x: IntervalTensor) -> IntervalTensor:
        self.layer_widths = [x.mean_width()]
        self.layer_diagnostics = [self._snapshot(x, "input")]
        for i, layer in enumerate(self.layers):
            x = layer(x)
            layer_name = type(layer).__name__
            self.layer_widths.append(x.mean_width())
            self.layer_diagnostics.append(self._snapshot(x, f"{layer_name}_{i}"))
        return x

    @staticmethod
    def _snapshot(x: IntervalTensor, name: str) -> dict:
        """Capture diagnostic snapshot of interval state."""
        diag: dict = {
            "name": name,
            "shape": x.shape,
            "mean_width": x.mean_width(),
            "max_width": x.max_width(),
        }
        if x.lo.size > 1:
            diag["unstable_relu_count"] = x.unstable_relu_count()
            diag["stability_ratio"] = x.stability_ratio()
            diag["width_percentiles"] = x.width_percentiles()
        return diag

    def width_report(self) -> str:
        """Report of interval blowup across layers."""
        lines = ["Layer  | Mean Width | Ratio"]
        lines.append("-------|------------|------")
        for i, w in enumerate(self.layer_widths):
            ratio = w / self.layer_widths[0] if self.layer_widths[0] > 0 else float("inf")
            label = "Input " if i == 0 else f"Layer{i}"
            lines.append(f"{label} | {w:.6f}   | {ratio:.2f}x")
        return "\n".join(lines)


def convert_model(torch_model, fold_bn: bool = False) -> IntervalSequential:
    """Convert a PyTorch model to IntervalSequential.

    Supported layers: Linear, ReLU, Sigmoid, Tanh, GELU, ELU, Softmax,
                      Conv2d, BatchNorm1d/2d, Flatten, MaxPool2d,
                      AvgPool2d, Sequential (recursive), ResBlock.
    Unsupported layers raise ValueError.

    Args:
        torch_model: PyTorch model (nn.Sequential or similar).
        fold_bn: If True, fold BatchNorm into preceding Conv2d/Linear.
                 Eliminates BN layers from the chain. Mathematically
                 identical output, but one fewer propagation step.
    """
    import torch.nn as nn
    from regulus.nn.layers import (
        IntervalBatchNorm, IntervalConv2d, IntervalFlatten,
        IntervalMaxPool2d, IntervalAvgPool2d,
    )
    # Lazy import to avoid circular dependency (architectures imports from layers)
    from regulus.nn.architectures import ResBlock, IntervalResBlock

    children = list(torch_model.named_children())
    interval_layers = []
    skip_next = False

    for idx, (_name, layer) in enumerate(children):
        if skip_next:
            skip_next = False
            continue

        # Peek ahead for BN folding
        next_layer = children[idx + 1][1] if idx + 1 < len(children) else None
        can_fold = (
            fold_bn
            and isinstance(next_layer, (nn.BatchNorm1d, nn.BatchNorm2d))
        )

        if isinstance(layer, nn.Linear):
            il = IntervalLinear.from_torch(layer)
            if can_fold:
                ibn = IntervalBatchNorm.from_torch(next_layer)
                il = il.fold_bn(ibn)
                skip_next = True
            interval_layers.append(il)
        elif isinstance(layer, nn.ReLU):
            interval_layers.append(IntervalReLU())
        elif isinstance(layer, nn.Sigmoid):
            interval_layers.append(IntervalSigmoid())
        elif isinstance(layer, nn.Tanh):
            interval_layers.append(IntervalTanh())
        elif isinstance(layer, nn.GELU):
            interval_layers.append(IntervalGELU())
        elif isinstance(layer, nn.ELU):
            interval_layers.append(IntervalELU(alpha=layer.alpha))
        elif isinstance(layer, nn.Softmax):
            interval_layers.append(IntervalSoftmax())
        elif isinstance(layer, nn.Conv2d):
            ic = IntervalConv2d.from_torch(layer)
            if can_fold:
                ibn = IntervalBatchNorm.from_torch(next_layer)
                ic = ic.fold_bn(ibn)
                skip_next = True
            interval_layers.append(ic)
        elif isinstance(layer, (nn.BatchNorm1d, nn.BatchNorm2d)):
            interval_layers.append(IntervalBatchNorm.from_torch(layer))
        elif isinstance(layer, nn.Flatten):
            interval_layers.append(IntervalFlatten())
        elif isinstance(layer, nn.MaxPool2d):
            interval_layers.append(IntervalMaxPool2d.from_torch(layer))
        elif isinstance(layer, nn.AvgPool2d):
            interval_layers.append(IntervalAvgPool2d.from_torch(layer))
        elif isinstance(layer, nn.Sequential):
            # Recursive: flatten children of nested Sequential
            sub = convert_model(layer, fold_bn=fold_bn)
            interval_layers.extend(sub.layers)
        elif isinstance(layer, ResBlock):
            interval_layers.append(IntervalResBlock.from_torch(layer))
        else:
            raise ValueError(
                f"Unsupported layer type: {type(layer).__name__}. "
                f"Supported: Linear, ReLU, Sigmoid, Tanh, GELU, ELU, Softmax, "
                f"Conv2d, BatchNorm1d/2d, Flatten, MaxPool2d, AvgPool2d, "
                f"Sequential, ResBlock"
            )

    return IntervalSequential(interval_layers)
