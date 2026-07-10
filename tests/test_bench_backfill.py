"""Tests for the bench_runs backfill (rebuild sessions from raw rows)."""

from __future__ import annotations

import json
import os
import tempfile

from asiai import __version__
from asiai.benchmark.backfill import backfill_bench_runs, detect_sessions
from asiai.storage.db import get_bench_run, init_db, query_bench_runs, store_benchmark

TS_ENGINE = 1_772_309_000  # historic engine-comparison session
TS_MATRIX = 1_783_714_798  # the multi-model compare session shape


def _make_db() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    return path


def _row(ts: int, engine: str, model: str, tok: float, run_index: int = 0, **overrides) -> dict:
    base = {
        "ts": ts,
        "engine": engine,
        "model": model,
        "prompt_type": "code",
        "tok_per_sec": tok,
        "ttft_ms": 120.0,
        "tokens_generated": 400,
        "total_duration_ms": 8000.0,
        "vram_bytes": 9_000_000_000,
        "thermal_level": "nominal",
        "run_index": run_index,
        "hw_chip": "Apple M5 Max",
        "os_version": "26.5.1",
        "ram_gb": 128,
    }
    base.update(overrides)
    return base


def _seed(path: str) -> None:
    rows = []
    # Session 1: same model on two engines — predates asiai_version column.
    for i in range(3):
        rows.append(_row(TS_ENGINE, "ollama", "qwen:4b", 50.0 + i, i))
        rows.append(_row(TS_ENGINE, "lmstudio", "qwen:4b", 60.0 + i, i))
    # Session 2: matrix compare, rows carry the version that ran them.
    for i in range(3):
        rows.append(
            _row(TS_MATRIX, "ollama", "qwen-27b-4bit-mlx", 67.0 + i, i, asiai_version="1.26.0")
        )
        rows.append(
            _row(TS_MATRIX, "llamacpp", "Qwen-27B-Q8.gguf", 29.0 + i, i, asiai_version="1.26.0")
        )
    store_benchmark(path, rows)


class TestDetectSessions:
    def test_one_session_per_distinct_ts(self):
        path = _make_db()
        try:
            _seed(path)
            sessions = detect_sessions(path)
            assert [s.ts for s in sessions] == [TS_ENGINE, TS_MATRIX]
            assert sessions[0].session_type == "engine"
            assert sessions[0].slot_names == ["lmstudio", "ollama"]  # median desc
            assert sessions[1].session_type == "matrix"
            assert sessions[1].slot_names == [
                "qwen-27b-4bit-mlx / ollama",
                "Qwen-27B-Q8.gguf / llamacpp",
            ]
            assert all(not s.exists for s in sessions)
        finally:
            os.unlink(path)


class TestBackfill:
    def test_dry_run_writes_nothing(self):
        path = _make_db()
        try:
            _seed(path)
            sessions = backfill_bench_runs(path, apply=False)
            assert len(sessions) == 2
            assert query_bench_runs(path) == []
        finally:
            os.unlink(path)

    def test_apply_creates_marked_rows(self):
        path = _make_db()
        try:
            _seed(path)
            sessions = backfill_bench_runs(path, apply=True)
            assert all(s.created_id is not None for s in sessions)
            rows = query_bench_runs(path)
            assert len(rows) == 2
            by_ts = {r["ts"]: r for r in rows}
            # engine session: legacy naming intact
            engine_row = get_bench_run(path, by_ts[TS_ENGINE]["id"])
            payload = json.loads(engine_row["payload"])
            assert payload["reconstructed"] is True
            assert set(payload["benchmark"]["engines"]) == {"ollama", "lmstudio"}
            # rows predate asiai_version → ABSENT, never today's version
            assert payload["asiai_version"] == ""
            assert engine_row["asiai_version"] == ""
            # matrix session: slot-labeled entries + the version that ran it
            matrix_row = get_bench_run(path, by_ts[TS_MATRIX]["id"])
            payload = json.loads(matrix_row["payload"])
            assert payload["reconstructed"] is True
            assert payload["asiai_version"] == "1.26.0"
            assert payload["asiai_version"] != __version__ or __version__ == "1.26.0"
            assert set(payload["benchmark"]["engines"]) == {
                "qwen-27b-4bit-mlx / ollama",
                "Qwen-27B-Q8.gguf / llamacpp",
            }
            # nothing invented: no memory gate (never persisted), no errors
            assert "memory_pressure" not in (payload.get("quality_gates") or {})
        finally:
            os.unlink(path)

    def test_apply_is_idempotent(self):
        path = _make_db()
        try:
            _seed(path)
            backfill_bench_runs(path, apply=True)
            again = backfill_bench_runs(path, apply=True)
            assert all(s.exists for s in again)
            assert all(s.created_id is None for s in again)
            assert len(query_bench_runs(path)) == 2
        finally:
            os.unlink(path)

    def test_live_persisted_session_not_duplicated(self):
        from asiai.benchmark.persist import persist_standard_session
        from asiai.benchmark.reporter import build_export_payload, build_report

        path = _make_db()
        try:
            _seed(path)
            # The matrix session was already persisted live (post-fix path).
            raw = [
                _row(TS_MATRIX, "ollama", "qwen-27b-4bit-mlx", 67.0),
                _row(TS_MATRIX, "llamacpp", "Qwen-27B-Q8.gguf", 29.0),
            ]
            persist_standard_session(path, build_export_payload(raw, build_report(raw)))
            sessions = backfill_bench_runs(path, apply=True)
            assert [s.exists for s in sessions] == [False, True]
            rows = query_bench_runs(path)
            assert len(rows) == 2  # 1 live + 1 backfilled, no duplicate
        finally:
            os.unlink(path)


class TestReconstructedRendering:
    def test_report_and_card_flag_reconstruction(self):
        from asiai.benchmark.cards import generate_card
        from asiai.benchmark.report_md import render_markdown
        from asiai.benchmark.result_model import build_result

        path = _make_db()
        try:
            _seed(path)
            backfill_bench_runs(path, apply=True)
            row = query_bench_runs(path, bench_type="standard")[0]
            payload = json.loads(get_bench_run(path, row["id"])["payload"])
            result = build_result("standard", payload)
            md = render_markdown(result)
            assert "rebuilt post-hoc" in md  # provenance says what this is
            svg = generate_card(result)
            assert "reconstructed post-hoc" in svg
            assert "unknown model" not in svg
        finally:
            os.unlink(path)
