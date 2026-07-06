"""Dashboard route — main landing page.

Since the multi-node redesign (Lot 2, direction D) the page is a shell:
node blocks are data-driven client-side from ``/api/v1/fleet/snapshot``
(with a local-snapshot fallback when no fleet is configured). The only
server-rendered data left is the last benchmark, which lives in this
hub's local DB.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render the main dashboard page."""
    state = request.app.state.app_state
    templates = request.app.state.templates

    last_bench = await asyncio.to_thread(_get_last_bench, state)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "nav_active": "dashboard",
            "last_bench": last_bench,
        },
    )


def _get_last_bench(state) -> dict | None:
    """Get the most recent benchmark from DB."""
    from asiai.benchmark.reporter import aggregate_results
    from asiai.storage.db import query_benchmarks

    try:
        rows = query_benchmarks(state.db_path, hours=24 * 7)
        if not rows:
            return None
        # Group by timestamp — get the latest bench session
        latest_ts = max(r["ts"] for r in rows)
        latest_rows = [r for r in rows if r["ts"] == latest_ts]
        report = aggregate_results(latest_rows)
        return report
    except Exception:
        return None
