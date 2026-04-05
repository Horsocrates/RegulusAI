#!/usr/bin/env python3
"""
Born-Optimal Compression Benchmark

Born rule = Parseval: allocate bits proportional to |f_hat_k|^2.
Test where this ACTUALLY helps vs uniform quantization.

Key insight: Born-optimal helps when coefficient dynamic range is LARGE.
Uniform wastes bits on small coefficients. Born gives more bits to important ones.

Run: uv run python -m tests.compression.born_benchmark
"""

import numpy as np
import json
from pathlib import Path
from tests.compression.tos_compression import compress, decompress, mse, snr_db


# ========================================================================
#  BORN-OPTIMAL COMPRESSOR (improved)
# ========================================================================

def compress_born(signal, M, total_bits_per_coeff=8):
    """Born-optimal: allocate bits proportional to spectral energy."""
    N = len(signal)
    coeffs = np.fft.fft(signal)
    energies = np.abs(coeffs) ** 2
    total_energy = np.sum(energies)

    # Select top M modes
    top_idx = np.argsort(energies)[::-1][:M]
    kept_e = energies[top_idx]
    kept_total = np.sum(kept_e)

    if kept_total < 1e-30:
        return np.real(np.fft.ifft(np.zeros(N))), {}

    # Born probabilities for kept modes
    born_probs = kept_e / kept_total

    # Bit allocation: bits_k = total_bits * p_k (proportional to energy)
    total_bits = M * total_bits_per_coeff
    bits_alloc = np.round(born_probs * total_bits).astype(int)
    bits_alloc = np.maximum(bits_alloc, 1)  # at least 1 bit per mode

    # Quantize each mode with its allocated bits
    q_coeffs = np.zeros(N, dtype=complex)
    actual_bits = 0
    for i, idx in enumerate(top_idx):
        b = int(bits_alloc[i])
        actual_bits += 2 * b  # re + im
        levels = max(2, 2 ** b)
        c = coeffs[idx]
        scale = np.abs(c) * 1.01 + 1e-15
        q_re = np.round(c.real / scale * levels / 2) * scale / (levels / 2)
        q_im = np.round(c.imag / scale * levels / 2) * scale / (levels / 2)
        q_coeffs[idx] = q_re + 1j * q_im

    recon = np.real(np.fft.ifft(q_coeffs))
    return recon, {
        'bits_alloc': bits_alloc.tolist(),
        'born_probs': born_probs.tolist(),
        'actual_bits': actual_bits,
        'dynamic_range_db': float(10 * np.log10(max(kept_e) / max(min(kept_e), 1e-30))),
    }


def compress_uniform(signal, M, bits_per_coeff=8):
    """Uniform: same bits for every coefficient."""
    N = len(signal)
    coeffs = np.fft.fft(signal)
    energies = np.abs(coeffs) ** 2
    top_idx = np.argsort(energies)[::-1][:M]

    q_coeffs = np.zeros(N, dtype=complex)
    levels = max(2, 2 ** bits_per_coeff)
    for idx in top_idx:
        c = coeffs[idx]
        scale = np.abs(c) * 1.01 + 1e-15
        q_re = np.round(c.real / scale * levels / 2) * scale / (levels / 2)
        q_im = np.round(c.imag / scale * levels / 2) * scale / (levels / 2)
        q_coeffs[idx] = q_re + 1j * q_im

    recon = np.real(np.fft.ifft(q_coeffs))
    return recon


# ========================================================================
#  TEST SIGNALS (designed to show dynamic range effects)
# ========================================================================

