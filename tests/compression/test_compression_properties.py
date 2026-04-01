"""
Property-based tests for ToS compression pipeline.
Uses hypothesis to verify properties that mirror Coq theorems.

Each property here corresponds to a Qed in the Coq formalization:
  - Lossless limit → CompressionPipeline.v: pipeline_lossless
  - Error monotone → ErrorComposition.v: more_modes_less_error
  - Parseval holds → FourierConvergence.v: parseval_*
  - Kraft ≤ 1 → VerifiedHuffman.v: kraft_balanced_le_1
  - Quantization bounded → VerifiedQuantization.v: error_bounded_3_2
"""

import numpy as np
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from tests.compression.tos_compression import (
    compress, decompress, mse, snr_db, max_error,
    parseval_check, kraft_sum, quantize, dequantize,
    dft_graph, idft_graph, cycle_eigenvalues
)


# ========================================================================
#  PROPERTY 1: LOSSLESS LIMIT
#  Coq: pipeline_lossless (CompressionPipeline.v)
# ========================================================================

class TestLosslessLimit:
    """When M=N and step→0, compression is nearly lossless."""

    @given(arrays(np.float64, 16, elements=st.floats(-10, 10, allow_nan=False, allow_infinity=False)))
    @settings(max_examples=50, deadline=5000)
    def test_full_modes_fine_step(self, f):
        """∀f: compress(f, M=N, step=small) ≈ f."""
        cs = compress(f, M=len(f), quant_step=0.0001, use_huffman=False)
        f_recon = decompress(cs)
        assert mse(f, f_recon) < 0.01

    def test_identity_signal(self):
        """Constant signal perfectly reconstructed."""
        f = np.ones(32) * 7.5
        cs = compress(f, M=32, quant_step=0.001, use_huffman=False)
        f_recon = decompress(cs)
        assert max_error(f, f_recon) < 0.01


# ========================================================================
#  PROPERTY 2: ERROR MONOTONE IN MODES
#  Coq: more_modes_less_error (ErrorComposition.v)
# ========================================================================

