"""
Integration benchmarks for Coq-verified components.

Validates that ported Coq theorems hold in Python and measures
performance characteristics of each new module.

Benchmark 1: EVT_idx argmax — correctness vs built-in max + speed
Benchmark 2: Verified softmax — soundness + tightness vs old heuristic
Benchmark 3: Composition width — chain_width_product prediction accuracy
Benchmark 4: Trisection — certified gap sizes + convergence rate
Benchmark 5: End-to-end NN verification (requires torch — skip if unavailable)

Run: uv run python benchmarks/integration_benchmark.py
"""

from __future__ import annotations

import math
import time
import random
from fractions import Fraction

# ---------------------------------------------------------------------------
#  Benchmark 1: EVT Argmax
# ---------------------------------------------------------------------------

def benchmark_1_evt_argmax() -> None:
    """Compare EVT argmax_idx to Python's built-in max."""
    from regulus.interval.evt import argmax_idx, grid_list, max_on_grid

    print("=" * 60)
    print("BENCHMARK 1: EVT_idx Verified Argmax")
    print("=" * 60)

    # Correctness: argmax_idx_maximizes
    random.seed(42)
    errors = 0
    for trial in range(1000):
        data = [random.uniform(-10, 10) for _ in range(50)]
        idx = argmax_idx(lambda x: x, data)
        if data[idx] != max(data):
            errors += 1
    print(f"  Correctness (identity f, 1000 trials): {1000 - errors}/1000 correct")

    # Correctness: quadratic function on grid
    f = lambda x: -(x - 0.3) ** 2
    for n in [10, 100, 1000]:
        val = max_on_grid(f, 0.0, 1.0, n)
        true_max = f(0.3)
        gap = abs(val - true_max)
        print(f"  Grid n={n:<5d}: max_on_grid={val:.8f}, true={true_max:.8f}, gap={gap:.2e}")

    # Speed: argmax_idx vs built-in
    data_big = [random.uniform(0, 1) for _ in range(10000)]
    t0 = time.perf_counter()
    for _ in range(100):
        argmax_idx(lambda x: x, data_big)
    t_evt = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(100):
        max(range(len(data_big)), key=lambda i: data_big[i])
    t_builtin = time.perf_counter() - t0

    print(f"  Speed (10K elements, 100 reps): EVT={t_evt:.3f}s, builtin={t_builtin:.3f}s")
    print()


# ---------------------------------------------------------------------------
#  Benchmark 2: Verified Softmax
# ---------------------------------------------------------------------------

def benchmark_2_softmax() -> None:
    """Verified softmax bounds: soundness and tightness."""
    from regulus.interval.softmax import interval_softmax

    print("=" * 60)
    print("BENCHMARK 2: Verified Softmax Bounds")
    print("=" * 60)

    random.seed(42)
    n_classes = 10
    n_samples = 500
    violations = 0
    total_width = 0.0

    for _ in range(n_samples):
        # Random interval inputs
        centers = [random.uniform(-3, 3) for _ in range(n_classes)]
        half_w = [random.uniform(0.01, 0.5) for _ in range(n_classes)]
        los = [c - h for c, h in zip(centers, half_w)]
        his = [c + h for c, h in zip(centers, half_w)]

        # Numerical stability shift
        shift = max(his)
        los_s = [lo - shift for lo in los]
        his_s = [hi - shift for hi in his]

        lb, ub = interval_softmax(los_s, his_s, math.exp)

        # Check soundness: sample a point and verify containment
        xs = [random.uniform(lo, hi) for lo, hi in zip(los, his)]
        xs_s = [x - shift for x in xs]
        exp_xs = [math.exp(x) for x in xs_s]
        denom = sum(exp_xs)
        actual_softmax = [e / denom for e in exp_xs]

        for i in range(n_classes):
            if actual_softmax[i] < lb[i] - 1e-12 or actual_softmax[i] > ub[i] + 1e-12:
                violations += 1

        # Track tightness (average width of bounds)
        for i in range(n_classes):
            total_width += ub[i] - lb[i]

    avg_width = total_width / (n_samples * n_classes)
    print(f"  Soundness: {violations} violations out of {n_samples * n_classes} checks")
    print(f"  Average bound width: {avg_width:.6f}")
    print(f"  (tighter = better; 0 = exact)")
    print()


# ---------------------------------------------------------------------------
#  Benchmark 3: Composition Width
# ---------------------------------------------------------------------------

