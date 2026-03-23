"""Tests for IOReport power monitoring."""

from __future__ import annotations

import platform
from unittest.mock import patch

import pytest

from asiai.collectors.ioreport import (
    IOReportReading,
    IOReportSampler,
    ioreport_available,
)

# ── IOReportReading tests ──────────────────────────────────────────


class TestIOReportReading:
    def test_defaults(self):
        r = IOReportReading()
        assert r.gpu_watts == 0.0
        assert r.cpu_watts == 0.0
        assert r.ane_watts == 0.0
        assert r.dram_watts == 0.0
        assert r.interval_s == 0.0

    def test_total_watts(self):
        r = IOReportReading(gpu_watts=12.5, cpu_watts=4.3, ane_watts=0.0, dram_watts=2.1)
        assert r.total_watts == pytest.approx(18.9, abs=0.01)

    def test_total_watts_all_zero(self):
        r = IOReportReading()
        assert r.total_watts == 0.0


# ── Availability tests ─────────────────────────────────────────────


class TestAvailability:
    def test_unavailable_on_linux(self):
        with patch("asiai.collectors.ioreport._load_libs", side_effect=OSError("not macOS")):
            # Reset cached state
            import asiai.collectors.ioreport as mod

            mod._available = None
            assert ioreport_available() is False

    def test_available_when_libs_load(self):
        with patch("asiai.collectors.ioreport._load_libs"):
            import asiai.collectors.ioreport as mod

            mod._available = None
            assert ioreport_available() is True

    def test_cached_result(self):
        import asiai.collectors.ioreport as mod

        mod._available = True
        # Should not call _load_libs again
        assert ioreport_available() is True
        mod._available = None  # reset


# ── PowerSample extended fields ────────────────────────────────────


class TestPowerSampleExtended:
    def test_new_fields_exist(self):
        from asiai.collectors.power import PowerSample

        s = PowerSample()
        assert s.ane_watts == 0.0
        assert s.dram_watts == 0.0
        assert s.total_package_watts == 0.0

    def test_backward_compatible(self):
        from asiai.collectors.power import PowerSample

        s = PowerSample(gpu_watts=15.0, cpu_watts=4.0, source="test")
        assert s.gpu_watts == 15.0
        assert s.cpu_watts == 4.0
        assert s.source == "test"
        assert s.ane_watts == 0.0


# ── Hardware integration test ──────────────────────────────────────


@pytest.mark.skipif(
    platform.system() != "Darwin" or platform.machine() != "arm64",
    reason="Requires macOS on Apple Silicon",
)
class TestIOReportHardware:
    def test_real_sample(self):
        """Integration test: take a real IOReport sample on Apple Silicon."""
        import time

        sampler = IOReportSampler()
        time.sleep(1)
        reading = sampler.sample()
        sampler.close()

        # At idle, GPU should be >= 0 and CPU should be > 0
        assert reading.gpu_watts >= 0.0
        assert reading.cpu_watts > 0.0
        assert reading.ane_watts >= 0.0
        assert reading.dram_watts >= 0.0
        assert reading.interval_s > 0.5
        assert reading.total_watts > 0.0

    def test_context_manager(self):
        """Test context manager usage."""
        import time

        with IOReportSampler() as sampler:
            time.sleep(1)
            reading = sampler.sample()
            assert reading.interval_s > 0.5
