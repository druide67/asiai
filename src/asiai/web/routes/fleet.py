"""Fleet mode endpoints: aggregate status across multiple asiai nodes.

Phase 1 (read-only):

- ``GET /api/v1/fleet/nodes`` — list configured nodes (no secrets)
- ``GET /api/v1/fleet/snapshot`` — parallel poll + aggregate, cached 10s
- ``GET /fleet`` — HTMX-driven HTML grid page

Phase 2 (writes, this module):

- ``POST /api/v1/fleet/{nickname}/command`` — machine path: execute a
  whitelisted write (the ``asiai.fleet.command_spec.ALLOWED_COMMANDS``
  set — start/stop/restart/load/unload/purge/install/uninstall/upgrade)
  on the local node after Bearer auth + per-token rate limit + audit
  log. The route proxies to ``aisctl serve`` on the loopback interface
  (``127.0.0.1:8898``); the fleet write surface is therefore disabled
  if ``aisctl serve`` is not running on the node.
- ``POST /fleet/{nickname}/action`` — operator (human) path: same-origin
  proxy for the dashboard's live buttons. Authenticates the operator
  session + CSRF, re-verifies the typed confirmation for destructive
  verbs, then forwards to the target node's machine edge holding the
  node Bearer server-side. Forwards only — never executes locally.

The synchronous parallel poll lives in ``asiai.fleet.poll`` and uses a
ThreadPoolExecutor + urllib (stdlib only). FastAPI handlers wrap any
blocking call in ``asyncio.to_thread`` so the uvicorn event loop stays
responsive.
"""

from __future__ import annotations

import asyncio
import http.client
import json as _json
import logging
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from asiai.auth import audit, loopback
from asiai.auth import config as auth_config
from asiai.auth.operator import OperatorSession
from asiai.auth.ratelimit import TokenRateLimiter
from asiai.fleet import config as fleet_config
from asiai.fleet import plan as uma_plan
from asiai.fleet.command_spec import (
    ALLOWED_COMMANDS,
    DESTRUCTIVE_COMMANDS,
    client_timeout,
    edge_timeout,
)
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
from asiai.web.routes.operator import require_operator, require_operator_csrf

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

# Command whitelist + timeouts now come from the single shared source
# (asiai.fleet.command_spec). The edge waits ``edge_timeout(cmd)`` = the loopback
# work budget + one hop margin, so it never abandons a command ``aisctl serve``
# is still legitimately running (SB, 2026-07-01: the old hand-maintained edge map
# was INVERTED — 300s edge vs 600s loopback upgrade — and killed live upgrades).

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

# Preset name regex — bundled tuned-manifest names (file basenames on the
# node). Same shape ``aisctl serve`` enforces before building the argv.
_PRESET_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._\-]{0,63}$")

# Max body size for a command request. The body is a small JSON envelope;
# anything beyond 64 KB is almost certainly malformed or hostile.
_MAX_BODY_BYTES = 64 * 1024

# Rate limit: 30 commands/min per token. The limiter is module-level so
# every fleet command route shares it (resets on process restart, which
# is acceptable — audit log covers long-term forensics).
_rate_limiter = TokenRateLimiter(limit=30, window_seconds=60.0)


def _audit_machine(**fields: Any) -> None:
    """Audit an event on the machine (Bearer) write path.

    Stamps ``actor_type`` so these entries are always distinguishable
    from operator-session (human) events in the shared audit log.
    """
    audit.log_event(actor_type=audit.ACTOR_MACHINE, **fields)


