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


def require_operator(request: Request) -> operator_auth.OperatorSession:
    """FastAPI dependency: the request must carry a live operator session.

    For browser-facing write routes. Machine (Bearer) endpoints keep
    their own auth — the audiences are deliberately separate.
    """
    session = _current_session(request)
    if session is None:
        raise HTTPException(status_code=401, detail="operator session required")
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

    if operator_auth.consume_login_code(code.strip()):
        session_id, session = _session_store(request).create()
        audit.log_event(
            actor_type=audit.ACTOR_OPERATOR,
            event="login",
            source_ip=ip,
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
        return JSONResponse({"authenticated": False})
    return JSONResponse(
        {
            "authenticated": True,
            "expires_at": int(session.expires_at),
            "csrf_token": session.csrf_secret,
        }
    )
