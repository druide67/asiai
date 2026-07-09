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
        m.assert_called_once_with(chip="", model="", days=90)

    def test_filters_forwarded(self, client):
        with patch.object(lb_routes, "fetch_leaderboard", return_value=[]) as m:
            resp = client.get("/api/v1/leaderboard?chip=Apple+M4+Pro&model=qwen3.5")
        assert resp.status_code == 200
        m.assert_called_once_with(chip="Apple M4 Pro", model="qwen3.5", days=90)

    def test_days_forwarded(self, client):
        with patch.object(lb_routes, "fetch_leaderboard", return_value=[]) as m:
            resp = client.get("/api/v1/leaderboard?days=30")
        assert resp.status_code == 200
        m.assert_called_once_with(chip="", model="", days=30)

    def test_days_out_of_range_rejected(self, client):
        assert client.get("/api/v1/leaderboard?days=0").status_code == 422
        assert client.get("/api/v1/leaderboard?days=366").status_code == 422
        assert client.get("/api/v1/leaderboard?days=abc").status_code == 422

    def test_oversized_params_rejected(self, client):
        resp = client.get("/api/v1/leaderboard?chip=" + "x" * 65)
        assert resp.status_code == 422

    def test_cache_absorbs_repeat_calls(self, client):
        with patch.object(lb_routes, "fetch_leaderboard", return_value=_ENTRIES) as m:
            client.get("/api/v1/leaderboard")
            client.get("/api/v1/leaderboard")
        assert m.call_count == 1

    def test_cache_key_includes_days(self, client):
        """Different windows are different cache entries — never cross-served."""
        with patch.object(lb_routes, "fetch_leaderboard", return_value=_ENTRIES) as m:
            client.get("/api/v1/leaderboard?days=30")
            client.get("/api/v1/leaderboard?days=90")
            client.get("/api/v1/leaderboard?days=30")
        assert m.call_count == 2
        windows = sorted(c.kwargs["days"] for c in m.call_args_list)
        assert windows == [30, 90]

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


_SUBMISSIONS = {
    "results": [
        {
            "id": "b7f6f3a2-0000-4000-8000-000000000001",
            "submitted_at": "2026-07-01T10:00:00Z",
            "hw_chip": "Apple M4 Pro",
            "hw_ram_gb": 64,
            "model": "qwen3.5:4b",
            "engine": "llamacpp",
            "engine_version": "b4521",
            "quantization": "Q4_K_M",
            "median_tok_s": 62.4,
            "card_url": "https://api.asiai.dev/card/b7f6f3a2",
        }
    ],
    "meta": {"total": 1, "limit": 25, "offset": 0, "window_days": 90},
}


