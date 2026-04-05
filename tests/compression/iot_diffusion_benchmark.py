#!/usr/bin/env python3
"""
IoT Diffusion + Dominant Modes Benchmark

Real-world IoT scenario: temperature sensors with diffusion physics + dominant modes.
Compare FULL ToS pipeline vs zlib, LZ4-like, float16, delta+zlib, SZ-like.

Three test cases:
  1. Indoor climate: 54 sensors, daily cycle + spatial diffusion
  2. Industrial furnace: 20 sensors, high temp + fast diffusion + dominant harmonics
  3. Cold chain: 10 sensors, slow drift + periodic door openings

Run: uv run python -m tests.compression.iot_diffusion_benchmark
"""

import numpy as np
import json
import time
import zlib
import struct
from pathlib import Path

from tests.compression.tos_compression import (
    compress, decompress, gft_compress, gft_decompress,
    make_knn_graph, mse, snr_db,
)
from tests.compression.auto_physics import detect_physics, compress_auto_physics
from tests.compression.born_benchmark import compress_born


# ========================================================================
#  REALISTIC IoT DATA GENERATORS
# ========================================================================

def gen_indoor_climate(n_sensors=54, n_hours=24, samples_per_hour=60):
    """Indoor climate monitoring: 54 sensors, 1-minute resolution, 24 hours."""
    rng = np.random.RandomState(42)
    n_frames = n_hours * samples_per_hour
    positions = np.column_stack([rng.uniform(2, 38, n_sensors),
                                  rng.uniform(2, 28, n_sensors)])

    # Sensor biases (calibration drift)
    biases = rng.randn(n_sensors) * 0.3

    frames = []
    for t in range(n_frames):
        hour = t / samples_per_hour
        # Base temperature: HVAC cycle
        base = 22.0 + 2.0 * np.sin(2 * np.pi * hour / 24)
        # Spatial gradient: windows on east side
        spatial = 1.5 * np.sin(2 * np.pi * positions[:, 0] / 40)
        # Sun heating (afternoon peak on south wall)
        sun = 0 if hour < 10 or hour > 18 else 1.5 * np.exp(-((positions[:, 1] - 2) / 8)**2)
        # Diffusion from HVAC vents (at positions 10,15 and 30,15)
        vent1 = 2.0 * np.exp(-np.sum((positions - [10, 15])**2, axis=1) / 50)
        vent2 = 2.0 * np.exp(-np.sum((positions - [30, 15])**2, axis=1) / 50)
        # Noise
        noise = 0.05 * rng.randn(n_sensors)

        field = base + spatial + sun + vent1 + vent2 + biases + noise
        frames.append(field)

    adj = make_knn_graph(positions, k=5)
    return frames, adj, positions, {
        'name': 'Indoor Climate', 'n_sensors': n_sensors,
        'n_frames': n_frames, 'duration_hours': n_hours,
        'temp_range': f"{np.min(frames):.1f}-{np.max(frames):.1f} C",
        'tolerance': 0.5,  # acceptable error in Celsius
    }


def gen_industrial_furnace(n_sensors=20, n_minutes=60, samples_per_min=10):
    """Industrial furnace: 20 sensors, 0.1s resolution, 1 hour."""
    rng = np.random.RandomState(123)
    n_frames = n_minutes * samples_per_min
    positions = np.column_stack([rng.uniform(0, 2, n_sensors),
                                  rng.uniform(0, 2, n_sensors)])

    frames = []
    for t in range(n_frames):
        minute = t / samples_per_min
        # High base temperature
        base = 800 + 50 * np.sin(2 * np.pi * minute / 15)  # 15-min cycle
        # Dominant harmonics (vibration from combustion)
        harm1 = 20 * np.sin(2 * np.pi * 3 * minute / 60)
        harm2 = 8 * np.sin(2 * np.pi * 7 * minute / 60)
        # Spatial: center hotter
        center_heat = 100 * np.exp(-np.sum((positions - [1, 1])**2, axis=1) / 0.5)
        # Fast diffusion (metal conducts well)
        noise = 0.5 * rng.randn(n_sensors)
        field = base + harm1 + harm2 + center_heat + noise
        frames.append(field)

    adj = make_knn_graph(positions, k=4)
    return frames, adj, positions, {
        'name': 'Industrial Furnace', 'n_sensors': n_sensors,
        'n_frames': n_frames, 'duration_min': n_minutes,
        'temp_range': f"{np.min(frames):.0f}-{np.max(frames):.0f} C",
        'tolerance': 2.0,
    }


