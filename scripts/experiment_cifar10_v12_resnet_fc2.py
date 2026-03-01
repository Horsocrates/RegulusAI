"""
Experiment v12: ResNetCIFAR_FC2 — ResNet + 2-layer FC head for CROWN.

v11 finding: CROWN gave 0% improvement because ResNetCIFAR has only
Linear(4096,10) after Flatten — no ReLU for CROWN to tighten.

v12 fix: ResNetCIFAR_FC2 adds intermediate FC layer:
  Flatten → Linear(4096,256) → ReLU → Linear(256,10)
                                 ↑ CROWN backward tightens here

On cifar_cnn_bn (same FC tail), CROWN improved cert from ~20-30% IBP
to 60-74% CROWN. Expected: similar 2-3x boost on ResNet.

Configs (100 epochs, ε=0.005):
  J1: λ=0.20, warmup=0.25, ramp=0.35 — match H3 (v9 best)
  J2: λ=0.25, warmup=0.25, ramp=0.35 — more IBP pressure
  J3: λ=0.30, warmup=0.20, ramp=0.30 — match E3/v4B level

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

        # CROWN(fc) certification
        if report_ibp.avg_output_max_width < 50.0:
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
                crown_improve = (
                    1.0 - report_crown.avg_output_max_width /
                    max(report_ibp.avg_output_max_width, 1e-6)
                ) * 100
                result["crown_improvement"] = round(crown_improve, 1)
                print(f"  CROWN improvement: {crown_improve:.1f}% width reduction")
            except Exception as e:
                print(f"\n  CROWN FAILED: {e}")
                result["crown_error"] = str(e)

        # Collapse check
        if report_ibp.clean_accuracy < 0.12:
            print(f"  ⚠ COLLAPSE DETECTED: clean < 12%")

        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description="CIFAR-10 v12: ResNet FC2 + CROWN")
    parser.add_argument("--n-test", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quick", action="store_true",
                        help="Quick smoke test (30 epochs, 20 images)")
    args = parser.parse_args()

    if args.quick:
        configs = [
            {
                "label": "quick_J1_fc2_lam20",
                "epochs": 30,
                "ibp_weight": 0.20,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.25,
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
                "label": "J1_fc2_lam20",
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
            {
                "label": "J2_fc2_lam25",
                "epochs": 100,
                "ibp_weight": 0.25,
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
                "label": "J3_fc2_lam30",
                "epochs": 100,
                "ibp_weight": 0.30,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.20,
                "ramp_fraction": 0.30,
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
    print("SUMMARY: v12 ResNetCIFAR_FC2 (ResNet + 2-layer FC head)")
    print(f"{'='*70}")
    print(f"  {'Config':<25} {'Clean':>7} {'IBP Cert':>9} {'IBP Width':>10} "
          f"{'CROWN Cert':>11} {'CROWN Width':>12} {'Improve':>8}")
    print(f"  {'-'*25} {'-'*7} {'-'*9} {'-'*10} {'-'*11} {'-'*12} {'-'*8}")
    for r in results:
        cc = r.get("crown_cert")
        cw = r.get("crown_width")
        ci = r.get("crown_improvement")
        cc_str = f"{cc*100:>10.1f}%" if cc is not None else f"{'--':>11}"
        cw_str = f"{cw:>12.4f}" if cw is not None else f"{'--':>12}"
        ci_str = f"{ci:>7.1f}%" if ci is not None else f"{'--':>8}"
        print(f"  {r['label']:<25} {r['clean']*100:>6.1f}% "
              f"{r['ibp_cert']*100:>8.1f}% {r['ibp_width']:>10.4f} "
              f"{cc_str} {cw_str} {ci_str}")

    # Comparison
    print(f"\n{'='*70}")
    print("COMPARISON vs baselines (all at ε=0.005)")
    print(f"{'='*70}")
    baselines = {
        "H3 v9 (ResNet, IBP)":       {"clean": 0.46, "cert": 0.29, "type": "IBP"},
        "v11 (ResNet, CROWN)":        {"clean": 0.50, "cert": 0.0, "type": "CROWN (=IBP)"},
        "E3 v6 (cnn_bn, CROWN)":      {"clean": 0.29, "cert": 0.745, "type": "CROWN"},
        "v4B v5 (cnn_bn, CROWN)":     {"clean": 0.33, "cert": 0.71, "type": "CROWN"},
        "F2 v7 (cnn_bn, CROWN)":      {"clean": 0.35, "cert": 0.60, "type": "CROWN"},
    }
    for bname, bvals in baselines.items():
        print(f"  {bname}: clean={bvals['clean']*100:.0f}%, "
              f"{bvals['type']}={bvals['cert']*100:.1f}%")

    # Target check
    print(f"\n{'='*70}")
    for r in results:
        crown_cert = r.get("crown_cert", r["ibp_cert"])
        met_clean = r["clean"] >= 0.40
        met_cert = crown_cert >= 0.40
        status = "✓" if met_clean and met_cert else "✗"
        print(f"  {status} {r['label']}: clean={r['clean']*100:.0f}%, "
              f"best_cert={crown_cert*100:.0f}% "
              f"(target: clean≥40%, cert≥40%)")

    output_path = os.path.join(os.path.dirname(__file__), "v12_resnet_fc2_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
