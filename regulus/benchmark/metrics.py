"""
Unified metrics for uncertainty quantification benchmark.

Threshold-independent: AUROC, AUPRC
Calibration: ECE (Expected Calibration Error)
Selective: accuracy after rejecting top-K% uncertain
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score


def compute_metrics(
    predictions: np.ndarray,
    uncertainties: np.ndarray,
    true_labels: np.ndarray,
    method_name: str,
    probs: np.ndarray | None = None,
) -> dict:
    """Compute all uncertainty-quality metrics.

    Args:
        predictions: predicted class labels (N,)
        uncertainties: continuous uncertainty scores (N,) — higher = more uncertain
        true_labels: ground truth labels (N,)
        method_name: display name
        probs: optional class probabilities (N, C) for ECE

    Returns:
        dict with accuracy, auroc, auprc, ece, selective_acc@K%
    """
    is_wrong = (predictions != true_labels).astype(float)
    accuracy = 1.0 - is_wrong.mean()

    # --- AUROC / AUPRC ---
    # Can uncertainty distinguish wrong from correct?
    n_wrong = int(is_wrong.sum())
    n_correct = len(is_wrong) - n_wrong
    if n_wrong > 0 and n_correct > 0:
        auroc = roc_auc_score(is_wrong, uncertainties)
        auprc = average_precision_score(is_wrong, uncertainties)
    else:
        auroc = float("nan")
        auprc = float("nan")

    # --- ECE (Expected Calibration Error) ---
    ece = _compute_ece(predictions, true_labels, uncertainties, probs)

    # --- Selective Accuracy ---
    # Reject top-K% most uncertain, measure accuracy on the rest
    selective = {}
    for reject_pct in [5, 10, 15, 20, 30]:
        threshold = np.percentile(uncertainties, 100 - reject_pct)
        keep = uncertainties <= threshold
        if keep.sum() > 0:
            sel_acc = float((predictions[keep] == true_labels[keep]).mean())
        else:
            sel_acc = float("nan")
        selective[f"selective_acc@{reject_pct}%"] = sel_acc

    return {
        "method": method_name,
        "accuracy": float(accuracy),
        "auroc": float(auroc),
        "auprc": float(auprc),
        "ece": float(ece),
        **selective,
    }


def _compute_ece(
    predictions: np.ndarray,
    true_labels: np.ndarray,
    uncertainties: np.ndarray,
    probs: np.ndarray | None = None,
    n_bins: int = 15,
) -> float:
    """Expected Calibration Error.

    Uses max class probability as confidence if probs available,
    otherwise uses (1 - uncertainty) as proxy.
    """
    if probs is not None and probs.ndim == 2:
        confidences = probs.max(axis=1)
    else:
        # Normalize uncertainty to [0, 1] for ECE
        u_min, u_max = uncertainties.min(), uncertainties.max()
        if u_max > u_min:
            norm_unc = (uncertainties - u_min) / (u_max - u_min)
        else:
            norm_unc = np.zeros_like(uncertainties)
        confidences = 1.0 - norm_unc

    correct = (predictions == true_labels).astype(float)
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0

    for i in range(n_bins):
        lo, hi = bin_boundaries[i], bin_boundaries[i + 1]
        if i == 0:
            mask = (confidences >= lo) & (confidences <= hi)
        else:
            mask = (confidences > lo) & (confidences <= hi)

        n_in_bin = mask.sum()
        if n_in_bin > 0:
            bin_acc = correct[mask].mean()
            bin_conf = confidences[mask].mean()
            ece += (n_in_bin / len(confidences)) * abs(bin_acc - bin_conf)

    return float(ece)


def compute_coverage_curve(
    predictions: np.ndarray,
    uncertainties: np.ndarray,
    true_labels: np.ndarray,
    n_points: int = 50,
) -> dict:
    """Risk-coverage curve data.

    At each coverage level, compute accuracy of retained predictions.
    Returns arrays for plotting.
    """
    sorted_idx = np.argsort(uncertainties)
    sorted_correct = (predictions[sorted_idx] == true_labels[sorted_idx]).astype(float)

    coverages = np.linspace(0.1, 1.0, n_points)
    accuracies = []

    for cov in coverages:
        n_keep = max(1, int(cov * len(sorted_correct)))
        acc = sorted_correct[:n_keep].mean()
        accuracies.append(float(acc))

    return {
        "coverages": coverages.tolist(),
        "accuracies": accuracies,
    }
