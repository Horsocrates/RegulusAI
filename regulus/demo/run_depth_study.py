"""
Depth study: how model depth affects interval width and reliability.

For each depth (2, 4, 6, 8, 10, 12 layers):
1. Train MLP on MNIST with same hidden_dim
2. Convert to interval model
3. Measure: actual width, predicted bound (Coq), recall
4. Plot: depth vs width, depth vs recall, predicted vs actual

Usage:
    python -m regulus.demo.run_depth_study
"""

from __future__ import annotations

import time
import numpy as np
import torch
import torch.nn as nn

from regulus.nn.interval_tensor import IntervalTensor
from regulus.nn.model import convert_model
from regulus.analysis.reliability import ReliabilityAnalysis, predict_max_width


def build_model(depth: int, input_dim: int, hidden_dim: int, output_dim: int):
    """Build MLP with given depth (number of Linear+ReLU pairs before final)."""
    layers = []
    prev = input_dim
    for i in range(depth):
        layers.extend([nn.Linear(prev, hidden_dim), nn.ReLU()])
        prev = hidden_dim
    layers.append(nn.Linear(prev, output_dim))
    return nn.Sequential(*layers)


def train_model(model, X_train, y_train, epochs=20, lr=0.001):
    """Train with mini-batch SGD."""
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    X_t = torch.FloatTensor(X_train)
    y_t = torch.LongTensor(y_train)

    batch_size = 512
    n_batches = (len(X_t) + batch_size - 1) // batch_size

    model.train()
    for epoch in range(epochs):
        perm = torch.randperm(len(X_t))
        for b in range(n_batches):
            idx = perm[b * batch_size : (b + 1) * batch_size]
            optimizer.zero_grad()
            loss = criterion(model(X_t[idx]), y_t[idx])
            loss.backward()
            optimizer.step()

    model.eval()
    with torch.no_grad():
        logits = model(X_t[:5000])
        acc = (logits.argmax(dim=-1) == y_t[:5000]).float().mean().item()
    return model, acc


def run_depth_study():
    print("=" * 60)
    print("DEPTH STUDY: Model Depth vs Interval Width")
    print("=" * 60)

    # Load MNIST
    print("\nLoading MNIST...")
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

    depths = [2, 4, 6, 8, 10, 12]
    hidden_dim = 128
    input_eps = 0.02
    n_test = 500  # Subset for speed

    results = []

    for depth in depths:
        print(f"\n{'='*50}")
        print(f"Depth: {depth} hidden layers | hidden_dim={hidden_dim}")
        print(f"{'='*50}")

        # Build and train
        torch.manual_seed(42)
        model = build_model(depth, 784, hidden_dim, 10)
        n_params = sum(p.numel() for p in model.parameters())
        print(f"  Parameters: {n_params:,}")

        model, train_acc = train_model(model, X_train, y_train, epochs=20)
        print(f"  Train accuracy: {train_acc:.4f}")

        # Convert
        interval_model = convert_model(model)

        # Coq-proven width bound
        bound_info = predict_max_width(interval_model, input_eps)
        predicted_bound = bound_info["output_width_bound"]
        blowup = bound_info["blowup_factor"]
        print(f"  Predicted max width (Coq): {predicted_bound:.4f}")
        print(f"  Blowup factor: {blowup:.2f}x")
        print(f"  L1 norms per layer: {[f'{n:.2f}' for n in bound_info['layer_l1_norms']]}")

        # Run interval analysis
        t0 = time.time()
        analysis_results = []
        actual_widths = []

        for i in range(n_test):
            x_interval = IntervalTensor.from_uncertainty(X_test[i], input_eps)
            output = interval_model(x_interval)
            analysis = ReliabilityAnalysis.classify(output)
            analysis_results.append(analysis)
            actual_widths.append(output.max_width())

        t_inf = time.time() - t0

        # Batch metrics
        batch = ReliabilityAnalysis.batch_analysis(analysis_results, y_test[:n_test])

        actual_max_w = max(actual_widths)
        actual_mean_w = np.mean(actual_widths)
        bound_tightness = predicted_bound / actual_max_w if actual_max_w > 0 else float("inf")

        # Test accuracy on full test set
        model.eval()
        with torch.no_grad():
            logits = model(torch.FloatTensor(X_test))
            test_acc = (logits.argmax(dim=-1) == torch.LongTensor(y_test)).float().mean().item()

        print(f"  Test accuracy: {test_acc:.4f}")
        print(f"  Actual max width: {actual_max_w:.4f}")
        print(f"  Actual mean width: {actual_mean_w:.4f}")
        print(f"  Bound tightness: {bound_tightness:.1f}x")
        print(f"  Bound holds: {'YES' if actual_max_w <= predicted_bound + 1e-10 else 'NO'}")
        print(f"  Recall: {batch['recall']:.1%}")
        print(f"  Flagged: {batch['flagged_unreliable']}/{batch['total']}")
        print(f"  Filtered accuracy: {batch['accuracy_after_filtering']:.2%}")
        print(f"  Time: {t_inf:.2f}s")

        results.append({
            "depth": depth,
            "n_params": n_params,
            "test_accuracy": test_acc,
            "predicted_max_width": predicted_bound,
            "actual_max_width": actual_max_w,
            "actual_mean_width": actual_mean_w,
            "bound_tightness": bound_tightness,
            "blowup_factor": blowup,
            "layer_l1_norms": bound_info["layer_l1_norms"],
            "recall": batch["recall"],
            "precision": batch["precision"],
            "flagged": batch["flagged_unreliable"],
            "filtered_accuracy": batch["accuracy_after_filtering"],
            "standard_accuracy": batch["accuracy_standard"],
        })

    # Print summary table
    _print_summary(results)

    # Plot
    _plot_depth_study(results)

    return results


