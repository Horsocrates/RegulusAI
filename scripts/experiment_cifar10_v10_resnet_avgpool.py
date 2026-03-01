"""
Experiment v10: CIFAR-10 — ResNetCIFAR_AvgPool.

v9 findings:
  - H3 (λ=0.20, MaxPool) got 46% clean, 29% IBP cert — best clean ever (+11pp over F2)
  - BUT IBP cert low due to MaxPool bound blowup
  - H1/H2 at lower λ collapsed (22%/18% clean)

v10 hypothesis:
  AvgPool (linear op) should give MUCH tighter IBP bounds than MaxPool,
  same way cifar_cnn_bn_avgpool improved over cifar_cnn_bn.
  Combined with ResBlock skip connections → best of both worlds.

Configs (100 epochs, ε=0.005):
  I1: λ=0.20, warmup=0.25, ramp=0.35 — direct H3 comparison with AvgPool
  I2: λ=0.25, warmup=0.25, ramp=0.35 — more IBP pressure
  I3: λ=0.30, warmup=0.20, ramp=0.30 — match v4B λ level

Target: clean ≥ 45% AND IBP cert ≥ 40% at ε=0.005
"""

import argparse
import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from regulus.nn.benchmark import train_cifar_diff_ibp, certify_cifar


def run_experiment(configs, architecture="resnet_cifar_avgpool", n_test=100, seed=42, verbose=True):
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

        eps_end = cfg.get("eps_end", 0.005)
        print(f"\n  IBP certification ({n_test} images, eps={eps_end})...")
        report_ibp = certify_cifar(
            model, epsilon=eps_end, n_test=n_test,
            strategy="naive", architecture=architecture,
            verbose=verbose, progress_interval=50,
        )

        result = {
            "label": label, "config": cfg,
            "architecture": architecture,
            "clean": report_ibp.clean_accuracy,
            "ibp_certified": report_ibp.certified_accuracy,
            "ibp_width": report_ibp.avg_output_max_width,
            "train_time": round(train_time, 1),
        }

        print(f"\n  {label}: clean={report_ibp.clean_accuracy*100:.1f}%, "
              f"IBP cert={report_ibp.certified_accuracy*100:.1f}%, "
              f"width={report_ibp.avg_output_max_width:.4f}")

        # Collapse check
        if report_ibp.clean_accuracy < 0.12:
            print(f"  ⚠ COLLAPSE DETECTED: clean < 12%")
        if report_ibp.avg_output_max_width < 0.001:
            print(f"  ⚠ WARNING: width near zero — constant output")

        # Try CROWN
        if report_ibp.avg_output_max_width < 50.0:
            print(f"\n  Running CROWN(fc)...")
            try:
                report_crown = certify_cifar(
                    model, epsilon=eps_end, n_test=n_test,
                    strategy="crown", architecture=architecture,
                    crown_depth="fc", verbose=verbose, progress_interval=50,
                )
                result["crown_certified"] = report_crown.certified_accuracy
                result["crown_width"] = report_crown.avg_output_max_width
                print(f"  CROWN: cert={report_crown.certified_accuracy*100:.1f}%, "
                      f"width={report_crown.avg_output_max_width:.4f}")
            except (ValueError, NotImplementedError) as e:
                print(f"  CROWN skipped: {e}")

        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description="CIFAR-10 v10: ResNetCIFAR AvgPool")
    parser.add_argument("--n-test", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quick", action="store_true",
                        help="Quick smoke test (30 epochs, 20 images)")
    args = parser.parse_args()

    if args.quick:
        configs = [
            {
                "label": "quick_I1_avgpool_lam20",
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
                "label": "I1_avgpool_lam20",
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
                "label": "I2_avgpool_lam25",
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
                "label": "I3_avgpool_lam30",
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
        configs=configs, architecture="resnet_cifar_avgpool",
        n_test=n_test, seed=args.seed,
    )

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY: v10 ResNetCIFAR AvgPool")
    print(f"{'='*70}")
    print(f"  {'Config':<30} {'Clean':>7} {'IBP Cert':>9} {'IBP Width':>11} "
          f"{'CROWN Cert':>11}")
    print(f"  {'-'*30} {'-'*7} {'-'*9} {'-'*11} {'-'*11}")
    for r in results:
        crown = r.get("crown_certified")
        crown_str = f"{crown*100:>10.1f}%" if crown is not None else f"{'--':>11}"
        print(f"  {r['label']:<30} {r['clean']*100:>6.1f}% "
              f"{r['ibp_certified']*100:>8.1f}% {r['ibp_width']:>11.4f} {crown_str}")

    # Comparison
    print(f"\n{'='*70}")
    print("COMPARISON vs previous best results")
    print(f"{'='*70}")
    baselines = {
        "H3 v9 (ResNet MaxPool)":  {"clean": 0.46, "cert": 0.29, "type": "IBP"},
        "E3 v6 (cifar_cnn_bn)":    {"clean": 0.29, "cert": 0.745, "type": "CROWN"},
        "F2 v7 (cifar_cnn_bn)":    {"clean": 0.35, "cert": 0.60, "type": "CROWN"},
    }
    for bname, bvals in baselines.items():
        print(f"  {bname}: clean={bvals['clean']*100:.0f}%, "
              f"{bvals['type']}={bvals['cert']*100:.1f}%")
    print()
    for r in results:
        cert_val = r.get("crown_certified", r["ibp_certified"])
        cert_type = "CROWN" if "crown_certified" in r else "IBP"
        # vs H3 (best ResNet)
        clean_d = (r["clean"] - 0.46) * 100
        cert_d = (cert_val - 0.29) * 100
        print(f"  {r['label']:<30} vs H3: clean {'+' if clean_d>0 else ''}{clean_d:.0f}pp, "
              f"{cert_type} {'+' if cert_d>0 else ''}{cert_d:.0f}pp")

    output_path = os.path.join(os.path.dirname(__file__), "v10_resnet_avgpool_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
