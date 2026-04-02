"""
Integration tests for .gft file format, streaming, and multi-channel.
"""

import numpy as np
import pytest
import tempfile
from pathlib import Path

from tests.compression.tos_compression import (
    compress, decompress, mse, snr_db, make_grid_graph,
    gft_compress, gft_decompress
)
from tests.compression.gft_format import (
    save_gft, load_gft,
    StreamEncoder, StreamDecoder,
    compress_multichannel, decompress_multichannel,
    save_gft_multichannel, load_gft_multichannel,
    MultiChannelCompressed, GFT_MAGIC
)


# ========================================================================
#  FILE FORMAT TESTS
# ========================================================================

class TestGFTFormat:
    def test_basic_roundtrip(self):
        """save_gft → load_gft → decompress = original result."""
        f = np.sin(2 * np.pi * 3 * np.linspace(0, 1, 64, endpoint=False))
        cs = compress(f, M=16, quant_step=0.01)
        f_expected = decompress(cs)

        with tempfile.NamedTemporaryFile(suffix='.gft', delete=False) as tmp:
            path = tmp.name

        try:
            save_gft(path, cs)
            cs_loaded, graph, extra = load_gft(path)
            f_loaded = decompress(cs_loaded)

            assert graph is None
            assert extra is None
            assert cs_loaded.N == cs.N
            assert len(cs_loaded.kept_modes) == len(cs.kept_modes)
            assert mse(f_expected, f_loaded) < 0.01
        finally:
            Path(path).unlink(missing_ok=True)

    def test_magic_bytes(self):
        """File starts with GFT1 magic."""
        f = np.ones(32)
        cs = compress(f, M=8, quant_step=0.1)

        with tempfile.NamedTemporaryFile(suffix='.gft', delete=False) as tmp:
            path = tmp.name

        try:
            save_gft(path, cs)
            data = Path(path).read_bytes()
            assert data[:4] == GFT_MAGIC
        finally:
            Path(path).unlink(missing_ok=True)

    def test_graph_roundtrip(self):
        """Graph adjacency stored and recovered."""
        N = 16
        adj = make_grid_graph((4, 4))
        f = np.random.RandomState(42).randn(N)
        cs = gft_compress(f, adj, M=8, quant_step=0.01)

        with tempfile.NamedTemporaryFile(suffix='.gft', delete=False) as tmp:
            path = tmp.name

        try:
            save_gft(path, cs, graph=adj)
            cs_loaded, graph_loaded, _ = load_gft(path)

            assert graph_loaded is not None
            assert graph_loaded.shape == (16, 16)
            # Check edge count matches
            assert np.sum(graph_loaded) == np.sum(adj)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_file_size_smaller_than_raw(self):
        """Compressed .gft file is smaller than raw signal."""
        f = np.sin(2 * np.pi * 5 * np.linspace(0, 1, 256, endpoint=False))
        cs = compress(f, M=16, quant_step=0.01)

        with tempfile.NamedTemporaryFile(suffix='.gft', delete=False) as tmp:
            path = tmp.name

        try:
            save_gft(path, cs)
            file_size = Path(path).stat().st_size
            raw_size = len(f) * 8  # 8 bytes per float64
            assert file_size < raw_size, \
                f"File {file_size} bytes >= raw {raw_size} bytes"
        finally:
            Path(path).unlink(missing_ok=True)


# ========================================================================
#  STREAMING TESTS
# ========================================================================

class TestStreaming:
    def test_stream_encode_decode(self):
        """Stream 50 frames, decode, check quality."""
        N = 64
        M = 16
        np.random.seed(42)
        base = np.sin(2 * np.pi * 3 * np.linspace(0, 1, N, endpoint=False))

        enc = StreamEncoder(N, M, quant_step=0.01, keyframe_interval=10)
        dec = StreamDecoder(N, quant_step=0.01)

        errors = []
        for i in range(50):
            frame = base + 0.01 * i + 0.001 * np.random.randn(N)
            data = enc.encode_frame(frame)
            recon = dec.decode_frame(data)
            errors.append(mse(frame, recon))

        # Average error should be reasonable
        avg_error = np.mean(errors)
        assert avg_error < 1.0, f"Average MSE too high: {avg_error}"

    def test_keyframe_recovery(self):
        """After a keyframe, error resets."""
        N = 32
        M = 16
        enc = StreamEncoder(N, M, quant_step=0.01, keyframe_interval=5)
        dec = StreamDecoder(N, quant_step=0.01)

        frames = [np.sin(2*np.pi*3*np.linspace(0,1,N) + 0.1*i) for i in range(20)]
        keyframe_errors = []
        delta_errors = []

        for i, frame in enumerate(frames):
            data = enc.encode_frame(frame)
            recon = dec.decode_frame(data)
            err = mse(frame, recon)
            if i % 5 == 0:
                keyframe_errors.append(err)
            else:
                delta_errors.append(err)

        # All should work without NaN/inf
        assert all(np.isfinite(e) for e in keyframe_errors)
        assert all(np.isfinite(e) for e in delta_errors)

    def test_stream_frame_count(self):
        """Encoder/decoder track frame count correctly."""
        N = 16
        enc = StreamEncoder(N, M=8, quant_step=0.1)
        dec = StreamDecoder(N, quant_step=0.1)

        for i in range(10):
            data = enc.encode_frame(np.random.randn(N))
            dec.decode_frame(data)

        assert enc.frame_count == 10
        assert dec.frame_count == 10


