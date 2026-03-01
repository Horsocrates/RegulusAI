"""
Experiment v11: CROWN certification for ResNetCIFAR (MaxPool).

Phase D Step 2: Now that CROWN supports ResBlock skip connections,
re-run H3 (the best model) with CROWN certification.

Background:
  - H3 (MaxPool ResNet, λ=0.20): 46% clean, 29% IBP cert @ ε=0.005
  - On cifar_cnn_bn, CROWN improved cert 2-3x (29% IBP → 74.5% CROWN)
  - Expected: CROWN on H3 should give 50-70% cert

Plan:
  1. Train H3 config (ResNet MaxPool, λ=0.20, 100 epochs)
  2. Certify with IBP (baseline, should match ~29%)
  3. Certify with CROWN(fc) — the new capability
  4. Compare widths and cert rates

This also serves as an integration test for CROWN + ResBlock.
"""

import argparse
import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from regulus.nn.benchmark import train_cifar_diff_ibp, certify_cifar


def main():
    parser = argparse.ArgumentParser(description="CIFAR-10 v11: CROWN for ResNet")
    parser.add_argument("--n-test", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quick", action="store_true",
                        help="Quick smoke test (30 epochs, 20 images)")
    parser.add_argument("--skip-train", action="store_true",
                        help="Skip training, load saved model")
    args = parser.parse_args()

    epochs = 30 if args.quick else 100
    n_test = 20 if args.quick else args.n_test
    eps = 0.005

    label = "H3_crown" if not args.quick else "quick_H3_crown"

    print(f"\n{'='*70}")
    print(f"v11: CROWN certification for ResNetCIFAR (MaxPool)")
    print(f"Config: λ=0.20, ε={eps}, epochs={epochs}")
    print(f"{'='*70}")

    # Step 1: Train H3 (same config as v9)
    print(f"\n[Step 1] Training ResNetCIFAR (MaxPool)...")
    t0 = time.perf_counter()
    model = train_cifar_diff_ibp(
        architecture="resnet_cifar",
        epochs=epochs,
        ibp_weight=0.20,
        eps_start=0.001,
        eps_end=eps,
        warmup_fraction=0.25,
        ramp_fraction=0.35,
        grad_clip=1.0,
        lr_schedule="cosine",
        margin_weight=0.0,
        seed=args.seed,
        verbose=True,
    )
    train_time = time.perf_counter() - t0
    print(f"\n  Training time: {train_time:.1f}s")

    results = {"label": label, "train_time": round(train_time, 1)}

    # Step 2: IBP certification (baseline)
    print(f"\n[Step 2] IBP certification ({n_test} images, ε={eps})...")
    report_ibp = certify_cifar(
        model, epsilon=eps, n_test=n_test,
        strategy="naive", architecture="resnet_cifar",
        verbose=True, progress_interval=25,
    )
    print(f"\n  IBP: clean={report_ibp.clean_accuracy*100:.1f}%, "
          f"cert={report_ibp.certified_accuracy*100:.1f}%, "
          f"width={report_ibp.avg_output_max_width:.4f}")
    results["clean"] = report_ibp.clean_accuracy
    results["ibp_cert"] = report_ibp.certified_accuracy
    results["ibp_width"] = report_ibp.avg_output_max_width

    # Step 3: CROWN(fc) certification
    print(f"\n[Step 3] CROWN(fc) certification ({n_test} images, ε={eps})...")
    try:
        report_crown = certify_cifar(
            model, epsilon=eps, n_test=n_test,
            strategy="crown", architecture="resnet_cifar",
            crown_depth="fc", verbose=True, progress_interval=25,
        )
        print(f"\n  CROWN(fc): clean={report_crown.clean_accuracy*100:.1f}%, "
              f"cert={report_crown.certified_accuracy*100:.1f}%, "
              f"width={report_crown.avg_output_max_width:.4f}")
        results["crown_cert"] = report_crown.certified_accuracy
        results["crown_width"] = report_crown.avg_output_max_width
        results["crown_improvement"] = round(
            (1.0 - report_crown.avg_output_max_width / max(report_ibp.avg_output_max_width, 1e-6)) * 100, 1
        )
    except Exception as e:
        print(f"\n  CROWN FAILED: {e}")
        results["crown_error"] = str(e)

    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY: v11 CROWN for ResNetCIFAR")
    print(f"{'='*70}")
    print(f"  Clean accuracy:  {results['clean']*100:.1f}%")
    print(f"  IBP certified:   {results['ibp_cert']*100:.1f}%  (width: {results['ibp_width']:.4f})")
    if "crown_cert" in results:
        print(f"  CROWN certified: {results['crown_cert']*100:.1f}%  (width: {results['crown_width']:.4f})")
        print(f"  CROWN improvement: {results['crown_improvement']}% width reduction")
    elif "crown_error" in results:
        print(f"  CROWN: FAILED — {results['crown_error']}")

    # Comparison
    print(f"\n{'='*70}")
    print("COMPARISON vs baselines (all at ε=0.005)")
    print(f"{'='*70}")
    baselines = {
        "H3 v9 (MaxPool, IBP only)": {"clean": 0.46, "cert": 0.29, "type": "IBP"},
        "E3 v6 (cifar_cnn_bn)":      {"clean": 0.29, "cert": 0.745, "type": "CROWN"},
        "v4B v5 (cifar_cnn_bn)":      {"clean": 0.33, "cert": 0.71, "type": "CROWN"},
        "F2 v7 (cifar_cnn_bn)":       {"clean": 0.35, "cert": 0.60, "type": "CROWN"},
    }
    for bname, bvals in baselines.items():
        print(f"  {bname}: clean={bvals['clean']*100:.0f}%, "
              f"{bvals['type']}={bvals['cert']*100:.1f}%")

    if "crown_cert" in results:
        crown_cert = results["crown_cert"]
        print(f"\n  v11 (ResNet+CROWN): clean={results['clean']*100:.1f}%, "
              f"CROWN={crown_cert*100:.1f}%")
        # Check target: clean ≥ 45% AND cert ≥ 40%
        target_clean = results['clean'] >= 0.45
        target_cert = crown_cert >= 0.40
        if target_clean and target_cert:
            print(f"\n  ✓ TARGET MET: clean ≥ 45% AND CROWN cert ≥ 40%!")
        else:
            issues = []
            if not target_clean:
                issues.append(f"clean {results['clean']*100:.0f}% < 45%")
            if not target_cert:
                issues.append(f"cert {crown_cert*100:.0f}% < 40%")
            print(f"\n  ✗ TARGET NOT MET: {', '.join(issues)}")

    output_path = os.path.join(os.path.dirname(__file__), "v11_crown_resblock_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
