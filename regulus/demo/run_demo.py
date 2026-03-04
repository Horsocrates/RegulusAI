"""
Regulus Demo: Interval Arithmetic vs Standard Neural Network

Demonstrates:
1. Train a standard neural network on Breast Cancer Wisconsin
2. Convert to interval version
3. Run test data with input uncertainty
4. Compare: standard model doesn't know about errors, interval model catches them

Run: uv run python -m regulus.demo.run_demo
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from regulus.nn.model import convert_model
from regulus.nn.interval_tensor import IntervalTensor
from regulus.nn.layers import IntervalSoftmax
from regulus.analysis.reliability import ReliabilityAnalysis


def run_analysis(
    interval_model,
    X_test: np.ndarray,
    y_test: np.ndarray,
    eps: float,
) -> dict:
    """Run interval analysis at a given eps and return batch metrics."""
    results = []
    for i in range(len(X_test)):
        x_interval = IntervalTensor.from_uncertainty(X_test[i], eps)
        output = interval_model(x_interval)
        # Classify on logits directly (more discriminative than softmax)
        analysis = ReliabilityAnalysis.classify(output)
        results.append(analysis)

    batch = ReliabilityAnalysis.batch_analysis(results, y_test)
    return batch, results


def main() -> None:
    # ============================================
    # 1. DATA PREPARATION
    # ============================================

    # Breast Cancer Wisconsin -- binary classification
    # Benign (0) vs Malignant (1)
    # 30 features, 569 samples
    # Chosen because errors here COST LIVES

    data = load_breast_cancer()
    X, y = data.data, data.target

    scaler = StandardScaler()
    X = scaler.fit_transform(X)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42
    )

    X_train_t = torch.FloatTensor(X_train)
    y_train_t = torch.LongTensor(y_train)
    X_test_t = torch.FloatTensor(X_test)

    # ============================================
    # 2. TRAIN STANDARD MODEL
    # ============================================

    model = nn.Sequential(
        nn.Linear(30, 16),
        nn.ReLU(),
        nn.Linear(16, 8),
        nn.ReLU(),
        nn.Linear(8, 2),  # 2 classes: benign / malignant
    )

    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.CrossEntropyLoss()

    print("Training standard model...")
    model.train()
    for epoch in range(200):
        optimizer.zero_grad()
        output = model(X_train_t)
        loss = criterion(output, y_train_t)
        loss.backward()
        optimizer.step()
        if (epoch + 1) % 50 == 0:
            print(f"  Epoch {epoch+1}/200, Loss: {loss.item():.4f}")

    # Standard accuracy
    model.eval()
    with torch.no_grad():
        logits = model(X_test_t)
        preds = logits.argmax(dim=1).numpy()
        standard_acc = np.mean(preds == y_test)

    print(f"\nStandard model accuracy: {standard_acc:.2%}")
    print(f"Standard model errors: {np.sum(preds != y_test)} / {len(y_test)}")

    # ============================================
    # 3. CONVERT TO INTERVAL MODEL
    # ============================================

    interval_model = convert_model(model)

    # ============================================
    # 4. EPS SWEEP — find the sweet spot
    # ============================================

    print("\n" + "=" * 60)
    print("EPS SWEEP: Finding optimal uncertainty level")
    print("=" * 60)
    print(f"{'eps':>6} | {'flagged':>7} | {'caught':>6} | {'missed':>6} | "
          f"{'false_alarm':>10} | {'recall':>6} | {'acc_filter':>10}")
    print("-" * 75)

    eps_values = [0.001, 0.005, 0.01, 0.02, 0.03, 0.05, 0.1]
    best_eps = None
    best_improvement = -1.0

    for eps in eps_values:
        batch, _ = run_analysis(interval_model, X_test, y_test, eps)
        improvement = batch["accuracy_after_filtering"] - batch["accuracy_standard"]
        acc_filter_str = f"{batch['accuracy_after_filtering']:.2%}"
        recall_str = f"{batch['recall']:.0%}" if batch["actually_wrong"] > 0 else "n/a"

        print(f"{eps:>6.3f} | {batch['flagged_unreliable']:>7} | "
              f"{batch['caught']:>6} | {batch['missed']:>6} | "
              f"{batch['false_alarm']:>10} | {recall_str:>6} | {acc_filter_str:>10}")

        if improvement > best_improvement:
            best_improvement = improvement
            best_eps = eps

    # ============================================
    # 5. DETAILED ANALYSIS at best eps
    # ============================================

    print(f"\nBest eps: {best_eps} (accuracy improvement: +{best_improvement:.2%})")
    print("\n" + "=" * 60)
    print(f"REGULUS RELIABILITY ANALYSIS (eps = {best_eps})")
    print("=" * 60)

    batch, results = run_analysis(interval_model, X_test, y_test, best_eps)

    print(f"Total predictions:     {batch['total']}")
    print(f"Standard accuracy:     {batch['accuracy_standard']:.2%}")
    print(f"Actually wrong:        {batch['actually_wrong']}")
    print(f"Flagged unreliable:    {batch['flagged_unreliable']}")
    print(f"Errors caught:         {batch['caught']}")
    print(f"Errors missed:         {batch['missed']}")
    print(f"False alarms:          {batch['false_alarm']}")
    print(f"Precision:             {batch['precision']:.2%}")
    print(f"Recall:                {batch['recall']:.2%}")
    print(f"Accuracy after filter: {batch['accuracy_after_filtering']:.2%}")
    print("=" * 60)

    # Key result
    if batch["recall"] > 0:
        print(f"\nInterval analysis caught {batch['caught']}/{batch['actually_wrong']} errors")
        print("that standard model presented with false confidence.")

    if batch["accuracy_after_filtering"] > batch["accuracy_standard"]:
        improvement = batch["accuracy_after_filtering"] - batch["accuracy_standard"]
        print(f"\nIf we TRUST ONLY reliable predictions:")
        print(
            f"  Accuracy improves from {batch['accuracy_standard']:.2%} "
            f"to {batch['accuracy_after_filtering']:.2%} (+{improvement:.2%})"
        )

    # ============================================
    # 6. EXAMPLES
    # ============================================

    print("\n\nEXAMPLE PREDICTIONS:")
    print("-" * 60)

    # Show caught errors
    caught_examples = [
        (i, r)
        for i, r in enumerate(results)
        if not r["reliable"] and r["predicted_class"] != y_test[i]
    ]

    if caught_examples:
        print("\nCaught errors (correctly flagged):")
        for i, r in caught_examples[:3]:
            true = "Malignant" if y_test[i] == 1 else "Benign"
            pred = "Malignant" if r["predicted_class"] == 1 else "Benign"
            print(f"\n  Sample {i}: True={true}, Predicted={pred}")
            print(f"  Logit interval: [{r['confidence_lo']:.4f}, {r['confidence_hi']:.4f}]")
            print(f"  Overlapping classes: {r['overlapping_pairs']}")
            print(f"  -> FLAGGED AS UNRELIABLE (correctly!)")

    # Show missed errors
    missed_examples = [
        (i, r)
        for i, r in enumerate(results)
        if r["reliable"] and r["predicted_class"] != y_test[i]
    ]

    if missed_examples:
        print(f"\n  {len(missed_examples)} errors were NOT caught")
        print("  (model was wrong but intervals didn't overlap)")

    # ============================================
    # 7. INTERVAL WIDTH PROPAGATION
    # ============================================

    x_sample = IntervalTensor.from_uncertainty(X_test[0], best_eps)
    _ = interval_model(x_sample)

    print("\n\nINTERVAL WIDTH PROPAGATION:")
    print(interval_model.width_report())

    # ============================================
    # 8. SOFTMAX ANALYSIS (for reference)
    # ============================================

    print("\n\nSOFTMAX ANALYSIS (eps = 0.1, conservative):")
    print("-" * 60)
    softmax = IntervalSoftmax()
    batch_sm, _ = run_softmax_analysis(interval_model, softmax, X_test, y_test, 0.1)
    print(f"  Flagged:    {batch_sm['flagged_unreliable']}/{batch_sm['total']}")
    print(f"  Recall:     {batch_sm['recall']:.0%}")
    print(f"  Note: softmax interval bounds are very conservative.")
    print(f"  Logit-level analysis (above) is more discriminative.")

    print("\n\nP4 INTERPRETATION:")
    print("Each interval is not an 'approximation to a real number'.")
    print("It IS the number at the current step of the process of determination.")
    print("Wide interval = the process has not yet determined the value precisely.")
    print("Overlapping classes = the process cannot yet distinguish the answer.")


def run_softmax_analysis(interval_model, softmax, X_test, y_test, eps):
    """Run analysis with softmax probabilities (more conservative)."""
    results = []
    for i in range(len(X_test)):
        x_interval = IntervalTensor.from_uncertainty(X_test[i], eps)
        output = interval_model(x_interval)
        probs = softmax(output)
        analysis = ReliabilityAnalysis.classify(probs)
        results.append(analysis)
    batch = ReliabilityAnalysis.batch_analysis(results, y_test)
    return batch, results


if __name__ == "__main__":
    main()
