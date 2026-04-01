#!/usr/bin/env python3
"""
Compression Pipeline Benchmark — Performance Testing

Tests the ToS verified compression pipeline on real signals.
Measures: compression ratio, SNR, MSE, speed.
Compares with: numpy FFT, zlib.

Run:
  uv run pytest tests/compression/test_compression_benchmark.py -v
  uv run python tests/compression/test_compression_benchmark.py  # full sweep
"""

import numpy as np
import json
import time
import zlib
import struct
import pytest
from pathlib import Path
from dataclasses import dataclass, asdict

from tests.compression.tos_compression import (
    compress, decompress, mse, snr_db, max_error,
    parseval_check, kraft_sum, dft_graph, idft_graph,
    cycle_eigenvalues, quantize, dequantize
)


# ========================================================================
#  TEST SIGNALS
# ========================================================================

def make_signals(N: int = 256) -> dict[str, np.ndarray]:
    """Generate test signals of length N."""
    t = np.linspace(0, 1, N, endpoint=False)
    return {
        'constant': np.ones(N) * 3.0,
        'ramp': np.linspace(0, 10, N),
        'sine': np.sin(2 * np.pi * 5 * t),
        'multi_sine': np.sin(2*np.pi*3*t) + 0.5*np.sin(2*np.pi*17*t) + 0.3*np.sin(2*np.pi*41*t),
        'step': np.concatenate([np.zeros(N//2), np.ones(N//2)]),
        'noise': np.random.RandomState(42).randn(N),
        'chirp': np.sin(2 * np.pi * (1 + 20*t) * t),
    }


# ========================================================================
#  PYTEST: CORRECTNESS TESTS
# ========================================================================

class TestPipelineCorrectness:
    """Verify pipeline behaves correctly."""

    def test_lossless_roundtrip(self):
        """Full modes + fine step → near-lossless."""
        f = np.array([1.0, 2.0, 3.0, 4.0])
        cs = compress(f, M=4, quant_step=0.001, use_huffman=False)
        f_recon = decompress(cs)
        assert mse(f, f_recon) < 0.01, f"MSE too high: {mse(f, f_recon)}"

    def test_lossy_reduces_size(self):
        """Truncating modes reduces compressed size."""
        f = np.random.RandomState(42).randn(64)
        cs_full = compress(f, M=64, quant_step=0.01, use_huffman=False)
        cs_half = compress(f, M=32, quant_step=0.01, use_huffman=False)
        assert cs_half.compression_ratio < cs_full.compression_ratio

    def test_quantization_error_bounded(self):
        """Quantization error ≤ step/2."""
        values = np.array([1.3, 2.7, -0.4, 5.5])
        step = 0.5
        indices = quantize(values, step)
        recon = dequantize(indices, step)
        errors = np.abs(values - recon)
        assert np.all(errors <= step / 2 + 1e-10)

    def test_parseval_energy_conservation(self):
        """DFT preserves energy (Parseval theorem)."""
        for name, f in make_signals(64).items():
            t_energy, f_energy = parseval_check(f)
            assert abs(t_energy - f_energy) < 1e-8 * t_energy, \
                f"Parseval failed for {name}: {t_energy} vs {f_energy}"

    def test_kraft_inequality(self):
        """Huffman codes satisfy Kraft inequality."""
        f = np.random.RandomState(42).randn(128)
        cs = compress(f, M=64, quant_step=0.1, use_huffman=True)
        if cs.codebook:
            ks = kraft_sum(cs.codebook)
            assert ks <= 1.0 + 1e-10, f"Kraft violated: {ks}"

    def test_eigenvalues_sum_zero(self):
        """Cycle graph eigenvalues sum to zero (trace of adjacency = 0)."""
        for N in [4, 8, 16, 64]:
            ev = cycle_eigenvalues(N)
            assert abs(np.sum(ev)) < 1e-10, f"N={N}: eigenvalue sum = {np.sum(ev)}"

    def test_snr_improves_with_modes(self):
        """More modes → higher SNR."""
        f = make_signals(64)['multi_sine']
        snr_values = []
        for M in [8, 16, 32, 64]:
            cs = compress(f, M=M, quant_step=0.001)
            f_recon = decompress(cs)
            snr_values.append(snr_db(f, f_recon))
        # SNR should be monotonically increasing
        for i in range(len(snr_values) - 1):
            assert snr_values[i] <= snr_values[i+1] + 0.1  # small tolerance


# ========================================================================
#  BENCHMARK SWEEP
# ========================================================================

@dataclass
class BenchmarkResult:
    signal_name: str
    N: int
    M: int
    quant_step: float
    compression_ratio: float
    snr_db: float
    mse: float
    max_error: float
    encode_ms: float
    decode_ms: float
    huffman_bits: int
    kraft_sum: float


def run_single_benchmark(f: np.ndarray, signal_name: str,
                          M: int, quant_step: float) -> BenchmarkResult:
    """Run pipeline and measure metrics."""
    N = len(f)

    t0 = time.perf_counter()
    cs = compress(f, M=M, quant_step=quant_step, use_huffman=True)
    encode_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    f_recon = decompress(cs)
    decode_ms = (time.perf_counter() - t0) * 1000

    ks = kraft_sum(cs.codebook) if cs.codebook else 0.0

    return BenchmarkResult(
        signal_name=signal_name, N=N, M=M, quant_step=quant_step,
        compression_ratio=cs.compression_ratio,
        snr_db=snr_db(f, f_recon), mse=mse(f, f_recon),
        max_error=max_error(f, f_recon),
        encode_ms=encode_ms, decode_ms=decode_ms,
        huffman_bits=cs.compressed_bits, kraft_sum=ks
    )


def run_full_benchmark():
    """Full benchmark sweep across signals, sizes, compression levels."""
    results = []

    for N in [16, 64, 256]:
        signals = make_signals(N)
        for sig_name, f in signals.items():
            for ratio in [0.1, 0.25, 0.5, 0.75, 1.0]:
                M = max(1, int(N * ratio))
                for step in [0.01, 0.1, 1.0]:
                    r = run_single_benchmark(f, sig_name, M, step)
                    results.append(r)

    return results


def compare_with_baselines(f: np.ndarray, M: int, step: float):
    """Compare ToS pipeline with numpy FFT and zlib."""
    N = len(f)

    # ToS pipeline
    t0 = time.perf_counter()
    cs = compress(f, M=M, quant_step=step, use_huffman=True)
    f_tos = decompress(cs)
    tos_time = (time.perf_counter() - t0) * 1000

    # numpy FFT (same algorithm, float64)
    t0 = time.perf_counter()
    fhat_np = np.fft.fft(f)
    indices_np = np.argsort(np.abs(fhat_np))[::-1][:M]
    fhat_trunc = np.zeros_like(fhat_np)
    fhat_trunc[indices_np] = fhat_np[indices_np]
    f_np = np.real(np.fft.ifft(fhat_trunc))
    np_time = (time.perf_counter() - t0) * 1000

    # zlib (lossless, general purpose)
    raw = f.tobytes()
    t0 = time.perf_counter()
    compressed = zlib.compress(raw)
    zlib_time = (time.perf_counter() - t0) * 1000
    f_zlib = np.frombuffer(zlib.decompress(compressed), dtype=f.dtype)

    return {
        'tos': {'snr': snr_db(f, f_tos), 'ratio': cs.compression_ratio,
                'time_ms': tos_time, 'mse': mse(f, f_tos)},
        'numpy_fft': {'snr': snr_db(f, f_np), 'ratio': M / N,
                      'time_ms': np_time, 'mse': mse(f, f_np)},
        'zlib': {'snr': float('inf'), 'ratio': len(compressed) / len(raw),
                 'time_ms': zlib_time, 'mse': 0.0},
    }


# ========================================================================
#  MAIN: RUN AND REPORT
# ========================================================================

def print_summary(results: list[BenchmarkResult]):
    """Print formatted results table."""
    print(f"\n{'Signal':<12} {'N':>5} {'M':>5} {'Step':>6} {'Ratio':>7} "
          f"{'SNR(dB)':>8} {'MSE':>10} {'MaxErr':>8} {'Enc(ms)':>8} {'Kraft':>6}")
    print("-" * 95)
    for r in results:
        snr_str = f"{r.snr_db:.1f}" if r.snr_db < 200 else "inf"
        print(f"{r.signal_name:<12} {r.N:>5} {r.M:>5} {r.quant_step:>6.2f} "
              f"{r.compression_ratio:>7.4f} {snr_str:>8} {r.mse:>10.6f} "
              f"{r.max_error:>8.4f} {r.encode_ms:>8.2f} {r.kraft_sum:>6.3f}")


def print_comparison(comp: dict, label: str):
    """Print comparison table."""
    print(f"\n=== {label} ===")
    print(f"{'Method':<12} {'SNR(dB)':>8} {'Ratio':>8} {'MSE':>12} {'Time(ms)':>10}")
    print("-" * 55)
    for method, metrics in comp.items():
        snr_str = f"{metrics['snr']:.1f}" if metrics['snr'] < 200 else "inf"
        print(f"{method:<12} {snr_str:>8} {metrics['ratio']:>8.4f} "
              f"{metrics['mse']:>12.8f} {metrics['time_ms']:>10.2f}")


if __name__ == '__main__':
    print("=" * 80)
    print("ToS Verified Compression Pipeline — Benchmark")
    print("=" * 80)

    # Quick benchmark on key signals
    key_results = []
    for N in [64, 256]:
        signals = make_signals(N)
        for sig_name in ['sine', 'multi_sine', 'noise', 'chirp']:
            for ratio in [0.25, 0.5]:
                M = max(1, int(N * ratio))
                r = run_single_benchmark(signals[sig_name], sig_name, M, 0.01)
                key_results.append(r)

    print_summary(key_results)

    # Comparison with baselines
    for N in [64, 256]:
        signals = make_signals(N)
        for sig_name in ['sine', 'multi_sine', 'noise']:
            f = signals[sig_name]
            M = N // 4
            comp = compare_with_baselines(f, M, 0.01)
            print_comparison(comp, f"{sig_name} N={N} M={M}")

    # Save results
    output_path = Path(__file__).parent / 'benchmark_results.json'
    with open(output_path, 'w') as fp:
        json.dump([asdict(r) for r in key_results], fp, indent=2)
    print(f"\nResults saved to {output_path}")
