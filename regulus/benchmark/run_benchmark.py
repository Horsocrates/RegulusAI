"""
Regulus Benchmark: Interval Arithmetic vs MC Dropout vs Deep Ensembles vs Temperature Scaling

Usage:
    python -m regulus.benchmark.run_benchmark
    python -m regulus.benchmark.run_benchmark --datasets breast_cancer credit
    python -m regulus.benchmark.run_benchmark --quick   (subset test data for speed)
"""

from __future__ import annotations

import sys
import time

from regulus.benchmark.runner import BenchmarkRunner
from regulus.benchmark.report import generate_report


def main():
    args = sys.argv[1:]

    # Parse simple args
    quick = "--quick" in args
    datasets = None
    if "--datasets" in args:
        idx = args.index("--datasets")
        datasets = []
        for a in args[idx + 1:]:
            if a.startswith("--"):
                break
            datasets.append(a)

    if not datasets:
        # Default: breast_cancer + credit (MNIST is slow)
        datasets = ["breast_cancer", "credit"]
        if "--mnist" in args or "--all" in args:
            datasets.append("mnist")

    print("=" * 60)
    print("REGULUS UNCERTAINTY QUANTIFICATION BENCHMARK")
    print("=" * 60)
    print(f"Datasets: {datasets}")
    print(f"Quick mode: {quick}")
    print()

    runner = BenchmarkRunner(
        datasets=datasets,
        regulus_eps=[0.01, 0.05, 0.1],
        mc_samples=50,
        ensemble_k=5,
        subset_test=500 if quick else None,
    )

    t0 = time.time()
    results = runner.run()
    t_total = time.time() - t0

    print(f"\nTotal benchmark time: {t_total:.1f}s")

    # Generate report
    df = generate_report(results)

    print("\n" + "=" * 60)
    print("BENCHMARK COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
