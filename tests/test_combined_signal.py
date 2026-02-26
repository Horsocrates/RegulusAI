"""Tests for combined signal experiment logic (pure functions, no model training)."""

import numpy as np
import pytest


# ============================================================
# Normalization
# ============================================================

class TestNormalize01:
    def test_basic(self):
        from regulus.experiments.combined_signal import _normalize_01
        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = _normalize_01(arr)
        assert result[0] == pytest.approx(0.0)
        assert result[-1] == pytest.approx(1.0)
        assert result[2] == pytest.approx(0.5)

    def test_constant(self):
        from regulus.experiments.combined_signal import _normalize_01
        arr = np.array([3.0, 3.0, 3.0])
        result = _normalize_01(arr)
        np.testing.assert_array_equal(result, [0.0, 0.0, 0.0])

    def test_single_element(self):
        from regulus.experiments.combined_signal import _normalize_01
        arr = np.array([7.0])
        result = _normalize_01(arr)
        assert result[0] == pytest.approx(0.0)

    def test_negative_range(self):
        from regulus.experiments.combined_signal import _normalize_01
        arr = np.array([-5.0, 0.0, 5.0])
        result = _normalize_01(arr)
        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(0.5)
        assert result[2] == pytest.approx(1.0)


# ============================================================
# Combination methods
# ============================================================

class TestCombinationMethods:
    def test_product(self):
        from regulus.experiments.combined_signal import combine_product
        u1 = np.array([0.0, 0.5, 1.0])
        u2 = np.array([1.0, 0.5, 0.0])
        result = combine_product(u1, u2)
        np.testing.assert_allclose(result, [0.0, 0.25, 0.0])

    def test_weighted_alpha_0(self):
        """alpha=0 -> pure TempScaling (u_temp)."""
        from regulus.experiments.combined_signal import combine_weighted
        u1 = np.array([0.1, 0.9])
        u2 = np.array([0.8, 0.2])
        result = combine_weighted(u1, u2, alpha=0.0)
        np.testing.assert_allclose(result, u2)

    def test_weighted_alpha_1(self):
        """alpha=1 -> pure RA-Margin (u_margin)."""
        from regulus.experiments.combined_signal import combine_weighted
        u1 = np.array([0.1, 0.9])
        u2 = np.array([0.8, 0.2])
        result = combine_weighted(u1, u2, alpha=1.0)
        np.testing.assert_allclose(result, u1)

    def test_weighted_alpha_half(self):
        from regulus.experiments.combined_signal import combine_weighted
        u1 = np.array([0.0, 1.0])
        u2 = np.array([1.0, 0.0])
        result = combine_weighted(u1, u2, alpha=0.5)
        np.testing.assert_allclose(result, [0.5, 0.5])

    def test_max(self):
        from regulus.experiments.combined_signal import combine_max
        u1 = np.array([0.1, 0.9, 0.5])
        u2 = np.array([0.8, 0.2, 0.5])
        result = combine_max(u1, u2)
        np.testing.assert_allclose(result, [0.8, 0.9, 0.5])

    def test_learned_shape_and_range(self):
        """Learned combiner returns valid probabilities."""
        from regulus.experiments.combined_signal import combine_learned
        np.random.seed(42)
        n_train = 200
        u1_tr = np.random.rand(n_train)
        u2_tr = np.random.rand(n_train)
        # is_wrong correlates with u1+u2
        is_wrong = ((u1_tr + u2_tr) > 1.0).astype(float)
        u1_te = np.random.rand(50)
        u2_te = np.random.rand(50)
        result = combine_learned(u1_tr, u2_tr, is_wrong, u1_te, u2_te)
        assert result.shape == (50,)
        assert np.all(result >= 0.0)
        assert np.all(result <= 1.0)


# ============================================================
# Alpha grid
# ============================================================

class TestAlphaGrid:
    def test_grid_size(self):
        from regulus.experiments.combined_signal import ALPHA_GRID
        assert len(ALPHA_GRID) == 11

    def test_grid_endpoints(self):
        from regulus.experiments.combined_signal import ALPHA_GRID
        assert ALPHA_GRID[0] == pytest.approx(0.0)
        assert ALPHA_GRID[-1] == pytest.approx(1.0)

    def test_grid_step(self):
        from regulus.experiments.combined_signal import ALPHA_GRID
        for i in range(len(ALPHA_GRID)):
            assert ALPHA_GRID[i] == pytest.approx(i * 0.1)
