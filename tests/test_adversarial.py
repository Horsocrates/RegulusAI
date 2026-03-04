"""Tests for regulus.nn.adversarial — trisection-based adversarial search."""

import importlib.util
import sys
from pathlib import Path

import pytest

# Load adversarial.py directly to bypass regulus.nn.__init__ (which imports torch)
_spec = importlib.util.spec_from_file_location(
    "regulus.nn.adversarial",
    Path(__file__).resolve().parent.parent / "regulus" / "nn" / "adversarial.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["regulus.nn.adversarial"] = _mod
_spec.loader.exec_module(_mod)

generate_adversarial_1d = _mod.generate_adversarial_1d
generate_adversarial_nd = _mod.generate_adversarial_nd
certified_gap = _mod.certified_gap


class TestAdversarial1D:
    def test_differs_from_enumeration(self):
        """Generated point differs from each test value."""
        values = [0.1, 0.3, 0.5, 0.7, 0.9]
        adv, gaps = generate_adversarial_1d(values)
        for i, v in enumerate(values):
            assert abs(adv - v) > 0, f"Adversarial equals test value {i}"

    def test_certified_gap_sizes(self):
        """Gap >= certified_gap(k) for each step."""
        values = [0.2, 0.4, 0.6, 0.8]
        adv, gaps = generate_adversarial_1d(values)
        for k in range(len(values)):
            assert gaps[k] >= certified_gap(k) - 1e-12, (
                f"Step {k}: gap={gaps[k]:.2e} < cert={certified_gap(k):.2e}"
            )

    def test_within_domain(self):
        """Generated point is within [a, b]."""
        adv, _ = generate_adversarial_1d([0.25, 0.75], domain=(0.0, 1.0))
        assert 0.0 <= adv <= 1.0

    def test_custom_domain(self):
        """Works on non-unit domain."""
        adv, _ = generate_adversarial_1d([5.0, 7.0, 9.0], domain=(4.0, 10.0))
        assert 4.0 <= adv <= 10.0

    def test_single_value(self):
        """Works with a single test value."""
        adv, gaps = generate_adversarial_1d([0.5])
        assert abs(adv - 0.5) > 0


class TestAdversarialND:
    def test_nd_produces_correct_dims(self):
        """Output has correct number of dimensions."""
        test_vecs = [[0.1, 0.5], [0.2, 0.8], [0.3, 0.6]]
        point, gaps = generate_adversarial_nd(test_vecs)
        assert len(point) == 3
        assert len(gaps) == 3

    def test_nd_within_domains(self):
        """Each coordinate within its domain."""
        test_vecs = [[0.5], [0.5]]
        domains = [(0.0, 1.0), (2.0, 3.0)]
        point, _ = generate_adversarial_nd(test_vecs, domains=domains)
        assert 0.0 <= point[0] <= 1.0
        assert 2.0 <= point[1] <= 3.0


class TestCertifiedGap:
    def test_certified_gap_values(self):
        """certified_gap(k) = 1 / (48 * 3^k)."""
        assert certified_gap(0) == pytest.approx(1 / 48)
        assert certified_gap(1) == pytest.approx(1 / 144)
        assert certified_gap(2) == pytest.approx(1 / 432)

    def test_certified_gap_decreasing(self):
        """Gaps decrease geometrically."""
        for k in range(10):
            assert certified_gap(k + 1) < certified_gap(k)
