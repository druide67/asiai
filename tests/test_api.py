"""Tests for the REST API endpoints (/api/snapshot, /api/status, /api/metrics)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from asiai.web.app import create_app
from asiai.web.state import AppState


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.name = "ollama"
    engine.base_url = "http://localhost:11434"
    engine.is_reachable.return_value = True
    engine.version.return_value = "0.17.4"

    model = MagicMock()
    model.name = "qwen3.5:35b-a3b"
    model.size_vram = 26_000_000_000
    model.size_total = 26_000_000_000
    model.format = "gguf"
    model.quantization = "Q4_K_M"
    model.context_length = 32768
    engine.list_running.return_value = [model]

    return engine


@pytest.fixture
def app_state(tmp_path, mock_engine):
    db_path = str(tmp_path / "test.db")
    from asiai.storage.db import init_db

    init_db(db_path)
    return AppState(engines=[mock_engine], db_path=db_path)


@pytest.fixture
def client(app_state):
    app = create_app(app_state)
    with TestClient(app) as c:
        yield c


class TestApiSnapshot:
    def test_snapshot_returns_200(self, client):
        response = client.get("/api/snapshot")
        assert response.status_code == 200
        data = response.json()
        assert "ts" in data
        assert "cpu_load_1" in data
        assert "mem_total" in data
        assert "engines_status" in data

    def test_snapshot_contains_engine_status(self, client):
        response = client.get("/api/snapshot")
        data = response.json()
        engines = data["engines_status"]
        assert len(engines) == 1
        assert engines[0]["name"] == "ollama"
        assert engines[0]["reachable"] is True
        assert engines[0]["version"] == "0.17.4"

    def test_snapshot_contains_models(self, client):
        response = client.get("/api/snapshot")
        data = response.json()
        engines = data["engines_status"]
        models = engines[0]["models"]
        assert len(models) == 1
        assert models[0]["name"] == "qwen3.5:35b-a3b"

    def test_snapshot_uses_cache(self, client, app_state):
        # First call populates cache
        resp1 = client.get("/api/snapshot")
        ts1 = resp1.json()["ts"]

        # Second call should use cache (same ts)
        resp2 = client.get("/api/snapshot")
        ts2 = resp2.json()["ts"]
        assert ts1 == ts2


class TestApiStatus:
    def test_status_returns_200(self, client):
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "engines" in data
        assert "ts" in data
        assert "uptime" in data

    def test_status_ok_when_all_reachable(self, client):
        response = client.get("/api/status")
        data = response.json()
        assert data["status"] == "ok"
        assert data["engines"]["ollama"] is True

    def test_status_degraded_when_mixed(self, client, app_state):
        # Add an unreachable engine
        engine2 = MagicMock()
        engine2.name = "lmstudio"
        engine2.base_url = "http://localhost:1234"
        engine2.is_reachable.return_value = False
        engine2.version.return_value = ""
        engine2.list_running.return_value = []
        app_state.engines.append(engine2)
        # Clear cache to force refresh
        app_state._snapshot_cache = None

        response = client.get("/api/status")
        data = response.json()
        assert data["status"] == "degraded"

    def test_status_has_memory_pressure(self, client):
        response = client.get("/api/status")
        data = response.json()
        assert "memory_pressure" in data

    def test_status_has_thermal_level(self, client):
        response = client.get("/api/status")
        data = response.json()
        assert "thermal_level" in data


class TestApiMetrics:
    def test_metrics_returns_200(self, client):
        response = client.get("/api/metrics")
        assert response.status_code == 200

    def test_metrics_content_type(self, client):
        response = client.get("/api/metrics")
        assert "text/plain" in response.headers["content-type"]

    def test_metrics_contains_system_gauges(self, client):
        response = client.get("/api/metrics")
        body = response.text
        assert "asiai_cpu_load_1m" in body
        assert "asiai_memory_used_bytes" in body
        assert "asiai_memory_total_bytes" in body
        assert "asiai_thermal_speed_limit_pct" in body

    def test_metrics_contains_engine_gauges(self, client):
        response = client.get("/api/metrics")
        body = response.text
        assert 'asiai_engine_reachable{engine="ollama"}' in body
        assert 'asiai_engine_models_loaded{engine="ollama"}' in body
        assert 'asiai_engine_version_info{engine="ollama"' in body

    def test_metrics_contains_model_gauges(self, client):
        response = client.get("/api/metrics")
        body = response.text
        assert 'asiai_model_loaded{engine="ollama",model="qwen3.5:35b-a3b"}' in body
        assert 'asiai_model_vram_bytes{engine="ollama"' in body

    def test_metrics_has_type_annotations(self, client):
        response = client.get("/api/metrics")
        body = response.text
        assert "# TYPE asiai_cpu_load_1m gauge" in body
        assert "# HELP asiai_cpu_load_1m" in body