def _loggable_command(payload: Any) -> str | None:
    """A ``command`` value safe to journal from an UNVALIDATED payload.

    Validation-failure branches must not copy the raw field into the
    audit log: the journal's ``command`` column is treated as closed-set
    metadata by the redacted read surface (LLM-facing), so free attacker
    text here would smuggle content past the whitelist. Only a known
    command passes verbatim; anything else logs a fixed placeholder.
    """
    if not isinstance(payload, dict):
        return None
    command = payload.get("command")
    if command is None:
        return None
    if isinstance(command, str) and command in ALLOWED_COMMANDS:
        return command
    return "<invalid>"


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
    if not isinstance(command, str) or command not in ALLOWED_COMMANDS:
        allowed = sorted(ALLOWED_COMMANDS)
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

    if command == "install":
        # Optional tuned-manifest preset (the picker's answer to the
        # silent-baseline trap). Shape-checked here; the node's aisctl
        # validates the name against its bundled registry.
        preset = raw_args.get("preset")
        if preset is not None:
            if not isinstance(preset, str) or not _PRESET_RE.match(preset):
                return (None, {}, "args.preset must match [a-zA-Z0-9][a-zA-Z0-9._-]{0,63}")
            args["preset"] = preset

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
    except http.client.HTTPException as e:
        # Garbled upstream (parity with _forward_to_node): urllib propagates
        # these unwrapped; keep the response deliberately coarse, never a 500.
        logger.warning("aisctl serve protocol error: %s", e)
        return (502, {"error": "aisctl_serve_protocol_error"})
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


@router.get("/api/v1/fleet/health-summary")
async def api_fleet_health_summary(request: Request) -> JSONResponse:
    """Reduced alert feed for the cross-page nav dot.

    Same 10s-cached aggregate as ``/api/v1/fleet/snapshot`` (a poll of this
    route never adds node traffic on a warm cache), reduced server-side so
    every page can poll it cheaply: only franc alarms count — engines whose
    rich state says unhealthy/degraded, and nodes that no longer answer.
    """
    state = request.app.state.app_state
    snapshot = await asyncio.to_thread(_aggregate_fleet_snapshot, state)
    unhealthy = 0
    unreachable = 0
    nodes = snapshot.get("nodes") or []
    for node in nodes:
        if not node.get("ok"):
            unreachable += 1
            continue
        engines = (node.get("snapshot") or {}).get("engines_status") or []
        for engine in engines:
            if isinstance(engine, dict) and engine.get("state") in ("unhealthy", "degraded"):
                unhealthy += 1
    return JSONResponse(
        {
            "unhealthy_engines": unhealthy,
            "unreachable_nodes": unreachable,
            "total_nodes": len(nodes),
            "polled_at": snapshot.get("polled_at"),
        },
        # An alert must never be served stale from a browser/proxy cache.
        headers={"Cache-Control": "no-store"},
    )


# ---------------------------------------------------------------------------
# Per-node READ proxies (History / Doctor across the fleet)
# ---------------------------------------------------------------------------
#
# Each proxy targets ONE hardcoded read endpoint on the node and forwards
# only a whitelisted, digit-validated query subset — deliberately not a
# generic path-through proxy, so the hub can never be steered into
# arbitrary-URL fetches (SSRF) or into a node's write surface. Same
# LAN read-only posture as the aggregate snapshot: the proxied data is
# what the node already serves unauthenticated on its own dashboard.

# Every whitelisted query param carries its own validation pattern —
# fail-closed, a value that doesn't fullmatch is silently dropped. The
# time-window params are plain digits (unix ts / hour counts); the plan
# params reuse the same identifier grammars as the write funnel.
_DIGITS_RE = re.compile(r"\d{1,12}")

# endpoint key -> (node path, param -> pattern, timeout seconds).
# Doctor gets a longer budget: it runs live probes, not a DB read.
_NODE_READ_ENDPOINTS: dict[str, tuple[str, dict[str, re.Pattern[str]], float]] = {
    "history": (
        "/api/history",
        {"hours": _DIGITS_RE, "since": _DIGITS_RE, "until": _DIGITS_RE},
        15.0,
    ),
    "benchmarks": (
        "/api/benchmarks",
        {"hours": _DIGITS_RE, "since": _DIGITS_RE, "until": _DIGITS_RE},
        15.0,
    ),
    "engine-history": ("/api/engine-history", {"hours": _DIGITS_RE}, 15.0),
    "benchmark-process": ("/api/benchmark-process", {"hours": _DIGITS_RE}, 15.0),
    "doctor": ("/api/v1/doctor", {}, 45.0),
    "presets": ("/api/v1/presets", {}, 10.0),
    "plan": ("/api/v1/plan", {"preset": _PRESET_RE, "engine": _ENGINE_RE}, 20.0),
}

_NODE_READ_MAX_BODY = 8 * 1024 * 1024

