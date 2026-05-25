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


class TestFleetCommandStub:
    def test_post_command_returns_501(self, client):
        # The CSRF middleware requires a matching Origin header on POST.
        resp = client.post(
            "/api/v1/fleet/alpha/command",
            headers={"Origin": "http://testserver", "Host": "testserver"},
        )
        assert resp.status_code == 501
        body = resp.json()
        assert body["error"] == "not_implemented"
        assert body["nickname"] == "alpha"

    def test_post_command_without_origin_rejected(self, client):
        # Sanity: the CSRF middleware blocks POST without Origin.
        resp = client.post("/api/v1/fleet/alpha/command")
        assert resp.status_code == 403


class TestFleetPage:
    def test_page_empty_fleet_renders(self, client):
        resp = client.get("/fleet")
        assert resp.status_code == 200
        assert "No nodes configured" in resp.text

    def test_page_with_nodes_renders_cards(self, client, monkeypatch):
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899")
        monkeypatch.setattr(
            fleet_routes,
            "poll_all",
            lambda nodes, timeout=5.0: [
                _fake_poll_one_ok(n["nickname"], n["asiai_url"]) for n in nodes
            ],
        )
        resp = client.get("/fleet")
        assert resp.status_code == 200
        assert "alpha" in resp.text
        assert "ollama" in resp.text


class TestFleetXssRegression:
    """Jinja2 autoescape is ON by default; this test guards against a
    future PR that would add ``|safe`` or disable autoescape and turn the
    /fleet page into a stored-XSS sink via the nickname or error fields."""

    def test_xss_in_error_message_is_escaped(self, client, monkeypatch):
        # nickname goes through _validate_nickname (regex), so it cannot
        # contain "<". But the `error` field is uncontrolled (comes from
        # the remote response) — that's the realistic XSS vector.
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
        # The literal <script> tag must NEVER appear unescaped in the
        # rendered HTML. Either autoescape produces &lt;script&gt; or
        # Jinja's HTML-escape strips it entirely.
        assert "<script>alert" not in resp.text
        assert "&lt;script&gt;" in resp.text or "alert" not in resp.text


class TestFleetGridFragment:
    def test_fragment_returns_html_not_json(self, client, monkeypatch):
        # Regression: the /fleet HTMX auto-refresh must hit an HTML
        # endpoint, not the JSON snapshot endpoint, otherwise raw JSON
        # would be swapped into the DOM on every 10s tick.
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899")
        monkeypatch.setattr(
            fleet_routes,
            "poll_all",
            lambda nodes, timeout=5.0: [
                _fake_poll_one_ok(n["nickname"], n["asiai_url"]) for n in nodes
            ],
        )
        resp = client.get("/fleet/grid-fragment")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert "<div" in resp.text
        assert "alpha" in resp.text
        assert "ollama" in resp.text
