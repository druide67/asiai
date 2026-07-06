"""Operator same-origin write proxy: POST /fleet/{nickname}/action.

The HUMAN write path (É2): operator session + CSRF, server-side typed
confirmation for destructive verbs, forward to the target node's machine
edge with the node Bearer held server-side. The machine path
(/api/v1/fleet/{nickname}/command) has its own suite and stays untouched.
"""

from __future__ import annotations

import json

import pytest

from asiai.auth import audit
from asiai.auth import operator as operator_auth
from asiai.fleet import config as fleet_config

pytest.importorskip("fastapi", reason="fleet routes require FastAPI optional dep")
pytest.importorskip("httpx", reason="TestClient requires httpx")

from fastapi.testclient import TestClient  # noqa: E402

from asiai.web.app import create_app  # noqa: E402
from asiai.web.routes import fleet as fleet_routes  # noqa: E402
from asiai.web.routes import operator as operator_routes  # noqa: E402
from asiai.web.state import AppState  # noqa: E402

_ORIGIN = "http://testserver"
_HOST = "testserver"


def _common_headers(extra: dict | None = None) -> dict:
    h = {"Origin": _ORIGIN, "Host": _HOST}
    if extra:
        h.update(extra)
    return h


@pytest.fixture
def tmp_state(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    monkeypatch.setattr(operator_auth, "STATE_DIR", str(state_dir))
    monkeypatch.setattr(
        operator_auth, "LOGIN_CODE_PATH", str(state_dir / "operator-login-code.json")
    )
    yield state_dir


@pytest.fixture
def tmp_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "AUDIT_DIR", str(tmp_path / "audit"))
    monkeypatch.setattr(audit, "AUDIT_PATH", str(tmp_path / "audit/fleet-audit.jsonl"))
    yield tmp_path / "audit/fleet-audit.jsonl"


