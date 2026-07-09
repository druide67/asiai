"""Tests for the unified result model + markdown report renderer."""

from __future__ import annotations

import pytest

from asiai.benchmark.report_md import render_markdown
from asiai.benchmark.result_model import build_result

NOW = 1783900000


def _standard_payload() -> dict:
    return {
        "schema_version": 2,
        "asiai_version": "1.24.0",
        "timestamp": NOW,
        "machine": {"chip": "Apple M5 Max", "os_version": "26.1", "ram_gb": 128, "gpu_cores": 40},
        "benchmark": {
            "model": "qwen3.5:4b",
            "runs_per_prompt": 3,
            "prompts": ["code", "prose"],
            "context_size": 0,
            "engines": {
                "llamacpp": {
                    "median_tok_s": 62.4,
                    "runs_count": 6,
                    "ci95": [58.1, 66.7],
                    "percentiles_tok_s": {"p50": 62.0, "p90": 66.0, "p99": 68.0},
                    "median_ttft_ms": 210.0,
                    "vram_bytes": 19_100_000_000,
                    "stability": "stable",
                    "engine_version": "b9580",
                    "model_quantization": "Q4_K_M",
                    "avg_soc_watts": 41.2,
                },
                "ollama": {
                    "median_tok_s": 55.0,
                    "runs_count": 6,
                    "ci95": [51.0, 57.0],
                    "median_ttft_ms": 300.0,
                    "model_quantization": "Q4_K_M",
                },
            },
            "winner": {"name": "llamacpp", "tok_s_delta": "+13.5%"},
        },
    }


def _agentic_payload() -> dict:
    return {
        "schema_version": "agentic-v5",
        "engine": "llamacpp",
        "model": "qwen3.5:4b",
        "started_at": NOW,
        "finished_at": NOW + 300,
        "prefix_cache_reuse_verdict": "REUSED",
        "prefix_cache_reuse": {"reuse_fraction": 0.93, "cache_source": "usage"},
        "repeats": 3,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
        "phase_stats": {
            "cold": {
                "ttft_ms": {"n": 3, "median": 1800.0, "cv": 0.12},
                "decode_tok_s": {"n": 3, "median": 60.0, "cv": 0.05},
            },
            "warm": {
                "ttft_ms": {"n": 3, "median": 150.0, "cv": 0.08},
                "decode_tok_s": {"n": 3, "median": 62.0, "cv": 0.04},
            },
        },
        "footprint": {"engine_rss_peak_mb": 26100.0, "engine_rss_warm_mb": 14500.0},
        "quality_gates": {
            "early_stop": {"detected": True, "truncated_runs": [{"phase": "warm-1"}]},
            "memory_pressure": {"alerted": False, "alert_reason": ""},
            "duplicate_processes": [],
            "output_validity": {"output_valid_pct": 100.0, "min_valid_pct": 75},
        },
        "asiai_version": "1.24.0",
        "hw_chip": "Apple M5 Max",
        "os_version": "26.1",
        "ram_gb": 128,
        "powermode": 2,
        "engine_version": "b9580",
    }


def _burst_payload() -> dict:
    return {
        "schema_version": "burst-v2",
        "engine": "rapidmlx",
        "model": "qwen3.5:4b",
        "started_at": NOW,
        "burst_sizes": [10, 60],
        "max_tokens_per_call": 64,
        "streaming": True,
        "runs": 1,
        "results": {
            "10": {
                "latency_ms": {"p50": 400.0, "p95": 900.0, "p99": 1100.0, "max": 1200.0},
                "throughput_tokens_aggregate_per_s": 480.0,
                "wall_time_s": 4.2,
                "errors_count": 0,
            },
            "60": {
                "latency_ms": {"p50": 2100.0, "p95": 4500.0, "p99": 5100.0, "max": 5600.0},
                "throughput_tokens_aggregate_per_s": 610.0,
                "wall_time_s": 14.8,
                "errors_count": 2,
                "memory_pressure_swap_delta_mb": 120.0,
            },
        },
        "hw_chip": "Apple M4 Pro",
    }


