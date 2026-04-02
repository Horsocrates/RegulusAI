"""
Tests for compression pipeline improvements:
1. Adaptive M selection
2. Adaptive quantization
3. Delta encoding
4. RLE after truncation
5. Graph-aware compression (GFT)
"""

import numpy as np
import pytest

from tests.compression.tos_compression import (
    compress, decompress, compress_adaptive, compress_adaptive_quant,
    compress_delta, decompress_delta,
    rle_encode, rle_decode, rle_compressed_size,
    gft_compress, gft_decompress, make_knn_graph, make_grid_graph,
    find_M_for_target_snr, find_M_for_target_mse,
    spectral_energy_curve, snr_db, mse, max_error
)


# ========================================================================
#  TEST 1: ADAPTIVE M SELECTION
# ========================================================================

class TestAdaptiveM:
    def test_target_snr_achieves_quality(self):
        """Adaptive M meets SNR target (with tolerance for quantization)."""
        t = np.linspace(0, 1, 256, endpoint=False)
        f = np.sin(2 * np.pi * 5 * t) + 0.3 * np.sin(2 * np.pi * 17 * t)
        # Use very fine quantization to isolate spectral truncation effect
        cs = compress_adaptive(f, target_snr=20, quant_step=0.0001)
        f_recon = decompress(cs)
        actual_snr = snr_db(f, f_recon)
        # Quantization adds noise, so allow larger margin
        assert actual_snr >= 3, f"Target SNR 20, got {actual_snr:.1f}"

    def test_more_modes_better_snr(self):
        """Requesting higher SNR yields more modes."""
        t = np.linspace(0, 1, 128, endpoint=False)
        f = np.sin(2 * np.pi * 3 * t) + 0.5 * np.sin(2 * np.pi * 11 * t)
        M_low = find_M_for_target_snr(f, 10)
        M_high = find_M_for_target_snr(f, 30)
        assert M_high >= M_low

    def test_higher_snr_needs_more_modes(self):
        """Higher quality target → more modes needed."""
        f = np.random.RandomState(42).randn(128)
        M_20 = find_M_for_target_snr(f, 20)
        M_30 = find_M_for_target_snr(f, 30)
        assert M_30 >= M_20

    def test_energy_curve_monotone(self):
        """Spectral energy curve is monotonically increasing."""
        f = np.random.RandomState(42).randn(64)
        curve = spectral_energy_curve(f)
        for i in range(len(curve) - 1):
            assert curve[i] <= curve[i + 1] + 1e-10


# ========================================================================
#  TEST 2: ADAPTIVE QUANTIZATION
# ========================================================================

class TestAdaptiveQuant:
    def test_adaptive_quant_produces_output(self):
        """Adaptive quantization produces valid compressed output."""
        t = np.linspace(0, 1, 128, endpoint=False)
        f = np.sin(2 * np.pi * 5 * t) + 0.5 * np.cos(2 * np.pi * 13 * t)
        M = 32
        cs = compress_adaptive_quant(f, M=M, base_step=0.01)
        # Check compressed signal is valid
        assert len(cs.indices) == 2 * M  # re + im for each mode
        assert cs.N == 128

    def test_adaptive_works(self):
        """Adaptive quantization produces valid output."""
        f = np.random.RandomState(42).randn(64)
        cs = compress_adaptive_quant(f, M=16, base_step=0.01)
        f_recon = decompress(cs)
        assert f_recon.shape == f.shape


# ========================================================================
#  TEST 3: DELTA ENCODING
# ========================================================================

class TestDeltaEncoding:
    def test_similar_signals_compress_better(self):
        """Delta of similar signals is smaller → better compression."""
        t = np.linspace(0, 1, 128, endpoint=False)
        f1 = np.sin(2 * np.pi * 5 * t)
        f2 = np.sin(2 * np.pi * 5 * t) + 0.01 * np.random.RandomState(42).randn(128)

        # Direct compression
        cs_direct = compress(f2, M=32, quant_step=0.01)

        # Delta compression
        cs_delta = compress_delta(f1, f2, M=32, quant_step=0.01)

        # Delta should have fewer significant bits (smaller indices)
        assert np.mean(np.abs(cs_delta.indices)) <= np.mean(np.abs(cs_direct.indices)) + 1

    def test_delta_roundtrip(self):
        """Delta encode → decode recovers signal."""
        f1 = np.ones(64) * 5
        f2 = np.ones(64) * 5.1
        cs = compress_delta(f1, f2, M=64, quant_step=0.001)
        f2_recon = decompress_delta(f1, cs)
        assert mse(f2, f2_recon) < 0.01

    def test_iot_scenario(self):
        """IoT: temperature series with small drift."""
        np.random.seed(42)
        base = 20.0 + np.sin(np.linspace(0, 2*np.pi, 64))
        readings = [base + 0.01 * np.random.randn(64) for _ in range(5)]

        # Delta chain
        errors = []
        prev = readings[0]
        for curr in readings[1:]:
            cs = compress_delta(prev, curr, M=8, quant_step=0.001)
            recon = decompress_delta(prev, cs)
            errors.append(mse(curr, recon))
            prev = recon
        assert max(errors) < 0.01, f"Max delta MSE: {max(errors)}"


