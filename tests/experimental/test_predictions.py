"""Tests for experimental predictions."""

import numpy as np
import pytest
from tests.experimental.predictions import (
    casimir_energy_lattice, compute_casimir_sequence,
    compute_lattice_spacing, mass_ratio_at_N, compute_higgs_sequence,
)


class TestCasimir:
    def test_finite_all_N(self):
        for N in [4, 8, 16, 32, 64, 128]:
            E = casimir_energy_lattice(N)
            assert np.isfinite(E), f"E_lattice({N}) not finite"

    def test_right_sign(self):
        results = compute_casimir_sequence()
        for r in results:
            assert r['E_casimir'] < 0, f"E_Casimir({r['N']}) = {r['E_casimir']} > 0"

    def test_convergence(self):
        """E_Casimir(N) converges (values stabilize)."""
        results = compute_casimir_sequence()
        vals = [r['E_casimir'] for r in results]
        # Last 3 values should be within 1% of each other
        assert abs(vals[-1] - vals[-2]) < abs(vals[-1]) * 0.01

    def test_converges_to_quarter(self):
        """Lattice Casimir converges to -1/4 (lattice value)."""
        results = compute_casimir_sequence()
        last = results[-1]['E_casimir']
        assert abs(last - (-0.25)) < 0.001, f"E_Casimir = {last}, expected -0.25"


class TestLatticeSpacing:
    def test_positive(self):
        s = compute_lattice_spacing()
        assert s['1/pi']['a_meters'] > 0

    def test_above_planck(self):
        s = compute_lattice_spacing()
        assert s['1/pi']['a_planck_lengths'] > 1

    def test_finite_and_positive(self):
        s = compute_lattice_spacing()
        a = s['1/pi']['a_meters']
        assert np.isfinite(a) and a > 0

    def test_report_scale(self):
        """Report what scale a is at (honest, may or may not be consistent)."""
        s = compute_lattice_spacing()
        a_um = s['1/pi']['a_micrometers']
        assert np.isfinite(a_um)  # just check it's computed


class TestHiggs:
    def test_finite_all_N(self):
        for N in [2, 4, 8, 16, 64]:
            r = mass_ratio_at_N(N)
            assert np.isfinite(r['corrected_ratio'])

    def test_tree_level(self):
        r = mass_ratio_at_N(4)
        assert abs(r['tree_ratio'] - 1 / np.sqrt(2)) < 1e-10

    def test_computed_for_range(self):
        results = compute_higgs_sequence()
        assert len(results) >= 8
        for r in results:
            assert 0 < r['corrected_ratio'] < 10
