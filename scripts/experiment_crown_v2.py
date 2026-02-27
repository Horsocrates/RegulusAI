"""
Experiment CROWN v2: Diagnostics + Strided Conv Architecture + 3-seed.

Step 1: Diagnose 15 CROWN-only and 10 uncertified images from v1
Step 2: Train cnn_bn_v2 (strided conv replacing MaxPool) + certify IBP & CROWN
Step 3: 3-seed stability with best config
"""

import sys
import os
import time
import json
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import torch.nn as nn
from regulus.nn.benchmark import train_mnist_model, certify_mnist
from regulus.nn.verifier import NNVerificationEngine
from regulus.nn.crown import CROWNEngine


def step1_diagnostics():
    """Diagnose the 15 CROWN-only and 10 uncertified images."""
    print("=" * 80)
    print("STEP 1: Diagnostics — CROWN-only + Uncertified images")
    print("=" * 80)

    # Train same model as v1
    print("\n  Training model (same config as crown_v1)...")
    model = train_mnist_model(
        epochs=10, architecture="cnn_bn",
        ibp_loss_weight=5.0, weight_reg=0.001,
        ibp_eps_start=0.01, ibp_eps_end=0.01,
        seed=42, verbose=False,
    )

    # Load test data
    import torchvision
    import torchvision.transforms as transforms
    from regulus.nn.benchmark import _ensure_mnist

    _ensure_mnist("./data")
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,)),
    ])
    test_dataset = torchvision.datasets.MNIST(
        root="./data", train=False, download=False, transform=transform
    )

    ibp_engine = NNVerificationEngine(strategy="naive", fold_bn=True)
    crown_engine = CROWNEngine(alpha_mode="adaptive")
    model.eval()

    n_test = 200
    epsilon = 0.01

    crown_only = []
    neither = []
    both = []

    print("  Certifying 200 images with both IBP and CROWN...\n")

    for i in range(n_test):
        image, true_label = test_dataset[i]
        image_np = image.numpy().astype(np.float64)

        # Clean prediction
        with torch.no_grad():
            point_out = model(image.unsqueeze(0))
            point_pred = int(point_out.argmax(1).item())

        # IBP verification
        ibp_result = ibp_engine.verify_from_point(model, image_np, epsilon)

        # CROWN verification
        crown_result = crown_engine.compute_bounds(model, image_np, epsilon)
        crown_lo, crown_hi = crown_result.output_lo, crown_result.output_hi

        # Determine CROWN certification
        from regulus.nn.interval_tensor import IntervalTensor
        from regulus.analysis.reliability import ReliabilityAnalysis
        crown_output = IntervalTensor(
            np.maximum(crown_lo, ibp_result.output_lo),
            np.minimum(crown_hi, ibp_result.output_hi),
        )
        crown_analysis = ReliabilityAnalysis.classify(crown_output)
        crown_certified = crown_analysis["reliable"]

        ibp_width = float(np.max(ibp_result.output_width))
        crown_width = float(np.max(crown_output.width))
        ibp_margin = ibp_result.margin
        crown_margin = crown_analysis["gap"]

        info = {
            "idx": i,
            "true_label": int(true_label),
            "predicted": point_pred,
            "correct": point_pred == true_label,
            "ibp_certified": ibp_result.certified_robust,
            "crown_certified": crown_certified,
            "ibp_max_width": ibp_width,
            "crown_max_width": crown_width,
            "ibp_margin": ibp_margin,
            "crown_margin": crown_margin,
            "width_reduction": 1.0 - crown_width / ibp_width if ibp_width > 0 else 0,
            "ibp_layer_widths": ibp_result.layer_widths,
        }

        if ibp_result.certified_robust and crown_certified:
            both.append(info)
        elif crown_certified and not ibp_result.certified_robust:
            crown_only.append(info)
        elif not crown_certified:
            neither.append(info)

    # Report: CROWN-only images
    print(f"  === 15 CROWN-only images (certified by CROWN, not IBP) ===")
    print(f"  {'Idx':>5} {'Label':>5} {'IBP_w':>8} {'CROWN_w':>8} {'Reduction':>9} {'IBP_m':>8} {'CROWN_m':>8}")
    print(f"  {'-----':>5} {'-----':>5} {'--------':>8} {'--------':>8} {'---------':>9} {'--------':>8} {'--------':>8}")
    for img in crown_only:
        print(f"  {img['idx']:>5} {img['true_label']:>5} "
              f"{img['ibp_max_width']:>8.4f} {img['crown_max_width']:>8.4f} "
              f"{img['width_reduction']:>8.1%} "
              f"{img['ibp_margin']:>8.4f} {img['crown_margin']:>8.4f}")

    if crown_only:
        avg_ibp_w = np.mean([x['ibp_max_width'] for x in crown_only])
        avg_crown_w = np.mean([x['crown_max_width'] for x in crown_only])
        avg_ibp_m = np.mean([x['ibp_margin'] for x in crown_only])
        avg_crown_m = np.mean([x['crown_margin'] for x in crown_only])
        print(f"  {'AVG':>5} {'':>5} "
              f"{avg_ibp_w:>8.4f} {avg_crown_w:>8.4f} "
              f"{1.0 - avg_crown_w/avg_ibp_w:>8.1%} "
              f"{avg_ibp_m:>8.4f} {avg_crown_m:>8.4f}")

    # Report: uncertified images
    print(f"\n  === {len(neither)} Uncertified images (neither IBP nor CROWN) ===")
    print(f"  {'Idx':>5} {'Label':>5} {'Pred':>5} {'OK':>3} {'IBP_w':>8} {'CROWN_w':>8} {'Reduction':>9} {'IBP_m':>8} {'CROWN_m':>8}")
    print(f"  {'-----':>5} {'-----':>5} {'-----':>5} {'---':>3} {'--------':>8} {'--------':>8} {'---------':>9} {'--------':>8} {'--------':>8}")
    for img in neither:
        print(f"  {img['idx']:>5} {img['true_label']:>5} {img['predicted']:>5} "
              f"{'Y' if img['correct'] else 'N':>3} "
              f"{img['ibp_max_width']:>8.4f} {img['crown_max_width']:>8.4f} "
              f"{img['width_reduction']:>8.1%} "
              f"{img['ibp_margin']:>8.4f} {img['crown_margin']:>8.4f}")

    if neither:
        avg_ibp_w = np.mean([x['ibp_max_width'] for x in neither])
        avg_crown_w = np.mean([x['crown_max_width'] for x in neither])
        avg_ibp_m = np.mean([x['ibp_margin'] for x in neither])
        avg_crown_m = np.mean([x['crown_margin'] for x in neither])
        print(f"  {'AVG':>5} {'':>5} {'':>5} {'':>3} "
              f"{avg_ibp_w:>8.4f} {avg_crown_w:>8.4f} "
              f"{1.0 - avg_crown_w/avg_ibp_w:>8.1%} "
              f"{avg_ibp_m:>8.4f} {avg_crown_m:>8.4f}")

        # Layer-wise width analysis for worst uncertified image
        worst = max(neither, key=lambda x: x['crown_max_width'])
        print(f"\n  Worst uncertified (idx={worst['idx']}, label={worst['true_label']}):")
        print(f"    Per-layer IBP widths: {[f'{w:.3f}' for w in worst['ibp_layer_widths']]}")

    return {"crown_only": crown_only, "neither": neither, "both_count": len(both)}


