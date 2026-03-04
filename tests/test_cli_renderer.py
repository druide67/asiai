"""Tests for CLI renderer functions."""

from __future__ import annotations

import time
from dataclasses import dataclass
from unittest.mock import patch

import asiai.display.formatters as fmt
from asiai.display.cli_renderer import (
    render_analyze,
    render_bench,
    render_bench_history,
    render_compare,
    render_detect,
    render_doctor,
    render_history,
    render_regressions,
    render_snapshot,
)


@dataclass
class _Check:
    """Minimal CheckResult stand-in for tests."""

    category: str
    name: str
    status: str
    message: str
    fix: str = ""


@dataclass
class _Regression:
    """Minimal Regression stand-in for tests."""

    engine: str
    model: str
    metric: str
    current: float
    baseline: float
    pct_change: float
    severity: str


def _no_color():
    """Context manager to disable ANSI colors during tests."""
    return patch.object(fmt, "_COLOR", False)


# --- render_doctor ---


class TestRenderDoctor:
    def test_all_ok(self, capsys):
        checks = [
            _Check("system", "Apple Silicon", "ok", "Apple M1 Max"),
            _Check("engine", "Ollama", "ok", "v0.6.2"),
        ]
        with _no_color():
            render_doctor(checks)
        out = capsys.readouterr().out
        assert "Doctor" in out
        assert "Apple Silicon" in out
        assert "2 ok" in out

    def test_warn_and_fail(self, capsys):
        checks = [
            _Check("system", "RAM", "ok", "64 GB"),
            _Check("engine", "LM Studio", "warn", "not running", fix="Start LM Studio"),
            _Check("database", "Schema", "fail", "migration needed", fix="asiai doctor --fix"),
        ]
        with _no_color():
            render_doctor(checks)
        out = capsys.readouterr().out
        assert "1 ok" in out
        assert "1 warning" in out
        assert "1 failed" in out
        assert "Fix: Start LM Studio" in out
        assert "Fix: asiai doctor --fix" in out

    def test_empty_checks(self, capsys):
        with _no_color():
            render_doctor([])
        out = capsys.readouterr().out
        assert "Doctor" in out


# --- render_detect ---


class TestRenderDetect:
    def test_no_engines(self, capsys):
        with _no_color():
            render_detect([])
        out = capsys.readouterr().out
        assert "No inference engines detected" in out

    def test_single_engine(self, capsys):
        engines = [
            {
                "name": "Ollama",
                "version": "0.6.2",
                "url": "http://localhost:11434",
                "models": [],
            }
        ]
        with _no_color():
            render_detect(engines)
        out = capsys.readouterr().out
        assert "Ollama" in out
        assert "0.6.2" in out

    def test_engine_with_models(self, capsys):
        engines = [
            {
                "name": "Ollama",
                "version": "0.6.2",
                "url": "http://localhost:11434",
                "models": [
                    {"name": "gemma2:9b", "size_vram": 5_000_000_000},
                    {"name": "llama3:8b", "size_vram": 0},
                ],
            }
        ]
        with _no_color():
            render_detect(engines)
        out = capsys.readouterr().out
        assert "2 model(s)" in out
        assert "gemma2:9b" in out
        assert "llama3:8b" in out


# --- render_snapshot ---


class TestRenderSnapshot:
    def test_basic_snapshot(self, capsys):
        snap = {
            "uptime": 3700,
            "cpu_load_1": 2.5,
            "cpu_load_5": 1.8,
            "cpu_load_15": 1.2,
            "mem_total": 68719476736,
            "mem_used": 34000000000,
            "mem_pressure": "normal",
            "thermal_level": "nominal",
            "thermal_speed_limit": 100,
            "inference_engine": "ollama",
            "engine_version": "ollama/0.6.2",
            "models": [
                {"name": "gemma2:9b", "engine": "ollama", "size_vram": 5_000_000_000},
            ],
        }
        with _no_color():
            render_snapshot(snap)
        out = capsys.readouterr().out
        assert "System" in out
        assert "1h" in out
        assert "2.50" in out
        assert "Inference" in out
        assert "ollama" in out
        assert "gemma2:9b" in out

    def test_high_memory(self, capsys):
        snap = {
            "uptime": 100,
            "cpu_load_1": 0.0,
            "cpu_load_5": 0.0,
            "cpu_load_15": 0.0,
            "mem_total": 68719476736,
            "mem_used": 65000000000,  # ~94%
            "mem_pressure": "warn",
            "thermal_level": "fair",
            "thermal_speed_limit": 80,
            "inference_engine": "none",
            "engine_version": "",
            "models": [],
        }
        with _no_color():
            render_snapshot(snap)
        out = capsys.readouterr().out
        assert "95%" in out
        assert "No engine detected" in out
        assert "No models loaded" in out

    def test_no_models(self, capsys):
        snap = {
            "uptime": 0,
            "cpu_load_1": 0.0,
            "cpu_load_5": 0.0,
            "cpu_load_15": 0.0,
            "mem_total": 0,
            "mem_used": 0,
            "mem_pressure": "unknown",
            "thermal_level": "unknown",
            "thermal_speed_limit": -1,
            "inference_engine": "none",
            "engine_version": "",
            "models": [],
        }
        with _no_color():
            render_snapshot(snap)
        out = capsys.readouterr().out
        assert "No models loaded" in out


