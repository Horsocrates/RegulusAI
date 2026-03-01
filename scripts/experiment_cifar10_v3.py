"""
Experiment v3: CIFAR-10 certification with AvgPool architecture.

Key insight from MNIST: AvgPool (linear op) vs MaxPool reduced IBP width
from ~11 to ~1.0 and achieved 91.5% IBP certified. CIFAR v2 with MaxPool
had widths of 60K-146K and 0% certified.

Plan:
  Phase 1: Clean baseline — AvgPool vs MaxPool side-by-side (no IBP)
  Phase 2: Gentle IBP training on best architecture (from v2 recipe)
  Phase 3: CROWN if IBP width < 5
"""

import argparse
import json
import time
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from regulus.nn.benchmark import train_cifar_model, certify_cifar


def run_phase1_clean(
    n_test: int = 100,
    epochs: int = 30,
    seed: int = 42,
    verbose: bool = True,
):
    """Phase 1: Compare AvgPool vs MaxPool clean baselines."""
    print("=" * 70)
    print(f"PHASE 1: CLEAN BASELINE — AvgPool vs MaxPool, {epochs} epochs")
    print("=" * 70)

    architectures = ["cifar_cnn_bn", "cifar_cnn_bn_avgpool"]
    results = {}

    for arch in architectures:
        print(f"\n{'-'*60}")
        print(f"  Architecture: {arch}")
        print(f"{'-'*60}")

        t0 = time.perf_counter()
        model = train_cifar_model(
            architecture=arch,
            epochs=epochs,
            lr=0.001,
            lr_schedule="cosine",
            ibp_loss_weight=0.0,
            weight_reg=0.0,
            augment=True,
            seed=seed,
            verbose=verbose,
        )
        train_time = time.perf_counter() - t0
        print(f"  Training time: {train_time:.1f}s")

        # IBP certification (measure width baseline)
        print(f"\n  Certifying with IBP ({n_test} images, eps=0.01)...")
        report_ibp = certify_cifar(
            model, epsilon=0.01, n_test=n_test,
            strategy="naive", architecture=arch,
            verbose=verbose, progress_interval=50,
        )

        # Also try CROWN right away to see improvement
        print(f"\n  Certifying with CROWN-fc ({n_test} images, eps=0.01)...")
        report_crown = certify_cifar(
            model, epsilon=0.01, n_test=n_test,
            strategy="crown", architecture=arch,
            crown_depth="fc",
            verbose=verbose, progress_interval=50,
        )

        results[arch] = {
            "clean": report_ibp.clean_accuracy,
            "ibp_certified": report_ibp.certified_accuracy,
            "ibp_width": report_ibp.avg_output_max_width,
            "ibp_margin": report_ibp.avg_margin,
            "crown_certified": report_crown.certified_accuracy,
            "crown_width": report_crown.avg_output_max_width,
            "crown_margin": report_crown.avg_margin,
            "train_time": round(train_time, 1),
        }

        print(f"\n  {arch}:")
        print(f"    Clean:  {report_ibp.clean_accuracy*100:.1f}%")
        print(f"    IBP:    cert={report_ibp.certified_accuracy*100:.1f}%, "
              f"width={report_ibp.avg_output_max_width:.4f}")
        print(f"    CROWN:  cert={report_crown.certified_accuracy*100:.1f}%, "
              f"width={report_crown.avg_output_max_width:.4f}")

    # Summary
    print(f"\n{'='*70}")
    print("PHASE 1 SUMMARY")
    print(f"{'='*70}")
    print(f"  {'Arch':<25} {'Clean':>7} {'IBP Cert':>9} {'IBP Width':>11} "
          f"{'CROWN Cert':>11} {'CROWN Width':>12}")
    print(f"  {'-'*25} {'-'*7} {'-'*9} {'-'*11} {'-'*11} {'-'*12}")
    for arch, r in results.items():
        print(f"  {arch:<25} {r['clean']*100:>6.1f}% {r['ibp_certified']*100:>8.1f}% "
              f"{r['ibp_width']:>11.2f} {r['crown_certified']*100:>10.1f}% "
              f"{r['crown_width']:>12.2f}")

    return results


