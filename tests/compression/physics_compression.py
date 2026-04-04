#!/usr/bin/env python3
"""
Physics-Derived Compression: Born-Optimal + Wave-Predictive

Two algorithms derived from Crown Jewel (Born = Parseval):
1. compress_born: allocate bits proportional to |f_hat_k|^2
2. compress_wave: predict next frame using transfer matrix T

Run: uv run python -m tests.compression.physics_compression
"""

import numpy as np
import json
import time
from pathlib import Path

from tests.compression.tos_compression import (
    compress, decompress, mse, snr_db,
)


# ========================================================================
#  ALGORITHM 1: BORN-OPTIMAL COMPRESSION
# ========================================================================

def compress_born(signal, M=None, total_bits=None, target_fidelity=0.95):
    """Born-optimal: allocate bits proportional to |f_hat_k|^2."""
    N = len(signal)
    coeffs = np.fft.fft(signal)
    energies = np.abs(coeffs) ** 2
    total_energy = np.sum(energies)
    if total_energy < 1e-15:
        return signal.copy(), {'method': 'born_trivial', 'mse': 0}

    born_probs = energies / total_energy

    # Auto M from fidelity
    if M is None:
        sorted_idx = np.argsort(energies)[::-1]
        cum = 0
        M = 0
        for idx in sorted_idx:
            cum += born_probs[idx]
            M += 1
            if cum >= target_fidelity:
                break

    sorted_idx = np.argsort(energies)[::-1]
    kept = sorted_idx[:M]

    if total_bits is None:
        total_bits = M * 8

    # Water-filling bit allocation
    kept_e = energies[kept]
    D_lo, D_hi = 1e-20, np.max(kept_e) + 1
    for _ in range(60):
        D_mid = (D_lo + D_hi) / 2
        bits = np.maximum(0, 0.5 * np.log2(np.maximum(kept_e / D_mid, 1e-30)))
        if np.sum(bits) > total_bits:
            D_lo = D_mid
        else:
            D_hi = D_mid
    bits_alloc = np.maximum(0, 0.5 * np.log2(np.maximum(kept_e / ((D_lo+D_hi)/2), 1e-30)))
    bits_alloc = np.round(bits_alloc).astype(int)
    bits_alloc = np.maximum(bits_alloc, 1)

    # Quantize each mode with allocated bits
    q_coeffs = np.zeros(N, dtype=complex)
    for i, idx in enumerate(kept):
        b = bits_alloc[i] if i < len(bits_alloc) else 1
        levels = 2 ** b
        c = coeffs[idx]
        c_max = np.abs(c) * 1.05 + 1e-10
        q_re = np.round(c.real / c_max * levels/2) * c_max / (levels/2)
        q_im = np.round(c.imag / c_max * levels/2) * c_max / (levels/2)
        q_coeffs[idx] = q_re + 1j * q_im

    recon = np.real(np.fft.ifft(q_coeffs))
    err = float(np.mean((signal - recon) ** 2))
    fidelity = float(np.sum(energies[kept]) / total_energy)

    return recon, {
        'method': 'born_optimal', 'M': M,
        'total_bits': int(np.sum(bits_alloc)),
        'born_fidelity': fidelity, 'mse': err,
        'snr_db': float(snr_db(signal, recon)),
    }


# ========================================================================
#  ALGORITHM 2: WAVE-PREDICTIVE COMPRESSION
# ========================================================================

def build_chain_laplacian(N):
    L = np.zeros((N, N))
    for i in range(N):
        L[i, i] = 2
        if i > 0: L[i, i-1] = -1
        if i < N-1: L[i, i+1] = -1
    L[0, 0] = 1
    L[N-1, N-1] = 1
    return L