def gen_cold_chain(n_sensors=10, n_hours=72, samples_per_hour=12):
    """Cold chain: 10 sensors in refrigerated truck, 72 hours, 5-min resolution."""
    rng = np.random.RandomState(456)
    n_frames = n_hours * samples_per_hour
    positions = np.linspace(0, 5, n_sensors).reshape(-1, 1)

    frames = []
    base_temp = -18.0
    for t in range(n_frames):
        hour = t / samples_per_hour
        # Slow drift (compressor aging)
        drift = 0.01 * hour
        # Door openings: spike every 8 hours, lasts ~30 min
        door_open = 0
        for open_hour in range(0, n_hours, 8):
            if open_hour <= hour < open_hour + 0.5:
                door_open = 15 * np.exp(-((positions[:, 0] - 0) / 1)**2).flatten()
        # Spatial gradient: door at position 0
        spatial = 0.5 * positions[:, 0] / 5
        noise = 0.02 * rng.randn(n_sensors)

        if isinstance(door_open, (int, float)):
            field = base_temp + drift + door_open + spatial + noise
        else:
            field = base_temp + drift + door_open + spatial.flatten() + noise
        frames.append(field.flatten())

    adj = np.zeros((n_sensors, n_sensors))
    for i in range(n_sensors - 1):
        adj[i, i+1] = adj[i+1, i] = 1
    return frames, adj, positions, {
        'name': 'Cold Chain', 'n_sensors': n_sensors,
        'n_frames': n_frames, 'duration_hours': n_hours,
        'temp_range': f"{np.min(frames):.1f}-{np.max(frames):.1f} C",
        'tolerance': 1.0,
    }


# ========================================================================
#  BASELINE COMPRESSORS
# ========================================================================

def compress_zlib(frames, level=6):
    raw = np.array(frames, dtype=np.float64).tobytes()
    t0 = time.perf_counter()
    comp = zlib.compress(raw, level)
    ct = time.perf_counter() - t0
    t0 = time.perf_counter()
    zlib.decompress(comp)
    dt = time.perf_counter() - t0
    return {'method': f'zlib-{level}', 'bytes': len(comp), 'raw_bytes': len(raw),
            'ratio': len(comp)/len(raw), 'mse': 0.0, 'snr_db': float('inf'),
            'compress_s': ct, 'decompress_s': dt, 'lossy': False}


def compress_delta_zlib(frames, level=6):
    deltas = [frames[0]] + [frames[i] - frames[i-1] for i in range(1, len(frames))]
    raw = np.array(deltas, dtype=np.float64).tobytes()
    comp = zlib.compress(raw, level)
    return {'method': 'delta+zlib', 'bytes': len(comp),
            'raw_bytes': len(np.array(frames).tobytes()),
            'ratio': len(comp)/len(np.array(frames).tobytes()),
            'mse': 0.0, 'snr_db': float('inf'), 'lossy': False}


def compress_float16(frames):
    raw64 = np.array(frames, dtype=np.float64)
    raw16 = raw64.astype(np.float16)
    recon = raw16.astype(np.float64)
    comp = zlib.compress(raw16.tobytes(), 6)
    err = float(np.mean((raw64 - recon)**2))
    snr = float(snr_db(raw64.flatten(), recon.flatten())) if err > 0 else float('inf')
    return {'method': 'float16+zlib', 'bytes': len(comp),
            'raw_bytes': raw64.nbytes, 'ratio': len(comp)/raw64.nbytes,
            'mse': err, 'snr_db': snr, 'lossy': True}


