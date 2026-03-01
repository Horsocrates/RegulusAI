"""
Experiment v9: CIFAR-10 — ResNetCIFAR + 3-Phase Schedule.

Phase D Step 1: Break the 35% clean accuracy ceiling by upgrading from
cifar_cnn_bn (~1.1M params, no skip connections) to ResNetCIFAR (~137K params,
skip connections).

Why ResNetCIFAR should help:
  1. Skip connections let gradients flow through residual path during IBP training
  2. Much smaller FC layer (4096→10 vs 4096→256→10) reduces bound explosion
  3. IBP through addition is EXACT: [a_lo+b_lo, a_hi+b_hi], so skip connections
     don't add looseness to bounds
  4. If inner path g(x) learns small updates, width(g(x)) stays small

Architecture (~137K params):
  stem: Conv2d(3,32,3,pad=1) → BN2d(32) → ReLU
  ResBlock(32) → MaxPool(2)                     [32→16]
  expand: Conv2d(32,64,1) → BN2d(64) → ReLU    [channel expand]
  ResBlock(64) → MaxPool(2)                     [16→8]
  Flatten → Linear(4096,10)

3-Phase Training Schedule:
  Phase 1 (clean):    [0, 30%] → λ=0, ε=ε_start  (build features)
  Phase 2 (ramp):     [30%, 60%] → λ ramps 0→λ_max, ε ramps  (gradual IBP)
  Phase 3 (robust):   [60%, 100%] → λ=λ_max, ε=ε_end  (full IBP pressure)

Anti-collapse watchdog:
  If ibp_loss > 2.25 (near ln(10)≈2.302) for 3+ epochs → model is collapsing

Configs:
  H1: λ=0.10, ε=0.005 — direct comparison with F2 (35%/60% on cifar_cnn_bn)
  H2: λ=0.15, ε=0.005 — in the "dead zone" for cifar_cnn_bn, but ResNet may fix it
  H3: λ=0.20, ε=0.005 — direct comparison with E3 (29%/74.5% on cifar_cnn_bn)

Target: clean ≥ 50% AND CROWN cert ≥ 40% at ε=0.005
"""

import argparse
import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from regulus.nn.benchmark import train_cifar_diff_ibp, certify_cifar


COLLAPSE_THRESHOLD = 2.25  # ln(10) ≈ 2.302, alert at 2.25


def run_experiment(configs, architecture="resnet_cifar", n_test=100, seed=42, verbose=True):
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
        if report_ibp.avg_output_max_width < 0.001:
            print(f"  ⚠ WARNING: width near zero — possible collapse to constant output")

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
    parser = argparse.ArgumentParser(description="CIFAR-10 v9: ResNetCIFAR")
    parser.add_argument("--arch", type=str, default="resnet_cifar")
    parser.add_argument("--n-test", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quick", action="store_true",
                        help="Quick smoke test (30 epochs, 20 images)")
    args = parser.parse_args()

    if args.quick:
        configs = [
            {
                "label": "quick_H1_resnet_lam10",
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
                "label": "H1_resnet_lam10",
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
                "label": "H2_resnet_lam15",
                "epochs": 100,
                "ibp_weight": 0.15,
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
                "label": "H3_resnet_lam20",
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
        configs=configs, architecture=args.arch,
        n_test=n_test, seed=args.seed,
    )

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY: v9 ResNetCIFAR")
    print(f"{'='*70}")
    print(f"  {'Config':<30} {'Clean':>7} {'IBP Cert':>9} {'IBP Width':>11} "
          f"{'CROWN Cert':>11}")
    print(f"  {'-'*30} {'-'*7} {'-'*9} {'-'*11} {'-'*11}")
    for r in results:
        crown = r.get("crown_certified")
        crown_str = f"{crown*100:>10.1f}%" if crown is not None else f"{'--':>11}"
        print(f"  {r['label']:<30} {r['clean']*100:>6.1f}% "
              f"{r['ibp_certified']*100:>8.1f}% {r['ibp_width']:>11.4f} {crown_str}")

    # Comparison with cifar_cnn_bn baselines
    print(f"\n{'='*70}")
    print("COMPARISON vs cifar_cnn_bn baselines")
    print(f"{'='*70}")
    baselines = {
        "E3 (lam20, cifar_cnn_bn)": {"clean": 0.29, "crown": 0.745},
        "v4B (lam30, cifar_cnn_bn)": {"clean": 0.33, "crown": 0.71},
        "F2 (lam10, cifar_cnn_bn)": {"clean": 0.35, "crown": 0.60},
    }
    for bname, bvals in baselines.items():
        print(f"  {bname}: clean={bvals['clean']*100:.0f}%, CROWN={bvals['crown']*100:.1f}%")

    print()
    for r in results:
        crown_val = r.get("crown_certified", r["ibp_certified"])
        # Compare vs F2 (best clean with cert>40%)
        clean_delta = (r["clean"] - 0.35) * 100
        cert_delta = (crown_val - 0.60) * 100
        clean_arrow = "+" if clean_delta > 0 else ""
        cert_arrow = "+" if cert_delta > 0 else ""
        print(f"  {r['label']:<30} vs F2: clean {clean_arrow}{clean_delta:.0f}pp, "
              f"CROWN {cert_arrow}{cert_delta:.0f}pp")

    # Goal check
    print(f"\n{'='*70}")
    print("GOAL CHECK: clean >= 50% AND CROWN cert >= 40%")
    print(f"{'='*70}")
    for r in results:
        crown_val = r.get("crown_certified", r["ibp_certified"])
        clean_ok = r["clean"] >= 0.50
        cert_ok = crown_val >= 0.40
        status = "PASS" if (clean_ok and cert_ok) else "FAIL"
        print(f"  {r['label']:<30} {status}  "
              f"(clean {'OK' if clean_ok else 'X'} {r['clean']*100:.0f}%, "
              f"CROWN {'OK' if cert_ok else 'X'} {crown_val*100:.0f}%)")

    output_path = os.path.join(os.path.dirname(__file__), "v9_resnet_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
