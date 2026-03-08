"""Tests for the web dashboard module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from asiai.web.app import create_app, format_bytes_filter, format_number_filter
from asiai.web.state import AppState, BenchStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_engine():
    """Create a mock inference engine."""
    engine = MagicMock()
    engine.name = "ollama"
    engine.base_url = "http://localhost:11434"

    status = MagicMock()
    status.reachable = True
    engine.status.return_value = status

    engine.version.return_value = "0.1.42"

    model = MagicMock()
    model.name = "qwen2.5:7b"
    model.size_vram = 4_500_000_000
    model.size_total = 5_000_000_000
    model.format = "gguf"
    model.quantization = "Q4_K_M"
    model.context_length = 32768
    engine.list_running.return_value = [model]

    return engine


@pytest.fixture
def app_state(tmp_path, mock_engine):
    """Create an AppState with a temp DB."""
    db_path = str(tmp_path / "test.db")
    from asiai.storage.db import init_db

    init_db(db_path)
    return AppState(engines=[mock_engine], db_path=db_path)


@pytest.fixture
def client(app_state):
    """Create a FastAPI TestClient."""
    app = create_app(app_state)
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Unit tests — filters
# ---------------------------------------------------------------------------


class TestFilters:
    def test_format_bytes_zero(self):
        assert format_bytes_filter(0) == ""

    def test_format_bytes_gb(self):
        result = format_bytes_filter(4_500_000_000)
        assert "GB" in result
        assert "4.2" in result

    def test_format_bytes_mb(self):
        result = format_bytes_filter(500_000_000)
        assert "MB" in result

    def test_format_number_default(self):
        assert format_number_filter(3.14159) == "3.1"

    def test_format_number_custom_decimals(self):
        assert format_number_filter(3.14159, 3) == "3.142"

    def test_format_number_none(self):
        assert format_number_filter(None) == "\u2014"


# ---------------------------------------------------------------------------
# Unit tests — state
# ---------------------------------------------------------------------------


class TestAppState:
    def test_bench_status_defaults(self):
        status = BenchStatus()
        assert not status.running
        assert not status.done
        assert status.error == ""

    def test_refresh_engines_if_stale(self, app_state):
        # First call should populate cache
        engines = app_state.refresh_engines_if_stale(max_age=0.0)
        assert len(engines) == 1
        assert engines[0].name == "ollama"

    def test_refresh_engines_uses_cache(self, app_state):
        app_state.refresh_engines_if_stale(max_age=30.0)
        # Should use cache on second call
        engines = app_state.refresh_engines_if_stale(max_age=30.0)
        assert len(engines) == 1


# ---------------------------------------------------------------------------
# Security tests — CSRF
# ---------------------------------------------------------------------------


class TestCSRF:
    def test_post_without_origin_returns_403(self, client):
        response = client.post("/doctor/refresh")
        assert response.status_code == 403

    def test_post_with_wrong_origin_returns_403(self, client):
        response = client.post(
            "/doctor/refresh", headers={"Origin": "http://evil.com"}
        )
        assert response.status_code == 403

    def test_post_with_correct_origin_passes(self, client):
        with patch("asiai.web.routes.doctor._run_checks") as mock_checks:
            mock_checks.return_value = []
            response = client.post(
                "/doctor/refresh", headers={"Origin": "http://testserver"}
            )
            assert response.status_code == 200


# ---------------------------------------------------------------------------
# Route tests — Dashboard
# ---------------------------------------------------------------------------


class TestDashboard:
    @patch("asiai.web.routes.dashboard._get_snapshot")
    def test_dashboard_returns_200(self, mock_snap, client):
        mock_snap.return_value = {
            "cpu_load_1": 2.5,
            "cpu_load_5": 2.0,
            "cpu_load_15": 1.5,
            "cpu_cores": 10,
            "mem_total": 68_719_476_736,
            "mem_used": 34_000_000_000,
            "mem_pressure": "normal",
            "thermal_level": "nominal",
            "thermal_speed_limit": -1,
            "uptime": 86400,
        }
        response = client.get("/")
        assert response.status_code == 200
        assert "Dashboard" in response.text
        assert "asiai" in response.text

    @patch("asiai.web.routes.dashboard._get_snapshot")
    def test_dashboard_shows_engines(self, mock_snap, client):
        mock_snap.return_value = {}
        response = client.get("/")
        assert response.status_code == 200
        assert "ollama" in response.text


# ---------------------------------------------------------------------------
# Route tests — Monitor
# ---------------------------------------------------------------------------


class TestMonitor:
    @patch("asiai.web.routes.monitor._get_snapshot")
    def test_monitor_page_returns_200(self, mock_snap, client):
        mock_snap.return_value = {
            "cpu_load_1": 1.0,
            "cpu_cores": 10,
            "mem_total": 68_719_476_736,
            "mem_used": 30_000_000_000,
            "mem_pressure": "normal",
            "thermal_level": "nominal",
            "thermal_speed_limit": -1,
        }
        response = client.get("/monitor")
        assert response.status_code == 200
        assert "Monitor" in response.text


# ---------------------------------------------------------------------------
# Route tests — Doctor
# ---------------------------------------------------------------------------


class TestDoctor:
    @patch("asiai.web.routes.doctor._run_checks")
    def test_doctor_page_returns_200(self, mock_checks, client):
        mock_checks.return_value = [
            {
                "category": "system",
                "name": "Apple Silicon",
                "status": "ok",
                "message": "Running on M1 Max",
                "fix": "",
            },
            {
                "category": "engine",
                "name": "Ollama",
                "status": "ok",
                "message": "Reachable at localhost:11434",
                "fix": "",
            },
        ]
        response = client.get("/doctor")
        assert response.status_code == 200
        assert "Doctor" in response.text
        assert "Apple Silicon" in response.text

    @patch("asiai.web.routes.doctor._run_checks")
    def test_doctor_refresh_returns_partial(self, mock_checks, client):
        mock_checks.return_value = [
            {
                "category": "system",
                "name": "RAM",
                "status": "ok",
                "message": "64 GB",
                "fix": "",
            },
        ]
        response = client.post(
            "/doctor/refresh", headers={"Origin": "http://testserver"}
        )
        assert response.status_code == 200
        assert "RAM" in response.text


# ---------------------------------------------------------------------------
# Route tests — Benchmark
# ---------------------------------------------------------------------------


class TestBench:
    @patch("asiai.web.routes.bench._get_prompts")
    @patch("asiai.web.routes.bench._get_engines_for_form")
    def test_bench_page_returns_200(self, mock_engines, mock_prompts, client):
        mock_engines.return_value = [
            {"name": "ollama", "reachable": True, "models": ["qwen2.5:7b"]},
        ]
        mock_prompts.return_value = [
            {"name": "code", "label": "Code Generation", "max_tokens": 512},
        ]
        response = client.get("/bench")
        assert response.status_code == 200
        assert "Benchmark" in response.text
        assert "ollama" in response.text

    def test_bench_run_conflict_when_running(self, client, app_state):
        app_state.bench_status.running = True
        response = client.post(
            "/bench/run",
            data={"model": "test"},
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# Route tests — History
# ---------------------------------------------------------------------------


class TestHistory:
    def test_history_page_returns_200(self, client):
        response = client.get("/history")
        assert response.status_code == 200
        assert "History" in response.text

    def test_api_benchmarks_returns_json(self, client):
        response = client.get("/api/benchmarks?hours=24")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_api_history_returns_json(self, client):
        response = client.get("/api/history?hours=24")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_api_benchmarks_with_filters(self, client):
        response = client.get("/api/benchmarks?hours=24&model=test&engine=ollama")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Route tests — Bench export
# ---------------------------------------------------------------------------


class TestBenchExport:
    def test_export_no_data(self, client):
        response = client.get("/bench/export")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Integration: app creation
# ---------------------------------------------------------------------------


class TestAppCreation:
    def test_create_app(self, app_state):
        app = create_app(app_state)
        assert app.title == "asiai"

    def test_static_files_mounted(self, client):
        response = client.get("/static/style.css")
        assert response.status_code == 200
        assert "bg-primary" in response.text

    def test_static_charts_js(self, client):
        response = client.get("/static/charts.js")
        assert response.status_code == 200
        assert "createBarChart" in response.text


# ---------------------------------------------------------------------------
# CLI: cmd_web
# ---------------------------------------------------------------------------


class TestCmdWeb:
    def test_web_import_guard(self):
        """Verify the HAS_FASTAPI guard works."""
        from asiai.web import HAS_FASTAPI

        assert HAS_FASTAPI is True  # Since we installed fastapi

    def test_web_command_in_parser(self):
        """Verify 'web' is registered as a subcommand."""
        from asiai.cli import main

        # --help should list 'web'
        with pytest.raises(SystemExit) as exc_info:
            main(["web", "--help"])
        assert exc_info.value.code == 0
