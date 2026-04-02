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
    rng = np.random.RandomState(42)
    signals = {
        # === BASIC ===
        'constant': np.ones(N) * 3.0,
        'ramp': np.linspace(0, 10, N),
        'sine': np.sin(2 * np.pi * 5 * t),
        'multi_sine': np.sin(2*np.pi*3*t) + 0.5*np.sin(2*np.pi*17*t) + 0.3*np.sin(2*np.pi*41*t),
        'noise': rng.randn(N),
        'chirp': np.sin(2 * np.pi * (1 + 20*t) * t),

        # === STRUCTURED: periodic + trend + noise (IoT-like) ===
        'iot_temp': (                                        # temperature sensor
            20.0                                             # base temperature
            + 5.0 * np.sin(2 * np.pi * t)                   # daily cycle
            + 0.3 * np.sin(2 * np.pi * 7 * t)               # weekly harmonic
            + 2.0 * t                                        # warming trend
            + 0.1 * rng.randn(N)                             # sensor noise
        ),
        'iot_vibration': (                                   # machine vibration
            np.sin(2 * np.pi * 50 * t)                       # 50 Hz main
            + 0.3 * np.sin(2 * np.pi * 100 * t)              # 2nd harmonic
            + 0.1 * np.sin(2 * np.pi * 150 * t)              # 3rd harmonic
            + 0.5 * t                                         # drift
            + 0.05 * rng.randn(N)                             # noise
        ),
        'iot_pressure': (                                    # pressure with spikes
            101.3 + 0.5 * np.sin(2 * np.pi * 3 * t)          # slow oscillation
            + 0.02 * rng.randn(N)                             # noise
            + 2.0 * (np.abs(t - 0.3) < 0.02).astype(float)   # spike at t=0.3
            + 1.5 * (np.abs(t - 0.7) < 0.02).astype(float)   # spike at t=0.7
        ),

        # === MULTI-SCALE: wavelet-like ===
        'wavelet_haar': np.concatenate([                     # Haar-like blocks
            np.ones(N//8) * v for v in [1, -1, 0.5, -0.5, 0.25, -0.25, 0.125, -0.125]
        ]),
        'wavelet_bump': sum(                                 # multi-scale bumps
            (0.5**k) * np.exp(-((t - 0.1*(2*k+1))*N/(2**k))**2)
            for k in range(5)
        ),
        'wavelet_chirplet': (                                # chirplet: localized chirp
            np.exp(-50*(t - 0.5)**2)                          # Gaussian envelope
            * np.sin(2 * np.pi * 30 * t)                      # carrier
        ),

        # === STEP FUNCTIONS: piecewise constant (edge test) ===
        'step': np.concatenate([np.zeros(N//2), np.ones(N//2)]),
        'step_multi': np.array([                             # 4-level staircase
            [0.0]*i + [float(k)] * (N//4 - i if k < 3 else N - 3*(N//4))
            for k, i in enumerate([0, 0, 0, 0])
        ]).sum(axis=0)[:N] if N >= 4 else np.zeros(N),
        'step_random': np.repeat(                            # random piecewise constant
            rng.randn(max(1, N // 16)),                       # 16-sample blocks
            min(16, N)
        )[:N],
        'step_sawtooth': (t * 8 % 1.0),                      # sawtooth with 8 teeth
        'step_square': np.sign(np.sin(2 * np.pi * 6 * t)),   # square wave, 6 periods
    }

    # Fix step_multi properly
    quarter = N // 4
    signals['step_multi'] = np.concatenate([
        np.zeros(quarter), np.ones(quarter) * 1.0,
        np.ones(quarter) * 2.5, np.ones(N - 3*quarter) * 4.0
    ])

    return signals


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


class TestStructuredSignals:
    """Tests for IoT-like structured signals (periodic + trend + noise)."""

    def test_iot_temp_compresses_well(self):
        """Temperature signal (smooth + periodic) should compress well."""
        signals = make_signals(256)
        f = signals['iot_temp']
        cs = compress(f, M=16, quant_step=0.01)
        f_recon = decompress(cs)
        # Smooth periodic signal → high SNR even with few modes
        assert snr_db(f, f_recon) > 15, f"IoT temp SNR too low: {snr_db(f, f_recon):.1f}"

    def test_iot_vibration_harmonics(self):
        """Vibration signal has discrete harmonics → very compressible."""
        signals = make_signals(256)
        f = signals['iot_vibration']
        cs = compress(f, M=8, quant_step=0.01)
        f_recon = decompress(cs)
        # Harmonics are discrete → 8 modes should capture most energy
        assert snr_db(f, f_recon) > 5

    def test_iot_pressure_spike_recovery(self):
        """Pressure with spikes: need enough modes to capture edges."""
        signals = make_signals(256)
        f = signals['iot_pressure']
        # Few modes: lose spikes
        cs_few = compress(f, M=8, quant_step=0.01)
        # Many modes: recover spikes
        cs_many = compress(f, M=64, quant_step=0.01)
        f_few = decompress(cs_few)
        f_many = decompress(cs_many)
        assert snr_db(f, f_many) > snr_db(f, f_few)

    def test_delta_on_iot_timeseries(self):
        """Delta encoding excels for slowly-drifting IoT signals."""
        from tests.compression.tos_compression import compress_delta, decompress_delta
        signals = make_signals(128)
        base = signals['iot_temp']
        # Simulate 5 consecutive readings with small drift
        rng = np.random.RandomState(123)
        readings = [base + 0.01 * i + 0.005 * rng.randn(128) for i in range(5)]
        prev = readings[0]
        for curr in readings[1:]:
            cs = compress_delta(prev, curr, M=8, quant_step=0.001)
            recon = decompress_delta(prev, cs)
            assert mse(curr, recon) < 0.1
            prev = recon


class TestMultiScaleSignals:
    """Tests for wavelet-like multi-scale signals."""

    def test_haar_blocks_need_many_modes(self):
        """Haar-like blocks have sharp edges → need more Fourier modes."""
        signals = make_signals(256)
        f = signals['wavelet_haar']
        cs_few = compress(f, M=8, quant_step=0.01)
        cs_many = compress(f, M=64, quant_step=0.01)
        # More modes much better for blocky signals
        snr_few = snr_db(f, decompress(cs_few))
        snr_many = snr_db(f, decompress(cs_many))
        assert snr_many > snr_few + 5

    def test_bump_localized(self):
        """Multi-scale bumps: localized in time → need many Fourier modes."""
        signals = make_signals(256)
        f = signals['wavelet_bump']
        # Localized signals need more modes for good reconstruction
        cs_few = compress(f, M=16, quant_step=0.001)
        cs_many = compress(f, M=128, quant_step=0.001)
        snr_few = snr_db(f, decompress(cs_few))
        snr_many = snr_db(f, decompress(cs_many))
        # More modes helps significantly for localized signals
        assert snr_many > snr_few + 3

    def test_chirplet_time_frequency(self):
        """Chirplet: localized in both time and frequency."""
        signals = make_signals(256)
        f = signals['wavelet_chirplet']
        cs = compress(f, M=32, quant_step=0.001)
        f_recon = decompress(cs)
        assert snr_db(f, f_recon) > 10


class TestStepSignals:
    """Tests for piecewise constant signals (edge compression)."""

    def test_step_gibbs_phenomenon(self):
        """Single step: Fourier modes cause Gibbs oscillation at edge."""
        signals = make_signals(256)
        f = signals['step']
        cs = compress(f, M=32, quant_step=0.001)
        f_recon = decompress(cs)
        # Step functions are HARD for Fourier → limited SNR
        assert max_error(f, f_recon) > 0.01  # Gibbs guaranteed

    def test_multi_step_staircase(self):
        """4-level staircase: more edges → harder."""
        signals = make_signals(256)
        f = signals['step_multi']
        cs = compress(f, M=64, quant_step=0.001)
        f_recon = decompress(cs)
        assert snr_db(f, f_recon) > 5

    def test_square_wave(self):
        """Square wave: odd harmonics only → predictable DFT."""
        signals = make_signals(256)
        f = signals['step_square']
        cs = compress(f, M=32, quant_step=0.001)
        f_recon = decompress(cs)
        assert snr_db(f, f_recon) > 5

    def test_sawtooth(self):
        """Sawtooth: all harmonics → harder than square wave."""
        signals = make_signals(256)
        f = signals['step_sawtooth']
        cs = compress(f, M=32, quant_step=0.001)
        f_recon = decompress(cs)
        assert snr_db(f, f_recon) > 5

    def test_random_piecewise(self):
        """Random piecewise constant: 16-sample blocks."""
        signals = make_signals(256)
        f = signals['step_random']
        cs = compress(f, M=32, quant_step=0.01)
        f_recon = decompress(cs)
        assert np.all(np.isfinite(f_recon))

    def test_step_vs_smooth_compression(self):
        """Step signals compress worse than smooth (Fourier disadvantage)."""
        signals = make_signals(256)
        f_smooth = signals['sine']
        f_step = signals['step']
        M = 16
        cs_smooth = compress(f_smooth, M=M, quant_step=0.001)
        cs_step = compress(f_step, M=M, quant_step=0.001)
        snr_smooth = snr_db(f_smooth, decompress(cs_smooth))
        snr_step = snr_db(f_step, decompress(cs_step))
        # Smooth signals compress MUCH better with Fourier
        assert snr_smooth > snr_step


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
