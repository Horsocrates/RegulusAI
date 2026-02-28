"""Tests for differentiable IBP forward pass and loss computation."""

import pytest
import torch
import torch.nn as nn
import numpy as np

from regulus.nn.ibp_loss import ibp_forward, ibp_worst_case_loss, ibp_combined_loss


# ─── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def simple_linear():
    """Simple Linear model: 4 -> 3."""
    model = nn.Sequential(nn.Linear(4, 3))
    model.eval()
    return model


@pytest.fixture
def mlp_relu():
    """MLP with ReLU: 4 -> 8 -> 3."""
    model = nn.Sequential(
        nn.Linear(4, 8),
        nn.ReLU(),
        nn.Linear(8, 3),
    )
    model.eval()
    return model


@pytest.fixture
def cnn_bn_model():
    """Small CNN+BN model similar to CIFAR architecture."""
    model = nn.Sequential(
        nn.Conv2d(3, 8, 3, padding=1),
        nn.BatchNorm2d(8),
        nn.ReLU(),
        nn.AvgPool2d(2),
        nn.Flatten(),
        nn.Linear(8 * 4 * 4, 10),
    )
    # Run a dummy forward to initialize BN running stats
    model.train()
    dummy = torch.randn(4, 3, 8, 8)
    model(dummy)
    model.eval()
    return model


@pytest.fixture
def cifar_cnn_bn():
    """CIFAR-10 CNN with BN + MaxPool (real architecture)."""
    model = nn.Sequential(
        nn.Conv2d(3, 32, 3, padding=1),
        nn.BatchNorm2d(32),
        nn.ReLU(),
        nn.Conv2d(32, 32, 3, padding=1),
        nn.BatchNorm2d(32),
        nn.ReLU(),
        nn.MaxPool2d(2),
        nn.Conv2d(32, 64, 3, padding=1),
        nn.BatchNorm2d(64),
        nn.ReLU(),
        nn.Conv2d(64, 64, 3, padding=1),
        nn.BatchNorm2d(64),
        nn.ReLU(),
        nn.MaxPool2d(2),
        nn.Flatten(),
        nn.Linear(64 * 8 * 8, 256),
        nn.ReLU(),
        nn.Linear(256, 10),
    )
    # Initialize BN running stats
    model.train()
    dummy = torch.randn(4, 3, 32, 32)
    model(dummy)
    model.eval()
    return model


# ─── Test: ibp_forward basic ────────────────────────────────────────

class TestIBPForward:

    def test_point_interval_equals_forward(self, simple_linear):
        """Zero-width interval should produce identical lo and hi."""
        x = torch.randn(2, 4)
        lo, hi = ibp_forward(simple_linear, x, x)

        expected = simple_linear(x)
        torch.testing.assert_close(lo, expected, atol=1e-6, rtol=1e-5)
        torch.testing.assert_close(hi, expected, atol=1e-6, rtol=1e-5)

    def test_lo_le_hi(self, simple_linear):
        """Lower bounds must be <= upper bounds."""
        x = torch.randn(2, 4)
        eps = 0.1
        lo, hi = ibp_forward(simple_linear, x - eps, x + eps)
        assert (lo <= hi + 1e-6).all(), f"lo > hi found: max diff = {(lo - hi).max()}"

    def test_soundness_linear(self, simple_linear):
        """Random points in input interval must produce outputs in output interval."""
        x = torch.randn(5, 4)
        eps = 0.1
        lo, hi = ibp_forward(simple_linear, x - eps, x + eps)

        # Sample 100 random points in [x-eps, x+eps]
        for _ in range(100):
            noise = torch.rand_like(x) * 2 * eps - eps
            x_pert = x + noise
            out = simple_linear(x_pert)
            assert (out >= lo - 1e-5).all(), "Output below lower bound"
            assert (out <= hi + 1e-5).all(), "Output above upper bound"

    def test_soundness_mlp(self, mlp_relu):
        """Soundness check for MLP with ReLU."""
        x = torch.randn(5, 4)
        eps = 0.05
        lo, hi = ibp_forward(mlp_relu, x - eps, x + eps)

        for _ in range(100):
            noise = torch.rand_like(x) * 2 * eps - eps
            x_pert = x + noise
            out = mlp_relu(x_pert)
            assert (out >= lo - 1e-5).all(), "Output below lower bound"
            assert (out <= hi + 1e-5).all(), "Output above upper bound"

    def test_soundness_cnn_bn(self, cnn_bn_model):
        """Soundness check for CNN+BN+AvgPool."""
        x = torch.randn(3, 3, 8, 8)
        eps = 0.01
        lo, hi = ibp_forward(cnn_bn_model, x - eps, x + eps)

        for _ in range(50):
            noise = torch.rand_like(x) * 2 * eps - eps
            x_pert = x + noise
            out = cnn_bn_model(x_pert)
            assert (out >= lo - 1e-4).all(), f"Below lo: {(lo - out).max()}"
            assert (out <= hi + 1e-4).all(), f"Above hi: {(out - hi).max()}"

    def test_width_increases_with_epsilon(self, simple_linear):
        """Larger epsilon should produce wider output intervals."""
        x = torch.randn(2, 4)

        lo1, hi1 = ibp_forward(simple_linear, x - 0.01, x + 0.01)
        lo2, hi2 = ibp_forward(simple_linear, x - 0.1, x + 0.1)

        w1 = (hi1 - lo1).mean()
        w2 = (hi2 - lo2).mean()
        assert w2 > w1, f"Wider eps should give wider output: {w1} vs {w2}"


