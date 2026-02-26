"""
Generate benchmark report: summary table + 4-panel comparison plot.

Output:
    benchmark_results/results.csv
    benchmark_results/comparison_plot.png
"""

from __future__ import annotations

import os
import numpy as np


def generate_report(all_results: list[dict], output_dir: str = "benchmark_results"):
    """Generate full benchmark report."""
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(output_dir, exist_ok=True)

    # ===== Summary Table =====
    # Remove non-scalar columns for CSV
    csv_results = []
    for r in all_results:
        row = {k: v for k, v in r.items() if k != "coverage_curve"}
        csv_results.append(row)

    df = pd.DataFrame(csv_results)

    # Print summary
    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS")
    print("=" * 80)

    cols = ["dataset", "method", "accuracy", "auroc", "auprc", "ece", "cost"]
    sel_cols = [c for c in df.columns if c.startswith("selective_acc")]
    display_cols = [c for c in cols + sel_cols if c in df.columns]
    print(df[display_cols].to_string(index=False, float_format="%.4f"))

    # Save CSV
    csv_path = os.path.join(output_dir, "results.csv")
    df.to_csv(csv_path, index=False)
    print(f"\nSaved: {csv_path}")

    # ===== Comparison Plot =====
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(
        "Regulus vs Existing Methods: Uncertainty Quantification Benchmark",
        fontsize=14, fontweight="bold",
    )

    datasets = df["dataset"].unique()
    methods = df["method"].unique()

    # Color scheme
    colors = {}
    for m in methods:
        m_lower = m.lower()
        if "regulus" in m_lower:
            colors[m] = "#e94560"
        elif "mc dropout" in m_lower:
            colors[m] = "#4a90d9"
        elif "ensemble" in m_lower:
            colors[m] = "#50c878"
        elif "temp" in m_lower:
            colors[m] = "#f5a623"
        else:
            colors[m] = "#888888"

    x_pos = np.arange(len(datasets))
    bar_width = 0.8 / max(len(methods), 1)

    # --- Panel 1: AUROC ---
    ax = axes[0, 0]
    for i, method in enumerate(methods):
        values = []
        for d in datasets:
            v = df[(df["method"] == method) & (df["dataset"] == d)]["auroc"].values
            values.append(v[0] if len(v) > 0 and not np.isnan(v[0]) else 0)
        ax.bar(
            x_pos + i * bar_width, values, bar_width,
            label=method, color=colors.get(method, "#888"), alpha=0.85,
        )
    ax.set_xticks(x_pos + bar_width * len(methods) / 2)
    ax.set_xticklabels(datasets, fontsize=8)
    ax.set_ylabel("AUROC")
    ax.set_title("Error Detection (higher = better)")
    ax.legend(fontsize=6, loc="lower right")
    ax.set_ylim(0, 1.05)

    # --- Panel 2: ECE ---
    ax = axes[0, 1]
    for i, method in enumerate(methods):
        values = []
        for d in datasets:
            v = df[(df["method"] == method) & (df["dataset"] == d)]["ece"].values
            values.append(v[0] if len(v) > 0 else 0)
        ax.bar(
            x_pos + i * bar_width, values, bar_width,
            label=method, color=colors.get(method, "#888"), alpha=0.85,
        )
    ax.set_xticks(x_pos + bar_width * len(methods) / 2)
    ax.set_xticklabels(datasets, fontsize=8)
    ax.set_ylabel("ECE")
    ax.set_title("Calibration Error (lower = better)")

    # --- Panel 3: Selective Accuracy @10% ---
    ax = axes[1, 0]
    key = "selective_acc@10%"
    for i, method in enumerate(methods):
        values = []
        for d in datasets:
            v = df[(df["method"] == method) & (df["dataset"] == d)][key].values
            values.append(v[0] if len(v) > 0 and not np.isnan(v[0]) else 0)
        ax.bar(
            x_pos + i * bar_width, values, bar_width,
            label=method, color=colors.get(method, "#888"), alpha=0.85,
        )
    ax.set_xticks(x_pos + bar_width * len(methods) / 2)
    ax.set_xticklabels(datasets, fontsize=8)
    ax.set_ylabel("Accuracy")
    ax.set_title("Accuracy After Rejecting 10% Most Uncertain")

    # --- Panel 4: Cost ---
    ax = axes[1, 1]
    cost_data = df.drop_duplicates("method")[["method", "cost"]].reset_index(drop=True)
    bar_colors = [colors.get(m, "#888") for m in cost_data["method"]]
    bars = ax.bar(range(len(cost_data)), cost_data["cost"].values, color=bar_colors, alpha=0.85)
    ax.set_xticks(range(len(cost_data)))
    ax.set_xticklabels(cost_data["method"], rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("Forward Passes")
    ax.set_title("Computational Cost per Prediction")
    for bar, val in zip(bars, cost_data["cost"].values):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
            f"{val}\u00d7", ha="center", fontsize=9,
        )

    plt.tight_layout()
    plot_path = os.path.join(output_dir, "comparison_plot.png")
    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {plot_path}")

    # ===== Coverage Curves (per dataset) =====
    _plot_coverage_curves(all_results, datasets, colors, output_dir)

    # ===== Width Bound Table (Regulus only) =====
    _print_width_bounds(df)

    return df


def _plot_coverage_curves(all_results, datasets, colors, output_dir):
    """Plot risk-coverage curves per dataset."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for ds in datasets:
        ds_results = [r for r in all_results if r.get("dataset") == ds]
        if not ds_results:
            continue

        fig, ax = plt.subplots(figsize=(8, 5))
        for r in ds_results:
            curve = r.get("coverage_curve")
            if curve:
                ax.plot(
                    curve["coverages"], curve["accuracies"],
                    label=r["method"],
                    color=colors.get(r["method"], "#888"),
                    linewidth=2, alpha=0.85,
                )

        ax.set_xlabel("Coverage (fraction retained)")
        ax.set_ylabel("Accuracy")
        ax.set_title(f"Risk-Coverage Curve: {ds}")
        ax.legend(fontsize=7)
        ax.set_xlim(0.1, 1.0)
        ax.grid(alpha=0.3)

        path = os.path.join(output_dir, f"coverage_{ds}.png")
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"Saved: {path}")


def _print_width_bounds(df):
    """Print Regulus width bound info."""
    regulus_rows = df[df["method"].str.contains("Regulus", case=False)]
    if regulus_rows.empty:
        return

    has_width = "predicted_max_width" in regulus_rows.columns
    if not has_width:
        return

    print("\n" + "-" * 60)
    print("WIDTH BOUND VERIFICATION (Coq-proven)")
    print("-" * 60)
    for _, row in regulus_rows.iterrows():
        pred = row.get("predicted_max_width", 0)
        actual = row.get("actual_max_width", 0)
        tight = row.get("bound_tightness", 0)
        print(
            f"  {row['dataset']} | {row['method']}: "
            f"predicted={pred:.4f}, actual={actual:.4f}, tightness={tight:.1f}x"
        )
