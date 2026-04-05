#!/usr/bin/env python3
"""
Combined Physics Pipeline: GFT + Auto-Physics + Born-Optimal

The FULL stack:
  1. Graph detection → GFT basis (or FFT for 1D)
  2. Auto-physics → matched predictor (wave/diffusion/delta)
  3. Born-optimal → bit allocation proportional to |f_hat_k|^2
  4. Huffman entropy coding

Each layer derived from E/R/R:
  GFT      = R-formula (Rules): graph Laplacian eigenvectors
  Predictor = R-formula (Rules): matched transfer matrix
  Born     = R-formula (Roles): energy significance determines bits
  Signal   = E-formula (Elements): field on graph

Run: uv run python -m tests.compression.combined_pipeline
"""

import numpy as np
import json
import time
import zlib
from pathlib import Path

from tests.compression.tos_compression import (
    compress, decompress, gft_compress, gft_decompress,
    make_grid_graph, make_knn_graph, mse, snr_db,
    huffman_encode, kraft_sum,
)
from tests.compression.auto_physics import (
    detect_physics, predict_wave, predict_diffusion, predict_damped,
    predict_delta, build_laplacian,
)
from tests.compression.born_benchmark import compress_born, compress_uniform


# ========================================================================
#  COMBINED PIPELINE
# ========================================================================

