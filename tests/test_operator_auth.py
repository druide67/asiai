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
        assert operator_auth.consume_login_code(code) == operator_auth.SCOPE_FULL

    def test_single_use(self, tmp_state):
        code = operator_auth.create_login_code()
        assert operator_auth.consume_login_code(code) == operator_auth.SCOPE_FULL
        assert operator_auth.consume_login_code(code) is None

    def test_wrong_code_keeps_pending_code(self, tmp_state):
        code = operator_auth.create_login_code()
        assert operator_auth.consume_login_code("aop_wrong") is None
        # The real code still works: a typo (or an attacker probing the
        # form) must not burn the operator's pending code.
        assert operator_auth.consume_login_code(code) == operator_auth.SCOPE_FULL

    def test_expired_code_rejected_and_cleaned(self, tmp_state):
        code = operator_auth.create_login_code(ttl=1.0)
        # Backdate expiry instead of sleeping.
        import json

        with open(operator_auth.LOGIN_CODE_PATH) as f:
            payload = json.load(f)
        payload["expires_at"] = time.time() - 1
        with open(operator_auth.LOGIN_CODE_PATH, "w") as f:
            json.dump(payload, f)
        assert operator_auth.consume_login_code(code) is None
        import os

        assert not os.path.exists(operator_auth.LOGIN_CODE_PATH)

    def test_no_pending_code(self, tmp_state):
        assert operator_auth.consume_login_code("aop_anything") is None

    def test_bad_prefix_rejected_without_file_read(self, tmp_state):
        operator_auth.create_login_code()
        assert operator_auth.consume_login_code("asai_not-a-login-code") is None

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

    def test_clamp_login_ttl(self):
        assert operator_auth.clamp_login_ttl(600) == operator_auth.MAX_LOGIN_CODE_TTL
        assert operator_auth.clamp_login_ttl(0.5) == 1.0
        assert operator_auth.clamp_login_ttl(-5) == 1.0
        assert operator_auth.clamp_login_ttl(60) == 60.0


class TestLoginCodeScope:
    """Scope is bound to the code at mint (gate condition 1)."""

    def test_scope_written_at_mint(self, tmp_state):
        import json

        operator_auth.create_login_code(scope=operator_auth.SCOPE_AUDIT_READ)
        with open(operator_auth.LOGIN_CODE_PATH) as f:
            payload = json.load(f)
        assert payload["scope"] == operator_auth.SCOPE_AUDIT_READ

    def test_consume_returns_mint_scope(self, tmp_state):
        code = operator_auth.create_login_code(scope=operator_auth.SCOPE_AUDIT_READ)
        assert operator_auth.consume_login_code(code) == operator_auth.SCOPE_AUDIT_READ

    def test_unknown_scope_refused_at_mint(self, tmp_state):
        with pytest.raises(ValueError):
            operator_auth.create_login_code(scope="root")

    def test_pre_scope_file_reads_as_full(self, tmp_state):
        """A code file minted by a pre-scope CLI has no scope field —
        its only possible intent was full access."""
        import json

        code = operator_auth.create_login_code()
        with open(operator_auth.LOGIN_CODE_PATH) as f:
            payload = json.load(f)
        del payload["scope"]
        with open(operator_auth.LOGIN_CODE_PATH, "w") as f:
            json.dump(payload, f)
        assert operator_auth.consume_login_code(code) == operator_auth.SCOPE_FULL

    def test_unknown_scope_in_file_fails_closed(self, tmp_state):
        import json

        code = operator_auth.create_login_code()
        with open(operator_auth.LOGIN_CODE_PATH) as f:
            payload = json.load(f)
        payload["scope"] = "root"
        with open(operator_auth.LOGIN_CODE_PATH, "w") as f:
            json.dump(payload, f)
        assert operator_auth.consume_login_code(code) is None

    def test_session_store_refuses_unknown_scope(self, tmp_state):
        store = operator_auth.OperatorSessionStore()
        with pytest.raises(ValueError):
            store.create(scope="root")

    def test_cli_mints_audit_read_scope(self, tmp_state, capsys):
        import argparse
        import json as _json

        from asiai.auth import cli as auth_cli

        args = argparse.Namespace(action="login", ttl=60.0, scope="audit:read", json=True)
        assert auth_cli.cmd_auth(args) == 0
        payload = _json.loads(capsys.readouterr().out)
        assert payload["scope"] == "audit:read"
        assert operator_auth.consume_login_code(payload["code"]) == operator_auth.SCOPE_AUDIT_READ


