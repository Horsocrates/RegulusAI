"""
Publication-quality figures for the Regulus UQ paper.

Generates 7 PDF figures from benchmark data:
  Figure 1: Main comparison (grouped bars)
  Figure 2: Depth study (2 panels: width + AUROC)
  Figure 3: Alpha sweep (from combined_signal CSV)
  Figure 4: Applicability map
  Figure 5: CIFAR-10 architecture comparison (grouped bars)
  Figure 6: Traceable uncertainty grid (reliable vs unreliable)
  Figure 7: Traceable uncertainty heatmap

All figures saved as vector PDF in paper/figures/.

Usage:
    .venv313\\Scripts\\python.exe -m regulus.paper.generate_figures
    .venv313\\Scripts\\python.exe -m regulus.paper.generate_figures --fig 1
"""

from __future__ import annotations

import os
import sys
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams


# ============================================================
# Style configuration
# ============================================================

COLORS = {
    "naive_ibp":       "#999999",
    "ra_margin":       "#d62728",
    "ra_adaptive":     "#ff7f0e",
    "mc_dropout":      "#1f77b4",
    "deep_ensemble":   "#2ca02c",
    "temp_scaling":    "#9467bd",
    "combined":        "#e377c2",
}

# Method display names -> color keys
METHOD_COLOR_MAP = {
    "Naive IBP":            "naive_ibp",
    "RA-Margin (bs=1)":     "ra_margin",
    "RA-Adaptive+Margin":   "ra_adaptive",
    "MC Dropout (N=50)":    "mc_dropout",
    "Deep Ensemble (K=5)":  "deep_ensemble",
    "TempScaling":          "temp_scaling",
}

METHOD_COSTS = {
    "Naive IBP":            1,
    "RA-Margin (bs=1)":     1,
    "RA-Adaptive+Margin":   1,
    "MC Dropout (N=50)":    50,
    "Deep Ensemble (K=5)":  5,
    "TempScaling":          1,
}

DATASET_LABELS = {
    "breast_cancer": "Breast\nCancer",
    "credit":        "German\nCredit",
    "mnist":         "MNIST",
}

INPUT_DIR_V2 = "benchmark_results/full_benchmark_v2"
INPUT_DIR_COMBINED = "benchmark_results/combined_signal"
INPUT_DIR_CIFAR = "benchmark_results/cifar10_benchmark"
INPUT_DIR_ARCH = "benchmark_results/architecture_benchmark"
OUTPUT_DIR = "paper/figures"


def _setup_style():
    """Academic matplotlib style: serif 10pt, clean axes, no titles."""
    rcParams.update({
        "font.family":       "serif",
        "font.size":         10,
        "axes.titlesize":    11,
        "axes.labelsize":    10,
        "xtick.labelsize":   9,
        "ytick.labelsize":   9,
        "legend.fontsize":   8,
        "figure.dpi":        300,
        "savefig.dpi":       300,
        "savefig.bbox":      "tight",
        "savefig.pad_inches": 0.05,
        "axes.spines.top":   False,
        "axes.spines.right": False,
    })


def _color(method_name: str) -> str:
    """Look up color for a method name."""
    key = METHOD_COLOR_MAP.get(method_name)
    if key:
        return COLORS[key]
    # Fallback heuristic matching
    for substr, ckey in [
        ("RA-Margin", "ra_margin"),
        ("RA-Adaptive", "ra_adaptive"),
        ("MC Dropout", "mc_dropout"),
        ("Deep Ensemble", "deep_ensemble"),
        ("TempScaling", "temp_scaling"),
        ("Temp Scaling", "temp_scaling"),
        ("Naive", "naive_ibp"),
    ]:
        if substr in method_name:
            return COLORS[ckey]
    return "#888888"


# ============================================================
# Figure 1: Main comparison -- grouped bar chart
# ============================================================

