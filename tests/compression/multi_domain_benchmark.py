#!/usr/bin/env python3
"""
Multi-Domain Compression Benchmark

Tests GFT compression across 6 domains:
  1. Medical (ECG, EEG)
  2. Industrial (Vibration, CNC)
  3. Environmental (Weather, Air quality)
  4. Financial (Stocks, Orderbook)
  5. Audio (Speech, Music)
  6. Geospatial (Elevation)

Honest assessment. No cherry-picking.

Run: uv run python -m tests.compression.multi_domain_benchmark
"""

from __future__ import annotations
import numpy as np
import json
import time
import zlib
from pathlib import Path
from dataclasses import dataclass, asdict, field

from tests.compression.tos_compression import (
    compress, decompress, gft_compress, gft_decompress,
    compress_delta, decompress_delta, make_knn_graph,
    snr_db, mse, max_error,
)


# ========================================================================
#  DOMAIN 1: MEDICAL
# ========================================================================

def generate_ecg(N=1024, leads=12, heart_rate=72):
    rng = np.random.RandomState(42)
    ecg = np.zeros((N, leads))
    beat_interval = int(360 * 60 / heart_rate)
    for lead in range(leads):
        amp = 1.0 + 0.3 * rng.randn()
        phase = lead * 5
        for beat in range(N // beat_interval + 1):
            bs = beat * beat_interval + phase
            # P wave
            for k in range(40):
                idx = bs + 20 + k
                if 0 <= idx < N:
                    ecg[idx, lead] += amp * 0.15 * np.exp(-((k - 20) / 8) ** 2)
            # QRS
            for k in range(10):
                idx = bs + 70 + k
                if 0 <= idx < N:
                    ecg[idx, lead] += amp * (-0.3 + 1.8 * np.exp(-((k - 4) / 1.5) ** 2))
            # T wave
            for k in range(60):
                idx = bs + 120 + k
                if 0 <= idx < N:
                    ecg[idx, lead] += amp * 0.3 * np.exp(-((k - 30) / 12) ** 2)
        ecg[:, lead] += 0.05 * rng.randn(N)

    adj = np.zeros((leads, leads))
    for i in range(min(6, leads)):
        for j in range(i + 1, min(6, leads)):
            adj[i, j] = adj[j, i] = 1
    for i in range(6, min(leads - 1, 11)):
        adj[i, i + 1] = adj[i + 1, i] = 1
    if leads >= 8:
        adj[0, 6] = adj[6, 0] = 1

    return ecg, adj, {'name': 'ecg_12lead', 'domain': 'medical',
                       'N': N, 'channels': leads, 'acceptable': 'PSNR>40dB'}


def generate_eeg(N=2048, channels=19, fs=256):
    rng = np.random.RandomState(42)
    t = np.linspace(0, N / fs, N)
    eeg = np.zeros((N, channels))
    for ch in range(channels):
        a_a = 0.5 + 0.5 * rng.rand()
        a_b = 0.3 + 0.3 * rng.rand()
        a_d = 0.2 * rng.rand()
        eeg[:, ch] = (a_a * np.sin(2 * np.pi * 10 * t + rng.rand() * 6.28) +
                      a_b * np.sin(2 * np.pi * 20 * t + rng.rand() * 6.28) +
                      a_d * np.sin(2 * np.pi * 2 * t + rng.rand() * 6.28) +
                      0.1 * rng.randn(N))
    nbrs = {0:[1,2,3],1:[0,5,6],2:[0,3,7],3:[0,2,4,8],4:[3,5,9],
            5:[1,4,6,10],6:[1,5,11],7:[2,8,12],8:[3,7,9,13],9:[4,8,10,14],
            10:[5,9,11,15],11:[6,10,16],12:[7,13],13:[8,12,14,17],
            14:[9,13,15],15:[10,14,16,18],16:[11,15],17:[12,13,18],18:[15,16,17]}
    adj = np.zeros((channels, channels))
    for i, ns in nbrs.items():
        if i < channels:
            for j in ns:
                if j < channels:
                    adj[i, j] = adj[j, i] = 1
    return eeg, adj, {'name': 'eeg_19ch', 'domain': 'medical',
                       'N': N, 'channels': channels, 'acceptable': 'PSNR>30dB'}


# ========================================================================
#  DOMAIN 2: INDUSTRIAL
# ========================================================================

def generate_vibration(N=4096, sensors=8):
    rng = np.random.RandomState(42)
    t = np.linspace(0, N / 10000, N)
    f_rot = 50
    vib = np.zeros((N, sensors))
    for s in range(sensors):
        att = 1.0 / (1 + 0.5 * s)
        ph = s * 0.2
        for h in range(1, 6):
            vib[:, s] += (att / h) * np.sin(2 * np.pi * f_rot * h * t + ph * h)
        bpfo = f_rot * 3.56
        for imp_t in np.arange(0, N / 10000, 1 / bpfo):
            idx = int(imp_t * 10000)
            if idx < N - 50:
                decay = np.exp(-np.arange(50) * 0.3)
                vib[idx:idx + 50, s] += 0.3 * att * decay * np.sin(
                    2 * np.pi * 2000 * np.arange(50) / 10000)
        vib[:, s] += 0.05 * rng.randn(N)
    adj = np.zeros((sensors, sensors))
    for i in range(sensors):
        adj[i, (i + 1) % sensors] = adj[(i + 1) % sensors, i] = 1
    return vib, adj, {'name': 'vibration_8ch', 'domain': 'industrial',
                       'N': N, 'channels': sensors, 'acceptable': 'preserve fault peaks'}


def generate_cnc(N=2048, axes=6):
    rng = np.random.RandomState(42)
    t = np.linspace(0, 10, N)
    data = np.zeros((N, axes))
    data[:, 0] = 50 * np.cos(2 * np.pi * t / 10)
    data[:, 1] = 50 * np.sin(2 * np.pi * t / 10)
    data[:, 2] = -np.minimum(t, 5) * 2
    data[:, 3] = -50 * 2 * np.pi / 10 * np.sin(2 * np.pi * t / 10) * (t < 8) + 0.5 * rng.randn(N)
    data[:, 4] = 50 * 2 * np.pi / 10 * np.cos(2 * np.pi * t / 10) * (t < 8) + 0.5 * rng.randn(N)
    data[:, 5] = -5 * (t < 5).astype(float) + 0.3 * rng.randn(N)
    adj = np.zeros((axes, axes))
    adj[0, 1] = adj[1, 0] = adj[1, 2] = adj[2, 1] = 1
    adj[0, 3] = adj[3, 0] = adj[1, 4] = adj[4, 1] = adj[2, 5] = adj[5, 2] = 1
    adj[3, 4] = adj[4, 3] = 1
    return data, adj, {'name': 'cnc_6axis', 'domain': 'industrial',
                        'N': N, 'channels': axes}


# ========================================================================
#  DOMAIN 3: ENVIRONMENTAL
# ========================================================================

def generate_weather(nx=8, ny=8, timesteps=100):
    rng = np.random.RandomState(42)
    N = nx * ny
    data = np.zeros((timesteps, N))
    x = np.linspace(0, 1, nx)
    y = np.linspace(0, 1, ny)
    X, Y = np.meshgrid(x, y)
    for t_i in range(timesteps):
        base = 15 + 10 * X.flatten() - 5 * Y.flatten()
        front = 3 * np.sin(2 * np.pi * (X.flatten() - 0.01 * t_i))
        diurnal = 5 * np.sin(2 * np.pi * t_i / 24)
        data[t_i] = base + front + diurnal + 0.5 * rng.randn(N)
    adj = np.zeros((N, N))
    for i in range(nx):
        for j in range(ny):
            v = i * ny + j
            if j + 1 < ny: adj[v, v + 1] = adj[v + 1, v] = 1
            if i + 1 < nx: adj[v, v + ny] = adj[v + ny, v] = 1
    return data, adj, {'name': f'weather_{nx}x{ny}', 'domain': 'environmental',
                        'N': N, 'grid': [nx, ny]}


def generate_air_quality(stations=20, pollutants=4, timesteps=200):
    rng = np.random.RandomState(42)
    positions = rng.rand(stations, 2) * 50
    base_levels = [35, 40, 60, 15]
    data = np.zeros((timesteps, stations * pollutants))
    for p in range(pollutants):
        for t_i in range(timesteps):
            source = base_levels[p] * np.exp(-np.sum((positions - [30, 30]) ** 2, axis=1) / 200)
            hour = t_i % 24
            traffic = 1.5 if 7 <= hour <= 9 or 17 <= hour <= 19 else 1.0
            vals = source * traffic + 0.3 * np.sin(2 * np.pi * t_i / 24) * base_levels[p] * 0.1
            vals += rng.randn(stations) * base_levels[p] * 0.1
            data[t_i, p * stations:(p + 1) * stations] = vals
    N_ch = stations * pollutants
    adj = make_knn_graph(positions, k=5)
    # Expand adjacency for multi-pollutant
    adj_full = np.zeros((N_ch, N_ch))
    for p in range(pollutants):
        adj_full[p * stations:(p + 1) * stations, p * stations:(p + 1) * stations] = adj
    return data, adj_full, {'name': f'airquality_{stations}st', 'domain': 'environmental',
                             'N': N_ch, 'stations': stations}


# ========================================================================
#  DOMAIN 4: FINANCIAL
# ========================================================================

def generate_stocks(N=4096, assets=20):
    rng = np.random.RandomState(42)
    sector_size = assets // 4
    corr = np.eye(assets) * 0.5
    for s in range(4):
        a, b = s * sector_size, (s + 1) * sector_size
        corr[a:b, a:b] += 0.4
    np.fill_diagonal(corr, 1.0)
    L = np.linalg.cholesky(corr)
    returns = np.array([L @ rng.randn(assets) * 0.01 for _ in range(N)])
    prices = 100 * np.exp(np.cumsum(returns, axis=0))
    c = np.corrcoef(returns.T)
    adj = (np.abs(c) > 0.5).astype(float)
    np.fill_diagonal(adj, 0)
    return prices, adj, {'name': f'stocks_{assets}', 'domain': 'financial',
                          'N': N, 'assets': assets, 'acceptable': 'PSNR>60dB'}


def generate_orderbook(N=2048, levels=10):
    rng = np.random.RandomState(42)
    mid = 100 + np.cumsum(0.01 * rng.randn(N))
    spread = 0.05 + 0.02 * np.abs(rng.randn(N))
    data = np.zeros((N, 2 * levels))
    for lv in range(levels):
        data[:, lv] = mid - spread / 2 - lv * 0.01
        data[:, levels + lv] = mid + spread / 2 + lv * 0.01
    data += 0.001 * rng.randn(N, 2 * levels)
    n_ch = 2 * levels
    adj = np.zeros((n_ch, n_ch))
    for lv in range(levels - 1):
        adj[lv, lv + 1] = adj[lv + 1, lv] = 1
        adj[levels + lv, levels + lv + 1] = adj[levels + lv + 1, levels + lv] = 1
    for lv in range(levels):
        adj[lv, levels + lv] = adj[levels + lv, lv] = 1
    return data, adj, {'name': f'orderbook_{levels}lvl', 'domain': 'financial',
                        'N': N, 'channels': n_ch}


# ========================================================================
#  DOMAIN 5: AUDIO
# ========================================================================

def _make_chain_graph(N: int) -> np.ndarray:
    """Path graph P_N: each node connected to neighbors."""
    adj = np.zeros((N, N))
    for i in range(N - 1):
        adj[i, i + 1] = adj[i + 1, i] = 1
    return adj


def generate_speech(N=512, fs=8000):
    """Speech: 512 samples (64ms frame) with chain graph."""
    rng = np.random.RandomState(42)
    t = np.linspace(0, N / fs, N)
    signal = np.zeros(N)
    # Voiced: fundamental + formants
    f0 = 130
    signal += 0.5 * np.sin(2 * np.pi * f0 * t)
    signal += 0.3 * np.sin(2 * np.pi * f0 * 3 * t)
    signal += 0.2 * np.sin(2 * np.pi * f0 * 5 * t)
    # Unvoiced tail
    signal[int(N * 0.75):] = 0.2 * rng.randn(N - int(N * 0.75))
    signal += 0.03 * rng.randn(N)
    adj = _make_chain_graph(N)
    return signal, adj, {'name': 'speech_512', 'domain': 'audio',
                          'N': N, 'fs': fs, 'acceptable': 'SNR>20dB'}


def generate_music(N=1024, fs=16000):
    """Music: 1024 samples (64ms frame) with chain graph."""
    rng = np.random.RandomState(42)
    t = np.linspace(0, N / fs, N)
    signal = np.zeros(N)
    for f in [261.6, 329.6, 392.0]:
        signal += 0.3 * np.sin(2 * np.pi * f * t)
    # Melody note
    env = np.exp(-5 * t)
    signal += 0.5 * env * np.sin(2 * np.pi * 523.3 * t)
    signal += 0.02 * rng.randn(N)
    adj = _make_chain_graph(N)
    return signal, adj, {'name': 'music_1024', 'domain': 'audio',
                          'N': N, 'fs': fs, 'acceptable': 'SNR>30dB'}


# ========================================================================
#  DOMAIN 6: GEOSPATIAL
# ========================================================================

def generate_elevation(nx=32, ny=32):
    rng = np.random.RandomState(42)
    x = np.linspace(0, 1, nx); y = np.linspace(0, 1, ny)
    X, Y = np.meshgrid(x, y)
    elev = (500 * np.sin(2 * np.pi * X) * np.cos(np.pi * Y) +
            300 * np.exp(-((X - 0.3) ** 2 + (Y - 0.7) ** 2) / 0.05) +
            200 * np.cos(3 * np.pi * X) * np.sin(2 * np.pi * Y))
    ridge = np.abs(Y - 0.5 * np.sin(4 * np.pi * X) - 0.5) < 0.05
    elev[ridge] += 200
    elev += 5 * rng.randn(ny, nx)
    N = nx * ny
    adj = np.zeros((N, N))
    for i in range(nx):
        for j in range(ny):
            v = i * ny + j
            if j + 1 < ny: adj[v, v + 1] = adj[v + 1, v] = 1
            if i + 1 < nx: adj[v, v + ny] = adj[v + ny, v] = 1
    return elev.flatten(), adj, {'name': f'elevation_{nx}x{ny}', 'domain': 'geospatial',
                                  'N': N}


# ========================================================================
#  BENCHMARK ENGINE
# ========================================================================

@dataclass
class DomainResult:
    domain: str
    signal_name: str
    N: int
    M_ratio: float
    gft_ratio: float
    gft_snr: float
    dft_ratio: float
    dft_snr: float
    graph_advantage_db: float
    zlib_ratio: float
    int16z_ratio: float


def benchmark_one(signal: np.ndarray, adj: np.ndarray, meta: dict,
                   M_ratio: float = 0.2) -> DomainResult:
    """Benchmark one signal at one M ratio."""
    N = len(signal)
    M = max(2, int(N * M_ratio))
    orig_bytes = N * 8

    # GFT
    try:
        cs_g = gft_compress(signal, adj, M=M, quant_step=0.01)
        r_g = decompress_gft_safe(cs_g, adj)
        gft_ratio = cs_g.compressed_bits / 8 / orig_bytes
        gft_snr = snr_db(signal, r_g)
    except Exception:
        gft_ratio, gft_snr = 0, 0

    # DFT
    cs_d = compress(signal, M=M, quant_step=0.01)
    r_d = decompress(cs_d)
    dft_ratio = cs_d.compressed_bits / 8 / orig_bytes
    dft_snr = snr_db(signal, r_d)

    # zlib
    raw = signal.astype(np.float64).tobytes()
    zraw = zlib.compress(raw, 6)
    zlib_ratio = len(zraw) / orig_bytes

    # int16+zlib
    vmin, vmax = signal.min(), signal.max()
    vrange = max(vmax - vmin, 1e-10)
    q16 = np.round((signal - vmin) / vrange * 65535).astype(np.uint16)
    q16z = zlib.compress(q16.tobytes(), 6)
    int16z_ratio = len(q16z) / orig_bytes

    return DomainResult(
        domain=meta['domain'], signal_name=meta['name'], N=N, M_ratio=M_ratio,
        gft_ratio=gft_ratio, gft_snr=gft_snr,
        dft_ratio=dft_ratio, dft_snr=dft_snr,
        graph_advantage_db=gft_snr - dft_snr,
        zlib_ratio=zlib_ratio, int16z_ratio=int16z_ratio
    )


def decompress_gft_safe(cs, adj):
    from tests.compression.tos_compression import gft_decompress
    return gft_decompress(cs, adj)


# ========================================================================
#  MAIN
# ========================================================================

def main():
    print("=" * 75)
    print("  MULTI-DOMAIN COMPRESSION BENCHMARK")
    print("=" * 75)

    # Generate all signals
    generators = [
        # Medical
        lambda: extract_snapshot(*generate_ecg()),
        lambda: extract_snapshot(*generate_eeg()),
        # Industrial
        lambda: extract_snapshot(*generate_vibration()),
        lambda: extract_snapshot(*generate_cnc()),
        # Environmental
        lambda: extract_snapshot(*generate_weather()),
        lambda: extract_snapshot(*generate_air_quality()),
        # Financial
        lambda: extract_snapshot(*generate_stocks()),
        lambda: extract_snapshot(*generate_orderbook()),
        # Audio
        lambda: (lambda s, a, m: (s, a, m))(*generate_speech()),
        lambda: (lambda s, a, m: (s, a, m))(*generate_music()),
        # Geospatial
        lambda: (lambda s, a, m: (s, a, m))(*generate_elevation()),
    ]

    results = []
    for gen in generators:
        signal, adj, meta = gen()
        for mr in [0.1, 0.2, 0.5]:
            r = benchmark_one(signal, adj, meta, mr)
            results.append(r)

    # Print main table at M=20%
    print(f"\n{'Domain':<14} {'Signal':<18} {'N':>6} "
          f"{'GFT%':>6} {'GFT dB':>7} {'DFT%':>6} {'DFT dB':>7} "
          f"{'Graph+':>7} {'zlib%':>6} {'i16z%':>6}")
    print("-" * 105)

    for r in results:
        if abs(r.M_ratio - 0.2) < 0.01:
            gs = f"{r.gft_snr:.1f}" if r.gft_snr < 200 else "inf"
            ds = f"{r.dft_snr:.1f}" if r.dft_snr < 200 else "inf"
            ga = f"+{r.graph_advantage_db:.1f}" if r.graph_advantage_db > 0 else f"{r.graph_advantage_db:.1f}"
            print(f"{r.domain:<14} {r.signal_name:<18} {r.N:>6} "
                  f"{r.gft_ratio * 100:>5.1f}% {gs:>7} "
                  f"{r.dft_ratio * 100:>5.1f}% {ds:>7} "
                  f"{ga:>7} {r.zlib_ratio * 100:>5.1f}% {r.int16z_ratio * 100:>5.1f}%")

    # Rankings
    r20 = [r for r in results if abs(r.M_ratio - 0.2) < 0.01]

    print(f"\n  DOMAIN RANKING (by graph advantage at M=20%):")
    for i, r in enumerate(sorted(r20, key=lambda x: -x.graph_advantage_db)):
        ga = f"+{r.graph_advantage_db:.1f}" if r.graph_advantage_db > 0 else f"{r.graph_advantage_db:.1f}"
        print(f"    {i + 1}. {r.signal_name:<18} {ga} dB")

    print(f"\n  DOMAIN RANKING (by GFT compression ratio at M=20%):")
    for i, r in enumerate(sorted(r20, key=lambda x: x.gft_ratio)):
        print(f"    {i + 1}. {r.signal_name:<18} {r.gft_ratio * 100:.1f}%")

    # Verdicts
    print(f"\n  CONCLUSIONS:")
    best_graph = max(r20, key=lambda x: x.graph_advantage_db)
    worst_graph = min(r20, key=lambda x: x.graph_advantage_db)
    best_ratio = min(r20, key=lambda x: x.gft_ratio)
    zlib_wins = [r for r in r20 if r.zlib_ratio < r.gft_ratio]

    print(f"    Graph helps MOST: {best_graph.signal_name} (+{best_graph.graph_advantage_db:.1f} dB)")
    print(f"    Graph helps LEAST: {worst_graph.signal_name} ({worst_graph.graph_advantage_db:.1f} dB)")
    print(f"    Best compression: {best_ratio.signal_name} ({best_ratio.gft_ratio * 100:.1f}%)")
    if zlib_wins:
        names = ", ".join(r.signal_name for r in zlib_wins)
        print(f"    zlib wins (lossless < GFT lossy): {names}")
    else:
        print(f"    GFT beats zlib on ALL domains at M=20% (lossy)")

    # Multi-ratio analysis
    print(f"\n  RATE-DISTORTION (GFT at M=10%, 20%, 50%):")
    for name in sorted(set(r.signal_name for r in results)):
        rs = [r for r in results if r.signal_name == name]
        rs.sort(key=lambda x: x.M_ratio)
        vals = " | ".join(f"M={int(r.M_ratio*100)}%: {r.gft_ratio*100:.1f}%/{r.gft_snr:.0f}dB" for r in rs)
        print(f"    {name:<18} {vals}")

    # Save
    output_dir = Path(__file__).parent / 'results'
    output_dir.mkdir(exist_ok=True)
    path = output_dir / 'multi_domain_results.json'
    with open(path, 'w') as f:
        json.dump([asdict(r) for r in results], f, indent=2, default=str)
    print(f"\n  Results saved to {path}")


def extract_snapshot(data, adj, meta):
    """Extract single snapshot from multi-channel/temporal data."""
    if data.ndim == 1:
        return data, adj, meta
    if data.ndim == 2:
        # Take first row if temporal (rows=time), else first col
        if data.shape[0] > data.shape[1]:
            # rows=time, cols=channels -> take snapshot across channels
            return data[0], adj, {**meta, 'N': data.shape[1]}
        else:
            return data[:, 0], adj, {**meta, 'N': data.shape[0]}
    return data.flatten(), adj, meta


if __name__ == '__main__':
    main()
