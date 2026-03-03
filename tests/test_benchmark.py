"""Tests for benchmark module (prompts, runner, reporter)."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

from asiai.benchmark.prompts import PROMPTS, get_prompts
from asiai.benchmark.reporter import _classify_stability, _stddev, aggregate_results
from asiai.benchmark.runner import (
    _check_model_availability,
    _model_matches,
    _resolve_model_name,
    find_common_model,
    run_benchmark,
)
from asiai.collectors.system import MemoryInfo, ThermalInfo
from asiai.engines.base import GenerateResult, InferenceEngine, ModelInfo
from asiai.storage.db import init_db, query_benchmarks, store_benchmark

# --- Prompts ---


class TestPrompts:
    def test_get_all_prompts(self):
        prompts = get_prompts()
        assert len(prompts) == 4
        names = [p.name for p in prompts]
        assert names == ["code", "tool_call", "reasoning", "long_gen"]

    def test_get_filtered_prompts(self):
        prompts = get_prompts(["code", "reasoning"])
        assert len(prompts) == 2
        assert prompts[0].name == "code"
        assert prompts[1].name == "reasoning"

    def test_get_prompts_ignores_unknown(self):
        prompts = get_prompts(["code", "nonexistent", "reasoning"])
        assert len(prompts) == 2

    def test_all_prompts_have_required_fields(self):
        for name, prompt in PROMPTS.items():
            assert prompt.name == name
            assert prompt.label
            assert prompt.prompt
            assert prompt.max_tokens > 0
            assert prompt.description


# --- Model matching ---


class TestModelMatches:
    def test_exact_match(self):
        assert _model_matches("qwen3.5:35b-a3b", "qwen3.5:35b-a3b")

    def test_latest_tag(self):
        assert _model_matches("llama3:latest", "llama3")

    def test_base_name_match(self):
        assert _model_matches("qwen3.5:35b-a3b", "qwen3.5:latest")

    def test_substring_match(self):
        assert _model_matches("qwen3.5-35b-a3b-instruct", "qwen3.5")

    def test_no_match(self):
        assert not _model_matches("llama3:8b", "qwen3.5:35b")


class TestResolveModelName:
    def test_exact_match(self):
        engine = _mock_engine(models=[ModelInfo(name="gemma2:9b")])
        assert _resolve_model_name(engine, "gemma2:9b") == "gemma2:9b"

    def test_cross_engine_name(self):
        engine = _mock_engine(models=[ModelInfo(name="gemma-2-9b")])
        assert _resolve_model_name(engine, "gemma2:9b") == "gemma-2-9b"

    def test_no_match_returns_target(self):
        engine = _mock_engine(models=[ModelInfo(name="llama3:8b")])
        assert _resolve_model_name(engine, "qwen3:32b") == "qwen3:32b"

    def test_empty_models(self):
        engine = _mock_engine(models=[])
        assert _resolve_model_name(engine, "gemma2:9b") == "gemma2:9b"


# --- Runner ---


def _mock_engine(name="ollama", models=None, generate_result=None):
    """Create a mock InferenceEngine."""
    engine = MagicMock(spec=InferenceEngine)
    engine.name = name
    engine.base_url = "http://localhost:11434"
    engine.is_reachable.return_value = True
    engine.list_running.return_value = (
        models if models is not None else [ModelInfo(name="test-model", size_vram=20_000_000_000)]
    )
    engine.generate.return_value = generate_result or GenerateResult(
        text="generated text",
        tokens_generated=100,
        tok_per_sec=45.2,
        ttft_ms=850.0,
        total_duration_ms=2200.0,
        model="test-model",
        engine=name,
    )
    return engine


class TestFindCommonModel:
    def test_explicit_filter(self):
        engine = _mock_engine()
        assert find_common_model([engine], "my-model") == "my-model"

    def test_intersection(self):
        e1 = _mock_engine(
            "ollama",
            [
                ModelInfo(name="shared-model"),
                ModelInfo(name="only-ollama"),
            ],
        )
        e2 = _mock_engine(
            "lmstudio",
            [
                ModelInfo(name="shared-model"),
                ModelInfo(name="only-lmstudio"),
            ],
        )
        assert find_common_model([e1, e2]) == "shared-model"

    def test_fallback_first_engine(self):
        e1 = _mock_engine("ollama", [ModelInfo(name="ollama-model")])
        e2 = _mock_engine("lmstudio", [ModelInfo(name="lm-model")])
        result = find_common_model([e1, e2])
        # No common model, falls back to first engine's first model (sorted)
        assert result in ("ollama-model", "lm-model")

    def test_no_models(self):
        e1 = _mock_engine("ollama", [])
        assert find_common_model([e1]) == ""

    def test_empty_engines(self):
        assert find_common_model([]) == ""


class TestCheckModelAvailability:
    def test_found_in_running(self):
        engine = _mock_engine(models=[ModelInfo(name="gemma2:9b", size_vram=20_000_000_000)])
        result = _check_model_availability(engine, "gemma2:9b")
        assert result["found"] is True
        assert result["resolved_name"] == "gemma2:9b"
        assert result["vram_bytes"] == 20_000_000_000

    def test_found_cross_engine_name(self):
        engine = _mock_engine(models=[ModelInfo(name="gemma-2-9b")])
        result = _check_model_availability(engine, "gemma2:9b")
        assert result["found"] is True
        assert result["resolved_name"] == "gemma-2-9b"

    def test_found_in_available(self):
        """Model downloaded but not loaded (Ollama)."""
        engine = _mock_engine(models=[])  # nothing loaded
        engine.list_available.return_value = [ModelInfo(name="gemma2:9b")]
        result = _check_model_availability(engine, "gemma2:9b")
        assert result["found"] is True
        assert result["vram_bytes"] == 0  # not loaded, no VRAM

    def test_not_found_with_loaded(self):
        engine = _mock_engine(models=[ModelInfo(name="llama3:8b")])
        engine.list_available.return_value = []
        result = _check_model_availability(engine, "gemma3:4b")
        assert result["found"] is False
        assert "gemma3:4b" in result["error"]
        assert "loaded: llama3:8b" in result["error"]

    def test_not_found_with_available(self):
        engine = _mock_engine(models=[])
        engine.list_available.return_value = [
            ModelInfo(name="gemma2:9b"),
            ModelInfo(name="llama3:8b"),
        ]
        result = _check_model_availability(engine, "qwen3:32b")
        assert result["found"] is False
        assert "qwen3:32b" in result["error"]
        assert "available:" in result["error"]

    def test_not_found_no_models(self):
        engine = _mock_engine(models=[])
        engine.list_available.return_value = []
        result = _check_model_availability(engine, "gemma3:4b")
        assert result["found"] is False
        assert "no models found" in result["error"]

    def test_not_found_shows_both_loaded_and_available(self):
        engine = _mock_engine(models=[ModelInfo(name="llama3:8b")])
        engine.list_available.return_value = [
            ModelInfo(name="llama3:8b"),  # also in running, should not duplicate
            ModelInfo(name="gemma2:9b"),  # only available
        ]
        result = _check_model_availability(engine, "qwen3:32b")
        assert result["found"] is False
        assert "loaded: llama3:8b" in result["error"]
        assert "available: gemma2:9b" in result["error"]


class TestRunBenchmark:
    @patch("asiai.benchmark.runner.collect_engine_processes", return_value=[])
    @patch("asiai.benchmark.runner.collect_thermal")
    @patch("asiai.benchmark.runner.collect_memory")
    def test_single_engine(self, mock_mem, mock_thermal, _mock_procs):
        mock_mem.return_value = MemoryInfo(total=68719476736, used=34000000000, pressure="normal")
        mock_thermal.return_value = ThermalInfo(level="nominal", speed_limit=100)

        engine = _mock_engine()
        run = run_benchmark([engine], "test-model", ["code"])

        assert len(run.results) == 1
        assert run.results[0]["engine"] == "ollama"
        assert run.results[0]["tok_per_sec"] == 45.2
        assert run.results[0]["model"] == "test-model"
        assert run.errors == []

    @patch("asiai.benchmark.runner.collect_engine_processes", return_value=[])
    @patch("asiai.benchmark.runner.collect_thermal")
    @patch("asiai.benchmark.runner.collect_memory")
    def test_multi_engine(self, mock_mem, mock_thermal, _mock_procs):
        mock_mem.return_value = MemoryInfo(total=68719476736, used=34000000000, pressure="normal")
        mock_thermal.return_value = ThermalInfo(level="nominal", speed_limit=100)

        e1 = _mock_engine(
            "ollama",
            generate_result=GenerateResult(
                tokens_generated=100,
                tok_per_sec=30.0,
                ttft_ms=1200.0,
                total_duration_ms=3000.0,
                model="test-model",
                engine="ollama",
            ),
        )
        e2 = _mock_engine(
            "lmstudio",
            generate_result=GenerateResult(
                tokens_generated=100,
                tok_per_sec=71.0,
                ttft_ms=0.0,
                total_duration_ms=1400.0,
                model="test-model",
                engine="lmstudio",
            ),
        )
        run = run_benchmark([e1, e2], "test-model", ["code"])

        assert len(run.results) == 2
        engines = {r["engine"] for r in run.results}
        assert engines == {"ollama", "lmstudio"}

    def test_unreachable_engine(self):
        engine = _mock_engine()
        engine.is_reachable.return_value = False

        run = run_benchmark([engine], "test-model", ["code"])
        assert len(run.results) == 0
        assert len(run.errors) == 1
        assert "not reachable" in run.errors[0]

    @patch("asiai.benchmark.runner.collect_engine_processes", return_value=[])
    @patch("asiai.benchmark.runner.collect_thermal")
    @patch("asiai.benchmark.runner.collect_memory")
    def test_generate_error(self, mock_mem, mock_thermal, _mock_procs):
        mock_mem.return_value = MemoryInfo()
        mock_thermal.return_value = ThermalInfo()

        engine = _mock_engine()
        engine.generate.return_value = GenerateResult(
            engine="ollama", model="test-model", error="model not loaded"
        )

        run = run_benchmark([engine], "test-model", ["code"])
        assert len(run.results) == 0
        assert len(run.errors) == 1
        assert "model not loaded" in run.errors[0]


class TestRunBenchmarkMultiRun:
    @patch("asiai.benchmark.runner.collect_engine_processes", return_value=[])
    @patch("asiai.benchmark.runner.collect_thermal")
    @patch("asiai.benchmark.runner.collect_memory")
    def test_runs_3_generates_3x(self, mock_mem, mock_thermal, _mock_procs):
        mock_mem.return_value = MemoryInfo(total=68719476736, used=34000000000, pressure="normal")
        mock_thermal.return_value = ThermalInfo(level="nominal", speed_limit=100)

        engine = _mock_engine()
        run = run_benchmark([engine], "test-model", ["code"], runs=3)

        assert len(run.results) == 3
        assert engine.generate.call_count == 3
        # Each result has a run_index
        indices = {r["run_index"] for r in run.results}
        assert indices == {0, 1, 2}


# --- Reporter ---


class TestReporter:
    def test_aggregate_empty(self):
        result = aggregate_results([])
        assert result["model"] == ""
        assert result["engines"] == {}
        assert result["winner"] is None

    def test_aggregate_single_engine(self):
        results = [
            {
                "engine": "ollama",
                "model": "m",
                "tok_per_sec": 30.0,
                "ttft_ms": 1200.0,
                "vram_bytes": 27_000_000_000,
                "thermal_level": "nominal",
                "prompt_type": "code",
            },
        ]
        report = aggregate_results(results)
        assert "ollama" in report["engines"]
        assert report["winner"] is None  # Single engine, no winner

    def test_aggregate_two_engines_winner(self):
        results = [
            {
                "engine": "ollama",
                "model": "m",
                "tok_per_sec": 30.0,
                "ttft_ms": 1200.0,
                "vram_bytes": 27_000_000_000,
                "thermal_level": "nominal",
                "prompt_type": "code",
            },
            {
                "engine": "lmstudio",
                "model": "m",
                "tok_per_sec": 71.0,
                "ttft_ms": 0.0,
                "vram_bytes": 24_000_000_000,
                "thermal_level": "nominal",
                "prompt_type": "code",
            },
        ]
        report = aggregate_results(results)
        assert report["winner"] is not None
        assert report["winner"]["name"] == "lmstudio"
        assert "2.4x faster" in report["winner"]["tok_s_delta"]

    def test_aggregate_multi_run_stddev(self):
        """Multi-run results should compute stddev and stability."""
        results = [
            {
                "engine": "ollama",
                "model": "m",
                "tok_per_sec": 45.0,
                "ttft_ms": 0.0,
                "vram_bytes": 0,
                "thermal_level": "",
                "prompt_type": "code",
                "run_index": 0,
            },
            {
                "engine": "ollama",
                "model": "m",
                "tok_per_sec": 47.0,
                "ttft_ms": 0.0,
                "vram_bytes": 0,
                "thermal_level": "",
                "prompt_type": "code",
                "run_index": 1,
            },
            {
                "engine": "ollama",
                "model": "m",
                "tok_per_sec": 46.0,
                "ttft_ms": 0.0,
                "vram_bytes": 0,
                "thermal_level": "",
                "prompt_type": "code",
                "run_index": 2,
            },
        ]
        report = aggregate_results(results)
        data = report["engines"]["ollama"]
        assert data["runs_count"] == 3
        assert data["std_dev_tok_s"] > 0
        assert data["stability"] == "stable"  # CV < 5%

    def test_aggregate_all_zero_tok_s(self):
        """All results with tok_per_sec=0 should not crash (no division by zero)."""
        results = [
            {
                "engine": "ollama",
                "model": "m",
                "tok_per_sec": 0.0,
                "ttft_ms": 0.0,
                "vram_bytes": 0,
                "thermal_level": "",
                "prompt_type": "code",
            },
            {
                "engine": "ollama",
                "model": "m",
                "tok_per_sec": 0.0,
                "ttft_ms": 0.0,
                "vram_bytes": 0,
                "thermal_level": "",
                "prompt_type": "reasoning",
            },
        ]
        report = aggregate_results(results)
        assert report["engines"]["ollama"]["avg_tok_s"] == 0.0
        assert report["engines"]["ollama"]["std_dev_tok_s"] == 0.0
        assert report["engines"]["ollama"]["stability"] == "stable"

    def test_aggregate_two_engines_both_zero(self):
        """Two engines with 0 tok/s should not produce a winner."""
        results = [
            {
                "engine": "a",
                "model": "m",
                "tok_per_sec": 0.0,
                "ttft_ms": 0.0,
                "vram_bytes": 0,
                "thermal_level": "",
                "prompt_type": "code",
            },
            {
                "engine": "b",
                "model": "m",
                "tok_per_sec": 0.0,
                "ttft_ms": 0.0,
                "vram_bytes": 0,
                "thermal_level": "",
                "prompt_type": "code",
            },
        ]
        report = aggregate_results(results)
        assert report["winner"] is None

    def test_aggregate_winner_vram_delta(self):
        results = [
            {
                "engine": "a",
                "model": "m",
                "tok_per_sec": 50.0,
                "ttft_ms": 0.0,
                "vram_bytes": 20_000_000_000,
                "thermal_level": "",
                "prompt_type": "code",
            },
            {
                "engine": "b",
                "model": "m",
                "tok_per_sec": 30.0,
                "ttft_ms": 0.0,
                "vram_bytes": 25_000_000_000,
                "thermal_level": "",
                "prompt_type": "code",
            },
        ]
        report = aggregate_results(results)
        assert report["winner"]["name"] == "a"
        assert "VRAM" in report["winner"]["vram_delta"]


class TestRunBenchmarkPower:
    """Tests for power=True path in run_benchmark."""

    @patch("asiai.benchmark.runner.collect_engine_processes", return_value=[])
    @patch("asiai.benchmark.runner.collect_thermal")
    @patch("asiai.benchmark.runner.collect_memory")
    @patch("asiai.collectors.power.PowerMonitor")
    def test_power_annotates_results(self, mock_power_cls, mock_mem, mock_thermal, _mock_procs):
        """power=True should annotate each result with watts and tok/s/W."""
        from asiai.collectors.power import PowerSample

        mock_mem.return_value = MemoryInfo(total=68719476736, used=34000000000, pressure="normal")
        mock_thermal.return_value = ThermalInfo(level="nominal", speed_limit=100)

        monitor = MagicMock()
        monitor.start.return_value = True
        monitor.stop.return_value = PowerSample(gpu_watts=20.0, cpu_watts=8.0, source="3 samples")
        mock_power_cls.return_value = monitor

        engine = _mock_engine(
            generate_result=GenerateResult(
                tokens_generated=100,
                tok_per_sec=50.0,
                ttft_ms=100.0,
                total_duration_ms=2000.0,
                model="test-model",
                engine="ollama",
            )
        )
        run = run_benchmark([engine], "test-model", ["code"], power=True)

        assert len(run.results) == 1
        assert run.results[0]["power_watts"] == 20.0
        # tok/s/W = 50.0 / 20.0 = 2.5
        assert run.results[0]["tok_per_sec_per_watt"] == 2.5
        monitor.start.assert_called_once()
        monitor.stop.assert_called_once()

    @patch("asiai.benchmark.runner.collect_engine_processes", return_value=[])
    @patch("asiai.benchmark.runner.collect_thermal")
    @patch("asiai.benchmark.runner.collect_memory")
    @patch("asiai.collectors.power.PowerMonitor")
    def test_power_no_sudo_adds_error(self, mock_power_cls, mock_mem, mock_thermal, _mock_procs):
        """power=True without sudo should add error and still run benchmark."""
        mock_mem.return_value = MemoryInfo(total=68719476736, used=34000000000, pressure="normal")
        mock_thermal.return_value = ThermalInfo(level="nominal", speed_limit=100)

        monitor = MagicMock()
        monitor.start.return_value = False  # No sudo
        mock_power_cls.return_value = monitor

        engine = _mock_engine()
        run = run_benchmark([engine], "test-model", ["code"], power=True)

        # Benchmark still runs, but with an error about power
        assert len(run.results) == 1
        assert any("sudo" in e for e in run.errors)
        # Results should NOT have power annotations
        assert "power_watts" not in run.results[0]

    @patch("asiai.benchmark.runner.collect_engine_processes", return_value=[])
    @patch("asiai.benchmark.runner.collect_thermal")
    @patch("asiai.benchmark.runner.collect_memory")
    @patch("asiai.collectors.power.PowerMonitor")
    def test_power_zero_watts_no_efficiency(
        self, mock_power_cls, mock_mem, mock_thermal, _mock_procs
    ):
        """If GPU reports 0W, tok_per_sec_per_watt should not be set."""
        from asiai.collectors.power import PowerSample

        mock_mem.return_value = MemoryInfo(total=68719476736, used=34000000000, pressure="normal")
        mock_thermal.return_value = ThermalInfo(level="nominal", speed_limit=100)

        monitor = MagicMock()
        monitor.start.return_value = True
        monitor.stop.return_value = PowerSample(gpu_watts=0.0, source="no samples")
        mock_power_cls.return_value = monitor

        engine = _mock_engine()
        run = run_benchmark([engine], "test-model", ["code"], power=True)

        assert run.results[0]["power_watts"] == 0.0
        # Division by zero guard: tok_per_sec_per_watt should not be set
        assert "tok_per_sec_per_watt" not in run.results[0]


class TestLoadTime:
    @patch("asiai.benchmark.runner.collect_engine_processes", return_value=[])
    @patch("asiai.benchmark.runner.collect_thermal")
    @patch("asiai.benchmark.runner.collect_memory")
    def test_load_time_stored_in_results(self, mock_mem, mock_thermal, _mock_procs):
        mock_mem.return_value = MemoryInfo(total=68719476736, used=34000000000, pressure="normal")
        mock_thermal.return_value = ThermalInfo(level="nominal", speed_limit=100)

        engine = _mock_engine()
        engine.measure_load_time.return_value = 1234.5

        run = run_benchmark([engine], "test-model", ["code"])
        assert run.results[0]["load_time_ms"] == 1234.5

    @patch("asiai.benchmark.runner.collect_engine_processes", return_value=[])
    @patch("asiai.benchmark.runner.collect_thermal")
    @patch("asiai.benchmark.runner.collect_memory")
    def test_load_time_exception_defaults_zero(self, mock_mem, mock_thermal, _mock_procs):
        """If measure_load_time() raises, result should have load_time_ms=0."""
        mock_mem.return_value = MemoryInfo(total=68719476736, used=34000000000, pressure="normal")
        mock_thermal.return_value = ThermalInfo(level="nominal", speed_limit=100)

        engine = _mock_engine()
        engine.measure_load_time.side_effect = RuntimeError("connection timeout")

        run = run_benchmark([engine], "test-model", ["code"])
        assert run.results[0]["load_time_ms"] == 0.0
        assert run.errors == []  # Should not add to errors, just log

    @patch("asiai.benchmark.runner.collect_engine_processes", return_value=[])
    @patch("asiai.benchmark.runner.collect_thermal")
    @patch("asiai.benchmark.runner.collect_memory")
    def test_load_time_default_zero(self, mock_mem, mock_thermal, _mock_procs):
        mock_mem.return_value = MemoryInfo(total=68719476736, used=34000000000, pressure="normal")
        mock_thermal.return_value = ThermalInfo(level="nominal", speed_limit=100)

        engine = _mock_engine()
        engine.measure_load_time.return_value = 0.0

        run = run_benchmark([engine], "test-model", ["code"])
        assert run.results[0]["load_time_ms"] == 0.0


class TestStddev:
    def test_stddev_known_values(self):
        # stddev of [10, 10, 10] = 0
        assert _stddev([10, 10, 10]) == 0.0

    def test_stddev_spread(self):
        # [10, 20] -> mean=15, var=25, stddev=5
        assert _stddev([10, 20]) == 5.0

    def test_stddev_single_value(self):
        assert _stddev([42.0]) == 0.0

    def test_stddev_empty(self):
        assert _stddev([]) == 0.0


class TestClassifyStability:
    def test_stable(self):
        assert _classify_stability(100.0, 2.0) == "stable"  # CV = 2%

    def test_variable(self):
        assert _classify_stability(100.0, 7.0) == "variable"  # CV = 7%

    def test_unstable(self):
        assert _classify_stability(100.0, 15.0) == "unstable"  # CV = 15%

    def test_zero_avg(self):
        assert _classify_stability(0.0, 5.0) == "stable"


# --- Storage ---


def _make_bench_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    return path


class TestBenchmarkStorage:
    def test_store_and_query(self):
        path = _make_bench_db()
        try:
            results = [
                {
                    "ts": 1000000,
                    "engine": "ollama",
                    "model": "test-model",
                    "prompt_type": "code",
                    "tokens_generated": 100,
                    "tok_per_sec": 45.2,
                    "ttft_ms": 850.0,
                    "total_duration_ms": 2200.0,
                    "vram_bytes": 20_000_000_000,
                    "mem_used": 34000000000,
                    "thermal_level": "nominal",
                    "thermal_speed_limit": 100,
                }
            ]
            store_benchmark(path, results)

            rows = query_benchmarks(path)
            assert len(rows) == 1
            assert rows[0]["engine"] == "ollama"
            assert rows[0]["tok_per_sec"] == 45.2
        finally:
            os.unlink(path)

    def test_query_filter_by_model(self):
        path = _make_bench_db()
        try:
            results = [
                {"ts": 1000000, "engine": "ollama", "model": "model-a", "prompt_type": "code"},
                {"ts": 1000000, "engine": "ollama", "model": "model-b", "prompt_type": "code"},
            ]
            store_benchmark(path, results)

            rows = query_benchmarks(path, model="model-a")
            assert len(rows) == 1
            assert rows[0]["model"] == "model-a"
        finally:
            os.unlink(path)