def generate_figure1():
    """Grouped bar chart: 3 dataset groups x 5 key methods, Y=AUROC."""
    _setup_style()

    df = pd.read_csv(os.path.join(INPUT_DIR_V2, "comparison_table.csv"))

    # Select 5 key methods for clean visualization
    key_methods = [
        "Naive IBP",
        "RA-Margin (bs=1)",
        "MC Dropout (N=50)",
        "Deep Ensemble (K=5)",
        "TempScaling",
    ]
    datasets = ["breast_cancer", "credit", "mnist"]

    fig, ax = plt.subplots(figsize=(7, 4))

    n_methods = len(key_methods)
    width = 0.14
    x = np.arange(len(datasets))

    for i, method in enumerate(key_methods):
        aurocs = []
        for ds in datasets:
            row = df[(df["method"] == method) & (df["dataset"] == ds)]
            aurocs.append(float(row["auroc"].values[0]) if len(row) else np.nan)

        offset = (i - n_methods / 2 + 0.5) * width
        color = _color(method)
        cost = METHOD_COSTS.get(method, 1)
        label = f"{method} ({cost}x)"

        bars = ax.bar(x + offset, aurocs, width, label=label,
                      color=color, edgecolor="white", linewidth=0.5)

        # Value labels on bars
        for bar, val in zip(bars, aurocs):
            if not np.isnan(val):
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.008,
                        f"{val:.2f}", ha="center", va="bottom",
                        fontsize=6, fontweight="bold")

    # Random baseline
    ax.axhline(y=0.5, color="gray", linestyle="--", alpha=0.4, linewidth=0.8,
               label="Random (0.5)")

    ax.set_xticks(x)
    ax.set_xticklabels([DATASET_LABELS[d] for d in datasets])
    ax.set_ylabel("AUROC (Error Detection)")
    ax.set_ylim(0.3, 1.08)
    ax.legend(loc="lower right", framealpha=0.9, fontsize=7)
    ax.grid(axis="y", alpha=0.15)

    path = os.path.join(OUTPUT_DIR, "fig1_main_comparison.pdf")
    plt.savefig(path, format="pdf")
    plt.close()
    print(f"Saved: {path}")


# ============================================================
# Figure 2: Depth study (2 panels)
# ============================================================

def generate_figure2():
    """Left: Width vs Depth (log Y). Right: AUROC vs Depth."""
    _setup_style()

    df = pd.read_csv(os.path.join(INPUT_DIR_V2, "depth_study_v2.csv"))

    depths = df["depth"].values
    naive_w = df["naive_mean_width"].values
    ra_w = df["ra_mean_width"].values
    naive_auroc = df["naive_auroc"].values
    ra_auroc = df["ra_auroc"].values
    mc_auroc = df["mc_auroc"].values

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7, 3))

    # --- Panel 1: Width vs Depth (log scale) ---
    ax1.semilogy(depths, naive_w, "o--", color=COLORS["naive_ibp"],
                 linewidth=1.5, markersize=5, label="Naive IBP")
    ax1.semilogy(depths, ra_w, "s-", color=COLORS["ra_margin"],
                 linewidth=1.5, markersize=5, label="RA-Margin")
    ax1.set_xlabel("Model Depth (linear layers)")
    ax1.set_ylabel("Mean Output Width (log scale)")
    ax1.legend(fontsize=8)
    ax1.set_xticks(depths)
    ax1.grid(alpha=0.2)

    # Annotate extreme values
    ax1.annotate(f"{naive_w[-1]:.0f}",
                 xy=(depths[-1], naive_w[-1]),
                 xytext=(-15, 10), textcoords="offset points",
                 fontsize=6, color=COLORS["naive_ibp"])
    ax1.annotate(f"{ra_w[-1]:.2f}",
                 xy=(depths[-1], ra_w[-1]),
                 xytext=(-15, -12), textcoords="offset points",
                 fontsize=6, color=COLORS["ra_margin"])

    # --- Panel 2: AUROC vs Depth ---
    ax2.plot(depths, naive_auroc, "o--", color=COLORS["naive_ibp"],
             linewidth=1.2, markersize=4, label="Naive IBP")
    ax2.plot(depths, ra_auroc, "s-", color=COLORS["ra_margin"],
             linewidth=1.5, markersize=5, label="RA-Margin")
    ax2.plot(depths, mc_auroc, "D-", color=COLORS["mc_dropout"],
             linewidth=1.2, markersize=4, label="MC Dropout")
    ax2.axhline(y=0.5, color="gray", linestyle="--", alpha=0.4, linewidth=0.8)
    ax2.set_xlabel("Model Depth (linear layers)")
    ax2.set_ylabel("AUROC")
    ax2.set_ylim(0.0, 1.05)
    ax2.legend(loc="lower left", fontsize=8)
    ax2.set_xticks(depths)
    ax2.grid(alpha=0.2)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig2_depth_study.pdf")
    plt.savefig(path, format="pdf")
    plt.close()
    print(f"Saved: {path}")


