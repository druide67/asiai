"""Fleet mode endpoints: aggregate status across multiple asiai nodes.

Phase 1 ships read-only routes:

- ``GET /api/v1/fleet/nodes`` — list configured nodes (no secrets)
- ``GET /api/v1/fleet/snapshot`` — parallel poll + aggregate, cached 10s
- ``GET /fleet`` — HTMX-driven HTML grid page

Phase 2 will fill the body of ``POST /api/v1/fleet/{nickname}/command``
(currently a 501 stub).

The synchronous parallel poll lives in ``asiai.fleet.poll`` and uses a
ThreadPoolExecutor + urllib (stdlib only). Each FastAPI handler wraps
that blocking call in ``asyncio.to_thread`` so the uvicorn event loop
stays responsive while a slow node times out.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

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
    # Fallback when only the legacy raw exception name is stored.
    lowered = raw.lower()
    if any(k in lowered for k in ("timeout", "refused", "gaierror", "dns")):
        return "unreachable"
    return "error"


if TYPE_CHECKING:
    from asiai.web.state import AppState

router = APIRouter(tags=["fleet"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/api/v1/fleet/nodes")
async def api_fleet_nodes() -> JSONResponse:
    """Return the configured fleet nodes (auth_token redacted).

    ``last_status`` is normalized to the public 3-value enum
    (``ok`` / ``unreachable`` / ``error`` / ``unknown``) instead of the
    raw exception class name, so that an attacker who can read this
    endpoint cannot fingerprint the LAN by distinguishing
    ``ConnectionRefusedError`` (host UP, port DOWN) from
    ``TimeoutError`` (host DOWN or firewall).
    """
    nodes_out = []
    for n in fleet_config.get_nodes():
        redacted = fleet_config.redact_node(n)
        if redacted:
            redacted["last_status"] = _public_status(
                redacted.get("last_status"),
                # error_class isn't stored in fleet.json (last_status holds
                # the raw exception name there), so we just pass None and
                # rely on the substring fallback in _public_status.
                None,
            )
        nodes_out.append(redacted)
    return JSONResponse({"nodes": nodes_out})


def _aggregate_fleet_snapshot(state: AppState, timeout: float = 5.0) -> dict:
    """Get cached fleet snapshot or run a fresh parallel poll.

    A ``state._fleet_poll_lock`` serializes the fan-out poll so two
    concurrent GETs that arrive after the 10s cache expires do not both
    fire N HTTP requests at every node (thundering herd). The lock is
    short-held: the second caller will block briefly, then see the
    snapshot the first caller just wrote into the cache.

    Each successful poll also writes ``last_seen``/``last_status`` back
    into ``fleet.json`` so the CLI ``asiai fleet list`` table stays
    consistent with what the web dashboard observes.
    """
    cached = state.get_fleet_cache(max_age=10.0)
    if cached:
        return cached

    with state._fleet_poll_lock:
        # Re-check the cache after acquiring the lock: a concurrent
        # caller may have just populated it.
        cached = state.get_fleet_cache(max_age=10.0)
        if cached:
            return cached

        nodes = fleet_config.get_nodes()
        polls = poll_all(nodes, timeout=timeout)
        snapshot = {
            "polled_at": int(time.time()),
            "nodes": [p.to_dict() for p in polls],
        }
        state.set_fleet_cache(snapshot)

        # Persist last_seen / last_status back to fleet.json so the
        # CLI table reflects the same observations as the web view.
        for p in polls:
            fleet_config.touch_node_status(p.nickname, ok=p.ok, error=p.error)

        return snapshot


@router.get("/api/v1/fleet/snapshot")
async def api_fleet_snapshot(request: Request) -> JSONResponse:
    """Parallel poll of every configured node, cached 10s.

    The poll itself is blocking (ThreadPoolExecutor + urllib), so we
    offload it to a worker thread to keep the event loop responsive
    while a slow node times out.
    """
    state = request.app.state.app_state
    snapshot = await asyncio.to_thread(_aggregate_fleet_snapshot, state)
    return JSONResponse(snapshot)


@router.post("/api/v1/fleet/{nickname}/command")
async def api_fleet_command(nickname: str) -> JSONResponse:
    """Reserved for Phase 2 (write commands). Currently a 501 stub."""
    return JSONResponse(
        {
            "error": "not_implemented",
            "message": (
                "Fleet write commands are planned for Phase 2. Track upstream issue for status."
            ),
            "nickname": nickname,
        },
        status_code=501,
    )


@router.get("/fleet")
async def page_fleet(request: Request):
    """Render the fleet HTML page (server-rendered grid + HTMX refresh)."""
    state = request.app.state.app_state
    snapshot = await asyncio.to_thread(_aggregate_fleet_snapshot, state)
    nodes = [fleet_config.redact_node(n) for n in fleet_config.get_nodes()]
    return templates.TemplateResponse(
        request,
        "fleet.html",
        {
            "request": request,
            "snapshot": snapshot,
            "nodes": nodes,
        },
    )


@router.get("/fleet/grid-fragment")
async def page_fleet_grid_fragment(request: Request):
    """Return the fleet grid as an HTML fragment for HTMX auto-refresh.

    The full ``/fleet`` page bootstraps the wrapper div + this fragment;
    subsequent ``hx-trigger="every 10s"`` requests target this endpoint
    and swap its rendered fragment into the wrapper's ``innerHTML``. This
    is required because the JSON endpoint ``/api/v1/fleet/snapshot``
    cannot be swapped directly into the DOM as HTMX innerHTML would
    inject raw JSON text.
    """
    state = request.app.state.app_state
    snapshot = await asyncio.to_thread(_aggregate_fleet_snapshot, state)
    return templates.TemplateResponse(
        request,
        "partials/fleet_grid.html",
        {
            "request": request,
            "snapshot": snapshot,
        },
    )
