"""Integration tests for the FastAPI fleet routes."""

from __future__ import annotations

import pytest

from asiai.fleet import config as fleet_config
from asiai.fleet.poll import NodePoll

pytest.importorskip("fastapi", reason="fleet routes require FastAPI optional dep")
pytest.importorskip("httpx", reason="TestClient requires httpx")

from fastapi.testclient import TestClient  # noqa: E402

from asiai.web.app import create_app  # noqa: E402
from asiai.web.routes import fleet as fleet_routes  # noqa: E402
from asiai.web.state import AppState  # noqa: E402


@pytest.fixture
def tmp_fleet(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "asiai"
    cfg_path = cfg_dir / "fleet.json"
    monkeypatch.setattr(fleet_config, "CONFIG_DIR", str(cfg_dir))
    monkeypatch.setattr(fleet_config, "CONFIG_PATH", str(cfg_path))
    yield cfg_path


@pytest.fixture
def client(tmp_path, tmp_fleet):
    state = AppState(engines=[], db_path=str(tmp_path / "bench.db"))
    app = create_app(state)
    # Reset rate limiter between tests so the suite is order-independent.
    fleet_routes._rate_limiter.reset()
    return TestClient(app)


def _fake_poll_one_ok(nickname, url, timeout=5.0):
    return NodePoll(
        nickname=nickname,
        url=url,
        ok=True,
        latency_ms=12.0,
        snapshot={
            "engines_status": [
                {"name": "ollama", "reachable": True, "models": [{"name": "llama3.2"}]}
            ]
        },
        error=None,
        reached_at=1700000000,
    )


class TestFleetNodesEndpoint:
    def test_empty_fleet_returns_empty_list(self, client):
        resp = client.get("/api/v1/fleet/nodes")
        assert resp.status_code == 200
        assert resp.json() == {"nodes": []}

    def test_nodes_listed_without_auth_token(self, client):
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899", auth_token="SECRET_TOKEN")
        resp = client.get("/api/v1/fleet/nodes")
        assert resp.status_code == 200
        nodes = resp.json()["nodes"]
        assert len(nodes) == 1
        # auth_token must never be echoed in the HTTP response.
        assert "auth_token" not in nodes[0]
        assert "SECRET_TOKEN" not in resp.text

    def test_last_status_normalized_on_public_api(self, client):
        # Internal fleet.json stores exception class names for debugging;
        # the public API must not leak them (LAN fingerprinting risk).
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899")
        fleet_config.touch_node_status("alpha", ok=False, error="ConnectionRefusedError")
        resp = client.get("/api/v1/fleet/nodes")
        assert resp.status_code == 200
        node = resp.json()["nodes"][0]
        # Raw exception name must NOT appear in the public payload.
        assert "ConnectionRefusedError" not in resp.text
        # Status is mapped to the public 3-value enum.
        assert node["last_status"] in {"ok", "unreachable", "error", "unknown"}
        assert node["last_status"] == "unreachable"


class TestFleetSnapshotEndpoint:
    def test_empty_fleet_snapshot(self, client):
        resp = client.get("/api/v1/fleet/snapshot")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["nodes"] == []
        assert "polled_at" in payload

    def test_snapshot_aggregates_poll_results(self, client, monkeypatch):
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899")
        fleet_config.upsert_node("beta", "http://192.0.2.2:8899")
        monkeypatch.setattr(
            fleet_routes,
            "poll_all",
            lambda nodes, timeout=5.0: [
                _fake_poll_one_ok(n["nickname"], n["asiai_url"]) for n in nodes
            ],
        )
        resp = client.get("/api/v1/fleet/snapshot")
        assert resp.status_code == 200
        payload = resp.json()
        assert len(payload["nodes"]) == 2
        nicks = {n["nickname"] for n in payload["nodes"]}
        assert nicks == {"alpha", "beta"}

    def test_snapshot_cache_hit_on_second_call(self, client, monkeypatch):
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899")
        call_count = {"n": 0}

        def counting_poll(nodes, timeout=5.0):
            call_count["n"] += 1
            return [_fake_poll_one_ok(n["nickname"], n["asiai_url"]) for n in nodes]

        monkeypatch.setattr(fleet_routes, "poll_all", counting_poll)
        client.get("/api/v1/fleet/snapshot")
        client.get("/api/v1/fleet/snapshot")
        # Cache TTL is 10s, second call must reuse the cached result.
        assert call_count["n"] == 1


class TestHealthSummaryEndpoint:
    """Reduced alert feed for the cross-page nav dot (global shell)."""

    def test_empty_fleet(self, client):
        resp = client.get("/api/v1/fleet/health-summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["unhealthy_engines"] == 0
        assert body["unreachable_nodes"] == 0
        assert body["total_nodes"] == 0
        # An alert must never be served stale from a browser/proxy cache.
        assert resp.headers["cache-control"] == "no-store"

    def test_counts_franc_alarms_only(self, client, monkeypatch):
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899")
        fleet_config.upsert_node("beta", "http://192.0.2.2:8899")

        def fake_poll(nodes, timeout=5.0):
            return [
                NodePoll(
                    nickname="alpha",
                    url="http://192.0.2.1:8899",
                    ok=True,
                    latency_ms=5.0,
                    snapshot={
                        "engines_status": [
                            {"name": "a", "state": "unhealthy"},
                            {"name": "b", "state": "degraded"},
                            # Dormant/foreign states are NOT alarms:
                            {"name": "c", "state": "stopped"},
                            {"name": "d", "state": "available"},
                            {"name": "e"},  # no rich state at all
                        ]
                    },
                    error=None,
                    reached_at=1700000000,
                ),
                NodePoll(
                    nickname="beta",
                    url="http://192.0.2.2:8899",
                    ok=False,
                    latency_ms=0.0,
                    snapshot=None,
                    error="ConnectionRefusedError",
                    reached_at=1700000000,
                ),
            ]

        monkeypatch.setattr(fleet_routes, "poll_all", fake_poll)
        resp = client.get("/api/v1/fleet/health-summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["unhealthy_engines"] == 2
        assert body["unreachable_nodes"] == 1
        assert body["total_nodes"] == 2


class TestGlobalShell:
    """The Lot-1 shell: topbar on regular pages, none on the cockpit/login,
    per-page vendor payloads (audit finding: htmx/SSE/ApexCharts were dead
    weight on cockpit/journal/login)."""

    def test_fleet_page_has_no_topbar_and_no_vendors(self, client):
        resp = client.get("/fleet")
        assert resp.status_code == 200
        assert "sh-topbar" not in resp.text
        assert "apexcharts" not in resp.text
        assert "htmx" not in resp.text
        # The shell script still loads (it feeds the nav alert dot).
        assert "shell.js" in resp.text
        assert "sh-fleet-attn" in resp.text

    def test_login_page_has_no_topbar_and_no_vendors(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200
        assert "sh-topbar" not in resp.text
        assert "apexcharts" not in resp.text

    def test_regular_page_keeps_topbar(self, client):
        """The shell topbar carries the operator session everywhere; the
        mono node select is GONE (Lot 2: node scoping lives in the pages —
        multi-select chips on multi-node pages, master column in the
        cockpit). /versions is a page that kept its vendors."""
        resp = client.get("/versions")
        assert resp.status_code == 200
        assert "sh-topbar" in resp.text
        assert "sh-session" in resp.text
        assert "sh-node-select" not in resp.text
        assert "shell.js" in resp.text
        assert "htmx" in resp.text  # vendors preserved on htmx pages


class TestFleetCommandSurface:
    """Smoke tests for the Phase 2 write endpoint mounted by Phase 1.

    Detailed behavior (auth, whitelist, rate limit, audit, proxy) lives
    in ``test_fleet_command_route.py``; here we just verify the route
    is registered and that the CSRF middleware still gates POSTs.
    """

    def test_post_command_without_bearer_returns_401(self, client):
        resp = client.post(
            "/api/v1/fleet/alpha/command",
            headers={"Origin": "http://testserver", "Host": "testserver"},
        )
        assert resp.status_code == 401

    def test_post_command_without_origin_rejected(self, client):
        # Sanity: the CSRF middleware blocks POST without Origin.
        resp = client.post("/api/v1/fleet/alpha/command")
        assert resp.status_code == 403


class TestFleetPage:
    def test_page_empty_fleet_renders(self, client):
        resp = client.get("/fleet")
        assert resp.status_code == 200
        assert "No nodes configured" in resp.text

    def test_page_with_nodes_renders_cockpit_shell(self, client):
        # The cockpit is client-rendered from /api/v1/fleet/snapshot: the
        # page must ship the shell (master column + detail panel hooks)
        # and NOT block on a server-side poll.
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899")
        resp = client.get("/fleet")
        assert resp.status_code == 200
        assert 'id="fl-root"' in resp.text
        assert 'id="fl-master-list"' in resp.text
        assert "fleet.js" in resp.text
        assert "No nodes configured" not in resp.text


class TestFleetXssRegression:
    """The cockpit shell must never interpolate poll data server-side.

    Node poll data (nicknames, engine names, remote error strings) is
    attacker-influenced; it reaches the DOM only through fleet.js, which
    renders exclusively via createElement/textContent. This test guards
    against a future PR routing poll results back through the Jinja
    template, where a ``|safe`` or autoescape change could turn /fleet
    into a stored-XSS sink again."""

    def test_poll_data_never_rendered_server_side(self, client, monkeypatch):
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899")

        def fake_poll(nodes, timeout=5.0):
            return [
                NodePoll(
                    nickname="alpha",
                    url="http://192.0.2.1:8899",
                    ok=False,
                    latency_ms=0.0,
                    snapshot=None,
                    error="<script>alert('xss')</script>",
                    reached_at=1700000000,
                )
            ]

        monkeypatch.setattr(fleet_routes, "poll_all", fake_poll)
        resp = client.get("/fleet")
        assert resp.status_code == 200
        assert "<script>alert" not in resp.text
        # The page renders the shell only — poll payloads stay in JSON.
        assert "alert" not in resp.text


class TestFleetGridFragmentRemoved:
    def test_fragment_route_is_gone(self, client):
        # The HTMX grid fragment was replaced by the client-rendered
        # cockpit (2026-07); a leftover route would resurrect the
        # server-side rendering path the XSS regression test guards.
        resp = client.get("/fleet/grid-fragment")
        assert resp.status_code == 404


class TestJournalPage:
    def test_page_renders_shell(self, client):
        # The page shell is public; the DATA behind it
        # (/api/v1/fleet/audit) requires an operator session.
        resp = client.get("/journal")
        assert resp.status_code == 200
        assert 'data-fl-page="journal"' in resp.text
        assert "fleet.js" in resp.text


class TestNodeReadProxy:
    """GET /api/v1/fleet/{nickname}/{endpoint} — whitelisted read proxy."""

    def _add_node(self, nickname="m4", url="http://192.0.2.10:8899"):
        fleet_config.upsert_node(nickname, url)

    def test_unknown_endpoint_404(self, client, tmp_fleet):
        self._add_node()
        resp = client.get("/api/v1/fleet/m4/command")
        assert resp.status_code == 404
        assert resp.json()["error"] == "unknown_endpoint"

    def test_unknown_node_404(self, client, tmp_fleet):
        resp = client.get("/api/v1/fleet/ghost/history")
        assert resp.status_code == 404
        assert resp.json()["error"] == "unknown_node"

    def test_invalid_nickname_400(self, client, tmp_fleet):
        resp = client.get("/api/v1/fleet/%0abad/history")
        assert resp.status_code == 400

    @pytest.mark.parametrize(
        "endpoint,node_path",
        [
            ("history", "/api/history"),
            ("benchmarks", "/api/benchmarks"),
            ("engine-history", "/api/engine-history"),
            ("benchmark-process", "/api/benchmark-process"),
            ("doctor", "/api/v1/doctor"),
        ],
    )
    def test_proxies_whitelisted_endpoints(self, client, tmp_fleet, endpoint, node_path):
        from unittest.mock import MagicMock, patch

        self._add_node()
        body = b'{"ok": true}'
        resp_mock = MagicMock()
        resp_mock.read.return_value = body
        resp_mock.__enter__ = MagicMock(return_value=resp_mock)
        resp_mock.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=resp_mock) as mock_open:
            resp = client.get(f"/api/v1/fleet/m4/{endpoint}?hours=24")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        req = mock_open.call_args[0][0]
        assert req.full_url.startswith("http://192.0.2.10:8899" + node_path)

    def test_query_whitelist_drops_junk(self, client, tmp_fleet):
        from unittest.mock import MagicMock, patch

        self._add_node()
        resp_mock = MagicMock()
        resp_mock.read.return_value = b"[]"
        resp_mock.__enter__ = MagicMock(return_value=resp_mock)
        resp_mock.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=resp_mock) as mock_open:
            client.get(
                "/api/v1/fleet/m4/history?hours=24&since=abc&evil=1%3B rm&until=170000&model=x"
            )
        url = mock_open.call_args[0][0].full_url
        assert "hours=24" in url
        assert "until=170000" in url
        assert "since" not in url  # non-digit value dropped
        assert "evil" not in url  # not whitelisted
        assert "model" not in url  # not whitelisted for history

    def test_node_unreachable_maps_502(self, client, tmp_fleet):
        from unittest.mock import patch
        from urllib.error import URLError

        self._add_node()
        with patch("urllib.request.urlopen", side_effect=URLError("refused")):
            resp = client.get("/api/v1/fleet/m4/history")
        assert resp.status_code == 502
        assert resp.json()["error"] == "node_unreachable"

    def test_node_http_error_maps_502(self, client, tmp_fleet):
        from unittest.mock import patch
        from urllib.error import HTTPError

        self._add_node()
        err = HTTPError(url="x", code=500, msg="boom", hdrs=None, fp=None)
        with patch("urllib.request.urlopen", side_effect=err):
            resp = client.get("/api/v1/fleet/m4/doctor")
        assert resp.status_code == 502
        body = resp.json()
        assert body["error"] == "node_http_error"
        assert body["node_status"] == 500


class TestDoctorApi:
    def test_doctor_json(self, client):
        from unittest.mock import patch

        checks = [
            {
                "category": "system",
                "name": "Apple Silicon",
                "status": "ok",
                "message": "arm64",
                "fix": None,
            }
        ]
        with patch("asiai.web.routes.doctor._run_checks", return_value=checks):
            resp = client.get("/api/v1/doctor")
        assert resp.status_code == 200
        body = resp.json()
        assert body["checks"] == checks
        assert isinstance(body["ts"], int)

    def test_doctor_json_drops_secret_categories(self, client):
        """The JSON twin must never expose checks the HTML hides — the
        webhook URL (alerting) and daemon PIDs are secret-bearing."""
        from unittest.mock import patch

        checks = [
            {"category": "system", "name": "RAM", "status": "ok", "message": "128 GB"},
            {
                "category": "alerting",
                "name": "Webhook URL",
                "status": "ok",
                "message": "https://hooks.slack.com/services/T00/B00/XXXXSECRET",
            },
            {"category": "daemon", "name": "monitor", "status": "ok", "message": "pid 4242"},
        ]
        with patch("asiai.web.routes.doctor._run_checks", return_value=checks):
            resp = client.get("/api/v1/doctor")
        body = resp.json()
        cats = {c["category"] for c in body["checks"]}
        assert cats == {"system"}
        assert "XXXXSECRET" not in str(body)
        assert "pid 4242" not in str(body)
