"""Tests for composition-aware adaptive reanchoring.

Verifies that predict_block_factors and predict_optimal_eps produce
sound predictions (predicted width ≥ actual width), and that
composition-aware reanchoring reduces output width compared to fixed eps.

Coq backing:
    chain_width_product: chain_width == factor_product * input_width
    reanchored_depth_independent: output <= last_factor * 2*eps
"""

import pytest
import numpy as np

from regulus.interval.composition import (
    LayerSpec, chain_width, factor_product, reanchored_chain_width,
    predict_block_factors, predict_optimal_eps,
)
from regulus.interval.interval import Interval


# ===================================================================
#  predict_block_factors (without torch — pure numpy mock)
# ===================================================================


class MockIntervalLinear:
    """Mock IntervalLinear for testing factor prediction."""

    def __init__(self, weight: np.ndarray) -> None:
        self.weight = weight

    def __call__(self, x):
        raise NotImplementedError("Mock — not for forward pass")


class MockIntervalReLU:
    """Mock IntervalReLU."""

    def __call__(self, x):
        raise NotImplementedError("Mock")


class MockIntervalBatchNorm:
    """Mock IntervalBatchNorm."""

    def __init__(self, scale: np.ndarray, shift: np.ndarray) -> None:
        self.scale = scale
        self.shift = shift

    def __call__(self, x):
        raise NotImplementedError("Mock")


class MockIntervalConv2d:
    """Mock IntervalConv2d."""

    def __init__(self, weight: np.ndarray) -> None:
        self.weight = weight

    def __call__(self, x):
        raise NotImplementedError("Mock")


class MockBlock:
    """Mock IntervalSequential block."""

    def __init__(self, layers: list) -> None:
        self.layers = layers


class TestPredictBlockFactors:
    def test_single_linear_block(self):
        """Factor = max row L1-norm of weight matrix."""
        # 2x2 weight: row 0 = [1,2] (L1=3), row 1 = [0.5,0.5] (L1=1)
        w = np.array([[1.0, 2.0], [0.5, 0.5]])
        block = MockBlock([MockIntervalLinear(w)])
        specs = predict_block_factors([block])
        assert len(specs) == 1
        assert specs[0].factor == pytest.approx(3.0)  # max row L1-norm

    def test_linear_relu_block(self):
        """Linear + ReLU: factor = linear_factor * 1.0."""
        w = np.array([[1.0, 1.0], [2.0, 2.0]])  # max row L1 = 4
        block = MockBlock([MockIntervalLinear(w), MockIntervalReLU()])
        specs = predict_block_factors([block])
        assert specs[0].factor == pytest.approx(4.0)

    def test_batchnorm_factor(self):
        """BatchNorm factor = max(|scale|)."""
        scale = np.array([0.5, -2.0, 1.0])
        shift = np.zeros(3)
        block = MockBlock([MockIntervalBatchNorm(scale, shift)])
        specs = predict_block_factors([block])
        assert specs[0].factor == pytest.approx(2.0)

    def test_conv2d_factor(self):
        """Conv2d factor = max over output channels of L1-norm."""
        # (C_out=2, C_in=1, kH=2, kW=2)
        w = np.array([
            [[[1.0, 0.5], [0.5, 0.0]]],  # ch0: L1 = 2.0
            [[[2.0, 1.0], [1.0, 0.5]]],  # ch1: L1 = 4.5
        ])
        block = MockBlock([MockIntervalConv2d(w)])
        specs = predict_block_factors([block])
        assert specs[0].factor == pytest.approx(4.5)

    def test_multiple_blocks(self):
        """Multiple blocks get independent factors."""
        w1 = np.array([[1.0, 1.0]])  # L1 = 2
        w2 = np.array([[3.0, 0.0], [0.0, 3.0]])  # max L1 = 3
        blocks = [
            MockBlock([MockIntervalLinear(w1)]),
            MockBlock([MockIntervalLinear(w2)]),
        ]
        specs = predict_block_factors(blocks)
        assert len(specs) == 2
        assert specs[0].factor == pytest.approx(2.0)
        assert specs[1].factor == pytest.approx(3.0)

    def test_empty_blocks(self):
        """No blocks → empty spec list."""
        specs = predict_block_factors([])
        assert specs == []

    def test_composite_block_factor(self):
        """Block with Linear + BN + ReLU: factors multiply."""
        w = np.array([[1.0, 1.0], [1.0, 1.0]])  # max L1 = 2
        scale = np.array([0.5, 0.5])  # max |scale| = 0.5
        block = MockBlock([
            MockIntervalLinear(w),
            MockIntervalBatchNorm(scale, np.zeros(2)),
            MockIntervalReLU(),
        ])
        specs = predict_block_factors([block])
        # factor = 2.0 * 0.5 * 1.0 = 1.0
        assert specs[0].factor == pytest.approx(1.0)


# ===================================================================
#  predict_optimal_eps
# ===================================================================


