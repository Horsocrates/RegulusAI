"""
Visualization for TraceableAnalysis reports.

Three plot types:
  plot_trace()         -- single sample: bar chart of per-block margins
  plot_trace_grid()    -- grid of N traces (reliable vs unreliable)
  plot_trace_heatmap() -- heatmap: samples x blocks, color = margin
"""

from __future__ import annotations

import numpy as np

from regulus.analysis.traceable import TraceReport


def plot_trace(report: TraceReport, save_path=None, title=None):
    """Horizontal bar chart of per-block margins for one example.

    Colors: red = critical block, green = margin > 1.0, orange = marginal.
    Dashed threshold line at 1.0.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    margins = [b.margin for b in report.block_reports]
    n_blocks = len(margins)

    fig, ax = plt.subplots(figsize=(8, max(3, n_blocks * 0.6)))

    colors = []
    for i, m in enumerate(margins):
        if i == report.critical_block:
            colors.append("#d62728")   # red
        elif m > 1.0:
            colors.append("#2ca02c")   # green
        else:
            colors.append("#ff7f0e")   # orange

    ax.barh(range(n_blocks), margins, color=colors, alpha=0.85)
    ax.axvline(x=1.0, color="black", linestyle="--", alpha=0.5,
               label="threshold=1.0")

    # Labels
    labels = []
    for b in report.block_reports:
        if b.is_final:
            labels.append(
                f"Block {b.block_idx} [class {b.top_class} vs {b.runner_up}]")
        else:
            labels.append(f"Block {b.block_idx}")

    ax.set_yticks(range(n_blocks))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Margin (distinguishability)")

    status = "RELIABLE" if report.reliable else "UNRELIABLE"
    color = "#2ca02c" if report.reliable else "#d62728"
    if title is None:
        title = f"Prediction: class {report.predicted_class} -- {status}"
    ax.set_title(title, color=color, fontweight="bold", fontsize=11)

    ax.invert_yaxis()
    ax.legend(fontsize=8)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()
    else:
        plt.close()

    return fig


def plot_trace_grid(reports: list, n_reliable: int = 3,
                    n_unreliable: int = 3, save_path=None):
    """Grid: N reliable + N unreliable examples side by side.

    Parameters
    ----------
    reports : list of TraceReport
    n_reliable : how many reliable examples to show
    n_unreliable : how many unreliable examples to show
    save_path : optional path to save PNG/PDF
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    reliable = [r for r in reports if r.reliable][:n_reliable]
    unreliable = [r for r in reports if not r.reliable][:n_unreliable]
    selected = reliable + unreliable
    n = len(selected)

    if n == 0:
        return None

    fig, axes = plt.subplots(1, n, figsize=(4 * n, 4), sharey=False)
    if n == 1:
        axes = [axes]

    for ax, report in zip(axes, selected):
        margins = [b.margin for b in report.block_reports]
        n_blocks = len(margins)

        colors = [
            "#d62728" if i == report.critical_block
            else "#2ca02c" if m > 1.0
            else "#ff7f0e"
            for i, m in enumerate(margins)
        ]

        ax.barh(range(n_blocks), margins, color=colors, alpha=0.85)
        ax.axvline(x=1.0, color="black", linestyle="--", alpha=0.3)
        ax.set_yticks(range(n_blocks))
        ax.set_yticklabels(
            [f"B{b.block_idx}" for b in report.block_reports], fontsize=8)

        status_mark = "OK" if report.reliable else "FAIL"
        color = "#2ca02c" if report.reliable else "#d62728"
        ax.set_title(f"Class {report.predicted_class} [{status_mark}]",
                     color=color, fontsize=10, fontweight="bold")
        ax.invert_yaxis()

    fig.suptitle("Traceable Uncertainty: Per-Block Margin Analysis",
                 fontsize=12)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()
    else:
        plt.close()

    return fig


def plot_trace_heatmap(reports: list, save_path=None, title=None):
    """Heatmap: examples x blocks, color = margin.

    Rows: examples sorted by final margin (ascending = least reliable first).
    Columns: blocks.
    Color: red = low margin, green = high margin.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors

    if not reports:
        return None

    # Sort by final margin
    sorted_reports = sorted(reports, key=lambda r: r.final_margin)

    n_examples = len(sorted_reports)
    n_blocks = len(sorted_reports[0].block_reports)

    matrix = np.zeros((n_examples, n_blocks))
    for i, r in enumerate(sorted_reports):
        for j, b in enumerate(r.block_reports):
            matrix[i, j] = min(b.margin, 5.0)  # cap for visualization

    fig, ax = plt.subplots(
        figsize=(max(6, n_blocks + 2), max(4, n_examples * 0.15 + 2)))

    cmap = mcolors.LinearSegmentedColormap.from_list(
        "margin", ["#d62728", "#ff7f0e", "#2ca02c"], N=256)

    im = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0, vmax=3)
    ax.set_xlabel("Block")
    ax.set_ylabel("Example (sorted by reliability)")
    ax.set_xticks(range(n_blocks))
    ax.set_xticklabels([f"B{i}" for i in range(n_blocks)])

    plt.colorbar(im, ax=ax, label="Margin")

    if title:
        ax.set_title(title, fontsize=11)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()
    else:
        plt.close()

    return fig