def _code_payload() -> dict:
    return {
        "schema_version": "code-v3",
        "dataset_version": "ds-2",
        "engine": "llamacpp",
        "model": "qwen3.5:4b",
        "started_at": NOW,
        "suites": ["tool_call", "coding"],
        "repeats": 2,
        "code_results": {
            "tool_call": {
                "pct_clean": 90.0,
                "pct_json_valid": 95.0,
                "pct_non_truncated": 100.0,
                "pct_schema_conform": 92.0,
                "edit_turns_pct_clean": 88.0,
                "count_empty_object_bug": 1,
            },
            "coding": {"tasks": [{"task": "lru", "judge": {}, "transcript": []}]},
        },
    }


def _language_payload() -> dict:
    return {
        "engine": "llamacpp",
        "model": "m",
        "started_at": NOW,
        "language": "fr",
        "language_name": "French",
        "fully_populated": False,
        "suites": ["adherence"],
        "language_results": {
            "adherence": {
                "pct_in_language": 96.0,
                "mean_adherence_ratio": 0.97,
                "pct_non_degenerate": 100.0,
                "mean_accent_density": 0.031,
            },
            "fluency": {"skipped": "no judge configured"},
        },
    }


def _instruct_payload() -> dict:
    return {
        "engine": "llamacpp",
        "model": "m",
        "started_at": NOW,
        "scenarios": ["verifiable"],
        "instruct_results": {
            "verifiable": {
                "prompt_level_strict": 72.0,
                "prompt_level_loose": 80.0,
                "instruction_level_strict": 85.0,
                "instruction_level_loose": 90.0,
                "prompts_scored": 25,
            }
        },
    }


def _thinking_payload() -> dict:
    return {
        "engine": "llamacpp",
        "model": "m",
        "started_at": NOW,
        "load": "tool-call-stress",
        "cells": [
            {
                "config": "thinking-on",
                "pct_clean": 95.0,
                "latency_ms_mean": 900.0,
                "ctx_growth": 4200,
                "reasoning_chars_mean": 800,
            },
            {
                "config": "thinking-off",
                "pct_clean": 88.0,
                "latency_ms_mean": 400.0,
                "ctx_growth": 1200,
                "reasoning_chars_mean": 0,
            },
        ],
    }


_ALL = {
    "standard": _standard_payload,
    "agentic": _agentic_payload,
    "burst": _burst_payload,
    "code": _code_payload,
    "language": _language_payload,
    "instruct": _instruct_payload,
    "thinking-ablation": _thinking_payload,
}


class TestBuildResult:
    @pytest.mark.parametrize("bench_type", sorted(_ALL))
    def test_builds_for_every_type(self, bench_type):
        result = build_result(bench_type, _ALL[bench_type]())
        assert result.bench_type == bench_type
        assert result.subjects, f"{bench_type}: no subjects"
        assert result.raw

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError):
            build_result("nope", {})

    def test_standard_winner_and_ci(self):
        r = build_result("standard", _standard_payload())
        assert r.winner == "llamacpp"
        heroes = {s.label: s.hero for s in r.subjects}
        assert heroes["llamacpp"].ci95 == (58.1, 66.7)
        assert heroes["llamacpp"].n == 6
        assert r.conditions["quantizations"] == "Q4_K_M"

    def test_standard_no_winner_has_note(self):
        payload = _standard_payload()
        payload["benchmark"]["winner"] = None
        r = build_result("standard", payload)
        assert r.winner is None
        assert "refused" in r.winner_note

    def test_agentic_gates(self):
        r = build_result("agentic", _agentic_payload())
        by_name = {g.name: g for g in r.gates}
        assert not by_name["early_stop"].passed
        assert by_name["memory_pressure"].passed
        assert by_name["output_validity"].passed
        assert r.headline is not None and r.headline.value == 0.93
        assert r.headline.label == "reuse_fraction"

    def test_burst_gates_and_subjects(self):
        r = build_result("burst", _burst_payload())
        assert [s.label for s in r.subjects] == ["burst-10", "burst-60"]
        names = {g.name for g in r.gates}
        assert "2 errors @60" in names
        assert "no errors @10" in names
        assert "swap +120 MB @60" in names

    def test_code_judge_offline_gate(self):
        r = build_result("code", _code_payload())
        gate = next(g for g in r.gates if g.name == "coding_judge")
        assert gate.passed
        assert "judge offline" in gate.detail

    def test_language_partial_coverage_gate(self):
        r = build_result("language", _language_payload())
        cov = next(g for g in r.gates if g.name == "dataset_coverage")
        assert not cov.passed

    def test_thinking_min_headline(self):
        r = build_result("thinking-ablation", _thinking_payload())
        assert r.headline is not None and r.headline.value == 88.0


