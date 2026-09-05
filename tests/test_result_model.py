"""Tests for the unified result model + markdown report renderer."""

from __future__ import annotations

import pytest

from asiai.benchmark.report_md import render_markdown
from asiai.benchmark.result_model import DOCUMENTED_GATES, build_result, display_model

NOW = 1783900000

# Slots mirroring the real bug repro: 3 slots, a DIFFERENT model per slot.
COMPARE_SLOTS = (
    ("llamacpp", "Qwen3.6-27B-UD-Q8_K_XL.gguf", 29.5),
    ("ollama", "qwen3.6:27b-instruct-q4_K_M", 67.4),
    ("mlxlm", "unsloth/Qwen3.6-27B-UD-MLX-4bit", 19.8),
)


def _compare_raw_results(slots=COMPARE_SLOTS) -> list[dict]:
    """Raw per-run results for a multi-model compare session."""
    results = []
    for engine, model, tok in slots:
        for run_index in range(3):
            for prompt_type in ("code", "reasoning"):
                results.append(
                    {
                        "ts": NOW,
                        "engine": engine,
                        "model": model,
                        "tok_per_sec": tok + run_index * 0.4,
                        "ttft_ms": 120.0,
                        "ttft_client_ms": 140.0,
                        "tokens_generated": 500,
                        "total_duration_ms": 9000.0,
                        "vram_bytes": 28_000_000_000,
                        "thermal_level": "serious" if engine == "ollama" else "nominal",
                        "thermal_speed_limit": 100,
                        "prompt_type": prompt_type,
                        "run_index": run_index,
                        "hw_chip": "Apple M5 Max",
                        "os_version": "26.5.1",
                        "ram_gb": 128,
                        "gpu_cores": 40,
                        "context_size": 0,
                        "engine_version": "1.0",
                        "model_format": "gguf",
                        "model_quantization": "Q8_0",
                    }
                )
    return results


def _compare_session_payload(errors: list[str] | None = None) -> dict:
    """Compare-session payload built through the REAL producer chain
    (raw results → build_report → build_export_payload), never a
    hand-invented fixture."""
    from asiai.benchmark.reporter import build_export_payload, build_report

    results = _compare_raw_results()
    if errors is None:
        errors = ["Memory pressure during benchmark: swap grew 900 MB"]
    return build_export_payload(results, build_report(results), errors=errors)


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


class TestDisplayModel:
    def test_single_name_passes_through(self):
        assert display_model(["qwen3.5:4b", "qwen3.5:4b", ""]) == "qwen3.5:4b"

    def test_empty_is_empty(self):
        assert display_model([]) == ""
        assert display_model(["", ""]) == ""

    def test_clean_family_prefix(self):
        assert display_model(["qwen3-4b-q4", "qwen3-4b-q8"]) == "qwen3-4b (2 models)"

    def test_prefix_equal_to_one_name_is_kept_whole(self):
        # commonprefix is "qwen3-4b" — a full name, not a partial token.
        assert display_model(["qwen3-4b", "qwen3-4b-q8"]) == "qwen3-4b (2 models)"

    def test_no_clean_prefix_falls_back_to_generic(self):
        models = [m for _e, m, _t in COMPARE_SLOTS]
        assert display_model(models) == "3-model comparison"

    def test_short_prefix_is_not_a_family(self):
        # "qwen" alone is too short to claim a family — generic label instead.
        assert display_model(["qwenA-27b", "qwenB-4b"]) == "2-model comparison"