class TestErrorMonotone:
    """More modes → less error."""

    @pytest.mark.parametrize("N", [16, 32, 64])
    def test_monotone_sine(self, N):
        """For sine signal: error(M) ≥ error(M+k)."""
        t = np.linspace(0, 1, N, endpoint=False)
        f = np.sin(2 * np.pi * 5 * t)
        prev_error = float('inf')
        for M in range(1, N + 1, max(1, N // 8)):
            cs = compress(f, M=M, quant_step=0.001, use_huffman=False)
            f_recon = decompress(cs)
            err = mse(f, f_recon)
            assert err <= prev_error + 1e-8, \
                f"Error increased at M={M}: {err} > {prev_error}"
            prev_error = err

    @pytest.mark.parametrize("N", [16, 32])
    def test_monotone_noise(self, N):
        """For random signal: error decreases with M."""
        f = np.random.RandomState(42).randn(N)
        errors = []
        for M in [1, N//4, N//2, N]:
            cs = compress(f, M=M, quant_step=0.001, use_huffman=False)
            f_recon = decompress(cs)
            errors.append(mse(f, f_recon))
        # Should be roughly decreasing (with tolerance for quantization)
        assert errors[-1] <= errors[0] + 0.01


# ========================================================================
#  PROPERTY 3: PARSEVAL (ENERGY CONSERVATION)
#  Coq: parseval_* (FourierConvergence.v)
# ========================================================================

class TestParseval:
    """DFT preserves total energy."""

    @given(arrays(np.float64, 16, elements=st.floats(-5, 5, allow_nan=False, allow_infinity=False)))
    @settings(max_examples=50, deadline=5000)
    def test_parseval_random(self, f):
        """∀f: ‖f‖² = Σ |f̂_k|² · ‖φ_k‖² (Parseval)."""
        t_energy, f_energy = parseval_check(f)
        if t_energy > 1e-10:
            assert abs(t_energy - f_energy) / t_energy < 1e-6, \
                f"Parseval violation: {t_energy} vs {f_energy}"

    @pytest.mark.parametrize("N", [4, 8, 16, 32, 64])
    def test_parseval_sizes(self, N):
        """Parseval holds for various N."""
        f = np.sin(2 * np.pi * np.arange(N) / N)
        t_energy, f_energy = parseval_check(f)
        assert abs(t_energy - f_energy) < 1e-8 * max(t_energy, 1)


# ========================================================================
#  PROPERTY 4: KRAFT INEQUALITY
#  Coq: kraft_tree_4 == 1 (VerifiedHuffman.v)
# ========================================================================

class TestKraft:
    """Huffman codes satisfy Kraft: Σ 2^{-l_i} ≤ 1."""

    @pytest.mark.parametrize("N", [16, 32, 64, 128])
    def test_kraft_various_signals(self, N):
        """∀ signal → Huffman tree satisfies Kraft."""
        f = np.random.RandomState(42).randn(N)
        cs = compress(f, M=N//2, quant_step=0.1, use_huffman=True)
        if cs.codebook:
            ks = kraft_sum(cs.codebook)
            assert ks <= 1.0 + 1e-10, f"Kraft violated: {ks}"

    def test_kraft_uniform(self):
        """Uniform distribution → all codes equal length → Kraft = 1."""
        symbols = np.array([0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3])
        from tests.compression.tos_compression import build_huffman_tree
        codebook, _ = build_huffman_tree(symbols)
        ks = kraft_sum(codebook)
        assert abs(ks - 1.0) < 1e-10


# ========================================================================
#  PROPERTY 5: QUANTIZATION ERROR BOUNDED
#  Coq: error_bounded_3_2 (VerifiedQuantization.v)
# ========================================================================

class TestQuantizationBound:
    """Quantization error ≤ step/2."""

    @given(
        arrays(np.float64, 32, elements=st.floats(-100, 100, allow_nan=False, allow_infinity=False)),
        st.floats(0.01, 10.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=5000)
    def test_error_bounded(self, values, step):
        """∀x, ∀Δ>0: |x - dequant(quant(x, Δ), Δ)| ≤ Δ/2."""
        indices = quantize(values, step)
        recon = dequantize(indices, step)
        errors = np.abs(values - recon)
        assert np.all(errors <= step / 2 + 1e-10), \
            f"Quantization bound violated: max error {np.max(errors)} > {step/2}"

    @pytest.mark.parametrize("step", [0.01, 0.1, 0.5, 1.0, 5.0])
    def test_integers_preserved(self, step):
        """Integer multiples of step are preserved exactly."""
        values = np.arange(-5, 6) * step
        indices = quantize(values, step)
        recon = dequantize(indices, step)
        assert np.allclose(values, recon, atol=1e-10)


# ========================================================================
#  PROPERTY 6: EIGENVALUE STRUCTURE
#  Coq: cycle_eigenvalue_4 (FourierBasis.v)
# ========================================================================

class TestEigenvalueStructure:
    """Graph eigenvalues have expected properties."""

    @pytest.mark.parametrize("N", [4, 8, 16, 32, 64, 128])
    def test_eigenvalue_sum_zero(self, N):
        """Trace of adjacency = 0: Σ λ_k = 0."""
        ev = cycle_eigenvalues(N)
        assert abs(np.sum(ev)) < 1e-10

    @pytest.mark.parametrize("N", [4, 8, 16, 32])
    def test_eigenvalue_bounded(self, N):
        """All eigenvalues ∈ [-2, 2]."""
        ev = cycle_eigenvalues(N)
        assert np.all(ev >= -2 - 1e-10) and np.all(ev <= 2 + 1e-10)

    def test_N4_concrete(self):
        """N=4: eigenvalues = {2, 0, -2, 0} (matches Coq)."""
        ev = cycle_eigenvalues(4)
        expected = np.array([2.0, 0.0, -2.0, 0.0])
        np.testing.assert_allclose(ev, expected, atol=1e-10)
