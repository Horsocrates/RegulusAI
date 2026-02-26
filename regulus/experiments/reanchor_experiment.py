"""
P4 Hypothesis Test: Process-Based Interval Propagation.

Compares re-anchored IBP strategies against naive IBP and standard baselines
on MNIST (4-layer MLP, 784->256->128->64->10).

Sweep: block_size x reanchor_eps x strategy
Baselines: Naive IBP, MC Dropout (50), Deep Ensemble (5), Temp Scaling

Usage:
    python -m regulus.experiments.reanchor_experiment
    python -m regulus.experiments.reanchor_experiment --quick
"""

from __future__ import annotations

import os
import sys
import time
import numpy as np
import torch
import torch.nn as nn

from regulus.nn.interval_tensor import IntervalTensor
from regulus.nn.model import convert_model
from regulus.nn.reanchor import ReanchoredIntervalModel
from regulus.benchmark.metrics import compute_metrics
from regulus.benchmark.methods import (
    RegulusMethod,
    ReanchoredRegulusMethod,
    MCDropoutMethod,
    DeepEnsembleMethod,
    TempScalingMethod,
)


# ============================================================
# MNIST loading (sklearn fallback)
# ============================================================

def load_mnist():
    """Load MNIST with torchvision->sklearn fallback."""
    try:
        from torchvision import datasets, transforms

        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Lambda(lambda x: x.view(-1).numpy()),
        ])
        train_data = datasets.MNIST("./data", train=True, download=True, transform=transform)
        test_data = datasets.MNIST("./data", train=False, transform=transform)

        X_train = np.stack([train_data[i][0] for i in range(len(train_data))])
        y_train = np.array([train_data[i][1] for i in range(len(train_data))])
        X_test = np.stack([test_data[i][0] for i in range(len(test_data))])
        y_test = np.array([test_data[i][1] for i in range(len(test_data))])
    except (RuntimeError, OSError):
        print("  torchvision download failed, using sklearn...")
        from sklearn.datasets import fetch_openml

        mnist = fetch_openml("mnist_784", version=1, as_frame=False)
        X_all = mnist.data.astype(np.float32) / 255.0
        y_all = mnist.target.astype(int)
        X_train, X_test = X_all[:60000], X_all[60000:]
        y_train, y_test = y_all[:60000], y_all[60000:]

    return X_train, y_train, X_test, y_test


def train_model(X_train, y_train, model, epochs=20, lr=0.001, batch_size=512):
    """Train MLP with mini-batch SGD."""
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    X_t = torch.FloatTensor(X_train)
    y_t = torch.LongTensor(y_train)
    n_batches = (len(X_t) + batch_size - 1) // batch_size

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
        if (epoch + 1) % 5 == 0:
            print(f"  Epoch {epoch+1}/{epochs}: loss={total_loss/n_batches:.4f}")

    model.eval()
    return model


def model_factory():
    """Create fresh MNIST MLP."""
    return nn.Sequential(
        nn.Linear(784, 256), nn.ReLU(),
        nn.Linear(256, 128), nn.ReLU(),
        nn.Linear(128, 64), nn.ReLU(),
        nn.Linear(64, 10),
    )


# ============================================================
# Main experiment
# ============================================================

