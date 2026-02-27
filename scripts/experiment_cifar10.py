"""
Experiment: CIFAR-10 IBP + CROWN certification.

Scales the Regulus verification pipeline from MNIST (1x28x28) to CIFAR-10 (3x32x32).
Uses make_cifar_cnn_bn() architecture: 4 conv layers + 2 MaxPool + 2 FC.

Comparison:
  cifar_cnn_bn + IBP (naive)    -- baseline IBP certification
  cifar_cnn_bn + CROWN(fc)      -- CROWN on FC layers only

CIFAR-10 is much harder than MNIST for certification:
  - 3x larger input (3072 vs 784 pixels)
  - More complex patterns -> wider intervals
  - Epsilon: 0.01 in tensor space ~ 0.64/255 in pixel space (small)

Reference MNIST results (1000 images x 3 seeds):
  IBP:   81.8% +/- 2.6%
  CROWN: 91.5% +/- 1.4%
"""

import argparse
import json
import time
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from regulus.nn.benchmark import train_cifar_model, certify_cifar


def run_cifar_experiment(
    n_test: int = 200,
    epochs: int = 10,
    seeds: list[int] | None = None,
    epsilon: float = 0.01,
    verbose: bool = True,
):
    """Train cifar_cnn_bn and certify with IBP + CROWN(fc)."""

    if seeds is None:
        seeds = [42, 123, 7]

    print("=" * 70)
    print(f"CIFAR-10 EXPERIMENT: cifar_cnn_bn -- {n_test} images x {len(seeds)} seeds")
    print(f"  epsilon={epsilon} (tensor space)")
    print("=" * 70)

    results = []

    for seed in seeds:
        print(f"\n{'-'*60}")
        print(f"  Seed {seed}")
        print(f"{'-'*60}")

        # Train with IBP-aware recipe
        t0 = time.perf_counter()
        print(f"  Training cifar_cnn_bn (ibp=5.0, wreg=0.001, seed={seed})...")
        model = train_cifar_model(
            architecture="cifar_cnn_bn",
            epochs=epochs,
            ibp_loss_weight=5.0,
            weight_reg=0.001,
            flat_eps=True,
            ibp_eps_end=epsilon,
            lambda_ramp=True,
            lambda_ramp_fraction=0.5,
            lambda_warmup_fraction=0.1,
            checkpoint=True,
            checkpoint_n_samples=20,
            seed=seed,
            verbose=verbose,
        )
        train_time = time.perf_counter() - t0
        print(f"  Training time: {train_time:.1f}s")

        seed_result = {"seed": seed, "architecture": "cifar_cnn_bn", "train_time": round(train_time, 1)}

        # IBP certification
        t1 = time.perf_counter()
        print(f"\n  Certifying with IBP ({n_test} images)...")
        report_ibp = certify_cifar(
            model, epsilon=epsilon, n_test=n_test,
            strategy="naive", architecture="cifar_cnn_bn",
            verbose=verbose, progress_interval=50,
        )
        ibp_time = time.perf_counter() - t1

        seed_result["clean"] = report_ibp.clean_accuracy
        seed_result["ibp_certified"] = report_ibp.certified_accuracy
        seed_result["ibp_width"] = report_ibp.avg_output_max_width
        seed_result["ibp_margin"] = report_ibp.avg_margin
        seed_result["ibp_time"] = round(ibp_time, 1)

        print(f"  IBP: {report_ibp.certified_accuracy*100:.1f}% certified, "
              f"width={report_ibp.avg_output_max_width:.4f}, {ibp_time:.1f}s")

        # CROWN(fc) certification
        t2 = time.perf_counter()
        print(f"\n  Certifying with CROWN(fc) ({n_test} images)...")
        report_crown = certify_cifar(
            model, epsilon=epsilon, n_test=n_test,
            strategy="crown", architecture="cifar_cnn_bn",
            crown_depth="fc",
            verbose=verbose, progress_interval=50,
        )
        crown_time = time.perf_counter() - t2

        seed_result["crown_certified"] = report_crown.certified_accuracy
        seed_result["crown_width"] = report_crown.avg_output_max_width
        seed_result["crown_margin"] = report_crown.avg_margin
        seed_result["crown_time"] = round(crown_time, 1)

        # Improvement metrics
        if report_ibp.avg_output_max_width > 0:
            seed_result["width_reduction_pct"] = round(
                (1.0 - report_crown.avg_output_max_width / report_ibp.avg_output_max_width) * 100, 1
            )
        else:
            seed_result["width_reduction_pct"] = 0.0

        seed_result["cert_improvement_pct"] = round(
            (report_crown.certified_accuracy - report_ibp.certified_accuracy) * 100, 1
        )

        print(f"  CROWN(fc): {report_crown.certified_accuracy*100:.1f}% certified, "
              f"width={report_crown.avg_output_max_width:.4f}, {crown_time:.1f}s")
        print(f"  CROWN D: +{seed_result['cert_improvement_pct']}% cert, "
              f"-{seed_result['width_reduction_pct']}% width")

        results.append(seed_result)

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY: CIFAR-10 cifar_cnn_bn")
    print(f"{'='*70}")
    print(f"  {'Seed':>6} {'Clean':>8} {'IBP':>8} {'CROWN':>8} "
          f"{'IBP_w':>10} {'CROWN_w':>10} {'Dcert':>8} {'Dwidth':>8}")
    print(f"  {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*10} {'-'*10} {'-'*8} {'-'*8}")

    ibp_certs = []
    crown_certs = []
    cleans = []

    for r in results:
        ibp_certs.append(r["ibp_certified"])
        crown_certs.append(r["crown_certified"])
        cleans.append(r["clean"])
        print(f"  {r['seed']:>6} {r['clean']*100:>7.1f}% {r['ibp_certified']*100:>7.1f}% "
              f"{r['crown_certified']*100:>7.1f}% {r['ibp_width']:>10.4f} {r['crown_width']:>10.4f} "
              f"{r['cert_improvement_pct']:>+7.1f}% {r['width_reduction_pct']:>7.1f}%")

    print(f"\n  Mean clean: {np.mean(cleans)*100:.1f}%")
    print(f"  Mean IBP:   {np.mean(ibp_certs)*100:.1f}% +/- {np.std(ibp_certs)*100:.1f}%")
    print(f"  Mean CROWN: {np.mean(crown_certs)*100:.1f}% +/- {np.std(crown_certs)*100:.1f}%")
    print(f"\n  MNIST reference: IBP 81.8% +/- 2.6%, CROWN 91.5% +/- 1.4%")

    # Save
    output = {
        "config": {
            "dataset": "cifar10",
            "architecture": "cifar_cnn_bn",
            "epsilon": epsilon,
            "epochs": epochs,
            "n_test": n_test,
            "seeds": seeds,
            "ibp_loss_weight": 5.0,
            "weight_reg": 0.001,
        },
        "per_seed": results,
        "aggregate": {
            "clean_mean": round(float(np.mean(cleans)), 4),
            "ibp_certified_mean": round(float(np.mean(ibp_certs)), 4),
            "ibp_certified_std": round(float(np.std(ibp_certs)), 4),
            "crown_certified_mean": round(float(np.mean(crown_certs)), 4),
            "crown_certified_std": round(float(np.std(crown_certs)), 4),
        },
    }

    output_path = os.path.join(os.path.dirname(__file__), "cifar10_results.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved to: {output_path}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CIFAR-10 IBP + CROWN experiment")
    parser.add_argument("--n-test", type=int, default=200,
                        help="Number of test images (default: 200)")
    parser.add_argument("--epochs", type=int, default=10,
                        help="Training epochs (default: 10)")
    parser.add_argument("--epsilon", type=float, default=0.01,
                        help="Epsilon in tensor space (default: 0.01)")
    parser.add_argument("--seeds", type=str, default="42,123,7",
                        help="Comma-separated seeds")
    args = parser.parse_args()

    seeds = [int(s) for s in args.seeds.split(",")]
    run_cifar_experiment(
        n_test=args.n_test,
        epochs=args.epochs,
        epsilon=args.epsilon,
        seeds=seeds,
    )