# ============================================================
# Figure 3: Alpha sweep
# ============================================================

def generate_figure3():
    """X=alpha, Y=AUROC, one curve per dataset. Shows optimal alpha."""
    _setup_style()

    csv_path = os.path.join(INPUT_DIR_COMBINED, "combined_signal.csv")
    if not os.path.exists(csv_path):
        print(f"SKIP Figure 3: {csv_path} not found. Run combined_signal first.")
        return

    df = pd.read_csv(csv_path)
    wavg = df[df["combo"] == "WeightedAvg"].copy()

    if wavg.empty:
        print("SKIP Figure 3: no WeightedAvg rows in combined_signal.csv")
        return

    fig, ax = plt.subplots(figsize=(5, 3.5))

    ds_colors = {
        "breast_cancer": COLORS["ra_margin"],
        "credit":        COLORS["mc_dropout"],
        "mnist":         COLORS["deep_ensemble"],
    }
    ds_labels = {
        "breast_cancer": "Breast Cancer",
        "credit":        "German Credit",
        "mnist":         "MNIST",
    }
    ds_markers = {
        "breast_cancer": "o",
        "credit":        "s",
        "mnist":         "D",
    }

    for ds_name in ["breast_cancer", "credit", "mnist"]:
        ds_data = wavg[wavg["dataset"] == ds_name].sort_values("alpha")
        if ds_data.empty:
            continue
        alphas = ds_data["alpha"].values
        aurocs = ds_data["auroc"].values
        color = ds_colors[ds_name]
        marker = ds_markers[ds_name]

        ax.plot(alphas, aurocs, f"{marker}-",
                color=color, linewidth=1.5, markersize=4,
                label=ds_labels[ds_name])

        # Star at best alpha
        best_idx = int(np.nanargmax(aurocs))
        ax.plot(alphas[best_idx], aurocs[best_idx], "*",
                color=color, markersize=12, zorder=5)
        ax.annotate(f"a={alphas[best_idx]:.1f}",
                    xy=(alphas[best_idx], aurocs[best_idx]),
                    xytext=(5, 5), textcoords="offset points",
                    fontsize=6, color=color)

    ax.set_xlabel(r"$\alpha$ (weight on RA-Margin)")
    ax.set_ylabel("AUROC")
    ax.set_xlim(-0.05, 1.05)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.2)

    # Endpoint annotations
    ax.text(0.02, 0.02, "Pure TempScaling",
            transform=ax.transAxes, fontsize=7, color="gray",
            ha="left", va="bottom")
    ax.text(0.98, 0.02, "Pure RA-Margin",
            transform=ax.transAxes, fontsize=7, color="gray",
            ha="right", va="bottom")

    path = os.path.join(OUTPUT_DIR, "fig3_alpha_sweep.pdf")
    plt.savefig(path, format="pdf")
    plt.close()
    print(f"Saved: {path}")


# ============================================================
# Figure 4: Applicability map
# ============================================================

