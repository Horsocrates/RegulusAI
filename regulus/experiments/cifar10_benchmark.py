"""
CIFAR-10 Benchmark + Traceable Uncertainty.

Two tracks:
  1. CIFAR-10 benchmark -- prove method generalizes beyond MNIST
  2. Traceable uncertainty -- show WHICH block caused unreliability

2 architectures x 5 methods on CIFAR-10:
  CNN+BN:     Conv->BN->ReLU x4 + Pool x2 -> FC
  ResNet+BN:  Conv->BN->ReLU + 2 ResBlocks -> FC

Usage:
    .venv313\\Scripts\\python.exe -u -m regulus.experiments.cifar10_benchmark
    .venv313\\Scripts\\python.exe -u -m regulus.experiments.cifar10_benchmark --quick
"""

from __future__ import annotations

import os
import sys
import time
import numpy as np
import torch
import torch.nn as nn

from regulus.benchmark.datasets import load_dataset
from regulus.benchmark.metrics import compute_metrics
from regulus.benchmark.methods import TempScalingMethod, _compute_margin_uncertainty
from regulus.nn.interval_tensor import IntervalTensor
from regulus.nn.model import convert_model
from regulus.nn.architectures import make_cifar_cnn_bn, ResNetCIFAR
from regulus.nn.layers import IntervalBatchNorm
from regulus.analysis.traceable import TraceableAnalysis
from regulus.analysis.trace_visualization import (
    plot_trace_grid, plot_trace_heatmap,
)

OUTPUT_DIR = "benchmark_results/cifar10_benchmark"
TRACE_DIR = os.path.join(OUTPUT_DIR, "traces")
EPS_LIST = [0.01, 0.02, 0.05]


# ============================================================
# Training helper
# ============================================================