def step2_strided_conv(seeds=None):
    """Train cnn_bn_v2 (strided conv) and certify with IBP + CROWN."""
    if seeds is None:
        seeds = [42]

    print("\n" + "=" * 80)
    print("STEP 2: Strided Conv Architecture (cnn_bn_v2)")
    print("=" * 80)

    all_results = []

    for seed in seeds:
        print(f"\n  --- Seed {seed} ---")
        print(f"  Training cnn_bn_v2 (strided conv, ibp=5.0, seed={seed})...")

        model = train_mnist_model(
            epochs=10, architecture="cnn_bn_v2",
            ibp_loss_weight=5.0, weight_reg=0.001,
            ibp_eps_start=0.01, ibp_eps_end=0.01,
            seed=seed, verbose=True,
        )

        n_test = 200
        epsilon = 0.01

        # IBP certification
        print(f"  Certifying with IBP...")
        ibp_report = certify_mnist(
            model, epsilon=epsilon, n_test=n_test,
            strategy="naive", architecture="cnn_bn_v2",
            verbose=True, progress_interval=40,
        )

        # CROWN certification
        print(f"  Certifying with CROWN...")
        crown_report = certify_mnist(
            model, epsilon=epsilon, n_test=n_test,
            strategy="crown", architecture="cnn_bn_v2",
            verbose=True, progress_interval=40,
        )

        result = {
            "seed": seed,
            "architecture": "cnn_bn_v2",
            "ibp_certified": ibp_report.certified_accuracy,
            "ibp_width": ibp_report.avg_output_max_width,
            "ibp_margin": ibp_report.avg_margin,
            "crown_certified": crown_report.certified_accuracy,
            "crown_width": crown_report.avg_output_max_width,
            "crown_margin": crown_report.avg_margin,
            "clean": ibp_report.clean_accuracy,
        }
        all_results.append(result)

        print(f"\n  Seed {seed} results:")
        print(f"    IBP:   {ibp_report.certified_accuracy:.1%} certified, width={ibp_report.avg_output_max_width:.4f}")
        print(f"    CROWN: {crown_report.certified_accuracy:.1%} certified, width={crown_report.avg_output_max_width:.4f}")

    return all_results


