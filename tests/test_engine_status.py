"""Tests for engine_status table and uptime queries."""

from __future__ import annotations

import sqlite3
import time
from unittest.mock import MagicMock

import pytest

from asiai.storage.db import (
    init_db,
    query_engine_uptime,
    query_latest_benchmarks,
    store_engine_status,
)


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


class TestStoreEngineStatus:
    def test_store_single_engine(self, db_path):
        statuses = [
            {
                "name": "ollama",
                "url": "http://localhost:11434",
                "reachable": True,
                "version": "0.17.4",
                "models": [{"name": "qwen3.5:35b-a3b"}],
                "vram_total": 26_000_000_000,
            },
        ]
        store_engine_status(db_path, statuses)

        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT * FROM engine_status").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][1] == "ollama"  # engine
        assert rows[0][2] == 1  # reachable

    def test_store_multiple_engines(self, db_path):
        statuses = [
            {
                "name": "ollama",
                "reachable": True,
                "version": "0.17.4",
                "models": [],
                "vram_total": 0,
            },
            {"name": "lmstudio", "reachable": False, "version": "", "models": [], "vram_total": 0},
        ]
        store_engine_status(db_path, statuses)

        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT engine, reachable FROM engine_status ORDER BY engine"
        ).fetchall()
        conn.close()
        assert len(rows) == 2
        assert rows[0] == ("lmstudio", 0)
        assert rows[1] == ("ollama", 1)

    def test_store_unreachable(self, db_path):
        statuses = [
            {"name": "ollama", "reachable": False, "version": "", "models": [], "vram_total": 0},
        ]
        store_engine_status(db_path, statuses)

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT reachable FROM engine_status").fetchone()
        conn.close()
        assert row[0] == 0


class TestQueryEngineUptime:
    def test_no_data(self, db_path):
        uptime = query_engine_uptime(db_path, "ollama", hours=24)
        assert uptime == 0.0

    def test_all_up(self, db_path):
        conn = sqlite3.connect(db_path)
        now = int(time.time())
        for i in range(10):
            conn.execute(
                "INSERT INTO engine_status (ts, engine, reachable) VALUES (?, ?, ?)",
                (now - i * 60, "ollama", 1),
            )
        conn.commit()
        conn.close()

        uptime = query_engine_uptime(db_path, "ollama", hours=1)
        assert uptime == 100.0

    def test_partial_uptime(self, db_path):
        conn = sqlite3.connect(db_path)
        now = int(time.time())
        # 5 up, 5 down
        for i in range(10):
            reachable = 1 if i < 5 else 0
            conn.execute(
                "INSERT INTO engine_status (ts, engine, reachable) VALUES (?, ?, ?)",
                (now - i * 60, "ollama", reachable),
            )
        conn.commit()
        conn.close()

        uptime = query_engine_uptime(db_path, "ollama", hours=1)
        assert uptime == 50.0


class TestQueryLatestBenchmarks:
    def test_no_benchmarks(self, db_path):
        results = query_latest_benchmarks(db_path)
        assert results == []

    def test_returns_latest(self, db_path):
        conn = sqlite3.connect(db_path)
        now = int(time.time())
        # Insert two benchmarks for same engine+model, different timestamps
        conn.execute(
            "INSERT INTO benchmarks"
            " (ts, engine, model, prompt_type, tok_per_sec, ttft_ms, power_watts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (now - 100, "ollama", "qwen3.5", "code", 25.0, 300.0, 15.0),
        )
        conn.execute(
            "INSERT INTO benchmarks"
            " (ts, engine, model, prompt_type, tok_per_sec, ttft_ms, power_watts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (now, "ollama", "qwen3.5", "code", 30.0, 250.0, 16.0),
        )
        conn.commit()
        conn.close()

        results = query_latest_benchmarks(db_path)
        assert len(results) == 1
        assert results[0]["tok_per_sec"] == 30.0


class TestCollectEnginesStatus:
    def test_collect_reachable(self):
        from asiai.collectors.snapshot import collect_engines_status

        engine = MagicMock()
        engine.name = "ollama"
        engine.base_url = "http://localhost:11434"
        engine.is_reachable.return_value = True
        engine.version.return_value = "0.17.4"

        model = MagicMock()
        model.name = "test-model"
        model.size_vram = 4_000_000_000
        model.format = "gguf"
        model.quantization = "Q4_K_M"
        model.context_length = 32768
        engine.list_running.return_value = [model]

        statuses = collect_engines_status([engine])
        assert len(statuses) == 1
        assert statuses[0]["reachable"] is True
        assert statuses[0]["version"] == "0.17.4"
        assert len(statuses[0]["models"]) == 1

    def test_collect_unreachable(self):
        from asiai.collectors.snapshot import collect_engines_status

        engine = MagicMock()
        engine.name = "lmstudio"
        engine.base_url = "http://localhost:1234"
        engine.is_reachable.return_value = False

        statuses = collect_engines_status([engine])
        assert len(statuses) == 1
        assert statuses[0]["reachable"] is False
        assert statuses[0]["models"] == []

    def test_collect_handles_exception(self):
        from asiai.collectors.snapshot import collect_engines_status

        engine = MagicMock()
        engine.name = "broken"
        engine.base_url = "http://localhost:9999"
        engine.is_reachable.side_effect = Exception("connection refused")

        statuses = collect_engines_status([engine])
        assert len(statuses) == 1
        assert statuses[0]["reachable"] is False
