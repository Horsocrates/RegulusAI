"""
.gft File Format + Streaming Codec

Binary format for ToS verified compression pipeline.
Supports: single/multi-channel, graph adjacency, delta streaming.

Format: GFT1 (Graph Fourier Transform, version 1)

Layout:
  MAGIC      4B  b'GFT1'
  VERSION    1B  uint8 (currently 1)
  FLAGS      1B  bit0=huffman, bit1=graph, bit2=multichannel, bit3=delta
  N          4B  uint32 (original signal length)
  M          4B  uint32 (kept modes)
  CHANNELS   2B  uint16 (1=mono)
  QSTEP      8B  float64
  KEPT_MODES M×4B  uint32 array
  CODEBOOK   variable (symbol→code pairs)
  DATA       variable (Huffman bitstream packed to bytes)
  [GRAPH]    optional sparse edge list
"""

from __future__ import annotations
import struct
import io
import math
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

from tests.compression.tos_compression import (
    CompressedSignal, compress, decompress,
    compress_delta, decompress_delta,
    huffman_encode, huffman_decode,
    gft_compress, gft_decompress,
)


# ========================================================================
#  CONSTANTS
# ========================================================================

GFT_MAGIC = b'GFT1'
GFT_VERSION = 1

FLAG_HUFFMAN = 0x01
FLAG_GRAPH = 0x02
FLAG_MULTICHANNEL = 0x04
FLAG_DELTA = 0x08


# ========================================================================
#  BINARY HELPERS
# ========================================================================

def _bits_to_bytes(bits: str) -> bytes:
    """Pack bitstring into bytes (pad with zeros)."""
    n = len(bits)
    padded = bits + '0' * ((8 - n % 8) % 8)
    return bytes(int(padded[i:i+8], 2) for i in range(0, len(padded), 8))


def _bytes_to_bits(data: bytes, n_bits: int) -> str:
    """Unpack bytes to bitstring of exactly n_bits length."""
    all_bits = ''.join(f'{b:08b}' for b in data)
    return all_bits[:n_bits]


def _write_codebook(buf: io.BytesIO, codebook: dict):
    """Write codebook: count + (symbol, code_len, code_bytes) entries."""
    buf.write(struct.pack('<H', len(codebook)))
    for symbol, code in sorted(codebook.items()):
        code_len = len(code)
        code_bytes = _bits_to_bytes(code)
        buf.write(struct.pack('<iB', symbol, code_len))
        buf.write(code_bytes)


def _read_codebook(buf: io.BytesIO) -> dict:
    """Read codebook from buffer."""
    count = struct.unpack('<H', buf.read(2))[0]
    codebook = {}
    for _ in range(count):
        symbol, code_len = struct.unpack('<iB', buf.read(5))
        n_bytes = math.ceil(code_len / 8)
        code_bytes = buf.read(n_bytes)
        code = _bytes_to_bits(code_bytes, code_len)
        codebook[symbol] = code
    return codebook


# ========================================================================
#  SAVE / LOAD .gft FILES
# ========================================================================

def save_gft(path: str | Path, cs: CompressedSignal,
             graph: Optional[np.ndarray] = None,
             channels: Optional[list[CompressedSignal]] = None):
    """Save compressed signal to .gft binary file.

    Args:
        path: output file path
        cs: compressed signal (first/only channel)
        graph: optional adjacency matrix (stored as sparse edge list)
        channels: optional additional channels (for multi-channel)
    """
    path = Path(path)
    buf = io.BytesIO()

    # Flags
    flags = 0
    if cs.huffman_bits is not None:
        flags |= FLAG_HUFFMAN
    if graph is not None:
        flags |= FLAG_GRAPH
    num_channels = 1
    if channels:
        flags |= FLAG_MULTICHANNEL
        num_channels = 1 + len(channels)

    M = len(cs.kept_modes)

    # Header
    buf.write(GFT_MAGIC)
    buf.write(struct.pack('<BBIIHd', GFT_VERSION, flags,
                           cs.N, M, num_channels, cs.quant_step))

    # Kept modes
    for mode in cs.kept_modes:
        buf.write(struct.pack('<I', int(mode)))

    # Write channel data
    _write_channel_data(buf, cs)

    # Additional channels
    if channels:
        for ch_cs in channels:
            _write_channel_data(buf, ch_cs)

    # Graph (sparse edge list)
    if graph is not None:
        edges = list(zip(*np.nonzero(graph)))
        # Only store upper triangle to avoid duplicates
        edges = [(i, j) for i, j in edges if i < j]
        buf.write(struct.pack('<II', graph.shape[0], len(edges)))
        for i, j in edges:
            buf.write(struct.pack('<II', i, j))

    path.write_bytes(buf.getvalue())


