"""Tests for regulus.nn — interval bound propagation through neural networks."""

import numpy as np
import pytest
import torch

from regulus.nn.interval_tensor import IntervalTensor, interval_matmul_exact_weights
from regulus.nn.layers import IntervalLinear, IntervalReLU, IntervalSoftmax
from regulus.nn.model import IntervalSequential, convert_model
from regulus.analysis.reliability import predict_max_width


class TestIntervalTensor:
    def test_from_exact(self):
        x = IntervalTensor.from_exact(np.array([1.0, 2.0, 3.0]))
        assert x.shape == (3,)
        np.testing.assert_array_equal(x.lo, x.hi)
        assert x.max_width() == 0.0

    def test_from_uncertainty(self):
        x = IntervalTensor.from_uncertainty(np.array([1.0, 2.0]), 0.1)
        np.testing.assert_allclose(x.lo, [0.9, 1.9])
        np.testing.assert_allclose(x.hi, [1.1, 2.1])
        assert abs(x.mean_width() - 0.2) < 1e-10

    def test_relu(self):
        x = IntervalTensor(np.array([-1.0, 0.5, -0.3]), np.array([0.5, 1.0, -0.1]))
        r = x.relu()
        np.testing.assert_allclose(r.lo, [0.0, 0.5, 0.0])
        np.testing.assert_allclose(r.hi, [0.5, 1.0, 0.0])

    def test_sigmoid(self):
        x = IntervalTensor(np.array([-2.0, 0.0]), np.array([2.0, 0.0]))
        s = x.sigmoid()
        assert s.lo[0] < 0.5  # sig(-2) < 0.5
        assert s.hi[0] > 0.5  # sig(2) > 0.5
        np.testing.assert_allclose(s.lo[1], 0.5)
        np.testing.assert_allclose(s.hi[1], 0.5)


class TestIntervalMatmul:
    def test_exact_weights_positive(self):
        W = np.array([[1.0, 2.0], [3.0, 4.0]])
        v = IntervalTensor.from_exact(np.array([1.0, 1.0]))
        result = interval_matmul_exact_weights(W, v)
        np.testing.assert_allclose(result.lo, [3.0, 7.0])
        np.testing.assert_allclose(result.hi, [3.0, 7.0])

    def test_exact_weights_with_uncertainty(self):
        W = np.array([[1.0, -1.0]])
        v = IntervalTensor(np.array([0.9, 0.9]), np.array([1.1, 1.1]))
        result = interval_matmul_exact_weights(W, v)
        # lo = 1*0.9 + (-1)*1.1 = -0.2
        # hi = 1*1.1 + (-1)*0.9 = 0.2
        np.testing.assert_allclose(result.lo, [-0.2])
        np.testing.assert_allclose(result.hi, [0.2])


class TestIntervalLinear:
    def test_exact_matches_torch(self):
        """Exact inputs -> result matches standard PyTorch."""
        torch_layer = torch.nn.Linear(3, 2)
        interval_layer = IntervalLinear.from_torch(torch_layer)

        x = np.array([1.0, 2.0, 3.0])
        x_interval = IntervalTensor.from_exact(x)

        result = interval_layer(x_interval)

        with torch.no_grad():
            expected = torch_layer(torch.FloatTensor(x)).numpy()

        np.testing.assert_allclose(result.lo, expected, atol=1e-6)
        np.testing.assert_allclose(result.hi, expected, atol=1e-6)

    def test_contains_truth(self):
        """Interval result ALWAYS contains the exact result (soundness)."""
        torch_layer = torch.nn.Linear(4, 3)
        interval_layer = IntervalLinear.from_torch(torch_layer)

        rng = np.random.default_rng(42)
        for _ in range(100):
            x_exact = rng.standard_normal(4)
            eps = 0.1
            x_interval = IntervalTensor.from_uncertainty(x_exact, eps)

            result = interval_layer(x_interval)

            with torch.no_grad():
                expected = torch_layer(torch.FloatTensor(x_exact)).numpy()

            assert np.all(result.lo <= expected + 1e-6), (
                f"Lower bound violation: {result.lo} > {expected}"
            )
            assert np.all(result.hi >= expected - 1e-6), (
                f"Upper bound violation: {result.hi} < {expected}"
            )


class TestIntervalReLU:
    def test_shrinks_intervals(self):
        """ReLU does not expand intervals (may shrink them)."""
        x = IntervalTensor(
            np.array([-0.5, 0.3, -0.1]),
            np.array([0.5, 0.7, 0.2]),
        )
        result = IntervalReLU()(x)
        assert np.all(result.width <= x.width + 1e-10)