# Bound concurrent node-read proxies. Each holds a thread of the
# process-wide ``asyncio.to_thread`` pool — SHARED with the aggregate
# snapshot and the operator write-forward — for up to its timeout (45s
# for doctor). Without a cap, a burst of proxy reads (real or to slow /
# unreachable nicknames) starves the whole dashboard. Same reasoning as
# ``_forward_semaphore`` on the write path; a separate semaphore so reads
# and writes can't exhaust each other's budget.
_MAX_CONCURRENT_NODE_READS = 6
_node_read_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_NODE_READS)

# Per-IP rate limit on the read proxy (unauthenticated LAN/mesh surface).
_node_read_rate_limiter = TokenRateLimiter(limit=60, window_seconds=60.0)


def _proxy_node_read(nickname: str, endpoint: str, query: dict[str, str]) -> tuple[int, Any]:
    """Fetch one whitelisted read endpoint from a fleet node.

    Returns ``(http_status, payload)``. Never raises. Every query value
    must fullmatch its param's whitelisted pattern — anything else is
    dropped, fail-closed.
    """
    spec = _NODE_READ_ENDPOINTS.get(endpoint)
    if spec is None:
        return (404, {"error": "unknown_endpoint"})
    path, allowed, timeout = spec
    if not _NICKNAME_RE.match(nickname or ""):
        return (400, {"error": "invalid_nickname"})
    node = fleet_config.find_node(nickname)
    if node is None:
        return (404, {"error": "unknown_node"})
    base = str(node.get("asiai_url") or "").rstrip("/")
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme not in ("http", "https"):
        return (502, {"error": "unsupported_node_url"})
    params = {
        k: v for k, v in query.items() if k in allowed and allowed[k].fullmatch(str(v)) is not None
    }
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        # nosec B310 — scheme checked above, URL comes from the operator's
        # own fleet config, path is hardcoded per endpoint.
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read(_NODE_READ_MAX_BODY)
        return (200, _json.loads(raw.decode("utf-8")))
    except urllib.error.HTTPError as e:
        return (502, {"error": "node_http_error", "node_status": e.code})
    except (urllib.error.URLError, OSError, ValueError) as e:
        logger.debug("node read proxy %s/%s failed: %s", nickname, endpoint, e)
        return (502, {"error": "node_unreachable"})


