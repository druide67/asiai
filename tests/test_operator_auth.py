"""Operator login flow: ephemeral shell-bound codes + server-side sessions.

Covers the auth module (code lifecycle, session store, CSRF) and the
web routes (/login, /logout, /api/v1/operator/session, and the
require_operator / require_operator_csrf dependencies).
"""

from __future__ import annotations

import time

import pytest

from asiai.auth import audit
from asiai.auth import operator as operator_auth

pytest.importorskip("fastapi", reason="operator routes require FastAPI optional dep")
pytest.importorskip("httpx", reason="TestClient requires httpx")

from fastapi import Depends  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from asiai.web.app import create_app  # noqa: E402
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
def client(tmp_path, tmp_state, tmp_audit):
    state = AppState(engines=[], db_path=str(tmp_path / "bench.db"))
    app = create_app(state)

    # Test-only routes exercising the dependencies exactly as the
    # future write proxy will consume them.
    @app.post("/test-gated")
    async def _gated(
        session: operator_auth.OperatorSession = Depends(operator_routes.require_operator),
    ):
        return {"ok": True}

    @app.post("/test-gated-csrf")
    async def _gated_csrf(
        session: operator_auth.OperatorSession = Depends(operator_routes.require_operator_csrf),
    ):
        return {"ok": True}

    operator_routes._login_rate_limiter.reset()
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
    assert operator_auth.SESSION_COOKIE in resp.cookies
    info = client.get("/api/v1/operator/session", headers=_common_headers()).json()
    assert info["authenticated"] is True
    return info["csrf_token"]


class TestLoginCode:
    def test_create_then_consume(self, tmp_state):
        code = operator_auth.create_login_code()
        assert code.startswith(operator_auth.LOGIN_CODE_PREFIX)
        assert operator_auth.consume_login_code(code) is True

    def test_single_use(self, tmp_state):
        code = operator_auth.create_login_code()
        assert operator_auth.consume_login_code(code) is True
        assert operator_auth.consume_login_code(code) is False

    def test_wrong_code_keeps_pending_code(self, tmp_state):
        code = operator_auth.create_login_code()
        assert operator_auth.consume_login_code("aop_wrong") is False
        # The real code still works: a typo (or an attacker probing the
        # form) must not burn the operator's pending code.
        assert operator_auth.consume_login_code(code) is True

    def test_expired_code_rejected_and_cleaned(self, tmp_state):
        code = operator_auth.create_login_code(ttl=1.0)
        # Backdate expiry instead of sleeping.
        import json

        with open(operator_auth.LOGIN_CODE_PATH) as f:
            payload = json.load(f)
        payload["expires_at"] = time.time() - 1
        with open(operator_auth.LOGIN_CODE_PATH, "w") as f:
            json.dump(payload, f)
        assert operator_auth.consume_login_code(code) is False
        import os

        assert not os.path.exists(operator_auth.LOGIN_CODE_PATH)

    def test_no_pending_code(self, tmp_state):
        assert operator_auth.consume_login_code("aop_anything") is False

    def test_bad_prefix_rejected_without_file_read(self, tmp_state):
        operator_auth.create_login_code()
        assert operator_auth.consume_login_code("asai_not-a-login-code") is False

    def test_ttl_is_clamped(self, tmp_state):
        import json

        operator_auth.create_login_code(ttl=10_000)
        with open(operator_auth.LOGIN_CODE_PATH) as f:
            payload = json.load(f)
        assert payload["expires_at"] - payload["created_at"] <= operator_auth.MAX_LOGIN_CODE_TTL

    def test_file_is_0600(self, tmp_state):
        import os
        import stat

        operator_auth.create_login_code()
        mode = stat.S_IMODE(os.stat(operator_auth.LOGIN_CODE_PATH).st_mode)
        assert mode == 0o600


