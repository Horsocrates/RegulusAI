"""Final benchmark: 1000 images x 3 seeds for v1 cnn_bn + CROWN(fc).

Produces publication-ready mean+/-std numbers.
"""

import argparse
import json
import time

import numpy as np

from regulus.nn.benchmark import train_mnist_model, certify_mnist


def run_benchmark(n_test: int = 1000, seeds: list[int] | None = None):
    if seeds is None:
        seeds = [42, 123, 7]

    print("=" * 80)
    print(f"FINAL BENCHMARK: v1 cnn_bn + CROWN(fc) -- {n_test} images x {len(seeds)} seeds")
    print("=" * 80)

    all_results = []

    for seed in seeds:
        print(f"\n{'-'*60}")
        print(f"  Seed {seed}")
        print(f"{'-'*60}")

        t0 = time.perf_counter()

        print(f"  Training cnn_bn (ibp=5.0, seed={seed})...")
        model = train_mnist_model(
            epochs=10, architecture="cnn_bn",
            ibp_loss_weight=5.0, weight_reg=0.001,
            ibp_eps_start=0.01, ibp_eps_end=0.01,
            seed=seed, verbose=True,
        )
        train_time = time.perf_counter() - t0

        # IBP certification
        t1 = time.perf_counter()
        print(f"  Certifying with IBP ({n_test} images)...")
        ibp_report = certify_mnist(
            model, epsilon=0.01, n_test=n_test,
            strategy="naive", architecture="cnn_bn",
            verbose=True, progress_interval=200,
        )
        ibp_time = time.perf_counter() - t1

        # CROWN certification
        t2 = time.perf_counter()
        print(f"  Certifying with CROWN ({n_test} images)...")
        crown_report = certify_mnist(
            model, epsilon=0.01, n_test=n_test,
            strategy="crown", architecture="cnn_bn",
            verbose=True, progress_interval=200,
            crown_depth="fc",
        )
        crown_time = time.perf_counter() - t2

        result = {
            "seed": seed,
            "n_test": n_test,
            "clean_accuracy": ibp_report.clean_accuracy,
            "ibp_certified": ibp_report.certified_accuracy,
            "ibp_width": ibp_report.avg_output_max_width,
            "ibp_margin": ibp_report.avg_margin,
            "ibp_time_s": round(ibp_time, 1),
            "crown_certified": crown_report.certified_accuracy,
            "crown_width": crown_report.avg_output_max_width,
            "crown_margin": crown_report.avg_margin,
            "crown_time_s": round(crown_time, 1),
            "train_time_s": round(train_time, 1),
            "crown_improvement_pct": round(
                (crown_report.certified_accuracy - ibp_report.certified_accuracy) * 100, 1
            ),
            "width_reduction_pct": round(
                (1.0 - crown_report.avg_output_max_width / ibp_report.avg_output_max_width) * 100, 1
            ),
        }
        all_results.append(result)

        print(f"\n  Seed {seed} results:")
        print(f"    Clean:  {result['clean_accuracy']:.1%}")
        print(f"    IBP:    {result['ibp_certified']:.1%} certified, width={result['ibp_width']:.4f}, {result['ibp_time_s']}s")
        print(f"    CROWN:  {result['crown_certified']:.1%} certified, width={result['crown_width']:.4f}, {result['crown_time_s']}s")
        print(f"    CROWN D: +{result['crown_improvement_pct']}% cert, -{result['width_reduction_pct']}% width")

    # Summary table
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"  {'Seed':>6} {'Clean':>8} {'IBP_cert':>10} {'CROWN_cert':>10} "
          f"{'IBP_w':>10} {'CROWN_w':>10} {'Dcert':>8} {'Dwidth':>8}")
    print(f"  {'-'*6} {'-'*8} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*8}")
    for r in all_results:
        print(f"  {r['seed']:>6} {r['clean_accuracy']:>7.1%} {r['ibp_certified']:>9.1%} "
              f"{r['crown_certified']:>9.1%} {r['ibp_width']:>10.4f} {r['crown_width']:>10.4f} "
              f"{r['crown_improvement_pct']:>+7.1f}% {r['width_reduction_pct']:>7.1f}%")

    # Aggregate stats
    ibp_certs = [r["ibp_certified"] for r in all_results]
    crown_certs = [r["crown_certified"] for r in all_results]
    ibp_widths = [r["ibp_width"] for r in all_results]
    crown_widths = [r["crown_width"] for r in all_results]
    cleans = [r["clean_accuracy"] for r in all_results]

    print(f"\n  {'MEAN+/-STD':>6} {np.mean(cleans):>7.1%} "
          f"{np.mean(ibp_certs):>6.1%}+/-{np.std(ibp_certs):>3.1%} "
          f"{np.mean(crown_certs):>6.1%}+/-{np.std(crown_certs):>3.1%} "
          f"{np.mean(ibp_widths):>10.4f} {np.mean(crown_widths):>10.4f}")

    summary = {
        "config": {
            "architecture": "cnn_bn",
            "ibp_loss_weight": 5.0,
            "weight_reg": 0.001,
            "epochs": 10,
            "epsilon": 0.01,
            "crown_depth": "fc",
            "alpha_mode": "adaptive",
            "n_test": n_test,
            "seeds": seeds,
        },
        "per_seed": all_results,
        "aggregate": {
            "clean_mean": round(float(np.mean(cleans)), 4),
            "ibp_certified_mean": round(float(np.mean(ibp_certs)), 4),
            "ibp_certified_std": round(float(np.std(ibp_certs)), 4),
            "crown_certified_mean": round(float(np.mean(crown_certs)), 4),
            "crown_certified_std": round(float(np.std(crown_certs)), 4),
            "ibp_width_mean": round(float(np.mean(ibp_widths)), 4),
            "crown_width_mean": round(float(np.mean(crown_widths)), 4),
            "crown_improvement_mean": round(
                float(np.mean(crown_certs) - np.mean(ibp_certs)) * 100, 1
            ),
            "width_reduction_mean": round(
                (1.0 - np.mean(crown_widths) / np.mean(ibp_widths)) * 100, 1
            ),
        },
    }

    output_file = f"scripts/final_benchmark_{n_test}.json"
    with open(output_file, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Results saved to {output_file}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-test", type=int, default=1000,
                        help="Number of test images (default: 1000)")
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 123, 7],
                        help="Random seeds")
    args = parser.parse_args()
    run_benchmark(n_test=args.n_test, seeds=args.seeds)
