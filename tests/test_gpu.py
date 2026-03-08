"""Tests for GPU utilization collector (ioreg)."""

import plistlib
import subprocess
from unittest.mock import MagicMock, patch

from asiai.collectors.gpu import GpuInfo, _int, _pct, collect_gpu


class TestGpuInfo:
    """Tests for GpuInfo dataclass defaults."""

    def test_defaults(self):
        info = GpuInfo()
        assert info.utilization_pct == -1.0
        assert info.renderer_pct == -1.0
        assert info.tiler_pct == -1.0
        assert info.mem_in_use == 0
        assert info.mem_allocated == 0


class TestCollectGpu:
    """Tests for collect_gpu() with mocked ioreg."""

    def _make_plist(self, perf_stats: dict) -> bytes:
        """Build a valid plist bytes from PerformanceStatistics dict."""
        return plistlib.dumps([{"PerformanceStatistics": perf_stats}])

    @patch("asiai.collectors.gpu.subprocess.run")
    def test_full_data(self, mock_run):
        """All GPU fields populated from ioreg output."""
        plist_data = self._make_plist({
            "Device Utilization %": 42,
            "Renderer Utilization %": 38,
            "Tiler Utilization %": 15,
            "In use system memory": 2_000_000_000,
            "Allocated system memory": 4_000_000_000,
        })
        mock_run.return_value = MagicMock(
            returncode=0, stdout=plist_data
        )
        gpu = collect_gpu()
        assert gpu.utilization_pct == 42.0
        assert gpu.renderer_pct == 38.0
        assert gpu.tiler_pct == 15.0
        assert gpu.mem_in_use == 2_000_000_000
        assert gpu.mem_allocated == 4_000_000_000

    @patch("asiai.collectors.gpu.subprocess.run")
    def test_partial_data(self, mock_run):
        """Missing fields get default values."""
        plist_data = self._make_plist({
            "Device Utilization %": 10,
        })
        mock_run.return_value = MagicMock(returncode=0, stdout=plist_data)
        gpu = collect_gpu()
        assert gpu.utilization_pct == 10.0
        assert gpu.renderer_pct == -1.0
        assert gpu.tiler_pct == -1.0
        assert gpu.mem_in_use == 0
        assert gpu.mem_allocated == 0

    @patch("asiai.collectors.gpu.subprocess.run")
    def test_ioreg_failure(self, mock_run):
        """Non-zero return code gives defaults."""
        mock_run.return_value = MagicMock(returncode=1, stdout=b"")
        gpu = collect_gpu()
        assert gpu.utilization_pct == -1.0

    @patch("asiai.collectors.gpu.subprocess.run")
    def test_ioreg_timeout(self, mock_run):
        """Timeout gives defaults."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ioreg", timeout=5)
        gpu = collect_gpu()
        assert gpu.utilization_pct == -1.0

    @patch("asiai.collectors.gpu.subprocess.run")
    def test_invalid_plist(self, mock_run):
        """Invalid plist data gives defaults."""
        mock_run.return_value = MagicMock(returncode=0, stdout=b"not plist")
        gpu = collect_gpu()
        assert gpu.utilization_pct == -1.0

    @patch("asiai.collectors.gpu.subprocess.run")
    def test_empty_entries(self, mock_run):
        """Empty plist array gives defaults."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout=plistlib.dumps([])
        )
        gpu = collect_gpu()
        assert gpu.utilization_pct == -1.0

    @patch("asiai.collectors.gpu.subprocess.run")
    def test_no_perf_stats(self, mock_run):
        """Entry without PerformanceStatistics gives defaults."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout=plistlib.dumps([{"IOClass": "AGXAccelerator"}])
        )
        gpu = collect_gpu()
        assert gpu.utilization_pct == -1.0


class TestHelpers:
    """Tests for _pct and _int helpers."""

    def test_pct_none(self):
        assert _pct(None) == -1.0

    def test_pct_valid(self):
        assert _pct(42) == 42.0
        assert _pct(0.5) == 0.5

    def test_pct_invalid(self):
        assert _pct("not_a_number") == -1.0

    def test_int_valid(self):
        assert _int(100) == 100
        assert _int(3.7) == 3

    def test_int_invalid(self):
        assert _int("bad") == 0
        assert _int(None) == 0
