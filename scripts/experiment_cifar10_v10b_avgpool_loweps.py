"""
Experiment v10b: CIFAR-10 — ResNetCIFAR_AvgPool with REDUCED training epsilon.

v10 failure analysis:
  - I1 (AvgPool, λ=0.20, ε=0.005) collapsed to 18.4% clean
  - AvgPool gives tighter bounds → same ε pushes IBP loss harder
  - v9 H3 (MaxPool, λ=0.20, ε=0.005) worked at 46% because MaxPool bounds are loose

v10b hypothesis:
  Train at ε=0.003 (reduced perturbation) to prevent collapse.
  Certify at ε=0.005 (same target) to compare vs baselines.
  If model trains stably → tighter AvgPool bounds should give BETTER cert at ε=0.005.

Configs (100 epochs):
  I4: λ=0.10, ε_train=0.003, warmup=0.30, ramp=0.40 — gentle
  I5: λ=0.15, ε_train=0.003, warmup=0.30, ramp=0.35 — moderate
  I6: λ=0.20, ε_train=0.003, warmup=0.35, ramp=0.35 — aggressive

Target: clean ≥ 45% AND IBP cert ≥ 35% at ε=0.005
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
        eps_certify = cfg.pop("eps_certify", 0.005)  # certification epsilon
        print(f"\n{'='*70}")
        print(f"CONFIG: {label}")
        print(f"Architecture: {architecture}")
        print(f"Training ε: {cfg.get('eps_end', 0.003)}, Certification ε: {eps_certify}")
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

        # Certify at TRAINING epsilon first
        eps_train = cfg.get("eps_end", 0.003)
        print(f"\n  IBP certification ({n_test} images, eps={eps_train} [train])...")
        report_train = certify_cifar(
            model, epsilon=eps_train, n_test=n_test,
            strategy="naive", architecture=architecture,
            verbose=verbose, progress_interval=50,
        )
        print(f"  IBP@{eps_train}: clean={report_train.clean_accuracy*100:.1f}%, "
              f"cert={report_train.certified_accuracy*100:.1f}%, "
              f"width={report_train.avg_output_max_width:.4f}")

        result = {
            "label": label, "config": cfg,
            "architecture": architecture,
            "clean": report_train.clean_accuracy,
            "ibp_certified_train_eps": report_train.certified_accuracy,
            "ibp_width_train_eps": report_train.avg_output_max_width,
            "train_time": round(train_time, 1),
        }

        # Also certify at TARGET epsilon (0.005)
        if eps_certify != eps_train:
            print(f"\n  IBP certification ({n_test} images, eps={eps_certify} [target])...")
            report_target = certify_cifar(
                model, epsilon=eps_certify, n_test=n_test,
                strategy="naive", architecture=architecture,
                verbose=verbose, progress_interval=50,
            )
            print(f"  IBP@{eps_certify}: cert={report_target.certified_accuracy*100:.1f}%, "
                  f"width={report_target.avg_output_max_width:.4f}")
            result["ibp_certified_target_eps"] = report_target.certified_accuracy
            result["ibp_width_target_eps"] = report_target.avg_output_max_width

        # Collapse check
        if report_train.clean_accuracy < 0.12:
            print(f"  ⚠ COLLAPSE DETECTED: clean < 12%")
        if report_train.avg_output_max_width < 0.001:
            print(f"  ⚠ WARNING: width near zero — constant output")

        # Try CROWN (will likely fail on ResBlock, but try anyway)
        if report_train.avg_output_max_width < 50.0:
            print(f"\n  Running CROWN(fc) @ eps={eps_certify}...")
            try:
                report_crown = certify_cifar(
                    model, epsilon=eps_certify, n_test=n_test,
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
    parser = argparse.ArgumentParser(description="CIFAR-10 v10b: AvgPool ResNet, reduced training ε")
    parser.add_argument("--n-test", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--quick", action="store_true",
                        help="Quick smoke test (30 epochs, 20 images)")
    args = parser.parse_args()

    if args.quick:
        configs = [
            {
                "label": "quick_I4_avgpool_lam10_eps3",
                "epochs": 30,
                "ibp_weight": 0.10,
                "eps_start": 0.0005,
                "eps_end": 0.003,
                "eps_certify": 0.005,
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
                "label": "I4_avgpool_lam10_eps3",
                "epochs": 100,
                "ibp_weight": 0.10,
                "eps_start": 0.0005,
                "eps_end": 0.003,
                "eps_certify": 0.005,
                "warmup_fraction": 0.30,
                "ramp_fraction": 0.40,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
            {
                "label": "I5_avgpool_lam15_eps3",
                "epochs": 100,
                "ibp_weight": 0.15,
                "eps_start": 0.0005,
                "eps_end": 0.003,
                "eps_certify": 0.005,
                "warmup_fraction": 0.30,
                "ramp_fraction": 0.35,
                "weight_reg": 0.0,
                "grad_clip": 1.0,
                "lr_schedule": "cosine",
                "margin_weight": 0.0,
            },
            {
                "label": "I6_avgpool_lam20_eps3",
                "epochs": 100,
                "ibp_weight": 0.20,
                "eps_start": 0.0005,
                "eps_end": 0.003,
                "eps_certify": 0.005,
                "warmup_fraction": 0.35,
                "ramp_fraction": 0.35,
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
    print("SUMMARY: v10b ResNetCIFAR AvgPool (ε_train=0.003)")
    print(f"{'='*70}")
    print(f"  {'Config':<30} {'Clean':>7} {'IBP@.003':>9} {'IBP@.005':>9} "
          f"{'Width@.003':>11} {'Width@.005':>11}")
    print(f"  {'-'*30} {'-'*7} {'-'*9} {'-'*9} {'-'*11} {'-'*11}")
    for r in results:
        cert_train = r.get("ibp_certified_train_eps", 0)
        cert_target = r.get("ibp_certified_target_eps", 0)
        w_train = r.get("ibp_width_train_eps", 0)
        w_target = r.get("ibp_width_target_eps", 0)
        print(f"  {r['label']:<30} {r['clean']*100:>6.1f}% "
              f"{cert_train*100:>8.1f}% {cert_target*100:>8.1f}% "
              f"{w_train:>11.4f} {w_target:>11.4f}")

    # Comparison
    print(f"\n{'='*70}")
    print("COMPARISON vs previous best results (all at ε=0.005)")
    print(f"{'='*70}")
    baselines = {
        "H3 v9 (ResNet MaxPool)":  {"clean": 0.46, "cert": 0.29, "type": "IBP"},
        "I1 v10 (ResNet AvgPool)": {"clean": 0.184, "cert": 0.0, "type": "IBP (COLLAPSED)"},
        "E3 v6 (cifar_cnn_bn)":    {"clean": 0.29, "cert": 0.745, "type": "CROWN"},
        "F2 v7 (cifar_cnn_bn)":    {"clean": 0.35, "cert": 0.60, "type": "CROWN"},
    }
    for bname, bvals in baselines.items():
        print(f"  {bname}: clean={bvals['clean']*100:.1f}%, "
              f"{bvals['type']}={bvals['cert']*100:.1f}%")
    print()
    for r in results:
        cert_val = r.get("ibp_certified_target_eps", r.get("ibp_certified_train_eps", 0))
        # vs H3 (best ResNet)
        clean_d = (r["clean"] - 0.46) * 100
        cert_d = (cert_val - 0.29) * 100
        print(f"  {r['label']:<30} vs H3: clean {'+' if clean_d>0 else ''}{clean_d:.0f}pp, "
              f"IBP@.005 {'+' if cert_d>0 else ''}{cert_d:.0f}pp")

    output_path = os.path.join(os.path.dirname(__file__), "v10b_avgpool_loweps_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