# --- render_history ---


class TestRenderHistory:
    def test_empty(self, capsys):
        with _no_color():
            render_history([], 24)
        out = capsys.readouterr().out
        assert "No data for the last 24h" in out

    def test_entries(self, capsys):
        data = [
            {
                "ts": 1709500000,
                "cpu_load_1": 1.5,
                "cpu_load_5": 1.0,
                "mem_used": 34000000000,
                "mem_pressure": "normal",
                "thermal_level": "nominal",
                "models": [{"name": "m1"}],
            },
            {
                "ts": 1709503600,
                "cpu_load_1": 2.0,
                "cpu_load_5": 1.5,
                "mem_used": 40000000000,
                "mem_pressure": "normal",
                "thermal_level": "nominal",
                "models": [],
            },
        ]
        with _no_color():
            render_history(data, 6)
        out = capsys.readouterr().out
        assert "2 entries" in out
        assert "1.50" in out


# --- render_compare ---


class TestRenderCompare:
    def test_insufficient_data(self, capsys):
        with _no_color():
            render_compare({"before": None, "after": None})
        out = capsys.readouterr().out
        assert "Insufficient data" in out

    def test_comparison(self, capsys):
        data = {
            "before": {
                "ts": 1709500000,
                "cpu_load_1": 1.0,
                "mem_used": 30000000000,
                "mem_pressure": "normal",
                "thermal_level": "nominal",
                "models": [{"name": "m1"}],
            },
            "after": {
                "ts": 1709503600,
                "cpu_load_1": 3.0,
                "mem_used": 50000000000,
                "mem_pressure": "warn",
                "thermal_level": "fair",
                "models": [{"name": "m1"}, {"name": "m2"}],
            },
        }
        with _no_color():
            render_compare(data)
        out = capsys.readouterr().out
        assert "Comparison" in out
        assert "+2.00" in out
        assert "m2" in out
        assert "Model changes" in out


# --- render_bench ---


