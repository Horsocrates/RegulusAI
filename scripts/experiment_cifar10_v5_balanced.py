"""
Experiment v5: CIFAR-10 Balanced — Clean Accuracy + Certified Robustness.

Building on v4 breakthrough (71% IBP certified, 33% clean), this experiment
addresses the clean/certified trade-off identified by GPT-5.2, Grok, Gemini:

Key changes from v4:
  1. Longer warmup (0.4-0.5) — lets model learn good features before IBP pressure
  2. Lower lambda (0.15-0.25) — less aggressive IBP weight preserves clean accuracy
  3. 100 epochs — more time for gradual convergence
  4. Margin regularization — prevents model collapse (Config C issue in v4)

Target: clean >= 60% AND IBP certified >= 30-50%

Configs from GPT-5.2 feedback analysis (margin weights tuned to prevent collapse):
  D1: eps=0.01, lambda=0.20, warmup=0.4, margin_weight=0.5 (aggressive eps, strong anti-collapse)
  D2: eps=0.005, lambda=0.25, warmup=0.4, margin_weight=0.5 (smaller eps, strong anti-collapse)
  D3: eps=0.005, lambda=0.15, warmup=0.5, margin_weight=0.3 (gentlest approach)
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
    """Run balanced clean+certified experiments."""

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
    parser = argparse.ArgumentParser(description="CIFAR-10 v5: Balanced Clean+Certified")
    parser.add_argument("--arch", type=str, default="cifar_cnn_bn")
    parser.add_argument("--n-test", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quick", action="store_true",
                        help="Quick smoke test (10 epochs, 20 images)")
    args = parser.parse_args()

    if args.quick:
        configs = [
            {
                "label": "quick_v5_smoke",
                "epochs": 10,
                "ibp_weight": 0.15,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.4,
                "ramp_fraction": 0.3,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.5,
                "margin_target": 2.0,
            },
        ]
        n_test = 20
    else:
        configs = [
            {
                "label": "D1_eps01_lam20_warm40",
                "epochs": 100,
                "ibp_weight": 0.20,
                "eps_start": 0.001,
                "eps_end": 0.01,
                "warmup_fraction": 0.4,
                "ramp_fraction": 0.3,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.5,
                "margin_target": 2.0,
            },
            {
                "label": "D2_eps005_lam25_warm40",
                "epochs": 100,
                "ibp_weight": 0.25,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.4,
                "ramp_fraction": 0.3,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.5,
                "margin_target": 2.0,
            },
            {
                "label": "D3_eps005_lam15_warm50",
                "epochs": 100,
                "ibp_weight": 0.15,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.5,
                "ramp_fraction": 0.3,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.3,
                "margin_target": 2.0,
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
    print("SUMMARY: v5 Balanced Clean + Certified")
    print(f"{'='*70}")
    print(f"  {'Config':<30} {'Clean':>7} {'IBP Cert':>9} {'IBP Width':>11} "
          f"{'CROWN Cert':>11}")
    print(f"  {'-'*30} {'-'*7} {'-'*9} {'-'*11} {'-'*11}")
    for r in results:
        crown = r.get("crown_certified")
        crown_str = f"{crown*100:>10.1f}%" if crown is not None else f"{'—':>11}"
        print(f"  {r['label']:<30} {r['clean']*100:>6.1f}% "
              f"{r['ibp_certified']*100:>8.1f}% {r['ibp_width']:>11.4f} {crown_str}")

    # Goal check
    print(f"\n{'='*70}")
    print("GOAL CHECK: clean >= 60% AND IBP certified >= 30%")
    print(f"{'='*70}")
    for r in results:
        clean_ok = r["clean"] >= 0.60
        cert_ok = r["ibp_certified"] >= 0.30
        status = "✓ PASS" if (clean_ok and cert_ok) else "✗ FAIL"
        clean_flag = "✓" if clean_ok else "✗"
        cert_flag = "✓" if cert_ok else "✗"
        print(f"  {r['label']:<30} {status}  "
              f"(clean {clean_flag} {r['clean']*100:.0f}%, "
              f"cert {cert_flag} {r['ibp_certified']*100:.0f}%)")

    # Save
    output_path = os.path.join(
        os.path.dirname(__file__),
        "v5_balanced_results.json"
    )
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
