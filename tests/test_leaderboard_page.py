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
    # Module-level cache and rate-limit state must not leak between tests.
    lb_routes._cache.clear()
    lb_routes._rate_limiter = lb_routes.TokenRateLimiter(limit=60, window_seconds=60.0)
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

    def test_rate_limited_returns_429(self, client):
        lb_routes._rate_limiter = lb_routes.TokenRateLimiter(limit=2, window_seconds=60.0)
        with patch.object(lb_routes, "fetch_leaderboard", return_value=_ENTRIES):
            assert client.get("/api/v1/leaderboard").status_code == 200
            assert client.get("/api/v1/leaderboard").status_code == 200
            resp = client.get("/api/v1/leaderboard")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers


class TestLeaderboardPage:
    def test_page_renders_with_nav(self, client):
        # collect_hw_chip runs for real (local sysctl read) — harmless and
        # exactly what the handler does in production.
        resp = client.get("/leaderboard")
        assert resp.status_code == 200
        assert "Community Leaderboard" in resp.text
        assert "/api/v1/leaderboard" in resp.text

    def test_local_chip_button_renders_valid_attribute(self, client):
        # Regression: chip names contain spaces (and could contain quotes);
        # an inline onclick with tojson produced a broken attribute that
        # killed the "This machine" filter on every real machine.
        with patch(
            "asiai.collectors.system.collect_hw_chip",
            return_value='Apple "M4" Pro',
        ):
            resp = client.get("/leaderboard")
        assert resp.status_code == 200
        import re

        m = re.search(r"<button[^>]*id=\"lb-chip-local\"[^>]*>", resp.text)
        assert m, "local chip button missing"
        button = m.group(0)
        # The chip lands in data-chip, HTML-escaped — never in inline JS.
        assert "onclick" not in button
        assert 'data-chip="Apple &#34;M4&#34; Pro"' in button

    def test_client_quick_wins_present(self, client):
        """Column sort, engine chips, tok/s bars and result counter ship in the page."""
        resp = client.get("/leaderboard")
        assert resp.status_code == 200
        # Sortable headers with data keys (default sort = tok/s descending).
        assert 'class="text-right sortable sort-desc" data-key="median_tok_s"' in resp.text
        assert 'data-key="engine"' in resp.text
        # Engine chips are injected client-side into a dedicated mount point.
        assert 'id="lb-engine-chips"' in resp.text
        # Results counter follows the active filters.
        assert 'id="lb-count"' in resp.text
        # Proportional tok/s mini-bar class used by the renderer.
        assert "lb-bar" in resp.text

    def test_nav_link_present_on_other_pages(self, client):
        resp = client.get("/versions")
        assert resp.status_code == 200
        assert 'href="/leaderboard"' in resp.text
