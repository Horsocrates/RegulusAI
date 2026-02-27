"""
Experiment: CROWN vs IBP Certification Comparison on MNIST.

Trains a model with IBP-aware training (best config from v3/v4),
then certifies with both naive IBP and CROWN to measure improvement.

Expected: CROWN gives tighter bounds → higher certified accuracy.
"""

import sys
import os
import time
import json
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
from regulus.nn.benchmark import train_mnist_model, certify_mnist


def main():
    print("=" * 80)
    print("REGULUS AI — CROWN vs IBP Certification Comparison")
    print("=" * 80)

    # -------------------------------------------------------
    # Step 1: Train model with best IBP config (from v3/v4)
    # -------------------------------------------------------
    print("\n[1/3] Training MNIST model with IBP-aware training...")
    print("  Config: cnn_bn, ibp=5.0, wreg=0.001, eps=flat 0.01, seed=42")

    t0 = time.perf_counter()
    model = train_mnist_model(
        epochs=10,
        architecture="cnn_bn",
        ibp_loss_weight=5.0,
        weight_reg=0.001,
        ibp_eps_start=0.01,
        ibp_eps_end=0.01,
        seed=42,
        verbose=True,
    )
    train_time = time.perf_counter() - t0
    print(f"  Training time: {train_time:.1f}s")

    # -------------------------------------------------------
    # Step 2: Certify with naive IBP
    # -------------------------------------------------------
    n_test = 200
    epsilon = 0.01

    print(f"\n[2/3] Certifying {n_test} images with NAIVE IBP (eps={epsilon})...")
    t1 = time.perf_counter()
    ibp_report = certify_mnist(
        model, epsilon=epsilon, n_test=n_test,
        strategy="naive", verbose=True, progress_interval=40,
    )
    ibp_time = time.perf_counter() - t1

    print(f"\n  IBP Results:")
    print(f"    Clean accuracy:     {ibp_report.correctly_classified}/{ibp_report.total_images} ({ibp_report.clean_accuracy:.1%})")
    print(f"    Certified robust:   {ibp_report.certified_robust}/{ibp_report.total_images} ({ibp_report.certified_accuracy:.1%})")
    print(f"    Avg output width:   {ibp_report.avg_output_max_width:.6f}")
    print(f"    Avg margin:         {ibp_report.avg_margin:.6f}")
    print(f"    Time:               {ibp_time:.1f}s")

    # -------------------------------------------------------
    # Step 3: Certify with CROWN
    # -------------------------------------------------------
    print(f"\n[3/3] Certifying {n_test} images with CROWN (eps={epsilon})...")
    t2 = time.perf_counter()
    crown_report = certify_mnist(
        model, epsilon=epsilon, n_test=n_test,
        strategy="crown", verbose=True, progress_interval=40,
    )
    crown_time = time.perf_counter() - t2

    print(f"\n  CROWN Results:")
    print(f"    Clean accuracy:     {crown_report.correctly_classified}/{crown_report.total_images} ({crown_report.clean_accuracy:.1%})")
    print(f"    Certified robust:   {crown_report.certified_robust}/{crown_report.total_images} ({crown_report.certified_accuracy:.1%})")
    print(f"    Avg output width:   {crown_report.avg_output_max_width:.6f}")
    print(f"    Avg margin:         {crown_report.avg_margin:.6f}")
    print(f"    Time:               {crown_time:.1f}s")

    # -------------------------------------------------------
    # Comparison
    # -------------------------------------------------------
    print("\n" + "=" * 80)
    print("COMPARISON: IBP vs CROWN")
    print("=" * 80)

    ibp_cert = ibp_report.certified_accuracy
    crown_cert = crown_report.certified_accuracy
    delta = crown_cert - ibp_cert

    print(f"  {'Metric':<25} {'IBP':>12} {'CROWN':>12} {'Delta':>12}")
    print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*12}")
    print(f"  {'Certified accuracy':<25} {ibp_cert:>11.1%} {crown_cert:>11.1%} {delta:>+11.1%}")
    print(f"  {'Clean accuracy':<25} {ibp_report.clean_accuracy:>11.1%} {crown_report.clean_accuracy:>11.1%}")
    print(f"  {'Avg output width':<25} {ibp_report.avg_output_max_width:>12.4f} {crown_report.avg_output_max_width:>12.4f} {crown_report.avg_output_max_width - ibp_report.avg_output_max_width:>+12.4f}")
    print(f"  {'Avg margin':<25} {ibp_report.avg_margin:>12.4f} {crown_report.avg_margin:>12.4f} {crown_report.avg_margin - ibp_report.avg_margin:>+12.4f}")
    print(f"  {'Verification time':<25} {ibp_time:>11.1f}s {crown_time:>11.1f}s {crown_time/ibp_time:>11.1f}x")

    # Per-image comparison
    ibp_only = 0  # Certified by IBP but not CROWN (should be 0)
    crown_only = 0  # Certified by CROWN but not IBP
    both_certified = 0
    neither = 0

    for ibp_img, crown_img in zip(ibp_report.per_image, crown_report.per_image):
        ibp_c = ibp_img.get("certified", False)
        crown_c = crown_img.get("certified", False)
        if ibp_c and crown_c:
            both_certified += 1
        elif ibp_c:
            ibp_only += 1
        elif crown_c:
            crown_only += 1
        else:
            neither += 1

    print(f"\n  Per-image breakdown:")
    print(f"    Both certified:   {both_certified}")
    print(f"    CROWN only:       {crown_only} (CROWN improvement)")
    print(f"    IBP only:         {ibp_only} (should be 0)")
    print(f"    Neither:          {neither}")

    # Save results
    results = {
        "ibp": {
            "certified": ibp_report.certified_robust,
            "total": ibp_report.total_images,
            "certified_accuracy": ibp_cert,
            "clean_accuracy": ibp_report.clean_accuracy,
            "avg_width": ibp_report.avg_output_max_width,
            "avg_margin": ibp_report.avg_margin,
            "time_s": ibp_time,
        },
        "crown": {
            "certified": crown_report.certified_robust,
            "total": crown_report.total_images,
            "certified_accuracy": crown_cert,
            "clean_accuracy": crown_report.clean_accuracy,
            "avg_width": crown_report.avg_output_max_width,
            "avg_margin": crown_report.avg_margin,
            "time_s": crown_time,
        },
        "improvement": {
            "certified_delta": delta,
            "width_reduction": 1.0 - (crown_report.avg_output_max_width / ibp_report.avg_output_max_width)
                if ibp_report.avg_output_max_width > 0 else 0,
            "crown_only": crown_only,
            "ibp_only": ibp_only,
        },
    }

    with open("scripts/crown_v1_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to scripts/crown_v1_results.json")


if __name__ == "__main__":
    main()