def benchmark_3_composition_width() -> None:
    """Verify chain_width_product theorem on random layer chains."""
    from regulus.interval.composition import (
        LayerSpec, chain_width, factor_product,
    )

    print("=" * 60)
    print("BENCHMARK 3: Composition Width (chain_width_product)")
    print("=" * 60)

    random.seed(42)
    max_err = 0.0
    for trial in range(100):
        n_layers = random.randint(1, 20)
        factors = [random.uniform(0.1, 3.0) for _ in range(n_layers)]
        layers = [LayerSpec(f) for f in factors]
        input_w = random.uniform(0.001, 1.0)

        cw = chain_width(layers, input_w)
        fp = factor_product(layers)
        predicted = fp * input_w
        err = abs(cw - predicted)
        max_err = max(max_err, err)

    print(f"  chain_width == factor_product * input_width")
    print(f"  Max absolute error over 100 trials: {max_err:.2e}")
    print(f"  Theorem holds: {'YES' if max_err < 1e-10 else 'NO'}")

    # Depth-independence demo
    print()
    print("  Depth-independence (reanchored_depth_independent):")
    eps = 0.001
    for depth in [5, 10, 50, 100]:
        layers = [LayerSpec(1.5)] * depth  # worst-case: all factors > 1
        naive_width = chain_width(layers, 2 * eps)
        # With re-anchoring: only last factor matters
        reanchored_width = layers[-1].factor * 2 * eps
        print(f"    depth={depth:<4d}: naive={naive_width:.6e}, reanchored={reanchored_width:.6e}")
    print()


# ---------------------------------------------------------------------------
#  Benchmark 4: Trisection
# ---------------------------------------------------------------------------

def benchmark_4_trisection() -> None:
    """Trisection: certified gap sizes and convergence."""
    from regulus.interval.trisection import (
        TrisectionState, trisect_iter, trisect_delta, diagonal_trisect,
    )

    print("=" * 60)
    print("BENCHMARK 4: Diagonal Trisection")
    print("=" * 60)

    # Create a simple enumeration: E(k) = k/(N+1) (evenly spaced in [0,1])
    N = 15
    values = [Fraction(k + 1, N + 2) for k in range(N)]

    def E(k: int, ref: int) -> Fraction:
        return values[k % N]

    initial = TrisectionState(Fraction(0), Fraction(1))

    # Run trisection
    D = diagonal_trisect(E, initial, N)
    d_val = float(D(N))

    print(f"  Enumeration: {N} evenly spaced values in (0, 1)")
    print(f"  Diagonal value after {N} steps: {d_val:.12f}")
    print()

    # Check certified gaps
    print("  Step | E(k)      | Gap          | Certified min | OK?")
    print("  -----|-----------|--------------|---------------|----")
    all_ok = True
    for k in range(N):
        e_val = float(values[k])
        gap = abs(d_val - e_val)
        cert_min = float(trisect_delta(k)) / 2
        ok = gap >= cert_min - 1e-15
        all_ok = all_ok and ok
        print(f"  {k:4d} | {e_val:.7f} | {gap:.10f} | {cert_min:.10f} | {'OK' if ok else 'FAIL'}")

    print(f"\n  All gaps certified: {'YES' if all_ok else 'NO'}")

    # Width convergence
    print()
    print("  Width convergence (should be 1/3^n):")
    for n in [5, 10, 15]:
        state = trisect_iter(E, initial, n)
        actual_w = float(state.width)
        expected_w = 1.0 / (3 ** n)
        ratio = actual_w / expected_w if expected_w > 0 else float('inf')
        print(f"    n={n:2d}: width={actual_w:.2e}, expected={expected_w:.2e}, ratio={ratio:.6f}")
    print()


# ---------------------------------------------------------------------------
#  Benchmark 5: End-to-end (requires torch)
# ---------------------------------------------------------------------------

def benchmark_5_end_to_end() -> None:
    """Full NN verification with all new components."""
    print("=" * 60)
    print("BENCHMARK 5: End-to-End NN Verification")
    print("=" * 60)

    try:
        import torch  # noqa: F401
    except (ImportError, OSError):
        print("  SKIPPED — torch not available on this machine")
        print("  Run on Vast.ai or machine with torch installed")
        print()
        return

    # If torch available, run a small MLP test
    from regulus.nn.verifier import NNVerificationEngine
    from regulus.nn.architectures import make_simple_mlp

    model = make_simple_mlp(input_dim=4, hidden_dim=16, output_dim=3)
    engine = NNVerificationEngine(model)

    import numpy as np
    x = np.array([0.5, 0.3, -0.2, 0.1])
    result = engine.verify(x, epsilon=0.01)

    print(f"  Model: MLP 4→16→3")
    print(f"  Input: {x}")
    print(f"  Epsilon: 0.01")
    print(f"  Output width: {result.output_width}")
    print(f"  Predicted class: {result.predicted_class}")
    print(f"  Certified robust: {result.certified_robust}")
    print()


# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("Regulus AI — Integration Benchmarks")
    print("Validating Coq-verified theorem ports")
    print()

    benchmark_1_evt_argmax()
    benchmark_2_softmax()
    benchmark_3_composition_width()
    benchmark_4_trisection()
    benchmark_5_end_to_end()

    print("=" * 60)
    print("ALL BENCHMARKS COMPLETE")
    print("=" * 60)