def make_test_signals(N=256):
    t = np.linspace(0, 1, N, endpoint=False)
    rng = np.random.RandomState(42)
    return {
        # LOW dynamic range (uniform good)
        'single_sine': np.sin(2 * np.pi * 5 * t),
        'white_noise': rng.randn(N),

        # MEDIUM dynamic range
        'two_sines': np.sin(2*np.pi*5*t) + 0.1*np.sin(2*np.pi*50*t),
        'chirp': np.sin(2*np.pi*(5 + 40*t)*t),

        # HIGH dynamic range (Born should help)
        'spike': np.zeros(N),  # will add spike below
        'dominant_fundamental': np.sin(2*np.pi*3*t) + 0.01*np.sin(2*np.pi*17*t) + 0.001*np.sin(2*np.pi*41*t),
        'speech_like': np.zeros(N),  # will build below
        'exponential_decay': np.zeros(N),  # will build below

        # EXTREME dynamic range
        'one_mode_dominant': np.zeros(N),  # will build below
        'power_law_spectrum': np.zeros(N),  # will build below
    }


def build_signals(N=256):
    signals = make_test_signals(N)
    t = np.linspace(0, 1, N, endpoint=False)
    rng = np.random.RandomState(42)

    # Spike
    signals['spike'][N//2] = 10.0
    signals['spike'] += 0.01 * rng.randn(N)

    # Speech-like (formants with very different amplitudes)
    for f, a in [(130, 1.0), (260, 0.5), (390, 0.3), (800, 0.05), (1200, 0.02), (2500, 0.005)]:
        signals['speech_like'] += a * np.sin(2 * np.pi * f / 256 * np.arange(N))

    # Exponential decay spectrum
    for k in range(1, 30):
        signals['exponential_decay'] += np.exp(-0.3 * k) * np.sin(2 * np.pi * k * t)

    # One dominant mode (99% energy in mode 5)
    signals['one_mode_dominant'] = 10 * np.sin(2*np.pi*5*t) + 0.01 * rng.randn(N)

    # Power-law spectrum: A_k ~ 1/k
    for k in range(1, 50):
        signals['power_law_spectrum'] += (1.0/k) * np.sin(2*np.pi*k*t + rng.rand()*6.28)

    return signals


# ========================================================================
#  BENCHMARK
# ========================================================================

def benchmark_signal(signal, name, M, bits_per_coeff=8):
    """Compare Born vs Uniform on one signal."""
    N = len(signal)

    # Uniform
    recon_u = compress_uniform(signal, M, bits_per_coeff)
    mse_u = mse(signal, recon_u)
    snr_u = snr_db(signal, recon_u)

    # Born
    recon_b, info = compress_born(signal, M, bits_per_coeff)
    mse_b = mse(signal, recon_b)
    snr_b = snr_db(signal, recon_b)

    improvement = (mse_u - mse_b) / max(mse_u, 1e-30) * 100
    dr = info.get('dynamic_range_db', 0)

    return {
        'name': name, 'N': N, 'M': M, 'bits': bits_per_coeff,
        'mse_uniform': float(mse_u), 'snr_uniform': float(snr_u),
        'mse_born': float(mse_b), 'snr_born': float(snr_b),
        'improvement_pct': float(improvement),
        'dynamic_range_db': float(dr),
    }


# ========================================================================
#  MAIN
# ========================================================================

def main():
    print("=" * 85)
    print("  BORN-OPTIMAL COMPRESSION BENCHMARK")
    print("  Allocate bits proportional to |f_hat_k|^2 (Born/Parseval)")
    print("=" * 85)

    signals = build_signals(256)

    # === MAIN TABLE ===
    print(f"\n  {'Signal':<22} {'DR(dB)':>7} {'M':>4} {'Unif SNR':>9} "
          f"{'Born SNR':>9} {'Improve':>8}")
    print(f"  {'-'*22} {'-'*7} {'-'*4} {'-'*9} {'-'*9} {'-'*8}")

    all_results = []
    for name in ['single_sine', 'white_noise', 'two_sines', 'chirp',
                   'spike', 'dominant_fundamental', 'speech_like',
                   'exponential_decay', 'one_mode_dominant', 'power_law_spectrum']:
        sig = signals[name]
        for M in [16, 32]:
            r = benchmark_signal(sig, name, M, bits_per_coeff=8)
            all_results.append(r)
            snr_u = f"{r['snr_uniform']:.1f}" if r['snr_uniform'] < 200 else "inf"
            snr_b = f"{r['snr_born']:.1f}" if r['snr_born'] < 200 else "inf"
            print(f"  {name:<22} {r['dynamic_range_db']:>7.1f} {M:>4} "
                  f"{snr_u:>9} {snr_b:>9} {r['improvement_pct']:>+7.1f}%")

    # === BIT BUDGET SWEEP ===
    print(f"\n{'=' * 85}")
    print(f"  BIT BUDGET SWEEP (power_law_spectrum, M=32)")
    print(f"{'=' * 85}")
    print(f"\n  {'Bits/coeff':>11} {'Unif SNR':>9} {'Born SNR':>9} {'Improve':>8}")
    print(f"  {'-'*11} {'-'*9} {'-'*9} {'-'*8}")

    sig = signals['power_law_spectrum']
    for bits in [2, 4, 6, 8, 10, 12, 16]:
        r = benchmark_signal(sig, 'power_law', 32, bits)
        snr_u = f"{r['snr_uniform']:.1f}" if r['snr_uniform'] < 200 else "inf"
        snr_b = f"{r['snr_born']:.1f}" if r['snr_born'] < 200 else "inf"
        print(f"  {bits:>11} {snr_u:>9} {snr_b:>9} {r['improvement_pct']:>+7.1f}%")

    # === DYNAMIC RANGE CORRELATION ===
    print(f"\n{'=' * 85}")
    print(f"  CORRELATION: Dynamic Range vs Born Improvement")
    print(f"{'=' * 85}")

    m32 = [r for r in all_results if r['M'] == 32]
    m32.sort(key=lambda x: x['dynamic_range_db'])
    print(f"\n  {'Signal':<22} {'DR(dB)':>7} {'Improvement':>11}")
    print(f"  {'-'*22} {'-'*7} {'-'*11}")
    for r in m32:
        print(f"  {r['name']:<22} {r['dynamic_range_db']:>7.1f} {r['improvement_pct']:>+10.1f}%")

    # Correlation
    drs = [r['dynamic_range_db'] for r in m32]
    imps = [r['improvement_pct'] for r in m32]
    if len(drs) > 2 and np.std(drs) > 0:
        corr = np.corrcoef(drs, imps)[0, 1]
        print(f"\n  Pearson correlation (DR vs improvement): {corr:.3f}")
        if corr > 0.3:
            print(f"  -> POSITIVE: higher dynamic range -> Born helps more")
        elif corr < -0.3:
            print(f"  -> NEGATIVE: unexpected inverse relationship")
        else:
            print(f"  -> WEAK: dynamic range alone doesn't predict Born advantage")

    # === VERDICT ===
    print(f"\n{'=' * 85}")
    print(f"  VERDICT")
    print(f"{'=' * 85}")

    born_wins = [r for r in m32 if r['improvement_pct'] > 1.0]
    born_loses = [r for r in m32 if r['improvement_pct'] < -1.0]
    neutral = [r for r in m32 if abs(r['improvement_pct']) <= 1.0]

    print(f"\n  Born wins (>1%): {len(born_wins)}/{len(m32)} signals")
    for r in born_wins:
        print(f"    {r['name']:<22} {r['improvement_pct']:>+.1f}% (DR={r['dynamic_range_db']:.0f}dB)")

    print(f"\n  Neutral (<1%): {len(neutral)}/{len(m32)} signals")
    print(f"\n  Born loses (<-1%): {len(born_loses)}/{len(m32)} signals")
    for r in born_loses:
        print(f"    {r['name']:<22} {r['improvement_pct']:>+.1f}%")

    # Save
    path = Path(__file__).parent / 'results' / 'born_benchmark.json'
    path.parent.mkdir(exist_ok=True)
    with open(path, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  Results saved to {path}")


if __name__ == '__main__':
    main()
