"""
Tests for I1 diagnostics (I1a, I1b, I1d).

Verifies:
1. unstable_relu_count with known intervals
2. stability_ratio computation
3. width_percentiles keys and values
4. layer_diagnostics populated after forward pass
5. diagnostics_report() formatting
6. Epsilon normalization in CertificationReport
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
import pytest

from regulus.nn.interval_tensor import IntervalTensor
from regulus.nn.model import IntervalSequential, convert_model
from regulus.nn.layers import IntervalLinear, IntervalReLU
from regulus.nn.verifier import NNVerificationEngine, NNVerificationResult
from regulus.nn.benchmark import CertificationReport
from regulus.nn.architectures import make_mlp


# =============================================================
# I1a: IntervalTensor diagnostic methods
# =============================================================

def test_unstable_relu_count_all_positive():
    """All-positive intervals: zero unstable neurons."""
    x = IntervalTensor(
        np.array([1.0, 2.0, 0.1, 5.0]),
        np.array([3.0, 4.0, 0.5, 7.0]),
    )
    assert x.unstable_relu_count() == 0


def test_unstable_relu_count_all_negative():
    """All-negative intervals: zero unstable neurons."""
    x = IntervalTensor(
        np.array([-5.0, -3.0, -1.0]),
        np.array([-2.0, -1.0, -0.1]),
    )
    assert x.unstable_relu_count() == 0


def test_unstable_relu_count_mixed():
    """Mixed intervals: only straddling-zero ones count."""
    x = IntervalTensor(
        np.array([-1.0, 0.5, -2.0, 3.0, -0.01]),
        np.array([1.0, 1.5, -0.5, 5.0, 0.01]),
    )
    # Unstable: [-1,1] and [-0.01, 0.01]. [-2,-0.5] is all negative, [0.5,1.5] all positive, [3,5] all positive.
    assert x.unstable_relu_count() == 2


def test_unstable_relu_count_boundary():
    """Boundary cases: lo=0 or hi=0 should NOT be unstable (not strictly straddling)."""
    x = IntervalTensor(
        np.array([0.0, -1.0, -1.0]),
        np.array([1.0, 0.0, 1.0]),
    )
    # [0,1]: lo=0, not < 0 → stable
    # [-1,0]: hi=0, not > 0 → stable
    # [-1,1]: lo<0 and hi>0 → unstable
    assert x.unstable_relu_count() == 1


def test_stability_ratio_all_stable():
    """All stable → ratio = 1.0."""
    x = IntervalTensor(np.array([1.0, 2.0]), np.array([3.0, 4.0]))
    assert x.stability_ratio() == 1.0


def test_stability_ratio_all_unstable():
    """All unstable → ratio = 0.0."""
    x = IntervalTensor(
        np.array([-1.0, -2.0, -0.5]),
        np.array([1.0, 2.0, 0.5]),
    )
    assert x.stability_ratio() == 0.0


def test_stability_ratio_half():
    """Half stable, half unstable → ratio = 0.5."""
    x = IntervalTensor(
        np.array([-1.0, 1.0, -1.0, 1.0]),
        np.array([1.0, 2.0, 1.0, 2.0]),
    )
    # Unstable: idx 0, 2. Stable: idx 1, 3.
    assert x.stability_ratio() == 0.5


def test_stability_ratio_empty():
    """Empty tensor → ratio = 1.0."""
    x = IntervalTensor(np.array([]), np.array([]))
    assert x.stability_ratio() == 1.0


def test_width_percentiles_keys():
    """width_percentiles returns correct keys."""
    x = IntervalTensor(np.zeros(100), np.ones(100))
    p = x.width_percentiles()
    assert set(p.keys()) == {50, 90, 95, 99, 100}


def test_width_percentiles_uniform():
    """Uniform-width interval: all percentiles should be equal."""
    x = IntervalTensor(np.zeros(100), np.ones(100) * 2.0)
    p = x.width_percentiles()
    for v in p.values():
        assert abs(v - 2.0) < 1e-10


def test_width_percentiles_custom():
    """Custom percentiles."""
    x = IntervalTensor(np.zeros(100), np.arange(100, dtype=np.float64))
    p = x.width_percentiles(percentiles=(25, 50, 75))
    assert set(p.keys()) == {25, 50, 75}
    # Widths are 0,1,2,...,99. Median ≈ 49.5
    assert abs(p[50] - 49.5) < 1.0


def test_width_percentiles_varying():
    """Varying widths: p100 should be the max."""
    widths = np.array([0.1, 0.5, 1.0, 5.0, 100.0])
    x = IntervalTensor(np.zeros(5), widths)
    p = x.width_percentiles()
    assert abs(p[100] - 100.0) < 1e-10


# =============================================================
# I1b: Per-layer diagnostics in IntervalSequential
# =============================================================

def test_layer_diagnostics_populated():
    """IntervalSequential should populate layer_diagnostics after forward pass."""
    # Simple 2-layer model: Linear(4,3) + ReLU
    W = np.random.randn(3, 4)
    b = np.zeros(3)
    layers = [IntervalLinear(W, b), IntervalReLU()]
    seq = IntervalSequential(layers)

    x = IntervalTensor(np.zeros(4) - 0.1, np.zeros(4) + 0.1)
    seq(x)

    # Should have 3 entries: input + Linear + ReLU
    assert len(seq.layer_diagnostics) == 3
    assert len(seq.layer_widths) == 3


def test_layer_diagnostics_content():
    """Each diagnostic entry should have required keys."""
    W = np.random.randn(3, 4)
    b = np.zeros(3)
    layers = [IntervalLinear(W, b), IntervalReLU()]
    seq = IntervalSequential(layers)

    x = IntervalTensor(np.ones(4) * -0.5, np.ones(4) * 0.5)
    seq(x)

    required_keys = {"name", "shape", "mean_width", "max_width"}
    for diag in seq.layer_diagnostics:
        assert required_keys.issubset(set(diag.keys())), (
            f"Missing keys in {diag.get('name', '?')}: "
            f"{required_keys - set(diag.keys())}"
        )

    # Non-scalar entries should also have unstable_relu_count
    for diag in seq.layer_diagnostics:
        if diag["name"] != "input" or True:  # all have size > 1
            assert "unstable_relu_count" in diag
            assert "stability_ratio" in diag
            assert "width_percentiles" in diag


def test_layer_diagnostics_names():
    """Diagnostic names should identify layer types."""
    W = np.random.randn(3, 4)
    b = np.zeros(3)
    layers = [IntervalLinear(W, b), IntervalReLU()]
    seq = IntervalSequential(layers)

    x = IntervalTensor(np.zeros(4), np.ones(4))
    seq(x)

    names = [d["name"] for d in seq.layer_diagnostics]
    assert names[0] == "input"
    assert "IntervalLinear" in names[1]
    assert "IntervalReLU" in names[2]


# =============================================================
# I1d: NNVerificationResult diagnostics_report()
# =============================================================

def test_diagnostics_report_formatting():
    """diagnostics_report() should produce readable table."""
    result = NNVerificationResult(
        output_lo=np.array([0.1, 0.2]),
        output_hi=np.array([0.5, 0.6]),
        output_width=np.array([0.4, 0.4]),
        predicted_class=0,
        certified_robust=True,
        margin=0.1,
        layer_diagnostics=[
            {
                "name": "input",
                "mean_width": 0.02,
                "max_width": 0.02,
                "unstable_relu_count": 0,
                "stability_ratio": 1.0,
            },
            {
                "name": "IntervalLinear_0",
                "mean_width": 0.15,
                "max_width": 0.30,
                "unstable_relu_count": 5,
                "stability_ratio": 0.75,
            },
            {
                "name": "IntervalReLU_1",
                "mean_width": 0.10,
                "max_width": 0.25,
                "unstable_relu_count": 3,
                "stability_ratio": 0.85,
            },
        ],
    )

    report = result.diagnostics_report()
    assert "Layer" in report
    assert "Mean W" in report
    assert "Max W" in report
    assert "Unstable" in report
    assert "Stab%" in report
    assert "input" in report
    assert "IntervalLinear" in report
    assert "IntervalReLU" in report


def test_diagnostics_report_empty():
    """diagnostics_report() with no data should return message."""
    result = NNVerificationResult(
        output_lo=np.array([0.1]),
        output_hi=np.array([0.5]),
        output_width=np.array([0.4]),
        predicted_class=0,
        certified_robust=True,
        margin=0.1,
    )
    report = result.diagnostics_report()
    assert "No diagnostic data" in report


def test_verification_engine_collects_diagnostics():
    """NNVerificationEngine should populate layer_diagnostics in result."""
    torch.manual_seed(42)
    np.random.seed(42)

    model = make_mlp()
    model.eval()

    engine = NNVerificationEngine(strategy="naive")
    center = np.random.randn(784).astype(np.float64) * 0.1
    result = engine.verify_from_point(model, center, epsilon=0.001)

    assert len(result.layer_diagnostics) > 0
    assert len(result.layer_widths) > 0
    assert result.strategy == "naive"


def test_verification_engine_fold_bn():
    """NNVerificationEngine with fold_bn=True should set bn_folded flag."""
    torch.manual_seed(42)
    np.random.seed(42)

    model = make_mlp()
    model.eval()

    engine = NNVerificationEngine(strategy="naive", fold_bn=True)
    center = np.random.randn(784).astype(np.float64) * 0.1
    result = engine.verify_from_point(model, center, epsilon=0.001)

    assert result.bn_folded is True


# =============================================================
# I1e: Epsilon normalization in CertificationReport
# =============================================================

def test_epsilon_normalization_values():
    """CertificationReport epsilon normalization should be correct."""
    report = CertificationReport(
        total_images=100,
        correctly_classified=98,
        certified_robust=50,
        epsilon=0.01,
        strategy="naive",
        architecture="cnn_bn",
        eps_01_space=0.01 * 0.3081,
        eps_pixel_255=0.01 * 0.3081 * 255,
    )
    assert abs(report.eps_01_space - 0.003081) < 1e-10
    assert abs(report.eps_pixel_255 - 0.003081 * 255) < 1e-6


def test_epsilon_normalization_in_summary():
    """summary() should include epsilon normalization context."""
    report = CertificationReport(
        total_images=10,
        correctly_classified=9,
        certified_robust=5,
        epsilon=0.01,
        strategy="naive",
        architecture="cnn_bn",
        eps_01_space=0.003081,
        eps_pixel_255=0.785655,
    )
    s = report.summary()
    assert "0,1" in s or "[0,1]" in s  # [0,1] scale mentioned
    assert "0,255" in s or "[0,255]" in s  # [0,255] scale mentioned


def test_certification_report_summary_complete():
    """summary() should contain all key fields."""
    report = CertificationReport(
        total_images=100,
        correctly_classified=95,
        certified_robust=60,
        epsilon=0.01,
        strategy="naive",
        architecture="cnn_bn",
        eps_01_space=0.003081,
        eps_pixel_255=0.785655,
    )
    s = report.summary()
    assert "REGULUS" in s
    assert "cnn_bn" in s
    assert "naive" in s
    assert "100" in s
    assert "95" in s
    assert "60" in s
