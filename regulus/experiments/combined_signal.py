"""
Combined Signal Experiment: RA-Margin x TempScaling fusion.

Tests whether combining structural (interval geometry) and statistical
(calibrated softmax) uncertainty signals improves error detection.

4 combination methods: Product, WeightedAvg (alpha sweep), Max, Learned.

Usage:
    .venv313\\Scripts\\python.exe -m regulus.experiments.combined_signal
    .venv313\\Scripts\\python.exe -m regulus.experiments.combined_signal --quick
"""

from __future__ import annotations

import os
import sys
import time
import numpy as np
import torch
import torch.nn as nn
from sklearn.model_selection import train_test_split as sk_split

from regulus.benchmark.datasets import load_dataset
from regulus.benchmark.metrics import compute_metrics
from regulus.benchmark.methods import (
    ReanchoredRegulusMethod,
    TempScalingMethod,
)
from regulus.experiments.full_benchmark_v2 import _get_config, train_model

OUTPUT_DIR = "benchmark_results/combined_signal"
ALPHA_GRID = [round(a * 0.1, 1) for a in range(11)]  # 0.0, 0.1, ..., 1.0


# ============================================================
# Normalization helper
# ============================================================

def _normalize_01(arr: np.ndarray) -> np.ndarray:
    """Min-max normalize to [0, 1]. If constant, return zeros."""
    lo, hi = float(arr.min()), float(arr.max())
    if hi - lo < 1e-15:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)


# ============================================================
# Combination methods
# ============================================================

def combine_product(u_margin: np.ndarray, u_temp: np.ndarray) -> np.ndarray:
    """Product: both signals must agree sample is uncertain."""
    return u_margin * u_temp


def combine_weighted(u_margin: np.ndarray, u_temp: np.ndarray,
                     alpha: float) -> np.ndarray:
    """Weighted average: alpha=1 is pure RA-Margin, alpha=0 is pure TempScaling."""
    return alpha * u_margin + (1.0 - alpha) * u_temp


def combine_max(u_margin: np.ndarray, u_temp: np.ndarray) -> np.ndarray:
    """Max: conservative, either signal can flag uncertainty."""
    return np.maximum(u_margin, u_temp)


def combine_learned(u_margin_train: np.ndarray, u_temp_train: np.ndarray,
                    is_wrong_train: np.ndarray,
                    u_margin_test: np.ndarray, u_temp_test: np.ndarray
                    ) -> np.ndarray:
    """Train LogisticRegression on val features, predict P(wrong) on test."""
    from sklearn.linear_model import LogisticRegression

    X_train_lr = np.column_stack([u_margin_train, u_temp_train])
    X_test_lr = np.column_stack([u_margin_test, u_temp_test])
    clf = LogisticRegression(random_state=42, max_iter=1000)
    clf.fit(X_train_lr, is_wrong_train.astype(int))
    return clf.predict_proba(X_test_lr)[:, 1]


# ============================================================
# Per-dataset runner
# ============================================================