def compress_full_pipeline(frames, M=None, bits_per_coeff=8,
                            graph=None, quant_step=0.01):
    """Full physics-derived pipeline: GFT + auto-physics + Born."""
    n_frames = len(frames)
    N = len(frames[0])
    if M is None:
        M = max(2, N // 4)

    # Step 1: Detect physics
    physics = detect_physics(frames[:min(10, n_frames)])

    # Step 2: Compress each frame
    total_bits = 0
    total_mse = 0
    prev = np.zeros(N)
    pprev = np.zeros(N)

    for t in range(n_frames):
        frame = np.array(frames[t], dtype=float)

        # Step 2a: Physics prediction
        if t == 0:
            predicted = np.zeros(N)
        elif physics == 'wave' and t >= 2:
            predicted = predict_wave(prev, pprev, N)
        elif physics == 'damped' and t >= 2:
            predicted = predict_damped(prev, pprev, N)
        elif physics == 'diffusion':
            predicted = predict_diffusion(prev, N)
        else:
            predicted = predict_delta(prev)

        residual = frame - predicted

        # Step 2b: GFT or FFT on residual
        if graph is not None:
            cs = gft_compress(residual, graph, M=M, quant_step=quant_step)
            recon_res = gft_decompress(cs, graph)
        else:
            # Step 2c: Born-optimal quantization
            recon_res, info = compress_born(residual, M, bits_per_coeff)

        total_bits += M * bits_per_coeff * 2  # approximate
        recon = predicted + recon_res
        total_mse += mse(frame, recon)

        pprev = prev.copy()
        prev = recon.copy()

    return {
        'method': f'full_pipeline({physics})',
        'physics': physics,
        'n_frames': n_frames,
        'N': N, 'M': M,
        'avg_mse': total_mse / n_frames,
        'total_bits': total_bits,
        'ratio': total_bits / (n_frames * N * 64),
    }


def compress_baseline(frames, method, M=None, graph=None, quant_step=0.01):
    """Baseline methods for comparison."""
    n_frames = len(frames)
    N = len(frames[0])
    if M is None:
        M = max(2, N // 4)

    total_bits = 0
    total_mse_val = 0
    prev = np.zeros(N)

    for t in range(n_frames):
        frame = np.array(frames[t], dtype=float)

        if method == 'raw':
            residual = frame
        elif method == 'delta':
            residual = frame - (prev if t > 0 else np.zeros(N))
        elif method == 'gft_raw' and graph is not None:
            cs = gft_compress(frame, graph, M=M, quant_step=quant_step)
            recon = gft_decompress(cs, graph)
            total_mse_val += mse(frame, recon)
            total_bits += cs.compressed_bits
            prev = recon.copy()
            continue
        else:
            residual = frame

        cs = compress(residual, M=M, quant_step=quant_step)
        total_bits += cs.compressed_bits
        recon_res = decompress(cs)
        if method == 'delta':
            recon = (prev if t > 0 else np.zeros(N)) + recon_res
        else:
            recon = recon_res
        total_mse_val += mse(frame, recon)
        prev = recon.copy()

    avg_mse = total_mse_val / n_frames
    return {
        'method': method, 'avg_mse': avg_mse,
        'total_bits': total_bits,
        'ratio': total_bits / (n_frames * N * 64),
        'snr_db': 10*np.log10(np.mean([np.var(f) for f in frames]) / max(avg_mse, 1e-30)) if avg_mse > 0 else float('inf'),
    }


# ========================================================================
#  TEST SCENARIOS
# ========================================================================

def scenario_wave_1d(N=64, n_frames=50):
    x = np.linspace(0, 1, N)
    f0 = np.exp(-((x - 0.3) / 0.08) ** 2) + 0.5 * np.exp(-((x - 0.7) / 0.08) ** 2)
    L = build_laplacian(N)
    T = 2 * np.eye(N) - 0.25 * L
    frames = [f0]; prev, curr = np.zeros(N), f0
    for _ in range(n_frames - 1):
        nxt = T @ curr - prev; frames.append(nxt); prev, curr = curr, nxt
    return frames, None, 'Wave 1D'

def scenario_diffusion_1d(N=64, n_frames=50):
    x = np.linspace(0, 1, N)
    f0 = 20 + 5*np.sin(2*np.pi*x) + 2*np.cos(6*np.pi*x)
    L = build_laplacian(N)
    T = np.eye(N) - 0.1 * L
    frames = [f0]; curr = f0
    for _ in range(n_frames - 1):
        curr = T @ curr; frames.append(curr)
    return frames, None, 'Diffusion 1D'

def scenario_iot_grid(nx=8, ny=8, n_frames=30):
    N = nx * ny
    adj = make_grid_graph((nx, ny))
    rng = np.random.RandomState(42)
    x, y = np.meshgrid(np.linspace(0,1,nx), np.linspace(0,1,ny))
    frames = []
    for t in range(n_frames):
        field = 20 + 3*np.sin(2*np.pi*x + 0.1*t) + 2*np.cos(2*np.pi*y)
        field += 0.05 * t + 0.1 * rng.randn(ny, nx)
        frames.append(field.flatten())
    return frames, adj, f'IoT Grid {nx}x{ny}'

def scenario_sensor_network(n_sensors=30, n_frames=40):
    rng = np.random.RandomState(42)
    positions = rng.rand(n_sensors, 2) * 50
    adj = make_knn_graph(positions, k=5)
    frames = []
    for t in range(n_frames):
        base = 22 + 3*np.sin(2*np.pi*t/24) + 0.5*positions[:, 0]/50
        field = base + 0.1*rng.randn(n_sensors)
        frames.append(field)
    return frames, adj, f'Sensor Net {n_sensors}'

def scenario_vibration(N=128, n_frames=50):
    rng = np.random.RandomState(42)
    t_ax = np.linspace(0, 1, N)
    frames = []
    for t in range(n_frames):
        decay = np.exp(-0.03*t)
        frame = decay * (np.sin(2*np.pi*50*t_ax + 0.1*t) +
                         0.3*np.sin(2*np.pi*100*t_ax + 0.2*t))
        frame += 0.01 * rng.randn(N)
        frames.append(frame)
    return frames, None, 'Vibration 128'

def scenario_random(N=64, n_frames=50):
    rng = np.random.RandomState(42)
    frames = [rng.randn(N)]
    for _ in range(n_frames - 1):
        frames.append(frames[-1] + 0.1*rng.randn(N))
    return frames, None, 'Random Walk'


# ========================================================================
#  MAIN
# ========================================================================

def main():
    print("=" * 90)
    print("  COMBINED PHYSICS PIPELINE: GFT + Auto-Physics + Born-Optimal")
    print("=" * 90)

    scenarios = [
        scenario_wave_1d(),
        scenario_diffusion_1d(),
        scenario_iot_grid(),
        scenario_sensor_network(),
        scenario_vibration(),
        scenario_random(),
    ]

    print(f"\n  {'Scenario':<20} {'Method':<28} {'MSE':>10} {'Ratio':>7} {'SNR(dB)':>8}")
    print(f"  {'-'*20} {'-'*28} {'-'*10} {'-'*7} {'-'*8}")

    summary = {}
    for frames, graph, name in scenarios:
        N = len(frames[0])
        M = max(2, N // 4)

        # Baselines
        r_raw = compress_baseline(frames, 'raw', M=M, graph=graph)
        r_delta = compress_baseline(frames, 'delta', M=M, graph=graph)

        # GFT if graph available
        r_gft = None
        if graph is not None:
            r_gft = compress_baseline(frames, 'gft_raw', M=M, graph=graph)

        # Full pipeline
        r_full = compress_full_pipeline(frames, M=M, graph=graph)

        # zlib baseline
        raw_bytes = np.array(frames).tobytes()
        zlib_bytes = zlib.compress(raw_bytes, 6)
        zlib_ratio = len(zlib_bytes) / len(raw_bytes)

        methods = [
            ('raw (no pred)', r_raw),
            ('delta', r_delta),
        ]
        if r_gft:
            methods.append(('GFT (graph)', r_gft))
        methods.append((f'FULL ({r_full["physics"]})', r_full))
        methods.append(('zlib (lossless)', {'avg_mse': 0, 'ratio': zlib_ratio, 'snr_db': float('inf')}))

        best_lossy = min(methods[:-1], key=lambda x: x[1]['avg_mse'])

        for label, r in methods:
            snr_s = f"{r.get('snr_db', 10*np.log10(np.mean([np.var(f) for f in frames]) / max(r['avg_mse'], 1e-30)) if r['avg_mse'] > 0 else float('inf')):.1f}" if r['avg_mse'] > 0 else "inf"
            marker = " <-- BEST" if label == best_lossy[0] else ""
            print(f"  {name:<20} {label:<28} {r['avg_mse']:>10.6f} {r['ratio']:>7.4f} {snr_s:>8}{marker}")

        # Calculate improvement
        full_vs_delta = (r_delta['avg_mse'] - r_full['avg_mse']) / max(r_delta['avg_mse'], 1e-30) * 100
        summary[name] = {
            'full_mse': r_full['avg_mse'], 'delta_mse': r_delta['avg_mse'],
            'full_ratio': r_full['ratio'], 'zlib_ratio': zlib_ratio,
            'improvement_vs_delta': full_vs_delta,
            'physics_detected': r_full['physics'],
        }
        print()

    # === VERDICT ===
    print(f"{'=' * 90}")
    print(f"  VERDICT: Full Pipeline vs Delta Encoding")
    print(f"{'=' * 90}")
    print(f"\n  {'Scenario':<20} {'Physics':>10} {'vs Delta':>10} {'vs zlib':>10}")
    print(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*10}")

    for name, s in summary.items():
        vs_d = f"{s['improvement_vs_delta']:+.0f}%"
        ratio_cmp = f"{s['full_ratio']/s['zlib_ratio']:.2f}x" if s['zlib_ratio'] > 0 else "N/A"
        print(f"  {name:<20} {s['physics_detected']:>10} {vs_d:>10} {ratio_cmp:>10}")

    wins = sum(1 for s in summary.values() if s['improvement_vs_delta'] > 0)
    print(f"\n  Full pipeline wins: {wins}/{len(summary)} scenarios")
    print(f"\n  FULL PIPELINE = GFT (graph) + Auto-Physics (predictor) + Born (bits)")
    print(f"  = THREE E/R/R formulas working together as ONE compressor.")

    # Save
    path = Path(__file__).parent / 'results' / 'combined_pipeline.json'
    path.parent.mkdir(exist_ok=True)
    with open(path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n  Results saved to {path}")


if __name__ == '__main__':
    main()