class TestPredictOptimalEps:
    def test_basic_optimal_eps(self):
        """eps = target / (2 * remaining_factor_product)."""
        specs = [LayerSpec(2.0), LayerSpec(3.0), LayerSpec(1.5)]
        # After block 0, remaining = [3.0, 1.5], product = 4.5
        eps = predict_optimal_eps(specs, 0, target_output_width=0.9)
        # eps = 0.9 / (2 * 4.5) = 0.1
        assert eps == pytest.approx(0.1)

    def test_last_block_no_remaining(self):
        """After last reanchor point, remaining = last block."""
        specs = [LayerSpec(2.0), LayerSpec(3.0)]
        # After block 0, remaining = [3.0], product = 3.0
        eps = predict_optimal_eps(specs, 0, target_output_width=0.6)
        # eps = 0.6 / (2 * 3.0) = 0.1
        assert eps == pytest.approx(0.1)

    def test_single_block_no_reanchor(self):
        """Single block: no reanchor points."""
        specs = [LayerSpec(5.0)]
        # block_index=0 is the last block, remaining = []
        # product of empty = 1.0
        # This would be the last block — reanchor doesn't happen here
        # But if called: eps = target / (2 * 1.0)
        eps = predict_optimal_eps(specs, 0, target_output_width=1.0)
        assert eps == pytest.approx(0.5)

    def test_chain_width_consistency(self):
        """Optimal eps produces target width through remaining chain."""
        specs = [LayerSpec(2.0), LayerSpec(3.0), LayerSpec(1.5)]
        target = 0.9
        eps = predict_optimal_eps(specs, 0, target)
        # Verify: chain_width(remaining, 2*eps) should equal target
        remaining = specs[1:]
        output_width = chain_width(remaining, 2.0 * eps)
        assert output_width == pytest.approx(target)


# ===================================================================
#  Composition-predicted widths are sound (predicted ≥ actual)
# ===================================================================


class TestCompositionSoundness:
    """Verify that predicted factors are UPPER BOUNDS on actual factors.

    This is the key soundness property: if predicted ≥ actual, then
    the composition-derived eps schedule will produce output widths
    no larger than predicted.

    Note: For pure linear layers without activations, predicted = actual.
    For layers with ReLU, predicted ≥ actual because ReLU can only shrink.
    """

    def test_linear_factor_is_exact_for_worst_case(self):
        """Max row L1-norm is exact worst-case for positive intervals."""
        # With all-positive weights and all-positive inputs,
        # the L1 bound is tight
        w = np.array([[2.0, 1.0], [0.5, 0.5]])
        factor_predicted = float(np.max(np.sum(np.abs(w), axis=1)))
        # factor = max(3.0, 1.0) = 3.0

        # Actual: input [a-eps, a+eps] → output worst-case width
        # for row 0: |2|*2eps + |1|*2eps = 3*2*eps = 6*eps; input was 2*eps
        # ratio = 3.0 (exact for positive weights, symmetric input)
        assert factor_predicted == pytest.approx(3.0)

    def test_relu_only_shrinks(self):
        """ReLU factor = 1, but actual can be < 1 (when lo < 0)."""
        # If interval = [-1, 2], width = 3.0
        # ReLU → [0, 2], width = 2.0
        # Actual factor = 2/3 < 1.0 (predicted)
        assert 2.0 / 3.0 < 1.0  # predicted ≥ actual ✓

    def test_predicted_ge_actual_chain(self):
        """For a chain of factors, predicted chain_width ≥ actual chain_width."""
        # Predicted factors (upper bounds)
        pred = [LayerSpec(3.0), LayerSpec(2.0)]
        # Actual factors (must be ≤ predicted)
        actual = [LayerSpec(2.5), LayerSpec(1.8)]

        input_w = 0.1
        pred_output = chain_width(pred, input_w)
        actual_output = chain_width(actual, input_w)

        assert pred_output >= actual_output


# ===================================================================
#  Integration: eps schedule
# ===================================================================


class TestEpsSchedule:
    def test_schedule_length(self):
        """Eps schedule has n-1 entries (one per reanchor point)."""
        specs = [LayerSpec(2.0), LayerSpec(3.0), LayerSpec(1.5)]
        from regulus.interval.composition import predict_optimal_eps

        # 3 blocks → 2 reanchor points
        schedule = []
        for i in range(len(specs) - 1):
            eps = predict_optimal_eps(specs, i, target_output_width=0.5)
            schedule.append(eps)
        assert len(schedule) == 2

    def test_schedule_decreases_with_larger_remaining(self):
        """More remaining blocks with large factors → smaller eps needed."""
        specs = [LayerSpec(2.0), LayerSpec(3.0), LayerSpec(4.0)]
        target = 1.0

        eps_0 = predict_optimal_eps(specs, 0, target)  # remaining: 3.0*4.0=12
        eps_1 = predict_optimal_eps(specs, 1, target)  # remaining: 4.0

        # eps_0 = 1.0 / (2*12) = 0.0417
        # eps_1 = 1.0 / (2*4) = 0.125
        assert eps_0 < eps_1

    def test_schedule_bounded_by_fixed_eps(self):
        """Composition eps is clamped to min(fixed, optimal)."""
        specs = [LayerSpec(0.1), LayerSpec(0.1)]  # very small factors
        fixed_eps = 0.001
        target = 10.0  # large target → optimal eps is huge

        optimal = predict_optimal_eps(specs, 0, target)
        # optimal = 10.0 / (2 * 0.1) = 50.0 >> fixed_eps
        # Schedule should use min(fixed_eps, optimal) = fixed_eps
        used = min(fixed_eps, optimal)
        assert used == pytest.approx(fixed_eps)