# ─── Test: Gradient flow ───────────────────────────────────────────

class TestGradientFlow:

    def test_gradients_flow_linear(self, simple_linear):
        """Gradients must flow to Linear weights."""
        x = torch.randn(2, 4)
        eps = 0.1
        lo, hi = ibp_forward(simple_linear, x - eps, x + eps)
        loss = (hi - lo).sum()  # Minimize width
        loss.backward()

        for name, p in simple_linear.named_parameters():
            assert p.grad is not None, f"No gradient for {name}"
            assert p.grad.abs().sum() > 0, f"Zero gradient for {name}"

    def test_gradients_flow_mlp(self, mlp_relu):
        """Gradients must flow through ReLU to all layers."""
        x = torch.randn(2, 4)
        eps = 0.1
        lo, hi = ibp_forward(mlp_relu, x - eps, x + eps)
        loss = (hi - lo).sum()
        loss.backward()

        for name, p in mlp_relu.named_parameters():
            assert p.grad is not None, f"No gradient for {name}"

    def test_gradients_flow_cnn_bn(self, cnn_bn_model):
        """Gradients flow through Conv2d + BN + AvgPool + Linear."""
        x = torch.randn(2, 3, 8, 8)
        eps = 0.01
        lo, hi = ibp_forward(cnn_bn_model, x - eps, x + eps)
        loss = (hi - lo).sum()
        loss.backward()

        grad_count = 0
        for name, p in cnn_bn_model.named_parameters():
            if p.grad is not None and p.grad.abs().sum() > 0:
                grad_count += 1
        assert grad_count > 0, "No gradients flowed to any parameter"

    def test_ibp_loss_gradients(self, mlp_relu):
        """ibp_worst_case_loss produces gradients."""
        x = torch.randn(4, 4)
        labels = torch.tensor([0, 1, 2, 0])
        eps = 0.1

        lo, hi = ibp_forward(mlp_relu, x - eps, x + eps)
        loss = ibp_worst_case_loss(lo, hi, labels)
        loss.backward()

        has_grad = any(
            p.grad is not None and p.grad.abs().sum() > 0
            for p in mlp_relu.parameters()
        )
        assert has_grad, "ibp_worst_case_loss produced no gradients"


# ─── Test: ibp_worst_case_loss ──────────────────────────────────────

