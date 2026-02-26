"""
Architecture Benchmark: P4 Architectures vs Standard MLP.

Tests the hypothesis that BatchNorm acts as architectural re-anchoring
(shrinks intervals) and ResNet skip connections keep updates small.

3 architectures x 5 methods on MNIST:
  MLP:        784->256->128->64->10
  CNN+BN:     Conv->BN->ReLU->Pool x2 -> FC
  ResNet+BN:  Conv->BN->ReLU + 2 ResBlocks -> FC

Usage:
    .venv313\\Scripts\\python.exe -m regulus.experiments.architecture_benchmark
    .venv313\\Scripts\\python.exe -m regulus.experiments.architecture_benchmark --quick
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
from regulus.nn.architectures import make_mlp, make_cnn_bn, ResNetMNIST
from regulus.nn.layers import IntervalBatchNorm

OUTPUT_DIR = "benchmark_results/architecture_benchmark"
EPS = 0.02  # input perturbation


# ============================================================
# Training helpers
# ============================================================

def train_model_flat(model, X_train, y_train, epochs, lr, batch_size):
    """Train MLP with flat (N, 784) input."""
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()
    X_t = torch.FloatTensor(X_train)
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


def train_model_2d(model, X_train, y_train, epochs, lr, batch_size):
    """Train CNN/ResNet with (N, 1, 28, 28) input."""
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()
    X_t = torch.FloatTensor(X_train).reshape(-1, 1, 28, 28)
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
# MC Dropout CNN
# ============================================================

class MCDropoutCNN(nn.Module):
    """CNN with Dropout for MC Dropout inference."""

    def __init__(self, dropout_p: float = 0.1) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.Dropout2d(dropout_p),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.Dropout2d(dropout_p),
            nn.MaxPool2d(2),
            nn.Flatten(),
            nn.Linear(1568, 128),
            nn.ReLU(),
            nn.Dropout(dropout_p),
            nn.Linear(128, 10),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class MCDropoutMLP(nn.Module):
    """MLP with Dropout for MC Dropout inference."""

    def __init__(self, dropout_p: float = 0.1) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(784, 256), nn.ReLU(), nn.Dropout(dropout_p),
            nn.Linear(256, 128), nn.ReLU(), nn.Dropout(dropout_p),
            nn.Linear(128, 64), nn.ReLU(), nn.Dropout(dropout_p),
            nn.Linear(64, 10),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def mc_dropout_predict(model, X_test, n_samples=50, reshape_2d=False):
    """MC Dropout predictions: run model N times with dropout active."""
    if reshape_2d:
        X_t = torch.FloatTensor(X_test).reshape(-1, 1, 28, 28)
    else:
        X_t = torch.FloatTensor(X_test)

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
                     base_preds, reshape_2d, mc_model, n_test):
    """Run 5 methods on one architecture."""
    results = []

    # --- 1. Naive IBP (width signal) ---
    print(f"  [1/5] Naive IBP (width)...")
    t0 = time.time()
    uncertainties = []
    for i in range(n_test):
        if reshape_2d:
            x = X_test[i].reshape(1, 28, 28)
            x_int = IntervalTensor(x - EPS, x + EPS)
        else:
            x_int = IntervalTensor.from_uncertainty(X_test[i], EPS)
        out = imodel(x_int)
        uncertainties.append(out.max_width())
    unc = np.array(uncertainties)
    m = compute_metrics(base_preds, unc, y_test, "Naive IBP")
    elapsed = time.time() - t0
    results.append({**m, "arch": arch_name, "mean_width": float(unc.mean()),
                    "time": elapsed, "cost": 1})
    print(f"    AUROC={m.get('auroc',0):.4f}, width={unc.mean():.2f} ({elapsed:.1f}s)")

    # --- 2. Naive IBP + Margin ---
    print(f"  [2/5] Naive IBP + Margin...")
    t0 = time.time()
    uncertainties = []
    for i in range(n_test):
        if reshape_2d:
            x = X_test[i].reshape(1, 28, 28)
            x_int = IntervalTensor(x - EPS, x + EPS)
        else:
            x_int = IntervalTensor.from_uncertainty(X_test[i], EPS)
        out = imodel(x_int)
        uncertainties.append(_compute_margin_uncertainty(out))
    unc = np.array(uncertainties)
    m = compute_metrics(base_preds, unc, y_test, "Naive IBP+Margin")
    elapsed = time.time() - t0
    results.append({**m, "arch": arch_name, "mean_width": float(unc.mean()),
                    "time": elapsed, "cost": 1})
    print(f"    AUROC={m.get('auroc',0):.4f} ({elapsed:.1f}s)")

    # --- 3. RA-Margin (manual layer-level re-anchoring) ---
    print(f"  [3/5] RA-Margin...")
    t0 = time.time()
    uncertainties = []
    for i in range(n_test):
        if reshape_2d:
            x = X_test[i].reshape(1, 28, 28)
            x_int = IntervalTensor(x - EPS, x + EPS)
        else:
            x_int = IntervalTensor.from_uncertainty(X_test[i], EPS)
        out = _ra_margin_forward(imodel, x_int, reanchor_eps=0.01)
        uncertainties.append(_compute_margin_uncertainty(out))
    unc = np.array(uncertainties)
    m = compute_metrics(base_preds, unc, y_test, "RA-Margin")
    elapsed = time.time() - t0
    results.append({**m, "arch": arch_name, "mean_width": float(unc.mean()),
                    "time": elapsed, "cost": 1})
    print(f"    AUROC={m.get('auroc',0):.4f} ({elapsed:.1f}s)")

    # --- 4. TempScaling ---
    print(f"  [4/5] TempScaling...")
    t0 = time.time()
    ts = TempScalingMethod(model)
    if reshape_2d:
        # TempScaling needs flat logits; wrap the model
        class FlatWrapper(nn.Module):
            def __init__(self, m):
                super().__init__()
                self.m = m
            def forward(self, x):
                return self.m(x.reshape(-1, 1, 28, 28))
        ts = TempScalingMethod(FlatWrapper(model))
    T = ts.calibrate(X_test[:min(1000, n_test)], y_test[:min(1000, n_test)])
    ts_preds, _, ts_unc = ts.predict_with_uncertainty(X_test[:n_test])
    m = compute_metrics(ts_preds, ts_unc, y_test, "TempScaling")
    elapsed = time.time() - t0
    results.append({**m, "arch": arch_name, "mean_width": float(ts_unc.mean()),
                    "time": elapsed, "cost": 1, "temperature": T})
    print(f"    AUROC={m.get('auroc',0):.4f}, T={T:.4f} ({elapsed:.1f}s)")

    # --- 5. MC Dropout (N=50) ---
    print(f"  [5/5] MC Dropout (N=50)...")
    t0 = time.time()
    mc_preds, mc_unc = mc_dropout_predict(
        mc_model, X_test[:n_test], n_samples=50, reshape_2d=reshape_2d)
    m = compute_metrics(mc_preds, mc_unc, y_test, "MC Dropout (N=50)")
    elapsed = time.time() - t0
    results.append({**m, "arch": arch_name, "mean_width": float(mc_unc.mean()),
                    "time": elapsed, "cost": 50})
    print(f"    AUROC={m.get('auroc',0):.4f} ({elapsed:.1f}s)")

    return results


# ============================================================
# Main benchmark
# ============================================================

def run_architecture_benchmark(quick: bool = False):
    print("=" * 70)
    print("ARCHITECTURE BENCHMARK: P4 Architectures vs Standard MLP")
    print("Dataset: MNIST | Input eps = 0.02")
    print("=" * 70)

    # Load MNIST
    ds = load_dataset("mnist")
    X_train = ds["X_train"].astype(np.float32)
    X_test = ds["X_test"].astype(np.float32)
    y_train = ds["y_train"].astype(np.int64)
    y_test = ds["y_test"].astype(np.int64)

    n_test = 500 if quick else 2000
    X_test = X_test[:n_test]
    y_test = y_test[:n_test]
    print(f"N_test = {n_test}")

    all_results = []
    bn_analysis = {}

    # ----------------------------------------------------------------
    # Architecture 1: MLP
    # ----------------------------------------------------------------
    print(f"\n{'='*60}")
    print("  Architecture 1: MLP (784->256->128->64->10)")
    print(f"{'='*60}")

    torch.manual_seed(42)
    mlp = make_mlp()
    mlp = train_model_flat(mlp, X_train, y_train, epochs=20, lr=0.001, batch_size=256)

    mlp.eval()
    with torch.no_grad():
        preds_mlp = mlp(torch.FloatTensor(X_test)).argmax(dim=-1).numpy()
    acc_mlp = float((preds_mlp == y_test).mean())
    print(f"  Accuracy: {acc_mlp:.4f}")

    imodel_mlp = convert_model(mlp)

    # MC Dropout MLP
    torch.manual_seed(42)
    mc_mlp = MCDropoutMLP()
    mc_mlp = train_model_flat(mc_mlp, X_train, y_train, epochs=20, lr=0.001, batch_size=256)

    results_mlp = run_architecture(
        "MLP", mlp, imodel_mlp, X_test, y_test,
        preds_mlp, reshape_2d=False, mc_model=mc_mlp, n_test=n_test)
    all_results.extend(results_mlp)

    # ----------------------------------------------------------------
    # Architecture 2: CNN+BN
    # ----------------------------------------------------------------
    print(f"\n{'='*60}")
    print("  Architecture 2: CNN+BN")
    print(f"{'='*60}")

    torch.manual_seed(42)
    cnn = make_cnn_bn()
    cnn = train_model_2d(cnn, X_train, y_train, epochs=10, lr=0.001, batch_size=128)

    cnn.eval()
    with torch.no_grad():
        preds_cnn = cnn(torch.FloatTensor(X_test).reshape(-1, 1, 28, 28)).argmax(dim=-1).numpy()
    acc_cnn = float((preds_cnn == y_test).mean())
    print(f"  Accuracy: {acc_cnn:.4f}")

    print("  BN shrinkage analysis:")
    bn_avg_cnn, bn_scales_cnn = analyze_bn_shrinkage(cnn, "CNN+BN")
    bn_analysis["CNN+BN"] = {"avg_scale": bn_avg_cnn, "scales": bn_scales_cnn}

    imodel_cnn = convert_model(cnn)

    # MC Dropout CNN
    torch.manual_seed(42)
    mc_cnn = MCDropoutCNN()
    mc_cnn = train_model_2d(mc_cnn, X_train, y_train, epochs=10, lr=0.001, batch_size=128)

    results_cnn = run_architecture(
        "CNN+BN", cnn, imodel_cnn, X_test, y_test,
        preds_cnn, reshape_2d=True, mc_model=mc_cnn, n_test=n_test)
    all_results.extend(results_cnn)

    # ----------------------------------------------------------------
    # Architecture 3: ResNet+BN
    # ----------------------------------------------------------------
    print(f"\n{'='*60}")
    print("  Architecture 3: ResNet+BN")
    print(f"{'='*60}")

    torch.manual_seed(42)
    resnet = ResNetMNIST()
    resnet = train_model_2d(resnet, X_train, y_train, epochs=15, lr=0.001, batch_size=128)

    resnet.eval()
    with torch.no_grad():
        preds_res = resnet(torch.FloatTensor(X_test).reshape(-1, 1, 28, 28)).argmax(dim=-1).numpy()
    acc_res = float((preds_res == y_test).mean())
    print(f"  Accuracy: {acc_res:.4f}")

    print("  BN shrinkage analysis:")
    bn_avg_res, bn_scales_res = analyze_bn_shrinkage(resnet, "ResNet+BN")
    bn_analysis["ResNet+BN"] = {"avg_scale": bn_avg_res, "scales": bn_scales_res}

    imodel_res = convert_model(resnet)

    # MC Dropout for ResNet — reuse MCDropoutCNN (similar architecture)
    torch.manual_seed(42)
    mc_res = MCDropoutCNN()
    mc_res = train_model_2d(mc_res, X_train, y_train, epochs=15, lr=0.001, batch_size=128)

    results_res = run_architecture(
        "ResNet+BN", resnet, imodel_res, X_test, y_test,
        preds_res, reshape_2d=True, mc_model=mc_res, n_test=n_test)
    all_results.extend(results_res)

    # ----------------------------------------------------------------
    # Output
    # ----------------------------------------------------------------
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    _print_summary(all_results, acc_mlp, acc_cnn, acc_res, bn_analysis)
    _save_csv(all_results)
    _generate_comparison_plot(all_results)
    _generate_width_plot(all_results)
    _generate_bn_plot(bn_analysis)

    return all_results


# ============================================================
# Console output
# ============================================================

def _print_summary(results, acc_mlp, acc_cnn, acc_res, bn_analysis):
    print("\n" + "=" * 70)
    print("ARCHITECTURE BENCHMARK: RESULTS SUMMARY")
    print("=" * 70)

    print("\nSTANDARD ACCURACY:")
    print(f"  MLP:        {acc_mlp:.4f}")
    print(f"  CNN+BN:     {acc_cnn:.4f}")
    print(f"  ResNet+BN:  {acc_res:.4f}")

    print("\nBATCHNORM ANALYSIS:")
    for name, info in bn_analysis.items():
        if info["avg_scale"] is not None:
            shrinks = "YES (shrinks)" if info["avg_scale"] < 1.0 else "NO"
            print(f"  {name}: avg |scale| = {info['avg_scale']:.4f} -> {shrinks}")

    for arch in ["MLP", "CNN+BN", "ResNet+BN"]:
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

    # Key findings
    print("\n" + "=" * 70)
    print("KEY FINDINGS:")

    # Check if BN shrinks
    cnn_naive = [r for r in results if r["arch"] == "CNN+BN" and r["method"] == "Naive IBP"]
    mlp_naive = [r for r in results if r["arch"] == "MLP" and r["method"] == "Naive IBP"]
    if cnn_naive and mlp_naive:
        cnn_w = cnn_naive[0].get("mean_width", 0)
        mlp_w = mlp_naive[0].get("mean_width", 0)
        shrinks = "YES" if cnn_w < mlp_w else "NO"
        print(f"  BatchNorm shrinks intervals: {shrinks} "
              f"(CNN width={cnn_w:.2f} vs MLP width={mlp_w:.2f})")

    # Check ResNet competitive
    res_naive = [r for r in results if r["arch"] == "ResNet+BN" and r["method"] == "Naive IBP"]
    if res_naive:
        res_auroc = res_naive[0].get("auroc", 0)
        competitive = "YES" if res_auroc > 0.80 else "NO"
        print(f"  ResNet controls blowup: {competitive} "
              f"(Naive AUROC={res_auroc:.4f})")

    res_margin = [r for r in results if r["arch"] == "ResNet+BN" and r["method"] == "Naive IBP+Margin"]
    if res_margin:
        res_m_auroc = res_margin[0].get("auroc", 0)
        print(f"  Naive IBP+Margin on ResNet+BN: AUROC={res_m_auroc:.4f}")

    print("=" * 70)


# ============================================================
# CSV
# ============================================================

def _save_csv(results):
    import pandas as pd
    rows = [{k: v for k, v in r.items() if not isinstance(v, (list, dict))}
            for r in results]
    df = pd.DataFrame(rows)
    path = os.path.join(OUTPUT_DIR, "architecture_results.csv")
    df.to_csv(path, index=False)
    print(f"\nSaved: {path}")


# ============================================================
# Visualizations
# ============================================================

def _generate_comparison_plot(results):
    """Grouped bars: 3 architectures x 5 methods, AUROC."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    archs = ["MLP", "CNN+BN", "ResNet+BN"]
    methods = ["Naive IBP", "Naive IBP+Margin", "RA-Margin",
               "TempScaling", "MC Dropout (N=50)"]
    method_colors = {
        "Naive IBP": "#999999",
        "Naive IBP+Margin": "#cccccc",
        "RA-Margin": "#d62728",
        "TempScaling": "#9467bd",
        "MC Dropout (N=50)": "#1f77b4",
    }

    fig, ax = plt.subplots(figsize=(9, 5))
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
                    f"{val:.2f}", ha="center", va="bottom", fontsize=6)

    ax.axhline(y=0.5, color="gray", linestyle="--", alpha=0.4)
    ax.set_xticks(x)
    ax.set_xticklabels(archs, fontsize=10)
    ax.set_ylabel("AUROC (Error Detection)", fontsize=10)
    ax.set_ylim(0.3, 1.08)
    ax.set_title("Architecture Comparison: AUROC by Method", fontsize=12)
    ax.legend(fontsize=7, loc="lower right")
    ax.grid(axis="y", alpha=0.15)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "architecture_comparison.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")


