"""
Experiment v6: CIFAR-10 — No Margin, Proven Base from v4.

v5 lesson learned: margin loss is COUNTERPRODUCTIVE.
- Builds large weights during warmup → massive IBP shock
- v4 Config B (no margin) achieved 33% clean / 71% cert
- All v5 configs with margin did WORSE

v6 strategy: v4 B's proven approach scaled to 100 epochs.
  - NO margin loss (margin_weight=0)
  - Shorter warmup (0.15-0.25) to avoid building large weights
  - Lambda 0.2-0.35 (v4 B used 0.3)
  - Test both eps=0.01 and eps=0.005

Configs:
  E1: eps=0.01, lambda=0.3, warmup=0.2, ramp=0.4 — v4 B exact, 2x epochs
  E2: eps=0.005, lambda=0.3, warmup=0.2, ramp=0.4 — easier eps, same schedule
  E3: eps=0.005, lambda=0.2, warmup=0.25, ramp=0.35 — gentler for clean acc

Target: clean >= 40% AND certified >= 50%
Stretch goal: clean >= 50% AND certified >= 40%
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
    """Run no-margin experiments."""

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
    parser = argparse.ArgumentParser(description="CIFAR-10 v6: No Margin")
    parser.add_argument("--arch", type=str, default="cifar_cnn_bn")
    parser.add_argument("--n-test", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quick", action="store_true",
                        help="Quick smoke test (20 epochs, 20 images)")
    args = parser.parse_args()

    if args.quick:
        configs = [
            {
                "label": "quick_v6_smoke",
                "epochs": 20,
                "ibp_weight": 0.3,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.2,
                "ramp_fraction": 0.4,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
        ]
        n_test = 20
    else:
        configs = [
            {
                "label": "E1_v4B_100ep",
                "epochs": 100,
                "ibp_weight": 0.30,
                "eps_start": 0.001,
                "eps_end": 0.01,
                "warmup_fraction": 0.20,
                "ramp_fraction": 0.40,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
            {
                "label": "E2_eps005_lam30",
                "epochs": 100,
                "ibp_weight": 0.30,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.20,
                "ramp_fraction": 0.40,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
            {
                "label": "E3_eps005_lam20_gentle",
                "epochs": 100,
                "ibp_weight": 0.20,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.25,
                "ramp_fraction": 0.35,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
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
    print("SUMMARY: v6 No Margin")
    print(f"{'='*70}")
    print(f"  {'Config':<30} {'Clean':>7} {'IBP Cert':>9} {'IBP Width':>11} "
          f"{'CROWN Cert':>11}")
    print(f"  {'-'*30} {'-'*7} {'-'*9} {'-'*11} {'-'*11}")
    for r in results:
        crown = r.get("crown_certified")
        crown_str = f"{crown*100:>10.1f}%" if crown is not None else f"{'—':>11}"
        print(f"  {r['label']:<30} {r['clean']*100:>6.1f}% "
              f"{r['ibp_certified']*100:>8.1f}% {r['ibp_width']:>11.4f} {crown_str}")

    # Progress vs v4 B baseline
    print(f"\n{'='*70}")
    print("PROGRESS vs v4 Config B (33% clean, 71% IBP cert)")
    print(f"{'='*70}")
    for r in results:
        clean_delta = r["clean"] - 0.33
        cert_delta = r["ibp_certified"] - 0.71
        clean_flag = "↑" if clean_delta > 0 else "↓"
        cert_flag = "↑" if cert_delta > 0 else "↓"
        print(f"  {r['label']:<30} clean {clean_flag}{abs(clean_delta)*100:+.0f}pp, "
              f"cert {cert_flag}{abs(cert_delta)*100:+.0f}pp")

    # Goal check
    print(f"\n{'='*70}")
    print("GOAL CHECK: clean >= 40% AND certified >= 50%")
    print(f"{'='*70}")
    for r in results:
        clean_ok = r["clean"] >= 0.40
        cert_ok = r["ibp_certified"] >= 0.50
        status = "✓ PASS" if (clean_ok and cert_ok) else "✗ FAIL"
        clean_flag = "✓" if clean_ok else "✗"
        cert_flag = "✓" if cert_ok else "✗"
        print(f"  {r['label']:<30} {status}  "
              f"(clean {clean_flag} {r['clean']*100:.0f}%, "
              f"cert {cert_flag} {r['ibp_certified']*100:.0f}%)")

    # Save
    output_path = os.path.join(
        os.path.dirname(__file__),
        "v6_no_margin_results.json"
    )
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
