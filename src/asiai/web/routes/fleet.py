"""Fleet mode endpoints: aggregate status across multiple asiai nodes.

Phase 1 (read-only):

- ``GET /api/v1/fleet/nodes`` — list configured nodes (no secrets)
- ``GET /api/v1/fleet/snapshot`` — parallel poll + aggregate, cached 10s
- ``GET /fleet`` — HTMX-driven HTML grid page

Phase 2 (writes, this module):

- ``POST /api/v1/fleet/{nickname}/command`` — execute a whitelisted
  write (``purge``, ``stop``, ``restart``, ``unload``, ``install``,
  ``uninstall``, ``upgrade``) on the local node after Bearer auth +
  per-token rate limit + audit log. The route proxies to
  ``aisctl serve`` on the loopback interface (``127.0.0.1:8898``); the
  fleet write surface is therefore disabled if ``aisctl serve`` is not
  running on the node.

The synchronous parallel poll lives in ``asiai.fleet.poll`` and uses a
ThreadPoolExecutor + urllib (stdlib only). FastAPI handlers wrap any
blocking call in ``asyncio.to_thread`` so the uvicorn event loop stays
responsive.
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from asiai.auth import audit, loopback
from asiai.auth import config as auth_config
from asiai.auth.ratelimit import TokenRateLimiter
from asiai.fleet import config as fleet_config
from asiai.fleet.poll import (
    ERROR_DNS,
    ERROR_HTTP_4XX,
    ERROR_HTTP_5XX,
    ERROR_OTHER,
    ERROR_OVERSIZED,
    ERROR_PARSE,
    ERROR_REFUSED,
    ERROR_TIMEOUT,
    ERROR_UNSUPPORTED_SCHEME,
    poll_all,
)
from asiai.web import fleet_metrics

logger = logging.getLogger("asiai.web.routes.fleet")

# Coarse public status: ``ok`` if the last poll succeeded, ``unreachable``
# for transport-level failures, ``error`` for everything else. Hides the
# raw exception class names from the API surface so a probe cannot
# fingerprint the LAN by replaying queries.
_UNREACHABLE_CLASSES = {ERROR_TIMEOUT, ERROR_REFUSED, ERROR_DNS}
_ERROR_CLASSES = {
    ERROR_HTTP_4XX,
    ERROR_HTTP_5XX,
    ERROR_PARSE,
    ERROR_OVERSIZED,
    ERROR_UNSUPPORTED_SCHEME,
    ERROR_OTHER,
}


def _public_status(raw: str | None, error_class: str | None) -> str:
    """Map an internal status string + error class to the public 3-value enum."""
    if raw == "ok":
        return "ok"
    if error_class in _UNREACHABLE_CLASSES:
        return "unreachable"
    if error_class in _ERROR_CLASSES:
        return "error"
    if raw is None:
        return "unknown"
    lowered = raw.lower()
    if any(k in lowered for k in ("timeout", "refused", "gaierror", "dns")):
        return "unreachable"
    return "error"


if TYPE_CHECKING:
    from asiai.web.state import AppState

router = APIRouter(tags=["fleet"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# ---------------------------------------------------------------------------
# Phase 2 — write command surface
# ---------------------------------------------------------------------------

# Loopback endpoint where ``aisctl serve`` listens. The default targets
# the port documented in ``asiai-inference-server``. A node operator can
# rebind the loopback service to a non-default port (testing, port
# conflict, multi-instance) by exporting ``ASIAI_AISCTL_SERVE_URL``
# before launching ``asiai web`` — typically via the LaunchDaemon's
# ``EnvironmentVariables`` dict.
AISCTL_SERVE_URL = os.environ.get("ASIAI_AISCTL_SERVE_URL", "http://127.0.0.1:8898")

# Commands the LAN-facing write endpoint will forward to ``aisctl serve``.
# Each value is the upstream timeout in seconds for that command.
# ``install`` / ``uninstall`` / ``upgrade`` get a longer budget because
# they shell out to Homebrew + LaunchDaemon orchestration.
COMMAND_TIMEOUTS: dict[str, float] = {
    "purge": 15.0,
    "load": 180.0,
    "unload": 30.0,
    "stop": 30.0,
    "start": 60.0,
    "restart": 60.0,
    "install": 180.0,
    "uninstall": 60.0,
    "upgrade": 300.0,
}

# Engine name regex (LAN-facing defense in depth; ``aisctl serve`` also
# validates against the live manifest registry). Matches the family
# pattern used by aisrv (``ollama``, ``llamacpp``, ``llamacpp-aux-5``,
# ``mlx-lm``, ``rapidmlx``, etc.). Rejects anything that could inject
# into a subprocess argv on the server side.
_ENGINE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")

# Nickname regex — same shape as ``fleet/config.py:_NICKNAME_RE`` so the
# audit log never sees a string the fleet config wouldn't accept. The
# nickname comes from the URL path and is otherwise uncontrolled by the
# server: validating here keeps newlines / CR / control chars out of the
# JSONL audit lines (defense against log injection / CRLF smuggling).
_NICKNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.\-]{0,63}$")

# Model name regex — accepts HF naming (``meta-llama/Llama-3.2-3B``)
# and bare tags (``llama3.2:3b``). Rejects shell metacharacters.
_MODEL_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_./:\-]{0,127}$")

# Max body size for a command request. The body is a small JSON envelope;
# anything beyond 64 KB is almost certainly malformed or hostile.
_MAX_BODY_BYTES = 64 * 1024

# Rate limit: 30 commands/min per token. The limiter is module-level so
# every fleet command route shares it (resets on process restart, which
# is acceptable — audit log covers long-term forensics).
_rate_limiter = TokenRateLimiter(limit=30, window_seconds=60.0)


def _redact_args(args: dict[str, Any]) -> dict[str, Any]:
    """Strip plausible secret-bearing keys from audit log args."""
    if not isinstance(args, dict):
        return {}
    redacted: dict[str, Any] = {}
    for k, v in args.items():
        if not isinstance(k, str):
            continue
        if any(s in k.lower() for s in ("token", "secret", "password", "auth")):
            redacted[k] = "***"
        else:
            redacted[k] = v
    return redacted


def _validate_command_payload(
    payload: Any,
) -> tuple[str | None, dict[str, Any], str | None]:
    """Validate the JSON body of a command request.

    Returns ``(command, args, error)``. ``error`` is set when the payload
    is malformed; ``command`` is None in that case.
    """
    if not isinstance(payload, dict):
        return (None, {}, "body must be a JSON object")
    command = payload.get("command")
    if not isinstance(command, str) or command not in COMMAND_TIMEOUTS:
        allowed = sorted(COMMAND_TIMEOUTS)
        return (None, {}, f"command must be one of: {', '.join(allowed)}")
    raw_args = payload.get("args") or {}
    if not isinstance(raw_args, dict):
        return (None, {}, "args must be a JSON object")

    engine = raw_args.get("engine")
    if command != "purge":
        if not isinstance(engine, str) or not _ENGINE_RE.match(engine):
            return (None, {}, "args.engine must match [a-z][a-z0-9_-]{0,31}")

    args: dict[str, Any] = {}
    if isinstance(engine, str) and _ENGINE_RE.match(engine):
        args["engine"] = engine

    if command in ("unload", "load"):
        model = raw_args.get("model")
        if command == "load" and not model:
            return (None, {}, "args.model is required for the 'load' command")
        if model is not None:
            if not isinstance(model, str) or not _MODEL_RE.match(model):
                return (None, {}, "args.model must match [a-zA-Z0-9][a-zA-Z0-9_./:-]{0,127}")
            args["model"] = model

    if command == "load":
        keep_alive = raw_args.get("keep_alive")
        if keep_alive is not None:
            if not isinstance(keep_alive, str) or not re.match(r"^[0-9]+[smh]?$", keep_alive):
                return (None, {}, "args.keep_alive must match [0-9]+[smh]? (e.g. '5m', '30s')")
            args["keep_alive"] = keep_alive

    return (command, args, None)


def _extract_bearer(request: Request) -> str | None:
    """Return the Bearer token from the Authorization header, or None."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    return header[7:].strip() or None