class TestLeaderboardSubmissionsApi:
    def test_passthrough(self, client):
        with patch.object(lb_routes, "fetch_benchmarks", return_value=_SUBMISSIONS) as m:
            resp = client.get("/api/v1/leaderboard/submissions?chip=Apple+M4+Pro&model=qwen3.5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["results"][0]["engine"] == "llamacpp"
        assert body["meta"]["total"] == 1
        m.assert_called_once_with(
            chip="Apple M4 Pro", model="qwen3.5", engine="", days=90, limit=25, offset=0
        )

    def test_optional_params_forwarded(self, client):
        with patch.object(lb_routes, "fetch_benchmarks", return_value=_SUBMISSIONS) as m:
            resp = client.get(
                "/api/v1/leaderboard/submissions"
                "?chip=M4&model=qwen&engine=llamacpp&days=30&limit=10&offset=20"
            )
        assert resp.status_code == 200
        m.assert_called_once_with(
            chip="M4", model="qwen", engine="llamacpp", days=30, limit=10, offset=20
        )

    def test_missing_required_params_rejected(self, client):
        assert client.get("/api/v1/leaderboard/submissions").status_code == 422
        assert client.get("/api/v1/leaderboard/submissions?chip=M4").status_code == 422
        assert client.get("/api/v1/leaderboard/submissions?model=qwen").status_code == 422

    def test_invalid_charset_rejected_locally(self, client):
        """Bad charset must 422 locally, never burn an outbound call."""
        with patch.object(lb_routes, "fetch_benchmarks") as m:
            resp = client.get("/api/v1/leaderboard/submissions?chip=M4%3Cscript%3E&model=qwen")
        assert resp.status_code == 422
        m.assert_not_called()

    def test_pagination_bounds_rejected(self, client):
        base = "/api/v1/leaderboard/submissions?chip=M4&model=qwen"
        assert client.get(base + "&limit=0").status_code == 422
        assert client.get(base + "&limit=101").status_code == 422
        assert client.get(base + "&offset=-1").status_code == 422

    def test_upstream_unavailable_degrades_to_404(self, client):
        """The community endpoint may not be deployed yet (404 upstream)."""
        with patch.object(lb_routes, "fetch_benchmarks", return_value=None):
            resp = client.get("/api/v1/leaderboard/submissions?chip=M4&model=qwen")
        assert resp.status_code == 404
        assert resp.json() == {"error": "detail_unavailable"}

    def test_upstream_404_via_urlopen(self, client):
        """End-to-end degradation: HTTPError 404 in community.fetch_benchmarks."""
        from io import BytesIO
        from urllib.error import HTTPError

        exc = HTTPError("https://api.asiai.dev", 404, "Not Found", {}, BytesIO(b""))
        with patch("asiai.community.urlopen", side_effect=exc):
            resp = client.get("/api/v1/leaderboard/submissions?chip=M4&model=qwen")
        assert resp.status_code == 404
        assert resp.json() == {"error": "detail_unavailable"}

    def test_rate_limited_returns_429(self, client):
        lb_routes._rate_limiter = lb_routes.TokenRateLimiter(limit=1, window_seconds=60.0)
        with patch.object(lb_routes, "fetch_benchmarks", return_value=_SUBMISSIONS):
            assert (
                client.get("/api/v1/leaderboard/submissions?chip=M4&model=qwen").status_code == 200
            )
            resp = client.get("/api/v1/leaderboard/submissions?chip=M4&model=qwen")
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

    def test_v2_columns_present(self, client):
        """Quant, W, tok/s/W and Last seen ship as sortable columns."""
        resp = client.get("/leaderboard")
        assert resp.status_code == 200
        assert 'data-key="quantizations"' in resp.text
        assert 'data-key="median_power_watts"' in resp.text
        assert 'data-key="median_tok_s_per_watt"' in resp.text
        assert 'data-key="last_submitted_at"' in resp.text
        # Freshness dot classes: green <30d, neutral 30-90d, degraded beyond.
        assert "lb-seen-dot" in resp.text
        assert "st-degraded" in resp.text

    def test_window_selector_present(self, client):
        """30/90/365-day window chips drive the proxied days parameter."""
        resp = client.get("/leaderboard")
        assert resp.status_code == 200
        assert 'id="lb-days-chips"' in resp.text
        for days in ("30", "90", "365"):
            assert f'data-days="{days}"' in resp.text

    def test_drilldown_wiring_present(self, client):
        """Row expand fetches the local submissions proxy and degrades quietly."""
        resp = client.get("/leaderboard")
        assert resp.status_code == 200
        assert "/api/v1/leaderboard/submissions" in resp.text
        assert "Per-submission detail unavailable." in resp.text
        # No inline handlers in the leaderboard markup/script: community
        # data stays out of HTML attributes (base.html theme toggle is
        # upstream of this block and uses no remote data).
        leaderboard_block = resp.text.split("Community Leaderboard", 1)[1]
        assert "onclick" not in leaderboard_block

    def test_nav_link_present_on_other_pages(self, client):
        resp = client.get("/versions")
        assert resp.status_code == 200
        assert 'href="/leaderboard"' in resp.text