def compress_wave_sequence(frames, c_sq=0.25, M=None, quant_step=0.01,
                            method='wave'):
    """Wave-predictive compression for frame sequences."""
    n_frames = len(frames)
    N = len(frames[0])
    if M is None:
        M = max(2, N // 4)

    if method == 'wave':
        L = build_chain_laplacian(N)
        T = 2 * np.eye(N) - c_sq * L

    total_raw_e = 0
    total_res_e = 0
    total_mse = 0
    total_bits = 0
    prev = np.zeros(N)
    pprev = np.zeros(N)

    for t in range(n_frames):
        frame = np.array(frames[t], dtype=float)
        total_raw_e += np.sum(frame ** 2)

        # Predict
        if method == 'wave' and t >= 1:
            predicted = T @ prev - pprev if t >= 2 else T @ prev
        elif method == 'delta' and t >= 1:
            predicted = prev.copy()
        else:
            predicted = np.zeros(N)

        residual = frame - predicted
        total_res_e += np.sum(residual ** 2)

        # Compress residual
        cs = compress(residual, M=M, quant_step=quant_step)
        total_bits += cs.compressed_bits
        recon_res = decompress(cs)
        recon_frame = predicted + recon_res
        total_mse += mse(frame, recon_frame)

        pprev = prev.copy()
        prev = recon_frame.copy()

    avg_mse = total_mse / n_frames
    pred_gain = 10 * np.log10(max(total_raw_e, 1e-15) / max(total_res_e, 1e-15))
    ratio = total_bits / (n_frames * N * 64)
    res_frac = total_res_e / max(total_raw_e, 1e-15)

    return {
        'method': method, 'n_frames': n_frames, 'N': N, 'M': M,
        'avg_mse': float(avg_mse),
        'snr_db': float(10 * np.log10(np.mean([np.var(f) for f in frames]) / max(avg_mse, 1e-15))) if avg_mse > 1e-15 else float('inf'),
        'prediction_gain_db': float(pred_gain),
        'compression_ratio': float(ratio),
        'residual_fraction': float(res_frac),
    }


# ========================================================================
#  TEST SIGNALS
# ========================================================================

def gen_wave(N=64, n_frames=50, c_sq=0.25):
    x = np.linspace(0, 1, N)
    f0 = np.exp(-((x - 0.5) / 0.1) ** 2)
    L = build_chain_laplacian(N)
    T = 2 * np.eye(N) - c_sq * L
    frames = [f0]
    prev, curr = np.zeros(N), f0
    for _ in range(n_frames - 1):
        nxt = T @ curr - prev
        frames.append(nxt)
        prev, curr = curr, nxt
    return frames

def gen_diffusion(N=64, n_frames=50, kappa=0.1):
    x = np.linspace(0, 1, N)
    f0 = 20 + 5 * np.sin(2*np.pi*x) + 2 * np.cos(4*np.pi*x)
    L = build_chain_laplacian(N)
    T = np.eye(N) - kappa * L
    frames = [f0]
    curr = f0
    for _ in range(n_frames - 1):
        curr = T @ curr
        frames.append(curr)
    return frames

def gen_oscillation(N=64, n_frames=50):
    t = np.linspace(0, 2*np.pi, N)
    rng = np.random.RandomState(42)
    frames = []
    for i in range(n_frames):
        decay = np.exp(-0.05 * i)
        frame = decay * np.sin(3*t + 0.1*i) + 0.5*decay*np.sin(7*t + 0.2*i)
        frame += 0.02 * rng.randn(N)
        frames.append(frame)
    return frames

def gen_random_walk(N=64, n_frames=50):
    rng = np.random.RandomState(42)
    frames = [rng.randn(N)]
    for _ in range(n_frames - 1):
        frames.append(frames[-1] + 0.1 * rng.randn(N))
    return frames


# ========================================================================
#  MAIN
# ========================================================================

def main():
    print("=" * 80)
    print("  PHYSICS-DERIVED COMPRESSION BENCHMARK")
    print("  Born-optimal quantization + Wave-predictive coding")
    print("=" * 80)

    # === BORN-OPTIMAL vs UNIFORM ===
    print(f"\n{'=' * 80}")
    print("  PART 1: Born-Optimal vs Uniform Quantization")
    print(f"{'=' * 80}")

    signals = {
        'sine': np.sin(2*np.pi*5*np.linspace(0,1,256)),
        'multi': np.sin(2*np.pi*3*np.linspace(0,1,256)) + 0.3*np.sin(2*np.pi*17*np.linspace(0,1,256)),
        'noise': np.random.RandomState(42).randn(256),
        'impulse': np.zeros(256),
    }
    signals['impulse'][128] = 1.0

    print(f"\n  {'Signal':<12} {'M':>4} {'Unif MSE':>10} {'Born MSE':>10} {'Improve':>8} {'Fidelity':>9}")
    print(f"  {'-'*12} {'-'*4} {'-'*10} {'-'*10} {'-'*8} {'-'*9}")

    for name, sig in signals.items():
        for M in [16, 32, 64]:
            # Uniform
            cs_u = compress(sig, M=M, quant_step=0.01)
            r_u = decompress(cs_u)
            mse_u = mse(sig, r_u)
            # Born
            r_b, info_b = compress_born(sig, M=M, total_bits=M*8)
            mse_b = info_b['mse']
            imp = (mse_u - mse_b) / max(mse_u, 1e-15) * 100
            fid = info_b.get('born_fidelity', 0)
            print(f"  {name:<12} {M:>4} {mse_u:>10.6f} {mse_b:>10.6f} {imp:>+7.1f}% {fid:>9.3f}")

    # === WAVE-PREDICTIVE vs DELTA ===
    print(f"\n{'=' * 80}")
    print("  PART 2: Wave-Predictive vs Delta Encoding")
    print(f"{'=' * 80}")

    test_signals = {
        'wave_propagation': gen_wave(),
        'diffusion_IoT': gen_diffusion(),
        'damped_vibration': gen_oscillation(),
        'random_walk': gen_random_walk(),
    }

    print(f"\n  {'Signal':<22} {'Method':<12} {'MSE':>10} {'PredGain':>10} {'ResFrac':>10}")
    print(f"  {'-'*22} {'-'*12} {'-'*10} {'-'*10} {'-'*10}")

    summary = {}
    for sig_name, frames in test_signals.items():
        N = len(frames[0])
        M = N // 4

        r_raw = compress_wave_sequence(frames, method='raw', M=M)
        r_delta = compress_wave_sequence(frames, method='delta', M=M)
        r_wave = compress_wave_sequence(frames, method='wave', M=M)

        for label, r in [('raw', r_raw), ('delta', r_delta), ('wave', r_wave)]:
            print(f"  {sig_name:<22} {label:<12} {r['avg_mse']:>10.6f} "
                  f"{r['prediction_gain_db']:>10.1f} {r['residual_fraction']*100:>9.1f}%")

        wave_vs_delta = (r_delta['avg_mse'] - r_wave['avg_mse']) / max(r_delta['avg_mse'], 1e-15) * 100
        summary[sig_name] = {
            'delta_mse': r_delta['avg_mse'], 'wave_mse': r_wave['avg_mse'],
            'improvement': wave_vs_delta,
            'wave_pred_gain': r_wave['prediction_gain_db'],
            'delta_pred_gain': r_delta['prediction_gain_db'],
        }
        print(f"  {'':22} {'wave vs delta':>12} {wave_vs_delta:>+9.1f}%")
        print()

    # === VERDICT ===
    print(f"{'=' * 80}")
    print("  VERDICT")
    print(f"{'=' * 80}")

    wave_wins = sum(1 for s in summary.values() if s['wave_mse'] < s['delta_mse'])
    print(f"\n  Wave-predictive wins: {wave_wins}/{len(summary)} signals")

    for sig_name, s in summary.items():
        win = "WAVE WINS" if s['wave_mse'] < s['delta_mse'] else "DELTA WINS"
        print(f"    {sig_name:<22} {win} ({s['improvement']:+.1f}%)")

    print(f"\n  EXPECTED: wave >> delta for physics-governed signals.")
    print(f"  EXPECTED: wave ~ delta for random walk.")

    # Save
    output_dir = Path(__file__).parent / 'results'
    output_dir.mkdir(exist_ok=True)
    path = output_dir / 'physics_compression_results.json'
    with open(path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n  Results saved to {path}")


if __name__ == '__main__':
    main()