def _client_ip(request: Request) -> str:
    """Best-effort peer IP for the audit log."""
    if request.client:
        return request.client.host
    return "unknown"


def _proxy_to_aisctl(
    command: str,
    args: dict[str, Any],
    internal_token: str,
    timeout: float,
) -> tuple[int, dict[str, Any]]:
    """POST to aisctl serve. Returns ``(http_status, body)``.

    Network failures map to a synthetic ``(502, {...})`` so callers can
    log a single shape regardless of upstream state.
    """
    payload = _json.dumps({"command": command, "args": args}).encode("utf-8")
    req = urllib.request.Request(
        f"{AISCTL_SERVE_URL}/internal/v1/command",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {internal_token}",
            "User-Agent": "asiai-web/fleet-phase2",
        },
    )
    try:
        # nosec B310 — fixed loopback URL constructed above, not user-controlled.
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read(_MAX_BODY_BYTES + 1)
            if len(raw) > _MAX_BODY_BYTES:
                return (502, {"error": "upstream_oversized"})
            try:
                body = _json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return (502, {"error": "upstream_parse_error"})
            return (resp.status, body if isinstance(body, dict) else {"data": body})
    except urllib.error.HTTPError as e:
        try:
            raw = e.read(_MAX_BODY_BYTES + 1)
            body = _json.loads(raw.decode("utf-8")) if raw else {}
            if not isinstance(body, dict):
                body = {"data": body}
        except (ValueError, UnicodeDecodeError, OSError):
            body = {"error": "upstream_http_error"}
        return (e.code, body)
    except urllib.error.URLError as e:
        # Log the full reason locally (visible in asiai web logs) but
        # never surface the raw exception text to the LAN client — it
        # leaks the loopback host:port and the OS-level errno string,
        # which a tcpdumper on the LAN could correlate with the node's
        # internal topology. Public detail is coarse-grained.
        logger.warning("aisctl serve unreachable at %s: %s", AISCTL_SERVE_URL, e)
        return (502, {"error": "aisctl_serve_unreachable"})
    except TimeoutError:
        return (504, {"error": "aisctl_serve_timeout"})
    except OSError as e:
        logger.warning("aisctl proxy I/O error: %s", e)
        return (502, {"error": "aisctl_serve_io_error"})


