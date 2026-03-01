"""
Experiment v7: CIFAR-10 — Fine-tuning the λ lever for clean/cert balance.

v6 E3 (λ=0.20, ε=0.005) beat v4 B baseline: 73.5% cert at 29% clean.
Now we explore λ=0.10-0.15 to push clean accuracy above 40%.

Key insight from v4-v6: λ is the primary lever.
  λ=0.30 → cert ~50%, clean ~29%
  λ=0.20 → cert ~73%, clean ~29%  (E3 sweet spot for cert)
  λ=0.15 → cert ~??%, clean ~35-40%?  (prediction)
  λ=0.10 → cert ~??%, clean ~40-50%?  (prediction)

All configs: no margin loss, ε=0.005, warmup=0.25-0.30.

Configs:
  F1: λ=0.15, warmup=0.25, ramp=0.35 — moderate, E3 but gentler
  F2: λ=0.10, warmup=0.30, ramp=0.30 — gentle, maximize clean
  F3: λ=0.12, warmup=0.30, ramp=0.35 — between F1 and F2

Target: clean >= 40% AND certified >= 40%
"""

import argparse
import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from regulus.nn.benchmark import train_cifar_diff_ibp, certify_cifar


def run_experiment(configs, architecture="cifar_cnn_bn", n_test=100, seed=42, verbose=True):
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
            architecture=architecture, seed=seed, verbose=verbose,
            return_result=False, **cfg,
        )
        train_time = time.perf_counter() - t0
        print(f"\n  Training time: {train_time:.1f}s")

        eps_end = cfg.get("eps_end", 0.005)
        print(f"\n  IBP certification ({n_test} images, eps={eps_end})...")
        report_ibp = certify_cifar(
            model, epsilon=eps_end, n_test=n_test,
            strategy="naive", architecture=architecture,
            verbose=verbose, progress_interval=50,
        )

        result = {
            "label": label, "config": cfg,
            "clean": report_ibp.clean_accuracy,
            "ibp_certified": report_ibp.certified_accuracy,
            "ibp_width": report_ibp.avg_output_max_width,
            "ibp_margin": report_ibp.avg_margin,
            "train_time": round(train_time, 1),
        }

        print(f"\n  {label}: clean={report_ibp.clean_accuracy*100:.1f}%, "
              f"IBP cert={report_ibp.certified_accuracy*100:.1f}%, "
              f"width={report_ibp.avg_output_max_width:.4f}")

        if report_ibp.avg_output_max_width < 50.0:
            print(f"\n  Running CROWN(fc)...")
            report_crown = certify_cifar(
                model, epsilon=eps_end, n_test=n_test,
                strategy="crown", architecture=architecture,
                crown_depth="fc", verbose=verbose, progress_interval=50,
            )
            result["crown_certified"] = report_crown.certified_accuracy
            result["crown_width"] = report_crown.avg_output_max_width
            print(f"  CROWN: cert={report_crown.certified_accuracy*100:.1f}%, "
                  f"width={report_crown.avg_output_max_width:.4f}")

        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description="CIFAR-10 v7: Balance λ")
    parser.add_argument("--arch", type=str, default="cifar_cnn_bn")
    parser.add_argument("--n-test", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quick", action="store_true",
                        help="Quick smoke test (30 epochs, 20 images)")
    args = parser.parse_args()

    if args.quick:
        configs = [
            {
                "label": "quick_F1_lam15",
                "epochs": 30,
                "ibp_weight": 0.15,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.25,
                "ramp_fraction": 0.35,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
            {
                "label": "quick_F2_lam10",
                "epochs": 30,
                "ibp_weight": 0.10,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.30,
                "ramp_fraction": 0.30,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
        ]
        n_test = 20
    else:
        configs = [
            {
                "label": "F1_lam15_warm25",
                "epochs": 100,
                "ibp_weight": 0.15,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.25,
                "ramp_fraction": 0.35,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
            {
                "label": "F2_lam10_warm30",
                "epochs": 100,
                "ibp_weight": 0.10,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.30,
                "ramp_fraction": 0.30,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
            {
                "label": "F3_lam12_warm30",
                "epochs": 100,
                "ibp_weight": 0.12,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.30,
                "ramp_fraction": 0.35,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
        ]
        n_test = args.n_test

    results = run_experiment(
        configs=configs, architecture=args.arch,
        n_test=n_test, seed=args.seed,
    )

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY: v7 Balance λ")
    print(f"{'='*70}")
    print(f"  {'Config':<30} {'Clean':>7} {'IBP Cert':>9} {'IBP Width':>11} "
          f"{'CROWN Cert':>11}")
    print(f"  {'-'*30} {'-'*7} {'-'*9} {'-'*11} {'-'*11}")
    for r in results:
        crown = r.get("crown_certified")
        crown_str = f"{crown*100:>10.1f}%" if crown is not None else f"{'—':>11}"
        print(f"  {r['label']:<30} {r['clean']*100:>6.1f}% "
              f"{r['ibp_certified']*100:>8.1f}% {r['ibp_width']:>11.4f} {crown_str}")

    # Pareto frontier
    print(f"\n{'='*70}")
    print("PARETO CHECK vs E3 baseline (29% clean, 73.5% IBP cert)")
    print(f"{'='*70}")
    for r in results:
        clean_delta = (r["clean"] - 0.29) * 100
        cert_delta = (r["ibp_certified"] - 0.735) * 100
        clean_arrow = "↑" if clean_delta > 0 else "↓"
        cert_arrow = "↑" if cert_delta > 0 else "↓"
        pareto = "PARETO ✓" if clean_delta > 0 or cert_delta > 0 else "dominated"
        print(f"  {r['label']:<30} clean {clean_arrow}{clean_delta:+.0f}pp, "
              f"cert {cert_arrow}{cert_delta:+.0f}pp  [{pareto}]")

    # Goal check
    print(f"\n{'='*70}")
    print("GOAL CHECK: clean >= 40% AND certified >= 40%")
    print(f"{'='*70}")
    for r in results:
        clean_ok = r["clean"] >= 0.40
        cert_ok = r["ibp_certified"] >= 0.40
        status = "✓ PASS" if (clean_ok and cert_ok) else "✗ FAIL"
        print(f"  {r['label']:<30} {status}  "
              f"(clean {'✓' if clean_ok else '✗'} {r['clean']*100:.0f}%, "
              f"cert {'✓' if cert_ok else '✗'} {r['ibp_certified']*100:.0f}%)")

    # Save
    output_path = os.path.join(os.path.dirname(__file__), "v7_balance_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
