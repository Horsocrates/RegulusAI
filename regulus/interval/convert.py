"""
Convert PyTorch models to interval-propagating equivalents.

Usage:
    import torch
    model = torch.nn.Sequential(
        torch.nn.Linear(2, 4),
        torch.nn.ReLU(),
        torch.nn.Linear(4, 2),
    )
    interval_model = convert_model(model)
"""

from __future__ import annotations

from typing import Any

from regulus.interval.nn import IntervalLayer, IntervalLinear, IntervalReLU, IntervalSequential


def convert_model(model: Any) -> IntervalSequential:
    """Convert a PyTorch Sequential model to IntervalSequential.

    Supports: nn.Linear, nn.ReLU.
    Raises TypeError for unsupported layers.
    """
    try:
        import torch.nn as nn
    except ImportError:
        raise ImportError("PyTorch is required for model conversion. Install with: pip install torch")

    layers: list[IntervalLayer] = []

    modules = list(model.children()) if hasattr(model, "children") else [model]

    for module in modules:
        if isinstance(module, nn.Linear):
            w = module.weight.detach().cpu().numpy().tolist()
            b = module.bias.detach().cpu().numpy().tolist() if module.bias is not None else [0.0] * module.out_features
            layers.append(IntervalLinear(w, b))
        elif isinstance(module, nn.ReLU):
            layers.append(IntervalReLU())
        elif isinstance(module, nn.Sequential):
            # Recursive
            inner = convert_model(module)
            layers.extend(inner.layers)
        else:
            raise TypeError(
                f"Unsupported layer type: {type(module).__name__}. "
                f"Supported: Linear, ReLU, Sequential."
            )

    return IntervalSequential(*layers)
