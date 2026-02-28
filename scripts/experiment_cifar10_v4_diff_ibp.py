"""
Experiment v4: CIFAR-10 with DIFFERENTIABLE IBP training.

Previous experiments (v1-v3) used indirect IBP pressure (scalar penalty on
weight norm) — gradients never flowed through interval bounds. Result: 0%
certified across all configs despite 83-90% clean accuracy.

This experiment uses ibp_forward() which propagates torch tensor intervals
through the network with full autograd — the model learns to minimize
worst-case cross-entropy loss directly.

Architecture: cifar_cnn_bn (MaxPool) — best from v3 Phase 1 (22K width vs 50K AvgPool).
"""

import argparse
import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from regulus.nn.benchmark import train_cifar_diff_ibp, certify_cifar


def run_experiment(
    configs: list[dict],
    architecture: str = "cifar_cnn_bn",
    n_test: int = 100,
    seed: int = 42,
    verbose: bool = True,
):
    """Run differentiable IBP training experiments."""

    results = []

    for ci, cfg in enumerate(configs):
        label = cfg.pop("label", f"config_{ci}")
        print(f"\n{'='*70}")
        print(f"CONFIG: {label}")
        print(f"{'='*70}")
        for k, v in cfg.items():
            print(f"  {k}: {v}")

        t0 = time.perf_counter()

        model = train_cifar_diff_ibp(
            architecture=architecture,
            seed=seed,
            verbose=verbose,
            return_result=False,
            **cfg,
        )

        train_time = time.perf_counter() - t0
        print(f"\n  Training time: {train_time:.1f}s")

        # Certify with IBP
        eps_end = cfg.get("eps_end", 0.01)
        print(f"\n  IBP certification ({n_test} images, eps={eps_end})...")
        report_ibp = certify_cifar(
            model, epsilon=eps_end, n_test=n_test,
            strategy="naive", architecture=architecture,
            verbose=verbose, progress_interval=50,
        )

        result = {
            "label": label,
            "config": cfg,
            "clean": report_ibp.clean_accuracy,
            "ibp_certified": report_ibp.certified_accuracy,
            "ibp_width": report_ibp.avg_output_max_width,
            "ibp_margin": report_ibp.avg_margin,
            "train_time": round(train_time, 1),
        }

        print(f"\n  {label}: clean={report_ibp.clean_accuracy*100:.1f}%, "
              f"IBP cert={report_ibp.certified_accuracy*100:.1f}%, "
              f"width={report_ibp.avg_output_max_width:.4f}")

        # CROWN if width is promising
        if report_ibp.avg_output_max_width < 50.0:
            print(f"\n  Width < 50 — running CROWN(fc)...")
            report_crown = certify_cifar(
                model, epsilon=eps_end, n_test=n_test,
                strategy="crown", architecture=architecture,
                crown_depth="fc",
                verbose=verbose, progress_interval=50,
            )
            result["crown_certified"] = report_crown.certified_accuracy
            result["crown_width"] = report_crown.avg_output_max_width
            result["crown_margin"] = report_crown.avg_margin
            print(f"  CROWN: cert={report_crown.certified_accuracy*100:.1f}%, "
                  f"width={report_crown.avg_output_max_width:.4f}")

        results.append(result)

    return results


def main():
    parser = argparse.ArgumentParser(description="CIFAR-10 v4: Differentiable IBP")
    parser.add_argument("--arch", type=str, default="cifar_cnn_bn")
    parser.add_argument("--n-test", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quick", action="store_true",
                        help="Quick smoke test (5 epochs, 20 images)")
    args = parser.parse_args()

    if args.quick:
        configs = [
            {
                "label": "quick_smoke_test",
                "epochs": 5,
                "ibp_weight": 0.1,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.2,
                "ramp_fraction": 0.3,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
            },
        ]
        n_test = 20
    else:
        configs = [
            {
                "label": "A_gentle_diff_ibp",
                "epochs": 50,
                "ibp_weight": 0.1,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.2,
                "ramp_fraction": 0.4,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
            },
            {
                "label": "B_moderate_diff_ibp",
                "epochs": 50,
                "ibp_weight": 0.3,
                "eps_start": 0.001,
                "eps_end": 0.01,
                "warmup_fraction": 0.2,
                "ramp_fraction": 0.4,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
            },
            {
                "label": "C_strong_diff_ibp",
                "epochs": 50,
                "ibp_weight": 0.5,
                "eps_start": 0.001,
                "eps_end": 0.01,
                "warmup_fraction": 0.2,
                "ramp_fraction": 0.4,
                "weight_reg": 0.001,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
            },
        ]
        n_test = args.n_test

    results = run_experiment(
        configs=configs,
        architecture=args.arch,
        n_test=n_test,
        seed=args.seed,
    )

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY: Differentiable IBP Training")
    print(f"{'='*70}")
    print(f"  {'Config':<25} {'Clean':>7} {'IBP Cert':>9} {'IBP Width':>11} "
          f"{'CROWN Cert':>11}")
    print(f"  {'-'*25} {'-'*7} {'-'*9} {'-'*11} {'-'*11}")
    for r in results:
        crown = r.get("crown_certified")
        crown_str = f"{crown*100:>10.1f}%" if crown is not None else f"{'—':>11}"
        print(f"  {r['label']:<25} {r['clean']*100:>6.1f}% "
              f"{r['ibp_certified']*100:>8.1f}% {r['ibp_width']:>11.4f} {crown_str}")

    # Save
    output_path = os.path.join(
        os.path.dirname(__file__),
        "v4_diff_ibp_results.json"
    )
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