class TestRenderBench:
    @patch("asiai.collectors.system.collect_memory")
    @patch("asiai.collectors.system.collect_machine_info")
    def test_no_results(self, mock_machine, mock_mem, capsys):
        with _no_color():
            render_bench({"model": "m", "engines": {}, "winner": None})
        out = capsys.readouterr().out
        assert "No benchmark results" in out

    @patch("asiai.collectors.system.collect_memory")
    @patch("asiai.collectors.system.collect_machine_info")
    def test_single_engine(self, mock_machine, mock_mem, capsys):
        from asiai.collectors.system import MemoryInfo

        mock_machine.return_value = "Apple M1 Max"
        mock_mem.return_value = MemoryInfo(total=68719476736, used=34000000000, pressure="normal")

        report = {
            "model": "gemma2:9b",
            "engines": {
                "ollama": {
                    "avg_tok_s": 45.0,
                    "median_tok_s": 44.5,
                    "std_dev_tok_s": 0.0,
                    "runs_count": 1,
                    "stability": "",
                    "avg_tokens_generated": 100,
                    "avg_total_duration_ms": 2200.0,
                    "avg_ttft_ms": 850.0,
                    "vram_bytes": 5_000_000_000,
                    "thermal_level": "nominal",
                    "prompt_results": [],
                },
            },
            "winner": None,
        }
        with _no_color():
            render_bench(report)
        out = capsys.readouterr().out
        assert "gemma2:9b" in out
        assert "45.0" in out
        assert "Single engine" in out
        assert "--power" in out

    @patch("asiai.collectors.system.collect_memory")
    @patch("asiai.collectors.system.collect_machine_info")
    def test_two_engines_winner(self, mock_machine, mock_mem, capsys):
        from asiai.collectors.system import MemoryInfo

        mock_machine.return_value = "Apple M1 Max"
        mock_mem.return_value = MemoryInfo(total=68719476736, used=34000000000, pressure="normal")

        report = {
            "model": "gemma2:9b",
            "engines": {
                "ollama": {
                    "avg_tok_s": 30.0,
                    "median_tok_s": 0.0,
                    "std_dev_tok_s": 0.0,
                    "runs_count": 1,
                    "stability": "",
                    "avg_tokens_generated": 100,
                    "avg_total_duration_ms": 3000.0,
                    "avg_ttft_ms": 1200.0,
                    "vram_bytes": 5_000_000_000,
                    "thermal_level": "nominal",
                    "prompt_results": [],
                },
                "lmstudio": {
                    "avg_tok_s": 70.0,
                    "median_tok_s": 0.0,
                    "std_dev_tok_s": 0.0,
                    "runs_count": 1,
                    "stability": "",
                    "avg_tokens_generated": 100,
                    "avg_total_duration_ms": 1400.0,
                    "avg_ttft_ms": 0.0,
                    "vram_bytes": 4_500_000_000,
                    "thermal_level": "nominal",
                    "prompt_results": [],
                },
            },
            "winner": {
                "name": "lmstudio",
                "tok_s_delta": "2.3x faster",
                "vram_delta": "0.5 GB less VRAM",
            },
        }
        with _no_color():
            render_bench(report)
        out = capsys.readouterr().out
        assert "Winner:" in out
        assert "lmstudio" in out
        assert "2.3x faster" in out

    @patch("asiai.collectors.system.collect_memory")
    @patch("asiai.collectors.system.collect_machine_info")
    def test_power_efficiency(self, mock_machine, mock_mem, capsys):
        from asiai.collectors.system import MemoryInfo

        mock_machine.return_value = "Apple M1 Max"
        mock_mem.return_value = MemoryInfo(total=68719476736, used=34000000000, pressure="normal")

        report = {
            "model": "m",
            "engines": {
                "ollama": {
                    "avg_tok_s": 50.0,
                    "median_tok_s": 0.0,
                    "std_dev_tok_s": 0.0,
                    "runs_count": 1,
                    "stability": "",
                    "avg_tokens_generated": 100,
                    "avg_total_duration_ms": 2000.0,
                    "avg_ttft_ms": 100.0,
                    "vram_bytes": 0,
                    "thermal_level": "nominal",
                    "prompt_results": [
                        {"power_watts": 20.0, "tok_per_sec_per_watt": 2.5},
                    ],
                },
            },
            "winner": None,
        }
        with _no_color():
            render_bench(report)
        out = capsys.readouterr().out
        assert "Power Efficiency" in out
        assert "20.0W" in out
        assert "tok/s/W" in out

    @patch("asiai.collectors.system.collect_memory")
    @patch("asiai.collectors.system.collect_machine_info")
    def test_multi_run_stddev(self, mock_machine, mock_mem, capsys):
        from asiai.collectors.system import MemoryInfo

        mock_machine.return_value = "Apple M1 Max"
        mock_mem.return_value = MemoryInfo(total=68719476736, used=34000000000, pressure="normal")

        report = {
            "model": "m",
            "engines": {
                "ollama": {
                    "avg_tok_s": 45.0,
                    "median_tok_s": 45.5,
                    "std_dev_tok_s": 1.2,
                    "runs_count": 3,
                    "stability": "stable",
                    "avg_tokens_generated": 100,
                    "avg_total_duration_ms": 2200.0,
                    "avg_ttft_ms": 100.0,
                    "vram_bytes": 0,
                    "thermal_level": "nominal",
                    "prompt_results": [],
                },
            },
            "winner": None,
        }
        with _no_color():
            render_bench(report)
        out = capsys.readouterr().out
        assert "45.5" in out  # median as primary
        assert "1.2" in out  # stddev
        assert "stable" in out

    @patch("asiai.collectors.system.collect_memory")
    @patch("asiai.collectors.system.collect_machine_info")
    def test_load_time(self, mock_machine, mock_mem, capsys):
        from asiai.collectors.system import MemoryInfo

        mock_machine.return_value = "Apple M1 Max"
        mock_mem.return_value = MemoryInfo(total=68719476736, used=34000000000, pressure="normal")

        report = {
            "model": "m",
            "engines": {
                "ollama": {
                    "avg_tok_s": 45.0,
                    "median_tok_s": 0.0,
                    "std_dev_tok_s": 0.0,
                    "runs_count": 1,
                    "stability": "",
                    "avg_tokens_generated": 100,
                    "avg_total_duration_ms": 2200.0,
                    "avg_ttft_ms": 100.0,
                    "vram_bytes": 0,
                    "thermal_level": "nominal",
                    "prompt_results": [{"load_time_ms": 3500.0}],
                },
            },
            "winner": None,
        }
        with _no_color():
            render_bench(report)
        out = capsys.readouterr().out
        assert "Model Load Time" in out
        assert "3.5s" in out