@router.get("/api/v1/fleet/nodes")
async def api_fleet_nodes() -> JSONResponse:
    """Return the configured fleet nodes (auth_token redacted)."""
    nodes_out = []
    for n in fleet_config.get_nodes():
        redacted = fleet_config.redact_node(n)
        if redacted:
            redacted["last_status"] = _public_status(redacted.get("last_status"), None)
        nodes_out.append(redacted)
    return JSONResponse({"nodes": nodes_out})


def _aggregate_fleet_snapshot(state: AppState, timeout: float = 10.0) -> dict:
    """Get cached fleet snapshot or run a fresh parallel poll.

    The per-node timeout is 10s (not 5s): a remote node's ``/api/v1/snapshot``
    does a full engine scan on a cold cache and can legitimately take ~6s on a
    loaded host, which a 5s timeout would mis-report as DOWN. The node caches
    its own snapshot ~10s, so subsequent polls are sub-second.
    """
    cached = state.get_fleet_cache(max_age=10.0)
    if cached:
        return cached
    with state._fleet_poll_lock:
        cached = state.get_fleet_cache(max_age=10.0)
        if cached:
            return cached
        nodes = fleet_config.get_nodes()
        polls = poll_all(nodes, timeout=timeout)
        snapshot = {"polled_at": int(time.time()), "nodes": [p.to_dict() for p in polls]}
        state.set_fleet_cache(snapshot)
        for p in polls:
            fleet_config.touch_node_status(p.nickname, ok=p.ok, error=p.error)
        return snapshot


