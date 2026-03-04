"""
MNIST demo: Regulus interval reliability analysis on handwritten digits.

Shows:
- 10-class classification (784->256->128->64->10)
- Interval width as uncertainty signal (higher = less reliable)
- Width bound verification vs Coq theorem
- Selective accuracy: reject most uncertain, improve accuracy

Usage:
    python -m regulus.demo.run_mnist
"""

from __future__ import annotations

import time
import numpy as np
import torch
import torch.nn as nn

from regulus.nn.interval_tensor import IntervalTensor
from regulus.nn.model import convert_model
from regulus.analysis.reliability import predict_max_width
from regulus.benchmark.metrics import compute_metrics


def train_mnist_model(X_train, y_train, model, epochs=20, lr=0.001):
    """Train MLP on MNIST."""
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    X_t = torch.FloatTensor(X_train)
    y_t = torch.LongTensor(y_train)

    batch_size = 512
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
    with torch.no_grad():
        logits = model(X_t[:5000])
        acc = (logits.argmax(dim=-1) == y_t[:5000]).float().mean().item()
    print(f"  Train accuracy (subset): {acc:.4f}")
    return model


def run_mnist_demo():
    print("=" * 60)
    print("REGULUS RELIABILITY ANALYSIS")
    print("Dataset: MNIST Handwritten Digits")
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

    print(f"  Train: {X_train.shape}, Test: {X_test.shape}")

    # Build and train model
    model = nn.Sequential(
        nn.Linear(784, 256), nn.ReLU(),
        nn.Linear(256, 128), nn.ReLU(),
        nn.Linear(128, 64), nn.ReLU(),
        nn.Linear(64, 10),
    )
    print(f"\nModel: MLP-4L (784->256->128->64->10)")
    print(f"Parameters: {sum(p.numel() for p in model.parameters()):,}")

    print("\nTraining...")
    model = train_mnist_model(X_train, y_train, model, epochs=20)

    # Base model test accuracy
    model.eval()
    X_test_t = torch.FloatTensor(X_test)
    y_test_t = torch.LongTensor(y_test)
    with torch.no_grad():
        logits = model(X_test_t)
        base_preds = logits.argmax(dim=-1).numpy()
        base_acc = (base_preds == y_test).mean()
    print(f"\nBase model test accuracy: {base_acc:.4f}")

    # Convert to interval model
    interval_model = convert_model(model)

    # Test on subset (full 10K is slow for per-sample IBP)
    n_test = 2000
    X_sub = X_test[:n_test]
    y_sub = y_test[:n_test]
    preds_sub = base_preds[:n_test]

    print(f"\nRunning interval analysis on {n_test} test samples...")

    for eps in [0.005, 0.01, 0.02]:
        print(f"\n{'='*60}")
        print(f"Input uncertainty: eps = {eps}")
        print(f"{'='*60}")

        # Width bound from Coq theorem
        bound_info = predict_max_width(interval_model, eps)
        print(f"Predicted max width (Coq): {bound_info['output_width_bound']:.4f}")
        print(f"Blowup factor: {bound_info['blowup_factor']:.2f}x")

        # Run interval propagation — collect width as uncertainty
        t0 = time.time()
        uncertainties = []

        for i in range(n_test):
            x_interval = IntervalTensor.from_uncertainty(X_sub[i], eps)
            output = interval_model(x_interval)
            uncertainties.append(output.max_width())

        uncertainties = np.array(uncertainties)
        t_inf = time.time() - t0

        # Use base model predictions + interval width as uncertainty
        is_wrong = preds_sub != y_sub
        n_wrong = int(is_wrong.sum())
        actual_max_w = float(uncertainties.max())
        actual_mean_w = float(uncertainties.mean())

        print(f"\nTotal predictions:     {n_test}")
        print(f"Base model accuracy:   {(~is_wrong).mean():.2%}")
        print(f"Actually wrong:        {n_wrong}")

        # Compute AUROC — can width distinguish errors?
        metrics = compute_metrics(preds_sub, uncertainties, y_sub, f"Regulus (eps={eps})")
        print(f"AUROC (width->error):  {metrics['auroc']:.4f}")
        print(f"AUPRC:                 {metrics['auprc']:.4f}")

        # Selective accuracy at various reject levels
        for pct in [5, 10, 20, 30]:
            key = f"selective_acc@{pct}%"
            if key in metrics:
                improvement = metrics[key] - metrics['accuracy']
                print(f"  Reject {pct:2d}%: accuracy = {metrics[key]:.4f} (+{improvement:.4f})")

        # Width analysis
        print(f"\nPredicted max width:   {bound_info['output_width_bound']:.4f} (Coq)")
        print(f"Actual max width:      {actual_max_w:.4f}")
        print(f"Actual mean width:     {actual_mean_w:.4f}")
        bound_tight = bound_info['output_width_bound'] / actual_max_w if actual_max_w > 0 else float('inf')
        print(f"Bound tightness:       {bound_tight:.1f}x")
        holds = actual_max_w <= bound_info['output_width_bound'] + 1e-10
        print(f"Bound holds:           {'YES' if holds else 'NO - VIOLATION'}")
        print(f"Inference time:        {t_inf:.2f}s ({t_inf/n_test*1000:.1f}ms/sample)")

        # Width distribution for correct vs wrong predictions
        _analyze_width_distribution(uncertainties, is_wrong)

        # Confusion analysis on high-uncertainty errors
        _analyze_confusion(preds_sub, y_sub, uncertainties)


def _analyze_width_distribution(uncertainties, is_wrong):
    """Compare uncertainty for correct vs wrong predictions."""
    correct_widths = uncertainties[~is_wrong]
    wrong_widths = uncertainties[is_wrong]

    print(f"\n  Width distribution:")
    print(f"    Correct predictions:  mean={correct_widths.mean():.4f}, "
          f"median={np.median(correct_widths):.4f}")
    if len(wrong_widths) > 0:
        print(f"    Wrong predictions:    mean={wrong_widths.mean():.4f}, "
              f"median={np.median(wrong_widths):.4f}")
        print(f"    Separation ratio:     {wrong_widths.mean()/correct_widths.mean():.2f}x")


def _analyze_confusion(preds, y_test, uncertainties):
    """Show which digit pairs have highest uncertainty when misclassified."""
    from collections import Counter

    confused_pairs = Counter()
    wrong_mask = preds != y_test
    wrong_idx = np.where(wrong_mask)[0]

    # Top uncertain errors
    wrong_unc = uncertainties[wrong_idx]
    top_k = min(10, len(wrong_idx))
    if top_k > 0:
        top_idx = wrong_idx[np.argsort(wrong_unc)[-top_k:]]

        for i in top_idx:
            pair = tuple(sorted([int(preds[i]), int(y_test[i])]))
            confused_pairs[pair] += 1

    if confused_pairs:
        print(f"\n  Most confused pairs (highest uncertainty errors):")
        for pair, count in confused_pairs.most_common(5):
            print(f"    {pair[0]} <-> {pair[1]}: {count} cases")


if __name__ == "__main__":
    run_mnist_demo()