def run_dataset(ds_name: str, X_train_full: np.ndarray, y_train_full: np.ndarray,
                X_test: np.ndarray, y_test: np.ndarray,
                config: dict, quick: bool = False) -> list[dict]:
    """Run combined signal experiment on one dataset."""
    results = []
    EPS = config["input_eps"]

    # --- Validation split: 20% of train ---
    X_train, X_val, y_train, y_val = sk_split(
        X_train_full, y_train_full,
        test_size=0.2, random_state=42, stratify=y_train_full,
    )
    print(f"  Train: {X_train.shape}, Val: {X_val.shape}, Test: {X_test.shape}")

    # --- Train base model on train subset ---
    torch.manual_seed(42)
    base_model = config["model_fn"]()
    base_model = train_model(
        base_model, X_train, y_train,
        epochs=config["epochs"], lr=config["lr"],
        batch_size=config["batch_size"],
    )

    # --- Base predictions on test ---
    base_model.eval()
    with torch.no_grad():
        test_logits = base_model(torch.FloatTensor(X_test))
        preds = test_logits.argmax(dim=-1).numpy()
        acc = float((preds == y_test).mean())
    print(f"  Accuracy: {acc:.4f}")

    # --- RA-Margin uncertainty on test ---
    print("  Computing RA-Margin uncertainty...")
    t0 = time.time()
    ra = ReanchoredRegulusMethod(
        base_model, input_eps=EPS, block_size=1,
        reanchor_eps=0.01, strategy="midpoint", signal="margin",
    )
    _, _, u_margin_raw = ra.predict_with_uncertainty(X_test)
    t_margin = time.time() - t0
    print(f"    RA-Margin done in {t_margin:.1f}s")

    # --- TempScaling uncertainty on test ---
    print("  Computing TempScaling uncertainty...")
    t0 = time.time()
    ts = TempScalingMethod(base_model)
    T = ts.calibrate(X_val, y_val)
    _, _, u_temp_raw = ts.predict_with_uncertainty(X_test)
    t_temp = time.time() - t0
    print(f"    TempScaling done in {t_temp:.1f}s (T={T:.4f})")

    # --- Individual baselines (raw signals) ---
    m_margin = compute_metrics(preds, u_margin_raw, y_test, "RA-Margin")
    m_temp = compute_metrics(preds, u_temp_raw, y_test, "TempScaling")
    results.append({**m_margin, "dataset": ds_name, "combo": "RA-Margin",
                    "alpha": None, "time": t_margin})
    results.append({**m_temp, "dataset": ds_name, "combo": "TempScaling",
                    "alpha": None, "time": t_temp, "temperature": T})
    print(f"    RA-Margin AUROC:   {m_margin.get('auroc', 0):.4f}")
    print(f"    TempScaling AUROC: {m_temp.get('auroc', 0):.4f}")

    # --- Normalize for combination ---
    u_margin = _normalize_01(u_margin_raw)
    u_temp = _normalize_01(u_temp_raw)

    # --- Method 1: Product ---
    u_prod = combine_product(u_margin, u_temp)
    m = compute_metrics(preds, u_prod, y_test, "Product")
    results.append({**m, "dataset": ds_name, "combo": "Product", "alpha": None})
    print(f"    Product AUROC:     {m.get('auroc', 0):.4f}")

    # --- Method 2: Weighted Average (alpha sweep) ---
    best_alpha, best_auroc_wavg = 0.5, 0.0
    for alpha in ALPHA_GRID:
        u_wavg = combine_weighted(u_margin, u_temp, alpha)
        m = compute_metrics(preds, u_wavg, y_test,
                            f"WeightedAvg(a={alpha:.1f})")
        results.append({**m, "dataset": ds_name, "combo": "WeightedAvg",
                        "alpha": alpha})
        auroc_val = m.get("auroc", 0)
        if not np.isnan(auroc_val) and auroc_val > best_auroc_wavg:
            best_auroc_wavg = auroc_val
            best_alpha = alpha
    print(f"    WeightedAvg best:  alpha={best_alpha:.1f} -> AUROC={best_auroc_wavg:.4f}")

    # --- Method 3: Max ---
    u_max = combine_max(u_margin, u_temp)
    m = compute_metrics(preds, u_max, y_test, "Max")
    results.append({**m, "dataset": ds_name, "combo": "Max", "alpha": None})
    print(f"    Max AUROC:         {m.get('auroc', 0):.4f}")

    # --- Method 4: Learned (LogisticRegression) ---
    # Need val-set uncertainties for training the combiner
    print("  Computing val-set uncertainties for learned combiner...")
    _, _, u_margin_val_raw = ra.predict_with_uncertainty(X_val.astype(np.float32))
    _, _, u_temp_val_raw = ts.predict_with_uncertainty(X_val.astype(np.float32))

    # Val predictions for is_wrong labels
    with torch.no_grad():
        val_preds = base_model(torch.FloatTensor(X_val)).argmax(dim=-1).numpy()
    is_wrong_val = (val_preds != y_val).astype(float)

    u_margin_val = _normalize_01(u_margin_val_raw)
    u_temp_val = _normalize_01(u_temp_val_raw)

    # Guard: need both classes in is_wrong_val for LogisticRegression
    n_wrong = int(is_wrong_val.sum())
    n_right = len(is_wrong_val) - n_wrong
    if n_wrong >= 2 and n_right >= 2:
        try:
            u_learned = combine_learned(
                u_margin_val, u_temp_val, is_wrong_val,
                u_margin, u_temp,
            )
            m = compute_metrics(preds, u_learned, y_test, "Learned(LR)")
            results.append({**m, "dataset": ds_name, "combo": "Learned",
                            "alpha": None})
            print(f"    Learned AUROC:     {m.get('auroc', 0):.4f}")
        except Exception as e:
            print(f"    Learned SKIPPED: {e}")
    else:
        print(f"    Learned SKIPPED: val set has {n_wrong} errors, "
              f"{n_right} correct (need >=2 of each)")

    return results