def generate_figure4():
    """Scatter: X=input dim (log), Y=depth, size=AUROC, color=best method."""
    _setup_style()

    df = pd.read_csv(os.path.join(INPUT_DIR_V2, "comparison_table.csv"))

    ds_info = {
        "breast_cancer": {"input_dim": 30,  "depth": 3},
        "credit":        {"input_dim": 20,  "depth": 3},
        "mnist":         {"input_dim": 784, "depth": 4},
    }

    fig, ax = plt.subplots(figsize=(6, 4))

    # Plot all methods as small dots + best as large dot per dataset
    for ds_name, info in ds_info.items():
        ds_data = df[df["dataset"] == ds_name]

        # Small dots for all methods
        np.random.seed(hash(ds_name) % 2**31)
        for _, row in ds_data.iterrows():
            jx = info["input_dim"] * (1 + np.random.uniform(-0.08, 0.08))
            jy = info["depth"] + np.random.uniform(-0.15, 0.15)
            auroc = float(row["auroc"])
            ax.scatter(jx, jy,
                       s=max(15, auroc * 100),
                       c=_color(row["method"]),
                       alpha=0.4, edgecolors="none")

        # Large dot for best method
        best_idx = ds_data["auroc"].idxmax()
        best_row = ds_data.loc[best_idx]
        best_method = best_row["method"]
        best_auroc = float(best_row["auroc"])

        ax.scatter(info["input_dim"], info["depth"],
                   s=best_auroc * 300,
                   c=_color(best_method),
                   edgecolors="black", linewidth=0.8, zorder=5)

        # Label
        label_text = ds_name.replace("_", " ").title()
        ax.annotate(f"{label_text}\n{best_method}\nAUROC={best_auroc:.2f}",
                    xy=(info["input_dim"], info["depth"]),
                    xytext=(15, 10), textcoords="offset points",
                    fontsize=6.5, ha="left",
                    arrowprops=dict(arrowstyle="-", color="gray",
                                    lw=0.5, alpha=0.5))

    # Legend for method colors
    for label, ckey in [
        ("Naive IBP",       "naive_ibp"),
        ("RA-Margin",       "ra_margin"),
        ("MC Dropout",      "mc_dropout"),
        ("Deep Ensemble",   "deep_ensemble"),
        ("TempScaling",     "temp_scaling"),
    ]:
        ax.scatter([], [], c=COLORS[ckey], s=50, label=label,
                   edgecolors="black", linewidth=0.5)

    ax.set_xlabel("Input Dimensionality")
    ax.set_ylabel("Model Depth (linear layers)")
    ax.set_xscale("log")
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(alpha=0.2)

    path = os.path.join(OUTPUT_DIR, "fig4_applicability.pdf")
    plt.savefig(path, format="pdf")
    plt.close()
    print(f"Saved: {path}")


# ============================================================
# Figure 5: CIFAR-10 Architecture Comparison
# ============================================================