def run_phase2_ibp(
    architecture: str,
    n_test: int = 100,
    epochs: int = 30,
    seed: int = 42,
    verbose: bool = True,
):
    """Phase 2: Gentle IBP training on chosen architecture."""
    print(f"\n{'='*70}")
    print(f"PHASE 2: GENTLE IBP TRAINING — {architecture}, {epochs} epochs")
    print(f"{'='*70}")

    configs = [
        {
            "label": "A_gentle_ramp",
            "ibp_loss_weight": 0.5,
            "ibp_eps_start": 0.001,
            "ibp_eps_end": 0.01,
            "flat_eps": False,
            "lambda_ramp": True,
            "lambda_ramp_fraction": 0.5,
            "lambda_warmup_fraction": 0.3,
            "weight_reg": 0.001,
            "lr_schedule": "cosine",
            "grad_clip": 1.0,
        },
        {
            "label": "B_stronger_reg",
            "ibp_loss_weight": 1.0,
            "ibp_eps_start": 0.001,
            "ibp_eps_end": 0.01,
            "flat_eps": False,
            "lambda_ramp": True,
            "lambda_ramp_fraction": 0.5,
            "lambda_warmup_fraction": 0.3,
            "weight_reg": 0.01,
            "lr_schedule": "cosine",
            "grad_clip": 1.0,
        },
        {
            "label": "C_small_eps",
            "ibp_loss_weight": 0.5,
            "ibp_eps_start": 0.001,
            "ibp_eps_end": 0.005,
            "flat_eps": False,
            "lambda_ramp": True,
            "lambda_ramp_fraction": 0.5,
            "lambda_warmup_fraction": 0.3,
            "weight_reg": 0.001,
            "lr_schedule": "cosine",
            "grad_clip": 1.0,
        },
    ]

    results = []
    for cfg in configs:
        label = cfg["label"]
        print(f"\n{'-'*60}")
        print(f"  Config: {label}")
        for k, v in cfg.items():
            if k != "label":
                print(f"    {k}: {v}")
        print(f"{'-'*60}")

        t0 = time.perf_counter()
        model = train_cifar_model(
            architecture=architecture,
            epochs=epochs,
            lr=0.001,
            lr_schedule=cfg["lr_schedule"],
            ibp_loss_weight=cfg["ibp_loss_weight"],
            ibp_eps_start=cfg["ibp_eps_start"],
            ibp_eps_end=cfg["ibp_eps_end"],
            ibp_check_interval=50,
            ibp_n_samples=4,
            ibp_target_margin=0.1,
            weight_reg=cfg["weight_reg"],
            flat_eps=cfg["flat_eps"],
            lambda_ramp=cfg["lambda_ramp"],
            lambda_ramp_fraction=cfg["lambda_ramp_fraction"],
            lambda_warmup_fraction=cfg["lambda_warmup_fraction"],
            augment=True,
            seed=seed,
            grad_clip=cfg["grad_clip"],
            checkpoint=True,
            checkpoint_n_samples=20,
            verbose=verbose,
        )
        train_time = time.perf_counter() - t0

        # IBP certification
        print(f"\n  IBP certification ({n_test} images)...")
        report_ibp = certify_cifar(
            model, epsilon=cfg["ibp_eps_end"], n_test=n_test,
            strategy="naive", architecture=architecture,
            verbose=verbose, progress_interval=50,
        )

        result = {
            "label": label,
            "config": {k: v for k, v in cfg.items() if k != "label"},
            "clean": report_ibp.clean_accuracy,
            "ibp_certified": report_ibp.certified_accuracy,
            "ibp_width": report_ibp.avg_output_max_width,
            "ibp_margin": report_ibp.avg_margin,
            "train_time": round(train_time, 1),
        }

        # CROWN if IBP width is promising
        if report_ibp.avg_output_max_width < 50.0:
            print(f"\n  Width={report_ibp.avg_output_max_width:.2f} — running CROWN(fc)...")
            report_crown = certify_cifar(
                model, epsilon=cfg["ibp_eps_end"], n_test=n_test,
                strategy="crown", architecture=architecture,
                crown_depth="fc",
                verbose=verbose, progress_interval=50,
            )
            result["crown_certified"] = report_crown.certified_accuracy
            result["crown_width"] = report_crown.avg_output_max_width
            result["crown_margin"] = report_crown.avg_margin
            print(f"  CROWN: cert={report_crown.certified_accuracy*100:.1f}%, "
                  f"width={report_crown.avg_output_max_width:.4f}")

        print(f"\n  {label}: clean={report_ibp.clean_accuracy*100:.1f}%, "
              f"IBP cert={report_ibp.certified_accuracy*100:.1f}%, "
              f"width={report_ibp.avg_output_max_width:.2f}")

        results.append(result)

    # Summary
    print(f"\n{'='*70}")
    print(f"PHASE 2 SUMMARY ({architecture})")
    print(f"{'='*70}")
    print(f"  {'Config':<20} {'Clean':>7} {'IBP Cert':>9} {'IBP Width':>11} "
          f"{'CROWN Cert':>11}")
    print(f"  {'-'*20} {'-'*7} {'-'*9} {'-'*11} {'-'*11}")
    for r in results:
        crown = r.get("crown_certified")
        crown_str = f"{crown*100:>10.1f}%" if crown is not None else f"{'—':>11}"
        print(f"  {r['label']:<20} {r['clean']*100:>6.1f}% "
              f"{r['ibp_certified']*100:>8.1f}% {r['ibp_width']:>11.2f} {crown_str}")

    return results


def main():
    parser = argparse.ArgumentParser(description="CIFAR-10 v3: AvgPool experiment")
    parser.add_argument("--phase", type=str, default="all",
                        choices=["clean", "ibp", "all"])
    parser.add_argument("--n-test", type=int, default=100)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    all_results = {}

    if args.phase in ("clean", "all"):
        phase1 = run_phase1_clean(
            n_test=args.n_test, epochs=args.epochs, seed=args.seed,
        )
        all_results["phase1_clean"] = phase1

    if args.phase in ("ibp", "all"):
        # Use AvgPool architecture for IBP phase
        arch = "cifar_cnn_bn_avgpool"
        phase2 = run_phase2_ibp(
            architecture=arch,
            n_test=args.n_test, epochs=args.epochs, seed=args.seed,
        )
        all_results["phase2_ibp"] = phase2

    # Save
    output_path = os.path.join(os.path.dirname(__file__), "v3_cifar10_avgpool_results.json")
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