def compress_int16_scaled(frames):
    raw = np.array(frames, dtype=np.float64)
    vmin, vmax = raw.min(), raw.max()
    scale = max(vmax - vmin, 1e-10)
    q = np.round((raw - vmin) / scale * 65535).astype(np.uint16)
    recon = q.astype(np.float64) / 65535 * scale + vmin
    comp = zlib.compress(q.tobytes(), 6)
    err = float(np.mean((raw - recon)**2))
    snr = float(snr_db(raw.flatten(), recon.flatten())) if err > 0 else float('inf')
    return {'method': 'int16-scaled+zlib', 'bytes': len(comp),
            'raw_bytes': raw.nbytes, 'ratio': len(comp)/raw.nbytes,
            'mse': err, 'snr_db': snr, 'lossy': True}


def compress_tos_full(frames, adj, M_ratio=0.3, quant_step=0.01):
    """Full ToS pipeline: GFT + auto-physics + Born."""
    n_frames = len(frames)
    N = len(frames[0])
    M = max(2, int(N * M_ratio))

    physics = detect_physics(frames[:min(10, n_frames)])

    total_bits = 0
    total_mse = 0
    prev = np.zeros(N)
    pprev = np.zeros(N)
    t0 = time.perf_counter()

    for t in range(n_frames):
        frame = np.array(frames[t], dtype=float)

        # Physics prediction
        if t == 0:
            predicted = np.zeros(N)
        elif physics == 'diffusion':
            predicted = 0.9 * prev + 0.1 * frame  # simple diffusion approx
            predicted = prev  # safe: just use previous
        else:
            predicted = prev

        residual = frame - predicted

        # GFT on residual
        if adj is not None and N <= 100:
            cs = gft_compress(residual, adj, M=M, quant_step=quant_step)
            recon_res = gft_decompress(cs, adj)
            total_bits += cs.compressed_bits
        else:
            recon_res, info = compress_born(residual, M, total_bits_per_coeff=8)
            total_bits += M * 16

        recon = predicted + recon_res
        total_mse += mse(frame, recon)
        pprev = prev.copy()
        prev = recon.copy()

    ct = time.perf_counter() - t0
    raw_bytes = n_frames * N * 8
    avg_mse = total_mse / n_frames
    return {
        'method': f'ToS-full(M={M_ratio:.0%})',
        'bytes': total_bits // 8,
        'raw_bytes': raw_bytes,
        'ratio': (total_bits // 8) / raw_bytes,
        'mse': avg_mse,
        'snr_db': float(10*np.log10(np.mean([np.var(f) for f in frames]) / max(avg_mse, 1e-30))) if avg_mse > 0 else float('inf'),
        'lossy': True,
        'physics': physics,
        'compress_s': ct,
    }


# ========================================================================
#  MAIN
# ========================================================================

def main():
    print("=" * 90)
    print("  IoT DIFFUSION + DOMINANT MODES BENCHMARK")
    print("  Real-world scenarios: climate, furnace, cold chain")
    print("=" * 90)

    scenarios = [
        gen_indoor_climate(),
        gen_industrial_furnace(),
        gen_cold_chain(),
    ]

    all_results = {}

    for frames, adj, positions, meta in scenarios:
        n_frames = len(frames)
        N = len(frames[0])
        raw_bytes = n_frames * N * 8

        print(f"\n{'=' * 90}")
        print(f"  {meta['name']}: {meta['n_sensors']} sensors, {n_frames} frames")
        print(f"  Range: {meta['temp_range']}, Tolerance: {meta['tolerance']} C")
        print(f"  Raw: {raw_bytes:,} bytes ({raw_bytes/1024:.1f} KB)")
        print(f"{'=' * 90}")

        results = []

        # Raw (no compression)
        results.append({'method': 'raw', 'bytes': raw_bytes, 'raw_bytes': raw_bytes,
                        'ratio': 1.0, 'mse': 0, 'snr_db': float('inf'), 'lossy': False})

        # Baselines
        results.append(compress_zlib(frames))
        results.append(compress_delta_zlib(frames))
        results.append(compress_float16(frames))
        results.append(compress_int16_scaled(frames))

        # ToS pipeline at different M
        for mr in [0.1, 0.2, 0.3, 0.5]:
            results.append(compress_tos_full(frames, adj, M_ratio=mr))

        # Sort by ratio
        results.sort(key=lambda r: r['ratio'])

        print(f"\n  {'Method':<24} {'Size':>10} {'Ratio':>7} {'MSE':>10} "
              f"{'SNR(dB)':>8} {'<Tol?':>6} {'Type'}")
        print(f"  {'-'*24} {'-'*10} {'-'*7} {'-'*10} {'-'*8} {'-'*6} {'-'*8}")

        for r in results:
            size_s = f"{r['bytes']:,}" if r['bytes'] < 1e6 else f"{r['bytes']/1024:.0f}K"
            snr_s = f"{r['snr_db']:.1f}" if r['snr_db'] < 200 else "inf"
            within_tol = "YES" if r['mse'] < meta['tolerance']**2 else ("N/A" if r['mse'] == 0 else "NO")
            type_s = "lossy" if r.get('lossy', False) else "lossless"
            print(f"  {r['method']:<24} {size_s:>10} {r['ratio']:>7.3f} "
                  f"{r['mse']:>10.4f} {snr_s:>8} {within_tol:>6} {type_s}")

        # Find best lossy within tolerance
        within_tol = [r for r in results if r.get('lossy') and r['mse'] < meta['tolerance']**2]
        if within_tol:
            best = min(within_tol, key=lambda r: r['ratio'])
            zlib_r = next(r for r in results if r['method'] == 'zlib-6')
            print(f"\n  BEST LOSSY (within {meta['tolerance']}C): {best['method']}")
            print(f"    Ratio: {best['ratio']:.3f} ({1/best['ratio']:.0f}x compression)")
            print(f"    vs zlib: {zlib_r['ratio']/best['ratio']:.1f}x smaller")
            print(f"    MSE: {best['mse']:.4f} C^2 (RMSE: {best['mse']**0.5:.3f} C)")

        all_results[meta['name']] = [
            {k: v for k, v in r.items() if k != 'compress_s' and k != 'decompress_s'}
            for r in results
        ]

    # === GRAND SUMMARY ===
    print(f"\n{'=' * 90}")
    print(f"  GRAND SUMMARY")
    print(f"{'=' * 90}")
    print(f"\n  {'Scenario':<22} {'Best ToS':>10} {'zlib':>10} {'delta+z':>10} {'int16+z':>10} {'Ratio':>8}")
    print(f"  {'-'*22} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")

    for name, results in all_results.items():
        tos_results = [r for r in results if 'ToS' in r['method'] and r['mse'] < 4]
        best_tos = min(tos_results, key=lambda r: r['ratio']) if tos_results else None
        zlib_r = next((r for r in results if r['method'] == 'zlib-6'), None)
        delta_r = next((r for r in results if r['method'] == 'delta+zlib'), None)
        int16_r = next((r for r in results if r['method'] == 'int16-scaled+zlib'), None)

        tos_s = f"{best_tos['ratio']:.3f}" if best_tos else "N/A"
        zlib_s = f"{zlib_r['ratio']:.3f}" if zlib_r else "N/A"
        delta_s = f"{delta_r['ratio']:.3f}" if delta_r else "N/A"
        int16_s = f"{int16_r['ratio']:.3f}" if int16_r else "N/A"

        if best_tos and zlib_r:
            ratio_s = f"{zlib_r['ratio']/best_tos['ratio']:.1f}x"
        else:
            ratio_s = "N/A"

        print(f"  {name:<22} {tos_s:>10} {zlib_s:>10} {delta_s:>10} {int16_s:>10} {ratio_s:>8}")

    # Save
    path = Path(__file__).parent / 'results' / 'iot_diffusion_benchmark.json'
    path.parent.mkdir(exist_ok=True)
    with open(path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  Results saved to {path}")


if __name__ == '__main__':
    main()
