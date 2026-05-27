"""Integration tests for POST /api/v1/fleet/{nickname}/command."""

from __future__ import annotations

import pytest

from asiai.auth import audit, loopback
from asiai.auth import config as auth_config
from asiai.fleet import config as fleet_config

pytest.importorskip("fastapi", reason="fleet routes require FastAPI optional dep")
pytest.importorskip("httpx", reason="TestClient requires httpx")

from fastapi.testclient import TestClient  # noqa: E402

from asiai.web.app import create_app  # noqa: E402
from asiai.web.routes import fleet as fleet_routes  # noqa: E402
from asiai.web.state import AppState  # noqa: E402

_ORIGIN = "http://testserver"
_HOST = "testserver"


@pytest.fixture
def tmp_auth(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "asiai"
    monkeypatch.setattr(auth_config, "CONFIG_DIR", str(cfg_dir))
    monkeypatch.setattr(auth_config, "CONFIG_PATH", str(cfg_dir / "auth.json"))
    monkeypatch.setattr(auth_config, "LOCK_PATH", str(cfg_dir / "auth.lock"))
    monkeypatch.setattr(fleet_config, "CONFIG_DIR", str(cfg_dir))
    monkeypatch.setattr(fleet_config, "CONFIG_PATH", str(cfg_dir / "fleet.json"))
    monkeypatch.setattr(fleet_config, "LOCK_PATH", str(cfg_dir / "fleet.lock"))
    yield cfg_dir


@pytest.fixture
def tmp_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "AUDIT_DIR", str(tmp_path / "audit"))
    monkeypatch.setattr(audit, "AUDIT_PATH", str(tmp_path / "audit/fleet-audit.jsonl"))
    yield tmp_path / "audit/fleet-audit.jsonl"


