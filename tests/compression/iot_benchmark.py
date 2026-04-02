#!/usr/bin/env python3
"""
Real-World IoT Benchmark: Intel Lab Sensor Data Compression

Tests GFT compression pipeline on real/synthetic IoT sensor data.
Compares with zlib, float32, int16+zlib baselines.
Reports: compression ratio, SNR, MSE, speed.

Run:
  uv run python -m tests.compression.iot_benchmark
"""

from __future__ import annotations
import numpy as np
import json
import time
import zlib
import sys
from pathlib import Path
from dataclasses import dataclass, asdict

from tests.compression.tos_compression import (
    compress, decompress, compress_adaptive, compress_delta, decompress_delta,
    gft_compress, gft_decompress, make_knn_graph,
    snr_db, mse, max_error, dft_graph
)


# ========================================================================
#  SYNTHETIC INTEL LAB DATA (fallback if download fails)
# ========================================================================

def generate_synthetic_iot(N_sensors: int = 54, N_snapshots: int = 200,
                            seed: int = 42) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate synthetic sensor data matching Intel Lab structure.

    Returns: (temp_matrix, humid_matrix, positions)
      temp_matrix: N_snapshots x N_sensors
      humid_matrix: N_snapshots x N_sensors
      positions: N_sensors x 2 (x, y in meters)
    """
    rng = np.random.RandomState(seed)

    # Sensor positions: irregular grid in 40x30m lab
    positions = np.column_stack([
        rng.uniform(2, 38, N_sensors),
        rng.uniform(2, 28, N_sensors)
    ])

    # Spatial temperature field: smooth 2D function + per-sensor offset
    sensor_offsets = rng.randn(N_sensors) * 0.5  # ±0.5degC per sensor

    temp_matrix = np.zeros((N_snapshots, N_sensors))
    humid_matrix = np.zeros((N_snapshots, N_sensors))

    for t in range(N_snapshots):
        phase = 2 * np.pi * t / N_snapshots

        for i in range(N_sensors):
            x, y = positions[i]
            # Base temperature: spatial gradient + daily cycle
            base_temp = (
                22.0                                        # room avg
                + 3.0 * np.sin(phase)                       # daily cycle
                + 1.5 * np.sin(2 * np.pi * x / 40)         # spatial x gradient
                + 1.0 * np.cos(2 * np.pi * y / 30)         # spatial y gradient
                + 0.02 * t                                  # warming trend
                + sensor_offsets[i]                          # sensor bias
                + 0.1 * rng.randn()                         # noise
            )
            temp_matrix[t, i] = base_temp

            # Humidity: anti-correlated with temp + independent noise
            base_humid = (
                45.0
                - 2.0 * (base_temp - 22.0)                 # anti-correlated
                + 0.5 * rng.randn()                         # noise
            )
            humid_matrix[t, i] = np.clip(base_humid, 10, 90)

    return temp_matrix, humid_matrix, positions


# ========================================================================
#  BUILD SENSOR GRAPHS
# ========================================================================

def build_graphs(temp_matrix: np.ndarray,
                  positions: np.ndarray) -> dict[str, np.ndarray]:
    """Build multiple graph types from sensor data."""
    N = temp_matrix.shape[1]
    graphs = {}

    # Correlation-based graph
    corr = np.corrcoef(temp_matrix.T)
    adj_corr = (np.abs(corr) > 0.7).astype(float)
    np.fill_diagonal(adj_corr, 0)
    graphs['correlation'] = adj_corr

    # k-NN from positions
    graphs['knn_k5'] = make_knn_graph(positions, k=5)
    graphs['knn_k3'] = make_knn_graph(positions, k=3)

    return graphs


# ========================================================================
#  BENCHMARK ONE SIGNAL
# ========================================================================

@dataclass
class MethodResult:
    method: str
    compressed_bytes: int
    ratio: float
    mse_val: float
    snr_db_val: float
    compress_ms: float
    decompress_ms: float
    notes: str = ""


def benchmark_signal(signal: np.ndarray, adjacency: np.ndarray = None,
                      label: str = "") -> list[MethodResult]:
    """Benchmark all methods on one signal."""
    N = len(signal)
    original_bytes = N * 8
    results = []

    # --- GFT with graph ---
    if adjacency is not None:
        for M_ratio in [0.1, 0.2, 0.3, 0.5]:
            M = max(2, int(N * M_ratio))
            try:
                t0 = time.perf_counter()
                cs = gft_compress(signal, adjacency, M=M, quant_step=0.01)
                ct = (time.perf_counter() - t0) * 1000

                t0 = time.perf_counter()
                recon = gft_decompress(cs, adjacency)
                dt = (time.perf_counter() - t0) * 1000

                cb = cs.compressed_bits // 8
                results.append(MethodResult(
                    f"GFT_M{int(M_ratio*100)}%", cb,
                    cb / original_bytes, mse(signal, recon),
                    snr_db(signal, recon), ct, dt, f"graph={label}"
                ))
            except Exception as e:
                results.append(MethodResult(
                    f"GFT_M{int(M_ratio*100)}%", 0, 0, 0, 0, 0, 0, f"ERROR: {e}"
                ))

    # --- Standard DFT (cycle graph) ---
    for M_ratio in [0.1, 0.2, 0.5]:
        M = max(2, int(N * M_ratio))
        t0 = time.perf_counter()
        cs = compress(signal, M=M, quant_step=0.01)
        ct = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        recon = decompress(cs)
        dt = (time.perf_counter() - t0) * 1000

        cb = cs.compressed_bits // 8
        results.append(MethodResult(
            f"DFT_M{int(M_ratio*100)}%", cb,
            cb / original_bytes, mse(signal, recon),
            snr_db(signal, recon), ct, dt
        ))

    # --- Adaptive ---
    for target in [20, 30]:
        try:
            t0 = time.perf_counter()
            cs = compress_adaptive(signal, target_snr=target, quant_step=0.01)
            ct = (time.perf_counter() - t0) * 1000
            recon = decompress(cs)
            dt = 0

            cb = cs.compressed_bits // 8
            results.append(MethodResult(
                f"Adaptive_SNR{target}", cb,
                cb / original_bytes, mse(signal, recon),
                snr_db(signal, recon), ct, dt
            ))
        except Exception:
            pass

    # --- zlib ---
    raw = signal.astype(np.float64).tobytes()
    for level in [1, 6]:
        t0 = time.perf_counter()
        comp = zlib.compress(raw, level)
        ct = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        zlib.decompress(comp)
        dt = (time.perf_counter() - t0) * 1000
        results.append(MethodResult(
            f"zlib_L{level}", len(comp), len(comp)/original_bytes,
            0.0, float('inf'), ct, dt, "LOSSLESS"
        ))

    # --- float32 ---
    r32 = signal.astype(np.float32).astype(np.float64)
    mse32 = mse(signal, r32)
    results.append(MethodResult(
        "float32", N*4, 0.5, mse32,
        snr_db(signal, r32), 0, 0, "LOSSY baseline"
    ))

    # --- int16 + zlib ---
    vmin, vmax = signal.min(), signal.max()
    vrange = max(vmax - vmin, 1e-10)
    q16 = np.round((signal - vmin) / vrange * 65535).astype(np.uint16)
    r16 = q16.astype(np.float64) / 65535 * vrange + vmin
    mse16 = mse(signal, r16)
    q16z = zlib.compress(q16.tobytes(), 6)
    results.append(MethodResult(
        "int16_zlib", len(q16z), len(q16z)/original_bytes,
        mse16, snr_db(signal, r16), 0, 0, "LOSSY+LOSSLESS"
    ))

    # --- raw ---
    results.append(MethodResult(
        "raw_float64", original_bytes, 1.0, 0.0, float('inf'), 0, 0
    ))

    return results


# ========================================================================
#  TEMPORAL BATCH BENCHMARK
# ========================================================================

def benchmark_temporal(temp_matrix: np.ndarray, N_snapshots: int = 100
                        ) -> dict:
    """Benchmark temporal compression: independent vs delta vs zlib."""
    N_snap = min(N_snapshots, len(temp_matrix))
    N_sensors = temp_matrix.shape[1]
    original_total = N_snap * N_sensors * 8
    M = max(2, N_sensors // 4)

    # Independent GFT
    ind_bytes = 0
    ind_mse = 0
    t0 = time.perf_counter()
    for t in range(N_snap):
        cs = compress(temp_matrix[t], M=M, quant_step=0.01)
        recon = decompress(cs)
        ind_bytes += cs.compressed_bits // 8 + 20
        ind_mse += mse(temp_matrix[t], recon)
    ind_time = (time.perf_counter() - t0) * 1000

    # Delta GFT
    delta_bytes = 0
    delta_mse_total = 0
    t0 = time.perf_counter()
    cs0 = compress(temp_matrix[0], M=M, quant_step=0.01)
    delta_bytes += cs0.compressed_bits // 8 + 20
    prev = decompress(cs0)
    delta_mse_total += mse(temp_matrix[0], prev)

    for t in range(1, N_snap):
        cs_d = compress_delta(prev, temp_matrix[t], M=M, quant_step=0.001)
        delta_bytes += cs_d.compressed_bits // 8 + 5
        prev = decompress_delta(prev, cs_d)
        delta_mse_total += mse(temp_matrix[t], prev)
    delta_time = (time.perf_counter() - t0) * 1000

    # zlib raw
    raw = temp_matrix[:N_snap].astype(np.float64).tobytes()
    t0 = time.perf_counter()
    zraw = zlib.compress(raw, 6)
    zraw_time = (time.perf_counter() - t0) * 1000

    # zlib delta
    delta_mat = np.diff(temp_matrix[:N_snap], axis=0)
    dbytes = np.vstack([temp_matrix[0:1], delta_mat]).astype(np.float64).tobytes()
    t0 = time.perf_counter()
    zdelta = zlib.compress(dbytes, 6)
    zdelta_time = (time.perf_counter() - t0) * 1000

    return {
        'N_snapshots': N_snap,
        'N_sensors': N_sensors,
        'original_bytes': original_total,
        'independent_GFT': {
            'bytes': ind_bytes, 'ratio': ind_bytes / original_total,
            'avg_mse': ind_mse / N_snap, 'time_ms': ind_time,
        },
        'delta_GFT': {
            'bytes': delta_bytes, 'ratio': delta_bytes / original_total,
            'avg_mse': delta_mse_total / N_snap, 'time_ms': delta_time,
        },
        'zlib_raw': {
            'bytes': len(zraw), 'ratio': len(zraw) / original_total,
            'mse': 0.0, 'time_ms': zraw_time,
        },
        'zlib_delta': {
            'bytes': len(zdelta), 'ratio': len(zdelta) / original_total,
            'mse': 0.0, 'time_ms': zdelta_time,
        },
    }


# ========================================================================
#  MAIN
# ========================================================================

def print_table(results: list[MethodResult], title: str):
    print(f"\n{title}")
    print(f"  {'Method':<22} {'Ratio':>7} {'SNR(dB)':>8} {'MSE':>12} "
          f"{'Enc(ms)':>8} {'Dec(ms)':>8} {'Notes'}")
    print(f"  {'-'*22} {'-'*7} {'-'*8} {'-'*12} {'-'*8} {'-'*8} {'-'*15}")
    for r in sorted(results, key=lambda x: x.ratio if x.ratio > 0 else 999):
        snr_s = f"{r.snr_db_val:.1f}" if r.snr_db_val < 200 else "inf"
        mse_s = f"{r.mse_val:.6f}" if r.mse_val > 0 else "0"
        print(f"  {r.method:<22} {r.ratio:>7.3f} {snr_s:>8} {mse_s:>12} "
              f"{r.compress_ms:>8.2f} {r.decompress_ms:>8.2f} {r.notes}")


def main():
    print("=" * 78)
    print("  REAL-WORLD IoT BENCHMARK — Synthetic Intel Lab Data")
    print("=" * 78)

    # Generate data
    N_sensors = 54
    N_snapshots = 200
    temp_matrix, humid_matrix, positions = generate_synthetic_iot(N_sensors, N_snapshots)

    print(f"\nDataset: {N_sensors} sensors, {N_snapshots} snapshots")
    print(f"Temperature: {temp_matrix.min():.1f}degC to {temp_matrix.max():.1f}degC")
    print(f"Humidity: {humid_matrix.min():.1f}% to {humid_matrix.max():.1f}%")

    # Build graphs
    graphs = build_graphs(temp_matrix, positions)
    for name, adj in graphs.items():
        edges = int(np.sum(adj) / 2)
        print(f"Graph '{name}': {edges} edges")

    # === SINGLE SNAPSHOT ===
    print(f"\n{'=' * 78}")
    print("  SINGLE SNAPSHOT COMPRESSION")
    print(f"  Signal: {N_sensors} sensors, one time step")
    print(f"{'=' * 78}")

    all_single = {}
    for graph_name in ['correlation', 'knn_k5']:
        adj = graphs[graph_name]
        results = benchmark_signal(temp_matrix[0], adj, graph_name)
        all_single[f"temp_{graph_name}"] = results
        print_table(results, f"Temperature — graph={graph_name}")

    # No-graph DFT
    results_dft = benchmark_signal(temp_matrix[0])
    all_single['temp_no_graph'] = results_dft
    print_table(results_dft, "Temperature — no graph (cycle DFT)")

    # === TEMPORAL BATCH ===
    print(f"\n{'=' * 78}")
    print(f"  TEMPORAL BATCH: {N_sensors} sensors x {min(100, N_snapshots)} steps")
    print(f"{'=' * 78}")

    temporal = benchmark_temporal(temp_matrix, N_snapshots=100)

    print(f"\n  {'Method':<22} {'Ratio':>7} {'MSE':>12} {'Time(ms)':>10} {'Notes'}")
    print(f"  {'-'*22} {'-'*7} {'-'*12} {'-'*10} {'-'*15}")
    for name in ['independent_GFT', 'delta_GFT', 'zlib_raw', 'zlib_delta']:
        r = temporal[name]
        mse_v = r.get('avg_mse', r.get('mse', 0))
        mse_s = f"{mse_v:.6f}" if mse_v > 0 else "0 (lossless)"
        notes = "LOSSY" if mse_v > 0 else "LOSSLESS"
        print(f"  {name:<22} {r['ratio']:>7.3f} {mse_s:>12} "
              f"{r.get('time_ms', 0):>10.1f} {notes}")

    # === VERDICT ===
    print(f"\n{'=' * 78}")
    print("  VERDICT")
    print(f"{'=' * 78}")

    # Q1: GFT with graph vs without
    gft_corr = [r for r in all_single.get('temp_correlation', [])
                if 'GFT_M20%' in r.method]
    dft_only = [r for r in all_single.get('temp_no_graph', [])
                if 'DFT_M20%' in r.method]
    if gft_corr and dft_only:
        snr_gft = gft_corr[0].snr_db_val
        snr_dft = dft_only[0].snr_db_val
        print(f"\n  Q1: Graph-aware GFT vs cycle DFT at M=20%:")
        print(f"      GFT (correlation): SNR = {snr_gft:.1f} dB")
        print(f"      DFT (cycle):       SNR = {snr_dft:.1f} dB")
        if snr_gft > snr_dft:
            print(f"      -> GFT wins by {snr_gft - snr_dft:.1f} dB")
        else:
            print(f"      -> DFT wins by {snr_dft - snr_gft:.1f} dB (graph doesn't help here)")

    # Q2: GFT vs zlib at matched quality
    zlib_ratio = next((r.ratio for r in results_dft if r.method == 'zlib_L6'), 1.0)
    gft_20 = next((r for r in results_dft if r.method == 'DFT_M20%'), None)
    if gft_20:
        print(f"\n  Q2: GFT (M=20%, lossy) vs zlib (lossless):")
        print(f"      GFT: ratio={gft_20.ratio:.3f}, SNR={gft_20.snr_db_val:.1f} dB")
        print(f"      zlib: ratio={zlib_ratio:.3f}, SNR=inf")
        if gft_20.ratio < zlib_ratio:
            print(f"      -> GFT {zlib_ratio/gft_20.ratio:.1f}x smaller at SNR {gft_20.snr_db_val:.0f} dB")
        else:
            print(f"      -> zlib smaller (lossless wins for this signal size)")

    # Q3: Delta GFT vs zlib-delta
    d_gft = temporal['delta_GFT']
    d_zlib = temporal['zlib_delta']
    print(f"\n  Q3: Delta GFT vs zlib-delta (temporal):")
    print(f"      Delta GFT:  ratio={d_gft['ratio']:.3f}, avg MSE={d_gft['avg_mse']:.6f}")
    print(f"      zlib-delta: ratio={d_zlib['ratio']:.3f}, MSE=0 (lossless)")

    # Save results
    output_dir = Path(__file__).parent / 'results'
    output_dir.mkdir(exist_ok=True)

    all_results = {
        'metadata': {
            'N_sensors': N_sensors, 'N_snapshots': N_snapshots,
            'temp_range': [float(temp_matrix.min()), float(temp_matrix.max())],
            'humid_range': [float(humid_matrix.min()), float(humid_matrix.max())],
            'data_type': 'synthetic_intel_lab',
        },
        'single_snapshot': {
            k: [asdict(r) for r in v] for k, v in all_single.items()
        },
        'temporal_batch': temporal,
    }

    results_path = output_dir / 'iot_benchmark_results.json'
    with open(results_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  Results saved to {results_path}")


if __name__ == '__main__':
    main()