# --- render_regressions ---


class TestRenderRegressions:
    def test_empty(self, capsys):
        with _no_color():
            render_regressions([])
        out = capsys.readouterr().out
        assert out == ""

    def test_minor_tok_s(self, capsys):
        regressions = [
            _Regression(
                engine="ollama",
                model="m",
                metric="tok_per_sec",
                current=40.0,
                baseline=45.0,
                pct_change=-11.0,
                severity="minor",
            ),
        ]
        with _no_color():
            render_regressions(regressions)
        out = capsys.readouterr().out
        assert "Regression Warnings" in out
        assert "ollama" in out
        assert "11%" in out
        assert "minor" in out

    def test_major_ttft(self, capsys):
        regressions = [
            _Regression(
                engine="lmstudio",
                model="m",
                metric="ttft_ms",
                current=2000.0,
                baseline=800.0,
                pct_change=150.0,
                severity="major",
            ),
        ]
        with _no_color():
            render_regressions(regressions)
        out = capsys.readouterr().out
        assert "TTFT increased" in out
        assert "major" in out


# --- render_bench_history ---


class TestRenderBenchHistory:
    def test_empty(self, capsys):
        with _no_color():
            render_bench_history([])
        out = capsys.readouterr().out
        assert "No benchmark history" in out

    def test_rows(self, capsys):
        rows = [
            {
                "ts": 1709500000,
                "engine": "ollama",
                "model": "gemma2:9b",
                "prompt_type": "code",
                "tok_per_sec": 45.2,
                "ttft_ms": 850.0,
            },
            {
                "ts": 1709503600,
                "engine": "lmstudio",
                "model": "gemma-2-9b",
                "prompt_type": "reasoning",
                "tok_per_sec": 71.0,
                "ttft_ms": 0,
            },
        ]
        with _no_color():
            render_bench_history(rows)
        out = capsys.readouterr().out
        assert "2 entries" in out
        assert "45.2" in out
        assert "71.0" in out
        assert "N/A" in out  # ttft_ms=0 shows N/A


# --- render_analyze ---


class TestRenderAnalyze:
    def test_empty(self, capsys):
        with _no_color():
            render_analyze([], 24)
        out = capsys.readouterr().out
        assert "No data for the last 24h" in out

    def test_full_analysis(self, capsys):
        now = int(time.time())
        data = [
            {
                "ts": now - 3600,
                "cpu_load_1": 2.0,
                "cpu_load_5": 1.5,
                "mem_used": 34000000000,
                "mem_pressure": "normal",
                "thermal_level": "nominal",
                "models": [
                    {"name": "gemma2:9b", "size_vram": 5_000_000_000},
                ],
            },
            {
                "ts": now - 1800,
                "cpu_load_1": 3.0,
                "cpu_load_5": 2.0,
                "mem_used": 40000000000,
                "mem_pressure": "normal",
                "thermal_level": "nominal",
                "models": [
                    {"name": "gemma2:9b", "size_vram": 5_000_000_000},
                    {"name": "llama3:8b", "size_vram": 4_000_000_000},
                ],
            },
            {
                "ts": now - 60,
                "cpu_load_1": 1.0,
                "cpu_load_5": 1.0,
                "mem_used": 35000000000,
                "mem_pressure": "normal",
                "thermal_level": "nominal",
                "models": [
                    {"name": "gemma2:9b", "size_vram": 5_000_000_000},
                ],
            },
        ]
        with _no_color():
            render_analyze(data, 2)
        out = capsys.readouterr().out
        assert "3 data points" in out
        assert "Model presence" in out
        assert "gemma2:9b" in out
        assert "Swap events" in out
        assert "2 swap(s)" in out
        assert "VRAM" in out
        assert "System stats" in out
        assert "Current lineup" in out
