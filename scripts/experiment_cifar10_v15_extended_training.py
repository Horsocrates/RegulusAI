"""
Experiment v15: Extended training at the L3/L4 sweet spot.

v14 key finding:
  L3 (λ=0.10, warmup=0.40, 100ep): 49% clean, 11% cert
  L4 (λ=0.12, warmup=0.45, 100ep): 47% clean, 19% cert  ← best balance

Problem: at 100 epochs with warmup=0.45, ramp=0.35, only 20 epochs
are at full IBP pressure. That may not be enough for tight bounds.

v15 strategy:
  1. Same λ=0.10-0.14, but 150 epochs → ~30-45 epochs at full IBP
  2. Test warmup=0.50 to see if even more warmup helps
  3. This doubles the time at full IBP compared to v14

Schedule math (150 epochs):
  M1: warmup=0.40, ramp=0.35 → 60ep clean + 52ep ramp + 38ep full IBP
  M2: warmup=0.45, ramp=0.35 → 68ep clean + 52ep ramp + 30ep full IBP
  M3: warmup=0.50, ramp=0.30 → 75ep clean + 45ep ramp + 30ep full IBP
  M4: warmup=0.45, ramp=0.35 → 68ep clean + 52ep ramp + 30ep full IBP

Configs:
  M1: λ=0.10, warmup=0.40, ramp=0.35, 150ep — L3 with 1.5x epochs
  M2: λ=0.12, warmup=0.45, ramp=0.35, 150ep — L4 with 1.5x epochs
  M3: λ=0.14, warmup=0.50, ramp=0.30, 150ep — higher λ, max warmup
  M4: λ=0.12, warmup=0.45, ramp=0.35, 200ep — L4 with 2x epochs

If L4 at 100ep gave 19% cert, at 150ep we might reach 25-30%.
Target: clean ≥ 40% AND cert ≥ 40% at ε=0.005
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
        print(f"Epochs: {cfg.get('epochs', '?')}")
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

        # Collapse detection
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
    parser = argparse.ArgumentParser(description="CIFAR-10 v15: Extended training at L3/L4 sweet spot")
    parser.add_argument("--n-test", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quick", action="store_true",
                        help="Quick smoke test (30 epochs, 20 images, 2 configs)")
    args = parser.parse_args()

    if args.quick:
        configs = [
            {
                "label": "quick_M2_lam12_150ep",
                "epochs": 30,
                "ibp_weight": 0.12,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.45,
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
                "label": "M1_fc2_lam10_150ep",
                "epochs": 150,
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
                "label": "M2_fc2_lam12_150ep",
                "epochs": 150,
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
                "label": "M3_fc2_lam14_150ep_maxwarm",
                "epochs": 150,
                "ibp_weight": 0.14,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.50,
                "ramp_fraction": 0.30,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
            {
                "label": "M4_fc2_lam12_200ep",
                "epochs": 200,
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
        ]
        n_test = args.n_test

    results = run_experiment(
        configs=configs, architecture="resnet_cifar_fc2",
        n_test=n_test, seed=args.seed,
    )

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY: v15 Extended Training (ResNetCIFAR_FC2)")
    print(f"{'='*70}")
    print(f"  {'Config':<30} {'λ':>5} {'Ep':>4} {'Warm':>5} {'Clean':>7} {'IBP Cert':>9} "
          f"{'CROWN Cert':>11} {'CROWN Width':>12} {'Improve':>8}")
    print(f"  {'-'*30} {'-'*5} {'-'*4} {'-'*5} {'-'*7} {'-'*9} {'-'*11} {'-'*12} {'-'*8}")
    for r in results:
        cc = r.get("crown_cert")
        cw = r.get("crown_width")
        ci = r.get("crown_improvement")
        lam = r["config"].get("ibp_weight", "?")
        warm = r["config"].get("warmup_fraction", "?")
        epochs = r["config"].get("epochs", "?")
        cc_str = f"{cc*100:>10.1f}%" if cc is not None else f"{'--':>11}"
        cw_str = f"{cw:>12.4f}" if cw is not None else f"{'--':>12}"
        ci_str = f"{ci:>7.1f}%" if ci is not None else f"{'--':>8}"
        status = "COLLAPSED" if r.get("collapsed") else f"{r['clean']*100:>6.1f}%"
        print(f"  {r['label']:<30} {lam:>5} {epochs:>4} {warm:>5} {status:>7} "
              f"{r['ibp_cert']*100:>8.1f}% {cc_str} "
              f"{cw_str} {ci_str}")

    # Comparison with prior best
    print(f"\n{'='*70}")
    print("COMPARISON vs all prior results (ε=0.005)")
    print(f"{'='*70}")
    baselines = {
        "H3 v9 (ResNet, IBP)":         {"clean": 0.46, "cert": 0.29, "type": "IBP"},
        "L3 v14 (FC2, λ=.10, 100ep)":  {"clean": 0.49, "cert": 0.11, "type": "IBP+CROWN"},
        "L4 v14 (FC2, λ=.12, 100ep)":  {"clean": 0.47, "cert": 0.19, "type": "IBP+CROWN"},
        "J2 v12 (FC2, λ=.25, 100ep)":  {"clean": 0.26, "cert": 0.36, "type": "IBP≈CROWN"},
        "E3 v6 (cnn_bn, CROWN)":       {"clean": 0.29, "cert": 0.745, "type": "CROWN"},
        "F2 v7 (cnn_bn, CROWN)":       {"clean": 0.35, "cert": 0.60, "type": "CROWN"},
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

    if any_met:
        print(f"\n  🎯 TARGET ACHIEVED!")

    output_path = os.path.join(os.path.dirname(__file__), "v15_extended_training_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
