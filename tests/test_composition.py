"""Tests for regulus.interval.composition — PInterval_Composition.v."""

import pytest
from regulus.interval.interval import Interval
from regulus.interval.composition import (
    pi_midpoint, pi_reanchor, pi_max_pair, pi_max_fold,
    pi_residual, pi_resblock_width_bound,
    LayerSpec, chain_width, factor_product, reanchored_chain_width,
    conv_bn_relu_factor,
)


# ===================================================================
#  Re-anchoring
# ===================================================================

class TestReanchor:
    def test_reanchor_width(self):
        """pi_reanchor_width: width == 2 * eps."""
        I = Interval(1.0, 5.0)
        for eps in [0.5, 1.0, 2.0, 0.001]:
            result = pi_reanchor(I, eps)
            assert result.width == pytest.approx(2 * eps)

    def test_reanchor_contains_midpoint(self):
        """pi_reanchor_contains_midpoint."""
        I = Interval(2.0, 8.0)
        result = pi_reanchor(I, 1.0)
        mid = pi_midpoint(I)
        assert result.contains(mid)

    def test_reanchor_loses_containment(self):
        """pi_reanchor_loses_containment: I=[0,10], eps=1, x=0 NOT in result."""
        I = Interval(0.0, 10.0)
        result = pi_reanchor(I, 1.0)
        # midpoint = 5.0, reanchored = [4.0, 6.0]
        assert I.contains(0.0)
        assert not result.contains(0.0)

    def test_reanchor_zero_eps(self):
        """eps=0 produces point interval at midpoint."""
        I = Interval(3.0, 7.0)
        result = pi_reanchor(I, 0.0)
        assert result.width == pytest.approx(0.0)
        assert result.lo == pytest.approx(5.0)

    def test_reanchor_negative_eps_raises(self):
        with pytest.raises(ValueError):
            pi_reanchor(Interval(0.0, 1.0), -0.1)

    def test_midpoint(self):
        """pi_midpoint: (lo + hi) / 2."""
        assert pi_midpoint(Interval(2.0, 8.0)) == pytest.approx(5.0)
        assert pi_midpoint(Interval(-3.0, 3.0)) == pytest.approx(0.0)


# ===================================================================
#  MaxPool (pi_max_pair)
# ===================================================================

class TestMaxPair:
    def test_max_pair_correct(self):
        """pi_max_pair_correct: max(x,y) in pi_max_pair(I,J)."""
        I = Interval(1.0, 4.0)
        J = Interval(2.0, 5.0)
        result = pi_max_pair(I, J)
        # For any x in I, y in J: max(x,y) in result
        for x in [1.0, 2.5, 4.0]:
            for y in [2.0, 3.5, 5.0]:
                assert result.contains(max(x, y))

    def test_max_pair_width(self):
        """pi_max_pair_width: width <= max(width_I, width_J)."""
        I = Interval(1.0, 4.0)  # width 3
        J = Interval(2.0, 5.0)  # width 3
        result = pi_max_pair(I, J)
        assert result.width <= max(I.width, J.width) + 1e-15

    def test_max_pair_disjoint(self):
        """MaxPair of disjoint intervals."""
        I = Interval(1.0, 2.0)
        J = Interval(5.0, 8.0)
        result = pi_max_pair(I, J)
        assert result.lo == pytest.approx(5.0)
        assert result.hi == pytest.approx(8.0)

    def test_max_fold(self):
        """pi_max_fold: MaxPool over list."""
        intervals = [Interval(1.0, 3.0), Interval(2.0, 4.0), Interval(0.0, 5.0)]
        result = pi_max_fold(intervals)
        assert result.lo == pytest.approx(2.0)  # max of los
        assert result.hi == pytest.approx(5.0)  # max of his

    def test_max_fold_single(self):
        I = Interval(1.0, 3.0)
        assert pi_max_fold([I]).lo == pytest.approx(1.0)

    def test_max_fold_empty_raises(self):
        with pytest.raises(ValueError):
            pi_max_fold([])


# ===================================================================
#  Residual (skip connection)
# ===================================================================

class TestResidual:
    def test_residual_correct(self):
        """pi_residual_correct: x + f(x) in result."""
        I = Interval(1.0, 3.0)
        F = Interval(-0.5, 0.5)
        result = pi_residual(I, F)
        # x=2.0, f(x)=0.1 → x+f(x) = 2.1
        assert result.contains(2.1)
        # Boundary: x=1.0, f(x)=-0.5 → 0.5
        assert result.contains(0.5)

    def test_residual_width(self):
        """Width = width_I + width_F (interval addition)."""
        I = Interval(1.0, 3.0)  # w=2
        F = Interval(-0.5, 0.5)  # w=1
        result = pi_residual(I, F)
        assert result.width == pytest.approx(3.0)

    def test_resblock_width_bound(self):
        """pi_resblock_width_bound: width(relu(res)) <= w_I + w_F."""
        bound = pi_resblock_width_bound(2.0, 1.0)
        assert bound == pytest.approx(3.0)


# ===================================================================
#  Chain width
# ===================================================================

class TestChainWidth:
    def test_chain_width_product(self):
        """chain_width_product: chain_width == factor_product * input_width."""
        layers = [LayerSpec(2.0), LayerSpec(0.5), LayerSpec(3.0)]
        w = 0.1
        cw = chain_width(layers, w)
        fp = factor_product(layers)
        assert cw == pytest.approx(fp * w)

    def test_chain_width_single(self):
        """Single layer: factor * input."""
        layers = [LayerSpec(1.5)]
        assert chain_width(layers, 2.0) == pytest.approx(3.0)

    def test_chain_width_empty(self):
        """No layers: identity."""
        assert chain_width([], 5.0) == pytest.approx(5.0)

    def test_factor_product_empty(self):
        assert factor_product([]) == pytest.approx(1.0)

    def test_chain_width_monotone(self):
        """chain_width_monotone: wider input → wider output (nonneg factors)."""
        layers = [LayerSpec(2.0), LayerSpec(1.5)]
        assert chain_width(layers, 1.0) <= chain_width(layers, 2.0)

    def test_reanchored_depth_independent(self):
        """reanchored_depth_independent: only last factor matters after re-anchor."""
        eps = 0.001
        # Single trailing layer
        layers_1 = [LayerSpec(1.5)]
        w1 = reanchored_chain_width(layers_1, eps)
        assert w1 == pytest.approx(1.5 * 2 * eps)

    def test_layer_spec_negative_raises(self):
        with pytest.raises(ValueError):
            LayerSpec(-1.0)

    def test_conv_bn_relu_factor(self):
        """conv_bn_relu_spec: |scale| * l1."""
        f = conv_bn_relu_factor(bn_scale=-2.0, conv_weight_l1=3.0)
        assert f == pytest.approx(6.0)
