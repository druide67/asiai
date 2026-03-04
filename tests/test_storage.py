"""Tests for SQLite storage."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import time

from asiai.storage.db import (
    init_db,
    purge_old,
    query_compare,
    query_history,
    store_benchmark,
    store_snapshot,
)


def _make_db() -> str:
    """Create a temp DB and return its path."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    return path


def _make_snapshot(ts: int, models: list[dict] | None = None) -> dict:
    return {
        "ts": ts,
        "cpu_load_1": 1.5,
        "cpu_load_5": 1.2,
        "cpu_load_15": 1.0,
        "mem_total": 68719476736,
        "mem_used": 34000000000,
        "mem_pressure": "normal",
        "thermal_level": "nominal",
        "thermal_speed_limit": 100,
        "uptime": 86400,
        "inference_engine": "ollama",
        "engine_version": "0.17.4",
        "models": models or [],
    }


class TestInitDb:
    def test_creates_tables(self):
        path = _make_db()
        try:
            conn = sqlite3.connect(path)
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            conn.close()
            assert "metrics" in tables
            assert "models" in tables
        finally:
            os.unlink(path)

    def test_idempotent(self):
        path = _make_db()
        try:
            init_db(path)  # second call should not fail
            init_db(path)  # third call
        finally:
            os.unlink(path)


class TestStoreAndQuery:
    def test_store_and_query_history(self):
        path = _make_db()
        now = int(time.time())
        try:
            snap = _make_snapshot(
                now,
                models=[
                    {
                        "engine": "ollama",
                        "name": "qwen3:30b",
                        "size_vram": 20_000_000_000,
                        "size_total": 16_000_000_000,
                        "format": "gguf",
                        "quantization": "Q4_K_M",
                    },
                ],
            )
            store_snapshot(path, snap)

            history = query_history(path, hours=1)
            assert len(history) == 1
            assert history[0]["ts"] == now
            assert len(history[0]["models"]) == 1
            assert history[0]["models"][0]["name"] == "qwen3:30b"
        finally:
            os.unlink(path)

    def test_store_no_models(self):
        path = _make_db()
        now = int(time.time())
        try:
            snap = _make_snapshot(now)
            store_snapshot(path, snap)

            history = query_history(path, hours=1)
            assert len(history) == 1
            assert history[0]["models"] == []
        finally:
            os.unlink(path)

    def test_query_compare(self):
        path = _make_db()
        now = int(time.time())
        try:
            store_snapshot(path, _make_snapshot(now - 3600))
            store_snapshot(path, _make_snapshot(now))

            result = query_compare(path, now - 3600, now)
            assert result["before"]["ts"] == now - 3600
            assert result["after"]["ts"] == now
        finally:
            os.unlink(path)


class TestPurge:
    def test_purge_old(self):
        path = _make_db()
        now = int(time.time())
        try:
            # Insert old entry (91 days ago)
            store_snapshot(path, _make_snapshot(now - 91 * 86400))
            # Insert recent entry
            store_snapshot(path, _make_snapshot(now))

            deleted = purge_old(path, days=90)
            assert deleted == 1

            history = query_history(path, hours=24 * 365)
            assert len(history) == 1
            assert history[0]["ts"] == now
        finally:
            os.unlink(path)


class TestMigrations:
    def test_v02_db_migrates_to_v03(self):
        """A DB created with v0.2 schema (no v0.3 columns) should migrate cleanly."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            # Create a v0.2 DB manually (without v0.3 columns)
            conn = sqlite3.connect(path)
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS benchmarks (
                    ts INTEGER NOT NULL,
                    engine TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_type TEXT NOT NULL,
                    tokens_generated INTEGER,
                    tok_per_sec REAL,
                    ttft_ms REAL,
                    total_duration_ms REAL,
                    vram_bytes INTEGER,
                    mem_used INTEGER,
                    thermal_level TEXT,
                    thermal_speed_limit INTEGER
                );
                CREATE TABLE IF NOT EXISTS metrics (
                    ts INTEGER PRIMARY KEY,
                    cpu_load_1 REAL,
                    cpu_load_5 REAL,
                    cpu_load_15 REAL,
                    mem_total INTEGER,
                    mem_used INTEGER,
                    mem_pressure TEXT,
                    thermal_level TEXT,
                    thermal_speed_limit INTEGER,
                    uptime INTEGER,
                    inference_engine TEXT,
                    engine_version TEXT
                );
                CREATE TABLE IF NOT EXISTS models (
                    ts INTEGER,
                    engine TEXT,
                    name TEXT,
                    size_vram INTEGER,
                    size_total INTEGER,
                    model_format TEXT,
                    quantization TEXT
                );
                """
            )
            # Insert a v0.2 row (no run_index, power_watts, etc.)
            conn.execute(
                """INSERT INTO benchmarks
                   (ts, engine, model, prompt_type, tok_per_sec, ttft_ms)
                   VALUES (1000, 'ollama', 'test', 'code', 45.0, 800.0)"""
            )
            conn.commit()
            conn.close()

            # Run init_db which triggers migrations
            init_db(path)

            # Verify new columns exist by inserting a v0.3 row
            conn = sqlite3.connect(path)
            conn.execute(
                """INSERT INTO benchmarks
                   (ts, engine, model, prompt_type, tok_per_sec, ttft_ms,
                    run_index, power_watts, tok_per_sec_per_watt, load_time_ms)
                   VALUES (2000, 'ollama', 'test', 'code', 50.0, 750.0,
                           1, 18.5, 2.7, 1234.5)"""
            )
            conn.commit()

            # Verify both old and new rows coexist
            rows = conn.execute("SELECT * FROM benchmarks ORDER BY ts").fetchall()
            conn.close()
            assert len(rows) == 2
        finally:
            os.unlink(path)

    def test_migration_idempotent(self):
        """Running init_db multiple times should not fail or duplicate columns."""
        path = _make_db()
        try:
            init_db(path)
            init_db(path)
            init_db(path)

            # Verify v0.3 columns exist
            conn = sqlite3.connect(path)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(benchmarks)").fetchall()}
            conn.close()
            assert "run_index" in columns
            assert "power_watts" in columns
            assert "tok_per_sec_per_watt" in columns
            assert "load_time_ms" in columns
        finally:
            os.unlink(path)

    def test_store_benchmark_with_v03_fields(self):
        """store_benchmark should accept and persist all v0.3 fields."""
        path = _make_db()
        try:
            results = [
                {
                    "ts": 1000,
                    "engine": "ollama",
                    "model": "test",
                    "prompt_type": "code",
                    "tok_per_sec": 50.0,
                    "ttft_ms": 800.0,
                    "run_index": 2,
                    "power_watts": 18.5,
                    "tok_per_sec_per_watt": 2.7,
                    "load_time_ms": 1234.5,
                }
            ]
            store_benchmark(path, results)

            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM benchmarks").fetchone()
            conn.close()

            assert row["run_index"] == 2
            assert row["power_watts"] == 18.5
            assert row["tok_per_sec_per_watt"] == 2.7
            assert row["load_time_ms"] == 1234.5
        finally:
            os.unlink(path)