def _write_channel_data(buf: io.BytesIO, cs: CompressedSignal):
    """Write one channel's codebook + data."""
    if cs.codebook:
        _write_codebook(buf, cs.codebook)
    else:
        buf.write(struct.pack('<H', 0))  # empty codebook

    if cs.huffman_bits:
        n_bits = len(cs.huffman_bits)
        data_bytes = _bits_to_bytes(cs.huffman_bits)
        buf.write(struct.pack('<I', n_bits))
        buf.write(data_bytes)
    else:
        # Raw indices
        buf.write(struct.pack('<I', 0))  # 0 bits = raw mode
        buf.write(struct.pack('<I', len(cs.indices)))
        for idx in cs.indices:
            buf.write(struct.pack('<q', int(idx)))


def load_gft(path: str | Path) -> tuple[CompressedSignal, Optional[np.ndarray],
                                          Optional[list[CompressedSignal]]]:
    """Load compressed signal from .gft file.

    Returns:
        (primary_cs, graph_or_None, additional_channels_or_None)
    """
    path = Path(path)
    buf = io.BytesIO(path.read_bytes())

    # Magic
    magic = buf.read(4)
    if magic != GFT_MAGIC:
        raise ValueError(f"Not a .gft file: magic={magic}")

    # Header
    version, flags, N, M, num_channels, quant_step = \
        struct.unpack('<BBIIHd', buf.read(20))

    if version != GFT_VERSION:
        raise ValueError(f"Unsupported version: {version}")

    has_huffman = bool(flags & FLAG_HUFFMAN)
    has_graph = bool(flags & FLAG_GRAPH)
    has_multi = bool(flags & FLAG_MULTICHANNEL)

    # Kept modes
    kept_modes = np.array([struct.unpack('<I', buf.read(4))[0] for _ in range(M)])

    # Read channels
    all_channels = []
    for ch in range(num_channels):
        cs = _read_channel_data(buf, N, M, quant_step, kept_modes)
        all_channels.append(cs)

    # Graph
    graph = None
    if has_graph:
        graph_n, n_edges = struct.unpack('<II', buf.read(8))
        graph = np.zeros((graph_n, graph_n))
        for _ in range(n_edges):
            i, j = struct.unpack('<II', buf.read(8))
            graph[i, j] = 1
            graph[j, i] = 1

    primary = all_channels[0]
    extra = all_channels[1:] if len(all_channels) > 1 else None

    return primary, graph, extra


def _read_channel_data(buf: io.BytesIO, N, M, quant_step,
                        kept_modes) -> CompressedSignal:
    """Read one channel's codebook + data."""
    codebook = _read_codebook(buf)
    if not codebook:
        codebook = None

    n_bits = struct.unpack('<I', buf.read(4))[0]

    if n_bits > 0:
        # Huffman mode
        n_bytes = math.ceil(n_bits / 8)
        data_bytes = buf.read(n_bytes)
        huffman_bits = _bytes_to_bits(data_bytes, n_bits)
        # Reconstruct indices from Huffman for CompressedSignal
        if codebook:
            rev = {v: k for k, v in codebook.items()}
            indices_list = []
            current = ''
            for b in huffman_bits:
                current += b
                if current in rev:
                    indices_list.append(rev[current])
                    current = ''
            indices = np.array(indices_list, dtype=np.int64)
        else:
            indices = np.array([], dtype=np.int64)
    else:
        # Raw mode
        n_indices = struct.unpack('<I', buf.read(4))[0]
        indices = np.array([struct.unpack('<q', buf.read(8))[0]
                           for _ in range(n_indices)], dtype=np.int64)
        huffman_bits = None

    return CompressedSignal(
        indices=indices, kept_modes=kept_modes, quant_step=quant_step,
        N=N, huffman_bits=huffman_bits if n_bits > 0 else None,
        codebook=codebook
    )


# ========================================================================
#  STREAMING DELTA ENCODER / DECODER
# ========================================================================

class StreamEncoder:
    """Stateful encoder for frame-by-frame compression.

    Usage:
        enc = StreamEncoder(N=256, M=32, quant_step=0.01)
        for frame in signal_frames:
            data = enc.encode_frame(frame)
            send(data)  # or write to file
    """

    def __init__(self, N: int, M: int, quant_step: float = 0.01,
                 keyframe_interval: int = 30):
        self.N = N
        self.M = M
        self.quant_step = quant_step
        self.keyframe_interval = keyframe_interval
        self.prev_frame: Optional[np.ndarray] = None
        self.frame_count = 0
        self.frame_index: list[int] = []  # byte offsets of keyframes

    def encode_frame(self, frame: np.ndarray) -> bytes:
        """Encode one frame. Returns bytes."""
        is_keyframe = (self.prev_frame is None or
                       self.frame_count % self.keyframe_interval == 0)

        if is_keyframe:
            cs = compress(frame, M=self.M, quant_step=self.quant_step)
        else:
            cs = compress_delta(self.prev_frame, frame,
                                M=self.M, quant_step=self.quant_step)

        self.prev_frame = frame.copy()
        self.frame_count += 1

        return self._serialize_frame(cs, is_keyframe)

    def _serialize_frame(self, cs: CompressedSignal, is_keyframe: bool) -> bytes:
        """Serialize single frame to bytes."""
        buf = io.BytesIO()
        # Frame header: 1 byte (keyframe flag) + 4 bytes (data length placeholder)
        buf.write(struct.pack('<B', 1 if is_keyframe else 0))

        # Kept modes (only for keyframes, delta reuses)
        if is_keyframe:
            M = len(cs.kept_modes)
            buf.write(struct.pack('<I', M))
            for mode in cs.kept_modes:
                buf.write(struct.pack('<I', int(mode)))

        # Codebook + data
        _write_channel_data(buf, cs)

        return buf.getvalue()