@router.get("/api/v1/presets")
async def api_node_presets() -> JSONResponse:
    """Bundled tuned-manifest presets of THIS node (via ``aisctl serve``).

    The cockpit's install picker reads it (directly or through the hub
    proxy) so an install can name a preset instead of silently shipping
    the generic baseline. Nodes without the ``aisctl serve`` companion
    (or without ``asiai-inference-server`` at all) answer an empty list
    — the picker then only offers the base manifest.
    """
    token = loopback.read_token()
    if not token:
        return JSONResponse({"presets": [], "note": "aisctl serve not available"})

    def _fetch() -> dict:
        req = urllib.request.Request(
            f"{AISCTL_SERVE_URL}/internal/v1/presets",
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            # nosec B310 — fixed loopback URL from a trusted env knob.
            with urllib.request.urlopen(req, timeout=5.0) as resp:  # noqa: S310
                data = _json.loads(resp.read(1024 * 1024).decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError):
            return {"presets": [], "note": "aisctl serve not available"}
        presets = data.get("presets") if isinstance(data, dict) else None
        return {"presets": presets if isinstance(presets, list) else []}

    return JSONResponse(await asyncio.to_thread(_fetch))


def _fetch_preset_cost(preset: str) -> tuple[uma_plan.PresetCost, str | None]:
    """Ask the local ``aisctl serve`` for the memory cost of ``preset``.

    Returns ``(cost, note)``. Any failure — companion absent, endpoint
    not shipped yet (pre-0.11 aisrv), malformed payload — degrades to an
    ``unknown`` confidence cost, which the verdict maps to ``unknown``
    (fail-closed). The note says why, for the UI.
    """
    unknown = uma_plan.PresetCost(0.0, 0.0, "unknown")
    token = loopback.read_token()
    if not token:
        return (unknown, "aisctl serve not available")
    url = f"{AISCTL_SERVE_URL}/internal/v1/plan?" + urllib.parse.urlencode({"preset": preset})
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        # nosec B310 — fixed loopback URL from a trusted env knob.
        with urllib.request.urlopen(req, timeout=10.0) as resp:  # noqa: S310
            data = _json.loads(resp.read(1024 * 1024).decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return (unknown, "aisctl serve has no planner (needs asiai-inference-server >= 0.11)")
        return (unknown, f"aisctl serve error {e.code}")
    except (urllib.error.URLError, OSError, ValueError):
        return (unknown, "aisctl serve not available")
    cost_raw = data.get("cost") if isinstance(data, dict) else None
    if not isinstance(cost_raw, dict):
        return (unknown, "malformed planner response")
    try:
        low = float(cost_raw["total_mb_low"])
        high = float(cost_raw["total_mb_high"])
        confidence = str(cost_raw.get("confidence", "unknown"))
    except (KeyError, TypeError, ValueError):
        return (unknown, "malformed planner response")
    components = cost_raw.get("components")
    return (
        uma_plan.PresetCost(
            total_mb_low=low,
            total_mb_high=high,
            confidence=confidence,
            components=components if isinstance(components, dict) else {},
        ),
        None,
    )


def _build_plan_response(preset: str, engine: str) -> dict:
    """Assemble cost + node state and judge them. Runs in a thread."""
    from asiai.collectors.system import collect_memory, collect_thermal, find_engine_process

    cost, note = _fetch_preset_cost(preset)

    mem = collect_memory()
    thermal = collect_thermal()
    engine_rss_mb: dict[str, float] = {}
    if engine:
        proc = find_engine_process(engine)
        if proc is not None and proc.resident_bytes > 0:
            engine_rss_mb[engine] = proc.resident_bytes / (1024 * 1024)

    node = uma_plan.NodeState(
        mem_total_mb=mem.total / (1024 * 1024),
        mem_used_mb=mem.used / (1024 * 1024),
        pressure=mem.pressure,
        thermal_level=thermal.level,
        gpu_wired_limit_mb=float(mem.gpu_wired_limit_mb),
        engine_rss_mb=engine_rss_mb,
    )
    verdict = uma_plan.cohabitation_verdict(cost, node, replaces_engine=engine or None)

    def _finite(x: float) -> float | None:
        # Starlette serializes with allow_nan=False: a NaN/Infinity echoed
        # from a buggy cost producer must never crash the response.
        return x if math.isfinite(x) else None

    payload = verdict.as_dict()
    payload.update(
        {
            "preset": preset,
            "engine": engine or None,
            "cost": {
                "total_mb_low": _finite(cost.total_mb_low),
                "total_mb_high": _finite(cost.total_mb_high),
                "confidence": cost.confidence,
            },
            "node": {
                "mem_total_mb": round(node.mem_total_mb, 1),
                "mem_used_mb": round(node.mem_used_mb, 1),
                "pressure": node.pressure,
                "thermal_level": node.thermal_level,
                "gpu_wired_limit_mb": node.gpu_wired_limit_mb,
            },
            "inputs_ts": int(time.time()),
        }
    )
    if note:
        payload["note"] = note
    return payload


@router.get("/api/v1/plan")
async def api_node_plan(request: Request) -> JSONResponse:
    """Advisory UMA cohabitation plan for installing a preset on THIS node.

    Cost comes from the local ``aisctl serve`` planner (loopback), the
    verdict from ``asiai.fleet.plan``. Same LAN read-only posture as
    ``/api/v1/presets``; the hub reaches it through the per-node read
    proxy. Advisory only — nothing here blocks an install.
    """
    preset = request.query_params.get("preset", "")
    engine = request.query_params.get("engine", "")
    if not _PRESET_RE.match(preset):
        return JSONResponse({"error": "invalid_preset"}, status_code=400)
    if engine and not _ENGINE_RE.match(engine):
        return JSONResponse({"error": "invalid_engine"}, status_code=400)
    payload = await asyncio.to_thread(_build_plan_response, preset, engine)
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


@router.get("/api/v1/fleet/{nickname}/{endpoint}")
async def api_fleet_node_read(nickname: str, endpoint: str, request: Request) -> JSONResponse:
    """Read-only per-node proxy for the endpoints in ``_NODE_READ_ENDPOINTS``.

    404 for anything not whitelisted — this route deliberately shadows
    no write path (commands are POST on a different route). Rate-limited
    per IP and concurrency-bounded so a burst of slow proxied reads can't
    starve the shared thread pool (503 busy instead).
    """
    allowed, _remaining, retry_after = _node_read_rate_limiter.check(_client_ip(request))
    if not allowed:
        return JSONResponse(
            {"error": "rate_limited"},
            status_code=429,
            headers={"Retry-After": str(int(retry_after) + 1)},
        )
    if _node_read_semaphore.locked():
        return JSONResponse(
            {
                "error": "busy",
                "detail": f"{_MAX_CONCURRENT_NODE_READS} node reads already in flight",
            },
            status_code=503,
            headers={"Retry-After": "2"},
        )
    query = dict(request.query_params.items())
    async with _node_read_semaphore:
        status, payload = await asyncio.to_thread(_proxy_node_read, nickname, endpoint, query)
    return JSONResponse(payload, status_code=status, headers={"Cache-Control": "no-store"})


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
        _audit_machine(
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
        _audit_machine(
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
        _audit_machine(
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
        _audit_machine(
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
        _audit_machine(
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
        _audit_machine(
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
        _audit_machine(
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
        _audit_machine(
            source_ip=ip,
            token_id=token_id,
            nickname=nickname,
            command=_loggable_command(payload),
            args=_redact_args(payload.get("args") or {}) if isinstance(payload, dict) else {},
            status="error",
            http_status=400,
            error=err or "bad_payload",
        )
        fleet_metrics.record(
            command=_loggable_command(payload),
            status="error",
            error="bad_payload",
            token_id=token_id,
        )
        return JSONResponse({"error": "bad_payload", "detail": err}, status_code=400)

    internal = loopback.read_token()
    if not internal:
        _audit_machine(
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

    timeout = edge_timeout(command)
    fleet_metrics.aisctl_inflight_inc()
    try:
        status, body = await asyncio.to_thread(_proxy_to_aisctl, command, args, internal, timeout)
    finally:
        fleet_metrics.aisctl_inflight_dec()

    duration_ms = int((time.monotonic() - started) * 1000)
    _audit_machine(
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


# ---------------------------------------------------------------------------
# Operator (human) write surface — the same-origin proxy (É2 / strategy M4b)
# ---------------------------------------------------------------------------
#
# The browser NEVER talks to a remote node: CSP ``connect-src 'self'`` forbids
# it, and the node Bearer must never reach the DOM. Instead the dashboard's own
# origin exposes ``POST /fleet/{nickname}/action``; this route authenticates
# the HUMAN (operator session + CSRF), then forwards to the target node's
# machine edge (``POST /api/v1/fleet/{nickname}/command``) holding the node's
# Bearer server-side — the exact request shape ``aisctl fleet push`` sends, so
# the machine path stays untouched. The proxy FORWARDS, it never executes:
# execution stays behind the target node's own edge → loopback → helper funnel.

# Max bytes accepted back from a node's edge (mirrors aisctl fleet push).
_MAX_FORWARD_RESPONSE_BYTES = 1024 * 1024

# Rate limit for the human path, keyed on a single bucket ON PURPOSE: one
# operator per dashboard by design (single session store, single human), and
# the ceiling stays BELOW the machine edge's 30/min so a runaway front-end
# script cannot exhaust the node token's own budget. Do NOT key this by
# session id — N concurrent sessions would multiply the ceiling to 20*N/min
# and defeat that cap; a second session throttling the first is the accepted
# trade-off (review 2026-07-05).
_operator_rate_limiter = TokenRateLimiter(limit=20, window_seconds=60.0)
_OPERATOR_RATE_KEY = "operator"

# Concurrent-forward cap. Long-budget commands (upgrade: 660s at client tier)
# would otherwise pin threads of the process-wide asyncio.to_thread pool —
# shared with every read endpoint — for minutes each. A burst of slow
# forwards must degrade the WRITE surface (503 busy), never the dashboard's
# reads. 4 mirrors aisctl serve's own MAX_CONCURRENT.
_MAX_CONCURRENT_FORWARDS = 4
_forward_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_FORWARDS)


def _audit_operator(**fields: Any) -> None:
    """Audit an event on the operator (human session) write path."""
    audit.log_event(actor_type=audit.ACTOR_OPERATOR, **fields)


def _forward_to_node(
    node: dict[str, Any],
    command: str,
    args: dict[str, Any],
    timeout: float,
) -> tuple[int, dict[str, Any]]:
    """POST a validated command to a node's machine edge. ``(status, body)``.

    Server-side replica of ``aisctl fleet push``'s ``_do_push``: node URL and
    Bearer come from the fleet registry (never from the browser), and the
    ``Origin`` header is set to the node's own URL on purpose — the remote
    edge's same-origin middleware rejects cross-origin POSTs, and a machine
    client asserts its legitimacy by presenting a matching Origin.
    """
    url = str(node.get("asiai_url", "")).rstrip("/")
    token = node.get("auth_token") or ""
    quoted = urllib.parse.quote(str(node.get("nickname", "_")), safe="")
    payload = _json.dumps({"command": command, "args": args}).encode("utf-8")
    req = urllib.request.Request(
        f"{url}/api/v1/fleet/{quoted}/command",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "Origin": url,
            "User-Agent": "asiai-web/operator-proxy",
        },
    )
    try:
        # nosec B310 — URL scheme is validated (http/https) by the fleet
        # registry before a node can be saved; not browser-controlled.
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read(_MAX_FORWARD_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_FORWARD_RESPONSE_BYTES:
                return (502, {"error": "node_response_oversized"})
            try:
                body = _json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return (502, {"error": "node_response_parse_error"})
            return (resp.status, body if isinstance(body, dict) else {"data": body})
    except urllib.error.HTTPError as e:
        try:
            raw = e.read(_MAX_FORWARD_RESPONSE_BYTES + 1)
            body = _json.loads(raw.decode("utf-8")) if raw else {}
            if not isinstance(body, dict):
                body = {"data": body}
        except (ValueError, UnicodeDecodeError, OSError):
            body = {"error": "node_http_error"}
        return (e.code, body)
    except urllib.error.URLError as e:
        # A connect-phase timeout arrives WRAPPED in URLError (urllib wraps
        # OSError during request(), not during getresponse()) — classify it
        # as 504 like a read timeout, not as unreachable.
        if isinstance(e.reason, TimeoutError):
            return (504, {"error": "node_timeout"})
        # Coarse public detail; the full reason stays in local logs (same
        # rationale as _proxy_to_aisctl: no topology leak in responses).
        logger.warning("fleet node %s unreachable: %s", node.get("nickname"), e)
        return (502, {"error": "node_unreachable"})
    except TimeoutError:
        return (504, {"error": "node_timeout"})
    except http.client.HTTPException as e:
        # Non-HTTP or garbled upstream (e.g. an asiai_url mistakenly pointing
        # at a TLS or binary port -> BadStatusLine). urllib propagates these
        # UNWRAPPED from getresponse(); without this clause they would escape
        # as a raw 500 instead of the deliberately coarse 502.
        logger.warning("fleet node %s protocol error: %s", node.get("nickname"), e)
        return (502, {"error": "node_protocol_error"})
    except OSError as e:
        logger.warning("fleet forward I/O error: %s", e)
        return (502, {"error": "node_io_error"})


@router.post("/fleet/{nickname}/action")
async def fleet_operator_action(
    nickname: str,
    request: Request,
    session: OperatorSession = Depends(require_operator_csrf),  # noqa: B008
) -> JSONResponse:
    """Execute a fleet write as the logged-in HUMAN operator (same-origin proxy).

    Authentication: operator session cookie + CSRF token (header
    ``X-CSRF-Token`` or form field ``_csrf``) — ``require_operator_csrf``.

    Request body (JSON)::

        {"command": "<start|stop|...>", "args": {"engine": "..."},
         "confirm": "<nickname>"}          # required for destructive commands

    DESTRUCTIVE commands (purge/install/uninstall/upgrade) additionally
    require ``confirm`` to equal the target nickname — the UI's typed
    confirmation is re-verified server-side, so a scripted or replayed
    request cannot skip it.

    Errors: 401 (no session), 403 (bad CSRF), 404 (unknown node), 400
    (bad payload / missing confirmation), 409 (node has no auth_token),
    429 (rate limit), 503 (forward slots busy), 502/504 (node edge
    unreachable or timed out).
    """
    started = time.monotonic()
    ip = _client_ip(request)

    if not _NICKNAME_RE.match(nickname):
        _audit_operator(
            source_ip=ip,
            nickname="<invalid>",
            command=None,
            status="denied",
            http_status=400,
            error="invalid_nickname",
        )
        fleet_metrics.record(
            command=None, status="denied", error="invalid_nickname", token_id="operator"
        )
        return JSONResponse(
            {
                "error": "bad_nickname",
                "detail": "nickname must match [a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}",
            },
            status_code=400,
        )

    allowed, _remaining, retry_after = _operator_rate_limiter.check(_OPERATOR_RATE_KEY)
    if not allowed:
        _audit_operator(
            source_ip=ip,
            nickname=nickname,
            command=None,
            status="denied",
            http_status=429,
            error="rate_limited",
        )
        fleet_metrics.record(
            command=None, status="denied", error="rate_limited", token_id="operator"
        )
        resp = JSONResponse(
            {"error": "rate_limited", "retry_after": round(retry_after, 1)},
            status_code=429,
        )
        resp.headers["Retry-After"] = str(int(retry_after) + 1)
        return resp

    raw = await request.body()
    if len(raw) > _MAX_BODY_BYTES:
        _audit_operator(
            source_ip=ip,
            nickname=nickname,
            command=None,
            status="denied",
            http_status=413,
            error="body_too_large",
        )
        fleet_metrics.record(
            command=None, status="denied", error="body_too_large", token_id="operator"
        )
        return JSONResponse({"error": "body_too_large"}, status_code=413)
    try:
        payload = _json.loads(raw.decode("utf-8")) if raw else {}
    except (ValueError, UnicodeDecodeError):
        _audit_operator(
            source_ip=ip,
            nickname=nickname,
            command=None,
            status="error",
            http_status=400,
            error="invalid_json",
        )
        fleet_metrics.record(
            command=None, status="error", error="invalid_json", token_id="operator"
        )
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    command, args, err = _validate_command_payload(payload)
    if err is not None or command is None:
        _audit_operator(
            source_ip=ip,
            nickname=nickname,
            command=_loggable_command(payload),
            args=_redact_args(payload.get("args") or {}) if isinstance(payload, dict) else {},
            status="error",
            http_status=400,
            error=err or "bad_payload",
        )
        fleet_metrics.record(
            command=_loggable_command(payload),
            status="error",
            error="bad_payload",
            token_id="operator",
        )
        return JSONResponse({"error": "bad_payload", "detail": err}, status_code=400)

    # Server-side typed confirmation for destructive verbs: the UI modal's
    # "type the nickname" is re-checked HERE, so it cannot be bypassed by
    # calling the API directly with a stolen session.
    if command in DESTRUCTIVE_COMMANDS:
        confirm = payload.get("confirm") if isinstance(payload, dict) else None
        if confirm != nickname:
            _audit_operator(
                source_ip=ip,
                nickname=nickname,
                command=command,
                args=_redact_args(args),
                status="denied",
                http_status=400,
                error="confirmation_required",
            )
            fleet_metrics.record(
                command=command,
                status="denied",
                error="confirmation_required",
                token_id="operator",
            )
            return JSONResponse(
                {
                    "error": "confirmation_required",
                    "detail": (
                        f"'{command}' is destructive: the request body must carry "
                        '"confirm": "<nickname>" matching the target node'
                    ),
                },
                status_code=400,
            )

    node = next(
        (n for n in fleet_config.get_nodes() if n.get("nickname") == nickname),
        None,
    )
    if node is None:
        _audit_operator(
            source_ip=ip,
            nickname=nickname,
            command=command,
            args=_redact_args(args),
            status="denied",
            http_status=404,
            error="unknown_node",
        )
        fleet_metrics.record(
            command=command, status="denied", error="unknown_node", token_id="operator"
        )
        return JSONResponse({"error": "unknown_node"}, status_code=404)
    if not node.get("auth_token") or not node.get("asiai_url"):
        _audit_operator(
            source_ip=ip,
            nickname=nickname,
            command=command,
            args=_redact_args(args),
            status="denied",
            http_status=409,
            error="node_not_writable",
        )
        fleet_metrics.record(
            command=command, status="denied", error="node_not_writable", token_id="operator"
        )
        return JSONResponse(
            {
                "error": "node_not_writable",
                "detail": (
                    "node has no auth_token/url in the fleet registry; add one with "
                    "'asiai fleet add <nick> --url ... --auth-token ...'"
                ),
            },
            status_code=409,
        )

    # Bound concurrent forwards: a long-budget forward (upgrade: 660s) pins a
    # thread of the shared to_thread pool; saturation must answer 503 on the
    # WRITE surface instead of starving the co-hosted read endpoints. The
    # locked() pre-check has a benign race (a competing request may slip in
    # between check and acquire — it then briefly waits instead of 503ing).
    if _forward_semaphore.locked():
        _audit_operator(
            source_ip=ip,
            nickname=nickname,
            command=command,
            args=_redact_args(args),
            status="denied",
            http_status=503,
            error="forwards_busy",
        )
        fleet_metrics.record(
            command=command, status="denied", error="forwards_busy", token_id="operator"
        )
        return JSONResponse(
            {
                "error": "forwards_busy",
                "detail": f"{_MAX_CONCURRENT_FORWARDS} forwards already in flight; retry shortly",
            },
            status_code=503,
        )

    # Two hops out from the loopback budget (proxy → edge → loopback).
    timeout = client_timeout(command)
    async with _forward_semaphore:
        status, body = await asyncio.to_thread(_forward_to_node, node, command, args, timeout)

    duration_ms = int((time.monotonic() - started) * 1000)
    _audit_operator(
        source_ip=ip,
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
        token_id="operator",
    )

    return JSONResponse(
        {**body, "command": command, "nickname": nickname, "duration_ms": duration_ms},
        status_code=status,
    )


# ---------------------------------------------------------------------------
# Audit journal read surface (operator-gated)
# ---------------------------------------------------------------------------
#
# The journal is written by THIS process (asiai.auth.audit) at
# ``~/.local/share/asiai/fleet-audit.jsonl``, so reading it is a local file
# tail — no loopback hop. It is operator-only: entries carry source IPs,
# token ids and command history, which is operational intel an anonymous
# LAN client must not enumerate. A GET needs no CSRF (no state change, and
# without CORS a cross-origin page cannot read the response).

_AUDIT_TAIL_DEFAULT = 100
_AUDIT_TAIL_MAX = 500


@router.get("/api/v1/fleet/audit")
async def api_fleet_audit(
    request: Request,
    limit: int = _AUDIT_TAIL_DEFAULT,
    session: OperatorSession = Depends(require_operator),  # noqa: B008
) -> JSONResponse:
    """Read the local fleet audit journal (newest first). Operator-only.

    Full-scope sessions only — this endpoint serves RAW events (args,
    errors) for the human drawer. Agents get the redacted one-shot
    exchange (``POST /api/v1/fleet/audit-tail``) instead; ``audit:read``
    codes cannot open sessions at all. Query params: ``limit`` (1..500,
    default 100). Errors: 401 (no operator session).
    """
    limit = max(1, min(limit, _AUDIT_TAIL_MAX))
    events = await asyncio.to_thread(audit.read_tail, limit)
    # no-store: source IPs, token ids and the command history must not
    # outlive the operator session in a shared browser's disk cache.
    return JSONResponse(
        {"events": events, "count": len(events)},
        headers={"Cache-Control": "no-store"},
    )


@router.get("/fleet")
async def page_fleet(request: Request):
    """Render the fleet cockpit shell (data arrives via /api/v1/fleet/snapshot).

    The template only needs to know whether ANY node is configured (to show
    the onboarding empty state); the cockpit itself is client-rendered from
    the JSON snapshot so the master-detail selection survives refreshes.
    """
    nodes = [fleet_config.redact_node(n) for n in fleet_config.get_nodes()]
    return templates.TemplateResponse(
        request,
        "fleet.html",
        {"request": request, "nodes": nodes, "nav_active": "fleet"},
    )


@router.get("/journal")
async def page_journal(request: Request):
    """Render the audit journal page shell.

    The page itself is public; the DATA is not — the client fetches
    ``/api/v1/fleet/audit``, which requires an operator session and
    otherwise renders a login invitation.
    """
    return templates.TemplateResponse(
        request,
        "journal.html",
        {"request": request, "nav_active": "journal"},
    )
