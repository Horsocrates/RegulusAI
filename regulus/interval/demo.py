"""
Demonstration of Regulus interval arithmetic.

Run: uv run python -m regulus.interval.demo
"""

from __future__ import annotations

import math

from regulus.interval.interval import Interval
from regulus.interval.interval_tensor import IntervalTensor
from regulus.interval.nn import IntervalLinear, IntervalReLU, IntervalSequential
from regulus.interval.bisection import bisection_iter


def demo_bisection():
    """IVT bisection: find sqrt(2) with verified bounds."""
    print("=== Bisection (IVT.v extraction) ===")
    print("f(x) = x^2 - 2, interval [1, 2]\n")

    f = lambda x: x * x - 2.0

    for n in [5, 10, 20, 30, 40, 53]:
        state = bisection_iter(f, 1.0, 2.0, n)
        mid = (state.left + state.right) / 2.0
        width = state.right - state.left
        error = abs(mid - math.sqrt(2))
        print(f"  n={n:2d}: [{state.left:.15f}, {state.right:.15f}]")
        print(f"         width = {width:.2e}, error = {error:.2e}")

    print(f"\n  sqrt(2) = {math.sqrt(2):.15f}")
    print()


def demo_interval_arithmetic():
    """Basic interval operations (PInterval.v)."""
    print("=== Interval Arithmetic (PInterval.v) ===\n")

    a = Interval(1.0, 2.0)
    b = Interval(3.0, 5.0)

    print(f"  a = {a}")
    print(f"  b = {b}")
    print(f"  a + b = {a + b}")
    print(f"  a - b = {a - b}")
    print(f"  a * b = {a * b}")
    print(f"  -a    = {-a}")
    print(f"  |Interval(-3, 2)| = {abs(Interval(-3.0, 2.0))}")
    print(f"  relu(Interval(-2, 3)) = {Interval(-2.0, 3.0).relu()}")
    print()


def demo_neural_network():
    """Interval propagation through a neural network."""
    print("=== Interval Neural Network ===\n")

    # Simple 2-input, 2-hidden, 2-output network
    model = IntervalSequential(
        IntervalLinear(
            weights=[[0.5, -0.3], [0.2, 0.8], [-0.4, 0.6], [0.7, -0.1]],
            biases=[0.1, -0.2, 0.0, 0.3],
        ),
        IntervalReLU(),
        IntervalLinear(
            weights=[[0.6, -0.2, 0.4, 0.1], [-0.3, 0.5, 0.7, -0.4]],
            biases=[0.0, 0.0],
        ),
    )

    # Input with uncertainty
    x = IntervalTensor([[0.71, 0.75], [0.28, 0.32]])
    print(f"  Input:  x[0] = {x[0]}, x[1] = {x[1]}")

    output = model(x)
    print(f"  Output: class_0 = {output[0]}")
    print(f"          class_1 = {output[1]}")

    if output[0].overlaps(output[1]):
        print("  Result: UNRELIABLE -- class intervals overlap")
    else:
        print("  Result: RELIABLE -- classes are separated")

    print()


def demo_robustness():
    """Show how intervals detect unreliable classifications."""
    print("=== Robustness Analysis ===\n")

    # A network that is confident for small perturbations
    # but fails for larger ones
    model = IntervalSequential(
        IntervalLinear(weights=[[10.0, -10.0]], biases=[0.0]),
        IntervalReLU(),
    )

    print("  Network: relu(10*x0 - 10*x1)")
    print("  Testing robustness at x = [0.6, 0.4]:\n")

    for eps in [0.01, 0.05, 0.1, 0.15, 0.2]:
        x = IntervalTensor.from_pm([0.6, 0.4], radius=eps)
        y = model(x)
        width = y[0].width
        status = "SAFE" if y[0].lo > 0 else "COULD BE ZERO"
        print(f"  eps={eps:.2f}: output = {y[0]}, width={width:.2f} -> {status}")

    print()


if __name__ == "__main__":
    print("=" * 60)
    print("  REGULUS PHASE 1: Verified Interval Arithmetic Demo")
    print("  Theory of Systems -> Coq -> Python")
    print("=" * 60)
    print()

    demo_bisection()
    demo_interval_arithmetic()
    demo_neural_network()
    demo_robustness()

    print("=" * 60)
    print("  All operations above have corresponding Coq proofs:")
    print("    - Archimedean.v: pow2 convergence")
    print("    - IVT.v: bisection correctness + Cauchy property")
    print("    - PInterval.v: interval arithmetic soundness")
    print("=" * 60)
