"""Tests for the self-describing agentic/burst recording, port-based RAM
matching, and the native agentic leaderboard renderer (1.12.0)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from asiai.benchmark.agentic import AgenticRun, run_agentic_bench
from asiai.benchmark.agentic_report import (
    gate,
    load_agentic_dir,
    parse_quant,
    summarize_agentic,
)
from asiai.benchmark.quality_gates import EngineMemorySampler
from asiai.collectors.system import (
    ProcessInfo,
    collect_power_mode,
    collect_process_by_pid,
    collect_run_metadata,
    find_engine_process_by_url,
)
from asiai.display.cli_renderer import render_agentic_leaderboard


def _mock_run(stdout: str, returncode: int = 0):
    r = MagicMock()
    r.stdout = stdout
    r.returncode = returncode
    return r


# --- Workstream A: power mode + run metadata -----------------------------


class TestCollectPowerMode:
    def test_high_power(self):
        with patch("asiai.collectors.system.subprocess.run") as m:
            m.return_value = _mock_run(" powermode            2\n")
            assert collect_power_mode() == 2

    def test_normal(self):
        with patch("asiai.collectors.system.subprocess.run") as m:
            m.return_value = _mock_run(" powermode            0\n")
            assert collect_power_mode() == 0

    def test_absent_returns_none(self):
        with patch("asiai.collectors.system.subprocess.run") as m:
            m.return_value = _mock_run("Active Profiles:\n SleepDisabled  0\n")
            assert collect_power_mode() is None

    def test_error_returns_none(self):
        with patch("asiai.collectors.system.subprocess.run", side_effect=OSError):
            assert collect_power_mode() is None


class TestCollectRunMetadata:
    def _patch_collectors(self):
        mem = MagicMock()
        mem.total = 128 * 1024**3
        return patch.multiple(
            "asiai.collectors.system",
            collect_machine_info=MagicMock(return_value="Mac15,3 — Apple M5 Max"),
            collect_hw_chip=MagicMock(return_value="Apple M5 Max"),
            collect_os_version=MagicMock(return_value="26.4"),
            collect_memory=MagicMock(return_value=mem),
            collect_cpu_cores=MagicMock(return_value=16),
            collect_power_mode=MagicMock(return_value=2),
        )

    def test_full_fields(self):
        with self._patch_collectors():
            md = collect_run_metadata(engine_version="b9430", bench_mode="agentic")
        assert md["machine_model"] == "Mac15,3"
        assert md["hw_chip"] == "Apple M5 Max"
        assert md["os_version"] == "26.4"
        assert md["ram_gb"] == 128
        assert md["cpu_cores"] == 16
        assert md["powermode"] == 2
        assert md["engine_version"] == "b9430"
        assert md["bench_mode"] == "agentic"

    def test_host_omitted_by_default(self):
        with self._patch_collectors():
            md = collect_run_metadata(bench_mode="burst")
        assert "host" not in md  # hostname is identifying — opt-in only

    def test_host_included_when_requested(self):
        with self._patch_collectors():
            md = collect_run_metadata(include_host=True)
        assert "host" in md and md["host"]


# --- Workstream B: port-based RAM matcher --------------------------------


class TestProcessByPid:
    def test_parses_ps_rss(self):
        with (
            patch("asiai.collectors.system.subprocess.run") as m,
            patch("asiai.collectors.system._get_phys_footprint", return_value=0),
        ):
            m.return_value = _mock_run("llama-server 20971520\n")  # 20 GB in KB
            p = collect_process_by_pid(4321)
        assert p is not None
        assert p.resident_bytes == 20971520 * 1024
        # phys falls back to rss when libproc returns 0
        assert p.phys_footprint_bytes == 20971520 * 1024

    def test_none_pid(self):
        assert collect_process_by_pid(None) is None
        assert collect_process_by_pid(0) is None


class TestFindEngineProcessByUrl:
    def test_name_match_wins(self):
        named = ProcessInfo(name="llamacpp", resident_bytes=999)
        with patch("asiai.collectors.system.find_engine_process", return_value=named):
            p = find_engine_process_by_url("llamacpp", "http://localhost:8080")
        assert p is named

    def test_port_fallback_on_name_miss(self):
        """Versioned label misses by name; the port recovers the listener PID."""
        recovered = ProcessInfo(name="llama-server", resident_bytes=12345)
        with (
            patch("asiai.collectors.system.find_engine_process", return_value=None),
            patch("asiai.collectors.system._pid_listening_on_port", return_value=4321) as pid,
            patch(
                "asiai.collectors.system.collect_process_by_pid", return_value=recovered
            ) as bypid,
        ):
            p = find_engine_process_by_url("llamacpp-b9430", "http://localhost:8080")
        assert p is recovered
        pid.assert_called_once_with(8080)
        bypid.assert_called_once_with(4321)

    def test_no_url_no_fallback(self):
        with patch("asiai.collectors.system.find_engine_process", return_value=None):
            assert find_engine_process_by_url("llamacpp-b9430", None) is None


class TestEngineMemorySamplerPort:
    def test_enabled_by_port_without_name(self):
        s = EngineMemorySampler(None, base_url="http://localhost:8080")
        assert s._enabled is True

    def test_disabled_without_name_or_port(self):
        s = EngineMemorySampler(None, base_url=None)
        assert s._enabled is False

    def test_sample_uses_url_matcher(self):
        s = EngineMemorySampler("llamacpp-b9430", base_url="http://localhost:8080")
        proc = ProcessInfo(
            name="llama-server",
            resident_bytes=20 * 1024**3,
            phys_footprint_bytes=5 * 1024**3,
        )
        with patch("asiai.benchmark.quality_gates.find_engine_process_by_url", return_value=proc):
            s._sample_once()
        assert s.result.max_rss_mb == pytest.approx(20 * 1024, rel=0.01)


# --- Workstream A integration: agentic + burst recording -----------------


def _fake_single(**kwargs):
    return AgenticRun(
        phase=kwargs["phase_name"],
        decode_tok_s=50.0,
        ttft_ms=100,
        completion_tokens=400,
        max_tokens_requested=400,
        engine_rss_mb=20000.0,
    )


def test_agentic_recording_v4_and_metadata(tmp_path):
    fake_md = {
        "machine_model": "Mac15,3",
        "hw_chip": "Apple M5 Max",
        "os_version": "26.4",
        "ram_gb": 128,
        "cpu_cores": 16,
        "powermode": 2,
        "engine_version": "b9430",
        "bench_mode": "agentic",
    }
    with (
        patch("asiai.benchmark.agentic._do_single_run", side_effect=_fake_single),
        patch("asiai.benchmark.agentic.collect_run_metadata", return_value=fake_md) as md,
        patch("asiai.benchmark.agentic.time.sleep"),
    ):
        out = run_agentic_bench(
            base_url="http://localhost:8080",
            engine_name="llamacpp",
            model="Qwen3.6-35B.gguf",
            pause=0,
            only=["cold", "warm"],
            engine_version="b9430",
            skip_quality_gates=True,
        )

    assert out["schema_version"] == "agentic-v4"
    assert out["bench_mode"] == "agentic"
    assert out["hw_chip"] == "Apple M5 Max"
    assert out["powermode"] == 2
    assert "host" not in out
    md.assert_called_once()
    assert md.call_args.kwargs["engine_version"] == "b9430"
    assert md.call_args.kwargs["bench_mode"] == "agentic"
    fp = out["footprint"]
    assert set(fp) == {
        "engine_rss_peak_mb",
        "engine_rss_warm_mb",
        "engine_phys_footprint_peak_mb",
    }
    assert fp["engine_rss_peak_mb"] == 20000.0
    assert fp["engine_rss_warm_mb"] == 20000.0  # warm phase present


def test_repeats_without_restart_flags_cold_contamination():
    """repeats>1 with no on_repeat restart → repeats 2..N start warm; the
    result flags it instead of silently presenting them as cold."""
    with (
        patch("asiai.benchmark.agentic._do_single_run", side_effect=_fake_single),
        patch("asiai.benchmark.agentic.time.sleep"),
    ):
        out = run_agentic_bench(
            base_url="http://localhost:8080",
            engine_name="llamacpp",
            model="m.gguf",
            pause=0,
            only=["cold"],
            repeats=3,
            skip_quality_gates=True,
        )
    assert out["cold_warm_repeats"] is True


def test_repeats_with_restart_callback_stays_cold():
    """on_repeat (auto-restart) fires once per extra repeat and clears the flag."""
    seen: list[int] = []
    with (
        patch("asiai.benchmark.agentic._do_single_run", side_effect=_fake_single),
        patch("asiai.benchmark.agentic.time.sleep"),
    ):
        out = run_agentic_bench(
            base_url="http://localhost:8080",
            engine_name="llamacpp",
            model="m.gguf",
            pause=0,
            only=["cold"],
            repeats=3,
            skip_quality_gates=True,
            on_repeat=seen.append,
        )
    assert seen == [1, 2]  # called before repeats 2 and 3, not before repeat 1
    assert out["cold_warm_repeats"] is False


def test_burst_recording_v2_and_metadata():
    from asiai.benchmark.burst import run_burst

    pass_dict = {
        "latency_ms": {"p50": 100.0, "p95": 200.0},
        "wall_time_s": 1.0,
        "errors_count": 0,
        "throughput_tokens_aggregate_per_s": 500.0,
    }
    fake_md = {"hw_chip": "Apple M4 Pro", "powermode": 2, "bench_mode": "burst"}
    with (
        patch("asiai.benchmark.burst._run_one_burst_pass", return_value=dict(pass_dict)),
        patch("asiai.benchmark.burst.collect_run_metadata", return_value=fake_md) as md,
        patch("asiai.benchmark.burst.time.sleep"),
    ):
        out = run_burst(
            base_url="http://localhost:8080",
            engine="llamacpp",
            model="m.gguf",
            burst_sizes=(2,),
            engine_version="b9430",
        )
    assert out["schema_version"] == "burst-v2"
    assert out["bench_mode"] == "burst"
    assert out["hw_chip"] == "Apple M4 Pro"
    assert md.call_args.kwargs["engine_version"] == "b9430"


# --- Workstream C/D: report summarize + gates + renderer -----------------


def _sample_data():
    return {
        "schema_version": "agentic-v4",
        "engine": "llamacpp",
        "model": "Qwopus3.6-35B-A3B-v1-MTP-Q4_K_S.gguf",
        "hw_chip": "Apple M5 Max",
        "ram_gb": 128,
        "powermode": 2,
        "engine_version": "b9430",
        "bench_mode": "agentic",
        "footprint": {
            "engine_rss_peak_mb": 29000,
            "engine_rss_warm_mb": 14800,
            "engine_phys_footprint_peak_mb": 12000,
        },
        "quality_gates": {"output_validity": {"output_valid_pct": 100.0}},
        "prefix_cache_reuse": {
            "reuse_fraction": 0.8,
            "reuse_corroborated_by_ttft": True,
            "cache_source": "usage_cached",
        },
        "runs": [
            {"phase": "warm", "decode_tok_s": 123.3, "ttft_ms": 67, "engine_rss_mb": 29000},
            {"phase": "long-context", "decode_tok_s": 83.8},
        ],
    }


class TestSummarizeAgentic:
    def test_self_describing_fields(self):
        row = summarize_agentic(_sample_data(), "M5-qwopus-35b-MTP-HPM")
        assert row["machine"] == "M5"  # from hw_chip, no stem parsing
        assert row["model"] == "Qwopus-35B"
        assert row["quant"] == "Q4_K_S"
        assert row["engine"] == "llamacpp"
        assert row["engine_version"] == "b9430"
        assert row["mtp"] is True
        assert row["dec"] == 123.3
        assert row["long_ctx"] == 83.8
        assert row["valid"] == 100.0
        assert row["reuse"] == 0.8
        assert row["ram_peak_mb"] == 29000

    def test_legacy_v3_recomputes_ram_from_runs(self):
        data = _sample_data()
        del data["footprint"]
        del data["hw_chip"]
        row = summarize_agentic(data, "m4-qwen-27b-HPM")
        assert row["machine"] == "M4"  # stem fallback
        assert row["ram_peak_mb"] == 29000  # recomputed from runs[].engine_rss_mb

    def test_parse_quant(self):
        assert parse_quant("foo-Q5_K_M.gguf") == "Q5_K_M"
        assert parse_quant("model-MLX-4bit") == "MLX4"
        assert parse_quant("no-quant-here") is None


class TestGate:
    def test_clean_pass(self):
        row = summarize_agentic(_sample_data(), "x")
        verdict, causes = gate(row)
        assert verdict == "✓"
        assert causes == []

    def test_ttft_eliminates(self):
        row = summarize_agentic(_sample_data(), "x")
        row["ttft"] = 9000.0
        assert gate(row)[0] == "✗"

    def test_low_validity_eliminates(self):
        row = summarize_agentic(_sample_data(), "x")
        row["valid"] = 70.0
        assert gate(row)[0] == "✗"

    def test_reserve_on_mid_validity(self):
        row = summarize_agentic(_sample_data(), "x")
        row["valid"] = 88.0
        assert gate(row)[0] == "⚠"


class TestLoadAndRender:
    def test_load_filters_non_agentic(self, tmp_path):
        (tmp_path / "agentic.json").write_text(json.dumps(_sample_data()))
        (tmp_path / "burst.json").write_text(
            json.dumps({"schema_version": "burst-v2", "bench_mode": "burst", "runs": [{}]})
        )
        (tmp_path / "broken.json").write_text("{not json")
        rows = load_agentic_dir(tmp_path)
        assert len(rows) == 1
        assert rows[0]["model"] == "Qwopus-35B"

    def test_render_tiered_no_crash(self, capsys):
        rows = [summarize_agentic(_sample_data(), "M5-x-MTP")]
        render_agentic_leaderboard(rows, view="tiered")
        out = capsys.readouterr().out
        assert "TIER 1" in out
        assert "Qwopus-35B" in out

    def test_render_grid_no_crash(self, capsys):
        rows = [summarize_agentic(_sample_data(), "M5-x-MTP")]
        render_agentic_leaderboard(rows, view="grid")
        out = capsys.readouterr().out
        assert "b9430" in out

    def test_render_empty(self, capsys):
        render_agentic_leaderboard([], view="tiered")
        assert "No agentic-bench results" in capsys.readouterr().out
