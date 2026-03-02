"""
Experiment v14: Fine λ sweep in the collapse boundary zone.

v13 findings:
  K3 (λ=0.05): 45% clean, 0% cert, width=3.64 (CROWN), 4.3% CROWN improve
  K4 (λ=0.10): 10% clean, 100% cert, width=0.00 — COLLAPSED (constant output)

The transition from "good clean, no cert" to "collapse" is somewhere in λ=0.05-0.10.
K4 collapsed with warmup=0.25, ramp=0.35 (40% of training at full IBP).

v14 strategy:
  1. Fine sweep λ=0.06, 0.08, 0.10, 0.12, 0.15
  2. Extended warmup (0.35-0.45) to prevent FC2 collapse
  3. The FC2 intermediate ReLU is the fragile point — more warmup lets
     the network learn stable features BEFORE IBP pressure hits

Key: original ResNetCIFAR (no FC2) handled λ=0.20 fine (H3: 46% clean, 29% cert).
FC2's intermediate ReLU layer makes it more fragile. Extended warmup should help.

Configs (100 epochs, ε=0.005):
  L1: λ=0.06, warmup=0.35, ramp=0.40 — gentle, just above K3
  L2: λ=0.08, warmup=0.35, ramp=0.40 — moderate
  L3: λ=0.10, warmup=0.40, ramp=0.35 — K4 retry with much more warmup
  L4: λ=0.12, warmup=0.45, ramp=0.35 — aggressive λ with max warmup
  L5: λ=0.15, warmup=0.45, ramp=0.35 — push hard with max warmup

If L3/L4 survive without collapsing, CROWN cert could be meaningful.
Target: clean ≥ 40% AND CROWN cert ≥ 40% at ε=0.005
"""

import argparse
import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from regulus.nn.benchmark import train_cifar_diff_ibp, certify_cifar


def run_experiment(configs, architecture="resnet_cifar_fc2", n_test=100, seed=42, verbose=True):
    results = []
    for ci, cfg in enumerate(configs):
        label = cfg.pop("label", f"config_{ci}")
        print(f"\n{'='*70}")
        print(f"CONFIG: {label}")
        print(f"Architecture: {architecture}")
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

        eps = cfg.get("eps_end", 0.005)

        # IBP certification
        print(f"\n  IBP certification ({n_test} images, eps={eps})...")
        report_ibp = certify_cifar(
            model, epsilon=eps, n_test=n_test,
            strategy="naive", architecture=architecture,
            verbose=verbose, progress_interval=25,
        )
        print(f"\n  IBP: clean={report_ibp.clean_accuracy*100:.1f}%, "
              f"cert={report_ibp.certified_accuracy*100:.1f}%, "
              f"width={report_ibp.avg_output_max_width:.4f}")

        result = {
            "label": label, "config": cfg,
            "architecture": architecture,
            "clean": report_ibp.clean_accuracy,
            "ibp_cert": report_ibp.certified_accuracy,
            "ibp_width": report_ibp.avg_output_max_width,
            "train_time": round(train_time, 1),
        }

        # Collapse detection — skip CROWN if collapsed
        collapsed = report_ibp.clean_accuracy < 0.12
        if collapsed:
            print(f"  ⚠ COLLAPSE DETECTED: clean < 12%, skipping CROWN")
            result["collapsed"] = True

        # CROWN(fc) certification
        if not collapsed and report_ibp.avg_output_max_width < 100.0:
            print(f"\n  CROWN(fc) certification ({n_test} images, eps={eps})...")
            try:
                report_crown = certify_cifar(
                    model, epsilon=eps, n_test=n_test,
                    strategy="crown", architecture=architecture,
                    crown_depth="fc", verbose=verbose, progress_interval=25,
                )
                print(f"\n  CROWN: clean={report_crown.clean_accuracy*100:.1f}%, "
                      f"cert={report_crown.certified_accuracy*100:.1f}%, "
                      f"width={report_crown.avg_output_max_width:.4f}")
                result["crown_cert"] = report_crown.certified_accuracy
                result["crown_width"] = report_crown.avg_output_max_width
                ibp_w = max(report_ibp.avg_output_max_width, 1e-6)
                crown_improve = (1.0 - report_crown.avg_output_max_width / ibp_w) * 100
                result["crown_improvement"] = round(crown_improve, 1)
                print(f"  CROWN improvement: {crown_improve:.1f}% width reduction")
            except Exception as e:
                print(f"\n  CROWN FAILED: {e}")
                result["crown_error"] = str(e)

        results.append(result)
        print(f"\n  {'='*50}")
        best_cert = result.get("crown_cert", result["ibp_cert"])
        status = "COLLAPSED" if collapsed else f"clean={result['clean']*100:.0f}%, best_cert={best_cert*100:.0f}%"
        print(f"  {label} DONE: {status}")
        print(f"  {'='*50}")

    return results