def run_reanchor_experiment(quick: bool = False):
    n_test = 2000 if quick else 5000
    INPUT_EPS = 0.02

    print("=" * 70)
    print("P4 HYPOTHESIS: PROCESS-BASED INTERVAL PROPAGATION")
    print("Dataset: MNIST | Model: MLP (784->256->128->64->10)")
    print(f"Input eps: {INPUT_EPS} | Test samples: {n_test}")
    print("=" * 70)

    # ---- Load data ----
    print("\nLoading MNIST...")
    X_train, y_train, X_test, y_test = load_mnist()
    X_test = X_test[:n_test].astype(np.float32)
    y_test = y_test[:n_test]
    print(f"  Train: {X_train.shape}, Test subset: {X_test.shape}")

    # ---- Train base model ----
    print("\nTraining base model...")
    torch.manual_seed(42)
    base_model = model_factory()
    base_model = train_model(X_train, y_train, base_model, epochs=20)

    base_model.eval()
    with torch.no_grad():
        test_logits = base_model(torch.FloatTensor(X_test))
        base_preds = test_logits.argmax(dim=-1).numpy()
        base_acc = (base_preds == y_test).mean()
    print(f"  Base model test accuracy: {base_acc:.4f}")

    # ---- Sweep configurations ----
    all_results = []

    # --- 1. Naive IBP baseline ---
    print("\n--- Naive IBP ---")
    t0 = time.time()
    naive = RegulusMethod(base_model, input_eps=INPUT_EPS)
    _, _, naive_unc = naive.predict_with_uncertainty(X_test)
    t_naive = time.time() - t0
    m = compute_metrics(base_preds, naive_unc, y_test, "Naive IBP")
    m.update({
        "type": "baseline",
        "mean_width": float(naive_unc.mean()),
        "max_width": float(naive_unc.max()),
        "n_reanchors": 0,
        "cost": 1,
        "time": t_naive,
    })
    all_results.append(m)
    print(f"  AUROC: {m['auroc']:.4f} | Width: {naive_unc.mean():.2f} | Time: {t_naive:.2f}s")

    # --- 2. Re-anchored sweep (midpoint + adaptive, trimmed) ---
    block_sizes = [1, 3]
    reanchor_epsilons = [0.0001, 0.001]
    strategies = ["midpoint", "adaptive"]

    for strategy in strategies:
        for bs in block_sizes:
            for re_eps in reanchor_epsilons:
                name = f"Reanchor({strategy[:3]},bs={bs},re={re_eps})"
                print(f"\n--- {name} ---")

                t0 = time.time()
                method = ReanchoredRegulusMethod(
                    base_model,
                    input_eps=INPUT_EPS,
                    block_size=bs,
                    reanchor_eps=re_eps,
                    strategy=strategy,
                    adaptive_threshold=1.0,
                )
                preds, _, unc = method.predict_with_uncertainty(X_test)
                t_ra = time.time() - t0

                m = compute_metrics(preds, unc, y_test, name)
                m.update({
                    "type": strategy,
                    "block_size": bs,
                    "reanchor_eps": re_eps,
                    "mean_width": float(unc.mean()),
                    "max_width": float(unc.max()),
                    "n_reanchors": method.reanchor_model.n_reanchors,
                    "cost": 1,
                    "time": t_ra,
                })
                all_results.append(m)
                print(
                    f"  AUROC: {m['auroc']:.4f} | "
                    f"Width: {unc.mean():.4f} | "
                    f"Reanchors: {method.reanchor_model.n_reanchors} | "
                    f"Time: {t_ra:.2f}s"
                )

    # --- 2b. Proportional re-anchoring (top configs from prior sweep) ---
    prop_configs = [
        (1, 0.01, 1e-4),   # best: 0.6622
        (1, 0.005, 5e-5),  # second: 0.6331
        (1, 0.01, 2e-4),   # third: 0.6011
        (1, 0.02, 5e-5),
        (1, 0.005, 1e-4),
    ]

    for bs, sf, me in prop_configs:
        name = f"Reanchor(prop,bs={bs},sf={sf},me={me})"
        print(f"\n--- {name} ---")

        t0 = time.time()
        method = ReanchoredRegulusMethod(
            base_model,
            input_eps=INPUT_EPS,
            block_size=bs,
            reanchor_eps=me,
            strategy="proportional",
            shrink_factor=sf,
        )
        preds, _, unc = method.predict_with_uncertainty(X_test)
        t_ra = time.time() - t0

        m = compute_metrics(preds, unc, y_test, name)
        m.update({
            "type": "proportional",
            "block_size": bs,
            "reanchor_eps": me,
            "shrink_factor": sf,
            "mean_width": float(unc.mean()),
            "max_width": float(unc.max()),
            "n_reanchors": method.reanchor_model.n_reanchors,
            "cost": 1,
            "time": t_ra,
        })
        all_results.append(m)
        print(
            f"  AUROC: {m['auroc']:.4f} | "
            f"Width: {unc.mean():.4f} | "
            f"Reanchors: {method.reanchor_model.n_reanchors} | "
            f"Time: {t_ra:.2f}s"
        )

    # --- 2c. Margin-based uncertainty signal ---
    # Instead of max_width, use interval margin: how separable are the top-2
    # classes in interval midpoint space relative to width.
    # Higher margin = more certain -> uncertainty = 1/(1 + margin)
    print("\n--- Margin-based uncertainty signal ---")

    margin_configs = [
        # (strategy, bs, reanchor_eps, shrink_factor, label)
        ("midpoint", 1, 1e-4, 0.1, "mid"),
        ("midpoint", 1, 1e-3, 0.1, "mid"),
        ("midpoint", 3, 1e-4, 0.1, "mid"),
        ("proportional", 1, 1e-4, 0.01, "prop"),
        ("proportional", 1, 5e-5, 0.005, "prop"),
    ]

    for strategy, bs, re_eps, sf, label in margin_configs:
        name = f"RA-Margin({label},bs={bs},re={re_eps})"
        print(f"\n--- {name} ---")

        t0 = time.time()
        ra_model = ReanchoredIntervalModel(
            base_model,
            block_size=bs,
            reanchor_eps=re_eps,
            strategy=strategy,
            shrink_factor=sf,
        )

        margin_uncs = []
        for i in range(len(X_test)):
            x_interval = IntervalTensor.from_uncertainty(X_test[i], INPUT_EPS)
            output = ra_model(x_interval)

            # Margin: gap between top-2 midpoints / mean_width
            mids = output.midpoint
            sorted_mids = np.sort(mids)[::-1]  # descending
            gap = sorted_mids[0] - sorted_mids[1]
            w = output.mean_width() + 1e-12
            margin = gap / w
            margin_uncs.append(1.0 / (1.0 + margin))

        margin_unc = np.array(margin_uncs)
        t_margin = time.time() - t0

        m = compute_metrics(base_preds, margin_unc, y_test, name)
        m.update({
            "type": "margin",
            "block_size": bs,
            "reanchor_eps": re_eps,
            "mean_width": float(margin_unc.mean()),
            "max_width": float(margin_unc.max()),
            "n_reanchors": ra_model.n_reanchors,
            "cost": 1,
            "time": t_margin,
        })
        all_results.append(m)
        print(f"  AUROC: {m['auroc']:.4f} | Time: {t_margin:.2f}s")

    # --- 2d. Also try naive IBP margin for comparison ---
    print("\n--- Naive IBP Margin ---")
    t0 = time.time()
    naive_model = convert_model(base_model)
    naive_margin_uncs = []
    for i in range(len(X_test)):
        x_interval = IntervalTensor.from_uncertainty(X_test[i], INPUT_EPS)
        output = naive_model(x_interval)
        mids = output.midpoint
        sorted_mids = np.sort(mids)[::-1]
        gap = sorted_mids[0] - sorted_mids[1]
        w = output.mean_width() + 1e-12
        margin = gap / w
        naive_margin_uncs.append(1.0 / (1.0 + margin))
    naive_margin_unc = np.array(naive_margin_uncs)
    t_nm = time.time() - t0
    m = compute_metrics(base_preds, naive_margin_unc, y_test, "Naive IBP Margin")
    m.update({
        "type": "baseline",
        "mean_width": float(naive_margin_unc.mean()),
        "max_width": float(naive_margin_unc.max()),
        "n_reanchors": 0,
        "cost": 1,
        "time": t_nm,
    })
    all_results.append(m)
    print(f"  AUROC: {m['auroc']:.4f} | Time: {t_nm:.2f}s")

    # (Width-spread signal removed — margin dominates)

    # --- 3. MC Dropout baseline ---
    print("\n--- MC Dropout (50 samples) ---")
    t0 = time.time()
    mc = MCDropoutMethod(None, n_samples=50)
    mc.train_model(model_factory, X_train, y_train, epochs=20, lr=0.001)
    mc_preds, _, mc_unc = mc.predict_with_uncertainty(X_test)
    t_mc = time.time() - t0
    m = compute_metrics(mc_preds, mc_unc, y_test, "MC Dropout (N=50)")
    m.update({"type": "baseline", "mean_width": float(mc_unc.mean()),
              "max_width": float(mc_unc.max()), "n_reanchors": 0,
              "cost": 50, "time": t_mc})
    all_results.append(m)
    print(f"  AUROC: {m['auroc']:.4f} | Time: {t_mc:.2f}s")

    # --- 4. Deep Ensemble baseline ---
    print("\n--- Deep Ensemble (K=5) ---")
    t0 = time.time()
    ens = DeepEnsembleMethod(None, n_models=5)
    ens.train_model(model_factory, X_train, y_train, epochs=20, lr=0.001)
    ens_preds, _, ens_unc = ens.predict_with_uncertainty(X_test)
    t_ens = time.time() - t0
    m = compute_metrics(ens_preds, ens_unc, y_test, "Ensemble (K=5)")
    m.update({"type": "baseline", "mean_width": float(ens_unc.mean()),
              "max_width": float(ens_unc.max()), "n_reanchors": 0,
              "cost": 5, "time": t_ens})
    all_results.append(m)
    print(f"  AUROC: {m['auroc']:.4f} | Time: {t_ens:.2f}s")

    # --- 5. Temp Scaling baseline ---
    print("\n--- Temp Scaling ---")
    t0 = time.time()
    ts = TempScalingMethod(base_model)
    T = ts.calibrate(X_train[:5000], y_train[:5000])
    ts_preds, _, ts_unc = ts.predict_with_uncertainty(X_test)
    t_ts = time.time() - t0
    m = compute_metrics(ts_preds, ts_unc, y_test, f"TempScaling (T={T:.2f})")
    m.update({"type": "baseline", "mean_width": float(ts_unc.mean()),
              "max_width": float(ts_unc.max()), "n_reanchors": 0,
              "cost": 1, "time": t_ts})
    all_results.append(m)
    print(f"  AUROC: {m['auroc']:.4f} | T={T:.3f} | Time: {t_ts:.2f}s")

    # ---- Summary ----
    _print_summary(all_results)
    _save_csv(all_results)
    _generate_plot(all_results)

    return all_results


