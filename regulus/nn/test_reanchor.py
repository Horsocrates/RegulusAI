"""Tests for ReanchoredIntervalModel (P4 re-anchoring)."""

import numpy as np
import pytest
import torch
import torch.nn as nn

from regulus.nn.interval_tensor import IntervalTensor
from regulus.nn.model import convert_model, IntervalSequential
from regulus.nn.reanchor import ReanchoredIntervalModel


def _make_mnist_model():
    """Small MNIST-like model: [L,R,L,R,L,R,L]."""
    torch.manual_seed(42)
    return nn.Sequential(
        nn.Linear(784, 256), nn.ReLU(),
        nn.Linear(256, 128), nn.ReLU(),
        nn.Linear(128, 64), nn.ReLU(),
        nn.Linear(64, 10),
    )


def _make_tiny_model():
    """Tiny model for fast tests: [L,R,L,R,L]."""
    torch.manual_seed(42)
    return nn.Sequential(
        nn.Linear(4, 8), nn.ReLU(),
        nn.Linear(8, 4), nn.ReLU(),
        nn.Linear(4, 2),
    )


# ============================================================
# Block splitting
# ============================================================

class TestBlockSplitting:

    def test_bs1_gives_4_blocks(self):
        model = _make_mnist_model()
        blocks = ReanchoredIntervalModel._split_into_blocks(model, block_size=1)
        assert len(blocks) == 4
        # Block 0: Linear + ReLU (2 children)
        assert len(list(blocks[0].children())) == 2
        # Block 3: Linear only (1 child)
        assert len(list(blocks[3].children())) == 1

    def test_bs2_gives_2_blocks(self):
        model = _make_mnist_model()
        blocks = ReanchoredIntervalModel._split_into_blocks(model, block_size=2)
        assert len(blocks) == 2
        # Block 0: L,R,L,R (4 children)
        assert len(list(blocks[0].children())) == 4
        # Block 1: L,R,L (3 children, final L has no activation)
        assert len(list(blocks[1].children())) == 3

    def test_bs3_gives_2_blocks(self):
        model = _make_mnist_model()
        blocks = ReanchoredIntervalModel._split_into_blocks(model, block_size=3)
        assert len(blocks) == 2
        # Block 0: L,R,L,R,L,R (6 children)
        assert len(list(blocks[0].children())) == 6
        # Block 1: L (1 child)
        assert len(list(blocks[1].children())) == 1

    def test_bs_larger_than_activations(self):
        """block_size=10 on a 3-activation model -> single block."""
        model = _make_mnist_model()
        blocks = ReanchoredIntervalModel._split_into_blocks(model, block_size=10)
        assert len(blocks) == 1
        assert len(list(blocks[0].children())) == 7

    def test_tiny_model_bs1(self):
        model = _make_tiny_model()
        blocks = ReanchoredIntervalModel._split_into_blocks(model, block_size=1)
        assert len(blocks) == 3  # [L,R], [L,R], [L]


# ============================================================
# Forward pass — midpoint strategy
# ============================================================

class TestMidpointStrategy:

    def test_output_shape(self):
        model = _make_tiny_model()
        ra = ReanchoredIntervalModel(model, block_size=1, reanchor_eps=0.01)
        x = IntervalTensor.from_uncertainty(np.random.randn(4), 0.1)
        out = ra(x)
        assert out.lo.shape == (2,)
        assert out.hi.shape == (2,)

    def test_width_much_less_than_naive(self):
        """Midpoint re-anchoring should produce dramatically narrower intervals."""
        model = _make_mnist_model()
        x = IntervalTensor.from_uncertainty(np.random.randn(784), 0.02)

        # Naive IBP
        naive = convert_model(model)
        naive_out = naive(x)

        # Re-anchored
        ra = ReanchoredIntervalModel(model, block_size=1, reanchor_eps=0.001)
        ra_out = ra(x)

        # Re-anchored should be MUCH narrower
        assert ra_out.max_width() < naive_out.max_width()
        # Expect at least 10x reduction
        assert ra_out.max_width() < naive_out.max_width() / 10

    def test_reanchor_count(self):
        """bs=1 on MNIST model: 3 re-anchor points."""
        model = _make_mnist_model()
        ra = ReanchoredIntervalModel(model, block_size=1, reanchor_eps=0.01)
        x = IntervalTensor.from_uncertainty(np.random.randn(784), 0.02)
        ra(x)
        assert ra.n_reanchors == 3  # between 4 blocks

    def test_reanchor_count_bs2(self):
        """bs=2 on MNIST model: 1 re-anchor point."""
        model = _make_mnist_model()
        ra = ReanchoredIntervalModel(model, block_size=2, reanchor_eps=0.01)
        x = IntervalTensor.from_uncertainty(np.random.randn(784), 0.02)
        ra(x)
        assert ra.n_reanchors == 1

    def test_eps_zero_gives_point_intervals(self):
        """reanchor_eps=0 means midpoint collapses to exact point propagation."""
        model = _make_tiny_model()
        ra = ReanchoredIntervalModel(model, block_size=1, reanchor_eps=0.0)
        x = IntervalTensor.from_uncertainty(np.random.randn(4), 0.1)
        out = ra(x)
        # After re-anchoring with eps=0, last block propagates point intervals
        # so output width should be 0 (or very close)
        assert out.max_width() < 1e-10

    def test_block_widths_recorded(self):
        model = _make_tiny_model()
        ra = ReanchoredIntervalModel(model, block_size=1, reanchor_eps=0.01)
        x = IntervalTensor.from_uncertainty(np.random.randn(4), 0.1)
        ra(x)
        # Should have entries: input, block0 out, reanchor, block1 out, reanchor, block2 out
        assert len(ra.block_widths) >= 4