# ========================================================================
#  MULTI-CHANNEL TESTS
# ========================================================================

class TestMultiChannel:
    def test_stereo_roundtrip(self):
        """Compress/decompress stereo signal."""
        N = 128
        t = np.linspace(0, 1, N, endpoint=False)
        left = np.sin(2 * np.pi * 5 * t)
        right = np.sin(2 * np.pi * 5 * t + 0.5)  # phase shifted

        mc = compress_multichannel([left, right], M=32, quant_step=0.001)
        recon = decompress_multichannel(mc)

        assert len(recon) == 2
        assert mse(left, recon[0]) < 0.01
        assert mse(right, recon[1]) < 0.01

    def test_shared_modes_optimization(self):
        """Shared modes should be valid for correlated channels."""
        N = 64
        t = np.linspace(0, 1, N, endpoint=False)
        ch1 = np.sin(2 * np.pi * 3 * t)
        ch2 = np.sin(2 * np.pi * 3 * t) * 0.8  # scaled version

        mc_shared = compress_multichannel([ch1, ch2], M=16, shared_modes=True)
        mc_indep = compress_multichannel([ch1, ch2], M=16, shared_modes=False)

        assert mc_shared.num_channels == 2
        assert mc_shared.shared_kept_modes is not None
        assert mc_indep.shared_kept_modes is None

    def test_multichannel_file_roundtrip(self):
        """Save/load multi-channel .gft file."""
        N = 64
        ch1 = np.sin(2 * np.pi * 5 * np.linspace(0, 1, N, endpoint=False))
        ch2 = np.cos(2 * np.pi * 5 * np.linspace(0, 1, N, endpoint=False))

        mc = compress_multichannel([ch1, ch2], M=16, quant_step=0.01)

        with tempfile.NamedTemporaryFile(suffix='.gft', delete=False) as tmp:
            path = tmp.name

        try:
            save_gft_multichannel(path, mc)
            mc_loaded, _ = load_gft_multichannel(path)

            assert mc_loaded.num_channels == 2
            recon = decompress_multichannel(mc_loaded)
            assert len(recon) == 2
        finally:
            Path(path).unlink(missing_ok=True)

    def test_three_channel_rgb(self):
        """3-channel signal (like RGB image)."""
        N = 64
        np.random.seed(42)
        channels = [np.random.rand(N) for _ in range(3)]

        mc = compress_multichannel(channels, M=16, quant_step=0.01)
        recon = decompress_multichannel(mc)

        assert len(recon) == 3
        for i in range(3):
            assert recon[i].shape == (N,)


# ========================================================================
#  FULL INTEGRATION
# ========================================================================

class TestFullIntegration:
    def test_graph_multichannel_file(self):
        """Multi-channel on grid graph → .gft file → roundtrip."""
        shape = (4, 4)
        N = 16
        adj = make_grid_graph(shape)

        # 2 channels on grid
        x, y = np.meshgrid(range(4), range(4))
        ch1 = np.sin(2 * np.pi * x / 4).flatten()
        ch2 = np.cos(2 * np.pi * y / 4).flatten()

        mc = compress_multichannel([ch1, ch2], M=8, quant_step=0.01)

        with tempfile.NamedTemporaryFile(suffix='.gft', delete=False) as tmp:
            path = tmp.name

        try:
            save_gft_multichannel(path, mc, graph=adj)
            mc_loaded, graph_loaded = load_gft_multichannel(path)

            assert mc_loaded.num_channels == 2
            assert graph_loaded is not None
            assert graph_loaded.shape == (16, 16)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_streaming_to_file(self):
        """Stream frames → save each to buffer → decode from buffer."""
        N = 32
        M = 8

        enc = StreamEncoder(N, M, quant_step=0.1, keyframe_interval=5)
        dec = StreamDecoder(N, quant_step=0.1)

        # Encode 15 frames, collect bytes
        frame_data = []
        for i in range(15):
            frame = np.sin(2 * np.pi * 2 * np.linspace(0, 1, N) + 0.1*i)
            data = enc.encode_frame(frame)
            frame_data.append(data)

        # Decode all frames from stored bytes
        for data in frame_data:
            recon = dec.decode_frame(data)
            assert recon.shape == (N,)
            assert np.all(np.isfinite(recon))

        assert dec.frame_count == 15
