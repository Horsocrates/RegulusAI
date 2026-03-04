"""Tests for EVT reliability score integration and adversarial suite.

Tests:
    - EVT margin computation (no torch)
    - EVT argmax grid functions (no torch)
    - Adversarial suite scaling and generation (no torch)
    - Certified gap formula (no torch)
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

# Load EVT module directly (no torch dependency)
from regulus.interval.evt import argmax_idx, max_on_grid

# Load adversarial.py directly to bypass regulus.nn.__init__ (which imports torch)
_adv_spec = importlib.util.spec_from_file_location(
    "regulus.nn.adversarial",
    Path(__file__).resolve().parent.parent / "regulus" / "nn" / "adversarial.py",
)
_adv_mod = importlib.util.module_from_spec(_adv_spec)
sys.modules["regulus.nn.adversarial"] = _adv_mod
_adv_spec.loader.exec_module(_adv_mod)

scale_to_perturbation_ball = _adv_mod.scale_to_perturbation_ball
generate_adversarial_suite = _adv_mod.generate_adversarial_suite
certified_gap = _adv_mod.certified_gap

# Load verifier module's _compute_evt_margin directly
_verifier_path = Path(__file__).resolve().parent.parent / "regulus" / "nn" / "verifier.py"


def _get_compute_evt_margin():
    """Extract _compute_evt_margin without loading full verifier (torch dep)."""
    source = _verifier_path.read_text()
    start = source.index("def _compute_evt_margin(")
    end = source.index("\nclass NNVerificationEngine:", start)
    func_source = source[start:end]
    ns = {"np": np, "argmax_idx": argmax_idx, "Optional": None}
    exec(func_source, ns)
    return ns["_compute_evt_margin"]


_compute_evt_margin = _get_compute_evt_margin()


# ---------------------------------------------------------------------------
#  Test EVT margin computation (no torch needed)
# ---------------------------------------------------------------------------

class TestEVTMargin:
    """Test _compute_evt_margin function."""

    def test_positive_margin_when_separated(self):
        """When predicted class has non-overlapping bounds, margin > 0."""
        lo = np.array([3.0, 1.0, 0.0])
        hi = np.array([5.0, 2.5, 1.0])
        margin = _compute_evt_margin(lo, hi, 0)
        assert margin == pytest.approx(0.5)

    def test_negative_margin_when_overlapping(self):
        """When bounds overlap, margin < 0."""
        lo = np.array([2.0, 2.5])
        hi = np.array([4.0, 3.5])
        margin = _compute_evt_margin(lo, hi, 0)
        assert margin == pytest.approx(-1.5)

    def test_single_class(self):
        """Single class: margin equals lo[0]."""
        lo = np.array([5.0])
        hi = np.array([7.0])
        margin = _compute_evt_margin(lo, hi, 0)
        assert margin == pytest.approx(5.0)

    def test_ten_classes_finds_worst_competitor(self):
        """With 10 classes, finds the highest non-predicted upper bound."""
        lo = np.zeros(10)
        hi = np.zeros(10)
        lo[3] = 5.0
        hi[3] = 8.0
        hi[7] = 4.8
        hi[1] = 3.0
        hi[9] = 2.0
        margin = _compute_evt_margin(lo, hi, 3)
        assert margin == pytest.approx(0.2)

    def test_evt_margin_uses_argmax(self):
        """Verify argmax_idx finds the max correctly."""
        values = [1.0, 3.0, 2.5, 0.5]
        idx = argmax_idx(lambda x: x, values)
        assert values[idx] == 3.0

    def test_margin_zero_at_boundary(self):
        """Margin = 0 when lo[pred] exactly equals max(hi[others])."""
        lo = np.array([3.0, 1.0])
        hi = np.array([5.0, 3.0])
        margin = _compute_evt_margin(lo, hi, 0)
        assert margin == pytest.approx(0.0)

    def test_margin_symmetric(self):
        """Margin for class 1 differs from class 0."""
        lo = np.array([2.0, 3.0])
        hi = np.array([4.0, 5.0])
        m0 = _compute_evt_margin(lo, hi, 0)
        m1 = _compute_evt_margin(lo, hi, 1)
        assert m0 == pytest.approx(-3.0)
        assert m1 == pytest.approx(-1.0)


class TestEVTArgmaxGrid:
    """Test EVT grid functions used for reliability scoring."""

    def test_max_on_grid_quadratic(self):
        """max_on_grid finds maximum of quadratic on grid."""
        f = lambda x: -(x - 0.3) ** 2
        val = max_on_grid(f, 0.0, 1.0, 100)
        assert val > -0.001

    def test_max_on_grid_monotone_refinement(self):
        """More grid points = better approximation."""
        f = lambda x: -(x - 0.37) ** 2
        v10 = max_on_grid(f, 0.0, 1.0, 10)
        v100 = max_on_grid(f, 0.0, 1.0, 100)
        assert v100 >= v10 - 1e-10


# ---------------------------------------------------------------------------
#  Test adversarial suite functions (no torch needed)
# ---------------------------------------------------------------------------

class TestAdversarialSuite:
    """Test adversarial suite generation and scaling."""

    def test_scale_to_perturbation_ball(self):
        """Scale maps [0,1]^d to [center-eps, center+eps]^d."""
        point_01 = [0.0, 0.5, 1.0]
        center = [1.0, 2.0, 3.0]
        eps = 0.1
        result = scale_to_perturbation_ball(point_01, center, eps)
        assert result[0] == pytest.approx(0.9)
        assert result[1] == pytest.approx(2.0)
        assert result[2] == pytest.approx(3.1)

    def test_scale_midpoint_is_center(self):
        """Midpoint [0.5, 0.5, ...] maps to center."""
        center = [5.0, -3.0, 0.0]
        point_01 = [0.5, 0.5, 0.5]
        result = scale_to_perturbation_ball(point_01, center, 1.0)
        for r, c in zip(result, center):
            assert r == pytest.approx(c)

    def test_generate_suite_produces_candidates(self):
        """Suite generates the requested number of candidates."""
        test_points = [[0.2, 0.3], [0.5, 0.7], [0.1, 0.9]]
        center = [0.5, 0.5]
        candidates = generate_adversarial_suite(
            test_points, center, epsilon=0.1, n_candidates=5, steps=3
        )
        assert len(candidates) == 5
        assert all(len(c) == 2 for c in candidates)

    def test_suite_candidates_in_ball(self):
        """All candidates are within perturbation ball."""
        test_points = [[0.3, 0.4], [0.6, 0.8]]
        center = [0.5, 0.5]
        eps = 0.2
        candidates = generate_adversarial_suite(
            test_points, center, epsilon=eps, n_candidates=3, steps=2
        )
        for pt in candidates:
            for d, (p, c) in enumerate(zip(pt, center)):
                assert c - eps - 1e-10 <= p <= c + eps + 1e-10, \
                    f"dim {d}: {p} not in [{c-eps}, {c+eps}]"

    def test_suite_empty_test_points(self):
        """Empty test_points returns empty candidates."""
        candidates = generate_adversarial_suite([], [0.5], 0.1)
        assert candidates == []


class TestCertifiedGap:
    """Test certified gap formula."""

    def test_gap_formula(self):
        """certified_gap(k) = 1/(48 * 3^k)."""
        assert certified_gap(0) == pytest.approx(1 / 48)
        assert certified_gap(1) == pytest.approx(1 / 144)
        assert certified_gap(2) == pytest.approx(1 / 432)

    def test_gap_decreasing(self):
        """Gaps decrease geometrically."""
        for k in range(5):
            assert certified_gap(k + 1) < certified_gap(k)
