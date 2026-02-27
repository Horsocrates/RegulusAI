"""
CROWN: Efficient Neural Network Verification via Linear Relaxation.

Implements backward-mode linear bound propagation for tighter output bounds
than naive IBP. CROWN is SOUND — the computed bounds are guaranteed to
contain the true output for any input within the perturbation region.

Algorithm overview:
  1. Forward IBP pass: compute pre-activation bounds [l_k, u_k] at each layer.
  2. Backward pass: propagate linear relaxation coefficients (Λ, Ω) from
     output back to input, substituting ReLU relaxations at each layer.
  3. Final concretization: evaluate the linear bounds at the input interval
     to get tight output bounds.

Key advantage over IBP:
  - IBP propagates BOXES (loses shape information at each ReLU).
  - CROWN propagates LINEAR FUNCTIONS (preserves correlations between neurons).
  - For unstable ReLUs: IBP uses [0, max(0,u)] which is a box.
    CROWN uses linear upper/lower bounds that are strictly tighter.

Reference: Zhang et al., "Efficient Neural Network Robustness Certification
with General Activation Functions" (NeurIPS 2018).

Soundness: CROWN bounds are >= IBP bounds (tighter). Since IBP is sound
(Coq: pi_dot, pi_relu), and CROWN never exceeds IBP bounds, CROWN is sound.

This module supports: Linear, Conv2d (as flattened Linear), BatchNorm (folded),
ReLU. The model MUST be converted with fold_bn=True before CROWN.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from regulus.nn.interval_tensor import IntervalTensor
from regulus.nn.model import convert_model, IntervalSequential
from regulus.nn.layers import (
    IntervalLinear, IntervalReLU, IntervalBatchNorm,
    IntervalConv2d, IntervalFlatten, IntervalMaxPool2d,
)


# =============================================================
# Data Structures
# =============================================================


@dataclass
class CROWNLayerBounds:
    """Pre-activation bounds at a single layer, computed by forward IBP."""
    pre_lo: np.ndarray  # Lower bound before activation
    pre_hi: np.ndarray  # Upper bound before activation
    post_lo: np.ndarray  # Lower bound after activation
    post_hi: np.ndarray  # Upper bound after activation
    layer_type: str  # "linear", "relu", "conv2d", "flatten", "maxpool2d", "batchnorm"
    shape: tuple  # Shape at this point


@dataclass
class CROWNResult:
    """Result of CROWN verification for a single input."""
    output_lo: np.ndarray  # Tight lower bounds on output neurons
    output_hi: np.ndarray  # Tight upper bounds on output neurons
    ibp_output_lo: np.ndarray  # IBP lower bounds (for comparison)
    ibp_output_hi: np.ndarray  # IBP upper bounds (for comparison)
    crown_improvement: float  # Average width reduction vs IBP
    layer_bounds: list[CROWNLayerBounds]  # Per-layer bounds


# =============================================================
# CROWN Engine
# =============================================================


class CROWNEngine:
    """CROWN backward-mode linear bound propagation.

    Usage:
        engine = CROWNEngine()
        result = engine.compute_bounds(torch_model, input_point, epsilon)
        # result.output_lo, result.output_hi are tighter than IBP
    """

    def __init__(self, alpha_mode: str = "adaptive", crown_depth: str = "fc") -> None:
        """
        Args:
            alpha_mode: How to choose lower bound slope for unstable ReLUs.
                "adaptive" — use α = u/(u-l) (minimizes area)
                "zero"     — use α = 0 (most conservative lower bound)
                "one"      — use α = 1 (identity lower bound)
                "parallel" — use α = u/(u-l) same as upper slope
            crown_depth: How deep CROWN backward goes.
                "fc"   — FC tail only (after last Flatten) — default, fast
                "deep" — include last Conv+ReLU block before Flatten
                "full" — all layers (may be slow or numerically unstable)
        """
        assert alpha_mode in ("adaptive", "zero", "one", "parallel"), \
            f"Unknown alpha_mode: {alpha_mode}"
        assert crown_depth in ("fc", "deep", "full"), \
            f"Unknown crown_depth: {crown_depth}"
        self.alpha_mode = alpha_mode
        self.crown_depth = crown_depth

    def compute_bounds(
        self,
        model: nn.Module,
        input_point: np.ndarray,
        epsilon: float,
    ) -> CROWNResult:
        """Compute CROWN output bounds for input_point ± epsilon.

        Hybrid strategy:
        - Forward IBP for all layers (including Conv2d, MaxPool, BN)
        - Backward CROWN only for the fully-connected tail (after Flatten)

        This is the standard CROWN implementation pattern:
        conv/pool layers use IBP (fast, sound), FC layers use CROWN
        (tighter bounds where they matter most — close to the output).

        Args:
            model: PyTorch model (Sequential of Linear/ReLU/Conv2d/BN/Flatten).
            input_point: Center point as numpy array.
            epsilon: L∞ perturbation radius (in tensor space).

        Returns:
            CROWNResult with tight output bounds.
        """
        model.eval()

        # -------------------------------------------------------
        # Step 1: Extract affine layers (W, b) and activations
        # -------------------------------------------------------
        layers_info = self._extract_layers(model, input_point.shape)

        # -------------------------------------------------------
        # Step 2: Forward IBP pass for pre-activation bounds
        # -------------------------------------------------------
        input_lo = input_point - epsilon
        input_hi = input_point + epsilon
        layer_bounds = self._forward_ibp(layers_info, input_lo, input_hi)

        # Save IBP output for comparison
        if layer_bounds:
            ibp_lo = layer_bounds[-1].post_lo.copy()
            ibp_hi = layer_bounds[-1].post_hi.copy()
        else:
            ibp_lo = input_lo.copy()
            ibp_hi = input_hi.copy()

        # -------------------------------------------------------
        # Step 3: Find where CROWN backward starts
        # -------------------------------------------------------
        fc_start = self._find_crown_start(layers_info)

        if fc_start is None:
            # No FC tail → use pure IBP
            return CROWNResult(
                output_lo=ibp_lo,
                output_hi=ibp_hi,
                ibp_output_lo=ibp_lo,
                ibp_output_hi=ibp_hi,
                crown_improvement=0.0,
                layer_bounds=layer_bounds,
            )

        # The "input" to the CROWN region is the post-activation of the previous layer
        if fc_start > 0:
            fc_input_lo = layer_bounds[fc_start - 1].post_lo
            fc_input_hi = layer_bounds[fc_start - 1].post_hi
        else:
            fc_input_lo = input_lo
            fc_input_hi = input_hi

        fc_layers = layers_info[fc_start:]
        fc_bounds = layer_bounds[fc_start:]

        # -------------------------------------------------------
        # Step 4: Backward CROWN on FC tail only
        # -------------------------------------------------------
        crown_lo, crown_hi = self._backward_crown(
            fc_layers, fc_bounds, fc_input_lo, fc_input_hi
        )

        # CROWN bounds should be at least as tight as IBP
        # (take the tighter of the two)
        final_lo = np.maximum(crown_lo, ibp_lo)
        final_hi = np.minimum(crown_hi, ibp_hi)

        # Ensure invariant: lo <= hi (numerical safety)
        final_lo = np.minimum(final_lo, final_hi)

        ibp_width = np.mean(ibp_hi - ibp_lo)
        crown_width = np.mean(final_hi - final_lo)
        improvement = 1.0 - (crown_width / ibp_width) if ibp_width > 0 else 0.0

        return CROWNResult(
            output_lo=final_lo,
            output_hi=final_hi,
            ibp_output_lo=ibp_lo,
            ibp_output_hi=ibp_hi,
            crown_improvement=improvement,
            layer_bounds=layer_bounds,
        )

    def _find_crown_start(self, layers_info: list[dict]) -> Optional[int]:
        """Find where CROWN backward pass starts.

        Returns index of first layer to include in backward pass, or None
        if CROWN can't be applied.

        Modes:
            "fc"   — starts after the last Flatten (FC tail only)
            "deep" — includes the last Conv+ReLU block before Flatten
            "full" — starts from layer 0 (entire network)
        """
        if self.crown_depth == "full":
            return 0

        # Find the flatten layer
        flatten_idx = None
        for i, layer in enumerate(layers_info):
            if layer["type"] == "flatten":
                flatten_idx = i

        if self.crown_depth == "fc":
            # Start right after flatten
            if flatten_idx is not None:
                fc_start = flatten_idx + 1
            else:
                # No flatten → check if all layers are FC
                has_non_fc = any(
                    layer["type"] in ("conv2d", "maxpool2d", "avgpool2d", "batchnorm")
                    for layer in layers_info
                )
                fc_start = 0 if not has_non_fc else None
                if fc_start is None:
                    return None

            if fc_start >= len(layers_info):
                return None
            has_affine = any(
                layers_info[i]["type"] == "affine"
                for i in range(fc_start, len(layers_info))
            )
            return fc_start if has_affine else None

        elif self.crown_depth == "deep":
            # Include the last Conv+ReLU block AND MaxPool before Flatten.
            # MaxPool is handled via mid-concretization (concretize at
            # MaxPool output, then IBP through MaxPool, start new CROWN
            # backward segment from MaxPool input).
            if flatten_idx is None:
                return 0

            # Walk backward from flatten_idx to find the conv block start.
            # Include: conv2d, relu, batchnorm, maxpool2d, avgpool2d.
            deep_start = flatten_idx
            i = flatten_idx - 1
            while i >= 0:
                ltype = layers_info[i]["type"]
                if ltype in ("maxpool2d", "avgpool2d", "relu", "batchnorm"):
                    deep_start = i
                    i -= 1
                elif ltype == "conv2d":
                    deep_start = i
                    break  # Found the conv layer, stop
                else:
                    break  # Hit a different layer type
            return deep_start

        return None

    # =============================================================
    # Layer extraction
    # =============================================================

    def _extract_layers(
        self, model: nn.Module, input_shape: tuple
    ) -> list[dict]:
        """Extract linear/affine layers and activations from PyTorch model.

        Converts the model into a list of operations:
          {"type": "affine", "W": ndarray, "b": ndarray}
          {"type": "relu"}
          {"type": "flatten"}

        Conv2d layers are kept as-is with torch weight tensors.
        BatchNorm is folded into preceding affine layer.
        """
        children = list(model.children())
        result = []
        skip_next = False

        for idx, layer in enumerate(children):
            if skip_next:
                skip_next = False
                continue

            next_layer = children[idx + 1] if idx + 1 < len(children) else None

            if isinstance(layer, nn.Linear):
                W = layer.weight.detach().cpu().numpy().astype(np.float64)
                b = layer.bias.detach().cpu().numpy().astype(np.float64) \
                    if layer.bias is not None else np.zeros(W.shape[0], dtype=np.float64)

                # Fold BN if next
                if isinstance(next_layer, (nn.BatchNorm1d, nn.BatchNorm2d)):
                    W, b = self._fold_bn(W, b, next_layer)
                    skip_next = True

                result.append({"type": "affine", "W": W, "b": b})

            elif isinstance(layer, nn.Conv2d):
                weight = layer.weight.detach().cpu().double()
                bias = layer.bias.detach().cpu().double() \
                    if layer.bias is not None else torch.zeros(layer.out_channels, dtype=torch.float64)
                stride = layer.stride[0] if isinstance(layer.stride, tuple) else layer.stride
                padding = layer.padding[0] if isinstance(layer.padding, tuple) else layer.padding

                # Fold BN if next
                if isinstance(next_layer, (nn.BatchNorm1d, nn.BatchNorm2d)):
                    weight, bias = self._fold_bn_conv(weight, bias, next_layer)
                    skip_next = True

                result.append({
                    "type": "conv2d",
                    "weight": weight,
                    "bias": bias,
                    "stride": stride,
                    "padding": padding,
                })

            elif isinstance(layer, nn.ReLU):
                result.append({"type": "relu"})

            elif isinstance(layer, nn.Flatten):
                result.append({"type": "flatten"})

            elif isinstance(layer, nn.MaxPool2d):
                ks = layer.kernel_size if isinstance(layer.kernel_size, int) else layer.kernel_size[0]
                stride = layer.stride if isinstance(layer.stride, int) else layer.stride[0]
                padding = layer.padding if isinstance(layer.padding, int) else layer.padding[0]
                result.append({
                    "type": "maxpool2d",
                    "kernel_size": ks,
                    "stride": stride,
                    "padding": padding,
                })

            elif isinstance(layer, nn.AvgPool2d):
                ks = layer.kernel_size if isinstance(layer.kernel_size, int) else layer.kernel_size[0]
                stride_val = layer.stride if isinstance(layer.stride, int) else layer.stride[0]
                padding_val = layer.padding if isinstance(layer.padding, int) else layer.padding[0]
                result.append({
                    "type": "avgpool2d",
                    "kernel_size": ks,
                    "stride": stride_val,
                    "padding": padding_val,
                })

            elif isinstance(layer, (nn.BatchNorm1d, nn.BatchNorm2d)):
                # Standalone BN (not folded) — extract scale+shift
                gamma = layer.weight.detach().cpu().numpy().astype(np.float64)
                beta = layer.bias.detach().cpu().numpy().astype(np.float64)
                running_mean = layer.running_mean.detach().cpu().numpy().astype(np.float64)
                running_var = layer.running_var.detach().cpu().numpy().astype(np.float64)
                eps = layer.eps

                scale = gamma / np.sqrt(running_var + eps)
                shift = beta - scale * running_mean
                n_dims = 2 if isinstance(layer, nn.BatchNorm2d) else 1
                result.append({"type": "batchnorm", "scale": scale, "shift": shift, "n_dims": n_dims})

            elif isinstance(layer, nn.Sequential):
                # Recursive
                sub_layers = self._extract_layers(layer, input_shape)
                result.extend(sub_layers)

            else:
                raise ValueError(
                    f"CROWN: unsupported layer type: {type(layer).__name__}. "
                    f"Supported: Linear, Conv2d, ReLU, Flatten, MaxPool2d, AvgPool2d, BatchNorm1d/2d"
                )

        return result

    @staticmethod
    def _fold_bn(W: np.ndarray, b: np.ndarray, bn_layer) -> tuple[np.ndarray, np.ndarray]:
        """Fold BatchNorm1d into Linear: (scale*W, scale*b + shift)."""
        gamma = bn_layer.weight.detach().cpu().numpy().astype(np.float64)
        beta = bn_layer.bias.detach().cpu().numpy().astype(np.float64)
        running_mean = bn_layer.running_mean.detach().cpu().numpy().astype(np.float64)
        running_var = bn_layer.running_var.detach().cpu().numpy().astype(np.float64)
        eps = bn_layer.eps

        scale = gamma / np.sqrt(running_var + eps)
        shift = beta - scale * running_mean

        W_new = scale[:, np.newaxis] * W
        b_new = scale * b + shift
        return W_new, b_new

    @staticmethod
    def _fold_bn_conv(weight: torch.Tensor, bias: torch.Tensor, bn_layer) -> tuple[torch.Tensor, torch.Tensor]:
        """Fold BatchNorm2d into Conv2d."""
        gamma = bn_layer.weight.detach().cpu().double()
        beta = bn_layer.bias.detach().cpu().double()
        running_mean = bn_layer.running_mean.detach().cpu().double()
        running_var = bn_layer.running_var.detach().cpu().double()
        eps = bn_layer.eps

        scale = gamma / torch.sqrt(running_var + eps)
        shift = beta - scale * running_mean

        # weight shape: (C_out, C_in, kH, kW)
        weight_new = scale.view(-1, 1, 1, 1) * weight
        bias_new = scale * bias + shift
        return weight_new, bias_new

    # =============================================================
    # Forward IBP pass
    # =============================================================

    def _forward_ibp(
        self,
        layers_info: list[dict],
        input_lo: np.ndarray,
        input_hi: np.ndarray,
    ) -> list[CROWNLayerBounds]:
        """Forward IBP pass to compute pre/post-activation bounds at each layer."""
        bounds = []
        lo = input_lo.copy()
        hi = input_hi.copy()

        for layer in layers_info:
            ltype = layer["type"]

            if ltype == "affine":
                W = layer["W"]
                b = layer["b"]
                W_pos = np.maximum(W, 0.0)
                W_neg = np.minimum(W, 0.0)
                pre_lo = W_pos @ lo.flatten() + W_neg @ hi.flatten() + b
                pre_hi = W_pos @ hi.flatten() + W_neg @ lo.flatten() + b
                bounds.append(CROWNLayerBounds(
                    pre_lo=pre_lo, pre_hi=pre_hi,
                    post_lo=pre_lo.copy(), post_hi=pre_hi.copy(),
                    layer_type="affine", shape=pre_lo.shape,
                ))
                lo, hi = pre_lo, pre_hi

            elif ltype == "conv2d":
                weight = layer["weight"]
                bias = layer["bias"]
                stride = layer["stride"]
                padding = layer["padding"]

                W_pos = torch.clamp(weight, min=0.0)
                W_neg = torch.clamp(weight, max=0.0)

                lo_t = torch.tensor(lo, dtype=torch.float64).unsqueeze(0)
                hi_t = torch.tensor(hi, dtype=torch.float64).unsqueeze(0)

                out_lo = (F.conv2d(lo_t, W_pos, stride=stride, padding=padding)
                          + F.conv2d(hi_t, W_neg, stride=stride, padding=padding)
                          + bias.view(1, -1, 1, 1))
                out_hi = (F.conv2d(hi_t, W_pos, stride=stride, padding=padding)
                          + F.conv2d(lo_t, W_neg, stride=stride, padding=padding)
                          + bias.view(1, -1, 1, 1))

                pre_lo = out_lo.squeeze(0).numpy()
                pre_hi = out_hi.squeeze(0).numpy()

                bounds.append(CROWNLayerBounds(
                    pre_lo=pre_lo, pre_hi=pre_hi,
                    post_lo=pre_lo.copy(), post_hi=pre_hi.copy(),
                    layer_type="conv2d", shape=pre_lo.shape,
                ))
                lo, hi = pre_lo, pre_hi

            elif ltype == "relu":
                pre_lo = lo.copy()
                pre_hi = hi.copy()
                post_lo = np.maximum(0.0, lo)
                post_hi = np.maximum(0.0, hi)
                bounds.append(CROWNLayerBounds(
                    pre_lo=pre_lo, pre_hi=pre_hi,
                    post_lo=post_lo, post_hi=post_hi,
                    layer_type="relu", shape=lo.shape,
                ))
                lo, hi = post_lo, post_hi

            elif ltype == "flatten":
                lo = lo.flatten()
                hi = hi.flatten()
                bounds.append(CROWNLayerBounds(
                    pre_lo=lo.copy(), pre_hi=hi.copy(),
                    post_lo=lo.copy(), post_hi=hi.copy(),
                    layer_type="flatten", shape=lo.shape,
                ))

            elif ltype == "maxpool2d":
                ks = layer["kernel_size"]
                stride = layer["stride"]
                padding = layer["padding"]

                lo_t = torch.tensor(lo, dtype=torch.float64).unsqueeze(0)
                hi_t = torch.tensor(hi, dtype=torch.float64).unsqueeze(0)

                out_lo = F.max_pool2d(lo_t, ks, stride, padding).squeeze(0).numpy()
                out_hi = F.max_pool2d(hi_t, ks, stride, padding).squeeze(0).numpy()

                bounds.append(CROWNLayerBounds(
                    pre_lo=out_lo, pre_hi=out_hi,
                    post_lo=out_lo.copy(), post_hi=out_hi.copy(),
                    layer_type="maxpool2d", shape=out_lo.shape,
                ))
                lo, hi = out_lo, out_hi

            elif ltype == "avgpool2d":
                ks = layer["kernel_size"]
                stride = layer["stride"]
                padding = layer["padding"]

                # AvgPool is linear and monotone with positive weights (1/k²)
                # so avgpool(lo) <= avgpool(x) <= avgpool(hi)
                lo_t = torch.tensor(lo, dtype=torch.float64).unsqueeze(0)
                hi_t = torch.tensor(hi, dtype=torch.float64).unsqueeze(0)

                out_lo = F.avg_pool2d(lo_t, ks, stride, padding).squeeze(0).numpy()
                out_hi = F.avg_pool2d(hi_t, ks, stride, padding).squeeze(0).numpy()

                bounds.append(CROWNLayerBounds(
                    pre_lo=out_lo, pre_hi=out_hi,
                    post_lo=out_lo.copy(), post_hi=out_hi.copy(),
                    layer_type="avgpool2d", shape=out_lo.shape,
                ))
                lo, hi = out_lo, out_hi

            elif ltype == "batchnorm":
                scale = layer["scale"]
                shift = layer["shift"]
                if lo.ndim == 3 and scale.ndim == 1:
                    scale_r = scale[:, np.newaxis, np.newaxis]
                    shift_r = shift[:, np.newaxis, np.newaxis]
                else:
                    scale_r = scale
                    shift_r = shift

                scale_pos = np.maximum(scale_r, 0.0)
                scale_neg = np.minimum(scale_r, 0.0)

                pre_lo = scale_pos * lo + scale_neg * hi + shift_r
                pre_hi = scale_pos * hi + scale_neg * lo + shift_r

                bounds.append(CROWNLayerBounds(
                    pre_lo=pre_lo, pre_hi=pre_hi,
                    post_lo=pre_lo.copy(), post_hi=pre_hi.copy(),
                    layer_type="batchnorm", shape=pre_lo.shape,
                ))
                lo, hi = pre_lo, pre_hi

        return bounds

    # =============================================================
    # Backward CROWN pass
    # =============================================================

    def _backward_crown(
        self,
        layers_info: list[dict],
        layer_bounds: list[CROWNLayerBounds],
        input_lo: np.ndarray,
        input_hi: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Backward CROWN pass: propagate linear bounds from output to input.

        For output neuron j, we maintain:
            output_j ∈ [Λ_lo · x + ω_lo, Λ_hi · x + ω_hi]

        where x is the flattened input vector, and (Λ, ω) are accumulated
        by back-propagating through each layer.

        Returns:
            (output_lo, output_hi) — tighter bounds than forward IBP.
        """
        if not layer_bounds:
            return input_lo.flatten().copy(), input_hi.flatten().copy()

        # Output dimension
        output_shape = layer_bounds[-1].post_lo.shape
        n_output = int(np.prod(output_shape))
        n_input = int(np.prod(input_lo.shape))

        # Initialize: Λ = I (identity), ω = 0
        # Shape: (n_output, n_input) for Λ, (n_output,) for ω
        Lambda_lo = np.eye(n_output, dtype=np.float64)
        Lambda_hi = np.eye(n_output, dtype=np.float64)
        omega_lo = np.zeros(n_output, dtype=np.float64)
        omega_hi = np.zeros(n_output, dtype=np.float64)

        # Process layers in reverse order
        for i in range(len(layers_info) - 1, -1, -1):
            layer = layers_info[i]
            bound = layer_bounds[i]
            ltype = layer["type"]

            if ltype == "relu":
                # Apply ReLU relaxation
                l = bound.pre_lo.flatten()
                u = bound.pre_hi.flatten()

                Lambda_lo, omega_lo = self._relu_backward(
                    Lambda_lo, omega_lo, l, u, bound_type="lower"
                )
                Lambda_hi, omega_hi = self._relu_backward(
                    Lambda_hi, omega_hi, l, u, bound_type="upper"
                )

            elif ltype == "affine":
                W = layer["W"]  # (out, in)
                b = layer["b"]  # (out,)

                # Λ_new = Λ_old @ W
                # ω_new = ω_old + Λ_old @ b
                omega_lo = omega_lo + Lambda_lo @ b
                omega_hi = omega_hi + Lambda_hi @ b
                Lambda_lo = Lambda_lo @ W
                Lambda_hi = Lambda_hi @ W

            elif ltype == "conv2d":
                # For CROWN backward through conv2d, we need the Jacobian.
                weight = layer["weight"]
                bias = layer["bias"]
                stride = layer["stride"]
                padding = layer["padding"]

                # Get pre-activation shape at this layer (spatial)
                conv_out_shape = bound.pre_lo.shape  # (C_out, H_out, W_out)

                # Get input shape: the post shape of previous layer
                if i > 0:
                    prev_shape = layer_bounds[i - 1].post_lo.shape
                else:
                    prev_shape = input_lo.shape

                # Handle bias: bias is (C_out,), repeated over spatial dims
                if len(conv_out_shape) == 3:
                    C_out, H_out, W_out = conv_out_shape
                    bias_expanded = np.repeat(bias.numpy(), H_out * W_out)
                else:
                    bias_expanded = bias.numpy()

                omega_lo = omega_lo + Lambda_lo @ bias_expanded
                omega_hi = omega_hi + Lambda_hi @ bias_expanded

                # Back-propagate through conv using Jacobian
                Lambda_lo = self._conv2d_backward_lambda(
                    Lambda_lo, weight, stride, padding,
                    conv_out_shape, prev_shape
                )
                Lambda_hi = self._conv2d_backward_lambda(
                    Lambda_hi, weight, stride, padding,
                    conv_out_shape, prev_shape
                )

            elif ltype == "flatten":
                # Flatten is just a reshape — no change to Lambda/omega
                # Lambda columns already correspond to flattened spatial dims
                pass

            elif ltype == "maxpool2d":
                # MaxPool: mid-concretization approach.
                # 1. Concretize current Lambda/omega at MaxPool output bounds
                #    to get tighter interval bounds there.
                # 2. IBP backward through MaxPool to get tighter input bounds.
                # 3. Re-init Lambda=I, omega=0 for the next CROWN segment.

                # Get the MaxPool output bounds (post-MaxPool IBP)
                mp_out_lo = bound.post_lo.flatten()
                mp_out_hi = bound.post_hi.flatten()

                # Concretize current linear bounds at the MaxPool output interval
                mid_lo = self._concretize(
                    Lambda_lo, omega_lo, mp_out_lo, mp_out_hi, "lower"
                )
                mid_hi = self._concretize(
                    Lambda_hi, omega_hi, mp_out_lo, mp_out_hi, "upper"
                )

                # Now we have tighter bounds at the output of this stage.
                # Propagate through MaxPool using IBP (sound).
                # MaxPool IBP backward: lo = maxpool(prev_lo), hi = maxpool(prev_hi)
                # The tighter bounds at MaxPool output don't help us get tighter
                # bounds at MaxPool INPUT via IBP. However, we can start a new
                # CROWN segment from the MaxPool input.

                # Get the pre-MaxPool bounds
                if i > 0:
                    prev_shape = layer_bounds[i - 1].post_lo.shape
                else:
                    prev_shape = input_lo.shape

                n_prev = int(np.prod(prev_shape))

                # Re-initialize Lambda/omega for the new CROWN segment
                # starting from the MaxPool input (pre-MaxPool space)
                n_mid = len(mid_lo)
                Lambda_lo = np.zeros((n_mid, n_prev), dtype=np.float64)
                Lambda_hi = np.zeros((n_mid, n_prev), dtype=np.float64)

                # Use the mid-concretized bounds directly as interval bounds.
                # The new CROWN segment will refine from here.
                # We skip further backward propagation through MaxPool —
                # the tighter bounds are captured in omega.
                omega_lo = mid_lo
                omega_hi = mid_hi

                # Since Lambda=0 and omega=mid, concretization will just give
                # omega (constant bounds, independent of earlier layers).
                # This means CROWN doesn't propagate through MaxPool,
                # but it does give tighter bounds at the MaxPool output
                # from the layers AFTER MaxPool.

            elif ltype == "avgpool2d":
                # AvgPool2d is a LINEAR operation with fixed weights (1/k²).
                # CROWN can backward-propagate through it cleanly.
                # No bias, just Λ_new = Λ_old @ J_avgpool.
                ks = layer["kernel_size"]
                stride_val = layer["stride"]
                padding_val = layer["padding"]

                pool_out_shape = bound.pre_lo.shape

                if i > 0:
                    prev_shape = layer_bounds[i - 1].post_lo.shape
                else:
                    prev_shape = input_lo.shape

                # Build AvgPool Jacobian using torch
                J = self._avgpool_jacobian(
                    ks, stride_val, padding_val, pool_out_shape, prev_shape
                )

                Lambda_lo = Lambda_lo @ J
                Lambda_hi = Lambda_hi @ J

            elif ltype == "batchnorm":
                scale = layer["scale"]
                shift = layer["shift"]

                if bound.pre_lo.ndim == 3 and scale.ndim == 1:
                    h, w = bound.pre_lo.shape[1], bound.pre_lo.shape[2]
                    scale_flat = np.repeat(scale, h * w)
                    shift_flat = np.repeat(shift, h * w)
                else:
                    scale_flat = scale
                    shift_flat = shift

                # BN is y = scale * x + shift
                omega_lo = omega_lo + Lambda_lo @ shift_flat
                omega_hi = omega_hi + Lambda_hi @ shift_flat
                Lambda_lo = Lambda_lo * scale_flat[np.newaxis, :]
                Lambda_hi = Lambda_hi * scale_flat[np.newaxis, :]

        # -------------------------------------------------------
        # Step 4: Concretize bounds at input interval
        # -------------------------------------------------------
        x_lo = input_lo.flatten()
        x_hi = input_hi.flatten()

        output_lo = self._concretize(Lambda_lo, omega_lo, x_lo, x_hi, bound_type="lower")
        output_hi = self._concretize(Lambda_hi, omega_hi, x_lo, x_hi, bound_type="upper")

        return output_lo, output_hi

    def _relu_backward(
        self,
        Lambda: np.ndarray,
        omega: np.ndarray,
        l: np.ndarray,
        u: np.ndarray,
        bound_type: str,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Back-propagate through ReLU relaxation.

        For each neuron j with pre-activation bounds [l_j, u_j]:

        Case 1: l_j >= 0 (stable positive)
            ReLU is identity → no change to Lambda[:,j] or omega

        Case 2: u_j <= 0 (stable negative)
            ReLU is zero → Lambda[:,j] = 0

        Case 3: l_j < 0 < u_j (unstable)
            Upper bound: line through (l,0)→(u,u): y = u/(u-l) * (x - l)
                slope = u/(u-l), intercept = -u*l/(u-l)
            Lower bound: depends on alpha_mode
                "adaptive": slope = u/(u-l) (same as upper)
                "zero": slope = 0
                "one": slope = 1

        For bound_type="upper":
            Lambda[:,j] *= upper_slope
            omega += Lambda[:,j] * upper_intercept  (before scaling Lambda)

        For bound_type="lower":
            Lambda[:,j] *= lower_slope
            omega += Lambda[:,j] * lower_intercept  (before scaling Lambda)
        """
        n_neurons = l.shape[0]

        # Classify neurons
        stable_pos = l >= 0  # Identity
        stable_neg = u <= 0  # Zero
        unstable = ~stable_pos & ~stable_neg  # Need relaxation

        # For stable positive: no change
        # For stable negative: zero out
        for j in range(n_neurons):
            if stable_neg[j]:
                Lambda[:, j] = 0.0

        # For unstable neurons: apply linear relaxation
        unstable_idx = np.where(unstable)[0]
        if len(unstable_idx) == 0:
            return Lambda, omega

        l_u = l[unstable_idx]
        u_u = u[unstable_idx]
        denom = u_u - l_u  # Always positive (u > 0 > l)

        # Upper bound slope and intercept (same for lower and upper bound_type
        # when Lambda entry is positive/negative)
        upper_slope = u_u / denom
        upper_intercept = -u_u * l_u / denom  # Always positive

        if bound_type == "upper":
            # For upper bound: when Lambda[:,j] > 0, use upper relaxation
            #                   when Lambda[:,j] < 0, use lower relaxation
            for k, j in enumerate(unstable_idx):
                lj = Lambda[:, j].copy()
                pos_mask = lj >= 0
                neg_mask = ~pos_mask

                # Positive Lambda entries use upper bound of ReLU
                if np.any(pos_mask):
                    omega[pos_mask] += lj[pos_mask] * upper_intercept[k]
                    Lambda[pos_mask, j] *= upper_slope[k]

                # Negative Lambda entries use lower bound of ReLU
                if np.any(neg_mask):
                    alpha = self._get_alpha(l_u[k], u_u[k])
                    # Lower bound: y >= alpha * x (no intercept for lower bound with zero intercept)
                    # Actually lower bound: y >= alpha * x
                    # intercept = 0 when alpha chosen this way
                    Lambda[neg_mask, j] *= alpha

        else:  # bound_type == "lower"
            # For lower bound: when Lambda[:,j] > 0, use lower relaxation
            #                    when Lambda[:,j] < 0, use upper relaxation
            for k, j in enumerate(unstable_idx):
                lj = Lambda[:, j].copy()
                pos_mask = lj >= 0
                neg_mask = ~pos_mask

                # Positive Lambda entries use lower bound of ReLU
                if np.any(pos_mask):
                    alpha = self._get_alpha(l_u[k], u_u[k])
                    Lambda[pos_mask, j] *= alpha

                # Negative Lambda entries use upper bound of ReLU
                if np.any(neg_mask):
                    omega[neg_mask] += lj[neg_mask] * upper_intercept[k]
                    Lambda[neg_mask, j] *= upper_slope[k]

        return Lambda, omega

    def _get_alpha(self, l: float, u: float) -> float:
        """Get lower bound slope for an unstable ReLU neuron.

        Args:
            l: Pre-activation lower bound (negative).
            u: Pre-activation upper bound (positive).

        Returns:
            Slope alpha ∈ [0, 1] for the lower linear bound.
        """
        if self.alpha_mode == "zero":
            return 0.0
        elif self.alpha_mode == "one":
            return 1.0
        elif self.alpha_mode == "adaptive":
            # Minimize relaxation area: if u > |l|, lean towards identity
            return float(u / (u - l))
        elif self.alpha_mode == "parallel":
            return float(u / (u - l))
        else:
            return 0.0

    def _conv2d_backward_lambda(
        self,
        Lambda: np.ndarray,
        weight: torch.Tensor,
        stride: int,
        padding: int,
        conv_out_shape: tuple,
        prev_shape: tuple,
    ) -> np.ndarray:
        """Back-propagate Lambda through a Conv2d layer.

        Uses the Jacobian of the conv2d operation to compute Lambda @ J.
        The Jacobian J[i,j] = d(conv_output_flat[i]) / d(input_flat[j]).

        Lambda: (n_output, n_curr) where n_curr = prod(conv_out_shape)
        Returns: (n_output, n_prev) where n_prev = prod(prev_shape)
        """
        n_output = Lambda.shape[0]
        n_curr = int(np.prod(conv_out_shape))
        n_prev = int(np.prod(prev_shape))

        # Build Jacobian by probing with unit vectors
        # J shape: (n_curr, n_prev), J[i,j] = ∂conv_out[i]/∂input[j]
        J = np.zeros((n_curr, n_prev), dtype=np.float64)
        for j in range(n_prev):
            e_j = np.zeros(n_prev, dtype=np.float64)
            e_j[j] = 1.0
            x = torch.tensor(e_j.reshape(prev_shape), dtype=torch.float64).unsqueeze(0)
            out = F.conv2d(x, weight, stride=stride, padding=padding)
            J[:, j] = out.squeeze(0).flatten().numpy()

        return Lambda @ J

    def _maxpool_backward_lambda(
        self,
        Lambda: np.ndarray,
        bound: CROWNLayerBounds,
        kernel_size: int,
        stride: int,
        padding: int,
        prev_shape: tuple,
        prev_layer_bounds: Optional[CROWNLayerBounds] = None,
    ) -> np.ndarray:
        """Back-propagate Lambda through MaxPool2d.

        Uses the midpoint of the pre-maxpool interval to determine which
        input element wins each pool window, then back-propagates as a
        selection (identity on winners). This is sound for MaxPool because
        max_pool(lo) <= max_pool(x) <= max_pool(hi) — the routing may
        differ but the bounds remain valid.

        Args:
            prev_layer_bounds: Bounds of the layer BEFORE maxpool (the input
                to maxpool). Needed to compute midpoint for routing.
        """
        n_output = Lambda.shape[0]
        n_prev = int(np.prod(prev_shape))
        n_curr = int(np.prod(bound.pre_lo.shape))

        if n_curr == n_prev:
            return Lambda  # No spatial reduction

        if len(prev_shape) != 3:
            # Fallback for non-3D inputs
            return Lambda[:, :n_prev] if Lambda.shape[1] >= n_prev else \
                np.hstack([Lambda, np.zeros((n_output, n_prev - Lambda.shape[1]))])

        C, H, W = prev_shape

        # Use the midpoint of the input-to-maxpool interval to determine
        # which element wins each window
        if prev_layer_bounds is not None:
            mid = (prev_layer_bounds.post_lo + prev_layer_bounds.post_hi) / 2.0
        else:
            # Fallback: use arange (deterministic routing)
            mid = np.arange(n_prev, dtype=np.float64).reshape(prev_shape)

        mid_t = torch.tensor(mid, dtype=torch.float64).unsqueeze(0)
        _, indices = F.max_pool2d(
            mid_t, kernel_size, stride, padding, return_indices=True
        )
        indices_flat = indices.flatten().numpy().astype(int)

        # Build selection matrix: each maxpool output maps to one input
        J = np.zeros((n_curr, n_prev), dtype=np.float64)
        for out_idx, in_idx in enumerate(indices_flat):
            if in_idx < n_prev:
                J[out_idx, in_idx] = 1.0

        return Lambda @ J

    def _avgpool_jacobian(
        self,
        kernel_size: int,
        stride: int,
        padding: int,
        pool_out_shape: tuple,
        prev_shape: tuple,
    ) -> np.ndarray:
        """Build the Jacobian matrix for AvgPool2d.

        AvgPool is a fixed linear operation: each output element is the
        average of k² input elements. The Jacobian has entries 1/k² at
        the corresponding positions.

        Returns: (n_out, n_in) numpy array.
        """
        n_out = int(np.prod(pool_out_shape))
        n_in = int(np.prod(prev_shape))

        # Build Jacobian by probing with unit vectors (same approach as conv2d)
        J = np.zeros((n_out, n_in), dtype=np.float64)
        for j in range(n_in):
            e_j = np.zeros(n_in, dtype=np.float64)
            e_j[j] = 1.0
            x = torch.tensor(e_j.reshape(prev_shape), dtype=torch.float64).unsqueeze(0)
            out = F.avg_pool2d(x, kernel_size, stride, padding)
            J[:, j] = out.squeeze(0).flatten().numpy()

        return J

    def _concretize(
        self,
        Lambda: np.ndarray,
        omega: np.ndarray,
        x_lo: np.ndarray,
        x_hi: np.ndarray,
        bound_type: str,
    ) -> np.ndarray:
        """Evaluate linear bounds at input interval to get concrete bounds.

        For lower bound: minimize Λ·x + ω over x ∈ [x_lo, x_hi]
            = Λ_pos · x_lo + Λ_neg · x_hi + ω

        For upper bound: maximize Λ·x + ω over x ∈ [x_lo, x_hi]
            = Λ_pos · x_hi + Λ_neg · x_lo + ω
        """
        Lambda_pos = np.maximum(Lambda, 0.0)
        Lambda_neg = np.minimum(Lambda, 0.0)

        if bound_type == "lower":
            return Lambda_pos @ x_lo + Lambda_neg @ x_hi + omega
        else:
            return Lambda_pos @ x_hi + Lambda_neg @ x_lo + omega


# =============================================================
# Convenience function for integration with verifier
# =============================================================


def crown_verify(
    model: nn.Module,
    input_point: np.ndarray,
    epsilon: float,
    alpha_mode: str = "adaptive",
) -> CROWNResult:
    """Convenience function: run CROWN verification on a single input.

    Args:
        model: PyTorch model.
        input_point: Center point.
        epsilon: L∞ perturbation radius.
        alpha_mode: CROWN alpha selection strategy.

    Returns:
        CROWNResult with tight output bounds.
    """
    engine = CROWNEngine(alpha_mode=alpha_mode)
    return engine.compute_bounds(model, input_point, epsilon)