def generate_figure5():
    """Grouped bar chart: 2 CIFAR architectures x 5 methods, Y=AUROC."""
    _setup_style()

    csv_path = os.path.join(INPUT_DIR_CIFAR, "cifar10_results.csv")
    if not os.path.exists(csv_path):
        print(f"SKIP Figure 5: {csv_path} not found. Run cifar10_benchmark first.")
        return

    df = pd.read_csv(csv_path)

    archs = ["CNN+BN", "ResNet+BN"]
    methods = ["Naive IBP", "Naive IBP+Margin", "RA-Margin",
               "TempScaling", "MC Dropout (N=50)"]
    method_colors_local = {
        "Naive IBP":           COLORS["naive_ibp"],
        "Naive IBP+Margin":    "#cccccc",
        "RA-Margin":           COLORS["ra_margin"],
        "TempScaling":         COLORS["temp_scaling"],
        "MC Dropout (N=50)":   COLORS["mc_dropout"],
    }

    fig, ax = plt.subplots(figsize=(7, 4))

    n_methods = len(methods)
    width = 0.14
    x = np.arange(len(archs))

    for i, method in enumerate(methods):
        aurocs = []
        for arch in archs:
            row = df[(df["method"] == method) & (df["arch"] == arch)]
            aurocs.append(float(row["auroc"].values[0]) if len(row) else np.nan)

        offset = (i - n_methods / 2 + 0.5) * width
        color = method_colors_local.get(method, "#888888")
        cost_map = {
            "Naive IBP": 1, "Naive IBP+Margin": 1, "RA-Margin": 1,
            "TempScaling": 1, "MC Dropout (N=50)": 50,
        }
        cost = cost_map.get(method, 1)
        label = f"{method} ({cost}x)"

        bars = ax.bar(x + offset, aurocs, width, label=label,
                      color=color, edgecolor="white", linewidth=0.5)

        for bar, val in zip(bars, aurocs):
            if not np.isnan(val):
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.008,
                        f"{val:.2f}", ha="center", va="bottom",
                        fontsize=6, fontweight="bold")

    ax.axhline(y=0.5, color="gray", linestyle="--", alpha=0.4, linewidth=0.8,
               label="Random (0.5)")

    ax.set_xticks(x)
    ax.set_xticklabels(archs)
    ax.set_ylabel("AUROC (Error Detection)")
    ax.set_ylim(0.3, 1.08)
    ax.legend(loc="lower right", framealpha=0.9, fontsize=7)
    ax.grid(axis="y", alpha=0.15)

    path = os.path.join(OUTPUT_DIR, "fig5_cifar10_comparison.pdf")
    plt.savefig(path, format="pdf")
    plt.close()
    print(f"Saved: {path}")


# ============================================================
# Figure 6: Traceable Uncertainty Grid
# ============================================================

def generate_figure6():
    """3 reliable + 3 unreliable trace examples as subplot grid."""
    _setup_style()

    # Load trace reports from pickle
    import pickle
    trace_path = os.path.join(INPUT_DIR_CIFAR, "traces", "trace_reports.pkl")
    if not os.path.exists(trace_path):
        print(f"SKIP Figure 6: {trace_path} not found. Run cifar10_benchmark first.")
        return

    with open(trace_path, "rb") as f:
        data = pickle.load(f)

    reports = data["reports"]
    labels = data["labels"]

    reliable_reports = [r for r in reports if r.reliable]
    unreliable_reports = [r for r in reports if not r.reliable]

    n_reliable = min(3, len(reliable_reports))
    n_unreliable = min(3, len(unreliable_reports))

    if n_reliable + n_unreliable == 0:
        print("SKIP Figure 6: no trace reports to plot.")
        return

    n_total = n_reliable + n_unreliable
    fig, axes = plt.subplots(1, n_total, figsize=(3.2 * n_total, 3.5))
    if n_total == 1:
        axes = [axes]

    for i, report in enumerate(reliable_reports[:n_reliable]):
        ax = axes[i]
        margins = [b.margin for b in report.block_reports]
        blocks = list(range(len(margins)))
        colors_list = ["#2ecc71" if m > 1.0 else "#f39c12" if m > 0.5
                       else "#e74c3c" for m in margins]
        ax.barh(blocks, margins, color=colors_list, edgecolor="white",
                linewidth=0.3)
        ax.axvline(x=1.0, color="black", linestyle="--", linewidth=0.6,
                   alpha=0.5)
        ax.set_yticks(blocks)
        ax.set_yticklabels([f"B{b}" for b in blocks], fontsize=7)
        ax.set_xlabel("Margin", fontsize=8)
        pred = report.predicted_class
        ax.set_title(f"Reliable (cls={pred})", fontsize=8, color="#2ecc71")
        ax.invert_yaxis()

    for j, report in enumerate(unreliable_reports[:n_unreliable]):
        ax = axes[n_reliable + j]
        margins = [b.margin for b in report.block_reports]
        blocks = list(range(len(margins)))
        colors_list = ["#2ecc71" if m > 1.0 else "#f39c12" if m > 0.5
                       else "#e74c3c" for m in margins]
        ax.barh(blocks, margins, color=colors_list, edgecolor="white",
                linewidth=0.3)
        ax.axvline(x=1.0, color="black", linestyle="--", linewidth=0.6,
                   alpha=0.5)
        ax.set_yticks(blocks)
        ax.set_yticklabels([f"B{b}" for b in blocks], fontsize=7)
        ax.set_xlabel("Margin", fontsize=8)
        crit = report.critical_block
        pred = report.predicted_class
        ax.set_title(f"Unreliable (cls={pred}, crit=B{crit})",
                     fontsize=8, color="#e74c3c")
        ax.invert_yaxis()

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig6_traceable_grid.pdf")
    plt.savefig(path, format="pdf")
    plt.close()
    print(f"Saved: {path}")


