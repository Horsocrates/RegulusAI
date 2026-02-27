"""
Experiment: v3 AvgPool architecture — the key CROWN innovation.

v3 replaces MaxPool with AvgPool. Since AvgPool is linear (fixed weights 1/k²),
CROWN can backward-propagate through it. This should give tighter bounds with
crown_depth="deep" compared to v1 (where MaxPool blocks CROWN backward).

Comparison matrix:
  v1 (MaxPool) + CROWN(fc)   — the golden baseline (93.2% ±2.6%)
  v3 (AvgPool) + IBP         — baseline IBP for v3
  v3 (AvgPool) + CROWN(fc)   — FC-only CROWN for v3
  v3 (AvgPool) + CROWN(deep) — full potential of v3 (should be best)

Training: same IBP-aware recipe as v1.
"""

import argparse
import json
import time
import sys
import os

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from regulus.nn.benchmark import train_mnist_model, certify_mnist


def run_v3_experiment(
    n_test: int = 200,
    epochs: int = 5,
    seeds: list[int] = [42, 123, 7],
    verbose: bool = True,
):
    """Train v3 (AvgPool) and certify with IBP, CROWN(fc), CROWN(deep)."""

    results = []

    for seed in seeds:
        print(f"\n{'='*60}")
        print(f"SEED {seed} — v3 AvgPool architecture")
        print(f"{'='*60}")

        # Train with IBP-aware recipe (same as v1)
        print(f"\n--- Training cnn_bn_v3 (AvgPool) seed={seed} ---")
        t0 = time.time()
        model = train_mnist_model(
            architecture="cnn_bn_v3",
            epochs=epochs,
            ibp_loss_weight=1.0,
            weight_reg=0.001,
            flat_eps=True,
            ibp_eps_end=0.01,
            lambda_ramp=True,
            lambda_ramp_fraction=0.5,
            lambda_warmup_fraction=0.1,
            checkpoint=True,
            checkpoint_n_samples=20,
            seed=seed,
            verbose=verbose,
        )
        train_time = time.time() - t0
        print(f"  Training time: {train_time:.1f}s")

        seed_result = {"seed": seed, "architecture": "cnn_bn_v3", "train_time": train_time}

        # Certify: IBP (naive)
        print(f"\n--- Certifying IBP (naive) ---")
        report_ibp = certify_mnist(
            model, epsilon=0.01, n_test=n_test,
            strategy="naive", architecture="cnn_bn_v3",
            progress_interval=50,
        )
        seed_result["ibp_certified"] = report_ibp.certified_accuracy
        seed_result["ibp_width"] = report_ibp.avg_output_max_width
        seed_result["ibp_margin"] = report_ibp.avg_margin
        seed_result["clean"] = report_ibp.clean_accuracy
        print(f"  IBP: {report_ibp.certified_accuracy*100:.1f}% certified, "
              f"width={report_ibp.avg_output_max_width:.4f}")

        # Certify: CROWN(fc)
        print(f"\n--- Certifying CROWN(fc) ---")
        report_crown_fc = certify_mnist(
            model, epsilon=0.01, n_test=n_test,
            strategy="crown", architecture="cnn_bn_v3",
            crown_depth="fc",
            progress_interval=50,
        )
        seed_result["crown_fc_certified"] = report_crown_fc.certified_accuracy
        seed_result["crown_fc_width"] = report_crown_fc.avg_output_max_width
        seed_result["crown_fc_margin"] = report_crown_fc.avg_margin
        print(f"  CROWN(fc): {report_crown_fc.certified_accuracy*100:.1f}% certified, "
              f"width={report_crown_fc.avg_output_max_width:.4f}")

        # Certify: CROWN(deep)
        print(f"\n--- Certifying CROWN(deep) ---")
        report_crown_deep = certify_mnist(
            model, epsilon=0.01, n_test=n_test,
            strategy="crown", architecture="cnn_bn_v3",
            crown_depth="deep",
            progress_interval=50,
        )
        seed_result["crown_deep_certified"] = report_crown_deep.certified_accuracy
        seed_result["crown_deep_width"] = report_crown_deep.avg_output_max_width
        seed_result["crown_deep_margin"] = report_crown_deep.avg_margin
        print(f"  CROWN(deep): {report_crown_deep.certified_accuracy*100:.1f}% certified, "
              f"width={report_crown_deep.avg_output_max_width:.4f}")

        # Width improvement analysis
        ibp_w = report_ibp.avg_output_max_width
        fc_w = report_crown_fc.avg_output_max_width
        deep_w = report_crown_deep.avg_output_max_width

        seed_result["fc_vs_ibp_improvement"] = 1.0 - (fc_w / ibp_w) if ibp_w > 0 else 0.0
        seed_result["deep_vs_fc_improvement"] = 1.0 - (deep_w / fc_w) if fc_w > 0 else 0.0
        seed_result["deep_vs_ibp_improvement"] = 1.0 - (deep_w / ibp_w) if ibp_w > 0 else 0.0

        print(f"\n  Width improvement:")
        print(f"    CROWN(fc) vs IBP:   {seed_result['fc_vs_ibp_improvement']*100:.1f}%")
        print(f"    CROWN(deep) vs fc:  {seed_result['deep_vs_fc_improvement']*100:.1f}%")
        print(f"    CROWN(deep) vs IBP: {seed_result['deep_vs_ibp_improvement']*100:.1f}%")

        results.append(seed_result)

    # Summary table
    print(f"\n{'='*80}")
    print("SUMMARY: v3 AvgPool — 3-seed stability")
    print(f"{'='*80}")
    print(f"{'Seed':>6} | {'Clean':>6} | {'IBP':>6} | {'CROWN(fc)':>10} | {'CROWN(deep)':>12} | "
          f"{'fc↑':>5} | {'deep↑':>6}")
    print("-" * 80)

    ibp_certs = []
    fc_certs = []
    deep_certs = []

    for r in results:
        ibp_certs.append(r["ibp_certified"])
        fc_certs.append(r["crown_fc_certified"])
        deep_certs.append(r["crown_deep_certified"])
        print(f"{r['seed']:>6} | {r['clean']*100:>5.1f}% | {r['ibp_certified']*100:>5.1f}% | "
              f"{r['crown_fc_certified']*100:>9.1f}% | {r['crown_deep_certified']*100:>11.1f}% | "
              f"{r['fc_vs_ibp_improvement']*100:>4.1f}% | {r['deep_vs_ibp_improvement']*100:>5.1f}%")

    print("-" * 80)
    print(f"{'Mean':>6} | {'':>6} | {np.mean(ibp_certs)*100:>5.1f}% | "
          f"{np.mean(fc_certs)*100:>9.1f}% | {np.mean(deep_certs)*100:>11.1f}%")
    print(f"{'Std':>6} | {'':>6} | {np.std(ibp_certs)*100:>5.1f}% | "
          f"{np.std(fc_certs)*100:>9.1f}% | {np.std(deep_certs)*100:>11.1f}%")

    # v1 reference for comparison
    print(f"\nv1 (MaxPool) reference: IBP 87.0% ±3.1%, CROWN(fc) 93.2% ±2.6%")
    print(f"  (CROWN(deep) = CROWN(fc) for v1 due to MaxPool blocking)")

    # Save results
    output_path = os.path.join(os.path.dirname(__file__), "v3_avgpool_results.json")
    with open(output_path, "w") as f:
        json.dump({"v3_avgpool": results}, f, indent=2)
    print(f"\nResults saved to: {output_path}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="v3 AvgPool experiment")
    parser.add_argument("--n-test", type=int, default=200,
                        help="Number of test images (default: 200)")
    parser.add_argument("--epochs", type=int, default=5,
                        help="Training epochs (default: 5)")
    parser.add_argument("--seeds", type=str, default="42,123,7",
                        help="Comma-separated seeds")
    args = parser.parse_args()

    seeds = [int(s) for s in args.seeds.split(",")]
    run_v3_experiment(
        n_test=args.n_test,
        epochs=args.epochs,
        seeds=seeds,
    )
