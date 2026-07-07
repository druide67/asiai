"""Operator login/logout routes + the session dependencies for write routes.

Flow (see :mod:`asiai.auth.operator`): the operator runs ``asiai auth
login`` in a trusted shell, then submits the single-use code through the
login form (``GET /login`` renders the form; the code is posted to
``POST /login``, never placed in a URL) and receives a server-side
session behind an ``HttpOnly; SameSite=Lax`` cookie. Browser-facing write routes take
:func:`require_operator` (or :func:`require_operator_csrf` for
form/HTMX posts) as a dependency; the node-to-node Bearer path is
untouched.

No ``Secure`` cookie flag yet: the dashboard is reached over loopback
or an SSH forward, so the cookie never crosses the LAN. Revisit when a
TLS transport lands.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from asiai.auth import audit
from asiai.auth import operator as operator_auth
from asiai.auth.ratelimit import TokenRateLimiter

logger = logging.getLogger(__name__)

router = APIRouter()

# Failed login attempts are throttled to bound scrypt CPU cost + log
# spam from a grinder. It counts FAILURES ONLY (see login_submit): a
# valid single-use code always authenticates regardless of the budget,
# so a flood of junk from a shared loopback IP can never lock out the
# real operator — the login-window DoS that keeping the code file on
# wrong attempts was designed to avoid. Keyed by peer IP (meaningful
# when bound to the LAN; on loopback all clients collapse to one bucket,
# which is fine because the budget only ever gates further failures).
_login_rate_limiter = TokenRateLimiter(limit=10, window_seconds=60.0)


def _client_ip(request: Request) -> str:
    """Best-effort peer IP for rate limiting + the audit log."""
    client = request.client
    return client.host if client else "unknown"


def _session_store(request: Request) -> operator_auth.OperatorSessionStore:
    return request.app.state.operator_sessions


def _current_session(request: Request) -> operator_auth.OperatorSession | None:
    session_id = request.cookies.get(operator_auth.SESSION_COOKIE)
    return _session_store(request).get(session_id)


def require_operator_read(request: Request) -> operator_auth.OperatorSession:
    """FastAPI dependency: any live operator session, whatever its scope.

    For operator-gated READ routes (the audit journal). Write routes
    must use :func:`require_operator` so a reduced-scope session can
    never mutate anything.
    """
    session = _current_session(request)
    if session is None:
        raise HTTPException(status_code=401, detail="operator session required")
    return session


def require_operator(request: Request) -> operator_auth.OperatorSession:
    """FastAPI dependency: a live FULL-scope operator session.

    For browser-facing write routes. A session inherited from a reduced-
    scope login code (e.g. ``audit:read``) is rejected here — the scope
    was bound to the code at mint and the write gate honors it. Machine
    (Bearer) endpoints keep their own auth — the audiences are
    deliberately separate.
    """
    session = require_operator_read(request)
    if session.scope != operator_auth.SCOPE_FULL:
        raise HTTPException(status_code=403, detail="session scope does not allow writes")
    return session


async def require_operator_csrf(request: Request) -> operator_auth.OperatorSession:
    """Like :func:`require_operator`, plus a session-bound CSRF check.

    The token is read from the ``X-CSRF-Token`` header (HTMX
    ``hx-headers``) or a ``_csrf`` form field. Use this on every
    state-changing form/HTMX route once write buttons ship.
    """
    session = require_operator(request)
    token = request.headers.get("x-csrf-token")
    if token is None:
        content_type = request.headers.get("content-type", "")
        if "form" in content_type:
            form = await request.form()
            raw = form.get("_csrf")
            token = raw if isinstance(raw, str) else None
    store = _session_store(request)
    if not store.verify_csrf(session, token):
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid")
    return session


@router.get("/login")
async def login_page(request: Request):
    """Render the login form; already-authenticated operators go home."""
    if _current_session(request) is not None:
        return RedirectResponse("/", status_code=303)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "login.html",
        {"nav_active": "login", "error": None},
    )


@router.post("/login")
async def login_submit(request: Request, code: str = Form(default="")):
    """Verify a single-use login code and open an operator session.

    A valid code is checked FIRST and always wins — the rate limit
    throttles only failed attempts, so a grinder sharing the operator's
    (loopback) IP cannot lock the operator out of a working code.
    """
    ip = _client_ip(request)

    scope = operator_auth.consume_login_code(code.strip())
    if scope is not None:
        session_id, session = _session_store(request).create(scope=scope)
        audit.log_event(
            actor_type=audit.ACTOR_OPERATOR,
            event="login",
            source_ip=ip,
            scope=scope,
            status="ok",
            http_status=303,
        )
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            operator_auth.SESSION_COOKIE,
            session_id,
            max_age=int(session.expires_at - session.created_at),
            httponly=True,
            samesite="lax",
            path="/",
        )
        return response

    # Failed attempt: now (and only now) charge the throttle budget.
    allowed, _remaining, retry_after = _login_rate_limiter.check(ip)
    if not allowed:
        audit.log_event(
            actor_type=audit.ACTOR_OPERATOR,
            event="login",
            source_ip=ip,
            status="denied",
            http_status=429,
            error="rate_limited",
        )
        return JSONResponse(
            {"error": "rate_limited", "retry_after": round(retry_after, 1)},
            status_code=429,
            headers={"Retry-After": str(int(retry_after) + 1)},
        )

    audit.log_event(
        actor_type=audit.ACTOR_OPERATOR,
        event="login",
        source_ip=ip,
        status="denied",
        http_status=401,
        error="invalid_or_expired_code",
    )
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "login.html",
        {"nav_active": "login", "error": "Invalid or expired code."},
        status_code=401,
    )


@router.post("/logout")
async def logout(request: Request):
    """Drop the operator session (server-side) and clear the cookie."""
    session_id = request.cookies.get(operator_auth.SESSION_COOKIE)
    revoked = _session_store(request).revoke(session_id)
    if revoked:
        audit.log_event(
            actor_type=audit.ACTOR_OPERATOR,
            event="logout",
            source_ip=_client_ip(request),
            status="ok",
            http_status=303,
        )
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(operator_auth.SESSION_COOKIE, path="/")
    return response


@router.get("/api/v1/operator/session")
async def operator_session_info(request: Request) -> JSONResponse:
    """Introspection for the dashboard: is an operator logged in?

    Exposes the session-bound CSRF token so HTMX write forms can send
    it back in ``X-CSRF-Token``. Cross-origin pages cannot read this
    response (no CORS is configured), so this does not leak the token
    to other origins.
    """
    session = _current_session(request)
    if session is None:
        return JSONResponse({"authenticated": False}, headers={"Cache-Control": "no-store"})
    # no-store: this response carries the CSRF token — it must never land
    # in a shared browser's disk cache and outlive the session.
    return JSONResponse(
        {
            "authenticated": True,
            "expires_at": int(session.expires_at),
            "csrf_token": session.csrf_secret,
            "scope": session.scope,
        },
        headers={"Cache-Control": "no-store"},
    )


# ── one-shot audit read (agents / MCP) ──────────────────────────────
#
# Gate (claude-config 2026-07-07): the audit journal may be read by a
# local agent ONLY through the operator-code funnel, with the scope
# bound at mint, a redacted output, a bounded window and a rate limit.
# This route is deliberately session-LESS: the code is exchanged for
# exactly one redacted read (a hardening beyond the approved
# session-based design — no cookie/CSRF lifecycle to manage in a
# non-browser consumer, nothing persists to revoke).

# Metadata-only whitelist (gate condition 2): the response feeds an LLM
# context, so no aop_ code, no token value, no secret name/value, no raw
# command payload may pass. `args` (raw command arguments) and `error`
# (free-form text) are deliberately absent. Unknown/future fields are
# dropped by construction.
_AUDIT_REDACT_WHITELIST = frozenset(
    {
        "ts",
        "actor_type",
        "event",
        "source_ip",
        "token_id",
        "nickname",
        "command",
        "status",
        "http_status",
        "duration_ms",
        "scope",
        "exchange_id",
        "lines_returned",
    }
)

_AUDIT_TAIL_ONESHOT_DEFAULT_LINES = 50
_AUDIT_TAIL_ONESHOT_MAX_LINES = 200
_AUDIT_TAIL_ONESHOT_DEFAULT_HOURS = 6.0
_AUDIT_TAIL_ONESHOT_MAX_HOURS = 24.0

# Every request charges the budget (unlike the failure-only login
# limiter): each successful call burns a single-use code anyway, so a
# tight all-requests limit simply bounds journal-scraping throughput
# (gate condition 3).
_audit_tail_rate_limiter = TokenRateLimiter(limit=6, window_seconds=60.0)


def _redact_audit_event(event: dict) -> dict:
    return {k: v for k, v in event.items() if k in _AUDIT_REDACT_WHITELIST}


@router.post("/api/v1/fleet/audit-tail")
async def api_audit_tail_oneshot(request: Request) -> JSONResponse:
    """Exchange an ``audit:read`` login code for ONE redacted journal read.

    Body (JSON): ``{"code": "aop_...", "lines": 50, "since_hours": 6}``.
    The code must have been minted with ``asiai auth login --scope
    audit:read`` — a full-scope code is refused (one scope, one exchange
    surface; mint decides use). The code is consumed either way once it
    verifies. Errors: 400 (bad body), 401 (bad/expired/wrong-scope
    code), 429 (rate limit).
    """
    ip = _client_ip(request)

    allowed, _remaining, retry_after = _audit_tail_rate_limiter.check(ip)
    if not allowed:
        audit.log_event(
            actor_type=audit.ACTOR_OPERATOR,
            event="audit_read",
            source_ip=ip,
            status="denied",
            http_status=429,
            error="rate_limited",
        )
        return JSONResponse(
            {"error": "rate_limited", "retry_after": round(retry_after, 1)},
            status_code=429,
            headers={"Retry-After": str(int(retry_after) + 1)},
        )

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 — malformed/absent JSON body
        body = None
    if not isinstance(body, dict) or not isinstance(body.get("code"), str):
        return JSONResponse({"error": "invalid_body"}, status_code=400)

    scope = operator_auth.consume_login_code(body["code"].strip())
    if scope is None or scope != operator_auth.SCOPE_AUDIT_READ:
        # A valid full-scope code IS consumed by the check above — by
        # design: pasting a full code here was a mint-time mistake and a
        # burned code is cheaper than an over-scoped exchange.
        audit.log_event(
            actor_type=audit.ACTOR_OPERATOR,
            event="audit_read",
            source_ip=ip,
            status="denied",
            http_status=401,
            error="invalid_code_or_scope",
        )
        return JSONResponse({"error": "invalid_code_or_scope"}, status_code=401)

    raw_lines = body.get("lines", _AUDIT_TAIL_ONESHOT_DEFAULT_LINES)
    raw_hours = body.get("since_hours", _AUDIT_TAIL_ONESHOT_DEFAULT_HOURS)
    if not isinstance(raw_lines, int) or isinstance(raw_lines, bool):
        raw_lines = _AUDIT_TAIL_ONESHOT_DEFAULT_LINES
    if not isinstance(raw_hours, (int, float)) or isinstance(raw_hours, bool):
        raw_hours = _AUDIT_TAIL_ONESHOT_DEFAULT_HOURS
    lines = max(1, min(raw_lines, _AUDIT_TAIL_ONESHOT_MAX_LINES))
    since_hours = max(0.1, min(float(raw_hours), _AUDIT_TAIL_ONESHOT_MAX_HOURS))

    import asyncio
    import secrets as _secrets
    import time as _time

    events = await asyncio.to_thread(audit.read_tail, lines)
    cutoff = _time.time() - since_hours * 3600.0
    redacted = [
        _redact_audit_event(e)
        for e in events
        if isinstance(e.get("ts"), (int, float)) and e["ts"] >= cutoff
    ]

    # The read is itself journaled (gate condition 5); the exchange id
    # ties this response to its audit line without minting any session.
    exchange_id = "aex_" + _secrets.token_urlsafe(8)
    audit.log_event(
        actor_type=audit.ACTOR_OPERATOR,
        event="audit_read",
        source_ip=ip,
        scope=scope,
        exchange_id=exchange_id,
        lines_returned=len(redacted),
        status="ok",
        http_status=200,
    )
    return JSONResponse(
        {"events": redacted, "count": len(redacted), "exchange_id": exchange_id},
        headers={"Cache-Control": "no-store"},
    )