def train_model_2d(model, X_train, y_train, epochs, lr, batch_size,
                   input_shape=(3, 32, 32)):
    """Train CNN/ResNet with (N, C, H, W) input."""
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()
    C, H, W = input_shape
    X_t = torch.FloatTensor(X_train).reshape(-1, C, H, W)
    y_t = torch.LongTensor(y_train)
    n_batches = max(1, (len(X_t) + batch_size - 1) // batch_size)

    model.train()
    for epoch in range(epochs):
        perm = torch.randperm(len(X_t))
        total_loss = 0
        for b in range(n_batches):
            idx = perm[b * batch_size: (b + 1) * batch_size]
            optimizer.zero_grad()
            loss = criterion(model(X_t[idx]), y_t[idx])
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        if (epoch + 1) % max(1, epochs // 4) == 0:
            print(f"    Epoch {epoch+1}/{epochs}: loss={total_loss/n_batches:.4f}")

    model.eval()
    return model


# ============================================================
# MC Dropout CIFAR
# ============================================================

class MCDropoutCIFAR_CNN(nn.Module):
    """CIFAR CNN with Dropout for MC Dropout inference."""

    def __init__(self, dropout_p: float = 0.1) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.Dropout2d(dropout_p),
            nn.Conv2d(32, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.Dropout2d(dropout_p),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.Dropout2d(dropout_p),
            nn.Conv2d(64, 64, 3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.Dropout2d(dropout_p),
            nn.MaxPool2d(2),
            nn.Flatten(),
            nn.Linear(64 * 8 * 8, 256),
            nn.ReLU(),
            nn.Dropout(dropout_p),
            nn.Linear(256, 10),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def mc_dropout_predict(model, X_test, n_samples=50, input_shape=(3, 32, 32)):
    """MC Dropout predictions: run model N times with dropout active."""
    C, H, W = input_shape
    X_t = torch.FloatTensor(X_test).reshape(-1, C, H, W)

    model.train()  # keep dropout active
    outputs = []
    with torch.no_grad():
        for _ in range(n_samples):
            logits = model(X_t)
            probs = torch.softmax(logits, dim=-1)
            outputs.append(probs)

    outputs = torch.stack(outputs)  # (N_samples, batch, classes)
    mean_probs = outputs.mean(dim=0)
    std_probs = outputs.std(dim=0)

    preds = mean_probs.argmax(dim=-1).numpy()
    uncertainty = std_probs.max(dim=-1).values.numpy()
    return preds, uncertainty


# ============================================================
# Manual RA-Margin forward
# ============================================================

def _ra_margin_forward(imodel, x_interval, reanchor_eps=0.01):
    """Re-anchor after each ReLU/ResBlock (except final layer)."""
    from regulus.nn.layers import IntervalReLU
    from regulus.nn.architectures import IntervalResBlock

    current = x_interval
    n = len(imodel.layers)
    for i, layer in enumerate(imodel.layers):
        current = layer(current)
        is_activation = isinstance(layer, (IntervalReLU, IntervalResBlock))
        if is_activation and i < n - 1:
            mid = current.midpoint
            current = IntervalTensor.from_uncertainty(mid, reanchor_eps)
    return current


# ============================================================
# BN shrinkage analysis
# ============================================================

def analyze_bn_shrinkage(model, arch_name):
    """Compute avg |scale| for all BN layers in the model."""
    scales = []
    for name, m in model.named_modules():
        if isinstance(m, (nn.BatchNorm1d, nn.BatchNorm2d)):
            gamma = m.weight.detach().numpy()
            var = m.running_var.detach().numpy()
            eps = m.eps
            scale = np.abs(gamma) / np.sqrt(var + eps)
            avg_scale = float(np.mean(scale))
            scales.append((name, avg_scale, scale))
            print(f"    {name}: avg |scale| = {avg_scale:.4f} "
                  f"(min={scale.min():.4f}, max={scale.max():.4f})")
    if scales:
        all_scales = np.concatenate([s[2] for s in scales])
        print(f"    Overall avg |scale| = {np.mean(all_scales):.4f}")
        return float(np.mean(all_scales)), all_scales
    return None, None


# ============================================================
# Per-architecture runner
# ============================================================

def run_architecture(arch_name, model, imodel, X_test, y_test,
                     base_preds, mc_model, n_test, eps=0.02):
    """Run 5 methods on one CIFAR architecture."""
    results = []

    # --- 1. Naive IBP (width signal) ---
    print(f"  [1/5] Naive IBP (width)...")
    t0 = time.time()
    uncertainties = []
    for i in range(n_test):
        x = X_test[i]  # (3, 32, 32)
        x_int = IntervalTensor(x - eps, x + eps)
        out = imodel(x_int)
        uncertainties.append(out.max_width())
    unc = np.array(uncertainties)
    m = compute_metrics(base_preds, unc, y_test, "Naive IBP")
    elapsed = time.time() - t0
    results.append({**m, "arch": arch_name, "mean_width": float(unc.mean()),
                    "time": elapsed, "cost": 1, "eps": eps})
    print(f"    AUROC={m.get('auroc',0):.4f}, width={unc.mean():.2f} ({elapsed:.1f}s)")

    # --- 2. Naive IBP + Margin ---
    print(f"  [2/5] Naive IBP + Margin...")
    t0 = time.time()
    uncertainties = []
    for i in range(n_test):
        x = X_test[i]
        x_int = IntervalTensor(x - eps, x + eps)
        out = imodel(x_int)
        uncertainties.append(_compute_margin_uncertainty(out))
    unc = np.array(uncertainties)
    m = compute_metrics(base_preds, unc, y_test, "Naive IBP+Margin")
    elapsed = time.time() - t0
    results.append({**m, "arch": arch_name, "mean_width": float(unc.mean()),
                    "time": elapsed, "cost": 1, "eps": eps})
    print(f"    AUROC={m.get('auroc',0):.4f} ({elapsed:.1f}s)")

    # --- 3. RA-Margin (manual layer-level re-anchoring) ---
    print(f"  [3/5] RA-Margin...")
    t0 = time.time()
    uncertainties = []
    for i in range(n_test):
        x = X_test[i]
        x_int = IntervalTensor(x - eps, x + eps)
        out = _ra_margin_forward(imodel, x_int, reanchor_eps=0.01)
        uncertainties.append(_compute_margin_uncertainty(out))
    unc = np.array(uncertainties)
    m = compute_metrics(base_preds, unc, y_test, "RA-Margin")
    elapsed = time.time() - t0
    results.append({**m, "arch": arch_name, "mean_width": float(unc.mean()),
                    "time": elapsed, "cost": 1, "eps": eps})
    print(f"    AUROC={m.get('auroc',0):.4f} ({elapsed:.1f}s)")

    # --- 4. TempScaling ---
    print(f"  [4/5] TempScaling...")
    t0 = time.time()

    class FlatWrapper(nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m
        def forward(self, x):
            return self.m(x.reshape(-1, 3, 32, 32))

    ts = TempScalingMethod(FlatWrapper(model))
    # Flatten test data for TempScaling
    X_flat = X_test[:n_test].reshape(n_test, -1)
    T = ts.calibrate(X_flat[:min(1000, n_test)], y_test[:min(1000, n_test)])
    ts_preds, _, ts_unc = ts.predict_with_uncertainty(X_flat)
    m = compute_metrics(ts_preds, ts_unc, y_test, "TempScaling")
    elapsed = time.time() - t0
    results.append({**m, "arch": arch_name, "mean_width": float(ts_unc.mean()),
                    "time": elapsed, "cost": 1, "temperature": T, "eps": eps})
    print(f"    AUROC={m.get('auroc',0):.4f}, T={T:.4f} ({elapsed:.1f}s)")

    # --- 5. MC Dropout (N=50) ---
    print(f"  [5/5] MC Dropout (N=50)...")
    t0 = time.time()
    mc_preds, mc_unc = mc_dropout_predict(
        mc_model, X_test[:n_test], n_samples=50)
    m = compute_metrics(mc_preds, mc_unc, y_test, "MC Dropout (N=50)")
    elapsed = time.time() - t0
    results.append({**m, "arch": arch_name, "mean_width": float(mc_unc.mean()),
                    "time": elapsed, "cost": 50, "eps": eps})
    print(f"    AUROC={m.get('auroc',0):.4f} ({elapsed:.1f}s)")

    return results


# ============================================================
# Eps sweep (RA-Margin only)
# ============================================================

def run_eps_sweep(arch_name, model, imodel, X_test, y_test,
                  base_preds, n_test, eps_list):
    """Sweep RA-Margin AUROC over multiple epsilon values."""
    sweep_results = []
    for eps in eps_list:
        print(f"  RA-Margin @ eps={eps}...")
        uncertainties = []
        for i in range(n_test):
            x = X_test[i]
            x_int = IntervalTensor(x - eps, x + eps)
            out = _ra_margin_forward(imodel, x_int, reanchor_eps=0.01)
            uncertainties.append(_compute_margin_uncertainty(out))
        unc = np.array(uncertainties)
        m = compute_metrics(base_preds[:n_test], unc, y_test[:n_test],
                            f"RA-Margin(eps={eps})")
        sweep_results.append({
            "arch": arch_name, "eps": eps,
            "auroc": m.get("auroc", 0), "auprc": m.get("auprc", 0),
            "mean_width": float(unc.mean()),
        })
        print(f"    AUROC={m.get('auroc',0):.4f}")
    return sweep_results


# ============================================================
# Traceable analysis
# ============================================================

def run_traceable_analysis(imodel, X_test, y_test, preds,
                           eps=0.02, n_correct=10, n_incorrect=10):
    """Run traceable analysis on selected correct + incorrect samples."""
    tracer = TraceableAnalysis(reanchor_eps=0.01)

    correct_idx = np.where(preds == y_test)[0]
    incorrect_idx = np.where(preds != y_test)[0]

    # Sample at most n_correct/n_incorrect
    np.random.seed(42)
    if len(correct_idx) > n_correct:
        correct_idx = np.random.choice(correct_idx, n_correct, replace=False)
    if len(incorrect_idx) > n_incorrect:
        incorrect_idx = np.random.choice(incorrect_idx, n_incorrect, replace=False)

    all_reports = []
    labels = []  # 'correct' or 'incorrect'

    for idx in correct_idx:
        x = X_test[idx]
        x_int = IntervalTensor(x - eps, x + eps)
        report = tracer.trace(imodel, x_int)
        all_reports.append(report)
        labels.append("correct")

    for idx in incorrect_idx:
        x = X_test[idx]
        x_int = IntervalTensor(x - eps, x + eps)
        report = tracer.trace(imodel, x_int)
        all_reports.append(report)
        labels.append("incorrect")

    return all_reports, labels


# ============================================================
# Main benchmark
# ============================================================

def run_cifar10_benchmark(quick: bool = False):
    print("=" * 70)
    print("CIFAR-10 BENCHMARK + TRACEABLE UNCERTAINTY")
    print("=" * 70)

    # Load CIFAR-10
    ds = load_dataset("cifar10")
    X_train = ds["X_train"].astype(np.float32)
    X_test = ds["X_test"].astype(np.float32)
    y_train = ds["y_train"].astype(np.int64)
    y_test = ds["y_test"].astype(np.int64)
    dataset_name = ds["name"]

    print(f"Dataset: {dataset_name}")
    print(f"Train: {X_train.shape}, Test: {X_test.shape}")

    n_test = 500 if quick else 2000
    X_test = X_test[:n_test]
    y_test = y_test[:n_test]
    print(f"N_test = {n_test}")

    epochs_cnn = 5 if quick else 15
    epochs_res = 7 if quick else 20

    all_results = []
    all_sweep = []
    bn_analysis = {}

    # ----------------------------------------------------------------
    # Architecture 1: CNN+BN
    # ----------------------------------------------------------------
    print(f"\n{'='*60}")
    print("  Architecture 1: CIFAR CNN+BN")
    print(f"{'='*60}")

    torch.manual_seed(42)
    cnn = make_cifar_cnn_bn()
    cnn = train_model_2d(cnn, X_train, y_train,
                         epochs=epochs_cnn, lr=0.001, batch_size=128)

    cnn.eval()
    with torch.no_grad():
        preds_cnn = cnn(torch.FloatTensor(X_test).reshape(
            -1, 3, 32, 32)).argmax(dim=-1).numpy()
    acc_cnn = float((preds_cnn == y_test).mean())
    print(f"  Accuracy: {acc_cnn:.4f}")

    print("  BN shrinkage analysis:")
    bn_avg_cnn, bn_scales_cnn = analyze_bn_shrinkage(cnn, "CNN+BN")
    bn_analysis["CNN+BN"] = {"avg_scale": bn_avg_cnn, "scales": bn_scales_cnn}

    imodel_cnn = convert_model(cnn)

    # MC Dropout CNN
    torch.manual_seed(42)
    mc_cnn = MCDropoutCIFAR_CNN()
    mc_cnn = train_model_2d(mc_cnn, X_train, y_train,
                            epochs=epochs_cnn, lr=0.001, batch_size=128)

    results_cnn = run_architecture(
        "CNN+BN", cnn, imodel_cnn, X_test, y_test,
        preds_cnn, mc_model=mc_cnn, n_test=n_test, eps=0.02)
    all_results.extend(results_cnn)

    # Eps sweep
    print("  Eps sweep (RA-Margin):")
    sweep_cnn = run_eps_sweep("CNN+BN", cnn, imodel_cnn, X_test, y_test,
                              preds_cnn, n_test=min(n_test, 300), eps_list=EPS_LIST)
    all_sweep.extend(sweep_cnn)

    # ----------------------------------------------------------------
    # Architecture 2: ResNet+BN
    # ----------------------------------------------------------------
    print(f"\n{'='*60}")
    print("  Architecture 2: CIFAR ResNet+BN")
    print(f"{'='*60}")

    torch.manual_seed(42)
    resnet = ResNetCIFAR()
    resnet = train_model_2d(resnet, X_train, y_train,
                            epochs=epochs_res, lr=0.001, batch_size=128)

    resnet.eval()
    with torch.no_grad():
        preds_res = resnet(torch.FloatTensor(X_test).reshape(
            -1, 3, 32, 32)).argmax(dim=-1).numpy()
    acc_res = float((preds_res == y_test).mean())
    print(f"  Accuracy: {acc_res:.4f}")

    print("  BN shrinkage analysis:")
    bn_avg_res, bn_scales_res = analyze_bn_shrinkage(resnet, "ResNet+BN")
    bn_analysis["ResNet+BN"] = {"avg_scale": bn_avg_res, "scales": bn_scales_res}

    imodel_res = convert_model(resnet)

    # MC Dropout ResNet (reuse CNN dropout architecture)
    torch.manual_seed(42)
    mc_res = MCDropoutCIFAR_CNN()
    mc_res = train_model_2d(mc_res, X_train, y_train,
                            epochs=epochs_res, lr=0.001, batch_size=128)

    results_res = run_architecture(
        "ResNet+BN", resnet, imodel_res, X_test, y_test,
        preds_res, mc_model=mc_res, n_test=n_test, eps=0.02)
    all_results.extend(results_res)

    # Eps sweep
    print("  Eps sweep (RA-Margin):")
    sweep_res = run_eps_sweep("ResNet+BN", resnet, imodel_res, X_test, y_test,
                              preds_res, n_test=min(n_test, 300), eps_list=EPS_LIST)
    all_sweep.extend(sweep_res)

    # ----------------------------------------------------------------
    # Traceable analysis (on ResNet)
    # ----------------------------------------------------------------
    print(f"\n{'='*60}")
    print("  Traceable Uncertainty Analysis (ResNet+BN)")
    print(f"{'='*60}")

    n_trace_correct = 10 if not quick else 5
    n_trace_incorrect = 10 if not quick else 5
    trace_reports, trace_labels = run_traceable_analysis(
        imodel_res, X_test, y_test, preds_res,
        eps=0.02, n_correct=n_trace_correct, n_incorrect=n_trace_incorrect)

    _print_trace_summary(trace_reports, trace_labels)

    # ----------------------------------------------------------------
    # Output
    # ----------------------------------------------------------------
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(TRACE_DIR, exist_ok=True)

    _print_summary(all_results, acc_cnn, acc_res, bn_analysis, dataset_name)
    _save_csv(all_results, all_sweep)
    _generate_comparison_plot(all_results)
    _generate_eps_sweep_plot(all_sweep)
    _generate_trace_plots(trace_reports, trace_labels)

    # Save trace reports for paper figure generation
    import pickle
    trace_pkl = os.path.join(TRACE_DIR, "trace_reports.pkl")
    with open(trace_pkl, "wb") as f:
        pickle.dump({"reports": trace_reports, "labels": trace_labels}, f)
    print(f"Saved: {trace_pkl}")

    return all_results


# ============================================================
# Trace summary
# ============================================================

def _print_trace_summary(reports, labels):
    correct_reports = [r for r, l in zip(reports, labels) if l == "correct"]
    incorrect_reports = [r for r, l in zip(reports, labels) if l == "incorrect"]

    if correct_reports:
        reliable_correct = sum(1 for r in correct_reports if r.reliable)
        pct = 100.0 * reliable_correct / len(correct_reports)
        print(f"  Correct predictions:   {reliable_correct}/{len(correct_reports)}"
              f" ({pct:.0f}%) have all-block margin > threshold")

    if incorrect_reports:
        unreliable_incorrect = sum(1 for r in incorrect_reports if not r.reliable)
        pct = 100.0 * unreliable_incorrect / len(incorrect_reports)
        print(f"  Incorrect predictions: {unreliable_incorrect}/{len(incorrect_reports)}"
              f" ({pct:.0f}%) flagged as unreliable")

    # Critical block distribution
    all_reports = correct_reports + incorrect_reports
    if all_reports:
        n_blocks = all_reports[0].n_blocks
        block_counts = [0] * n_blocks
        for r in all_reports:
            if not r.reliable:
                block_counts[r.critical_block] += 1
        total_unreliable = sum(block_counts)
        if total_unreliable > 0:
            print("  Critical block distribution (unreliable only):")
            for i, cnt in enumerate(block_counts):
                pct = 100.0 * cnt / total_unreliable
                print(f"    Block {i}: {cnt} ({pct:.0f}%)")


# ============================================================
# Console output
# ============================================================

def _print_summary(results, acc_cnn, acc_res, bn_analysis, dataset_name):
    print("\n" + "=" * 70)
    print(f"CIFAR-10 BENCHMARK: RESULTS SUMMARY ({dataset_name})")
    print("=" * 70)

    print("\nSTANDARD ACCURACY:")
    print(f"  CNN+BN:     {acc_cnn:.4f}")
    print(f"  ResNet+BN:  {acc_res:.4f}")

    print("\nBATCHNORM ANALYSIS:")
    for name, info in bn_analysis.items():
        if info["avg_scale"] is not None:
            shrinks = "YES (shrinks)" if info["avg_scale"] < 1.0 else "NO"
            print(f"  {name}: avg |scale| = {info['avg_scale']:.4f} -> {shrinks}")

    for arch in ["CNN+BN", "ResNet+BN"]:
        arch_results = [r for r in results if r["arch"] == arch]
        if not arch_results:
            continue
        print(f"\n{arch}:")
        print(f"  {'Method':<25s} {'AUROC':>7s} {'AUPRC':>7s} "
              f"{'SelAcc90':>9s} {'Width':>10s} {'Cost':>5s}")
        print("  " + "-" * 65)
        for m in sorted(arch_results, key=lambda x: -x.get("auroc", 0)):
            auroc = m.get("auroc", float("nan"))
            auprc = m.get("auprc", float("nan"))
            sel10 = m.get("selective_acc@10%", float("nan"))
            width = m.get("mean_width", float("nan"))
            cost = m.get("cost", 1)
            a_s = f"{auroc:.4f}" if not np.isnan(auroc) else "  N/A"
            p_s = f"{auprc:.4f}" if not np.isnan(auprc) else "  N/A"
            s_s = f"{sel10:.4f}" if not np.isnan(sel10) else "    N/A"
            w_s = f"{width:.4f}" if not np.isnan(width) else "     N/A"
            print(f"  {m['method']:<25s} {a_s:>7s} {p_s:>7s} "
                  f"{s_s:>9s} {w_s:>10s} {cost:>4d}x")

    print("=" * 70)


# ============================================================
# CSV
# ============================================================

def _save_csv(results, sweep_results):
    import pandas as pd

    rows = [{k: v for k, v in r.items() if not isinstance(v, (list, dict))}
            for r in results]
    df = pd.DataFrame(rows)
    path = os.path.join(OUTPUT_DIR, "cifar10_results.csv")
    df.to_csv(path, index=False)
    print(f"\nSaved: {path}")

    if sweep_results:
        df_sweep = pd.DataFrame(sweep_results)
        path_sweep = os.path.join(OUTPUT_DIR, "eps_sweep.csv")
        df_sweep.to_csv(path_sweep, index=False)
        print(f"Saved: {path_sweep}")


# ============================================================
# Visualizations
# ============================================================

def _generate_comparison_plot(results):
    """Grouped bars: 2 architectures x 5 methods, AUROC."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    archs = ["CNN+BN", "ResNet+BN"]
    methods = ["Naive IBP", "Naive IBP+Margin", "RA-Margin",
               "TempScaling", "MC Dropout (N=50)"]
    method_colors = {
        "Naive IBP": "#999999",
        "Naive IBP+Margin": "#cccccc",
        "RA-Margin": "#d62728",
        "TempScaling": "#9467bd",
        "MC Dropout (N=50)": "#1f77b4",
    }

    fig, ax = plt.subplots(figsize=(8, 5))
    n_methods = len(methods)
    width = 0.14
    x = np.arange(len(archs))

    for i, method in enumerate(methods):
        aurocs = []
        for arch in archs:
            row = [r for r in results
                   if r["arch"] == arch and r["method"] == method]
            aurocs.append(row[0].get("auroc", 0) if row else 0)

        offset = (i - n_methods / 2 + 0.5) * width
        color = method_colors.get(method, "#888888")
        bars = ax.bar(x + offset, aurocs, width, label=method,
                      color=color, edgecolor="white", linewidth=0.5)
        for bar, val in zip(bars, aurocs):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.01,
                    f"{val:.2f}", ha="center", va="bottom", fontsize=7)

    ax.axhline(y=0.5, color="gray", linestyle="--", alpha=0.4)
    ax.set_xticks(x)
    ax.set_xticklabels(archs, fontsize=10)
    ax.set_ylabel("AUROC (Error Detection)", fontsize=10)
    ax.set_ylim(0.3, 1.08)
    ax.set_title("CIFAR-10: Architecture Comparison", fontsize=12)
    ax.legend(fontsize=7, loc="lower right")
    ax.grid(axis="y", alpha=0.15)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "cifar10_comparison.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")


def _generate_eps_sweep_plot(sweep_results):
    """Line chart: AUROC vs eps for each architecture."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not sweep_results:
        return

    fig, ax = plt.subplots(figsize=(6, 4))
    colors = {"CNN+BN": "#2ecc71", "ResNet+BN": "#e94560"}

    for arch in ["CNN+BN", "ResNet+BN"]:
        rows = [r for r in sweep_results if r["arch"] == arch]
        if not rows:
            continue
        rows.sort(key=lambda r: r["eps"])
        eps_vals = [r["eps"] for r in rows]
        auroc_vals = [r["auroc"] for r in rows]
        ax.plot(eps_vals, auroc_vals, "o-",
                label=arch, color=colors.get(arch, "#888888"),
                linewidth=2, markersize=6)

    ax.axhline(y=0.5, color="gray", linestyle="--", alpha=0.4)
    ax.set_xlabel("Input eps (normalized)", fontsize=10)
    ax.set_ylabel("AUROC (Error Detection)", fontsize=10)
    ax.set_title("RA-Margin: AUROC vs Epsilon", fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.15)
    ax.set_ylim(0.3, 1.05)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "eps_sweep.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")


def _generate_trace_plots(reports, labels):
    """Generate trace grid and heatmap."""
    if not reports:
        return

    # Grid: reliable vs unreliable
    grid_path = os.path.join(TRACE_DIR, "trace_grid.png")
    plot_trace_grid(reports, n_reliable=3, n_unreliable=3,
                    save_path=grid_path)
    print(f"Saved: {grid_path}")

    # Heatmap
    heatmap_path = os.path.join(TRACE_DIR, "trace_heatmap.png")
    plot_trace_heatmap(reports, save_path=heatmap_path,
                       title="Traceable Uncertainty: Per-Block Margins")
    print(f"Saved: {heatmap_path}")


# ============================================================
# CLI
# ============================================================

def main():
    quick = "--quick" in sys.argv
    run_cifar10_benchmark(quick=quick)


if __name__ == "__main__":
    main()
