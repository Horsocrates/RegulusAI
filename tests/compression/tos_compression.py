"""
ToS Verified Compression Pipeline — Python Implementation

Mirrors the Coq formalization in _tos_coq_clone/src/stdlib/compression/.
Every function here has a corresponding Qed-verified Coq definition.

Pipeline: f → DFT → truncate → quantize → [store] → dequantize → IDFT → f'

Coq correspondence:
  dft_graph    ↔ FourierBasis.v: dft_4 (generalized to N)
  idft_graph   ↔ FourierBasis.v: idft_4 (generalized to N)
  truncate     ↔ SpectralCompression.v: truncated_recon
  quantize     ↔ VerifiedQuantization.v: quantize
  dequantize   ↔ VerifiedQuantization.v: dequantize
  compress     ↔ CompressionPipeline.v: compress_pipeline
  huffman_*    ↔ VerifiedHuffman.v: CodeTree, kraft_sum
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import Optional
import heapq
import time


# ========================================================================
#  DFT ON CYCLE GRAPH (mirrors FourierBasis.v)
# ========================================================================

def cycle_eigenvalues(N: int) -> np.ndarray:
    """Eigenvalues of cycle graph C_N adjacency matrix.
    λ_k = 2cos(2πk/N) for k = 0, ..., N-1.
    Coq: cycle_eigenvalue_4 for N=4."""
    k = np.arange(N)
    return 2 * np.cos(2 * np.pi * k / N)


def cycle_eigenvectors(N: int) -> np.ndarray:
    """Eigenvectors of C_N. Column k = φ_k.
    Real DFT basis: cos and sin components.
    Coq: phi_0, phi_1, phi_2, phi_3 for N=4."""
    basis = np.zeros((N, N))
    for k in range(N):
        for j in range(N):
            basis[j, k] = np.cos(2 * np.pi * k * j / N)
    return basis


def dft_graph(f: np.ndarray) -> np.ndarray:
    """DFT via standard FFT on cycle graph C_N.
    Eigenvalues of C_N adjacency = 2cos(2πk/N), eigenvectors = DFT columns.
    Returns complex coefficients (N values).
    Coq: dft_4 (generalized to N)."""
    return np.fft.fft(f)


def idft_graph(fhat: np.ndarray, N: Optional[int] = None) -> np.ndarray:
    """Inverse DFT: f = IFFT(f̂).
    Coq: idft_4 (generalized)."""
    if N is None:
        N = len(fhat)
    result = np.fft.ifft(fhat, n=N)
    return np.real(result)


# ========================================================================
#  SPECTRAL TRUNCATION (mirrors SpectralCompression.v)
# ========================================================================

def truncate(fhat: np.ndarray, M: int) -> tuple[np.ndarray, np.ndarray]:
    """Keep top M coefficients by magnitude, zero the rest.
    Returns (truncated_fhat, kept_indices).
    Coq: truncated_recon with keep predicate."""
    result = np.zeros_like(fhat)
    if M >= len(fhat):
        return fhat.copy(), np.arange(len(fhat))
    indices = np.argsort(np.abs(fhat))[::-1][:M]
    result[indices] = fhat[indices]
    return result, indices


# ========================================================================
#  QUANTIZATION (mirrors VerifiedQuantization.v)
# ========================================================================

def quantize(x: np.ndarray, step: float) -> np.ndarray:
    """Quantize to nearest grid point.
    Coq: quantize_index(x, step) = floor(x/step + 0.5).
    Returns integer indices."""
    if step <= 0:
        return x.copy()
    return np.floor(x / step + 0.5).astype(np.int64)


def dequantize(indices: np.ndarray, step: float) -> np.ndarray:
    """Reconstruct from indices.
    Coq: dequantize(idx, step) = idx * step."""
    return indices.astype(np.float64) * step


# ========================================================================
#  HUFFMAN CODING (mirrors VerifiedHuffman.v)
# ========================================================================

@dataclass
class HuffmanNode:
    """Binary tree node. Coq: CodeTree = CTLeaf | CTNode."""
    freq: float
    symbol: Optional[int] = None
    left: Optional['HuffmanNode'] = None
    right: Optional['HuffmanNode'] = None

    def __lt__(self, other):
        return self.freq < other.freq


def build_huffman_tree(symbols: np.ndarray) -> tuple[dict, HuffmanNode]:
    """Build Huffman tree from symbol array.
    Returns (codebook, tree).
    Coq: tree_4_optimal for specific distribution."""
    unique, counts = np.unique(symbols, return_counts=True)
    if len(unique) <= 1:
        return {int(unique[0]): '0'} if len(unique) == 1 else {}, HuffmanNode(0)

    heap = [HuffmanNode(c, s) for s, c in zip(unique, counts)]
    heapq.heapify(heap)

    while len(heap) > 1:
        left = heapq.heappop(heap)
        right = heapq.heappop(heap)
        merged = HuffmanNode(left.freq + right.freq, left=left, right=right)
        heapq.heappush(heap, merged)

    tree = heap[0]
    codebook = {}

    def _build_codes(node, prefix=''):
        if node.symbol is not None:
            codebook[int(node.symbol)] = prefix or '0'
        else:
            if node.left:
                _build_codes(node.left, prefix + '0')
            if node.right:
                _build_codes(node.right, prefix + '1')

    _build_codes(tree)
    return codebook, tree


def huffman_encode(symbols: np.ndarray) -> tuple[str, dict]:
    """Encode symbols to bitstring via Huffman.
    Returns (bitstring, codebook)."""
    codebook, _ = build_huffman_tree(symbols)
    bits = ''.join(codebook[int(s)] for s in symbols)
    return bits, codebook


def huffman_decode(bits: str, codebook: dict) -> list[int]:
    """Decode Huffman bitstring."""
    reverse = {v: k for k, v in codebook.items()}
    result = []
    current = ''
    for b in bits:
        current += b
        if current in reverse:
            result.append(reverse[current])
            current = ''
    return result


def kraft_sum(codebook: dict) -> float:
    """Kraft inequality: Σ 2^{-l_i}. Should be ≤ 1.
    Coq: kraft_sum(tree) verified == 1."""
    return sum(2 ** (-len(code)) for code in codebook.values())


# ========================================================================
#  FULL COMPRESSION PIPELINE (mirrors CompressionPipeline.v)
# ========================================================================

@dataclass
class CompressedSignal:
    """Compressed representation."""
    indices: np.ndarray          # quantized DFT coefficients (integers)
    kept_modes: np.ndarray       # which modes were kept
    quant_step: float            # quantization step size
    N: int                       # original signal length
    huffman_bits: Optional[str] = None
    codebook: Optional[dict] = None

    @property
    def compressed_bits(self) -> int:
        if self.huffman_bits:
            return len(self.huffman_bits)
        return len(self.indices) * 16  # fallback: 16 bits per index

    @property
    def original_bits(self) -> int:
        return self.N * 64  # 64-bit float per sample

    @property
    def compression_ratio(self) -> float:
        return self.compressed_bits / self.original_bits


def compress(f: np.ndarray, M: int, quant_step: float = 0.01,
             use_huffman: bool = True) -> CompressedSignal:
    """Full pipeline: f → DFT → truncate → quantize → [Huffman] → compressed.
    Coq: compress_pipeline."""
    N = len(f)

    # Step 1-2: DFT + truncate
    fhat = dft_graph(f)
    fhat_trunc, kept = truncate(fhat, M)

    # Step 3: Quantize real and imaginary parts separately
    kept_values_re = np.real(fhat_trunc[kept])
    kept_values_im = np.imag(fhat_trunc[kept])
    indices_re = quantize(kept_values_re, quant_step)
    indices_im = quantize(kept_values_im, quant_step)
    # Interleave: [re0, im0, re1, im1, ...]
    indices = np.empty(2 * len(kept), dtype=np.int64)
    indices[0::2] = indices_re
    indices[1::2] = indices_im

    # Step 4: Huffman encode
    bits, codebook = None, None
    if use_huffman and len(indices) > 0:
        bits, codebook = huffman_encode(indices)

    return CompressedSignal(
        indices=indices, kept_modes=kept, quant_step=quant_step,
        N=N, huffman_bits=bits, codebook=codebook
    )


def decompress(cs: CompressedSignal) -> np.ndarray:
    """Reconstruct: dequantize → IDFT → signal.
    Coq: decompress."""
    # Step 5: Dequantize (or Huffman decode first)
    if cs.huffman_bits and cs.codebook:
        decoded = np.array(huffman_decode(cs.huffman_bits, cs.codebook))
        values_flat = dequantize(decoded, cs.quant_step)
    else:
        values_flat = dequantize(cs.indices, cs.quant_step)

    # Step 6: Reconstruct complex coefficients from interleaved re/im
    n_kept = len(cs.kept_modes)
    values_re = values_flat[0::2][:n_kept]
    values_im = values_flat[1::2][:n_kept]
    values = values_re + 1j * values_im

    # Reconstruct full coefficient vector
    fhat = np.zeros(cs.N, dtype=complex)
    fhat[cs.kept_modes[:len(values)]] = values

    # Step 7: IDFT
    return idft_graph(fhat, cs.N)


# ========================================================================
#  METRICS (mirrors ErrorComposition.v)
# ========================================================================

def mse(f: np.ndarray, f_recon: np.ndarray) -> float:
    """Mean squared error."""
    return float(np.mean((f - f_recon) ** 2))


def snr_db(f: np.ndarray, f_recon: np.ndarray) -> float:
    """Signal-to-noise ratio in dB.
    SNR = 10·log10(signal_power / noise_power)."""
    signal_power = np.mean(f ** 2)
    noise_power = np.mean((f - f_recon) ** 2)
    if noise_power < 1e-30:
        return float('inf')
    return float(10 * np.log10(signal_power / noise_power))


def max_error(f: np.ndarray, f_recon: np.ndarray) -> float:
    """Maximum absolute error.
    Coq: Qabs bound."""
    return float(np.max(np.abs(f - f_recon)))


def parseval_check(f: np.ndarray) -> tuple[float, float]:
    """Verify Parseval: N·‖f‖² = Σ |f̂_k|².
    For standard FFT: Σ|f̂_k|² = N·Σ|f_j|² (Parseval-Plancherel).
    Returns (time_energy, freq_energy/N). Should be equal."""
    N = len(f)
    time_energy = float(np.sum(f ** 2))
    fhat = np.fft.fft(f)
    freq_energy = float(np.sum(np.abs(fhat) ** 2)) / N
    return time_energy, freq_energy


# ========================================================================
#  IMPROVEMENT 1: ADAPTIVE M SELECTION
#  Select M automatically to meet target quality (SNR, MSE, or ratio).
#  Uses Parseval: Error(M) = Σ_{k>M} |f̂_k|² / N.
# ========================================================================

def spectral_energy_curve(f: np.ndarray) -> np.ndarray:
    """Cumulative spectral energy: E(M) = Σ_{top M} |f̂_k|² / N.
    Sorted by coefficient magnitude (largest first)."""
    fhat = dft_graph(f)
    N = len(f)
    mags_sq = np.abs(fhat) ** 2 / N
    sorted_mags = np.sort(mags_sq)[::-1]
    return np.cumsum(sorted_mags)


def find_M_for_target_snr(f: np.ndarray, target_snr: float) -> int:
    """Find minimum M modes to achieve target SNR (dB).
    SNR = 10·log10(signal_power / error_power).
    Error(M) = total - kept = Σ_{discarded} |f̂_k|²/N."""
    N = len(f)
    total = float(np.mean(f ** 2))
    if total < 1e-30:
        return 1
    target_noise = total / (10 ** (target_snr / 10))
    curve = spectral_energy_curve(f)
    for M in range(1, N + 1):
        error = total - curve[M - 1]
        if error <= target_noise:
            return M
    return N


def find_M_for_target_mse(f: np.ndarray, target_mse: float) -> int:
    """Find minimum M modes to achieve target MSE."""
    N = len(f)
    total = float(np.mean(f ** 2))
    curve = spectral_energy_curve(f)
    for M in range(1, N + 1):
        error = total - curve[M - 1]
        if error <= target_mse:
            return M
    return N


def find_M_for_target_ratio(f: np.ndarray, target_ratio: float,
                              quant_step: float = 0.01) -> int:
    """Find M modes that gives approximately target compression ratio."""
    N = len(f)
    # Each kept mode stores ~2 quantized values (re, im)
    # Approximate: ratio ≈ 2M * avg_bits / (N * 64)
    # Solve for M: M ≈ target_ratio * N * 64 / (2 * avg_bits)
    avg_bits = 8  # rough estimate for Huffman
    M = max(1, int(target_ratio * N * 64 / (2 * avg_bits)))
    return min(M, N)


def compress_adaptive(f: np.ndarray, *,
                       target_snr: Optional[float] = None,
                       target_mse: Optional[float] = None,
                       target_ratio: Optional[float] = None,
                       quant_step: float = 0.01,
                       use_huffman: bool = True) -> CompressedSignal:
    """Compress with automatic M selection based on quality target.
    Exactly ONE of target_snr, target_mse, target_ratio must be set."""
    if target_snr is not None:
        M = find_M_for_target_snr(f, target_snr)
    elif target_mse is not None:
        M = find_M_for_target_mse(f, target_mse)
    elif target_ratio is not None:
        M = find_M_for_target_ratio(f, target_ratio, quant_step)
    else:
        M = len(f) // 2  # default: keep half
    return compress(f, M=M, quant_step=quant_step, use_huffman=use_huffman)


# ========================================================================
#  IMPROVEMENT 2: ADAPTIVE QUANTIZATION
#  More bits for important (low-frequency) coefficients.
# ========================================================================

def adaptive_quant_step(k: int, N: int, base_step: float = 0.01) -> float:
    """Quantization step for mode k: finer for low-k, coarser for high-k.
    bits(k) ≈ max(4, 16 - 2·log₂(k+1)), step = base / 2^(extra_bits)."""
    # Low modes get finer quantization
    extra_bits = max(0, 8 - int(2 * np.log2(k + 1)))
    return base_step * (2 ** max(0, 4 - extra_bits))


def compress_adaptive_quant(f: np.ndarray, M: int,
                              base_step: float = 0.01,
                              use_huffman: bool = True) -> CompressedSignal:
    """Compress with per-mode quantization step."""
    N = len(f)
    fhat = dft_graph(f)
    fhat_trunc, kept = truncate(fhat, M)

    # Adaptive quantization per mode
    indices_list = []
    for idx in kept:
        step = adaptive_quant_step(int(idx), N, base_step)
        re_idx = quantize(np.array([np.real(fhat_trunc[idx])]), step)[0]
        im_idx = quantize(np.array([np.imag(fhat_trunc[idx])]), step)[0]
        indices_list.extend([re_idx, im_idx])

    indices = np.array(indices_list, dtype=np.int64)

    bits, codebook = None, None
    if use_huffman and len(indices) > 0:
        bits, codebook = huffman_encode(indices)

    return CompressedSignal(
        indices=indices, kept_modes=kept, quant_step=base_step,
        N=N, huffman_bits=bits, codebook=codebook
    )


# ========================================================================
#  IMPROVEMENT 3: DELTA ENCODING FOR TIME SERIES
# ========================================================================

def compress_delta(f_prev: np.ndarray, f_curr: np.ndarray,
                    M: int, quant_step: float = 0.01) -> CompressedSignal:
    """Compress difference between consecutive signals.
    For time series: f(t+1) ≈ f(t), so delta = f(t+1) - f(t) is small."""
    delta = f_curr - f_prev
    return compress(delta, M=M, quant_step=quant_step)


def decompress_delta(f_prev: np.ndarray, cs: CompressedSignal) -> np.ndarray:
    """Reconstruct from previous signal + compressed delta."""
    delta_recon = decompress(cs)
    return f_prev + delta_recon


# ========================================================================
#  IMPROVEMENT 4: RUN-LENGTH ENCODING AFTER TRUNCATION
# ========================================================================

def rle_encode(data: np.ndarray) -> list[tuple[int, int]]:
    """Run-length encode: (value, count) pairs.
    Especially effective after truncation (many zeros)."""
    if len(data) == 0:
        return []
    runs = []
    current = int(data[0])
    count = 1
    for i in range(1, len(data)):
        if int(data[i]) == current:
            count += 1
        else:
            runs.append((current, count))
            current = int(data[i])
            count = 1
    runs.append((current, count))
    return runs


def rle_decode(runs: list[tuple[int, int]]) -> np.ndarray:
    """Decode run-length encoded data."""
    result = []
    for value, count in runs:
        result.extend([value] * count)
    return np.array(result, dtype=np.int64)


def rle_compressed_size(runs: list[tuple[int, int]]) -> int:
    """Estimate compressed size in bits: each run = (value_bits + count_bits)."""
    return sum(16 + max(1, int(np.log2(max(c, 1))) + 1) for _, c in runs)


# ========================================================================
#  IMPROVEMENT 5: GRAPH-AWARE COMPRESSION (GFT)
# ========================================================================

def gft_compress(f: np.ndarray, adjacency: np.ndarray, M: int,
                  quant_step: float = 0.01,
                  use_huffman: bool = True) -> CompressedSignal:
    """Graph Fourier Transform compression on arbitrary graph.
    GFT = eigenvectors of graph Laplacian L = D - A.
    f: signal on N nodes. adjacency: N×N adjacency matrix."""
    N = len(f)
    # Graph Laplacian
    degree = np.diag(np.sum(adjacency, axis=1))
    laplacian = degree - adjacency

    # Eigendecomposition (GFT basis)
    eigenvalues, eigenvectors = np.linalg.eigh(laplacian)

    # GFT: project onto eigenvectors
    fhat = eigenvectors.T @ f

    # Truncate top M by magnitude
    sorted_idx = np.argsort(np.abs(fhat))[::-1][:M]
    fhat_trunc = np.zeros(N)
    fhat_trunc[sorted_idx] = fhat[sorted_idx]

    # Quantize
    indices = quantize(fhat_trunc[sorted_idx], quant_step)

    bits, codebook = None, None
    if use_huffman and len(indices) > 0:
        bits, codebook = huffman_encode(indices)

    return CompressedSignal(
        indices=indices, kept_modes=sorted_idx, quant_step=quant_step,
        N=N, huffman_bits=bits, codebook=codebook
    )


def gft_decompress(cs: CompressedSignal,
                     adjacency: np.ndarray) -> np.ndarray:
    """Reconstruct from GFT-compressed signal."""
    N = cs.N
    degree = np.diag(np.sum(adjacency, axis=1))
    laplacian = degree - adjacency
    _, eigenvectors = np.linalg.eigh(laplacian)

    if cs.huffman_bits and cs.codebook:
        decoded = np.array(huffman_decode(cs.huffman_bits, cs.codebook))
        values = dequantize(decoded, cs.quant_step)
    else:
        values = dequantize(cs.indices, cs.quant_step)

    fhat = np.zeros(N)
    fhat[cs.kept_modes[:len(values)]] = values
    return eigenvectors @ fhat


def make_knn_graph(points: np.ndarray, k: int = 5) -> np.ndarray:
    """Build k-nearest-neighbor graph from point cloud.
    Returns symmetric adjacency matrix."""
    from scipy.spatial.distance import cdist
    N = len(points)
    if points.ndim == 1:
        points = points.reshape(-1, 1)
    dists = cdist(points, points)
    adj = np.zeros((N, N))
    for i in range(N):
        neighbors = np.argsort(dists[i])[1:k+1]
        adj[i, neighbors] = 1
        adj[neighbors, i] = 1
    return adj


def make_grid_graph(shape: tuple[int, ...]) -> np.ndarray:
    """Build grid graph adjacency matrix.
    shape = (H, W) for 2D, (H, W, D) for 3D."""
    N = int(np.prod(shape))
    adj = np.zeros((N, N))
    ndim = len(shape)
    coords = np.array(np.unravel_index(range(N), shape)).T
    for i in range(N):
        for d in range(ndim):
            for delta in [-1, 1]:
                neighbor = coords[i].copy()
                neighbor[d] += delta
                if 0 <= neighbor[d] < shape[d]:
                    j = int(np.ravel_multi_index(neighbor, shape))
                    adj[i, j] = 1
    return adj
