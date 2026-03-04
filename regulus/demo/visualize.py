"""
Regulus Visualization: eps sweep and reliability plots.

Generates:
1. Accuracy vs eps curve (standard vs filtered)
2. Recall / precision vs eps
3. Flagged count vs eps
4. Interval width propagation bar chart

Run: uv run python -m regulus.demo.visualize
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

import matplotlib.pyplot as plt

from regulus.nn.model import convert_model
from regulus.nn.interval_tensor import IntervalTensor
from regulus.analysis.reliability import ReliabilityAnalysis


def train_model():
    """Train standard model on Breast Cancer Wisconsin."""
    data = load_breast_cancer()
    X, y = data.data, data.target

    scaler = StandardScaler()
    X = scaler.fit_transform(X)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42
    )

    model = nn.Sequential(
        nn.Linear(30, 16),
        nn.ReLU(),
        nn.Linear(16, 8),
        nn.ReLU(),
        nn.Linear(8, 2),
    )

    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.CrossEntropyLoss()

    model.train()
    for epoch in range(200):
        optimizer.zero_grad()
        output = model(torch.FloatTensor(X_train))
        loss = criterion(output, torch.LongTensor(y_train))
        loss.backward()
        optimizer.step()

    model.eval()
    return model, X_test, y_test


def sweep_eps(interval_model, X_test, y_test, eps_values):
    """Run interval analysis at each eps, return metrics."""
    metrics = []
    for eps in eps_values:
        results = []
        for i in range(len(X_test)):
            x_interval = IntervalTensor.from_uncertainty(X_test[i], eps)
            output = interval_model(x_interval)
            analysis = ReliabilityAnalysis.classify(output)
            results.append(analysis)

        batch = ReliabilityAnalysis.batch_analysis(results, y_test)
        batch["eps"] = eps
        metrics.append(batch)
    return metrics


def plot_all(metrics, save_path="regulus_reliability.png"):
    """Generate a 2x2 figure with key plots."""
    eps_vals = [m["eps"] for m in metrics]
    acc_std = [m["accuracy_standard"] * 100 for m in metrics]
    acc_filt = [m["accuracy_after_filtering"] * 100 for m in metrics]
    recalls = [m["recall"] * 100 for m in metrics]
    precisions = [m["precision"] * 100 for m in metrics]
    flagged = [m["flagged_unreliable"] for m in metrics]
    caught = [m["caught"] for m in metrics]
    false_alarm = [m["false_alarm"] for m in metrics]

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.suptitle("Regulus: Interval Bound Propagation Reliability Analysis",
                 fontsize=14, fontweight="bold")

    # Plot 1: Accuracy comparison
    ax = axes[0, 0]
    ax.plot(eps_vals, acc_std, "k--", label="Standard accuracy", linewidth=2)
    ax.plot(eps_vals, acc_filt, "b-o", label="Filtered accuracy", linewidth=2)
    ax.fill_between(eps_vals, acc_std, acc_filt, alpha=0.2, color="green",
                    where=[f > s for f, s in zip(acc_filt, acc_std)])
    ax.set_xlabel("Input uncertainty (eps)")
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("Accuracy: Standard vs Filtered")
    ax.legend()
    ax.set_xscale("log")
    ax.grid(True, alpha=0.3)

    # Plot 2: Recall and Precision
    ax = axes[0, 1]
    ax.plot(eps_vals, recalls, "r-o", label="Recall (errors caught)", linewidth=2)
    ax.plot(eps_vals, precisions, "g-s", label="Precision", linewidth=2)
    ax.set_xlabel("Input uncertainty (eps)")
    ax.set_ylabel("%")
    ax.set_title("Recall & Precision vs Uncertainty")
    ax.legend()
    ax.set_xscale("log")
    ax.grid(True, alpha=0.3)
    ax.set_ylim(-5, 105)

    # Plot 3: Flagged breakdown
    ax = axes[1, 0]
    ax.bar(range(len(eps_vals)), caught, label="Caught (true positive)",
           color="green", alpha=0.8)
    ax.bar(range(len(eps_vals)), false_alarm, bottom=caught,
           label="False alarm", color="orange", alpha=0.8)
    ax.set_xticks(range(len(eps_vals)))
    ax.set_xticklabels([f"{e}" for e in eps_vals], rotation=45)
    ax.set_xlabel("Input uncertainty (eps)")
    ax.set_ylabel("Count")
    ax.set_title("Flagged Predictions Breakdown")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    # Plot 4: Key numbers table
    ax = axes[1, 1]
    ax.axis("off")
    total = metrics[0]["total"]
    wrong = metrics[0]["actually_wrong"]

    # Find best eps (highest accuracy improvement)
    best_idx = max(range(len(metrics)),
                   key=lambda i: metrics[i]["accuracy_after_filtering"] - metrics[i]["accuracy_standard"])
    best = metrics[best_idx]

    table_data = [
        ["Total test samples", str(total)],
        ["Standard errors", str(wrong)],
        ["Best eps", f"{best['eps']}"],
        ["Errors caught", f"{best['caught']}/{wrong}"],
        ["False alarms", str(best["false_alarm"])],
        ["Recall", f"{best['recall']:.0%}"],
        ["Precision", f"{best['precision']:.1%}"],
        ["Standard accuracy", f"{best['accuracy_standard']:.2%}"],
        ["Filtered accuracy", f"{best['accuracy_after_filtering']:.2%}"],
        ["Improvement", f"+{(best['accuracy_after_filtering'] - best['accuracy_standard'])*100:.2f}pp"],
    ]
    table = ax.table(
        cellText=table_data,
        colLabels=["Metric", "Value"],
        loc="center",
        cellLoc="left",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)
    ax.set_title("Summary (best eps)", pad=20)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    print(f"Saved: {save_path}")
    plt.show()


def main():
    print("Training model...")
    model, X_test, y_test = train_model()

    interval_model = convert_model(model)

    eps_values = [0.001, 0.002, 0.005, 0.01, 0.02, 0.03, 0.05, 0.07, 0.1, 0.15, 0.2]
    print(f"Sweeping {len(eps_values)} eps values...")
    metrics = sweep_eps(interval_model, X_test, y_test, eps_values)

    print("Generating plots...")
    plot_all(metrics)

    print("Done.")


if __name__ == "__main__":
    main()
