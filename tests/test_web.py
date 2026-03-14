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
        assert status.card_svg_url == ""
        assert status.card_png_url == ""
        assert status.share_url == ""
        assert status.card_error == ""

    def test_bench_status_snapshot_includes_card_fields(self):
        status = BenchStatus(
            card_svg_url="/cards/test.svg",
            card_png_url="/cards/test.png",
            share_url="https://asiai.dev/card/abc",
            card_error="",
        )
        snap = status.snapshot()
        assert snap["card_svg_url"] == "/cards/test.svg"
        assert snap["card_png_url"] == "/cards/test.png"
        assert snap["share_url"] == "https://asiai.dev/card/abc"
        assert snap["card_error"] == ""

    def test_update_bench_card_fields(self, app_state):
        app_state.update_bench(
            card_svg_url="/cards/bench.svg",
            card_png_url="/cards/bench.png",
            share_url="https://asiai.dev/card/123",
        )
        snap = app_state.get_bench_snapshot()
        assert snap["card_svg_url"] == "/cards/bench.svg"
        assert snap["card_png_url"] == "/cards/bench.png"
        assert snap["share_url"] == "https://asiai.dev/card/123"

    def test_reset_bench_clears_card_fields(self, app_state):
        app_state.update_bench(card_svg_url="/cards/old.svg", share_url="https://old")
        app_state.reset_bench(running=True)
        snap = app_state.get_bench_snapshot()
        assert snap["card_svg_url"] == ""
        assert snap["share_url"] == ""

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
        response = client.post("/doctor/refresh", headers={"Origin": "http://evil.com"})
        assert response.status_code == 403

    def test_post_with_correct_origin_passes(self, client):
        with patch("asiai.web.routes.doctor._run_checks") as mock_checks:
            mock_checks.return_value = []
            response = client.post("/doctor/refresh", headers={"Origin": "http://testserver"})
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
        response = client.post("/doctor/refresh", headers={"Origin": "http://testserver"})
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

    @patch("asiai.web.routes.bench._get_prompts")
    @patch("asiai.web.routes.bench._get_engines_for_form")
    def test_bench_page_has_quick_bench_button(self, mock_engines, mock_prompts, client):
        mock_engines.return_value = []
        mock_prompts.return_value = []
        response = client.get("/bench")
        assert response.status_code == 200
        assert "quick-bench-btn" in response.text
        assert "Quick Bench" in response.text

    @patch("asiai.web.routes.bench._get_prompts")
    @patch("asiai.web.routes.bench._get_engines_for_form")
    def test_bench_page_has_advanced_details(self, mock_engines, mock_prompts, client):
        mock_engines.return_value = []
        mock_prompts.return_value = []
        response = client.get("/bench")
        assert response.status_code == 200
        assert "advanced-options" in response.text
        assert "context_size" in response.text

    @patch("asiai.web.routes.bench._get_prompts")
    @patch("asiai.web.routes.bench._get_engines_for_form")
    def test_bench_page_has_share_section_placeholder(self, mock_engines, mock_prompts, client):
        mock_engines.return_value = []
        mock_prompts.return_value = []
        response = client.get("/bench")
        assert response.status_code == 200
        assert "bench-share-section" in response.text

    def test_bench_run_conflict_when_running(self, client, app_state):
        app_state.bench_status.running = True
        response = client.post(
            "/bench/run",
            data={"model": "test"},
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 409

    @patch("asiai.web.routes.bench._run_benchmark_thread")
    def test_bench_run_quick_mode(self, mock_thread, client, app_state):
        """Quick mode should start benchmark with quick=on."""
        response = client.post(
            "/bench/run",
            data={"quick": "on"},
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "started"
        mock_thread.assert_called_once()
        # Quick mode: prompts=["code"], runs=1
        args = mock_thread.call_args
        assert args[0][3] == ["code"]  # prompt_names
        assert args[0][4] == 1  # runs

    @patch("asiai.web.routes.bench._run_benchmark_thread")
    def test_bench_run_context_size_parsed(self, mock_thread, client, app_state):
        """Context size should be parsed from form value."""
        response = client.post(
            "/bench/run",
            data={"context_size": "16k"},
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 200
        args = mock_thread.call_args
        assert args[0][6] == 16384  # context_size

    @patch("asiai.web.routes.bench._run_benchmark_thread")
    def test_bench_run_context_size_empty(self, mock_thread, client, app_state):
        """Empty context_size should default to 0."""
        response = client.post(
            "/bench/run",
            data={"context_size": ""},
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 200
        args = mock_thread.call_args
        assert args[0][6] == 0  # context_size

    @patch("asiai.web.routes.bench._run_benchmark_thread")
    def test_bench_run_context_size_invalid(self, mock_thread, client, app_state):
        """Invalid context_size should default to 0."""
        response = client.post(
            "/bench/run",
            data={"context_size": "999k"},
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 200
        args = mock_thread.call_args
        assert args[0][6] == 0  # context_size


# ---------------------------------------------------------------------------
# Bench thread — card generation
# ---------------------------------------------------------------------------


class TestBenchThread:
    @patch("asiai.web.routes.bench.run_benchmark", create=True)
    @patch("asiai.web.routes.bench.find_common_model", create=True)
    def test_thread_card_generation_success(self, mock_find, mock_run, app_state):
        """Card gen should populate card_svg_url and card_png_url on success."""
        from asiai.web.routes.bench import _run_benchmark_thread

        mock_find.return_value = "qwen2.5:7b"
        mock_bench_run = MagicMock()
        mock_bench_run.results = [{"hw_chip": "Apple M4 Pro", "tok_per_sec": 50.0}]
        mock_run.return_value = mock_bench_run

        svg_p = patch("asiai.benchmark.card.generate_card_svg", return_value="<svg></svg>")
        save_p = patch("asiai.benchmark.card.save_card", return_value="/tmp/cards/bench.svg")
        png_p = patch(
            "asiai.benchmark.card.convert_svg_to_png",
            return_value="/tmp/cards/bench.png",
        )
        store_p = patch("asiai.storage.db.store_benchmark")
        agg_p = patch("asiai.benchmark.reporter.aggregate_results", return_value={})
        with svg_p, save_p, png_p, store_p, agg_p:
            _run_benchmark_thread(app_state, "qwen2.5:7b", [], None, 1, False, 0)

        snap = app_state.get_bench_snapshot()
        assert snap["done"] is True
        assert snap["card_svg_url"] == "/cards/bench.svg"
        assert snap["card_png_url"] == "/cards/bench.png"
        assert snap["error"] == ""

    @patch("asiai.web.routes.bench.run_benchmark", create=True)
    @patch("asiai.web.routes.bench.find_common_model", create=True)
    def test_thread_card_generation_failure_non_blocking(self, mock_find, mock_run, app_state):
        """Card gen failure should not block benchmark completion."""
        from asiai.web.routes.bench import _run_benchmark_thread

        mock_find.return_value = "qwen2.5:7b"
        mock_bench_run = MagicMock()
        mock_bench_run.results = [{"hw_chip": "Apple M4 Pro"}]
        mock_run.return_value = mock_bench_run

        svg_p = patch(
            "asiai.benchmark.card.generate_card_svg",
            side_effect=RuntimeError("svg fail"),
        )
        store_p = patch("asiai.storage.db.store_benchmark")
        agg_p = patch("asiai.benchmark.reporter.aggregate_results", return_value={})
        with svg_p, store_p, agg_p:
            _run_benchmark_thread(app_state, "qwen2.5:7b", [], None, 1, False, 0)

        snap = app_state.get_bench_snapshot()
        assert snap["done"] is True
        assert snap["error"] == ""
        assert "svg fail" in snap["card_error"]

    def test_thread_no_engines(self, app_state):
        """Thread should report error when no engines available."""
        from asiai.web.routes.bench import _run_benchmark_thread

        app_state.engines = []
        _run_benchmark_thread(app_state, "test", [], None, 1, False, 0)
        snap = app_state.get_bench_snapshot()
        assert snap["done"] is True
        assert "No engines" in snap["error"]


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

    def test_cards_route_mounted(self, app_state):
        """Verify /cards/ is mounted as a static files directory."""
        app = create_app(app_state)
        route_names = [r.name for r in app.routes]
        assert "cards" in route_names

    def test_css_has_new_bench_classes(self, client):
        """Verify new CSS classes for bench v2 are present."""
        response = client.get("/static/style.css")
        assert response.status_code == 200
        assert ".btn-quick" in response.text
        assert ".bench-card-preview" in response.text
        assert ".share-url-row" in response.text
        assert ".share-actions" in response.text
        assert ".btn-muted" in response.text


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
