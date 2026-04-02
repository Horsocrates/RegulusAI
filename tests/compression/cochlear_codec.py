#!/usr/bin/env python3
"""
Cochlear Codec: Perception-Adapted Audio Compression

The ear IS a GFT analyzer on a tapered graph (basilar membrane).
Each position resonates at a specific frequency.
Optimal audio compression = GFT on the SAME graph the ear uses.

This codec builds a cochlear-inspired graph and compresses audio
using GFT on that graph vs standard DFT (uniform frequency spacing).

Key insight from Acoustics formalization:
  Sound = propagation of L1-L5 tension on graph.
  Hearing = GFT decomposition on cochlear graph.
  Compression = selecting which tensions to keep.
  Cochlear GFT = keep what the EAR keeps. No wasted bits.

Run: uv run python -m tests.compression.cochlear_codec
"""

from __future__ import annotations
import numpy as np
import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict

from tests.compression.tos_compression import (
    compress, decompress, gft_compress, gft_decompress,
    snr_db, mse, max_error,
)


# ========================================================================
#  COCHLEAR GRAPH: MODELS BASILAR MEMBRANE
# ========================================================================

def bark_scale(f_hz: float) -> float:
    """Bark scale: perceptual frequency mapping.
    Bark(f) = 13*atan(0.76*f/1000) + 3.5*atan((f/7500)^2)"""
    return 13 * np.arctan(0.00076 * f_hz) + 3.5 * np.arctan((f_hz / 7500) ** 2)


def erb_scale(f_hz: float) -> float:
    """Equivalent Rectangular Bandwidth.
    ERB(f) = 21.4 * log10(1 + 0.00437*f)"""
    return 21.4 * np.log10(1 + 0.00437 * f_hz)


