"""Local community-leaderboard view: /leaderboard page + /api/v1/leaderboard."""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("fastapi", reason="web routes require FastAPI optional dep")
pytest.importorskip("httpx", reason="TestClient requires httpx")

from fastapi.testclient import TestClient  # noqa: E402

from asiai.web.app import create_app  # noqa: E402
from asiai.web.routes import leaderboard as lb_routes  # noqa: E402
from asiai.web.state import AppState  # noqa: E402

_ENTRIES = [
    {
        "engine": "llamacpp",
        "model": "qwen3.5:4b",
        "chip": "Apple M4 Pro",
        "median_tok_s": 62.4,
        "median_ttft_ms": 210.0,
        "samples": 12,
    }
]


@pytest.fixture
def client(tmp_path):
    state = AppState(engines=[], db_path=str(tmp_path / "bench.db"))
    app = create_app(state)
    # Module-level cache must not leak between tests.
    lb_routes._cache.clear()
    return TestClient(app)


class TestLeaderboardApi:
    def test_entries_passthrough(self, client):
        with patch.object(lb_routes, "fetch_leaderboard", return_value=_ENTRIES) as m:
            resp = client.get("/api/v1/leaderboard")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["entries"][0]["engine"] == "llamacpp"
        m.assert_called_once_with(chip="", model="")

    def test_filters_forwarded(self, client):
        with patch.object(lb_routes, "fetch_leaderboard", return_value=[]) as m:
            resp = client.get("/api/v1/leaderboard?chip=Apple+M4+Pro&model=qwen3.5")
        assert resp.status_code == 200
        m.assert_called_once_with(chip="Apple M4 Pro", model="qwen3.5")

    def test_oversized_params_rejected(self, client):
        resp = client.get("/api/v1/leaderboard?chip=" + "x" * 65)
        assert resp.status_code == 422

    def test_cache_absorbs_repeat_calls(self, client):
        with patch.object(lb_routes, "fetch_leaderboard", return_value=_ENTRIES) as m:
            client.get("/api/v1/leaderboard")
            client.get("/api/v1/leaderboard")
        assert m.call_count == 1

    def test_empty_result_not_cached(self, client):
        """An unreachable community API must not stick for the full TTL."""
        with patch.object(lb_routes, "fetch_leaderboard", return_value=[]) as m:
            client.get("/api/v1/leaderboard")
            client.get("/api/v1/leaderboard")
        assert m.call_count == 2

    def test_unreachable_api_returns_empty_list(self, client):
        with patch.object(lb_routes, "fetch_leaderboard", return_value=[]):
            resp = client.get("/api/v1/leaderboard")
        assert resp.status_code == 200
        assert resp.json() == {"entries": [], "count": 0}


class TestLeaderboardPage:
    def test_page_renders_with_nav(self, client):
        # collect_hw_chip runs for real (local sysctl read) — harmless and
        # exactly what the handler does in production.
        resp = client.get("/leaderboard")
        assert resp.status_code == 200
        assert "Community Leaderboard" in resp.text
        assert "/api/v1/leaderboard" in resp.text

    def test_nav_link_present_on_other_pages(self, client):
        resp = client.get("/versions")
        assert resp.status_code == 200
        assert 'href="/leaderboard"' in resp.text