class StreamDecoder:
    """Stateful decoder for frame-by-frame decompression.

    Usage:
        dec = StreamDecoder(N=256)
        for data in stream:
            frame = dec.decode_frame(data)
            output(frame)
    """

    def __init__(self, N: int, quant_step: float = 0.01):
        self.N = N
        self.quant_step = quant_step
        self.prev_frame: Optional[np.ndarray] = None
        self.kept_modes: Optional[np.ndarray] = None
        self.frame_count = 0

    def decode_frame(self, data: bytes) -> np.ndarray:
        """Decode one frame from bytes."""
        buf = io.BytesIO(data)
        is_keyframe = struct.unpack('<B', buf.read(1))[0] == 1

        if is_keyframe:
            M = struct.unpack('<I', buf.read(4))[0]
            self.kept_modes = np.array([
                struct.unpack('<I', buf.read(4))[0] for _ in range(M)
            ])

        cs = _read_channel_data(buf, self.N, len(self.kept_modes),
                                 self.quant_step, self.kept_modes)

        if is_keyframe or self.prev_frame is None:
            frame = decompress(cs)
        else:
            frame = decompress_delta(self.prev_frame, cs)

        self.prev_frame = frame.copy()
        self.frame_count += 1
        return frame


# ========================================================================
#  MULTI-CHANNEL COMPRESSION
# ========================================================================

@dataclass
class MultiChannelCompressed:
    """Multi-channel compressed signal."""
    channels: list[CompressedSignal]
    shared_kept_modes: Optional[np.ndarray]
    N: int
    num_channels: int

    @property
    def total_compressed_bits(self) -> int:
        return sum(c.compressed_bits for c in self.channels)

    @property
    def total_original_bits(self) -> int:
        return self.N * 64 * self.num_channels

    @property
    def compression_ratio(self) -> float:
        return self.total_compressed_bits / self.total_original_bits


def compress_multichannel(channels: list[np.ndarray], M: int,
                           quant_step: float = 0.01,
                           shared_modes: bool = True) -> MultiChannelCompressed:
    """Compress multiple channels.

    shared_modes=True: compute DFT of all channels, take union of top M
    modes across all, then project each channel onto shared basis.
    """
    from tests.compression.tos_compression import dft_graph, truncate

    N = len(channels[0])
    num_ch = len(channels)

    if shared_modes and num_ch > 1:
        # Find shared kept modes: union of important modes across channels
        all_fhat = [dft_graph(ch) for ch in channels]
        combined_energy = sum(np.abs(fhat) ** 2 for fhat in all_fhat)
        top_modes = np.argsort(combined_energy)[::-1][:M]

        compressed = []
        for ch in channels:
            cs = compress(ch, M=M, quant_step=quant_step)
            # Override kept_modes with shared
            cs_shared = CompressedSignal(
                indices=cs.indices, kept_modes=top_modes,
                quant_step=quant_step, N=N,
                huffman_bits=cs.huffman_bits, codebook=cs.codebook
            )
            compressed.append(cs_shared)

        return MultiChannelCompressed(
            channels=compressed, shared_kept_modes=top_modes,
            N=N, num_channels=num_ch
        )
    else:
        compressed = [compress(ch, M=M, quant_step=quant_step) for ch in channels]
        return MultiChannelCompressed(
            channels=compressed, shared_kept_modes=None,
            N=N, num_channels=num_ch
        )


def decompress_multichannel(mc: MultiChannelCompressed) -> list[np.ndarray]:
    """Decompress all channels."""
    return [decompress(cs) for cs in mc.channels]


def save_gft_multichannel(path: str | Path, mc: MultiChannelCompressed,
                            graph: Optional[np.ndarray] = None):
    """Save multi-channel compressed signal to .gft file."""
    extra = mc.channels[1:] if mc.num_channels > 1 else None
    save_gft(path, mc.channels[0], graph=graph, channels=extra)


def load_gft_multichannel(path: str | Path) -> tuple[MultiChannelCompressed,
                                                       Optional[np.ndarray]]:
    """Load multi-channel from .gft file."""
    primary, graph, extra = load_gft(path)
    all_ch = [primary] + (extra or [])
    mc = MultiChannelCompressed(
        channels=all_ch,
        shared_kept_modes=primary.kept_modes if len(all_ch) > 1 else None,
        N=primary.N, num_channels=len(all_ch)
    )
    return mc, graph