class TestSessionStore:
    def test_create_and_get(self):
        store = operator_auth.OperatorSessionStore()
        sid, session = store.create()
        assert store.get(sid) is session
        assert store.count() == 1

    def test_unknown_and_empty_sid(self):
        store = operator_auth.OperatorSessionStore()
        assert store.get("nope") is None
        assert store.get(None) is None
        assert store.get("") is None

    def test_expiry(self):
        store = operator_auth.OperatorSessionStore(ttl=0.05)
        sid, _ = store.create()
        time.sleep(0.08)
        assert store.get(sid) is None
        assert store.count() == 0

    def test_revoke(self):
        store = operator_auth.OperatorSessionStore()
        sid, _ = store.create()
        assert store.revoke(sid) is True
        assert store.revoke(sid) is False
        assert store.get(sid) is None

    def test_csrf_verify(self):
        store = operator_auth.OperatorSessionStore()
        _, session = store.create()
        assert store.verify_csrf(session, session.csrf_secret) is True
        assert store.verify_csrf(session, "wrong") is False
        assert store.verify_csrf(session, None) is False
        assert store.verify_csrf(session, "") is False


class TestLoginRoutes:
    def test_login_page_renders(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200
        assert "asiai auth login" in resp.text

    def test_login_page_redirects_when_authenticated(self, client):
        _login(client)
        resp = client.get("/login", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/"

    def test_wrong_code_401(self, client):
        resp = client.post(
            "/login",
            headers=_common_headers(),
            data={"code": "aop_wrong"},
        )
        assert resp.status_code == 401
        assert "Invalid or expired code" in resp.text

    def test_valid_code_sets_session_cookie(self, client):
        csrf = _login(client)
        assert csrf

    def test_login_rate_limited(self, client):
        for _ in range(5):
            client.post("/login", headers=_common_headers(), data={"code": "aop_wrong"})
        resp = client.post("/login", headers=_common_headers(), data={"code": "aop_wrong"})
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_session_info_unauthenticated(self, client):
        info = client.get("/api/v1/operator/session", headers=_common_headers()).json()
        assert info == {"authenticated": False}

    def test_logout_revokes_server_side(self, client):
        _login(client)
        resp = client.post("/logout", headers=_common_headers(), follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login"
        info = client.get("/api/v1/operator/session", headers=_common_headers()).json()
        assert info == {"authenticated": False}

    def test_audit_trail_written(self, client, tmp_audit):
        import json

        _login(client)
        lines = [json.loads(line) for line in tmp_audit.read_text().splitlines()]
        login_ok = [
            e
            for e in lines
            if e.get("event") == "login"
            and e.get("status") == "ok"
            and e.get("actor_type") == audit.ACTOR_OPERATOR
        ]
        assert login_ok


class TestGatedRoutes:
    def test_gated_route_rejects_anonymous(self, client):
        resp = client.post("/test-gated", headers=_common_headers())
        assert resp.status_code == 401

    def test_gated_route_accepts_session(self, client):
        _login(client)
        resp = client.post("/test-gated", headers=_common_headers())
        assert resp.status_code == 200

    def test_gated_route_rejects_stale_cookie(self, client):
        _login(client)
        client.post("/logout", headers=_common_headers(), follow_redirects=False)
        # httpx keeps the (now dead) cookie unless the server clears it;
        # force the stale value to simulate a replayed cookie.
        client.cookies.set(operator_auth.SESSION_COOKIE, "stale-session-id")
        resp = client.post("/test-gated", headers=_common_headers())
        assert resp.status_code == 401

    def test_csrf_route_rejects_missing_token(self, client):
        _login(client)
        resp = client.post("/test-gated-csrf", headers=_common_headers())
        assert resp.status_code == 403

    def test_csrf_route_accepts_header_token(self, client):
        csrf = _login(client)
        resp = client.post(
            "/test-gated-csrf",
            headers=_common_headers({"X-CSRF-Token": csrf}),
        )
        assert resp.status_code == 200

    def test_csrf_route_accepts_form_token(self, client):
        csrf = _login(client)
        resp = client.post(
            "/test-gated-csrf",
            headers=_common_headers(),
            data={"_csrf": csrf},
        )
        assert resp.status_code == 200

    def test_csrf_route_rejects_wrong_token(self, client):
        _login(client)
        resp = client.post(
            "/test-gated-csrf",
            headers=_common_headers({"X-CSRF-Token": "wrong"}),
        )
        assert resp.status_code == 403

    def test_csrf_requires_session_first(self, client):
        resp = client.post(
            "/test-gated-csrf",
            headers=_common_headers({"X-CSRF-Token": "whatever"}),
        )
        assert resp.status_code == 401