class TestFromStandardCompare:
    """Regression: a multi-model compare session used to build a payload with
    NO benchmark.engines — empty card titled 'unknown model'."""

    def test_subjects_carry_their_own_model_and_engine(self):
        result = build_result("standard", _compare_session_payload())
        assert len(result.subjects) == 3
        by_engine = {s.engine: s for s in result.subjects}
        assert set(by_engine) == {"llamacpp", "ollama", "mlxlm"}
        for engine, model, _tok in COMPARE_SLOTS:
            assert by_engine[engine].model == model
            assert by_engine[engine].label == f"{model} / {engine}"

    def test_title_is_not_unknown(self):
        result = build_result("standard", _compare_session_payload())
        assert result.title == "Throughput — 3-model comparison"

    def test_winner_label_matches_a_subject(self):
        result = build_result("standard", _compare_session_payload())
        assert result.winner == "qwen3.6:27b-instruct-q4_K_M / ollama"
        assert result.winner in {s.label for s in result.subjects}

    def test_session_gates_surface(self):
        result = build_result("standard", _compare_session_payload())
        gates = {g.name: g for g in result.gates}
        assert gates["thermal"].passed is False  # worst level "serious"
        assert "serious" in gates["thermal"].detail
        assert gates["memory_pressure"].passed is False
        assert "swap grew 900 MB" in gates["memory_pressure"].detail

    def test_memory_gate_passes_when_run_had_no_alert(self):
        result = build_result("standard", _compare_session_payload(errors=[]))
        gates = {g.name: g for g in result.gates}
        assert gates["memory_pressure"].passed is True

    def test_engine_session_subjects_unchanged(self):
        # Non-regression: the historical same-model/N-engines payload keeps
        # the session model on every subject and engine names as labels.
        result = build_result("standard", _standard_payload())
        assert {s.label for s in result.subjects} == {"llamacpp", "ollama"}
        assert {s.model for s in result.subjects} == {"qwen3.5:4b"}
        assert result.title == "Throughput — qwen3.5:4b"
        assert result.gates == []  # no gates block in the legacy payload

    def test_markdown_report_lists_all_slots(self):
        md = render_markdown(build_result("standard", _compare_session_payload()))
        for engine, model, _tok in COMPARE_SLOTS:
            assert f"{model} / {engine}" in md


# --- gates that were computed but never surfaced --------------------------


def _gates_payload(**gates) -> dict:
    """Minimal agentic payload; `gates` overrides entries of quality_gates."""
    qg = {
        "early_stop": {"detected": False, "truncated_runs": []},
        "duplicate_processes": [],
        "other_engines_resident": [],
        "thermal": {"observed": True, "min_speed_limit": 100, "throttled": False},
        "output_validity": {"output_valid_pct": 100.0, "min_valid_pct": 80.0},
        "thinking": {
            "requested_off": True,
            "reasoning_detected": False,
            "honoured": True,
            "status": "off_honoured",
            "comparable": True,
        },
    }
    qg.update(gates)
    return {
        "engine": "mtplx",
        "model": "qwen3.6-27b",
        "prefix_cache_reuse_verdict": "yes",
        "prefix_cache_reuse": {"reuse_fraction": 0.84, "cache_source": "usage"},
        "quality_gates": qg,
        "phase_stats": {},
        "footprint": {},
        "context_depth": {
            "median": 7530,
            "min": 7528,
            "max": 7594,
            "spread_pct": 0.88,
            "n": 18,
            "short": {"median": 7530, "min": 7528, "max": 7594, "spread_pct": 0.88, "n": 18},
            "long": {"median": 55839, "min": 55839, "max": 55841, "spread_pct": 0.0, "n": 6},
        },
    }


def _find_gate(result, name):
    return next(g for g in result.gates if g.name == name)


def test_agentic_exposes_thinking_and_other_engines_as_gates():
    result = build_result("agentic", _gates_payload())
    assert _find_gate(result, "thinking").passed is True
    assert _find_gate(result, "other_engines_resident").passed is True


def test_thinking_gate_fails_on_uncontrolled_reasoning():
    """The shipped case: nothing requested, engine reasoned. ``honoured`` is
    True (vacuously) — the gate must key off ``comparable`` instead."""
    payload = _gates_payload(
        thinking={
            "requested_off": False,
            "reasoning_detected": True,
            "honoured": True,
            "status": "unrequested",
            "comparable": False,
        }
    )
    assert _find_gate(build_result("agentic", payload), "thinking").passed is False