def _generate_width_plot(results):
    """Bar chart: Naive IBP mean width per architecture."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    archs = ["MLP", "CNN+BN", "ResNet+BN"]
    widths = []
    for arch in archs:
        row = [r for r in results
               if r["arch"] == arch and r["method"] == "Naive IBP"]
        widths.append(row[0].get("mean_width", 0) if row else 0)

    fig, ax = plt.subplots(figsize=(6, 4))
    colors = ["#999999", "#2ecc71", "#e94560"]
    bars = ax.bar(archs, widths, color=colors, edgecolor="white")

    for bar, val in zip(bars, widths):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f"{val:.1f}", ha="center", va="bottom", fontsize=9)

    ax.set_ylabel("Mean Output Width (Naive IBP)", fontsize=10)
    ax.set_title("Interval Width by Architecture (Naive IBP, eps=0.02)",
                 fontsize=11)
    ax.set_yscale("log")
    ax.grid(axis="y", alpha=0.15)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "width_by_architecture.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")


def _generate_bn_plot(bn_analysis):
    """Scatter of |scale| values for each BN layer."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 4))

    colors = {"CNN+BN": "#2ecc71", "ResNet+BN": "#e94560"}
    for name, info in bn_analysis.items():
        if info["scales"] is not None:
            scales = info["scales"]
            ax.scatter(range(len(scales)), np.sort(scales)[::-1],
                       label=f"{name} (avg={info['avg_scale']:.3f})",
                       color=colors.get(name, "#888888"),
                       alpha=0.6, s=10)

    ax.axhline(y=1.0, color="black", linestyle="--", alpha=0.5,
               label="|scale|=1 (no shrinkage)")
    ax.set_xlabel("Channel index (sorted by scale)", fontsize=10)
    ax.set_ylabel("|scale| = |gamma| / sqrt(var + eps)", fontsize=10)
    ax.set_title("BatchNorm Shrinkage: Per-Channel |scale|", fontsize=11)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.15)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "bn_shrinkage.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")


# ============================================================
# CLI
# ============================================================

def main():
    quick = "--quick" in sys.argv
    run_architecture_benchmark(quick=quick)


if __name__ == "__main__":
    main()
