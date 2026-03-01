"""
Experiment v13: Low-λ training + CROWN certification for ResNetCIFAR_FC2.

Key insight from v12:
  IBP training eliminates unstable ReLU neurons → CROWN ≈ IBP (0% improvement).
  CROWN only helps when neurons are UNSTABLE (crossing zero).

v13 hypothesis:
  Train with very LOW λ (0.01-0.10) to preserve unstable neurons.
  High clean accuracy + many unstable neurons → CROWN can tighten bounds.
  This is closer to how α-CROWN / auto_LiRPA actually work in practice.

Configs (100 epochs, ε=0.005):
  K1: λ=0.01 — minimal IBP, max clean accuracy, most unstable neurons
  K2: λ=0.03 — light IBP pressure
  K3: λ=0.05 — moderate low-end
  K4: λ=0.10 — reference (known from v9: collapses on ResNet MaxPool)

All use ResNetCIFAR_FC2 (2-layer FC head for CROWN benefit).

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
        if report_ibp.avg_output_max_width < 100.0:
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

        # Collapse check
        if report_ibp.clean_accuracy < 0.12:
            print(f"  ⚠ COLLAPSE DETECTED: clean < 12%")

        results.append(result)
        print(f"\n  {'='*50}")
        best_cert = result.get("crown_cert", result["ibp_cert"])
        print(f"  {label} DONE: clean={result['clean']*100:.0f}%, "
              f"best_cert={best_cert*100:.0f}%")
        print(f"  {'='*50}")

    return results


def main():
    parser = argparse.ArgumentParser(description="CIFAR-10 v13: Low-λ + CROWN")
    parser.add_argument("--n-test", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quick", action="store_true",
                        help="Quick smoke test (30 epochs, 20 images, 1 config)")
    args = parser.parse_args()

    if args.quick:
        configs = [
            {
                "label": "quick_K2_lam03",
                "epochs": 30,
                "ibp_weight": 0.03,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.30,
                "ramp_fraction": 0.40,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
        ]
        n_test = 20
    else:
        configs = [
            {
                "label": "K1_fc2_lam01",
                "epochs": 100,
                "ibp_weight": 0.01,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.30,
                "ramp_fraction": 0.40,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
            {
                "label": "K2_fc2_lam03",
                "epochs": 100,
                "ibp_weight": 0.03,
                "eps_start": 0.001,
                "eps_end": 0.005,
                "warmup_fraction": 0.30,
                "ramp_fraction": 0.40,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
            {
                "label": "K3_fc2_lam05",
                "epochs": 100,
                "ibp_weight": 0.05,
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
                "label": "K4_fc2_lam10",
                "epochs": 100,
                "ibp_weight": 0.10,
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
        configs=configs, architecture="resnet_cifar_fc2",
        n_test=n_test, seed=args.seed,
    )

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY: v13 Low-λ + CROWN (ResNetCIFAR_FC2)")
    print(f"{'='*70}")
    print(f"  {'Config':<22} {'Clean':>7} {'IBP Cert':>9} {'CROWN Cert':>11} "
          f"{'IBP Width':>10} {'CROWN Width':>12} {'Improve':>8}")
    print(f"  {'-'*22} {'-'*7} {'-'*9} {'-'*11} {'-'*10} {'-'*12} {'-'*8}")
    for r in results:
        cc = r.get("crown_cert")
        cw = r.get("crown_width")
        ci = r.get("crown_improvement")
        cc_str = f"{cc*100:>10.1f}%" if cc is not None else f"{'--':>11}"
        cw_str = f"{cw:>12.4f}" if cw is not None else f"{'--':>12}"
        ci_str = f"{ci:>7.1f}%" if ci is not None else f"{'--':>8}"
        print(f"  {r['label']:<22} {r['clean']*100:>6.1f}% "
              f"{r['ibp_cert']*100:>8.1f}% {cc_str} "
              f"{r['ibp_width']:>10.4f} {cw_str} {ci_str}")

    # Comparison
    print(f"\n{'='*70}")
    print("COMPARISON vs all baselines (ε=0.005)")
    print(f"{'='*70}")
    baselines = {
        "H3 v9 (ResNet, IBP)":     {"clean": 0.46, "cert": 0.29, "type": "IBP"},
        "v11 (ResNet, CROWN=IBP)":  {"clean": 0.50, "cert": 0.0, "type": "CROWN"},
        "J2 v12 (FC2, λ=.25)":     {"clean": 0.26, "cert": 0.36, "type": "IBP≈CROWN"},
        "E3 v6 (cnn_bn, CROWN)":   {"clean": 0.29, "cert": 0.745, "type": "CROWN"},
        "F2 v7 (cnn_bn, CROWN)":   {"clean": 0.35, "cert": 0.60, "type": "CROWN"},
    }
    for bname, bvals in baselines.items():
        print(f"  {bname}: clean={bvals['clean']*100:.0f}%, "
              f"{bvals['type']}={bvals['cert']*100:.1f}%")

    # Target check
    print(f"\n  TARGET: clean ≥ 40% AND cert ≥ 40%")
    print(f"  {'-'*60}")
    for r in results:
        best_cert = r.get("crown_cert", r["ibp_cert"])
        met_clean = r["clean"] >= 0.40
        met_cert = best_cert >= 0.40
        status = "✓ TARGET MET" if met_clean and met_cert else "✗"
        print(f"  {status} {r['label']}: clean={r['clean']*100:.0f}%, "
              f"best_cert={best_cert*100:.0f}%")

    output_path = os.path.join(os.path.dirname(__file__), "v13_low_lambda_crown_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