@pytest.fixture
def tmp_fleet(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "asiai"
    monkeypatch.setattr(fleet_config, "CONFIG_DIR", str(cfg_dir))
    monkeypatch.setattr(fleet_config, "CONFIG_PATH", str(cfg_dir / "fleet.json"))
    monkeypatch.setattr(fleet_config, "LOCK_PATH", str(cfg_dir / "fleet.lock"))
    yield cfg_dir


@pytest.fixture
def client(tmp_path, tmp_state, tmp_audit, tmp_fleet):
    state = AppState(engines=[], db_path=str(tmp_path / "bench.db"))
    app = create_app(state)
    operator_routes._login_rate_limiter.reset()
    fleet_routes._operator_rate_limiter.reset()
    return TestClient(app)


def _login(client: TestClient) -> str:
    """Full login flow; returns the CSRF token."""
    code = operator_auth.create_login_code()
    resp = client.post(
        "/login",
        headers=_common_headers(),
        data={"code": code},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    info = client.get("/api/v1/operator/session", headers=_common_headers()).json()
    assert info["authenticated"] is True
    return info["csrf_token"]


def _add_node(nickname: str = "node-a", token: str | None = "asai_node_secret") -> None:
    fleet_config.upsert_node(nickname, "http://192.0.2.10:8899", auth_token=token)


def _post_action(client, csrf, nickname="node-a", body=None):
    return client.post(
        f"/fleet/{nickname}/action",
        headers=_common_headers({"X-CSRF-Token": csrf}),
        json=body or {"command": "restart", "args": {"engine": "llamacpp"}},
    )


def _read_audit(path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# --- auth gates ------------------------------------------------------------


class TestAuthGates:
    def test_no_session_401(self, client):
        resp = client.post(
            "/fleet/node-a/action",
            headers=_common_headers(),
            json={"command": "restart", "args": {"engine": "llamacpp"}},
        )
        assert resp.status_code == 401

    def test_session_without_csrf_403(self, client):
        _login(client)
        resp = client.post(
            "/fleet/node-a/action",
            headers=_common_headers(),
            json={"command": "restart", "args": {"engine": "llamacpp"}},
        )
        assert resp.status_code == 403

    def test_bad_csrf_403(self, client):
        _login(client)
        resp = _post_action(client, "not-the-token")
        assert resp.status_code == 403


# --- payload validation -----------------------------------------------------


class TestPayload:
    def test_unknown_command_400(self, client):
        csrf = _login(client)
        resp = _post_action(client, csrf, body={"command": "reboot", "args": {}})
        assert resp.status_code == 400
        assert resp.json()["error"] == "bad_payload"

    def test_bad_nickname_400(self, client):
        csrf = _login(client)
        resp = _post_action(client, csrf, nickname="..%0a")
        assert resp.status_code in (400, 404)  # route match may reject first

    def test_destructive_without_confirm_400(self, client):
        csrf = _login(client)
        _add_node()
        resp = _post_action(client, csrf, body={"command": "purge", "args": {}})
        assert resp.status_code == 400
        assert resp.json()["error"] == "confirmation_required"

    def test_destructive_confirm_mismatch_400(self, client):
        csrf = _login(client)
        _add_node()
        resp = _post_action(
            client,
            csrf,
            body={"command": "purge", "args": {}, "confirm": "wrong-node"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "confirmation_required"


# --- node resolution ----------------------------------------------------------


class TestNodeResolution:
    def test_unknown_node_404(self, client):
        csrf = _login(client)
        resp = _post_action(client, csrf, nickname="ghost")
        assert resp.status_code == 404
        assert resp.json()["error"] == "unknown_node"

    def test_node_without_token_409(self, client):
        csrf = _login(client)
        _add_node(token=None)
        resp = _post_action(client, csrf)
        assert resp.status_code == 409
        assert resp.json()["error"] == "node_not_writable"


# --- forwarding ---------------------------------------------------------------


class TestForward:
    def test_reversible_forwarded_and_audited(self, client, tmp_audit, monkeypatch):
        csrf = _login(client)
        _add_node()
        captured: dict = {}

        def fake_forward(node, command, args, timeout):
            captured.update(node=node, command=command, args=args, timeout=timeout)
            return (200, {"ok": True, "exit_code": 0})

        monkeypatch.setattr(fleet_routes, "_forward_to_node", fake_forward)
        resp = _post_action(client, csrf)
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["command"] == "restart"
        assert body["nickname"] == "node-a"
        assert captured["command"] == "restart"
        assert captured["node"]["auth_token"] == "asai_node_secret"
        # client tier: two hop margins beyond the loopback budget
        assert captured["timeout"] == pytest.approx(120.0 + 60.0)
        ops = [e for e in _read_audit(tmp_audit) if e.get("actor_type") == "operator"]
        assert any(e.get("command") == "restart" and e.get("status") == "ok" for e in ops)

    def test_destructive_with_confirm_forwarded(self, client, monkeypatch):
        csrf = _login(client)
        _add_node()
        monkeypatch.setattr(fleet_routes, "_forward_to_node", lambda *a, **k: (200, {"ok": True}))
        resp = _post_action(
            client,
            csrf,
            body={"command": "purge", "args": {}, "confirm": "node-a"},
        )
        assert resp.status_code == 200

    @pytest.mark.parametrize("command", ["enable", "disable"])
    def test_cold_standby_pair_reversible_no_confirm(self, client, monkeypatch, command):
        """enable/disable (1.18) are REVERSIBLE: accepted without a typed
        confirmation and forwarded with the engine untouched."""
        csrf = _login(client)
        _add_node()
        captured: dict = {}

        def fake_forward(node, cmd, args, timeout):
            captured.update(command=cmd, args=args)
            return (200, {"ok": True, "exit_code": 0})

        monkeypatch.setattr(fleet_routes, "_forward_to_node", fake_forward)
        resp = _post_action(
            client,
            csrf,
            body={"command": command, "args": {"engine": "llamacpp-aux-4"}},
        )
        assert resp.status_code == 200
        assert captured["command"] == command
        assert captured["args"] == {"engine": "llamacpp-aux-4"}

    def test_node_error_mapped_through(self, client, monkeypatch):
        csrf = _login(client)
        _add_node()
        monkeypatch.setattr(
            fleet_routes,
            "_forward_to_node",
            lambda *a, **k: (502, {"error": "node_unreachable"}),
        )
        resp = _post_action(client, csrf)
        assert resp.status_code == 502
        assert resp.json()["error"] == "node_unreachable"

    def test_forward_request_shape(self, client, monkeypatch):
        """_forward_to_node itself: Bearer + Origin headers, edge URL, payload."""
        seen: dict = {}

        class _Resp:
            status = 200

            def read(self, _n):
                return b'{"ok": true}'

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout):
            seen["url"] = req.full_url
            seen["headers"] = dict(req.headers)
            seen["data"] = req.data
            seen["timeout"] = timeout
            return _Resp()

        monkeypatch.setattr(fleet_routes.urllib.request, "urlopen", fake_urlopen)
        node = {
            "nickname": "node-a",
            "asiai_url": "http://192.0.2.10:8899",
            "auth_token": "asai_node_secret",
        }
        status, body = fleet_routes._forward_to_node(node, "stop", {"engine": "ollama"}, 90.0)
        assert status == 200 and body == {"ok": True}
        assert seen["url"] == "http://192.0.2.10:8899/api/v1/fleet/node-a/command"
        assert seen["headers"]["Authorization"] == "Bearer asai_node_secret"
        # Same-origin middleware on the remote edge: Origin must match its host.
        assert seen["headers"]["Origin"] == "http://192.0.2.10:8899"
        assert json.loads(seen["data"]) == {"command": "stop", "args": {"engine": "ollama"}}
        assert seen["timeout"] == 90.0


# --- rate limiting --------------------------------------------------------------


class TestRateLimit:
    def test_operator_bucket_429(self, client, monkeypatch):
        csrf = _login(client)
        _add_node()
        monkeypatch.setattr(fleet_routes, "_forward_to_node", lambda *a, **k: (200, {"ok": True}))
        for _ in range(20):
            assert _post_action(client, csrf).status_code == 200
        resp = _post_action(client, csrf)
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers


# --- review 2026-07-05 hardenings -------------------------------------------------


class TestForwardConcurrencyCap:
    def test_saturated_semaphore_503(self, client, monkeypatch):
        """All forward slots busy -> immediate 503, never thread-pool starvation."""
        csrf = _login(client)
        _add_node()
        sem = fleet_routes._forward_semaphore

        class _AlwaysLocked:
            def locked(self):
                return True

        monkeypatch.setattr(fleet_routes, "_forward_semaphore", _AlwaysLocked())
        try:
            resp = _post_action(client, csrf)
        finally:
            monkeypatch.setattr(fleet_routes, "_forward_semaphore", sem)
        assert resp.status_code == 503
        assert resp.json()["error"] == "forwards_busy"


class TestForwardErrorMapping:
    def _node(self):
        return {
            "nickname": "node-a",
            "asiai_url": "http://192.0.2.10:8899",
            "auth_token": "asai_node_secret",
        }

    def test_protocol_error_maps_502_not_500(self, monkeypatch):
        """A garbled upstream (http:// against a TLS port -> BadStatusLine)
        must return the coarse 502, never escape as an unhandled 500."""
        import http.client as http_client

        def fake_urlopen(req, timeout):
            raise http_client.BadStatusLine("\\x16\\x03\\x01")

        monkeypatch.setattr(fleet_routes.urllib.request, "urlopen", fake_urlopen)
        status, body = fleet_routes._forward_to_node(self._node(), "stop", {"engine": "x"}, 30.0)
        assert status == 502
        assert body["error"] == "node_protocol_error"

    def test_connect_timeout_maps_504(self, monkeypatch):
        """A connect-phase timeout arrives WRAPPED in URLError; it must be
        classified 504 like a read timeout, not 502 unreachable."""
        import urllib.error

        def fake_urlopen(req, timeout):
            raise urllib.error.URLError(TimeoutError("timed out"))

        monkeypatch.setattr(fleet_routes.urllib.request, "urlopen", fake_urlopen)
        status, body = fleet_routes._forward_to_node(self._node(), "stop", {"engine": "x"}, 30.0)
        assert status == 504
        assert body["error"] == "node_timeout"


# --- audit journal read (GET /api/v1/fleet/audit) ---------------------------------


class TestAuditJournal:
    def test_requires_operator_401(self, client):
        resp = client.get("/api/v1/fleet/audit", headers=_common_headers())
        assert resp.status_code == 401

    def test_events_newest_first(self, client, tmp_audit):
        _login(client)
        for i in range(3):
            audit.log_event(
                actor_type=audit.ACTOR_OPERATOR,
                nickname="node-a",
                command=f"cmd-{i}",
                status="ok",
            )
        resp = client.get("/api/v1/fleet/audit", headers=_common_headers())
        assert resp.status_code == 200
        # source IPs / token ids must never persist in a shared browser cache
        assert resp.headers["Cache-Control"] == "no-store"
        body = resp.json()
        commands = [e.get("command") for e in body["events"] if e.get("command")]
        assert commands[:3] == ["cmd-2", "cmd-1", "cmd-0"]
        assert body["count"] == len(body["events"])

    def test_limit_clamped_and_applied(self, client, tmp_audit):
        _login(client)
        for i in range(10):
            audit.log_event(actor_type=audit.ACTOR_MACHINE, command=f"cmd-{i}", status="ok")
        resp = client.get("/api/v1/fleet/audit?limit=3", headers=_common_headers())
        events = resp.json()["events"]
        # login predates the 10 commands, so the 3 newest are cmd-9/8/7
        assert [e["command"] for e in events] == ["cmd-9", "cmd-8", "cmd-7"]
        # out-of-range limits clamp instead of erroring
        low = client.get("/api/v1/fleet/audit?limit=0", headers=_common_headers())
        assert low.status_code == 200
        big = client.get("/api/v1/fleet/audit?limit=99999", headers=_common_headers())
        assert big.status_code == 200

    def test_corrupt_lines_skipped(self, client, tmp_audit):
        _login(client)
        audit.log_event(actor_type=audit.ACTOR_OPERATOR, command="good", status="ok")
        with open(tmp_audit, "a") as f:
            f.write("{not json\n")
            f.write('"a bare string"\n')
        audit.log_event(actor_type=audit.ACTOR_OPERATOR, command="good-2", status="ok")
        resp = client.get("/api/v1/fleet/audit", headers=_common_headers())
        commands = [e.get("command") for e in resp.json()["events"] if e.get("command")]
        assert commands[:2] == ["good-2", "good"]

    def test_missing_file_empty(self, client, tmp_audit, monkeypatch):
        # A session must exist, but its login event lands in the audit file;
        # point the reader at a path that was never created instead.
        _login(client)
        monkeypatch.setattr(audit, "AUDIT_PATH", str(tmp_audit) + ".nowhere")
        resp = client.get("/api/v1/fleet/audit", headers=_common_headers())
        assert resp.status_code == 200
        assert resp.json() == {"events": [], "count": 0}

    def test_rotation_straddle(self, client, tmp_audit):
        """When the current file has fewer lines than the limit, the tail
        completes from the most recent rotated backup (.1)."""
        _login(client)
        backup = str(tmp_audit) + ".1"
        with open(backup, "w") as f:
            f.write(json.dumps({"ts": 1, "command": "old-1", "status": "ok"}) + "\n")
            f.write(json.dumps({"ts": 2, "command": "old-2", "status": "ok"}) + "\n")
        audit.log_event(actor_type=audit.ACTOR_OPERATOR, command="new-1", status="ok")
        resp = client.get("/api/v1/fleet/audit?limit=10", headers=_common_headers())
        commands = [e.get("command") for e in resp.json()["events"] if e.get("command")]
        assert commands[:3] == ["new-1", "old-2", "old-1"]
