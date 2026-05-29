"""Engine versions endpoints (read-only).

- ``GET /api/v1/versions`` — running/installed/available per engine, cached
  60s. ``?upstream=1`` opts into network fetches (PyPI/GitHub).
- ``GET /versions`` — HTML table page with changelog links.
- ``GET /versions/grid-fragment`` — HTMX auto-refresh fragment.

``collect_reports`` is synchronous (subprocess + optional network), so every
handler wraps it in ``asyncio.to_thread`` to keep the uvicorn event loop
responsive — same discipline as the fleet routes.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from asiai.versions.cli import collect_reports

if TYPE_CHECKING:
    from asiai.web.state import AppState

router = APIRouter(tags=["versions"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# Network fetches can be slow; cache upstream results longer than offline.
_OFFLINE_TTL = 60.0
_UPSTREAM_TTL = 600.0


def _aggregate_versions(state: AppState, check_upstream: bool) -> dict:
    """Return a cached versions snapshot or compute a fresh one."""
    key = "upstream" if check_upstream else "offline"
    ttl = _UPSTREAM_TTL if check_upstream else _OFFLINE_TTL
    cached = state.get_versions_cache(key, max_age=ttl)
    if cached:
        return cached
    with state._versions_lock:
        cached = state.get_versions_cache(key, max_age=ttl)
        if cached:
            return cached
        reports = collect_reports(check_upstream=check_upstream)
        snapshot = {
            "polled_at": int(time.time()),
            "check_upstream": check_upstream,
            "engines": [r.to_dict() for r in reports],
        }
        state.set_versions_cache(key, snapshot)
        return snapshot


def _wants_upstream(request: Request) -> bool:
    """Parse the ``?upstream=1`` query flag (also accepts true/yes/on)."""
    raw = request.query_params.get("upstream", "")
    return raw.lower() in ("1", "true", "yes", "on")


@router.get("/api/v1/versions")
async def api_versions(request: Request) -> JSONResponse:
    """Per-engine running/installed/available versions (cached)."""
    state = request.app.state.app_state
    check_upstream = _wants_upstream(request)
    snapshot = await asyncio.to_thread(_aggregate_versions, state, check_upstream)
    return JSONResponse(snapshot)


@router.get("/versions")
async def page_versions(request: Request):
    """Render the versions HTML page (server-rendered table + HTMX refresh)."""
    state = request.app.state.app_state
    check_upstream = _wants_upstream(request)
    snapshot = await asyncio.to_thread(_aggregate_versions, state, check_upstream)
    return templates.TemplateResponse(
        request,
        "versions.html",
        {"request": request, "snapshot": snapshot, "nav_active": "versions"},
    )


@router.get("/versions/grid-fragment")
async def page_versions_fragment(request: Request):
    """Return the versions table as an HTML fragment for HTMX auto-refresh."""
    state = request.app.state.app_state
    check_upstream = _wants_upstream(request)
    snapshot = await asyncio.to_thread(_aggregate_versions, state, check_upstream)
    return templates.TemplateResponse(
        request,
        "partials/versions_grid.html",
        {"request": request, "snapshot": snapshot},
    )