# ============================================================
# Output
# ============================================================

def _print_summary(results):
    print("\n" + "=" * 90)
    print("P4 HYPOTHESIS RESULTS -- SORTED BY AUROC")
    print("=" * 90)
    print(f"{'Method':<42} {'AUROC':>7} {'MeanW':>10} {'MaxW':>10} {'SelAcc10':>9} {'Cost':>5}")
    print("-" * 90)

    for m in sorted(results, key=lambda x: -x.get("auroc", 0)):
        auroc = m.get("auroc", float("nan"))
        mean_w = m.get("mean_width", float("nan"))
        max_w = m.get("max_width", float("nan"))
        sel10 = m.get("selective_acc@10%", float("nan"))
        cost = m.get("cost", 1)
        marker = "*" if ("Reanchor" in m["method"] or "RA-Margin" in m["method"]) else " "
        auroc_s = f"{auroc:.4f}" if not np.isnan(auroc) else "  N/A"
        sel_s = f"{sel10:.4f}" if not np.isnan(sel10) else "  N/A"
        print(
            f"{marker} {m['method']:<40} {auroc_s:>7} "
            f"{mean_w:>10.4f} {max_w:>10.4f} {sel_s:>9} {cost:>4}x"
        )

    print("=" * 90)

    # Highlight best re-anchored
    reanchored = [m for m in results
                  if "Reanchor" in m["method"] or "RA-Margin" in m["method"]]
    if reanchored:
        best = max(reanchored, key=lambda x: x.get("auroc", 0))
        naive = [m for m in results if m["method"] == "Naive IBP"]
        naive_auroc = naive[0]["auroc"] if naive else 0

        print(f"\nBest re-anchored: {best['method']}")
        print(f"  AUROC: {best['auroc']:.4f} (naive: {naive_auroc:.4f}, "
              f"delta: {best['auroc'] - naive_auroc:+.4f})")
        if naive:
            print(f"  Width: {best['mean_width']:.4f} (naive: "
                  f"{naive[0]['mean_width']:.2f})")

        if best["auroc"] >= 0.70:
            print("\n>>> P4 HYPOTHESIS CONFIRMED: AUROC >= 0.70 <<<")
        elif best["auroc"] >= 0.65:
            print("\n>>> P4 HYPOTHESIS: PARTIAL SUPPORT (0.65 <= AUROC < 0.70) <<<")
        else:
            print("\n>>> P4 HYPOTHESIS NOT CONFIRMED: AUROC < 0.65 <<<")