@pytest.fixture
def tmp_loopback(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    monkeypatch.setattr(loopback, "STATE_DIR", str(state_dir))
    monkeypatch.setattr(loopback, "TOKEN_PATH", str(state_dir / "aisctl-serve-token"))
    yield state_dir


@pytest.fixture
def client(tmp_path, tmp_auth, tmp_audit, tmp_loopback):
    state = AppState(engines=[], db_path=str(tmp_path / "bench.db"))
    app = create_app(state)
    # Reset rate limiter between tests so the suite is order-independent.
    fleet_routes._rate_limiter.reset()
    return TestClient(app)


def _common_headers(extra: dict | None = None) -> dict:
    h = {"Origin": _ORIGIN, "Host": _HOST}
    if extra:
        h.update(extra)
    return h


def _stub_proxy(status: int, body: dict):
    def _fake(command, args, internal, timeout):
        return (status, body)

    return _fake


class TestAuth:
    def test_no_bearer_returns_401(self, client):
        resp = client.post(
            "/api/v1/fleet/alpha/command",
            headers=_common_headers(),
            json={"command": "purge"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"] == "unauthorized"

    def test_no_tokens_configured_returns_501(self, client):
        # Bearer present but auth.json was never initialized → 501.
        resp = client.post(
            "/api/v1/fleet/alpha/command",
            headers=_common_headers({"Authorization": "Bearer asai_anything"}),
            json={"command": "purge"},
        )
        assert resp.status_code == 501
        assert "not_initialized" in resp.json().get("error", "")

    def test_revoked_all_tokens_falls_back_to_401(self, client):
        # auth.json exists, but every token has been revoked. The client
        # gets 401 (not 501) so it knows to refresh, not to call init.
        _, tid, secret = auth_config.init_auth()
        auth_config.revoke_token(tid)
        resp = client.post(
            "/api/v1/fleet/alpha/command",
            headers=_common_headers({"Authorization": f"Bearer {secret}"}),
            json={"command": "purge"},
        )
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        auth_config.init_auth()
        resp = client.post(
            "/api/v1/fleet/alpha/command",
            headers=_common_headers({"Authorization": "Bearer asai_wrong_secret"}),
            json={"command": "purge"},
        )
        assert resp.status_code == 401

    def test_revoked_token_falls_through_to_401(self, client):
        # When at least one OTHER token exists, presenting a revoked one
        # gets 401 (not 501) because auth.json is initialized.
        _, tid, secret = auth_config.init_auth()
        auth_config.create_token(label="other")
        auth_config.revoke_token(tid)
        resp = client.post(
            "/api/v1/fleet/alpha/command",
            headers=_common_headers({"Authorization": f"Bearer {secret}"}),
            json={"command": "purge"},
        )
        assert resp.status_code == 401


class TestPayloadValidation:
    @pytest.fixture
    def authed(self, client):
        _, _, secret = auth_config.init_auth()
        loopback.write_token()
        return client, secret

    def test_bad_json_returns_400(self, authed):
        client, secret = authed
        resp = client.post(
            "/api/v1/fleet/alpha/command",
            headers=_common_headers(
                {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}
            ),
            content=b"this is not json",
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_json"

    def test_unknown_command_returns_400(self, authed):
        client, secret = authed
        resp = client.post(
            "/api/v1/fleet/alpha/command",
            headers=_common_headers({"Authorization": f"Bearer {secret}"}),
            json={"command": "drop_database"},
        )
        assert resp.status_code == 400

    def test_engine_required_for_stop(self, authed):
        client, secret = authed
        resp = client.post(
            "/api/v1/fleet/alpha/command",
            headers=_common_headers({"Authorization": f"Bearer {secret}"}),
            json={"command": "stop", "args": {}},
        )
        assert resp.status_code == 400
        assert "engine" in resp.json().get("detail", "")

    def test_engine_regex_rejects_injection(self, authed):
        client, secret = authed
        resp = client.post(
            "/api/v1/fleet/alpha/command",
            headers=_common_headers({"Authorization": f"Bearer {secret}"}),
            json={"command": "stop", "args": {"engine": "ollama; rm -rf /"}},
        )
        assert resp.status_code == 400

    def test_purge_accepts_empty_args(self, authed, monkeypatch):
        client, secret = authed
        monkeypatch.setattr(
            fleet_routes, "_proxy_to_aisctl", _stub_proxy(200, {"ok": True, "exit_code": 0})
        )
        resp = client.post(
            "/api/v1/fleet/alpha/command",
            headers=_common_headers({"Authorization": f"Bearer {secret}"}),
            json={"command": "purge"},
        )
        assert resp.status_code == 200
        assert resp.json()["command"] == "purge"


class TestProxy:
    @pytest.fixture
    def authed(self, client):
        _, _, secret = auth_config.init_auth()
        loopback.write_token()
        return client, secret

    def test_aisctl_serve_down_returns_503(self, client):
        _, _, secret = auth_config.init_auth()
        # Do NOT call loopback.write_token() — simulates aisctl serve down.
        resp = client.post(
            "/api/v1/fleet/alpha/command",
            headers=_common_headers({"Authorization": f"Bearer {secret}"}),
            json={"command": "purge"},
        )
        assert resp.status_code == 503
        assert "aisctl_serve" in resp.json().get("error", "")

    def test_success_path_forwards_response(self, authed, monkeypatch):
        client, secret = authed
        monkeypatch.setattr(
            fleet_routes,
            "_proxy_to_aisctl",
            _stub_proxy(200, {"ok": True, "exit_code": 0, "stdout": "freed 2 GB"}),
        )
        resp = client.post(
            "/api/v1/fleet/alpha/command",
            headers=_common_headers({"Authorization": f"Bearer {secret}"}),
            json={"command": "purge"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["command"] == "purge"
        assert body["nickname"] == "alpha"
        assert "duration_ms" in body
        assert body["stdout"] == "freed 2 GB"

    def test_upstream_error_forwarded(self, authed, monkeypatch):
        client, secret = authed
        monkeypatch.setattr(
            fleet_routes,
            "_proxy_to_aisctl",
            _stub_proxy(500, {"ok": False, "error": "engine_not_installed"}),
        )
        resp = client.post(
            "/api/v1/fleet/alpha/command",
            headers=_common_headers({"Authorization": f"Bearer {secret}"}),
            json={"command": "stop", "args": {"engine": "ollama"}},
        )
        assert resp.status_code == 500
        assert resp.json()["error"] == "engine_not_installed"


class TestRateLimit:
    def test_rate_limited_after_burst(self, client, monkeypatch):
        _, _, secret = auth_config.init_auth()
        loopback.write_token()
        monkeypatch.setattr(fleet_routes, "_proxy_to_aisctl", _stub_proxy(200, {"ok": True}))
        # Tighten the limiter for this test.
        from asiai.auth.ratelimit import TokenRateLimiter

        monkeypatch.setattr(
            fleet_routes, "_rate_limiter", TokenRateLimiter(limit=3, window_seconds=60.0)
        )
        for _ in range(3):
            r = client.post(
                "/api/v1/fleet/alpha/command",
                headers=_common_headers({"Authorization": f"Bearer {secret}"}),
                json={"command": "purge"},
            )
            assert r.status_code == 200
        r = client.post(
            "/api/v1/fleet/alpha/command",
            headers=_common_headers({"Authorization": f"Bearer {secret}"}),
            json={"command": "purge"},
        )
        assert r.status_code == 429
        assert r.json()["error"] == "rate_limited"
        assert "Retry-After" in r.headers


class TestAuditLog:
    def test_audit_logs_denied(self, client, tmp_audit):
        resp = client.post(
            "/api/v1/fleet/alpha/command",
            headers=_common_headers(),
            json={"command": "purge"},
        )
        assert resp.status_code == 401
        # The audit file may not exist yet if writes failed silently;
        # but a 401 must produce one denied line.
        assert tmp_audit.exists()
        import json as _json

        lines = [_json.loads(ln) for ln in tmp_audit.read_text().splitlines() if ln.strip()]
        assert any(line["status"] == "denied" and line["nickname"] == "alpha" for line in lines)

    def test_audit_redacts_args(self, client, tmp_audit, monkeypatch):
        _, _, secret = auth_config.init_auth()
        loopback.write_token()
        monkeypatch.setattr(fleet_routes, "_proxy_to_aisctl", _stub_proxy(200, {"ok": True}))
        # Send an arg with a suspicious key — must be redacted in the log.
        client.post(
            "/api/v1/fleet/alpha/command",
            headers=_common_headers({"Authorization": f"Bearer {secret}"}),
            json={"command": "stop", "args": {"engine": "ollama", "secret_password": "leak"}},
        )
        import json as _json

        lines = [_json.loads(ln) for ln in tmp_audit.read_text().splitlines() if ln.strip()]
        ok_lines = [line for line in lines if line.get("status") == "ok"]
        assert ok_lines
        last = ok_lines[-1]
        # Suspicious key was stripped (we drop it during validation, but
        # if any redaction occurred, the value must not be the plaintext).
        if "secret_password" in last.get("args", {}):
            assert last["args"]["secret_password"] == "***"