# ============================================================
# Main
# ============================================================

def run_combined_signal(quick: bool = False) -> list[dict]:
    print("=" * 70)
    print("COMBINED SIGNAL EXPERIMENT: RA-Margin x TempScaling")
    print("=" * 70)

    all_results = []

    for ds_name in ["breast_cancer", "credit", "mnist"]:
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
        print(f"  Input eps: {config['input_eps']}")
        print(f"{'='*60}")

        results = run_dataset(
            ds_name, X_train, y_train, X_test, y_test, config, quick=quick)
        all_results.extend(results)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    _print_summary(all_results)
    _save_csv(all_results)

    return all_results


def _print_summary(results: list[dict]) -> None:
    """Print formatted console summary."""
    print("\n" + "=" * 70)
    print("COMBINED SIGNAL: RESULTS SUMMARY")
    print("=" * 70)

    for ds_name in ["breast_cancer", "credit", "mnist"]:
        # Show non-alpha-sweep results
        ds_results = [r for r in results
                      if r["dataset"] == ds_name and r.get("alpha") is None]
        if not ds_results:
            continue

        print(f"\n{ds_name.upper().replace('_', ' ')}:")
        print(f"  {'Method':<30s} {'AUROC':>7s} {'AUPRC':>7s}")
        print("  " + "-" * 46)

        for m in sorted(ds_results, key=lambda x: -x.get("auroc", 0)):
            auroc = m.get("auroc", float("nan"))
            auprc = m.get("auprc", float("nan"))
            auroc_s = f"{auroc:.4f}" if not np.isnan(auroc) else "  N/A"
            auprc_s = f"{auprc:.4f}" if not np.isnan(auprc) else "  N/A"
            print(f"  {m['method']:<30s} {auroc_s:>7s} {auprc_s:>7s}")

    # Alpha sweep summary
    print("\n" + "-" * 50)
    print("ALPHA SWEEP (best alpha per dataset):")
    for ds_name in ["breast_cancer", "credit", "mnist"]:
        wavg = [r for r in results
                if r["dataset"] == ds_name and r.get("combo") == "WeightedAvg"]
        if wavg:
            best = max(wavg, key=lambda r: r.get("auroc", 0))
            print(f"  {ds_name:<20s}: alpha={best['alpha']:.1f}, "
                  f"AUROC={best['auroc']:.4f}")

    print("=" * 70)


def _save_csv(results: list[dict]) -> None:
    """Save all results to CSV."""
    import pandas as pd

    rows = []
    for r in results:
        row = {k: v for k, v in r.items() if not isinstance(v, (list, dict))}
        rows.append(row)

    df = pd.DataFrame(rows)
    path = os.path.join(OUTPUT_DIR, "combined_signal.csv")
    df.to_csv(path, index=False)
    print(f"\nSaved: {path}")


def main():
    quick = "--quick" in sys.argv
    run_combined_signal(quick=quick)


if __name__ == "__main__":
    main()
