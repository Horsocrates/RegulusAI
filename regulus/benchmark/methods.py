"""
Uncertainty quantification methods for benchmarking.

All methods implement: predict_with_uncertainty(X) -> (preds, probs, uncertainties)
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

from regulus.nn.model import convert_model
from regulus.nn.interval_tensor import IntervalTensor
from regulus.analysis.reliability import ReliabilityAnalysis, predict_max_width


# =============================================================
# Shared: Margin-based uncertainty signal
# =============================================================

def _compute_margin_uncertainty(output_interval: IntervalTensor) -> float:
    """Margin-based uncertainty: gap between top-2 midpoints / width.

    Low margin = classes are close in interval space = uncertain.
    Returns uncertainty in (0, 1]: higher = more uncertain.
    """
    mids = output_interval.midpoint
    sorted_mids = np.sort(mids)[::-1]  # descending
    gap = sorted_mids[0] - sorted_mids[1]
    w = output_interval.mean_width()
    if w < 1e-10:
        margin = gap  # width ~0 -> use raw gap
    else:
        margin = gap / w
    return 1.0 / (1.0 + margin)


# =============================================================
# Regulus — Interval Bound Propagation (OUR method)
# =============================================================

class RegulusMethod:
    """Interval Bound Propagation with Coq-proven width bounds."""

    def __init__(self, torch_model, input_eps: float = 0.1):
        self.torch_model = torch_model
        self.interval_model = convert_model(torch_model)
        self.input_eps = input_eps
        self._width_bound = predict_max_width(self.interval_model, input_eps)

    def predict_with_uncertainty(self, X: np.ndarray):
        import torch

        # Use base model for predictions (same as other methods)
        self.torch_model.eval()
        with torch.no_grad():
            logits = self.torch_model(torch.FloatTensor(X))
            preds = logits.argmax(dim=-1).numpy()

        # Use interval width as uncertainty signal
        uncertainties = []
        for i in range(len(X)):
            x_interval = IntervalTensor.from_uncertainty(X[i], self.input_eps)
            output = self.interval_model(x_interval)
            uncertainties.append(output.max_width())

        return preds, None, np.array(uncertainties)

    @property
    def name(self):
        return f"Regulus (eps={self.input_eps})"

    @property
    def cost(self):
        return 1

    @property
    def width_bound(self):
        return self._width_bound


# =============================================================
# Regulus -- Re-anchored IBP (P4 Hypothesis)
# =============================================================

class ReanchoredRegulusMethod:
    """Re-anchored Interval Bound Propagation.

    Process-based: splits model into blocks, re-anchors between them.
    Same cost as naive IBP (1 forward pass) but controlled width.

    signal='width'  : use max output width as uncertainty (original)
    signal='margin' : use margin between top-2 midpoints / width (P4 discovery)
    """

    def __init__(
        self,
        torch_model,
        input_eps: float = 0.02,
        block_size: int = 1,
        reanchor_eps: float = 0.001,
        strategy: str = "midpoint",
        adaptive_threshold: float = 1.0,
        shrink_factor: float = 0.1,
        signal: str = "width",
    ):
        self.torch_model = torch_model
        self.input_eps = input_eps
        self.block_size = block_size
        self._reanchor_eps = reanchor_eps
        self._strategy = strategy
        self._shrink_factor = shrink_factor
        self._signal = signal

        from regulus.nn.reanchor import ReanchoredIntervalModel

        self.reanchor_model = ReanchoredIntervalModel(
            torch_model,
            block_size=block_size,
            reanchor_eps=reanchor_eps,
            strategy=strategy,
            adaptive_threshold=adaptive_threshold,
            shrink_factor=shrink_factor,
        )

    def predict_with_uncertainty(self, X: np.ndarray):
        # Predictions from base model (same as other methods)
        self.torch_model.eval()
        with torch.no_grad():
            logits = self.torch_model(torch.FloatTensor(X))
            preds = logits.argmax(dim=-1).numpy()

        # Uncertainty from re-anchored intervals
        uncertainties = []
        for i in range(len(X)):
            x_interval = IntervalTensor.from_uncertainty(X[i], self.input_eps)
            output = self.reanchor_model(x_interval)
            if self._signal == "margin":
                uncertainties.append(_compute_margin_uncertainty(output))
            else:
                uncertainties.append(output.max_width())

        return preds, None, np.array(uncertainties)

    @property
    def name(self):
        sig = "+Margin" if self._signal == "margin" else ""
        return (
            f"Reanchor (bs={self.block_size}, "
            f"re={self._reanchor_eps}, {self._strategy}){sig}"
        )

    @property
    def cost(self):
        return 1


# =============================================================
# Naive IBP + Margin signal (for comparison)
# =============================================================

class NaiveIBPMarginMethod:
    """Naive IBP with margin-based uncertainty signal.

    Uses full-chain interval propagation (no re-anchoring) but computes
    margin between top-2 class midpoints instead of width.
    This proves that re-anchoring is essential: naive IBP intervals are
    so wide that midpoints lose discriminative meaning.
    """

    def __init__(self, torch_model, input_eps: float = 0.02):
        self.torch_model = torch_model
        self.interval_model = convert_model(torch_model)
        self.input_eps = input_eps

    def predict_with_uncertainty(self, X: np.ndarray):
        self.torch_model.eval()
        with torch.no_grad():
            logits = self.torch_model(torch.FloatTensor(X))
            preds = logits.argmax(dim=-1).numpy()

        uncertainties = []
        for i in range(len(X)):
            x_interval = IntervalTensor.from_uncertainty(X[i], self.input_eps)
            output = self.interval_model(x_interval)
            uncertainties.append(_compute_margin_uncertainty(output))

        return preds, None, np.array(uncertainties)

    @property
    def name(self):
        return f"Naive IBP+Margin (eps={self.input_eps})"

    @property
    def cost(self):
        return 1


# =============================================================
# MC Dropout
# =============================================================

class MCDropoutModel(nn.Module):
    """MLP with Dropout layers for MC Dropout inference."""

    def __init__(self, layer_dims: list[int], dropout_p: float = 0.1):
        super().__init__()
        layers = []
        for i in range(len(layer_dims) - 2):
            layers.extend([
                nn.Linear(layer_dims[i], layer_dims[i + 1]),
                nn.ReLU(),
                nn.Dropout(dropout_p),
            ])
        layers.append(nn.Linear(layer_dims[-2], layer_dims[-1]))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x)


class MCDropoutMethod:
    """MC Dropout uncertainty estimation."""

    def __init__(self, torch_model, n_samples: int = 50, dropout_p: float = 0.1):
        self.n_samples = n_samples
        self.dropout_p = dropout_p
        self.model = None
        self._base_model = torch_model

    def train_model(self, model_fn, X_train, y_train, epochs=100, lr=0.001):
        """Train a model with dropout layers."""
        # Extract architecture from model_fn
        base = model_fn()
        dims = []
        for m in base.modules():
            if isinstance(m, nn.Linear):
                if not dims:
                    dims.append(m.in_features)
                dims.append(m.out_features)

        self.model = MCDropoutModel(dims, self.dropout_p)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.CrossEntropyLoss()

        X_t = torch.FloatTensor(X_train)
        y_t = torch.LongTensor(y_train)

        self.model.train()
        for _ in range(epochs):
            optimizer.zero_grad()
            loss = criterion(self.model(X_t), y_t)
            loss.backward()
            optimizer.step()

    def predict_with_uncertainty(self, X: np.ndarray):
        if self.model is None:
            raise RuntimeError("Call train_model first")

        X_t = torch.FloatTensor(X)
        self.model.train()  # Keep dropout active

        outputs = []
        with torch.no_grad():
            for _ in range(self.n_samples):
                logits = self.model(X_t)
                probs = torch.softmax(logits, dim=-1)
                outputs.append(probs)

        outputs = torch.stack(outputs)  # (n_samples, batch, classes)
        mean_probs = outputs.mean(dim=0)
        std_probs = outputs.std(dim=0)

        preds = mean_probs.argmax(dim=-1).numpy()
        uncertainty = std_probs.max(dim=-1).values.numpy()

        return preds, mean_probs.numpy(), uncertainty

    @property
    def name(self):
        return f"MC Dropout (N={self.n_samples})"

    @property
    def cost(self):
        return self.n_samples


# =============================================================
# Deep Ensembles
# =============================================================

class DeepEnsembleMethod:
    """Deep Ensembles uncertainty estimation."""

    def __init__(self, torch_model, n_models: int = 5):
        self.n_models = n_models
        self.models = []

    def train_model(self, model_fn, X_train, y_train, epochs=100, lr=0.001):
        """Train n_models with different random seeds."""
        X_t = torch.FloatTensor(X_train)
        y_t = torch.LongTensor(y_train)

        self.models = []
        for i in range(self.n_models):
            torch.manual_seed(i * 42 + 7)
            model = model_fn()
            optimizer = torch.optim.Adam(model.parameters(), lr=lr)
            criterion = nn.CrossEntropyLoss()

            model.train()
            for _ in range(epochs):
                optimizer.zero_grad()
                loss = criterion(model(X_t), y_t)
                loss.backward()
                optimizer.step()

            model.eval()
            self.models.append(model)

    def predict_with_uncertainty(self, X: np.ndarray):
        if not self.models:
            raise RuntimeError("Call train_model first")

        X_t = torch.FloatTensor(X)

        outputs = []
        for model in self.models:
            model.eval()
            with torch.no_grad():
                probs = torch.softmax(model(X_t), dim=-1)
                outputs.append(probs)

        outputs = torch.stack(outputs)
        mean_probs = outputs.mean(dim=0)
        std_probs = outputs.std(dim=0)

        preds = mean_probs.argmax(dim=-1).numpy()
        uncertainty = std_probs.max(dim=-1).values.numpy()

        return preds, mean_probs.numpy(), uncertainty

    @property
    def name(self):
        return f"Deep Ensemble (K={self.n_models})"

    @property
    def cost(self):
        return self.n_models


# =============================================================
# Temperature Scaling
# =============================================================

class TempScalingMethod:
    """Temperature Scaling for calibration."""

    def __init__(self, torch_model):
        self.model = torch_model
        self.temperature = 1.0

    def calibrate(self, X_val, y_val):
        """Find optimal temperature on validation data."""
        X_t = torch.FloatTensor(X_val)
        y_t = torch.LongTensor(y_val)

        self.model.eval()
        with torch.no_grad():
            logits = self.model(X_t)

        temp = nn.Parameter(torch.ones(1) * 1.5)
        optimizer = torch.optim.LBFGS([temp], lr=0.01, max_iter=50)

        def closure():
            optimizer.zero_grad()
            loss = nn.CrossEntropyLoss()(logits / temp, y_t)
            loss.backward()
            return loss

        optimizer.step(closure)
        self.temperature = max(temp.item(), 0.1)  # Prevent degenerate T
        return self.temperature

    def predict_with_uncertainty(self, X: np.ndarray):
        X_t = torch.FloatTensor(X)

        self.model.eval()
        with torch.no_grad():
            logits = self.model(X_t)
            probs = torch.softmax(logits / self.temperature, dim=-1)

        preds = probs.argmax(dim=-1).numpy()
        uncertainty = (1.0 - probs.max(dim=-1).values).numpy()

        return preds, probs.numpy(), uncertainty

    @property
    def name(self):
        return f"Temp Scaling (T={self.temperature:.2f})"

    @property
    def cost(self):
        return 1
