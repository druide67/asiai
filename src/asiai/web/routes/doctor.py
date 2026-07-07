"""Doctor route — diagnostic health checks."""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()

# The doctor page renders only these categories; the ``alerting`` check
# carries the raw webhook URL (a bearer credential) and ``daemon`` carries
# PIDs — neither is ever shown to a browser. The JSON twin is reachable
# over the LAN/mesh with no auth, so it must expose no MORE than the HTML:
# same allowlist, enforced here.
_WEB_SAFE_CHECK_CATEGORIES = frozenset({"system", "engine", "database"})


@router.get("/api/v1/doctor")
async def api_doctor(request: Request) -> JSONResponse:
    """Doctor checks as JSON — the machine-readable twin of ``/doctor``.

    Exists so the fleet hub can proxy another node's diagnostics
    (per-node Doctor view) without scraping HTML. Same LAN read-only
    posture as ``/api/v1/snapshot`` — and the same category allowlist as
    the page, so no secret-bearing check (webhook URL, daemon PIDs) leaks
    through a surface the browser never sees.
    """
    state = request.app.state.app_state
    checks = await asyncio.to_thread(_run_checks, state)
    safe = [c for c in checks if c.get("category") in _WEB_SAFE_CHECK_CATEGORIES]
    return JSONResponse({"ts": int(time.time()), "checks": safe})


@router.get("/doctor", response_class=HTMLResponse)
async def doctor_page(request: Request) -> HTMLResponse:
    """Render the doctor page with health checks."""
    state = request.app.state.app_state
    templates = request.app.state.templates

    checks = await asyncio.to_thread(_run_checks, state)

    return templates.TemplateResponse(
        request,
        "doctor.html",
        {
            "nav_active": "doctor",
            "checks": checks,
        },
    )


@router.post("/doctor/refresh", response_class=HTMLResponse)
async def doctor_refresh(request: Request) -> HTMLResponse:
    """htmx partial: re-run checks and return updated cards."""
    state = request.app.state.app_state
    templates = request.app.state.templates

    checks = await asyncio.to_thread(_run_checks, state)

    return templates.TemplateResponse(
        request,
        "partials/doctor_checks.html",
        {
            "checks": checks,
        },
    )


def _run_checks(state) -> list[dict]:
    """Run doctor checks and return as dicts for templates."""
    from asiai.doctor import run_checks

    results = run_checks(state.db_path)
    return [
        {
            "category": c.category,
            "name": c.name,
            "status": c.status,
            "message": c.message,
            "fix": c.fix,
        }
        for c in results
    ]