def _print_summary(results):
    print("\n" + "=" * 80)
    print("DEPTH STUDY SUMMARY")
    print("=" * 80)
    print(f"{'Depth':>5} {'Params':>8} {'TestAcc':>8} {'PredW':>10} {'ActualW':>10} "
          f"{'Tight':>7} {'Recall':>7} {'FiltAcc':>8}")
    print("-" * 80)
    for r in results:
        print(
            f"{r['depth']:>5} {r['n_params']:>8,} {r['test_accuracy']:>8.4f} "
            f"{r['predicted_max_width']:>10.4f} {r['actual_max_width']:>10.4f} "
            f"{r['bound_tightness']:>7.1f}x {r['recall']:>6.1%} "
            f"{r['filtered_accuracy']:>8.4f}"
        )


def _plot_depth_study(results):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import os

    os.makedirs("benchmark_results", exist_ok=True)

    depths = [r["depth"] for r in results]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle("Depth Study: Model Depth vs Interval Analysis Quality",
                 fontsize=13, fontweight="bold")

    # Panel 1: Width (predicted vs actual)
    ax = axes[0]
    ax.plot(depths, [r["predicted_max_width"] for r in results],
            "o-", color="#e94560", linewidth=2, label="Predicted (Coq bound)")
    ax.plot(depths, [r["actual_max_width"] for r in results],
            "s-", color="#4a90d9", linewidth=2, label="Actual max width")
    ax.plot(depths, [r["actual_mean_width"] for r in results],
            "^--", color="#50c878", linewidth=1.5, label="Actual mean width")
    ax.set_xlabel("Model Depth (hidden layers)")
    ax.set_ylabel("Output Interval Width")
    ax.set_title("Width vs Depth")
    ax.legend(fontsize=8)
    ax.set_yscale("log")
    ax.grid(alpha=0.3)

    # Panel 2: Recall and accuracy
    ax = axes[1]
    ax.plot(depths, [r["recall"] for r in results],
            "o-", color="#e94560", linewidth=2, label="Recall (errors caught)")
    ax.plot(depths, [r["test_accuracy"] for r in results],
            "s-", color="#4a90d9", linewidth=2, label="Test accuracy")
    ax.plot(depths, [r["filtered_accuracy"] for r in results],
            "^-", color="#50c878", linewidth=2, label="Filtered accuracy")
    ax.set_xlabel("Model Depth (hidden layers)")
    ax.set_ylabel("Rate")
    ax.set_title("Detection Quality vs Depth")
    ax.legend(fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.grid(alpha=0.3)

    # Panel 3: Bound tightness
    ax = axes[2]
    ax.bar(depths, [r["bound_tightness"] for r in results],
           color="#f5a623", alpha=0.8, width=1.2)
    ax.set_xlabel("Model Depth (hidden layers)")
    ax.set_ylabel("Tightness (predicted / actual)")
    ax.set_title("Coq Bound Tightness")
    ax.axhline(y=1, color="red", linestyle="--", alpha=0.5, label="Perfect tightness")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    plt.tight_layout()
    path = "benchmark_results/depth_study.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    run_depth_study()