class TestConvertModel:
    def test_convert_and_run(self):
        """convert_model works on a simple Sequential."""
        model = torch.nn.Sequential(
            torch.nn.Linear(4, 3),
            torch.nn.ReLU(),
            torch.nn.Linear(3, 2),
        )
        interval_model = convert_model(model)

        x = IntervalTensor.from_uncertainty(np.random.randn(4), 0.1)
        result = interval_model(x)
        assert result.shape == (2,)
        assert np.all(result.lo <= result.hi)

    def test_soundness_full_model(self):
        """Full model: interval output contains exact output."""
        model = torch.nn.Sequential(
            torch.nn.Linear(4, 8),
            torch.nn.ReLU(),
            torch.nn.Linear(8, 4),
            torch.nn.ReLU(),
            torch.nn.Linear(4, 2),
        )
        interval_model = convert_model(model)

        rng = np.random.default_rng(42)
        for _ in range(50):
            x_exact = rng.standard_normal(4)
            x_interval = IntervalTensor.from_uncertainty(x_exact, 0.05)

            result = interval_model(x_interval)

            with torch.no_grad():
                expected = model(torch.FloatTensor(x_exact)).numpy()

            assert np.all(result.lo <= expected + 1e-5), (
                f"Lower bound violation: {result.lo} > {expected}"
            )
            assert np.all(result.hi >= expected - 1e-5), (
                f"Upper bound violation: {result.hi} < {expected}"
            )


class TestIntervalSoftmax:
    def test_bounds_valid(self):
        """Softmax output is within [0, 1]."""
        x = IntervalTensor(np.array([-1.0, 0.5, 2.0]), np.array([0.0, 1.5, 3.0]))
        result = IntervalSoftmax()(x)
        assert np.all(result.lo >= 0.0)
        assert np.all(result.hi <= 1.0)
        assert np.all(result.lo <= result.hi)

    def test_exact_matches(self):
        """Exact inputs -> softmax lo == hi == standard softmax."""
        logits = np.array([1.0, 2.0, 3.0])
        x = IntervalTensor.from_exact(logits)
        result = IntervalSoftmax()(x)

        expected = np.exp(logits) / np.sum(np.exp(logits))
        np.testing.assert_allclose(result.lo, expected, atol=1e-6)
        np.testing.assert_allclose(result.hi, expected, atol=1e-6)


class TestWidthBound:
    """Tests for predict_max_width — Coq-proven width bound."""

    def test_bound_holds_single_layer(self):
        """Width bound >= actual width for a single Linear layer."""
        layer = torch.nn.Linear(4, 3)
        model = convert_model(torch.nn.Sequential(layer))

        eps = 0.05
        bound_info = predict_max_width(model, eps)

        # Run actual interval propagation
        rng = np.random.default_rng(42)
        for _ in range(50):
            x = rng.standard_normal(4)
            x_interval = IntervalTensor.from_uncertainty(x, eps)
            result = model(x_interval)
            actual_max_width = result.max_width()
            assert actual_max_width <= bound_info["output_width_bound"] + 1e-10, (
                f"Width bound violated: {actual_max_width} > {bound_info['output_width_bound']}"
            )

    def test_bound_holds_multilayer(self):
        """Width bound >= actual width for multi-layer model."""
        model = torch.nn.Sequential(
            torch.nn.Linear(4, 8),
            torch.nn.ReLU(),
            torch.nn.Linear(8, 4),
            torch.nn.ReLU(),
            torch.nn.Linear(4, 2),
        )
        interval_model = convert_model(model)

        eps = 0.1
        bound_info = predict_max_width(interval_model, eps)

        rng = np.random.default_rng(42)
        for _ in range(50):
            x = rng.standard_normal(4)
            x_interval = IntervalTensor.from_uncertainty(x, eps)
            result = interval_model(x_interval)
            actual_max_width = result.max_width()
            assert actual_max_width <= bound_info["output_width_bound"] + 1e-10, (
                f"Width bound violated: {actual_max_width} > {bound_info['output_width_bound']}"
            )

    def test_bound_structure(self):
        """predict_max_width returns correct structure."""
        model = convert_model(torch.nn.Sequential(
            torch.nn.Linear(4, 3),
            torch.nn.ReLU(),
            torch.nn.Linear(3, 2),
        ))
        result = predict_max_width(model, 0.1)
        assert "input_eps" in result
        assert "output_width_bound" in result
        assert "layer_l1_norms" in result
        assert "blowup_factor" in result
        assert len(result["layer_l1_norms"]) == 2  # two Linear layers
        assert result["output_width_bound"] > 0
        assert result["blowup_factor"] > 0

    def test_relu_does_not_increase_bound(self):
        """Adding ReLU doesn't increase the bound (proven in Coq)."""
        # Model without ReLU
        torch.manual_seed(42)
        linear1 = torch.nn.Linear(4, 3)
        linear2 = torch.nn.Linear(3, 2)

        model_no_relu = convert_model(torch.nn.Sequential(linear1, linear2))

        # Model with ReLU (same weights)
        torch.manual_seed(42)
        linear1b = torch.nn.Linear(4, 3)
        linear2b = torch.nn.Linear(3, 2)
        model_with_relu = convert_model(torch.nn.Sequential(
            linear1b, torch.nn.ReLU(), linear2b
        ))

        eps = 0.1
        bound_no = predict_max_width(model_no_relu, eps)
        bound_with = predict_max_width(model_with_relu, eps)

        # Same bound because ReLU doesn't change the L1-norm product
        assert abs(bound_no["output_width_bound"] - bound_with["output_width_bound"]) < 1e-10
