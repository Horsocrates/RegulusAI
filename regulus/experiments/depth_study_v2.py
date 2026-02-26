"""
Depth Study v2: Naive IBP vs RA-Margin vs MC Dropout across model depths.

Shows that RA-Margin scales to deep models while Naive IBP blows up.

Usage:
    .venv313\\Scripts\\python.exe -m regulus.experiments.depth_study_v2
    .venv313\\Scripts\\python.exe -m regulus.experiments.depth_study_v2 --quick
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
    MCDropoutMethod,
    _compute_margin_uncertainty,
)

OUTPUT_DIR = "benchmark_results/full_benchmark_v2"
INPUT_EPS = 0.02


# ============================================================
# Model factory for varying depths
# ============================================================

def make_depth_model(depth: int) -> nn.Sequential:
    """Create MNIST MLP with specified number of Linear layers.

    depth=2:  784->256->10
    depth=4:  784->256->128->64->10
    depth=6:  784->256->128->128->128->64->10
    depth=8:  784->256->128->128->128->128->64->10
    depth=10: 784->256->128(x6)->128->64->10
    depth=12: 784->256->128(x8)->128->64->10
    """
    if depth < 2:
        raise ValueError("Minimum depth is 2")

    if depth == 2:
        return nn.Sequential(
            nn.Linear(784, 256), nn.ReLU(),
            nn.Linear(256, 10),
        )

    # depth >= 4: start with 784->256->ReLU, end with 64->10
    layers: list[nn.Module] = [nn.Linear(784, 256), nn.ReLU()]

    if depth >= 4:
        layers += [nn.Linear(256, 128), nn.ReLU()]

    # Middle layers: 128->128 pairs
    n_middle = max(0, depth - 4)
    for _ in range(n_middle):
        layers += [nn.Linear(128, 128), nn.ReLU()]

    if depth >= 4:
        layers += [nn.Linear(128, 64), nn.ReLU()]
        layers += [nn.Linear(64, 10)]
    else:
        # depth=3 edge case (shouldn't happen with our list)
        layers += [nn.Linear(256, 10)]

    return nn.Sequential(*layers)


def _count_params(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())


# ============================================================
# MNIST loading
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

    return X_train.astype(np.float32), y_train, X_test.astype(np.float32), y_test


# ============================================================
# Training
# ============================================================

def train_model(model, X_train, y_train, epochs=20, lr=0.001, batch_size=256):
    """Train with mini-batch Adam."""
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
        if (epoch + 1) % 5 == 0:
            print(f"      Epoch {epoch+1}/{epochs}: loss={total_loss/n_batches:.4f}")

    model.eval()
    return model


# ============================================================
# Main depth study
# ============================================================

def run_depth_study(quick: bool = False):
    depths = [2, 4, 6, 8, 10, 12]
    n_test = 1000 if quick else 2000

    print("=" * 70)
    print("DEPTH STUDY v2: Naive IBP vs RA-Margin vs MC Dropout")
    print(f"Depths: {depths} | Input eps: {INPUT_EPS} | Test: {n_test}")
    print("=" * 70)

    # Load data
    print("\nLoading MNIST...")
    X_train, y_train, X_test, y_test = load_mnist()
    X_test = X_test[:n_test]
    y_test = y_test[:n_test]
    print(f"  Train: {X_train.shape}, Test: {X_test.shape}")

    all_results = []

    for depth in depths:
        print(f"\n--- Depth {depth} ---")
        torch.manual_seed(42)
        model = make_depth_model(depth)
        n_params = _count_params(model)
        print(f"  Params: {n_params:,}")

        # Train
        model = train_model(model, X_train, y_train, epochs=20)

        model.eval()
        with torch.no_grad():
            preds = model(torch.FloatTensor(X_test)).argmax(dim=-1).numpy()
            acc = (preds == y_test).mean()
        print(f"  Test accuracy: {acc:.4f}")

        row = {"depth": depth, "n_params": n_params, "accuracy": acc}

        # -- Naive IBP --
        t0 = time.time()
        naive_model = convert_model(model)
        naive_widths = []
        naive_margin_uncs = []
        for i in range(n_test):
            x_int = IntervalTensor.from_uncertainty(X_test[i], INPUT_EPS)
            out = naive_model(x_int)
            naive_widths.append(out.mean_width())
            naive_margin_uncs.append(_compute_margin_uncertainty(out))

        naive_unc_w = np.array(naive_widths)
        naive_unc_m = np.array(naive_margin_uncs)
        t_naive = time.time() - t0

        m_naive_w = compute_metrics(preds, naive_unc_w, y_test, "Naive IBP")
        m_naive_m = compute_metrics(preds, naive_unc_m, y_test, "Naive IBP+Margin")

        row["naive_auroc"] = m_naive_w.get("auroc", np.nan)
        row["naive_margin_auroc"] = m_naive_m.get("auroc", np.nan)
        row["naive_mean_width"] = float(naive_unc_w.mean())
        row["naive_max_width"] = float(naive_unc_w.max())
        print(f"  Naive IBP:        AUROC={row['naive_auroc']:.4f}, "
              f"Width={row['naive_mean_width']:.2f}, Time={t_naive:.1f}s")
        print(f"  Naive IBP+Margin: AUROC={row['naive_margin_auroc']:.4f}")

        # -- RA-Margin --
        t0 = time.time()
        ra_model = ReanchoredIntervalModel(
            model, block_size=1, reanchor_eps=0.01, strategy="midpoint")
        ra_margin_uncs = []
        ra_widths = []
        for i in range(n_test):
            x_int = IntervalTensor.from_uncertainty(X_test[i], INPUT_EPS)
            out = ra_model(x_int)
            ra_margin_uncs.append(_compute_margin_uncertainty(out))
            ra_widths.append(out.mean_width())

        ra_unc = np.array(ra_margin_uncs)
        ra_w = np.array(ra_widths)
        t_ra = time.time() - t0

        m_ra = compute_metrics(preds, ra_unc, y_test, "RA-Margin")
        row["ra_auroc"] = m_ra.get("auroc", np.nan)
        row["ra_mean_width"] = float(ra_w.mean())
        row["ra_max_width"] = float(ra_w.max())
        row["ra_n_reanchors"] = ra_model.n_reanchors
        print(f"  RA-Margin:        AUROC={row['ra_auroc']:.4f}, "
              f"Width={row['ra_mean_width']:.4f}, Reanchors={ra_model.n_reanchors}, "
              f"Time={t_ra:.1f}s")

        # -- MC Dropout --
        t0 = time.time()
        mc = MCDropoutMethod(None, n_samples=50)
        mc.train_model(lambda: make_depth_model(depth), X_train, y_train,
                       epochs=20, lr=0.001)
        mc_preds, _, mc_unc = mc.predict_with_uncertainty(X_test)
        t_mc = time.time() - t0

        m_mc = compute_metrics(mc_preds, mc_unc, y_test, "MC Dropout")
        row["mc_auroc"] = m_mc.get("auroc", np.nan)
        print(f"  MC Dropout:       AUROC={row['mc_auroc']:.4f}, Time={t_mc:.1f}s")

        all_results.append(row)

    # Output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    _print_depth_table(all_results)
    _save_depth_csv(all_results)
    _generate_depth_plot(all_results)

    return all_results


# ============================================================
# Output
# ============================================================

def _print_depth_table(results):
    print("\n" + "=" * 90)
    print("DEPTH STUDY v2: RESULTS")
    print("=" * 90)
    print(f"{'Depth':>5s}  {'Params':>8s}  {'Acc':>6s}  "
          f"{'Naive':>7s}  {'NvMarg':>7s}  {'RA-Marg':>7s}  {'MC-Drop':>7s}  "
          f"{'NaiveW':>10s}  {'RA-W':>10s}")
    print("-" * 90)
    for r in results:
        print(
            f"{r['depth']:>5d}  {r['n_params']:>8,d}  {r['accuracy']:>6.4f}  "
            f"{r['naive_auroc']:>7.4f}  {r['naive_margin_auroc']:>7.4f}  "
            f"{r['ra_auroc']:>7.4f}  {r['mc_auroc']:>7.4f}  "
            f"{r['naive_mean_width']:>10.2f}  {r['ra_mean_width']:>10.4f}"
        )
    print("=" * 90)


def _save_depth_csv(results):
    import pandas as pd
    df = pd.DataFrame(results)
    path = os.path.join(OUTPUT_DIR, "depth_study_v2.csv")
    df.to_csv(path, index=False)
    print(f"\nSaved: {path}")


def _generate_depth_plot(results):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    depths = [r["depth"] for r in results]
    naive_w = [r["naive_mean_width"] for r in results]
    ra_w = [r["ra_mean_width"] for r in results]
    naive_auroc = [r["naive_auroc"] for r in results]
    naive_m_auroc = [r["naive_margin_auroc"] for r in results]
    ra_auroc = [r["ra_auroc"] for r in results]
    mc_auroc = [r["mc_auroc"] for r in results]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Depth Study v2: Scalability of RA-Margin on MNIST",
                 fontsize=13, fontweight="bold")

    # Panel 1: Width vs Depth
    ax1.semilogy(depths, naive_w, "o-", color="#cccccc", linewidth=2,
                 markersize=8, label="Naive IBP", zorder=3)
    ax1.semilogy(depths, ra_w, "s-", color="#2ecc71", linewidth=2,
                 markersize=8, label="RA-Midpoint (bs=1)", zorder=3)
    ax1.set_xlabel("Model Depth (# Linear layers)", fontsize=10)
    ax1.set_ylabel("Mean Output Width (log scale)", fontsize=10)
    ax1.set_title("Width Control", fontsize=11, fontweight="bold")
    ax1.legend(fontsize=9)
    ax1.grid(alpha=0.3)
    ax1.set_xticks(depths)

    # Panel 2: AUROC vs Depth
    ax2.plot(depths, naive_auroc, "o--", color="#cccccc", linewidth=2,
             markersize=7, label="Naive IBP (width)")
    ax2.plot(depths, naive_m_auroc, "v--", color="#95a5a6", linewidth=2,
             markersize=7, label="Naive IBP+Margin")
    ax2.plot(depths, ra_auroc, "s-", color="#2ecc71", linewidth=2.5,
             markersize=8, label="RA-Margin (bs=1)", zorder=3)
    ax2.plot(depths, mc_auroc, "D-", color="#4a90d9", linewidth=2,
             markersize=7, label="MC Dropout (N=50)")
    ax2.axhline(y=0.5, color="red", linestyle="--", alpha=0.3, label="Random")
    ax2.set_xlabel("Model Depth (# Linear layers)", fontsize=10)
    ax2.set_ylabel("AUROC (error detection)", fontsize=10)
    ax2.set_title("Detection Quality", fontsize=11, fontweight="bold")
    ax2.set_ylim(0.35, 1.02)
    ax2.legend(fontsize=8, loc="lower left")
    ax2.grid(alpha=0.3)
    ax2.set_xticks(depths)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "depth_study_v2.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {path}")


# ============================================================
# CLI
# ============================================================

def main():
    quick = "--quick" in sys.argv
    run_depth_study(quick=quick)


if __name__ == "__main__":
    main()
