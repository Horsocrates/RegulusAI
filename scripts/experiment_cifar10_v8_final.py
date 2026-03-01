"""
Experiment v8: CIFAR-10 — Final push for clean >= 40% + cert >= 40%.

v7 F2 (λ=0.10) achieved 35% clean / 60% CROWN — closest to goal.
Need +5pp clean while maintaining cert.

Key finding: λ=0.12-0.15 is a "dead zone" (width ~1.57, poor cert).
Sweet spots: λ=0.10 (balanced) and λ=0.20 (cert-focused).

Three strategies to push clean accuracy:
  G1: λ=0.08 — even gentler IBP pressure
  G2: λ=0.10, ε=0.003 — easier ε makes IBP less destructive
  G3: λ=0.10, lr_schedule=none — constant LR prevents loss of
      learning capacity during IBP phase (cosine drops LR too early)

Target: clean >= 40% AND CROWN certified >= 40%
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
    parser = argparse.ArgumentParser(description="CIFAR-10 v8: Final Push")
    parser.add_argument("--arch", type=str, default="cifar_cnn_bn")
    parser.add_argument("--n-test", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()

    if args.quick:
        configs = [
            {
                "label": "quick_G1_lam08",
                "epochs": 30,
                "ibp_weight": 0.08,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.35,
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
                "label": "G1_lam08_gentle",
                "epochs": 100,
                "ibp_weight": 0.08,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.35,
                "ramp_fraction": 0.30,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
            {
                "label": "G2_lam10_eps003",
                "epochs": 100,
                "ibp_weight": 0.10,
                "eps_start": 0.001,
                "eps_end": 0.003,
                "warmup_fraction": 0.30,
                "ramp_fraction": 0.30,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
            {
                "label": "G3_lam10_constLR",
                "epochs": 100,
                "ibp_weight": 0.10,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.30,
                "ramp_fraction": 0.30,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "none",
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
    print("SUMMARY: v8 Final Push")
    print(f"{'='*70}")
    print(f"  {'Config':<30} {'Clean':>7} {'IBP Cert':>9} {'IBP Width':>11} "
          f"{'CROWN Cert':>11}")
    print(f"  {'-'*30} {'-'*7} {'-'*9} {'-'*11} {'-'*11}")
    for r in results:
        crown = r.get("crown_certified")
        crown_str = f"{crown*100:>10.1f}%" if crown is not None else f"{'—':>11}"
        print(f"  {r['label']:<30} {r['clean']*100:>6.1f}% "
              f"{r['ibp_certified']*100:>8.1f}% {r['ibp_width']:>11.4f} {crown_str}")

    # Best result highlight
    best = max(results, key=lambda r: r["clean"] + r.get("crown_certified", r["ibp_certified"]))
    crown_best = best.get("crown_certified", best["ibp_certified"])
    print(f"\n  BEST: {best['label']} — clean={best['clean']*100:.0f}% + "
          f"CROWN={crown_best*100:.0f}% = {(best['clean']+crown_best)*100:.0f}pp combined")

    # Goal check
    print(f"\n{'='*70}")
    print("GOAL CHECK: clean >= 40% AND CROWN cert >= 40%")
    print(f"{'='*70}")
    for r in results:
        crown_val = r.get("crown_certified", r["ibp_certified"])
        clean_ok = r["clean"] >= 0.40
        cert_ok = crown_val >= 0.40
        status = "✓ PASS" if (clean_ok and cert_ok) else "✗ FAIL"
        print(f"  {r['label']:<30} {status}  "
              f"(clean {'✓' if clean_ok else '✗'} {r['clean']*100:.0f}%, "
              f"CROWN {'✓' if cert_ok else '✗'} {crown_val*100:.0f}%)")

    output_path = os.path.join(os.path.dirname(__file__), "v8_final_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