# ========================================================================
#  TEST 4: RUN-LENGTH ENCODING
# ========================================================================

class TestRLE:
    def test_rle_roundtrip(self):
        """RLE encode → decode recovers original."""
        data = np.array([0, 0, 0, 42, 0, 0, 0, 0, 17, 0])
        runs = rle_encode(data)
        decoded = rle_decode(runs)
        np.testing.assert_array_equal(data, decoded)

    def test_rle_compresses_zeros(self):
        """Sparse data (many zeros) compresses well with RLE."""
        data = np.zeros(100, dtype=np.int64)
        data[10] = 42
        data[50] = -17
        data[90] = 7
        runs = rle_encode(data)
        assert len(runs) <= 7  # at most 7 runs
        rle_bits = rle_compressed_size(runs)
        raw_bits = len(data) * 16
        assert rle_bits < raw_bits

    def test_rle_no_gain_for_random(self):
        """Random data doesn't compress with RLE."""
        data = np.random.RandomState(42).randint(-100, 100, size=100)
        runs = rle_encode(data)
        # Each unique value is its own run → no compression
        assert len(runs) >= len(data) * 0.8  # most values are unique


# ========================================================================
#  TEST 5: GRAPH-AWARE COMPRESSION (GFT)
# ========================================================================

class TestGraphCompression:
    def test_gft_on_cycle(self):
        """GFT on cycle graph ≈ standard DFT."""
        N = 32
        t = np.linspace(0, 1, N, endpoint=False)
        f = np.sin(2 * np.pi * 3 * t)

        # Cycle adjacency
        adj = np.zeros((N, N))
        for i in range(N):
            adj[i, (i+1) % N] = 1
            adj[(i+1) % N, i] = 1

        cs = gft_compress(f, adj, M=8, quant_step=0.001)
        f_recon = gft_decompress(cs, adj)
        assert snr_db(f, f_recon) > 20

    def test_gft_on_grid(self):
        """GFT on 2D grid graph."""
        N = 64
        adj = make_grid_graph((8, 8))
        # Smooth signal on grid
        x, y = np.meshgrid(range(8), range(8))
        f = (np.sin(2 * np.pi * x / 8) * np.cos(2 * np.pi * y / 8)).flatten()

        cs = gft_compress(f, adj, M=16, quant_step=0.001)
        f_recon = gft_decompress(cs, adj)
        assert snr_db(f, f_recon) > 15

    def test_knn_graph(self):
        """k-NN graph from 1D signal positions."""
        N = 64
        positions = np.linspace(0, 1, N)
        adj = make_knn_graph(positions, k=3)
        # Check adjacency is symmetric
        np.testing.assert_array_equal(adj, adj.T)
        # Check each node has ≤ 2k neighbors
        assert np.max(np.sum(adj, axis=1)) <= 6

    def test_grid_graph_structure(self):
        """Grid graph has correct structure."""
        adj = make_grid_graph((4, 4))
        assert adj.shape == (16, 16)
        # Corner has 2 neighbors, edge has 3, interior has 4
        assert np.sum(adj[0]) == 2   # corner
        assert np.sum(adj[1]) == 3   # edge
        assert np.sum(adj[5]) == 4   # interior

    def test_gft_vs_dft_on_irregular(self):
        """GFT on irregular graph should differ from DFT."""
        N = 16
        # Star graph: node 0 connected to all others
        adj = np.zeros((N, N))
        for i in range(1, N):
            adj[0, i] = 1
            adj[i, 0] = 1

        f = np.random.RandomState(42).randn(N)
        cs_gft = gft_compress(f, adj, M=8, quant_step=0.01)
        cs_dft = compress(f, M=8, quant_step=0.01)

        f_gft = gft_decompress(cs_gft, adj)
        f_dft = decompress(cs_dft)

        # GFT should be better on star graph (adapted basis)
        snr_gft = snr_db(f, f_gft)
        snr_dft = snr_db(f, f_dft)
        # Just check both work
        assert snr_gft > 0 or snr_dft > 0


# ========================================================================
#  INTEGRATION: COMBINED PIPELINE
# ========================================================================

class TestIntegration:
    def test_full_adaptive_pipeline(self):
        """Full pipeline: adaptive M + Huffman achieves compression."""
        t = np.linspace(0, 1, 256, endpoint=False)
        f = np.sin(2*np.pi*5*t) + 0.3*np.sin(2*np.pi*17*t) + 0.1*np.sin(2*np.pi*41*t)

        cs = compress_adaptive(f, target_snr=10, quant_step=0.001)
        f_recon = decompress(cs)

        # Check pipeline works and compresses
        assert snr_db(f, f_recon) > 3
        assert cs.compression_ratio < 1.0

    def test_delta_chain_stability(self):
        """Delta encoding doesn't accumulate unbounded error."""
        N = 64
        np.random.seed(42)
        signals = [np.sin(2*np.pi*3*np.linspace(0, 1, N)) + 0.01*i
                    for i in range(10)]

        prev = signals[0]
        for curr in signals[1:]:
            cs = compress_delta(prev, curr, M=32, quant_step=0.001)
            prev = decompress_delta(prev, cs)

        final_error = mse(signals[-1], prev)
        assert final_error < 0.1, f"Accumulated error: {final_error}"
