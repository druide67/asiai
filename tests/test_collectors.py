"""Tests for system metrics collectors."""

from __future__ import annotations

import platform
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from asiai.collectors.system import (
    ThermalInfo,
    collect_cpu_cores,
    collect_cpu_load,
    collect_engine_processes,
    collect_memory,
    collect_thermal,
    collect_uptime,
)


def _mock_run(stdout: str, returncode: int = 0):
    """Create a mock subprocess.run result."""
    result = MagicMock()
    result.stdout = stdout
    result.returncode = returncode
    return result


class TestCpuLoad:
    def test_normal(self):
        with patch("asiai.collectors.system.subprocess.run") as mock:
            mock.return_value = _mock_run("{ 1.23 2.34 3.45 }")
            load = collect_cpu_load()

        assert load.load_1 == 1.23
        assert load.load_5 == 2.34
        assert load.load_15 == 3.45

    def test_french_locale_comma_decimal(self):
        """FR locale: sysctl vm.loadavg returns comma as decimal separator."""
        with patch("asiai.collectors.system.subprocess.run") as mock:
            mock.return_value = _mock_run("{ 44,42 12,34 8,56 }")
            load = collect_cpu_load()

        assert load.load_1 == 44.42
        assert load.load_5 == 12.34
        assert load.load_15 == 8.56

    def test_error(self):
        with patch("asiai.collectors.system.subprocess.run", side_effect=OSError):
            load = collect_cpu_load()

        assert load.load_1 == -1.0


class TestCpuCores:
    def test_normal(self):
        with patch("asiai.collectors.system.subprocess.run") as mock:
            mock.return_value = _mock_run("12")
            assert collect_cpu_cores() == 12

    def test_error(self):
        with patch("asiai.collectors.system.subprocess.run", side_effect=OSError):
            assert collect_cpu_cores() == -1


class TestMemory:
    def test_normal(self):
        sysctl_memsize = _mock_run("68719476736")  # 64 GB
        vm_stat_output = _mock_run(
            "Mach Virtual Memory Statistics: (page size of 16384 bytes)\n"
            "Pages free:                              100000.\n"
            "Pages inactive:                           50000.\n"
            "Pages speculative:                        10000.\n"
        )
        sysctl_pressure = _mock_run("1")

        call_count = 0

        def mock_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if "hw.memsize" in cmd:
                return sysctl_memsize
            if "vm_stat" in cmd:
                return vm_stat_output
            if "kern.memorystatus_vm_pressure_level" in cmd:
                return sysctl_pressure
            return _mock_run("")

        with patch("asiai.collectors.system.subprocess.run", side_effect=mock_run):
            mem = collect_memory()

        assert mem.total == 68719476736
        assert mem.used > 0
        assert mem.pressure == "normal"


class TestThermal:
    def test_notifyd_preferred_when_available(self):
        # notifyd is the live Apple-Silicon signal; it short-circuits the
        # legacy sysctl/pmset fallback (the Intel OID is dead on M-series).
        with patch(
            "asiai.collectors.system._thermal_via_notifyd",
            return_value=ThermalInfo(level="fair", speed_limit=80),
        ):
            thermal = collect_thermal()
        assert thermal.level == "fair"
        assert thermal.speed_limit == 80

    def test_nominal_via_sysctl(self):
        # Force the fallback path (notifyd unavailable, e.g. Intel/older macOS).
        with (
            patch("asiai.collectors.system._thermal_via_notifyd", return_value=None),
            patch("asiai.collectors.system.subprocess.run") as mock,
        ):
            mock.return_value = _mock_run("0")
            thermal = collect_thermal()

        assert thermal.level == "nominal"
        assert thermal.speed_limit == 100

    def test_fallback_pmset(self):
        def mock_run(cmd, **kwargs):
            if "machdep.xcpm" in cmd:
                raise subprocess.CalledProcessError(1, cmd)
            if "pmset" in cmd:
                return _mock_run("No thermal warning level has been recorded")
            return _mock_run("")

        with (
            patch("asiai.collectors.system._thermal_via_notifyd", return_value=None),
            patch("asiai.collectors.system.subprocess.run", side_effect=mock_run),
        ):
            thermal = collect_thermal()

        assert thermal.level == "nominal"

    @pytest.mark.skipif(
        platform.system() != "Darwin" or platform.machine() != "arm64",
        reason="notifyd thermal pressure channel is Apple Silicon only",
    )
    def test_notifyd_real_returns_valid_level(self):
        # Integration: the channel is live on Apple Silicon and yields a real
        # level (the whole point of Lot D — the sysctl signal was dead here).
        from asiai.collectors.system import _thermal_via_notifyd

        result = _thermal_via_notifyd()
        assert result is not None
        assert result.speed_limit >= 0
        assert result.level in {"nominal", "fair", "serious", "critical"}


class TestEngineProcesses:
    def test_french_locale_comma_decimal(self):
        """ps aux with French locale uses comma as decimal separator."""
        ps_output = (
            "USER       PID  %CPU %MEM      VSZ    RSS   TT  STAT STARTED      TIME COMMAND\n"
            "jmn      12345   3,4  1,2  1234567  65432   ??  S    10:00AM   0:01.23 ollama serve\n"
        )
        with patch("asiai.collectors.system.subprocess.run") as mock:
            mock.return_value = _mock_run(ps_output)
            procs = collect_engine_processes()

        assert len(procs) == 1
        assert procs[0].name == "ollama"
        assert procs[0].cpu_pct == 3.4
        assert procs[0].mem_pct == 1.2

    def test_english_locale_dot_decimal(self):
        """ps aux with English locale uses dot as decimal separator."""
        ps_output = (
            "USER       PID  %CPU %MEM      VSZ    RSS   TT  STAT STARTED      TIME COMMAND\n"
            "jmn      12345   3.4  1.2  1234567  65432   ??  S    10:00AM   0:01.23 ollama serve\n"
        )
        with patch("asiai.collectors.system.subprocess.run") as mock:
            mock.return_value = _mock_run(ps_output)
            procs = collect_engine_processes()

        assert len(procs) == 1
        assert procs[0].cpu_pct == 3.4
        # True RSS from the ps RSS column (KB → bytes). On a bogus PID
        # proc_pid_rusage fails, so phys_footprint_bytes falls back to the RSS.
        assert procs[0].resident_bytes == 65432 * 1024
        assert procs[0].phys_footprint_bytes == 65432 * 1024

    def test_no_engine_processes(self):
        """No engine processes found should return empty list."""
        ps_output = (
            "USER       PID  %CPU %MEM      VSZ    RSS   TT  STAT STARTED      TIME COMMAND\n"
            "jmn      12345   1.0  0.5  1234567  65432   ??  S    10:00AM   0:01.23 /usr/bin/zsh\n"
        )
        with patch("asiai.collectors.system.subprocess.run") as mock:
            mock.return_value = _mock_run(ps_output)
            procs = collect_engine_processes()

        assert procs == []

    def test_ps_failure(self):
        """ps aux failure should return empty list, not crash."""
        with patch("asiai.collectors.system.subprocess.run", side_effect=OSError("no ps")):
            procs = collect_engine_processes()
        assert procs == []


class TestUptime:
    def test_normal(self):
        with patch("asiai.collectors.system.subprocess.run") as mock:
            mock.return_value = _mock_run("{ sec = 1709000000, usec = 0 }")
            with patch("asiai.collectors.system.time.time", return_value=1709086400.0):
                uptime = collect_uptime()

        assert uptime == 86400