def test_thinking_gate_falls_back_for_exports_predating_comparable():
    """Older JSON has no ``comparable`` key; the gate must derive it rather
    than default to green."""
    payload = _gates_payload(
        thinking={"requested_off": False, "reasoning_detected": True, "honoured": True}
    )
    assert _find_gate(build_result("agentic", payload), "thinking").passed is False


def test_other_engines_gate_fails_when_a_foreign_engine_is_resident():
    payload = _gates_payload(
        other_engines_resident=[{"engine": "llamacpp", "pid": "1", "command": "llama-server"}]
    )
    g = _find_gate(build_result("agentic", payload), "other_engines_resident")
    assert g.passed is False
    assert "llamacpp" in g.detail


def test_context_depth_is_reported_per_phase_group():
    cond = build_result("agentic", _gates_payload()).conditions["context_depth"]
    assert "short phases 7530 tokens" in cond
    assert "long phases 55839 tokens" in cond


def test_context_depth_falls_back_for_exports_without_groups():
    """Older JSON has no short/long split; the condition must still render."""
    payload = _gates_payload()
    payload["context_depth"] = {"median": 7530, "spread_pct": 0.88, "n": 18}
    cond = build_result("agentic", payload).conditions["context_depth"]
    assert "7530 prompt tokens" in cond


# ── energy gates on the standard result ───────────────────────────────────────


def _std_payload(engines: dict) -> dict:
    return {"benchmark": {"model": "m", "engines": engines}, "hw_chip": "M5 Max"}


def test_energy_gates_absent_when_nothing_measured():
    from asiai.benchmark.result_model import build_result

    r = build_result("standard", _std_payload({"mtplx": {"median_tok_s": 40.0}}))
    assert not [g for g in r.gates if g.name.startswith("energy_")]


def test_energy_gates_pass_when_block_present():
    from asiai.benchmark.result_model import build_result

    eng = {"median_tok_s": 40.0, "energy": {"energy_per_token_j": 0.2, "soc_watts": 10.0}}
    r = build_result("standard", _std_payload({"mtplx": eng}))
    g = {x.name: x for x in r.gates}
    assert g["energy_provenance"].passed and g["energy_thermal"].passed
    assert any(m.key == "energy_per_token_j" and m.value == 0.2 for m in r.subjects[0].metrics)


def test_energy_provenance_gate_fails_on_refusal():
    from asiai.benchmark.result_model import build_result

    eng = {
        "median_tok_s": 40.0,
        "energy_refused": "provenance: required IOReport rail missing on a run",
    }
    r = build_result("standard", _std_payload({"mtplx": eng}))
    g = {x.name: x for x in r.gates}
    assert g["energy_provenance"].passed is False
    assert g["energy_thermal"].passed is True


def test_energy_thermal_gate_fails_when_all_runs_throttled():
    from asiai.benchmark.result_model import build_result

    eng = {
        "median_tok_s": 40.0,
        "energy_refused": "thermal: all 3 measured run(s) thermally throttled",
    }
    r = build_result("standard", _std_payload({"mtplx": eng}))
    g = {x.name: x for x in r.gates}
    assert g["energy_thermal"].passed is False
    assert g["energy_provenance"].passed is True


# ── every documented gate is buildable — the test that would have caught
#    session_replay being computed, listed in FAIL_ON_GATE, and never built ────

import pytest  # noqa: E402