class TestIBPLoss:

    def test_zero_width_equals_clean(self, mlp_relu):
        """With zero-width interval, IBP loss == clean CE loss."""
        x = torch.randn(4, 4)
        labels = torch.tensor([0, 1, 2, 0])

        # Clean loss
        clean_out = mlp_relu(x)
        clean_loss = nn.CrossEntropyLoss()(clean_out, labels)

        # IBP loss with zero epsilon
        lo, hi = ibp_forward(mlp_relu, x, x)
        ibp_loss = ibp_worst_case_loss(lo, hi, labels)

        torch.testing.assert_close(
            ibp_loss, clean_loss, atol=1e-5, rtol=1e-4
        )

    def test_ibp_loss_ge_clean_loss(self, mlp_relu):
        """IBP loss should be >= clean loss (worst case is harder)."""
        x = torch.randn(8, 4)
        labels = torch.randint(0, 3, (8,))

        clean_out = mlp_relu(x)
        clean_loss = nn.CrossEntropyLoss()(clean_out, labels)

        lo, hi = ibp_forward(mlp_relu, x - 0.1, x + 0.1)
        ibp_loss = ibp_worst_case_loss(lo, hi, labels)

        # IBP loss >= clean loss (with tolerance for numerical issues)
        assert ibp_loss.item() >= clean_loss.item() - 0.01, (
            f"IBP loss {ibp_loss.item()} < clean loss {clean_loss.item()}"
        )

    def test_loss_positive(self, mlp_relu):
        """Cross-entropy loss is always positive."""
        x = torch.randn(4, 4)
        labels = torch.tensor([0, 1, 2, 0])
        lo, hi = ibp_forward(mlp_relu, x - 0.1, x + 0.1)
        loss = ibp_worst_case_loss(lo, hi, labels)
        assert loss.item() > 0


# ─── Test: ibp_combined_loss ────────────────────────────────────────

class TestIBPCombinedLoss:

    def test_lam_zero_is_clean(self, cnn_bn_model):
        """lambda=0 should give pure clean loss."""
        x = torch.randn(2, 3, 8, 8)
        labels = torch.randint(0, 10, (2,))

        loss, info = ibp_combined_loss(cnn_bn_model, x, labels, epsilon=0.01, lam=0.0)
        assert info["loss_ibp"] == 0.0
        assert info["loss_total"] == info["loss_clean"]

    def test_combined_loss_runs(self, cnn_bn_model):
        """Combined loss should run without errors."""
        x = torch.randn(2, 3, 8, 8)
        labels = torch.randint(0, 10, (2,))

        loss, info = ibp_combined_loss(cnn_bn_model, x, labels, epsilon=0.01, lam=0.5)
        assert loss.item() > 0
        assert info["loss_clean"] > 0
        assert info["loss_ibp"] > 0
        assert info["ibp_width"] > 0

    def test_combined_gradients(self, cnn_bn_model):
        """Combined loss should produce gradients."""
        x = torch.randn(2, 3, 8, 8)
        labels = torch.randint(0, 10, (2,))

        loss, info = ibp_combined_loss(cnn_bn_model, x, labels, epsilon=0.01, lam=0.5)
        loss.backward()

        has_grad = any(
            p.grad is not None and p.grad.abs().sum() > 0
            for p in cnn_bn_model.parameters()
        )
        assert has_grad, "Combined loss produced no gradients"


# ─── Test: Real CIFAR architecture ─────────────────────────────────

class TestCIFARArchitecture:

    def test_cifar_ibp_forward(self, cifar_cnn_bn):
        """ibp_forward works on real CIFAR architecture."""
        x = torch.randn(2, 3, 32, 32)
        eps = 0.01
        lo, hi = ibp_forward(cifar_cnn_bn, x - eps, x + eps)

        assert lo.shape == (2, 10)
        assert hi.shape == (2, 10)
        assert (lo <= hi + 1e-4).all()

    def test_cifar_ibp_gradients(self, cifar_cnn_bn):
        """Gradients flow through full CIFAR architecture."""
        x = torch.randn(2, 3, 32, 32)
        labels = torch.tensor([3, 7])
        eps = 0.01

        lo, hi = ibp_forward(cifar_cnn_bn, x - eps, x + eps)
        loss = ibp_worst_case_loss(lo, hi, labels)
        loss.backward()

        grad_params = [
            name for name, p in cifar_cnn_bn.named_parameters()
            if p.grad is not None and p.grad.abs().sum() > 0
        ]
        assert len(grad_params) > 0, "No gradients in CIFAR model"

    def test_cifar_soundness(self, cifar_cnn_bn):
        """Soundness on CIFAR architecture (small epsilon)."""
        x = torch.randn(2, 3, 32, 32)
        eps = 0.005
        lo, hi = ibp_forward(cifar_cnn_bn, x - eps, x + eps)

        for _ in range(20):
            noise = torch.rand_like(x) * 2 * eps - eps
            out = cifar_cnn_bn(x + noise)
            assert (out >= lo - 1e-3).all(), f"Below lo: {(lo - out).max()}"
            assert (out <= hi + 1e-3).all(), f"Above hi: {(out - hi).max()}"
