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
            snap = _make_snapshot(now, models=[
                {
                    "engine": "ollama",
                    "name": "qwen3:30b",
                    "size_vram": 20_000_000_000,
                    "size_total": 16_000_000_000,
                    "format": "gguf",
                    "quantization": "Q4_K_M",
                },
            ])
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
