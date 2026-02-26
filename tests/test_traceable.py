"""Tests for TraceableAnalysis and trace visualization."""

from __future__ import annotations

import numpy as np
import pytest
import torch
import torch.nn as nn

from regulus.nn.interval_tensor import IntervalTensor
from regulus.nn.model import convert_model
from regulus.nn.architectures import make_mlp, make_cnn_bn, ResNetMNIST
from regulus.analysis.traceable import TraceableAnalysis, BlockReport, TraceReport


# ============================================================
# Helpers
# ============================================================

def _train_tiny_mlp():
    """Train a small MLP on random data to get meaningful BN stats."""
    model = make_mlp()
    model.train()
    X = torch.randn(200, 784)
    y = torch.randint(0, 10, (200,))
    opt = torch.optim.Adam(model.parameters(), lr=0.01)
    crit = nn.CrossEntropyLoss()
    for _ in range(5):
        opt.zero_grad()
        loss = crit(model(X), y)
        loss.backward()
        opt.step()
    model.eval()
    return model


def _train_tiny_cnn():
    """Train a small CNN on random data."""
    model = make_cnn_bn()
    model.train()
    X = torch.randn(100, 1, 28, 28)
    y = torch.randint(0, 10, (100,))
    opt = torch.optim.Adam(model.parameters(), lr=0.01)
    crit = nn.CrossEntropyLoss()
    for _ in range(3):
        opt.zero_grad()
        loss = crit(model(X), y)
        loss.backward()
        opt.step()
    model.eval()
    return model


# ============================================================
# Tests for TraceReport structure
# ============================================================

class TestTraceReportStructure:

    def test_report_has_all_fields(self):
        """TraceReport has all expected fields."""
        model = _train_tiny_mlp()
        imodel = convert_model(model)
        tracer = TraceableAnalysis(reanchor_eps=0.01)

        x = IntervalTensor.from_uncertainty(np.random.randn(784), 0.01)
        report = tracer.trace(imodel, x)

        assert hasattr(report, "reliable")
        assert hasattr(report, "predicted_class")
        assert hasattr(report, "final_margin")
        assert hasattr(report, "block_reports")
        assert hasattr(report, "critical_block")
        assert hasattr(report, "explanation")
        assert hasattr(report, "n_blocks")

    def test_block_report_fields(self):
        """BlockReport has expected fields."""
        model = _train_tiny_mlp()
        imodel = convert_model(model)
        tracer = TraceableAnalysis()

        x = IntervalTensor.from_uncertainty(np.random.randn(784), 0.01)
        report = tracer.trace(imodel, x)

        for b in report.block_reports:
            assert hasattr(b, "block_idx")
            assert hasattr(b, "margin")
            assert hasattr(b, "mean_width")
            assert hasattr(b, "is_final")


# ============================================================
# Tests for TraceableAnalysis logic
# ============================================================