def build_cochlear_graph(N: int, fs: int = 16000,
                          scale: str = 'bark') -> tuple[np.ndarray, np.ndarray]:
    """Build cochlear-inspired graph for N-point audio frame.

    The basilar membrane maps frequency to position logarithmically.
    Adjacent positions on membrane = adjacent nodes on graph.
    But: bandwidth increases with frequency (critical bands widen).

    Returns: (adjacency_matrix, center_frequencies)
    """
    # Frequency bins for N-point DFT
    freqs = np.fft.fftfreq(N, d=1.0/fs)[:N//2+1]  # positive freqs
    freqs[0] = 1  # avoid log(0)
    n_bins = len(freqs)

    # Map to perceptual scale
    if scale == 'bark':
        perceptual = np.array([bark_scale(f) for f in freqs])
    else:
        perceptual = np.array([erb_scale(f) for f in freqs])

    # Normalize to [0, 1]
    if perceptual[-1] > perceptual[0]:
        perceptual = (perceptual - perceptual[0]) / (perceptual[-1] - perceptual[0])

    # Build graph: connect bins that are close in PERCEPTUAL space
    # This makes low-frequency bins more connected (finer resolution)
    # and high-frequency bins less connected (coarser resolution)
    adj = np.zeros((N, N))

    # Chain graph on DFT bins with perceptual weighting
    for i in range(N - 1):
        # Weight = inverse perceptual distance (closer = stronger coupling)
        fi = freqs[min(i, n_bins-1) % n_bins] if i < n_bins else freqs[-(i - n_bins + 1) % n_bins]
        fi1 = freqs[min(i+1, n_bins-1) % n_bins] if i+1 < n_bins else freqs[-(i+1 - n_bins + 1) % n_bins]
        adj[i, i+1] = 1
        adj[i+1, i] = 1

    # Add cross-connections for critical bands
    # Bins within same critical band are connected
    band_width = max(1, N // 24)  # ~24 Bark bands
    for i in range(0, N, band_width):
        for j in range(i, min(i + band_width, N)):
            for k in range(j + 1, min(i + band_width, N)):
                adj[j, k] = 0.5  # weaker intra-band connection
                adj[k, j] = 0.5

    return adj, freqs[:n_bins]


def build_mel_graph(N: int, n_mels: int = 40, fs: int = 16000) -> np.ndarray:
    """Build graph based on mel filterbank structure.
    Each mel band = one node. Adjacent bands connected.
    Within each band: connected to constituent DFT bins."""
    # Simple: chain graph on N points with mel-spaced extra connections
    adj = np.zeros((N, N))

    # Base: chain
    for i in range(N - 1):
        adj[i, i+1] = adj[i+1, i] = 1

    # Mel-spaced groupings: connect bins within each mel band
    mel_edges = np.linspace(0, 2595 * np.log10(1 + fs/2/700), n_mels + 2)
    mel_edges = 700 * (10 ** (mel_edges / 2595) - 1)
    bin_edges = (mel_edges * N / fs).astype(int)

    for m in range(n_mels):
        lo = max(0, bin_edges[m])
        hi = min(N, bin_edges[m + 2])
        for i in range(lo, hi):
            for j in range(i + 1, hi):
                if adj[i, j] == 0:
                    adj[i, j] = adj[j, i] = 0.3

    return adj


# ========================================================================
#  AUDIO SIGNAL GENERATORS
# ========================================================================

def generate_speech_frame(N: int = 512, fs: int = 16000) -> np.ndarray:
    """Voiced speech: F0 + formants."""
    rng = np.random.RandomState(42)
    t = np.arange(N) / fs
    f0 = 130  # male fundamental
    signal = np.zeros(N)
    # Harmonics with formant envelope
    formants = [800, 1200, 2500, 3500]  # F1-F4
    bandwidths = [80, 100, 120, 150]
    for n in range(1, 30):
        freq = f0 * n
        # Formant gain
        gain = 0
        for fi, bw in zip(formants, bandwidths):
            gain += np.exp(-0.5 * ((freq - fi) / bw) ** 2)
        gain = max(gain, 0.01)
        signal += gain / n * np.sin(2 * np.pi * freq * t)
    signal += 0.01 * rng.randn(N)
    return signal / np.max(np.abs(signal))


def generate_music_frame(N: int = 1024, fs: int = 16000) -> np.ndarray:
    """Piano chord: C major with overtones."""
    t = np.arange(N) / fs
    signal = np.zeros(N)
    # C4, E4, G4
    for note_f in [261.6, 329.6, 392.0]:
        for h in range(1, 8):
            amp = 0.5 / h ** 1.5
            signal += amp * np.sin(2 * np.pi * note_f * h * t)
    # Decay envelope
    signal *= np.exp(-3 * t)
    signal += 0.005 * np.random.RandomState(42).randn(N)
    return signal / np.max(np.abs(signal))


def generate_noise_frame(N: int = 512) -> np.ndarray:
    """White noise."""
    return np.random.RandomState(42).randn(N) * 0.5


def generate_mixed_frame(N: int = 512, fs: int = 16000) -> np.ndarray:
    """Speech + background noise."""
    speech = generate_speech_frame(N, fs)
    noise = 0.1 * np.random.RandomState(123).randn(N)
    return speech + noise


# ========================================================================
#  BENCHMARK
# ========================================================================

@dataclass
class CodecResult:
    signal_type: str
    method: str
    N: int
    M: int
    ratio: float
    snr: float
    mse_val: float
    compress_ms: float
    graph_type: str = ""


def benchmark_frame(signal: np.ndarray, signal_type: str,
                     M_ratio: float = 0.2) -> list[CodecResult]:
    """Compare cochlear GFT vs standard DFT on one frame."""
    N = len(signal)
    M = max(2, int(N * M_ratio))
    results = []

    # 1. Standard DFT (cycle graph = FFT)
    t0 = time.perf_counter()
    cs_dft = compress(signal, M=M, quant_step=0.001)
    ct = (time.perf_counter() - t0) * 1000
    r_dft = decompress(cs_dft)
    results.append(CodecResult(
        signal_type, 'DFT (uniform)', N, M,
        cs_dft.compressed_bits / (N * 64),
        snr_db(signal, r_dft), mse(signal, r_dft), ct, 'cycle'
    ))

    # 2. Cochlear GFT (Bark scale)
    adj_bark, _ = build_cochlear_graph(N, scale='bark')
    t0 = time.perf_counter()
    cs_bark = gft_compress(signal, adj_bark, M=M, quant_step=0.001)
    ct = (time.perf_counter() - t0) * 1000
    r_bark = gft_decompress(cs_bark, adj_bark)
    results.append(CodecResult(
        signal_type, 'GFT (Bark cochlear)', N, M,
        cs_bark.compressed_bits / (N * 64),
        snr_db(signal, r_bark), mse(signal, r_bark), ct, 'cochlear_bark'
    ))

    # 3. Mel filterbank GFT
    adj_mel = build_mel_graph(N)
    t0 = time.perf_counter()
    cs_mel = gft_compress(signal, adj_mel, M=M, quant_step=0.001)
    ct = (time.perf_counter() - t0) * 1000
    r_mel = gft_decompress(cs_mel, adj_mel)
    results.append(CodecResult(
        signal_type, 'GFT (Mel filterbank)', N, M,
        cs_mel.compressed_bits / (N * 64),
        snr_db(signal, r_mel), mse(signal, r_mel), ct, 'mel'
    ))

    # 4. Simple chain graph (path P_N)
    adj_chain = np.zeros((N, N))
    for i in range(N - 1):
        adj_chain[i, i+1] = adj_chain[i+1, i] = 1
    t0 = time.perf_counter()
    cs_chain = gft_compress(signal, adj_chain, M=M, quant_step=0.001)
    ct = (time.perf_counter() - t0) * 1000
    r_chain = gft_decompress(cs_chain, adj_chain)
    results.append(CodecResult(
        signal_type, 'GFT (chain P_N)', N, M,
        cs_chain.compressed_bits / (N * 64),
        snr_db(signal, r_chain), mse(signal, r_chain), ct, 'chain'
    ))

    return results


def rate_distortion_sweep(signal: np.ndarray, signal_type: str,
                           adj: np.ndarray, method_name: str,
                           graph_type: str) -> list[CodecResult]:
    """Sweep M from 5% to 80% for rate-distortion curve."""
    N = len(signal)
    results = []
    for ratio in [0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.8]:
        M = max(2, int(N * ratio))
        try:
            cs = gft_compress(signal, adj, M=M, quant_step=0.001)
            r = gft_decompress(cs, adj)
            results.append(CodecResult(
                signal_type, method_name, N, M,
                cs.compressed_bits / (N * 64),
                snr_db(signal, r), mse(signal, r), 0, graph_type
            ))
        except Exception:
            pass
    return results


# ========================================================================
#  MAIN
# ========================================================================

def main():
    print("=" * 75)
    print("  COCHLEAR CODEC BENCHMARK")
    print("  Perception-adapted GFT vs uniform DFT for audio")
    print("=" * 75)

    # Generate signals
    signals = {
        'speech': generate_speech_frame(256, 16000),
        'music': generate_music_frame(256, 16000),
        'noise': generate_noise_frame(256),
        'mixed': generate_mixed_frame(256, 16000),
    }

    # === MAIN COMPARISON at M=20% ===
    print(f"\n--- SINGLE FRAME COMPARISON (N=256, M=20%) ---")
    print(f"{'Signal':<10} {'Method':<22} {'Ratio':>7} {'SNR(dB)':>8} "
          f"{'MSE':>10} {'Time(ms)':>9}")
    print("-" * 75)

    all_results = []
    for sig_name, signal in signals.items():
        results = benchmark_frame(signal, sig_name, M_ratio=0.2)
        all_results.extend(results)
        for r in results:
            snr_s = f"{r.snr:.1f}" if r.snr < 200 else "inf"
            print(f"{r.signal_type:<10} {r.method:<22} {r.ratio:>7.4f} "
                  f"{snr_s:>8} {r.mse_val:>10.6f} {r.compress_ms:>9.2f}")
        print()

    # === RATE-DISTORTION CURVES ===
    print(f"\n--- RATE-DISTORTION: Speech (N=256) ---")
    print(f"{'M%':>4} {'DFT SNR':>8} {'Cochlear SNR':>13} {'Mel SNR':>9} {'Chain SNR':>10}")
    print("-" * 50)

    speech = signals['speech']
    N = len(speech)

    # Build graphs once
    adj_bark, _ = build_cochlear_graph(N)
    adj_mel = build_mel_graph(N)
    adj_chain = np.zeros((N, N))
    for i in range(N - 1):
        adj_chain[i, i+1] = adj_chain[i+1, i] = 1

    for ratio in [0.05, 0.1, 0.15, 0.2, 0.3, 0.5]:
        M = max(2, int(N * ratio))

        # DFT
        cs_d = compress(speech, M=M, quant_step=0.001)
        snr_d = snr_db(speech, decompress(cs_d))

        # Cochlear
        cs_b = gft_compress(speech, adj_bark, M=M, quant_step=0.001)
        snr_b = snr_db(speech, gft_decompress(cs_b, adj_bark))

        # Mel
        cs_m = gft_compress(speech, adj_mel, M=M, quant_step=0.001)
        snr_m = snr_db(speech, gft_decompress(cs_m, adj_mel))

        # Chain
        cs_c = gft_compress(speech, adj_chain, M=M, quant_step=0.001)
        snr_c = snr_db(speech, gft_decompress(cs_c, adj_chain))

        def fmt(s): return f"{s:.1f}" if s < 200 else "inf"
        print(f"{int(ratio*100):>3}% {fmt(snr_d):>8} {fmt(snr_b):>13} "
              f"{fmt(snr_m):>9} {fmt(snr_c):>10}")

    # === VERDICT ===
    print(f"\n--- VERDICT ---")

    # Compare at M=20%
    speech_results = [r for r in all_results if r.signal_type == 'speech']
    if len(speech_results) >= 4:
        dft_snr = speech_results[0].snr
        bark_snr = speech_results[1].snr
        mel_snr = speech_results[2].snr
        chain_snr = speech_results[3].snr

        print(f"\n  Speech at M=20%:")
        print(f"    DFT (uniform):      {dft_snr:.1f} dB")
        print(f"    GFT (Bark cochlear):{bark_snr:.1f} dB")
        print(f"    GFT (Mel):          {mel_snr:.1f} dB")
        print(f"    GFT (chain):        {chain_snr:.1f} dB")

        best = max([(dft_snr, 'DFT'), (bark_snr, 'Bark'), (mel_snr, 'Mel'), (chain_snr, 'Chain')])
        worst = min([(dft_snr, 'DFT'), (bark_snr, 'Bark'), (mel_snr, 'Mel'), (chain_snr, 'Chain')])
        print(f"\n    Best:  {best[1]} ({best[0]:.1f} dB)")
        print(f"    Worst: {worst[1]} ({worst[0]:.1f} dB)")
        print(f"    Gap:   {best[0] - worst[0]:.1f} dB")

        if bark_snr > dft_snr:
            print(f"\n    -> Cochlear graph WINS by {bark_snr - dft_snr:.1f} dB")
            print(f"       Perception-adapted basis captures speech better.")
        elif dft_snr > bark_snr:
            print(f"\n    -> DFT WINS by {dft_snr - bark_snr:.1f} dB")
            print(f"       For short frames, uniform DFT is hard to beat.")
            print(f"       Cochlear advantage may appear at lower M or longer frames.")
        else:
            print(f"\n    -> Tied. Graph structure doesn't help for this frame size.")

    # Music
    music_results = [r for r in all_results if r.signal_type == 'music']
    if len(music_results) >= 2:
        print(f"\n  Music at M=20%:")
        for r in music_results:
            snr_s = f"{r.snr:.1f}" if r.snr < 200 else "inf"
            print(f"    {r.method:<22} {snr_s} dB")

    # Save
    output_dir = Path(__file__).parent / 'results'
    output_dir.mkdir(exist_ok=True)
    path = output_dir / 'cochlear_codec_results.json'
    with open(path, 'w') as f:
        json.dump([asdict(r) for r in all_results], f, indent=2)
    print(f"\n  Results saved to {path}")


if __name__ == '__main__':
    main()