def main():
    parser = argparse.ArgumentParser(description="CIFAR-10 v14: Fine λ sweep + extended warmup")
    parser.add_argument("--n-test", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quick", action="store_true",
                        help="Quick smoke test (30 epochs, 20 images, 2 configs)")
    args = parser.parse_args()

    if args.quick:
        configs = [
            {
                "label": "quick_L2_lam08",
                "epochs": 30,
                "ibp_weight": 0.08,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.35,
                "ramp_fraction": 0.40,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
            {
                "label": "quick_L3_lam10",
                "epochs": 30,
                "ibp_weight": 0.10,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.40,
                "ramp_fraction": 0.35,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
        ]
        n_test = 20
    else:
        configs = [
            {
                "label": "L1_fc2_lam06",
                "epochs": 100,
                "ibp_weight": 0.06,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.35,
                "ramp_fraction": 0.40,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
            {
                "label": "L2_fc2_lam08",
                "epochs": 100,
                "ibp_weight": 0.08,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.35,
                "ramp_fraction": 0.40,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
            {
                "label": "L3_fc2_lam10_longwarm",
                "epochs": 100,
                "ibp_weight": 0.10,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.40,
                "ramp_fraction": 0.35,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
            {
                "label": "L4_fc2_lam12_longwarm",
                "epochs": 100,
                "ibp_weight": 0.12,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.45,
                "ramp_fraction": 0.35,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
            {
                "label": "L5_fc2_lam15_longwarm",
                "epochs": 100,
                "ibp_weight": 0.15,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.45,
                "ramp_fraction": 0.35,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
        ]
        n_test = args.n_test

    results = run_experiment(
        configs=configs, architecture="resnet_cifar_fc2",
        n_test=n_test, seed=args.seed,
    )

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY: v14 Fine λ Sweep + Extended Warmup (ResNetCIFAR_FC2)")
    print(f"{'='*70}")
    print(f"  {'Config':<26} {'λ':>5} {'Warm':>5} {'Clean':>7} {'IBP Cert':>9} "
          f"{'CROWN Cert':>11} {'IBP Width':>10} {'CROWN Width':>12} {'Improve':>8}")
    print(f"  {'-'*26} {'-'*5} {'-'*5} {'-'*7} {'-'*9} {'-'*11} {'-'*10} {'-'*12} {'-'*8}")
    for r in results:
        cc = r.get("crown_cert")
        cw = r.get("crown_width")
        ci = r.get("crown_improvement")
        lam = r["config"].get("ibp_weight", "?")
        warm = r["config"].get("warmup_fraction", "?")
        cc_str = f"{cc*100:>10.1f}%" if cc is not None else f"{'--':>11}"
        cw_str = f"{cw:>12.4f}" if cw is not None else f"{'--':>12}"
        ci_str = f"{ci:>7.1f}%" if ci is not None else f"{'--':>8}"
        status = "COLLAPSED" if r.get("collapsed") else f"{r['clean']*100:>6.1f}%"
        print(f"  {r['label']:<26} {lam:>5} {warm:>5} {status:>7} "
              f"{r['ibp_cert']*100:>8.1f}% {cc_str} "
              f"{r['ibp_width']:>10.4f} {cw_str} {ci_str}")

    # Comparison with prior best
    print(f"\n{'='*70}")
    print("COMPARISON vs all prior results (ε=0.005)")
    print(f"{'='*70}")
    baselines = {
        "H3 v9 (ResNet, IBP)":        {"clean": 0.46, "cert": 0.29, "type": "IBP"},
        "J2 v12 (FC2, λ=.25)":        {"clean": 0.26, "cert": 0.36, "type": "IBP≈CROWN"},
        "K3 v13 (FC2, λ=.05)":        {"clean": 0.45, "cert": 0.00, "type": "CROWN(width=3.64)"},
        "E3 v6 (cnn_bn, CROWN)":      {"clean": 0.29, "cert": 0.745, "type": "CROWN"},
        "F2 v7 (cnn_bn, CROWN)":      {"clean": 0.35, "cert": 0.60, "type": "CROWN"},
    }
    for bname, bvals in baselines.items():
        print(f"  {bname}: clean={bvals['clean']*100:.0f}%, "
              f"{bvals['type']}={bvals['cert']*100:.1f}%")

    # Target check
    print(f"\n  TARGET: clean ≥ 40% AND cert ≥ 40%")
    print(f"  {'-'*60}")
    any_met = False
    for r in results:
        best_cert = r.get("crown_cert", r["ibp_cert"])
        met_clean = r["clean"] >= 0.40
        met_cert = best_cert >= 0.40
        if r.get("collapsed"):
            status = "✗ COLLAPSED"
        elif met_clean and met_cert:
            status = "✓ TARGET MET"
            any_met = True
        else:
            status = "✗"
        print(f"  {status} {r['label']}: clean={r['clean']*100:.0f}%, "
              f"best_cert={best_cert*100:.0f}%")

    if not any_met:
        # Find closest to target
        print(f"\n  Closest to target:")
        for r in results:
            if r.get("collapsed"):
                continue
            best_cert = r.get("crown_cert", r["ibp_cert"])
            gap_clean = max(0, 0.40 - r["clean"])
            gap_cert = max(0, 0.40 - best_cert)
            total_gap = gap_clean + gap_cert
            print(f"    {r['label']}: gap = {total_gap*100:.1f}pp "
                  f"(clean gap: {gap_clean*100:.1f}pp, cert gap: {gap_cert*100:.1f}pp)")

    output_path = os.path.join(os.path.dirname(__file__), "v14_fine_lambda_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