class TestTraceableAnalysis:

    def test_mlp_block_count(self):
        """MLP with 3 ReLUs should produce 4 blocks
        (3 activation-terminated + 1 final Linear)."""
        model = _train_tiny_mlp()
        imodel = convert_model(model)
        tracer = TraceableAnalysis()

        x = IntervalTensor.from_uncertainty(np.random.randn(784), 0.01)
        report = tracer.trace(imodel, x)

        # make_mlp: Linear->ReLU -> Linear->ReLU -> Linear->ReLU -> Linear
        # 3 activations = 3 blocks + 1 final = 4 blocks
        assert report.n_blocks == 4

    def test_critical_block_is_argmin(self):
        """critical_block should be the argmin of margins."""
        model = _train_tiny_mlp()
        imodel = convert_model(model)
        tracer = TraceableAnalysis()

        x = IntervalTensor.from_uncertainty(np.random.randn(784), 0.01)
        report = tracer.trace(imodel, x)

        margins = [b.margin for b in report.block_reports]
        expected_critical = int(np.argmin(margins))
        assert report.critical_block == expected_critical

    def test_final_margin_matches_last_block(self):
        """final_margin should equal the last block's margin."""
        model = _train_tiny_mlp()
        imodel = convert_model(model)
        tracer = TraceableAnalysis()

        x = IntervalTensor.from_uncertainty(np.random.randn(784), 0.01)
        report = tracer.trace(imodel, x)

        assert abs(report.final_margin - report.block_reports[-1].margin) < 1e-10

    def test_last_block_is_final(self):
        """Last block should have is_final=True."""
        model = _train_tiny_mlp()
        imodel = convert_model(model)
        tracer = TraceableAnalysis()

        x = IntervalTensor.from_uncertainty(np.random.randn(784), 0.01)
        report = tracer.trace(imodel, x)

        assert report.block_reports[-1].is_final is True
        # All others should NOT be final
        for b in report.block_reports[:-1]:
            assert b.is_final is False

    def test_final_block_has_class_info(self):
        """Final block should have top_class and runner_up."""
        model = _train_tiny_mlp()
        imodel = convert_model(model)
        tracer = TraceableAnalysis()

        x = IntervalTensor.from_uncertainty(np.random.randn(784), 0.01)
        report = tracer.trace(imodel, x)

        final = report.block_reports[-1]
        assert final.top_class is not None
        assert final.runner_up is not None
        assert final.top_class != final.runner_up
        assert 0 <= final.top_class < 10
        assert 0 <= final.runner_up < 10

    def test_predicted_class_matches_final(self):
        """predicted_class should match final block's top_class."""
        model = _train_tiny_mlp()
        imodel = convert_model(model)
        tracer = TraceableAnalysis()

        x = IntervalTensor.from_uncertainty(np.random.randn(784), 0.01)
        report = tracer.trace(imodel, x)

        assert report.predicted_class == report.block_reports[-1].top_class

    def test_explanation_is_string(self):
        """Explanation should be a non-empty string."""
        model = _train_tiny_mlp()
        imodel = convert_model(model)
        tracer = TraceableAnalysis()

        x = IntervalTensor.from_uncertainty(np.random.randn(784), 0.01)
        report = tracer.trace(imodel, x)

        assert isinstance(report.explanation, str)
        assert len(report.explanation) > 10

    def test_trace_cnn(self):
        """Trace through CNN+BN with 3D intervals works correctly."""
        model = _train_tiny_cnn()
        imodel = convert_model(model)
        tracer = TraceableAnalysis()

        x = np.random.randn(1, 28, 28).astype(np.float64)
        x_int = IntervalTensor(x - 0.01, x + 0.01)
        report = tracer.trace(imodel, x_int)

        assert report.n_blocks > 0
        assert report.predicted_class >= 0
        assert report.predicted_class < 10
        assert len(report.block_reports) == report.n_blocks


# ============================================================
# Tests for visualization (no crash)
# ============================================================

class TestVisualization:

    def test_plot_trace_no_crash(self, tmp_path):
        """plot_trace should not crash."""
        from regulus.analysis.trace_visualization import plot_trace

        model = _train_tiny_mlp()
        imodel = convert_model(model)
        tracer = TraceableAnalysis()

        x = IntervalTensor.from_uncertainty(np.random.randn(784), 0.01)
        report = tracer.trace(imodel, x)

        save_path = str(tmp_path / "trace.png")
        plot_trace(report, save_path=save_path)

        import os
        assert os.path.exists(save_path)

    def test_plot_trace_heatmap_no_crash(self, tmp_path):
        """plot_trace_heatmap should not crash."""
        from regulus.analysis.trace_visualization import plot_trace_heatmap

        model = _train_tiny_mlp()
        imodel = convert_model(model)
        tracer = TraceableAnalysis()

        reports = []
        for _ in range(5):
            x = IntervalTensor.from_uncertainty(np.random.randn(784), 0.01)
            reports.append(tracer.trace(imodel, x))

        save_path = str(tmp_path / "heatmap.png")
        plot_trace_heatmap(reports, save_path=save_path)

        import os
        assert os.path.exists(save_path)