# ============================================================
# Adaptive strategy
# ============================================================

class TestAdaptiveStrategy:

    def test_skips_reanchor_when_narrow(self):
        """With very high threshold, adaptive should never re-anchor."""
        model = _make_tiny_model()
        ra = ReanchoredIntervalModel(
            model, block_size=1, reanchor_eps=0.01,
            strategy="adaptive", adaptive_threshold=1e10,
        )
        x = IntervalTensor.from_uncertainty(np.random.randn(4), 0.001)
        ra(x)
        assert ra.n_reanchors == 0

    def test_reanchors_when_wide(self):
        """With low threshold, adaptive should re-anchor."""
        model = _make_mnist_model()
        ra = ReanchoredIntervalModel(
            model, block_size=1, reanchor_eps=0.001,
            strategy="adaptive", adaptive_threshold=0.1,
        )
        x = IntervalTensor.from_uncertainty(np.random.randn(784), 0.02)
        ra(x)
        assert ra.n_reanchors >= 1


# ============================================================
# Hybrid strategy
# ============================================================

class TestHybridStrategy:

    def test_uses_naive_when_narrow(self):
        """Small model with tiny eps -> naive width is fine -> no re-anchor."""
        model = _make_tiny_model()
        ra = ReanchoredIntervalModel(
            model, block_size=1, reanchor_eps=0.001,
            strategy="hybrid", adaptive_threshold=1e10,
        )
        x = IntervalTensor.from_uncertainty(np.random.randn(4), 0.0001)
        ra(x)
        assert ra.n_reanchors == 0

    def test_falls_back_when_wide(self):
        """Deep model with large eps -> naive blows up -> re-anchor activated."""
        model = _make_mnist_model()
        ra = ReanchoredIntervalModel(
            model, block_size=1, reanchor_eps=0.001,
            strategy="hybrid", adaptive_threshold=1.0,
        )
        x = IntervalTensor.from_uncertainty(np.random.randn(784), 0.02)
        out = ra(x)
        assert ra.n_reanchors >= 1
        # Width should be controlled (not millions)
        assert out.max_width() < 100


# ============================================================
# Proportional strategy
# ============================================================

class TestProportionalStrategy:

    def test_output_shape_preserved(self):
        model = _make_mnist_model()
        ra = ReanchoredIntervalModel(
            model, block_size=1, reanchor_eps=1e-6,
            strategy="proportional", shrink_factor=0.1,
        )
        x = IntervalTensor.from_uncertainty(np.random.randn(784), 0.02)
        out = ra(x)
        assert out.shape == (10,)

    def test_width_controlled(self):
        """Proportional should also control width (not blow up to millions)."""
        model = _make_mnist_model()
        ra = ReanchoredIntervalModel(
            model, block_size=1, reanchor_eps=1e-6,
            strategy="proportional", shrink_factor=0.1,
        )
        x = IntervalTensor.from_uncertainty(np.random.randn(784), 0.02)
        out = ra(x)
        assert out.max_width() < 100
        assert ra.n_reanchors == 3  # bs=1, 3 activations = 3 re-anchors

    def test_preserves_relative_differences(self):
        """Two inputs with different magnitudes should produce different widths.

        This is the key advantage over fixed-eps midpoint: proportional
        preserves sample-dependent variation in the uncertainty signal.
        """
        model = _make_mnist_model()
        ra = ReanchoredIntervalModel(
            model, block_size=1, reanchor_eps=1e-8,
            strategy="proportional", shrink_factor=0.1,
        )

        # Two different inputs
        np.random.seed(123)
        x1 = IntervalTensor.from_uncertainty(np.random.randn(784), 0.02)
        x2 = IntervalTensor.from_uncertainty(np.random.randn(784) * 3, 0.02)

        out1 = ra(x1)
        out2 = ra(x2)

        # Widths should be different (signal preserved)
        w1 = out1.max_width()
        w2 = out2.max_width()
        assert w1 != w2, "Proportional should produce different widths for different inputs"

    def test_shrink_factor_zero_gives_minimal_width(self):
        """With shrink_factor=0, only reanchor_eps floor remains."""
        model = _make_tiny_model()
        ra = ReanchoredIntervalModel(
            model, block_size=1, reanchor_eps=1e-6,
            strategy="proportional", shrink_factor=0.0,
        )
        x = IntervalTensor.from_uncertainty(np.random.randn(4), 0.1)
        out = ra(x)
        # Width should be tiny (just the reanchor_eps floor propagated through final block)
        assert out.max_width() < 0.01


# ============================================================
# Width report
# ============================================================

class TestWidthReport:

    def test_report_is_string(self):
        model = _make_tiny_model()
        ra = ReanchoredIntervalModel(model, block_size=1, reanchor_eps=0.01)
        x = IntervalTensor.from_uncertainty(np.random.randn(4), 0.1)
        ra(x)
        report = ra.width_report()
        assert isinstance(report, str)
        assert "ReanchoredIntervalModel" in report
        assert "Re-anchors" in report
