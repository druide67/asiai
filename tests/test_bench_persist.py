"""Tests for bench_runs persistence (all bench types) — storage + headline."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time

from asiai.benchmark.persist import extract_headline, persist_bench_run
from asiai.storage.db import (
    get_bench_run,
    init_db,
    purge_old,
    query_bench_runs,
    store_bench_run,
    store_benchmark,
)

NOW = int(time.time())


def _make_db() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    return path


def _meta(bench_mode: str) -> dict:
    """Common collect_run_metadata block as the mode payloads carry it."""
    return {
        "asiai_version": "1.24.0",
        "machine_model": "Mac16,6",
        "hw_chip": "Apple M5 Max",
        "os_version": "26.1",
        "ram_gb": 128,
        "cpu_cores": 16,
        "powermode": 2,
        "engine_version": "b9580",
        "bench_mode": bench_mode,
    }


# ---------------------------------------------------------------------------
# Storage round-trip
# ---------------------------------------------------------------------------


class TestStoreBenchRun:
    def test_round_trip(self):
        path = _make_db()
        try:
            run_id = store_bench_run(
                path,
                {
                    "ts": NOW,
                    "finished_ts": NOW + 60,
                    "bench_type": "code",
                    "engine": "llamacpp",
                    "engine_version": "b9580",
                    "model": "qwen3.5:4b",
                    "asiai_version": "1.24.0",
                    "schema_version": "code-v3",
                    "dataset_version": "code-ds-2",
                    "hw_chip": "Apple M5 Max",
                    "ram_gb": 128,
                    "powermode": 2,
                    "score_primary": 87.5,
                    "score_label": "mean_pct_clean_deterministic",
                    "gates_failed": 0,
                    "payload": json.dumps({"hello": "world"}),
                },
            )
            assert run_id > 0

            rows = query_bench_runs(path)
            assert len(rows) == 1
            row = rows[0]
            assert row["bench_type"] == "code"
            assert row["score_primary"] == 87.5
            assert row["score_label"] == "mean_pct_clean_deterministic"
            # List view never carries the payload.
            assert "payload" not in row

            full = get_bench_run(path, run_id)
            assert full is not None
            assert json.loads(full["payload"]) == {"hello": "world"}
        finally:
            os.unlink(path)

    def test_query_filters(self):
        path = _make_db()
        try:
            for i, (btype, engine, model) in enumerate(
                [
                    ("code", "llamacpp", "qwen"),
                    ("agentic", "llamacpp", "qwen"),
                    ("code", "ollama", "gemma"),
                ]
            ):
                store_bench_run(
                    path,
                    {
                        "ts": NOW - i,
                        "bench_type": btype,
                        "engine": engine,
                        "model": model,
                        "payload": "{}",
                    },
                )
            assert len(query_bench_runs(path)) == 3
            assert len(query_bench_runs(path, bench_type="code")) == 2
            assert len(query_bench_runs(path, engine="ollama")) == 1
            assert len(query_bench_runs(path, model="qwen")) == 2
            assert len(query_bench_runs(path, bench_type="code", model="gemma")) == 1
            # Newest first
            rows = query_bench_runs(path)
            assert rows[0]["ts"] >= rows[-1]["ts"]
        finally:
            os.unlink(path)

    def test_get_missing_returns_none(self):
        path = _make_db()
        try:
            assert get_bench_run(path, 424242) is None
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# persist_bench_run per type (payload shapes mirror the real out-dicts)
# ---------------------------------------------------------------------------


class TestPersistPerType:
    def _persist_and_fetch(self, bench_type: str, payload: dict) -> dict:
        path = _make_db()
        try:
            run_id = persist_bench_run(path, bench_type, payload)
            assert run_id is not None and run_id > 0
            full = get_bench_run(path, run_id)
            assert full is not None
            # Payload survives verbatim.
            assert json.loads(full["payload"]) == json.loads(
                json.dumps(payload, default=str, ensure_ascii=False)
            )
            return full
        finally:
            os.unlink(path)

    def test_agentic(self):
        payload = {
            "schema_version": "agentic-v5",
            "engine": "llamacpp",
            "model": "qwen3.5:4b",
            "base_url": "http://127.0.0.1:8090",
            "started_at": NOW,
            "finished_at": NOW + 300,
            "prefix_cache_reuse_verdict": "REUSED",
            "prefix_cache_reuse": {"reuse_fraction": 0.93, "cache_source": "usage"},
            "quality_gates": {
                "early_stop": {"detected": True, "truncated_runs": [{"phase": "warm-1"}]},
                "memory_pressure": {"alerted": False},
                "duplicate_processes": [],
                # Real _summarize_output shape: output_valid_pct + min_valid_pct.
                "output_validity": {"output_valid_pct": 100.0, "min_valid_pct": 80},
            },
            **_meta("agentic"),
        }
        row = self._persist_and_fetch("agentic", payload)
        assert row["score_primary"] == 0.93
        assert row["score_label"] == "reuse_fraction"
        assert row["gates_failed"] == 1  # early_stop only
        assert row["hw_chip"] == "Apple M5 Max"
        assert row["asiai_version"] == "1.24.0"
        assert row["powermode"] == 2

    def test_agentic_output_validity_gate_fires(self):
        # Below the bench's own min_valid_pct threshold → counts as failed.
        _score, _label, failed = extract_headline(
            "agentic",
            {
                "prefix_cache_reuse": {"reuse_fraction": 0.9},
                "quality_gates": {
                    "output_validity": {"output_valid_pct": 50.0, "min_valid_pct": 80}
                },
            },
        )
        assert failed == 1

    def test_burst(self):
        payload = {
            "schema_version": "burst-v2",
            "engine": "rapidmlx",
            "model": "qwen3.5:4b",
            "started_at": NOW,
            "finished_at": NOW + 120,
            "burst_sizes": [10, 60],
            "results": {
                "10": {"latency_ms": {"p95": 900.0}, "errors_count": 0},
                "60": {"latency_ms": {"p95": 4500.0}, "errors_count": 2},
            },
            **_meta("burst"),
        }
        row = self._persist_and_fetch("burst", payload)
        assert row["score_primary"] == 4500.0
        assert row["score_label"] == "p95_ms_at_burst_60"
        assert row["gates_failed"] == 1  # one size with errors

    def test_burst_multi_runs_p95_dict(self):
        payload = {
            "engine": "llamacpp",
            "model": "m",
            "started_at": NOW,
            "results": {
                "30": {
                    "latency_ms": {"p95": {"median": 2000.0, "min": 1800.0, "max": 2300.0}},
                    "errors_count": 0,
                }
            },
        }
        score, label, failed = extract_headline("burst", payload)
        assert score == 2000.0
        assert label == "p95_ms_at_burst_30"
        assert failed == 0

    def test_burst_multi_runs_errors_dict_zero_not_counted(self):
        # runs>1: _aggregate_passes folds errors_count into a dict — a
        # zero-error dict is truthy and must NOT count as a failed gate.
        payload = {
            "engine": "llamacpp",
            "model": "m",
            "results": {
                "30": {
                    "latency_ms": {"p95": {"median": 1000.0, "min": 900.0, "max": 1100.0}},
                    "errors_count": {"median": 0, "min": 0, "max": 0},
                },
                "60": {
                    "latency_ms": {"p95": {"median": 3000.0, "min": 2800.0, "max": 3200.0}},
                    "errors_count": {"median": 0, "min": 0, "max": 2},
                },
            },
        }
        _score, _label, failed = extract_headline("burst", payload)
        assert failed == 1  # only the size where at least one pass errored

    def test_code(self):
        payload = {
            "schema_version": "code-v3",
            "dataset_version": "ds-2",
            "engine": "llamacpp",
            "model": "qwen3.5:4b",
            "started_at": NOW,
            "finished_at": NOW + 600,
            "extra_body": {"enable_thinking": False},
            "code_results": {
                "tool_call": {"pct_clean": 90.0},
                "recovery": {"pct_recovered": 80.0},
                "thinking": {"pct_no_think_leak": 100.0},
                "coding": {"tasks": []},  # judge block never blends in
            },
            **_meta("code"),
        }
        row = self._persist_and_fetch("code", payload)
        assert row["score_primary"] == 90.0  # mean(90, 80, 100)
        assert row["score_label"] == "mean_pct_clean_deterministic"
        assert row["dataset_version"] == "ds-2"
        assert json.loads(row["extra_body"]) == {"enable_thinking": False}

    def test_language(self):
        payload = {
            "engine": "llamacpp",
            "model": "m",
            "started_at": NOW,
            "language": "fr",
            "language_results": {"adherence": {"pct_in_language": 96.0}},
            **_meta("language"),
        }
        row = self._persist_and_fetch("language", payload)
        assert row["score_primary"] == 96.0
        assert row["score_label"] == "pct_in_language"

    def test_instruct(self):
        payload = {
            "engine": "llamacpp",
            "model": "m",
            "started_at": NOW,
            "instruct_results": {"verifiable": {"prompt_level_strict": 72.0}},
            **_meta("instruct"),
        }
        row = self._persist_and_fetch("instruct", payload)
        assert row["score_primary"] == 72.0
        assert row["score_label"] == "prompt_strict_pct"

    def test_instruct_agentic_only(self):
        score, label, _ = extract_headline(
            "instruct",
            {"instruct_results": {"research_brief": {"pct_primary_delivered": 60.0}}},
        )
        assert score == 60.0
        assert label == "pct_primary_delivered_research_brief"

    def test_thinking_ablation(self):
        payload = {
            "engine": "llamacpp",
            "model": "m",
            "started_at": NOW,
            "cells": [{"pct_clean": 95.0}, {"pct_clean": 40.0}],
            **_meta("thinking-ablation"),
        }
        row = self._persist_and_fetch("thinking-ablation", payload)
        assert row["score_primary"] == 40.0  # min — the ablation's weak spot
        assert row["score_label"] == "min_pct_clean"

    def test_standard_session(self):
        payload = {
            "schema_version": 2,
            "asiai_version": "1.24.0",
            "timestamp": NOW,
            "machine": {"chip": "Apple M4 Pro", "os_version": "26.0", "ram_gb": 64},
            "benchmark": {
                "model": "qwen3.5:4b",
                "engines": {
                    "llamacpp": {"median_tok_s": 62.0},
                    "ollama": {"median_tok_s": 55.0},
                },
                # Real export shape: _determine_winner's dict, not a name.
                "winner": {"name": "llamacpp", "tok_s_delta": "+12.7%"},
            },
        }
        row = self._persist_and_fetch("standard", payload)
        assert row["score_primary"] == 62.0
        assert row["score_label"] == "winner_median_tok_s"
        assert row["engine"] == "llamacpp,ollama"
        assert row["model"] == "qwen3.5:4b"
        assert row["hw_chip"] == "Apple M4 Pro"
        assert row["ram_gb"] == 64

    def test_standard_no_winner_falls_back_to_best(self):
        score, label, _ = extract_headline(
            "standard",
            {"benchmark": {"engines": {"a": {"median_tok_s": 10.0}, "b": {"median_tok_s": 20.0}}}},
        )
        assert score == 20.0
        assert label == "best_median_tok_s"


# ---------------------------------------------------------------------------
# Robustness — a persistence problem must never lose a finished bench
# ---------------------------------------------------------------------------


class TestRobustness:
    def test_headline_missing_fields_returns_none_not_zero(self):
        for btype in (
            "standard",
            "agentic",
            "burst",
            "code",
            "language",
            "instruct",
            "thinking-ablation",
        ):
            score, _label, failed = extract_headline(btype, {})
            assert score is None, f"{btype}: empty payload must not invent a score"
            assert failed == 0

    def test_unknown_type_is_harmless(self):
        assert extract_headline("nope", {"x": 1}) == (None, "", 0)

    def test_persist_never_raises_on_bad_db_path(self):
        result = persist_bench_run("/nonexistent-dir/nope/metrics.db", "code", {"model": "m"})
        assert result is None

    def test_hostile_payload_values_survive(self):
        path = _make_db()
        try:
            run_id = persist_bench_run(
                path,
                "code",
                {
                    "engine": "llamacpp",
                    "model": "m",
                    "started_at": NOW,
                    "schema_version": {"weird": "dict"},
                    "code_results": {"tool_call": {"pct_clean": "not-a-number"}},
                },
            )
            assert run_id is not None
            row = get_bench_run(path, run_id)
            assert row is not None
            assert row["score_primary"] is None  # non-numeric never coerced
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Migration + retention
# ---------------------------------------------------------------------------


class TestMigrationAndRetention:
    def test_new_benchmark_columns_round_trip(self):
        path = _make_db()
        try:
            store_benchmark(
                path,
                [
                    {
                        "ts": NOW,
                        "engine": "ollama",
                        "model": "m",
                        "prompt_type": "code",
                        "output_degenerate": True,
                        "ttft_source": "server",
                        "vram_estimated": False,
                        "engine_runner": "mlx",
                        "extra_body": '{"enable_thinking": false}',
                        "asiai_version": "1.24.0",
                    }
                ],
            )
            conn = sqlite3.connect(path)
            row = conn.execute(
                "SELECT output_degenerate, ttft_source, vram_estimated, "
                "engine_runner, extra_body, asiai_version FROM benchmarks"
            ).fetchone()
            conn.close()
            assert row == (1, "server", 0, "mlx", '{"enable_thinking": false}', "1.24.0")
        finally:
            os.unlink(path)

    def test_new_columns_default_to_null_unknown(self):
        """Rows written without the flags read as NULL (unknown) — NEVER a
        truthy sentinel like -1, which would make every pre-migration row
        read as degenerate and poison aggregate_results/compare/winner."""
        path = _make_db()
        try:
            store_benchmark(
                path,
                [{"ts": NOW, "engine": "e", "model": "m", "prompt_type": "p"}],
            )
            conn = sqlite3.connect(path)
            row = conn.execute(
                "SELECT output_degenerate, vram_estimated FROM benchmarks"
            ).fetchone()
            conn.close()
            assert row == (None, None)
        finally:
            os.unlink(path)

    def test_pre_migration_rows_stay_clean_for_aggregation(self):
        """Regression (audit PR#55 critique): historic rows must aggregate
        exactly as before the migration — never counted degenerate."""
        from asiai.benchmark.reporter import aggregate_results
        from asiai.storage.db import query_benchmarks

        path = _make_db()
        try:
            store_benchmark(
                path,
                [
                    {
                        "ts": NOW,
                        "engine": "ollama",
                        "model": "m",
                        "prompt_type": "code",
                        "tok_per_sec": 42.0,
                        "ttft_ms": 100.0,
                        # no output_degenerate key — pre-migration shape
                    }
                ],
            )
            rows = query_benchmarks(path)
            report = aggregate_results(rows)
            assert report["engines"]["ollama"]["output_valid_pct"] == 100.0
        finally:
            os.unlink(path)

    def test_empty_session_ghost_rows_skipped(self):
        from asiai.benchmark.persist import persist_standard_session

        path = _make_db()
        try:
            # Nothing measured (no engines at all) → skip, no ghost.
            assert persist_standard_session(path, {"benchmark": {"slots": []}}) is None
            assert query_bench_runs(path) == []
            # A real session payload still persists.
            ok = persist_standard_session(
                path,
                {"timestamp": NOW, "benchmark": {"model": "m", "engines": {"e": {}}}},
            )
            assert ok is not None
        finally:
            os.unlink(path)

    def test_compare_session_persists_a_row(self):
        """Regression: a multi-model compare session left bench_runs EMPTY
        (the old 'ghost row' skip keyed on the empty benchmark.engines the
        old export produced for compare reports)."""
        from asiai.benchmark.persist import persist_standard_session
        from tests.test_result_model import _compare_session_payload

        payload = _compare_session_payload()
        path = _make_db()
        try:
            row_id = persist_standard_session(path, payload)
            assert row_id is not None
            assert len(query_bench_runs(path)) == 1
            from asiai.storage.db import get_bench_run

            row = get_bench_run(path, row_id)
            assert row["bench_type"] == "standard"
            # engine/model columns: bare names, joined and sorted — never
            # the "model / engine" slot labels.
            assert row["engine"] == "llamacpp,mlxlm,ollama"
            assert row["model"] == (
                "Qwen3.6-27B-UD-Q8_K_XL.gguf,"
                "qwen3.6:27b-instruct-q4_K_M,"
                "unsloth/Qwen3.6-27B-UD-MLX-4bit"
            )
            # headline = the winner's median, explicitly labeled
            assert row["score_label"] == "winner_median_tok_s"
            winner_key = payload["benchmark"]["winner"]["name"]
            expected = payload["benchmark"]["engines"][winner_key]["median_tok_s"]
            assert row["score_primary"] == expected
            # session gates (thermal serious + memory pressure) counted
            assert row["gates_failed"] == 2
            # payload stored VERBATIM
            assert json.loads(row["payload"]) == payload
        finally:
            os.unlink(path)

    def test_migration_idempotent_with_bench_runs(self):
        path = _make_db()
        try:
            init_db(path)  # second run must be a no-op
            conn = sqlite3.connect(path)
            cols = {r[1] for r in conn.execute("PRAGMA table_info(bench_runs)").fetchall()}
            conn.close()
            assert {"bench_type", "score_primary", "score_label", "payload"} <= cols
        finally:
            os.unlink(path)

    def test_purge_keeps_bench_runs_and_process(self):
        path = _make_db()
        old = NOW - 400 * 86400
        try:
            store_bench_run(
                path,
                {"ts": old, "bench_type": "code", "engine": "e", "model": "m", "payload": "{}"},
            )
            conn = sqlite3.connect(path)
            conn.execute(
                "INSERT INTO benchmark_process (ts, engine, proc_rss_bytes) VALUES (?, 'e', 1)",
                (old,),
            )
            conn.commit()
            conn.close()

            purge_old(path, days=90)

            conn = sqlite3.connect(path)
            runs = conn.execute("SELECT COUNT(*) FROM bench_runs").fetchone()[0]
            procs = conn.execute("SELECT COUNT(*) FROM benchmark_process").fetchone()[0]
            conn.close()
            # Campaign history is forever — including process samples now
            # (their volume matches benchmarks; the 7-day window was an
            # inconsistency, not a saving).
            assert runs == 1
            assert procs == 1
        finally:
            os.unlink(path)