def step3_v1_stability(seeds=None):
    """3-seed stability test on v1 (cnn_bn with MaxPool) — the proven config."""
    if seeds is None:
        seeds = [42, 123, 7]

    print("\n" + "=" * 80)
    print("STEP 3: 3-Seed Stability (v1 cnn_bn + CROWN)")
    print("=" * 80)

    all_results = []

    for seed in seeds:
        print(f"\n  --- Seed {seed} ---")
        print(f"  Training cnn_bn (ibp=5.0, seed={seed})...")

        model = train_mnist_model(
            epochs=10, architecture="cnn_bn",
            ibp_loss_weight=5.0, weight_reg=0.001,
            ibp_eps_start=0.01, ibp_eps_end=0.01,
            seed=seed, verbose=True,
        )

        n_test = 200
        epsilon = 0.01

        # IBP certification
        print(f"  Certifying with IBP...")
        ibp_report = certify_mnist(
            model, epsilon=epsilon, n_test=n_test,
            strategy="naive", architecture="cnn_bn",
            verbose=True, progress_interval=40,
        )

        # CROWN certification
        print(f"  Certifying with CROWN...")
        crown_report = certify_mnist(
            model, epsilon=epsilon, n_test=n_test,
            strategy="crown", architecture="cnn_bn",
            verbose=True, progress_interval=40,
        )

        result = {
            "seed": seed,
            "architecture": "cnn_bn",
            "ibp_certified": ibp_report.certified_accuracy,
            "ibp_width": ibp_report.avg_output_max_width,
            "ibp_margin": ibp_report.avg_margin,
            "crown_certified": crown_report.certified_accuracy,
            "crown_width": crown_report.avg_output_max_width,
            "crown_margin": crown_report.avg_margin,
            "clean": ibp_report.clean_accuracy,
        }
        all_results.append(result)

        print(f"\n  Seed {seed} results:")
        print(f"    IBP:   {ibp_report.certified_accuracy:.1%} certified, width={ibp_report.avg_output_max_width:.4f}")
        print(f"    CROWN: {crown_report.certified_accuracy:.1%} certified, width={crown_report.avg_output_max_width:.4f}")

    # Summary table
    print(f"\n  {'Seed':>6} {'IBP_cert':>10} {'CROWN_cert':>10} {'IBP_w':>10} {'CROWN_w':>10} {'Clean':>8}")
    print(f"  {'------':>6} {'----------':>10} {'----------':>10} {'----------':>10} {'----------':>10} {'--------':>8}")
    for r in all_results:
        print(f"  {r['seed']:>6} {r['ibp_certified']:>9.1%} {r['crown_certified']:>9.1%} "
              f"{r['ibp_width']:>10.4f} {r['crown_width']:>10.4f} {r['clean']:>7.1%}")

    ibp_certs = [r['ibp_certified'] for r in all_results]
    crown_certs = [r['crown_certified'] for r in all_results]
    print(f"\n  IBP mean: {np.mean(ibp_certs):.1%} +/- {np.std(ibp_certs):.1%}")
    print(f"  CROWN mean: {np.mean(crown_certs):.1%} +/- {np.std(crown_certs):.1%}")

    return all_results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", type=int, default=0, help="1=diag, 2=v2 arch, 3=3-seed, 0=all")
    args = parser.parse_args()

    results = {}

    if args.step in (0, 1):
        diag = step1_diagnostics()
        results["diagnostics"] = {
            "crown_only_count": len(diag["crown_only"]),
            "neither_count": len(diag["neither"]),
            "both_count": diag["both_count"],
            "crown_only": diag["crown_only"],
            "neither": diag["neither"],
        }

    if args.step in (0, 2):
        v2_results = step2_strided_conv(seeds=[42])
        results["v2_single"] = v2_results

    if args.step in (0, 3):
        # 3-seed stability on v1 (cnn_bn, the proven config)
        v1_3seed = step3_v1_stability(seeds=[42, 123, 7])
        results["v1_3seed"] = v1_3seed

        certs = [r["crown_certified"] for r in v1_3seed]
        print(f"\n  3-seed CROWN stability: {np.mean(certs):.1%} +/- {np.std(certs):.1%}")

    # Summary comparison
    if args.step == 0 and "v2_single" in results:
        print("\n" + "=" * 80)
        print("FULL COMPARISON")
        print("=" * 80)
        v2 = results["v2_single"][0]
        print(f"  {'':25} {'v1 cnn_bn':>12} {'v2 strided':>12} {'Delta':>10}")
        print(f"  {'':25} {'MaxPool':>12} {'Conv':>12} {'':>10}")
        print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*10}")
        print(f"  {'IBP certified':25} {'87.5%':>12} {v2['ibp_certified']:>11.1%} {v2['ibp_certified']-0.875:>+9.1%}")
        print(f"  {'CROWN certified':25} {'95.0%':>12} {v2['crown_certified']:>11.1%} {v2['crown_certified']-0.95:>+9.1%}")
        print(f"  {'IBP width':25} {'1.9657':>12} {v2['ibp_width']:>12.4f} {v2['ibp_width']-1.9657:>+10.4f}")
        print(f"  {'CROWN width':25} {'1.0646':>12} {v2['crown_width']:>12.4f} {v2['crown_width']-1.0646:>+10.4f}")
        print(f"  {'Clean accuracy':25} {'98.0%':>12} {v2['clean']:>11.1%}")

    # Save
    output_file = f"scripts/crown_v2_results_step{args.step}.json"

    # Make results JSON-serializable
    def to_serializable(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=to_serializable)
    print(f"\n  Results saved to {output_file}")


if __name__ == "__main__":
    main()
