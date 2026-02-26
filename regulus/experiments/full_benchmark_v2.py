"""
Full Benchmark v2: Naive IBP vs Re-Anchored Margin vs Baselines.

Runs 8 methods across 3 datasets (Breast Cancer, Credit, MNIST).
Generates comparison tables, heatmaps, and per-dataset bar charts.

Usage:
    .venv313\\Scripts\\python.exe -m regulus.experiments.full_benchmark_v2
    .venv313\\Scripts\\python.exe -m regulus.experiments.full_benchmark_v2 --quick
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
from regulus.benchmark.methods import (
    RegulusMethod,
    ReanchoredRegulusMethod,
    NaiveIBPMarginMethod,
    MCDropoutMethod,
    DeepEnsembleMethod,
    TempScalingMethod,
)

OUTPUT_DIR = "benchmark_results/full_benchmark_v2"


# ============================================================
# Dataset configuration (overrides from spec)
# ============================================================

def _get_config(ds_name: str, n_features: int | None = None) -> dict:
    """Return per-dataset model architecture + training params from spec."""
    if ds_name == "breast_cancer":
        return {
            "model_fn": lambda: nn.Sequential(
                nn.Linear(30, 64), nn.ReLU(),
                nn.Linear(64, 32), nn.ReLU(),
                nn.Linear(32, 2),
            ),
            "epochs": 50, "lr": 0.001, "batch_size": 32, "input_eps": 0.01,
            "n_classes": 2, "n_layers": 3,
            "desc": "Breast Cancer (30 features, 2 classes, 3-layer MLP)",
        }
    elif ds_name == "credit":
        n = n_features or 20
        return {
            "model_fn": lambda: nn.Sequential(
                nn.Linear(n, 64), nn.ReLU(),
                nn.Linear(64, 32), nn.ReLU(),
                nn.Linear(32, 2),
            ),
            "epochs": 50, "lr": 0.001, "batch_size": 32, "input_eps": 0.01,
            "n_classes": 2, "n_layers": 3,
            "desc": f"German Credit ({n} features, 2 classes, 3-layer MLP)",
        }
    elif ds_name == "mnist":
        return {
            "model_fn": lambda: nn.Sequential(
                nn.Linear(784, 256), nn.ReLU(),
                nn.Linear(256, 128), nn.ReLU(),
                nn.Linear(128, 64), nn.ReLU(),
                nn.Linear(64, 10),
            ),
            "epochs": 20, "lr": 0.001, "batch_size": 256, "input_eps": 0.02,
            "n_classes": 10, "n_layers": 4,
            "desc": "MNIST (784 features, 10 classes, 4-layer MLP)",
        }
    else:
        raise ValueError(f"Unknown dataset: {ds_name}")


# ============================================================
# Training helper
# ============================================================

def train_model(model, X_train, y_train, epochs=50, lr=0.001, batch_size=32):
    """Train MLP with mini-batch Adam."""
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
            idx = perm[b * batch_size : (b + 1) * batch_size]
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
# Per-dataset runner
# ============================================================

def run_dataset(ds_name, X_train, y_train, X_test, y_test, config):
    """Run all 8 methods on one dataset, return list of result dicts."""
    results = []
    EPS = config["input_eps"]
    model_fn = config["model_fn"]

    # --- Train base model ---
    print(f"\n  Training base model...")
    torch.manual_seed(42)
    base_model = model_fn()
    base_model = train_model(
        base_model, X_train, y_train,
        epochs=config["epochs"], lr=config["lr"],
        batch_size=config["batch_size"],
    )

    base_model.eval()
    with torch.no_grad():
        logits = base_model(torch.FloatTensor(X_test))
        base_preds = logits.argmax(dim=-1).numpy()
        base_acc = (base_preds == y_test).mean()
    print(f"  Base accuracy: {base_acc:.4f}")

    def _add(m, name_override=None, extra=None):
        r = dict(m)
        r["dataset"] = ds_name
        if name_override:
            r["method"] = name_override
        if extra:
            r.update(extra)
        results.append(r)
        auroc = r.get("auroc", float("nan"))
        print(f"    {r['method']:<35s} AUROC={auroc:.4f}")

    # --- 1. Naive IBP (width) ---
    t0 = time.time()
    naive = RegulusMethod(base_model, input_eps=EPS)
    _, _, unc = naive.predict_with_uncertainty(X_test)
    m = compute_metrics(base_preds, unc, y_test, "Naive IBP")
    _add(m, extra={"cost": 1, "mean_width": float(unc.mean()),
                    "time": time.time() - t0})

    # --- 2. Naive IBP + Margin ---
    t0 = time.time()
    naive_m = NaiveIBPMarginMethod(base_model, input_eps=EPS)
    _, _, unc = naive_m.predict_with_uncertainty(X_test)
    m = compute_metrics(base_preds, unc, y_test, "Naive IBP+Margin")
    _add(m, extra={"cost": 1, "mean_width": float(unc.mean()),
                    "time": time.time() - t0})

    # --- 3. RA-Midpoint (width) ---
    t0 = time.time()
    ra_w = ReanchoredRegulusMethod(
        base_model, input_eps=EPS, block_size=1,
        reanchor_eps=0.01, strategy="midpoint", signal="width")
    _, _, unc = ra_w.predict_with_uncertainty(X_test)
    m = compute_metrics(base_preds, unc, y_test, "RA-Mid (width)")
    _add(m, extra={"cost": 1, "mean_width": float(unc.mean()),
                    "time": time.time() - t0})

    # --- 4. RA-Midpoint + Margin (KEY METHOD) ---
    t0 = time.time()
    ra_m = ReanchoredRegulusMethod(
        base_model, input_eps=EPS, block_size=1,
        reanchor_eps=0.01, strategy="midpoint", signal="margin")
    _, _, unc = ra_m.predict_with_uncertainty(X_test)
    m = compute_metrics(base_preds, unc, y_test, "RA-Margin (bs=1)")
    _add(m, extra={"cost": 1, "mean_width": float(unc.mean()),
                    "time": time.time() - t0})

    # --- 5. RA-Adaptive + Margin ---
    t0 = time.time()
    ra_am = ReanchoredRegulusMethod(
        base_model, input_eps=EPS, block_size=1,
        reanchor_eps=0.01, strategy="adaptive",
        adaptive_threshold=1.0, signal="margin")
    _, _, unc = ra_am.predict_with_uncertainty(X_test)
    m = compute_metrics(base_preds, unc, y_test, "RA-Adaptive+Margin")
    _add(m, extra={"cost": 1, "mean_width": float(unc.mean()),
                    "time": time.time() - t0})

    # --- 6. MC Dropout (N=50) ---
    t0 = time.time()
    mc = MCDropoutMethod(None, n_samples=50)
    mc.train_model(model_fn, X_train, y_train,
                   epochs=config["epochs"], lr=config["lr"])
    mc_preds, _, mc_unc = mc.predict_with_uncertainty(X_test)
    m = compute_metrics(mc_preds, mc_unc, y_test, "MC Dropout (N=50)")
    _add(m, extra={"cost": 50, "mean_width": float(mc_unc.mean()),
                    "time": time.time() - t0})

    # --- 7. Deep Ensemble (K=5) ---
    t0 = time.time()
    ens = DeepEnsembleMethod(None, n_models=5)
    ens.train_model(model_fn, X_train, y_train,
                    epochs=config["epochs"], lr=config["lr"])
    ens_preds, _, ens_unc = ens.predict_with_uncertainty(X_test)
    m = compute_metrics(ens_preds, ens_unc, y_test, "Deep Ensemble (K=5)")
    _add(m, extra={"cost": 5, "mean_width": float(ens_unc.mean()),
                    "time": time.time() - t0})

    # --- 8. Temperature Scaling ---
    t0 = time.time()
    ts = TempScalingMethod(base_model)
    T = ts.calibrate(X_train[:5000], y_train[:5000])
    ts_preds, _, ts_unc = ts.predict_with_uncertainty(X_test)
    m = compute_metrics(ts_preds, ts_unc, y_test, "TempScaling")
    _add(m, extra={"cost": 1, "mean_width": float(ts_unc.mean()),
                    "time": time.time() - t0, "temperature": T})

    return results


# ============================================================
# Main benchmark
# ============================================================

def run_full_benchmark(quick: bool = False):
    print("=" * 70)
    print("FULL BENCHMARK v2: Naive IBP vs Re-Anchored Margin vs Baselines")
    print("=" * 70)

    all_results = []

    for ds_name in ["breast_cancer", "credit", "mnist"]:
        # Load data
        ds = load_dataset(ds_name)
        X_train = ds["X_train"].astype(np.float32)
        X_test = ds["X_test"].astype(np.float32)
        y_train = ds["y_train"].astype(np.int64)
        y_test = ds["y_test"].astype(np.int64)

        # Limit MNIST test samples
        if ds_name == "mnist":
            n_test = 2000 if quick else 5000
            X_test = X_test[:n_test]
            y_test = y_test[:n_test]

        n_features = X_train.shape[1]
        config = _get_config(ds_name, n_features=n_features)

        print(f"\n{'='*60}")
        print(f"  {config['desc']}")
        print(f"  Train: {X_train.shape}, Test: {X_test.shape}")
        print(f"  Input eps: {config['input_eps']}")
        print(f"{'='*60}")

        results = run_dataset(
            ds_name, X_train, y_train, X_test, y_test, config)
        all_results.extend(results)

    # Output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    _print_console_summary(all_results)
    _save_csv(all_results)
    _generate_heatmap(all_results)
    _generate_per_dataset_bars(all_results)
    _generate_applicability_map(all_results)

    return all_results


# ============================================================
# Console output
# ============================================================

def _print_console_summary(results):
    print("\n" + "=" * 80)
    print("FULL BENCHMARK v2: RESULTS SUMMARY")
    print("=" * 80)

    for ds_name in ["breast_cancer", "credit", "mnist"]:
        ds_results = [r for r in results if r["dataset"] == ds_name]
        if not ds_results:
            continue

        print(f"\n{ds_name.upper().replace('_', ' ')}:")
        print(f"  {'Method':<35s} {'AUROC':>7s} {'AUPRC':>7s} {'SelAcc90':>9s} "
              f"{'MeanW':>10s} {'Cost':>5s}")
        print("  " + "-" * 75)

        for m in sorted(ds_results, key=lambda x: -x.get("auroc", 0)):
            auroc = m.get("auroc", float("nan"))
            auprc = m.get("auprc", float("nan"))
            sel10 = m.get("selective_acc@10%", float("nan"))
            mean_w = m.get("mean_width", float("nan"))
            cost = m.get("cost", 1)
            auroc_s = f"{auroc:.4f}" if not np.isnan(auroc) else "  N/A"
            auprc_s = f"{auprc:.4f}" if not np.isnan(auprc) else "  N/A"
            sel_s = f"{sel10:.4f}" if not np.isnan(sel10) else "    N/A"
            w_s = f"{mean_w:.4f}" if not np.isnan(mean_w) else "     N/A"
            print(f"  {m['method']:<35s} {auroc_s:>7s} {auprc_s:>7s} "
                  f"{sel_s:>9s} {w_s:>10s} {cost:>4d}x")

    print("\n" + "=" * 80)


# ============================================================
# CSV output
# ============================================================

def _save_csv(results):
    import pandas as pd

    rows = []
    for r in results:
        row = {k: v for k, v in r.items() if not isinstance(v, (list, dict))}
        rows.append(row)

    df = pd.DataFrame(rows)
    path = os.path.join(OUTPUT_DIR, "comparison_table.csv")
    df.to_csv(path, index=False)
    print(f"\nSaved: {path}")


# ============================================================
# Heatmap: AUROC matrix (methods x datasets)
# ============================================================

def _generate_heatmap(results):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    datasets = ["breast_cancer", "credit", "mnist"]
    methods = []
    for r in results:
        if r["method"] not in methods:
            methods.append(r["method"])

    matrix = np.full((len(methods), len(datasets)), np.nan)
    for r in results:
        i = methods.index(r["method"])
        j = datasets.index(r["dataset"])
        matrix[i, j] = r.get("auroc", np.nan)

    fig, ax = plt.subplots(1, 1, figsize=(8, 6))
    im = ax.imshow(matrix, cmap="RdYlGn", aspect="auto",
                   vmin=0.4, vmax=1.0)

    ax.set_xticks(range(len(datasets)))
    ax.set_xticklabels([d.replace("_", "\n") for d in datasets], fontsize=9)
    ax.set_yticks(range(len(methods)))
    ax.set_yticklabels(methods, fontsize=8)

    # Annotate cells
    for i in range(len(methods)):
        for j in range(len(datasets)):
            val = matrix[i, j]
            if not np.isnan(val):
                color = "white" if val < 0.6 else "black"
                ax.text(j, i, f"{val:.3f}", ha="center", va="center",
                        fontsize=8, color=color, fontweight="bold")

    plt.colorbar(im, ax=ax, label="AUROC", shrink=0.8)
    ax.set_title("AUROC: Methods x Datasets", fontsize=12, fontweight="bold")
    plt.tight_layout()

    path = os.path.join(OUTPUT_DIR, "comparison_heatmap.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")


# ============================================================
# Per-dataset bar charts
# ============================================================

def _generate_per_dataset_bars(results):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    datasets = ["breast_cancer", "credit", "mnist"]
    ds_labels = ["Breast Cancer", "German Credit", "MNIST"]

    def _color(name):
        if "RA-Margin" in name or "RA-Adaptive" in name:
            return "#2ecc71"
        if "RA-Mid" in name:
            return "#e94560"
        if "Naive" in name and "Margin" in name:
            return "#95a5a6"
        if "Naive" in name:
            return "#cccccc"
        if "MC" in name:
            return "#4a90d9"
        if "Ensemble" in name:
            return "#50c878"
        if "Temp" in name:
            return "#f5a623"
        return "#888888"

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle("AUROC by Method across Datasets",
                 fontsize=13, fontweight="bold")

    for idx, (ds, ds_label) in enumerate(zip(datasets, ds_labels)):
        ax = axes[idx]
        ds_results = [r for r in results if r["dataset"] == ds]
        ds_results = sorted(ds_results, key=lambda x: x.get("auroc", 0))

        names = [r["method"][:30] for r in ds_results]
        aurocs = [r.get("auroc", 0) for r in ds_results]
        colors = [_color(r["method"]) for r in ds_results]

        bars = ax.barh(range(len(names)), aurocs, color=colors, alpha=0.85)
        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names, fontsize=7)
        ax.set_xlabel("AUROC", fontsize=9)
        ax.set_title(ds_label, fontsize=10, fontweight="bold")
        ax.set_xlim(0.3, 1.05)
        ax.axvline(x=0.5, color="red", linestyle="--", alpha=0.3)

        # Annotate bars
        for bar, val in zip(bars, aurocs):
            ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height()/2,
                    f"{val:.3f}", va="center", fontsize=7)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "per_dataset_bars.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")


# ============================================================
# Applicability map: scatter x=depth, y=input_dim, size=AUROC
# ============================================================

def _generate_applicability_map(results):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ds_info = {
        "breast_cancer": {"input_dim": 30, "depth": 3},
        "credit":        {"input_dim": 20, "depth": 3},
        "mnist":         {"input_dim": 784, "depth": 4},
    }

    method_colors = {
        "Naive IBP": "#cccccc",
        "Naive IBP+Margin": "#95a5a6",
        "RA-Mid (width)": "#e94560",
        "RA-Margin (bs=1)": "#2ecc71",
        "RA-Adaptive+Margin": "#27ae60",
        "MC Dropout (N=50)": "#4a90d9",
        "Deep Ensemble (K=5)": "#50c878",
    }

    fig, ax = plt.subplots(1, 1, figsize=(10, 7))

    # Jitter for visibility
    np.random.seed(42)

    for r in results:
        ds = r["dataset"]
        info = ds_info.get(ds, {"input_dim": 0, "depth": 0})
        base_name = r["method"]
        # Normalize method name for color
        color = "#888888"
        for key, c in method_colors.items():
            if key in base_name:
                color = c
                break
        if "Temp" in base_name:
            color = "#f5a623"

        auroc = r.get("auroc", 0.5)
        x = info["depth"] + np.random.uniform(-0.15, 0.15)
        y = info["input_dim"] * (1 + np.random.uniform(-0.03, 0.03))
        size = max(20, auroc * 200)

        ax.scatter(x, y, s=size, c=color, alpha=0.7,
                   edgecolors="black", linewidth=0.3)

    # Legend
    for label, color in method_colors.items():
        ax.scatter([], [], c=color, s=60, label=label,
                   edgecolors="black", linewidth=0.3)
    ax.scatter([], [], c="#f5a623", s=60, label="TempScaling",
               edgecolors="black", linewidth=0.3)

    ax.set_xlabel("Model Depth (# Linear layers)", fontsize=10)
    ax.set_ylabel("Input Dimensionality", fontsize=10)
    ax.set_title("Applicability Map: Size = AUROC", fontsize=12, fontweight="bold")
    ax.set_yscale("log")
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(alpha=0.3)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "applicability_map.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")


# ============================================================
# CLI
# ============================================================

def main():
    quick = "--quick" in sys.argv
    run_full_benchmark(quick=quick)


if __name__ == "__main__":
    main()
