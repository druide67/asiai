"""Tests for the Prometheus exposition format formatter."""

from __future__ import annotations

from asiai.web.prometheus import _escape_label, format_prometheus


def _make_snapshot(**overrides) -> dict:
    """Create a minimal snapshot for testing."""
    base = {
        "ts": 1709700000,
        "cpu_load_1": 2.5,
        "cpu_load_5": 2.0,
        "cpu_load_15": 1.5,
        "mem_total": 68_719_476_736,
        "mem_used": 34_000_000_000,
        "mem_pressure": "normal",
        "thermal_level": "nominal",
        "thermal_speed_limit": 100,
        "engines_status": [
            {
                "name": "ollama",
                "url": "http://localhost:11434",
                "reachable": True,
                "version": "0.17.4",
                "vram_total": 26_000_000_000,
                "models": [
                    {
                        "name": "qwen3.5:35b-a3b",
                        "size_vram": 26_000_000_000,
                        "format": "gguf",
                        "quantization": "Q4_K_M",
                        "context_length": 32768,
                    },
                ],
            },
        ],
    }
    base.update(overrides)
    return base


class TestEscapeLabel:
    def test_plain_text(self):
        assert _escape_label("ollama") == "ollama"

    def test_quotes(self):
        assert _escape_label('model"name') == 'model\\"name'

    def test_backslash(self):
        assert _escape_label("path\\to") == "path\\\\to"

    def test_newline(self):
        assert _escape_label("line\nbreak") == "line\\nbreak"


class TestFormatPrometheus:
    def test_system_metrics_present(self):
        output = format_prometheus(_make_snapshot())
        assert "asiai_cpu_load_1m 2.5" in output
        assert "asiai_cpu_load_5m 2.0" in output
        assert "asiai_cpu_load_15m 1.5" in output
        assert "asiai_memory_used_bytes 34000000000" in output
        assert "asiai_memory_total_bytes 68719476736" in output

    def test_pressure_level_mapping(self):
        output = format_prometheus(_make_snapshot(mem_pressure="normal"))
        assert "asiai_memory_pressure_level 0" in output

        output = format_prometheus(_make_snapshot(mem_pressure="warn"))
        assert "asiai_memory_pressure_level 1" in output

        output = format_prometheus(_make_snapshot(mem_pressure="critical"))
        assert "asiai_memory_pressure_level 2" in output

    def test_thermal_speed_limit(self):
        output = format_prometheus(_make_snapshot(thermal_speed_limit=85))
        assert "asiai_thermal_speed_limit_pct 85" in output

    def test_engine_reachable(self):
        output = format_prometheus(_make_snapshot())
        assert 'asiai_engine_reachable{engine="ollama"} 1' in output

    def test_engine_unreachable(self):
        snap = _make_snapshot()
        snap["engines_status"][0]["reachable"] = False
        output = format_prometheus(snap)
        assert 'asiai_engine_reachable{engine="ollama"} 0' in output

    def test_engine_version_info(self):
        output = format_prometheus(_make_snapshot())
        assert 'asiai_engine_version_info{engine="ollama",version="0.17.4"} 1' in output

    def test_engine_models_loaded(self):
        output = format_prometheus(_make_snapshot())
        assert 'asiai_engine_models_loaded{engine="ollama"} 1' in output

    def test_model_vram(self):
        output = format_prometheus(_make_snapshot())
        assert (
            'asiai_model_vram_bytes{engine="ollama",model="qwen3.5:35b-a3b"} 26000000000' in output
        )

    def test_model_context_length(self):
        output = format_prometheus(_make_snapshot())
        assert 'asiai_model_context_length{engine="ollama",model="qwen3.5:35b-a3b"} 32768' in output

    def test_model_loaded(self):
        output = format_prometheus(_make_snapshot())
        assert 'asiai_model_loaded{engine="ollama",model="qwen3.5:35b-a3b"} 1' in output

    def test_type_annotations(self):
        output = format_prometheus(_make_snapshot())
        assert "# TYPE asiai_cpu_load_1m gauge" in output
        assert "# TYPE asiai_engine_reachable gauge" in output
        assert "# TYPE asiai_model_loaded gauge" in output

    def test_help_annotations(self):
        output = format_prometheus(_make_snapshot())
        assert "# HELP asiai_cpu_load_1m" in output
        assert "# HELP asiai_engine_reachable" in output

    def test_no_engines_status(self):
        snap = _make_snapshot()
        snap["engines_status"] = []
        output = format_prometheus(snap)
        assert "asiai_cpu_load_1m" in output
        assert "asiai_engine_reachable" not in output

    def test_with_benchmarks(self):
        benchmarks = [
            {
                "engine": "ollama",
                "model": "qwen3.5:35b-a3b",
                "tok_per_sec": 30.4,
                "ttft_ms": 250.0,
                "power_watts": 16.0,
            },
        ]
        output = format_prometheus(_make_snapshot(), benchmarks=benchmarks)
        assert 'asiai_bench_tok_per_sec{engine="ollama",model="qwen3.5:35b-a3b"} 30.4' in output
        assert 'asiai_bench_ttft_seconds{engine="ollama",model="qwen3.5:35b-a3b"} 0.25' in output
        assert 'asiai_bench_power_watts{engine="ollama",model="qwen3.5:35b-a3b"} 16.0' in output

    def test_without_benchmarks(self):
        output = format_prometheus(_make_snapshot())
        assert "asiai_bench_tok_per_sec" not in output

    def test_ends_with_newline(self):
        output = format_prometheus(_make_snapshot())
        assert output.endswith("\n")

    def test_multiple_engines(self):
        snap = _make_snapshot()
        snap["engines_status"].append(
            {
                "name": "lmstudio",
                "url": "http://localhost:1234",
                "reachable": True,
                "version": "0.4.5",
                "vram_total": 0,
                "models": [
                    {
                        "name": "qwen3.5-35b-a3b",
                        "size_vram": 0,
                        "format": "mlx",
                        "quantization": "",
                        "context_length": 65536,
                    },
                ],
            },
        )
        output = format_prometheus(snap)
        assert 'asiai_engine_reachable{engine="ollama"} 1' in output
        assert 'asiai_engine_reachable{engine="lmstudio"} 1' in output
        assert 'asiai_model_loaded{engine="lmstudio",model="qwen3.5-35b-a3b"} 1' in output
