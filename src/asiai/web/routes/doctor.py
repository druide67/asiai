"""Doctor route — diagnostic health checks."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


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