_AGENTIC_FULL_GATES = {
    "early_stop": {"detected": True, "truncated_runs": [{"phase": "cold"}]},
    "memory_pressure": {"alerted": True, "alert_reason": "swap"},
    "duplicate_processes": [{"pid": 1}],
    "output_validity": {"output_valid_pct": 50.0, "min_valid_pct": 90.0},
    "session_replay": {"detected": True, "replay_runs": [{"phase": "prefix-test-3"}]},
    "bank_preload": {"detected": True, "reason": "cold rep0 reused 7424 cached tokens"},
    "thermal": {"observed": True, "throttled": True, "min_speed_limit": 50},
    "thinking": {"status": "off_ignored", "comparable": False},
    "other_engines_resident": [{"engine": "ollama"}],
}


@pytest.mark.parametrize("name", sorted(DOCUMENTED_GATES["agentic"]))
def test_every_agentic_gate_name_is_buildable_and_can_fail(name):
    payload = {
        "schema_version": "agentic-v5",
        "engine": "mtplx",
        "model": "m",
        "runs": [],
        "phase_stats": {},
        "quality_gates": _AGENTIC_FULL_GATES,
    }
    r = build_result("agentic", payload)
    g = {x.name: x for x in r.gates}
    assert name in g, f"{name} is documented but build_result never emits it"
    assert g[name].passed is False, f"{name} did not FAIL on a payload built to fail it"


@pytest.mark.parametrize("name", sorted(DOCUMENTED_GATES["standard"]))
def test_every_standard_gate_name_is_buildable_and_can_fail(name):
    payload = {
        "hw_chip": "M5 Max",
        "benchmark": {
            "model": "m",
            "engines": {
                "mtplx": {
                    "median_tok_s": 40.0,
                    "energy_refused": "thermal: all 1 measured run(s) thermally throttled",
                },
                "llamacpp": {
                    "median_tok_s": 30.0,
                    "energy_refused": "provenance: required IOReport rail missing on a run",
                },
            },
        },
        "quality_gates": {
            "thermal": {
                "observed": True,
                "throttled": True,
                "min_speed_limit": 50,
                "worst_level": "serious",
            },
            "memory_pressure": {"alerted": True, "alert_reason": "swap 14 GB"},
        },
    }
    r = build_result("standard", payload)
    g = {x.name: x for x in r.gates}
    assert name in g, f"{name} is documented but build_result never emits it"
    assert g[name].passed is False, f"{name} did not FAIL on a payload built to fail it"


def test_energy_provenance_passes_when_engine_reports_no_token_usage():
    """Not measurable is not a fault: no gate fails for an engine without `usage`."""
    p = _standard_payload()
    p["benchmark"]["engines"]["llamacpp"]["energy_refused"] = (
        "not_applicable: token count is an estimate (tokens_source != usage)"
    )
    g = {x.name: x for x in build_result("standard", p).gates}
    assert g["energy_provenance"].passed is True
    assert "without token usage" in g["energy_provenance"].detail
    assert g["energy_thermal"].passed is True


def test_documented_gates_cover_every_literal_gate_the_adapters_emit():
    """DOCUMENTED_GATES must name every Gate("literal") its adapter emits, and
    nothing else — the two lists used to be maintained by hand and drifted
    (2026-09-05 review: --fail-on-gate fluency_judge refused as a typo)."""
    import inspect
    import re

    from asiai.benchmark import result_model

    src = inspect.getsource(result_model)
    for bench_type, fn in (
        ("standard", "from_standard"),
        ("agentic", "from_agentic"),
        ("language", "from_language"),
    ):
        start = src.index(f"def {fn}(")
        end = src.find("\ndef ", start + 1)
        body = src[start:end]
        emitted = set(re.findall(r'Gate\(\s*"([a-z_]+)"', body))
        assert emitted, f"{fn} emits no literal gate?"
        documented = DOCUMENTED_GATES[bench_type]
        assert emitted <= documented, (
            f"{bench_type}: emitted but undocumented: {sorted(emitted - documented)}"
        )
        assert documented <= emitted, (
            f"{bench_type}: documented but never emitted: {sorted(documented - emitted)}"
        )
