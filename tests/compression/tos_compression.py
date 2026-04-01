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
