"""
Benchmark runner: train base model, run all methods, collect metrics.

Usage:
    from regulus.benchmark.runner import BenchmarkRunner
    runner = BenchmarkRunner(datasets=['breast_cancer', 'credit'])
    results = runner.run()
"""

from __future__ import annotations

import time
import numpy as np
import torch
import torch.nn as nn

from regulus.benchmark.datasets import load_dataset
from regulus.benchmark.methods import (
    RegulusMethod,
    MCDropoutMethod,
    DeepEnsembleMethod,
    TempScalingMethod,
)
from regulus.benchmark.metrics import compute_metrics, compute_coverage_curve
from regulus.analysis.reliability import predict_max_width
from regulus.nn.model import convert_model
from regulus.nn.interval_tensor import IntervalTensor


def train_base_model(model_fn, X_train, y_train, epochs=100, lr=0.001):
    """Train a model with standard cross-entropy."""
    model = model_fn()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    X_t = torch.FloatTensor(X_train)
    y_t = torch.LongTensor(y_train)

    model.train()
    for epoch in range(epochs):
        optimizer.zero_grad()
        loss = criterion(model(X_t), y_t)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        logits = model(X_t)
        acc = (logits.argmax(dim=-1) == y_t).float().mean().item()

    return model, acc


class BenchmarkRunner:
    """Run all benchmark methods on all datasets."""

    def __init__(
        self,
        datasets: list[str] | None = None,
        regulus_eps: list[float] | None = None,
        mc_samples: int = 50,
        ensemble_k: int = 5,
        subset_test: int | None = None,
    ):
        self.dataset_names = datasets or ["breast_cancer", "credit"]
        self.regulus_eps = regulus_eps or [0.01, 0.05, 0.1]
        self.mc_samples = mc_samples
        self.ensemble_k = ensemble_k
        self.subset_test = subset_test  # Limit test samples for speed

    def run(self) -> list[dict]:
        """Run full benchmark. Returns list of result dicts."""
        all_results = []

        for ds_name in self.dataset_names:
            print(f"\n{'='*60}")
            print(f"Dataset: {ds_name}")
            print(f"{'='*60}")

            try:
                data = load_dataset(ds_name)
            except Exception as e:
                print(f"  SKIP: {e}")
                continue

            X_train = data["X_train"].astype(np.float32)
            X_test = data["X_test"].astype(np.float32)
            y_train = data["y_train"].astype(np.int64)
            y_test = data["y_test"].astype(np.int64)
            model_fn = data["model_fn"]
            epochs = data.get("epochs", 100)
            lr = data.get("lr", 0.001)
            default_eps = data.get("input_eps", 0.1)

            if self.subset_test and len(X_test) > self.subset_test:
                idx = np.random.default_rng(42).choice(
                    len(X_test), self.subset_test, replace=False
                )
                X_test = X_test[idx]
                y_test = y_test[idx]

            # --- Train base model ---
            print(f"  Training base model ({epochs} epochs)...")
            t0 = time.time()
            base_model, train_acc = train_base_model(
                model_fn, X_train, y_train, epochs=epochs, lr=lr
            )
            t_train = time.time() - t0
            print(f"  Train accuracy: {train_acc:.4f} ({t_train:.1f}s)")

            # --- Regulus methods (various eps) ---
            for eps in self.regulus_eps:
                result = self._run_regulus(
                    base_model, X_test, y_test, eps, ds_name
                )
                all_results.append(result)

            # --- MC Dropout ---
            result = self._run_mc_dropout(
                model_fn, X_train, y_train, X_test, y_test,
                epochs, lr, ds_name
            )
            all_results.append(result)

            # --- Deep Ensemble ---
            result = self._run_ensemble(
                model_fn, X_train, y_train, X_test, y_test,
                epochs, lr, ds_name
            )
            all_results.append(result)

            # --- Temperature Scaling ---
            result = self._run_temp_scaling(
                base_model, X_train, y_train, X_test, y_test, ds_name
            )
            all_results.append(result)

        return all_results

    def _run_regulus(self, base_model, X_test, y_test, eps, ds_name):
        name = f"Regulus (eps={eps})"
        print(f"\n  {name}")
        t0 = time.time()

        method = RegulusMethod(base_model, input_eps=eps)
        preds, probs, unc = method.predict_with_uncertainty(X_test)

        t_inf = time.time() - t0
        print(f"    Inference: {t_inf:.2f}s")

        metrics = compute_metrics(preds, unc, y_test, name, probs)
        coverage = compute_coverage_curve(preds, unc, y_test)

        # Width bound info
        interval_model = convert_model(base_model)
        bound_info = predict_max_width(interval_model, eps)

        metrics.update({
            "dataset": ds_name,
            "cost": method.cost,
            "inference_time": t_inf,
            "predicted_max_width": bound_info["output_width_bound"],
            "actual_max_width": float(unc.max()) if len(unc) > 0 else 0,
            "bound_tightness": (
                bound_info["output_width_bound"] / unc.max()
                if unc.max() > 0 else float("inf")
            ),
            "blowup_factor": bound_info["blowup_factor"],
            "coverage_curve": coverage,
        })
        self._print_summary(metrics)
        return metrics

    def _run_mc_dropout(
        self, model_fn, X_train, y_train, X_test, y_test, epochs, lr, ds_name
    ):
        name = f"MC Dropout (N={self.mc_samples})"
        print(f"\n  {name}")
        t0 = time.time()

        method = MCDropoutMethod(None, n_samples=self.mc_samples)
        method.train_model(model_fn, X_train, y_train, epochs=epochs, lr=lr)

        t_train = time.time() - t0
        print(f"    Training: {t_train:.1f}s")

        t0 = time.time()
        preds, probs, unc = method.predict_with_uncertainty(X_test)
        t_inf = time.time() - t0
        print(f"    Inference: {t_inf:.2f}s ({self.mc_samples} forward passes)")

        metrics = compute_metrics(preds, unc, y_test, name, probs)
        coverage = compute_coverage_curve(preds, unc, y_test)
        metrics.update({
            "dataset": ds_name,
            "cost": method.cost,
            "inference_time": t_inf,
            "coverage_curve": coverage,
        })
        self._print_summary(metrics)
        return metrics

    def _run_ensemble(
        self, model_fn, X_train, y_train, X_test, y_test, epochs, lr, ds_name
    ):
        name = f"Deep Ensemble (K={self.ensemble_k})"
        print(f"\n  {name}")
        t0 = time.time()

        method = DeepEnsembleMethod(None, n_models=self.ensemble_k)
        method.train_model(model_fn, X_train, y_train, epochs=epochs, lr=lr)

        t_train = time.time() - t0
        print(f"    Training: {t_train:.1f}s ({self.ensemble_k} models)")

        t0 = time.time()
        preds, probs, unc = method.predict_with_uncertainty(X_test)
        t_inf = time.time() - t0
        print(f"    Inference: {t_inf:.2f}s")

        metrics = compute_metrics(preds, unc, y_test, name, probs)
        coverage = compute_coverage_curve(preds, unc, y_test)
        metrics.update({
            "dataset": ds_name,
            "cost": method.cost,
            "inference_time": t_inf,
            "coverage_curve": coverage,
        })
        self._print_summary(metrics)
        return metrics

    def _run_temp_scaling(
        self, base_model, X_train, y_train, X_test, y_test, ds_name
    ):
        name = "Temp Scaling"
        print(f"\n  {name}")
        t0 = time.time()

        method = TempScalingMethod(base_model)
        T = method.calibrate(X_train, y_train)
        print(f"    Temperature: {T:.3f}")

        preds, probs, unc = method.predict_with_uncertainty(X_test)
        t_inf = time.time() - t0
        print(f"    Inference: {t_inf:.2f}s")

        metrics = compute_metrics(preds, unc, y_test, method.name, probs)
        coverage = compute_coverage_curve(preds, unc, y_test)
        metrics.update({
            "dataset": ds_name,
            "cost": method.cost,
            "inference_time": t_inf,
            "coverage_curve": coverage,
        })
        self._print_summary(metrics)
        return metrics

    @staticmethod
    def _print_summary(m):
        print(f"    Accuracy: {m['accuracy']:.4f}")
        auroc = m.get("auroc", float("nan"))
        print(f"    AUROC:    {auroc:.4f}" if not np.isnan(auroc) else "    AUROC:    N/A")
        print(f"    ECE:      {m['ece']:.4f}")
        sa10 = m.get("selective_acc@10%", float("nan"))
        if not np.isnan(sa10):
            print(f"    Sel.Acc@10%: {sa10:.4f}")
        if "predicted_max_width" in m:
            print(f"    Predicted width: {m['predicted_max_width']:.4f}")
            print(f"    Actual width:    {m['actual_max_width']:.4f}")
            print(f"    Bound tightness: {m['bound_tightness']:.1f}x")