@router.get("/api/v1/fleet/snapshot")
async def api_fleet_snapshot(request: Request) -> JSONResponse:
    """Parallel poll of every configured node, cached 10s."""
    state = request.app.state.app_state
    snapshot = await asyncio.to_thread(_aggregate_fleet_snapshot, state)
    return JSONResponse(snapshot)


@router.post("/api/v1/fleet/{nickname}/command")
async def api_fleet_command(nickname: str, request: Request) -> JSONResponse:
    """Execute a whitelisted write command on the local node.

    Authentication: ``Authorization: Bearer <secret>`` validated against
    the local ``~/.config/asiai/auth.json``.

    Request body (JSON)::

        {"command": "<purge|stop|...>", "args": {"engine": "...", "model": "..."}}

    Response (JSON)::

        {"ok": true, "exit_code": 0, "stdout": "...", "stderr": "...",
         "duration_ms": 123, "command": "purge", "nickname": "..."}

    Errors: 401 (no/bad token), 403 (rate limit), 400 (bad payload),
    501 (no auth tokens registered yet), 502/504 (aisctl serve down).
    """
    started = time.monotonic()
    ip = _client_ip(request)

    if not _NICKNAME_RE.match(nickname):
        # Reject before we even spend bytes reading the body — the
        # nickname goes into the audit log, and a CRLF/ANSI-injected
        # value could compromise a downstream log viewer.
        audit.log_event(
            source_ip=ip,
            token_id=None,
            nickname="<invalid>",
            command=None,
            status="denied",
            http_status=400,
            error="invalid_nickname",
        )
        fleet_metrics.record(command=None, status="denied", error="invalid_nickname")
        return JSONResponse(
            {
                "error": "bad_nickname",
                "detail": "nickname must match [a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}",
            },
            status_code=400,
        )

    raw = await request.body()
    if len(raw) > _MAX_BODY_BYTES:
        audit.log_event(
            source_ip=ip,
            token_id=None,
            nickname=nickname,
            command=None,
            status="denied",
            http_status=413,
            error="body_too_large",
        )
        fleet_metrics.record(command=None, status="denied", error="body_too_large")
        return JSONResponse({"error": "body_too_large"}, status_code=413)

    secret = _extract_bearer(request)
    if not secret:
        audit.log_event(
            source_ip=ip,
            token_id=None,
            nickname=nickname,
            command=None,
            status="denied",
            http_status=401,
            error="missing_bearer",
        )
        fleet_metrics.record(command=None, status="denied", error="missing_bearer")
        return JSONResponse(
            {"error": "unauthorized", "detail": "missing Bearer token"},
            status_code=401,
        )

    # Distinguish "auth never configured" (501) from "token presented is
    # invalid or revoked" (401). The former tells the operator what to do
    # (``asiai auth init``); the latter tells the client to refresh its
    # secret. Both branches still produce an audit log entry.
    all_tokens = auth_config.list_tokens()
    if not all_tokens:
        audit.log_event(
            source_ip=ip,
            token_id=None,
            nickname=nickname,
            command=None,
            status="denied",
            http_status=501,
            error="no_tokens_configured",
        )
        fleet_metrics.record(command=None, status="denied", error="no_tokens_configured")
        return JSONResponse(
            {
                "error": "not_initialized",
                "detail": "no auth tokens configured (run 'asiai auth init' on this node)",
            },
            status_code=501,
        )

    token_id = auth_config.verify_token(secret)
    if not token_id:
        audit.log_event(
            source_ip=ip,
            token_id=None,
            nickname=nickname,
            command=None,
            status="denied",
            http_status=401,
            error="invalid_token",
        )
        fleet_metrics.record(command=None, status="denied", error="invalid_token")
        return JSONResponse(
            {"error": "unauthorized", "detail": "invalid Bearer token"},
            status_code=401,
        )

    allowed, _remaining, retry_after = _rate_limiter.check(token_id)
    if not allowed:
        audit.log_event(
            source_ip=ip,
            token_id=token_id,
            nickname=nickname,
            command=None,
            status="denied",
            http_status=429,
            error="rate_limited",
        )
        fleet_metrics.record(command=None, status="denied", error="rate_limited", token_id=token_id)
        resp = JSONResponse(
            {"error": "rate_limited", "retry_after": round(retry_after, 1)},
            status_code=429,
        )
        resp.headers["Retry-After"] = str(int(retry_after) + 1)
        return resp

    try:
        payload = _json.loads(raw.decode("utf-8")) if raw else {}
    except (ValueError, UnicodeDecodeError):
        audit.log_event(
            source_ip=ip,
            token_id=token_id,
            nickname=nickname,
            command=None,
            status="error",
            http_status=400,
            error="invalid_json",
        )
        fleet_metrics.record(command=None, status="error", error="invalid_json", token_id=token_id)
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    command, args, err = _validate_command_payload(payload)
    if err is not None or command is None:
        audit.log_event(
            source_ip=ip,
            token_id=token_id,
            nickname=nickname,
            command=payload.get("command") if isinstance(payload, dict) else None,
            args=_redact_args(payload.get("args") or {}) if isinstance(payload, dict) else {},
            status="error",
            http_status=400,
            error=err or "bad_payload",
        )
        fleet_metrics.record(
            command=payload.get("command") if isinstance(payload, dict) else None,
            status="error",
            error="bad_payload",
            token_id=token_id,
        )
        return JSONResponse({"error": "bad_payload", "detail": err}, status_code=400)

    internal = loopback.read_token()
    if not internal:
        audit.log_event(
            source_ip=ip,
            token_id=token_id,
            nickname=nickname,
            command=command,
            args=_redact_args(args),
            status="error",
            http_status=503,
            error="aisctl_serve_not_running",
        )
        fleet_metrics.record(
            command=command,
            status="error",
            error="aisctl_serve_not_running",
            token_id=token_id,
        )
        return JSONResponse(
            {
                "error": "aisctl_serve_unavailable",
                "detail": (
                    "no loopback token found; start `aisctl serve` on this node "
                    "to enable fleet write commands"
                ),
            },
            status_code=503,
        )

    timeout = COMMAND_TIMEOUTS.get(command, 60.0)
    fleet_metrics.aisctl_inflight_inc()
    try:
        status, body = await asyncio.to_thread(_proxy_to_aisctl, command, args, internal, timeout)
    finally:
        fleet_metrics.aisctl_inflight_dec()

    duration_ms = int((time.monotonic() - started) * 1000)
    audit.log_event(
        source_ip=ip,
        token_id=token_id,
        nickname=nickname,
        command=command,
        args=_redact_args(args),
        status="ok" if status < 400 else "error",
        http_status=status,
        duration_ms=duration_ms,
        exit_code=body.get("exit_code") if isinstance(body, dict) else None,
        error=body.get("error") if isinstance(body, dict) and status >= 400 else None,
    )
    fleet_metrics.record(
        command=command,
        status="ok" if status < 400 else "error",
        duration_ms=duration_ms,
        error=(body.get("error") if isinstance(body, dict) and status >= 400 else None),
        token_id=token_id,
    )

    response_body = {
        **body,
        "command": command,
        "nickname": nickname,
        "duration_ms": duration_ms,
    }
    return JSONResponse(response_body, status_code=status)


@router.get("/fleet")
async def page_fleet(request: Request):
    """Render the fleet HTML page (server-rendered grid + HTMX refresh)."""
    state = request.app.state.app_state
    snapshot = await asyncio.to_thread(_aggregate_fleet_snapshot, state)
    nodes = [fleet_config.redact_node(n) for n in fleet_config.get_nodes()]
    return templates.TemplateResponse(
        request,
        "fleet.html",
        {"request": request, "snapshot": snapshot, "nodes": nodes},
    )


@router.get("/fleet/grid-fragment")
async def page_fleet_grid_fragment(request: Request):
    """Return the fleet grid as an HTML fragment for HTMX auto-refresh."""
    state = request.app.state.app_state
    snapshot = await asyncio.to_thread(_aggregate_fleet_snapshot, state)
    return templates.TemplateResponse(
        request,
        "partials/fleet_grid.html",
        {"request": request, "snapshot": snapshot},
    )
