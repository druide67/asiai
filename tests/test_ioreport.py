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

    def test_defaults_include_energy_and_dcs(self):
        r = IOReportReading()
        assert r.dcs_watts == 0.0
        # No rail read → no package figure. 0.0 here used to mean "idle" AND
        # "unknown" at once; the empty default now says unknown, on purpose.
        assert r.soc_watts is None
        assert r.soc_joules is None
        assert r.rails_present == frozenset()
        assert r.gpu_joules == 0.0
        assert r.dcs_joules == 0.0

    def test_soc_watts_includes_dcs(self):
        # soc_watts = gpu+cpu+ane+dram+dcs; total_watts stays DCS-free (legacy).
        r = IOReportReading(
            gpu_watts=12.5,
            cpu_watts=4.3,
            ane_watts=0.0,
            dram_watts=2.1,
            dcs_watts=2.2,
            rails_present=frozenset({"gpu", "cpu", "ane", "dram", "dcs"}),
        )
        assert r.total_watts == pytest.approx(18.9, abs=0.01)
        assert r.soc_watts == pytest.approx(21.1, abs=0.01)

    def test_soc_joules_sums_all_rails(self):
        r = IOReportReading(
            gpu_joules=10.0,
            cpu_joules=5.0,
            ane_joules=0.0,
            dram_joules=2.0,
            dcs_joules=3.0,
            rails_present=frozenset({"gpu", "cpu", "ane", "dram", "dcs"}),
        )
        assert r.soc_joules == pytest.approx(20.0, abs=0.01)


# ── _reading_from_channels: rails present vs absent (the seam) ────────
#
# Why these exist (2026-09-02): _read_delta initialised every rail to 0.0 and
# silently skipped unknown channel names and unknown units. On a chip where a
# rail is named differently, soc_watts came out as the SUM OF THE OTHER RAILS —
# strictly positive, so it passed every ``if soc_watts > 0`` guard downstream
# and an under-counted J/token would have been published with no signal at all.
# A rail that was not read must be ABSENT (rails_present), and a package figure
# that misses a required rail must be None — never a smaller number.


def _ch(name, unit, raw):
    return (name, unit, raw)


FIVE_RAILS = [
    _ch("CPU Energy", "mJ", 4000),
    _ch("GPU", "mJ", 20000),
    _ch("ANE", "mJ", 0),
    _ch("DRAM", "mJ", 1000),
    _ch("DCS", "mJ", 500),
]


class TestReadingFromChannels:
    def test_nominal_five_rails(self):
        r = IOReportSampler._reading_from_channels(FIVE_RAILS, interval=2.0)
        assert r.gpu_watts == pytest.approx(10.0)
        assert r.cpu_watts == pytest.approx(2.0)
        assert r.dram_watts == pytest.approx(0.5)
        assert r.dcs_watts == pytest.approx(0.25)
        assert r.rails_present == frozenset({"gpu", "cpu", "ane", "dram", "dcs"})
        assert r.soc_watts == pytest.approx(12.75)
        assert r.soc_joules == pytest.approx(25.5)

    def test_missing_gpu_rail_marks_rail_absent_not_zero(self):
        # No channel named GPU at all (renamed on this chip, say).
        chans = [c for c in FIVE_RAILS if c[0] not in ("GPU", "GPU Energy")]
        r = IOReportSampler._reading_from_channels(chans, interval=2.0)
        assert "gpu" not in r.rails_present
        # The package figure must refuse, not shrink to cpu+dram+dcs.
        assert r.soc_watts is None
        assert r.soc_joules is None

    def test_unknown_unit_on_required_rail_marks_absent(self):
        chans = [c for c in FIVE_RAILS if c[0] != "GPU"] + [_ch("GPU", "kWh", 3)]
        r = IOReportSampler._reading_from_channels(chans, interval=2.0)
        assert "gpu" not in r.rails_present
        assert r.soc_watts is None

    def test_none_unit_label_marks_absent(self):
        # A failed CFString conversion yields None for the unit.
        chans = [c for c in FIVE_RAILS if c[0] != "DRAM"] + [_ch("DRAM", None, 1000)]
        r = IOReportSampler._reading_from_channels(chans, interval=2.0)
        assert "dram" not in r.rails_present
        assert r.soc_watts is None

    def test_zero_energy_rail_is_still_present(self):
        # ANE at 0 J is a READ rail (it exists, it idles) — not an absent one.
        r = IOReportSampler._reading_from_channels(FIVE_RAILS, interval=2.0)
        assert "ane" in r.rails_present
        assert r.ane_watts == 0.0

    def test_optional_ane_missing_does_not_refuse(self):
        chans = [c for c in FIVE_RAILS if c[0] != "ANE"]
        r = IOReportSampler._reading_from_channels(chans, interval=2.0)
        assert "ane" not in r.rails_present
        assert r.soc_watts == pytest.approx(12.75)  # ANE is optional

    def test_gpu_nj_fallback_is_visible_in_rails(self):
        chans = [c for c in FIVE_RAILS if c[0] != "GPU"] + [_ch("GPU Energy", "nJ", 20_000_000_000)]
        r = IOReportSampler._reading_from_channels(chans, interval=2.0)
        assert r.gpu_watts == pytest.approx(10.0)
        assert "gpu_nj" in r.rails_present
        assert r.soc_watts is not None

    def test_joule_unit_is_converted(self):
        # A channel reported in plain Joules used to be dropped (rail → 0).
        chans = [c for c in FIVE_RAILS if c[0] != "GPU"] + [_ch("GPU", "J", 20)]
        r = IOReportSampler._reading_from_channels(chans, interval=2.0)
        assert r.gpu_watts == pytest.approx(10.0)
        assert "gpu" in r.rails_present

    def test_amcc_and_fab_are_read_when_exposed(self):
        # Present on M5 Max (0.39 W + 0.22 W at idle, +29 % over soc5); read as
        # optional rails so the soc5→soc7 decision can be taken on real numbers.
        chans = FIVE_RAILS + [_ch("AMCC", "mJ", 800), _ch("FAB", "mJ", 400)]
        r = IOReportSampler._reading_from_channels(chans, interval=2.0)
        assert r.amcc_watts == pytest.approx(0.4)
        assert r.fab_watts == pytest.approx(0.2)
        assert {"amcc", "fab"} <= r.rails_present
        assert r.soc_watts == pytest.approx(12.75)  # soc5 unchanged until decided
        assert r.soc7_watts == pytest.approx(13.35)


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


def _can_create_sampler() -> bool:
    """Check if IOReportSampler can actually be created (fails on CI VMs)."""
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        return False
    try:
        s = IOReportSampler()
        s.close()
        return True
    except Exception:
        return False


@pytest.mark.apple_silicon
@pytest.mark.skipif(
    not _can_create_sampler(),
    reason="IOReport not available (CI VM or non-Apple Silicon)",
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
        assert reading.dcs_watts >= 0.0
        assert reading.interval_s > 0.5
        assert reading.total_watts > 0.0
        # soc_watts adds the DCS (DRAM controller) rail on top of total_watts.
        assert reading.soc_watts >= reading.total_watts
        assert reading.soc_joules > 0.0

    def test_context_manager(self):
        """Test context manager usage."""
        import time

        with IOReportSampler() as sampler:
            time.sleep(1)
            reading = sampler.sample()
            assert reading.interval_s > 0.5