class TestRenderMarkdown:
    @pytest.mark.parametrize("bench_type", sorted(_ALL))
    def test_always_complete(self, bench_type):
        """The unbiased-by-construction invariant: every report carries
        its conditions, provenance and headline label — for every type."""
        md = render_markdown(build_result(bench_type, _ALL[bench_type]()))
        assert "## Conditions" in md
        assert "## Provenance" in md
        assert "## Results" in md
        # A headline is always labeled, never naked.
        if "**Headline" in md:
            assert "`" in md.split("**Headline", 1)[1].split("\n", 1)[0]

    def test_standard_snapshot_essentials(self):
        md = render_markdown(build_result("standard", _standard_payload()))
        assert "Winner: llamacpp" in md
        assert "CI95 58.1–66.7" in md
        assert "n=6" in md
        assert "Q4_K_M" in md
        assert "| asiai_version | 1.24.0 |" in md

    def test_n1_disclaimer(self):
        payload = _standard_payload()
        payload["benchmark"]["engines"]["llamacpp"]["runs_count"] = 1
        payload["benchmark"]["engines"]["llamacpp"]["ci95"] = [0.0, 0.0]
        md = render_markdown(build_result("standard", payload))
        assert "n=1 — no noise estimate" in md

    def test_failed_gate_visible(self):
        md = render_markdown(build_result("agentic", _agentic_payload()))
        assert "❌ `early_stop`" in md
        assert "✅ `memory_pressure`" in md

    def test_no_winner_disclosed(self):
        payload = _standard_payload()
        payload["benchmark"]["winner"] = None
        md = render_markdown(build_result("standard", payload))
        assert "No winner declared" in md

    def test_extra_body_in_conditions(self):
        md = render_markdown(build_result("agentic", _agentic_payload()))
        assert "enable_thinking" in md

    def test_language_metric_never_duplicated(self):
        # Regression (audit F3): the hero must be the same instance as the
        # first metric — "in language" appeared twice.
        md = render_markdown(build_result("language", _language_payload()))
        assert md.count("| in language") == 1

    def test_instruct_loop_search_blocks_rendered(self):
        # Regression (audit F1): loop_search_* scenarios were silently
        # absent from the report.
        payload = _instruct_payload()
        payload["instruct_results"]["loop_search_short"] = {
            "pct_stopped_cleanly": 70.0,
            "prompts_scored": 10,
        }
        md = render_markdown(build_result("instruct", payload))
        assert "loop search (short)" in md
        assert "stopped cleanly" in md

    def test_agentic_thermal_gate_rendered(self):
        # Regression (audit F4): a throttled run must never render clean.
        payload = _agentic_payload()
        payload["quality_gates"]["thermal"] = {
            "observed": True,
            "min_speed_limit": 60,
            "throttled": True,
        }
        md = render_markdown(build_result("agentic", payload))
        assert "❌ `thermal` — min speed limit 60%" in md

    def test_markdown_cells_sanitized(self):
        # Regression (audit F6): pipes/newlines in payload strings must not
        # break the table layout.
        payload = _standard_payload()
        payload["benchmark"]["model"] = "evil|model\nname"
        payload["benchmark"]["engines"]["llamacpp"]["model_quantization"] = "Q4|K"
        md = render_markdown(build_result("standard", payload))
        assert "Q4\\|K" in md  # pipe escaped in the table cell
        assert "Q4|K |" not in md  # never raw (would add a column)
        assert "evil\\|model name" in md  # newline flattened, pipe escaped
        assert md.splitlines()[0].startswith("# ")  # title stays one line

    def test_burst_ttft_and_calls_rendered(self):
        payload = _burst_payload()
        payload["results"]["10"]["ttft_ms"] = {"p50": 110.0, "p95": 450.0, "p99": 800.0}
        payload["results"]["10"]["throughput_calls_per_s"] = 2.4
        md = render_markdown(build_result("burst", payload))
        assert "p50 TTFT" in md
        assert "calls/s" in md

    def test_code_judged_success_visible(self):
        payload = _code_payload()
        payload["code_results"]["coding"]["tasks"] = [
            {"task": "lru", "judge": {"scores": {"correctness": 8}}, "transcript": []}
        ]
        md = render_markdown(build_result("code", payload))
        assert "judged 1/1 tasks" in md