# ============================================================
# Figure 7: Traceable Uncertainty Heatmap
# ============================================================

def generate_figure7():
    """Rows=samples sorted by final margin, cols=blocks, color=margin."""
    _setup_style()

    import pickle
    trace_path = os.path.join(INPUT_DIR_CIFAR, "traces", "trace_reports.pkl")
    if not os.path.exists(trace_path):
        print(f"SKIP Figure 7: {trace_path} not found. Run cifar10_benchmark first.")
        return

    with open(trace_path, "rb") as f:
        data = pickle.load(f)

    reports = data["reports"]

    if not reports:
        print("SKIP Figure 7: no trace reports.")
        return

    n_blocks = reports[0].n_blocks
    n_samples = len(reports)

    # Build matrix: rows=samples, cols=blocks
    matrix = np.zeros((n_samples, n_blocks))
    for i, r in enumerate(reports):
        for j, b in enumerate(r.block_reports):
            matrix[i, j] = b.margin

    # Sort rows by final margin (last column)
    order = np.argsort(matrix[:, -1])
    matrix = matrix[order]

    # Clip for better visual range
    matrix = np.clip(matrix, 0, 5)

    fig, ax = plt.subplots(figsize=(max(4, n_blocks * 0.8 + 1), max(4, n_samples * 0.25 + 1)))

    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list(
        "margin_cmap",
        [(0, "#e74c3c"), (0.2, "#f39c12"), (0.4, "#2ecc71"), (1.0, "#27ae60")]
    )

    im = ax.imshow(matrix, aspect="auto", cmap=cmap,
                   interpolation="nearest", vmin=0, vmax=5)

    ax.set_xlabel("Block Index")
    ax.set_ylabel("Sample (sorted by final margin)")
    ax.set_xticks(range(n_blocks))
    ax.set_xticklabels([f"B{i}" for i in range(n_blocks)], fontsize=8)

    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Margin", fontsize=8)

    # Horizontal line at threshold boundary
    final_margins_sorted = matrix[:, -1]
    boundary = np.searchsorted(final_margins_sorted, 1.0)
    if 0 < boundary < n_samples:
        ax.axhline(y=boundary - 0.5, color="white", linestyle="--",
                   linewidth=1.5, alpha=0.8)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "fig7_trace_heatmap.pdf")
    plt.savefig(path, format="pdf")
    plt.close()
    print(f"Saved: {path}")


# ============================================================
# CLI
# ============================================================

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Parse --fig N argument
    fig_arg = None
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--fig" and i + 1 < len(args):
            fig_arg = int(args[i + 1])
            break
        elif arg.startswith("--fig="):
            fig_arg = int(arg.split("=")[1])
            break

    generators = {
        1: ("Main Comparison", generate_figure1),
        2: ("Depth Study", generate_figure2),
        3: ("Alpha Sweep", generate_figure3),
        4: ("Applicability Map", generate_figure4),
        5: ("CIFAR-10 Comparison", generate_figure5),
        6: ("Traceable Grid", generate_figure6),
        7: ("Traceable Heatmap", generate_figure7),
    }

    if fig_arg:
        name, gen = generators[fig_arg]
        print(f"Generating Figure {fig_arg}: {name}...")
        gen()
    else:
        for num, (name, gen) in generators.items():
            print(f"\nGenerating Figure {num}: {name}...")
            gen()

    print("\nDone. All figures in:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