class TestLoginCLI:
    def test_cli_reports_effective_ttl_not_raw(self, tmp_state, capsys):
        import argparse

        from asiai.auth import cli as auth_cli

        args = argparse.Namespace(action="login", ttl=600.0, json=True)
        rc = auth_cli.cmd_auth(args)
        assert rc == 0
        out = capsys.readouterr().out
        import json as _json

        payload = _json.loads(out)
        # Reported expiry must be the clamped value (300), not the raw 600.
        assert payload["expires_in"] == int(operator_auth.MAX_LOGIN_CODE_TTL)
        # And the minted code is really the clamped one on disk.
        with open(operator_auth.LOGIN_CODE_PATH) as f:
            disk = _json.load(f)
        assert disk["expires_at"] - disk["created_at"] <= operator_auth.MAX_LOGIN_CODE_TTL


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

    def test_login_rate_limited_on_failures(self, client):
        for _ in range(10):
            client.post("/login", headers=_common_headers(), data={"code": "aop_wrong"})
        resp = client.post("/login", headers=_common_headers(), data={"code": "aop_wrong"})
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_valid_code_bypasses_failure_throttle(self, client):
        # Exhaust the failure budget with junk from the same (loopback) IP.
        for _ in range(20):
            client.post("/login", headers=_common_headers(), data={"code": "aop_wrong"})
        # A freshly minted VALID code must still log the operator in —
        # the throttle counts failures only and never locks out a real
        # code (finding: shared-loopback login-window DoS).
        code = operator_auth.create_login_code()
        resp = client.post(
            "/login",
            headers=_common_headers(),
            data={"code": code},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert operator_auth.SESSION_COOKIE in resp.cookies

    def test_successful_login_does_not_consume_budget(self, client):
        # Two back-to-back valid logins; neither charges the throttle, so
        # a subsequent single wrong attempt is still a plain 401, not 429.
        for _ in range(3):
            code = operator_auth.create_login_code()
            client.post("/login", headers=_common_headers(), data={"code": code})
        resp = client.post("/login", headers=_common_headers(), data={"code": "aop_wrong"})
        assert resp.status_code == 401

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


class TestScopedSessions:
    """Reduced-scope sessions must never pass the write gate."""

    def _login_with_scope(self, client, scope):
        code = operator_auth.create_login_code(scope=scope)
        resp = client.post(
            "/login",
            headers=_common_headers(),
            data={"code": code},
            follow_redirects=False,
        )
        assert resp.status_code == 303

    def test_audit_read_session_rejected_on_write(self, client):
        self._login_with_scope(client, operator_auth.SCOPE_AUDIT_READ)
        resp = client.post("/test-gated", headers=_common_headers())
        assert resp.status_code == 403

    def test_audit_read_session_rejected_on_csrf_write(self, client):
        self._login_with_scope(client, operator_auth.SCOPE_AUDIT_READ)
        info = client.get("/api/v1/operator/session", headers=_common_headers()).json()
        assert info["scope"] == operator_auth.SCOPE_AUDIT_READ
        resp = client.post(
            "/test-gated-csrf",
            headers=_common_headers({"X-CSRF-Token": info["csrf_token"]}),
        )
        assert resp.status_code == 403

    def test_audit_read_session_may_read_journal(self, client):
        self._login_with_scope(client, operator_auth.SCOPE_AUDIT_READ)
        resp = client.get("/api/v1/fleet/audit", headers=_common_headers())
        assert resp.status_code == 200

    def test_full_session_still_writes(self, client):
        self._login_with_scope(client, operator_auth.SCOPE_FULL)
        resp = client.post("/test-gated", headers=_common_headers())
        assert resp.status_code == 200

    def test_session_info_reports_full_scope(self, client):
        _login(client)
        info = client.get("/api/v1/operator/session", headers=_common_headers()).json()
        assert info["scope"] == operator_auth.SCOPE_FULL


class TestAuditTailOneShot:
    """POST /api/v1/fleet/audit-tail — code-for-one-redacted-read exchange."""

    @pytest.fixture(autouse=True)
    def _reset_rate_limiter(self):
        operator_routes._audit_tail_rate_limiter.reset()
        yield
        operator_routes._audit_tail_rate_limiter.reset()

    def _seed_audit(self, n=3, **extra):
        for i in range(n):
            audit.log_event(
                actor_type=audit.ACTOR_MACHINE,
                command=f"cmd-{i}",
                nickname="node-a",
                status="ok",
                http_status=200,
                args={"engine": "llamacpp", "model": "secret-model-path.gguf"},
                error="raw error text with /Users/someone/private/path",
                **extra,
            )

    def _mint(self):
        return operator_auth.create_login_code(scope=operator_auth.SCOPE_AUDIT_READ)

    def test_exchange_returns_redacted_events(self, client):
        self._seed_audit()
        resp = client.post(
            "/api/v1/fleet/audit-tail",
            headers=_common_headers(),
            json={"code": self._mint()},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] >= 3
        assert body["exchange_id"].startswith("aex_")
        for ev in body["events"]:
            assert "args" not in ev
            assert "error" not in ev
            assert "secret-model-path" not in str(ev)
            assert "/Users/someone" not in str(ev)

    def test_full_scope_code_refused_and_burned(self, client):
        self._seed_audit()
        code = operator_auth.create_login_code(scope=operator_auth.SCOPE_FULL)
        resp = client.post(
            "/api/v1/fleet/audit-tail",
            headers=_common_headers(),
            json={"code": code},
        )
        assert resp.status_code == 401
        # The full code was consumed by the failed exchange: it can no
        # longer open a dashboard session either (mint decides use).
        login = client.post(
            "/login",
            headers=_common_headers(),
            data={"code": code},
            follow_redirects=False,
        )
        assert login.status_code == 401

    def test_code_is_single_use(self, client):
        self._seed_audit()
        code = self._mint()
        first = client.post(
            "/api/v1/fleet/audit-tail", headers=_common_headers(), json={"code": code}
        )
        assert first.status_code == 200
        second = client.post(
            "/api/v1/fleet/audit-tail", headers=_common_headers(), json={"code": code}
        )
        assert second.status_code == 401

    def test_audit_read_code_cannot_open_web_session(self, client):
        """Condition 1 end-to-end: an audit:read code pasted into /login
        yields a session that the write gate refuses."""
        code = self._mint()
        resp = client.post(
            "/login",
            headers=_common_headers(),
            data={"code": code},
            follow_redirects=False,
        )
        assert resp.status_code == 303  # session opens...
        gated = client.post("/test-gated", headers=_common_headers())
        assert gated.status_code == 403  # ...but cannot write

    def test_lines_and_hours_clamped(self, client):
        self._seed_audit(n=5)
        resp = client.post(
            "/api/v1/fleet/audit-tail",
            headers=_common_headers(),
            json={"code": self._mint(), "lines": 999999, "since_hours": 999999},
        )
        assert resp.status_code == 200
        assert resp.json()["count"] <= operator_routes._AUDIT_TAIL_ONESHOT_MAX_LINES

    def test_since_hours_filters_old_events(self, client, tmp_audit):
        import json as _json

        # One old event (30h ago), two fresh ones.
        old = {"ts": int(time.time()) - 30 * 3600, "command": "old", "status": "ok"}
        audit._ensure_dir()
        with open(audit.AUDIT_PATH, "a") as f:
            f.write(_json.dumps(old) + "\n")
        self._seed_audit(n=2)
        resp = client.post(
            "/api/v1/fleet/audit-tail",
            headers=_common_headers(),
            json={"code": self._mint(), "since_hours": 24},
        )
        assert resp.status_code == 200
        commands = [e.get("command") for e in resp.json()["events"]]
        assert "old" not in commands
        assert commands.count("cmd-0") == 1

    def test_bad_body_rejected(self, client):
        resp = client.post("/api/v1/fleet/audit-tail", headers=_common_headers(), json={"nope": 1})
        assert resp.status_code == 400

    def test_rate_limited(self, client):
        for _ in range(6):
            client.post(
                "/api/v1/fleet/audit-tail",
                headers=_common_headers(),
                json={"code": "aop_junk"},
            )
        resp = client.post(
            "/api/v1/fleet/audit-tail",
            headers=_common_headers(),
            json={"code": self._mint()},
        )
        assert resp.status_code == 429

    def test_read_is_itself_journaled(self, client):
        self._seed_audit()
        resp = client.post(
            "/api/v1/fleet/audit-tail",
            headers=_common_headers(),
            json={"code": self._mint()},
        )
        assert resp.status_code == 200
        exchange_id = resp.json()["exchange_id"]
        events = audit.read_tail(5)
        logged = [e for e in events if e.get("event") == "audit_read"]
        assert logged and logged[0]["exchange_id"] == exchange_id
        assert logged[0]["lines_returned"] == resp.json()["count"]