def _save_csv(results):
    import pandas as pd

    os.makedirs("benchmark_results", exist_ok=True)
    csv_results = []
    for r in results:
        row = {k: v for k, v in r.items() if not isinstance(v, (list, dict))}
        csv_results.append(row)

    df = pd.DataFrame(csv_results)
    path = "benchmark_results/reanchor_results.csv"
    df.to_csv(path, index=False)
    print(f"\nSaved: {path}")


def _generate_plot(results):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs("benchmark_results", exist_ok=True)

    fig, axes = plt.subplots(2, 2, figsize=(15, 11))
    fig.suptitle(
        "P4 Hypothesis: Process-Based Interval Propagation\n"
        "MNIST MLP (784->256->128->64->10), eps=0.02",
        fontsize=13, fontweight="bold",
    )

    # Categorize
    reanchored = [m for m in results
                  if "Reanchor" in m["method"] or "RA-Margin" in m["method"]]
    baselines = [m for m in results
                 if "Reanchor" not in m["method"] and "RA-Margin" not in m["method"]]

    def _color(name):
        if "RA-Margin" in name:
            return "#2ecc71"  # bright green for margin
        if "Spread" in name:
            return "#1abc9c"  # teal for spread
        if "Naive" in name:
            return "#cccccc"
        if "prop" in name.lower():
            return "#9b59b6"  # purple for proportional
        if "mid" in name.lower():
            return "#e94560"
        if "ada" in name.lower():
            return "#ff7b54"
        if "MC" in name:
            return "#4a90d9"
        if "Ensemble" in name:
            return "#50c878"
        if "Temp" in name:
            return "#f5a623"
        return "#888888"

    # ---- Panel 1: AUROC (all methods, sorted) ----
    ax = axes[0, 0]
    sorted_r = sorted(results, key=lambda x: x.get("auroc", 0))
    names = [m["method"][:35] for m in sorted_r]
    aurocs = [m.get("auroc", 0) for m in sorted_r]
    colors = [_color(m["method"]) for m in sorted_r]

    bars = ax.barh(range(len(names)), aurocs, color=colors, alpha=0.85)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=6)
    ax.set_xlabel("AUROC")
    ax.set_title("Error Detection Quality")
    ax.axvline(x=0.5, color="red", linestyle="--", alpha=0.3)
    ax.set_xlim(0.35, 1.0)

    # ---- Panel 2: Width control (log scale) ----
    ax = axes[0, 1]
    if reanchored:
        # Group by block_size
        for bs in sorted(set(m.get("block_size", 0) for m in reanchored)):
            subset = [m for m in reanchored if m.get("block_size") == bs
                      and "mid" in m["method"].lower()]
            if not subset:
                continue
            eps_vals = [m.get("reanchor_eps", 0) for m in subset]
            widths = [m.get("mean_width", 0) for m in subset]
            ax.plot(eps_vals, widths, "o-", label=f"bs={bs}", linewidth=2, markersize=6)

    # Add naive baseline
    naive = [m for m in baselines if "Naive" in m["method"]]
    if naive:
        ax.axhline(y=naive[0].get("mean_width", 0), color="gray",
                    linestyle="--", alpha=0.5, label="Naive IBP")

    ax.set_xlabel("reanchor_eps")
    ax.set_ylabel("Mean Output Width")
    ax.set_title("Width Control (midpoint)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    # ---- Panel 3: AUROC vs Width scatter ----
    ax = axes[1, 0]
    for m in results:
        auroc = m.get("auroc", 0)
        width = m.get("mean_width", 0)
        color = _color(m["method"])
        ax.scatter(width, auroc, c=color, s=60, alpha=0.8,
                   edgecolors="black", linewidth=0.3)

    # Label baselines
    for m in baselines:
        ax.annotate(
            m["method"][:15], (m.get("mean_width", 0), m.get("auroc", 0)),
            fontsize=5.5, xytext=(3, 3), textcoords="offset points",
        )

    ax.set_xlabel("Mean Output Width (log)")
    ax.set_ylabel("AUROC")
    ax.set_title("Width vs Detection Quality")
    ax.set_xscale("log")
    ax.axhline(y=0.5, color="red", linestyle="--", alpha=0.3)
    ax.axhline(y=0.7, color="green", linestyle="--", alpha=0.3, label="target 0.70")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    # ---- Panel 4: Cost comparison ----
    ax = axes[1, 1]
    method_groups = {
        "Naive IBP": 1,
        "Re-anchored (best)": 1,
        "MC Dropout": 50,
        "Deep Ensemble": 5,
        "Temp Scaling": 1,
    }
    group_colors = ["#cccccc", "#e94560", "#4a90d9", "#50c878", "#f5a623"]

    # Get best re-anchored AUROC for annotation
    best_ra = max(reanchored, key=lambda x: x.get("auroc", 0)) if reanchored else None
    group_aurocs = {}
    for m in baselines:
        if "Naive" in m["method"]:
            group_aurocs["Naive IBP"] = m.get("auroc", 0)
        elif "MC" in m["method"]:
            group_aurocs["MC Dropout"] = m.get("auroc", 0)
        elif "Ensemble" in m["method"]:
            group_aurocs["Deep Ensemble"] = m.get("auroc", 0)
        elif "Temp" in m["method"]:
            group_aurocs["Temp Scaling"] = m.get("auroc", 0)
    if best_ra:
        group_aurocs["Re-anchored (best)"] = best_ra.get("auroc", 0)

    x_labels = list(method_groups.keys())
    costs = list(method_groups.values())
    bars = ax.bar(range(len(x_labels)), costs, color=group_colors, alpha=0.85)
    ax.set_xticks(range(len(x_labels)))
    ax.set_xticklabels(x_labels, rotation=30, ha="right", fontsize=7)
    ax.set_ylabel("Forward Passes per Prediction")
    ax.set_title("Computational Cost (AUROC annotated)")
    for i, (bar, label) in enumerate(zip(bars, x_labels)):
        auroc = group_aurocs.get(label, 0)
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            f"{costs[i]}x\nAUR={auroc:.2f}",
            ha="center", fontsize=7,
        )

    plt.tight_layout()
    path = "benchmark_results/reanchor_experiment.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")


# ============================================================
# CLI
# ============================================================

def main():
    quick = "--quick" in sys.argv
    run_reanchor_experiment(quick=quick)


if __name__ == "__main__":
    main()
