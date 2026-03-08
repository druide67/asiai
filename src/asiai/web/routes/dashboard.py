"""Dashboard route — main landing page."""

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

    # Collect data in parallel using asyncio.to_thread
    engines_data, snapshot, last_bench = await asyncio.gather(
        asyncio.to_thread(_get_engines_data, state),
        asyncio.to_thread(_get_snapshot, state),
        asyncio.to_thread(_get_last_bench, state),
    )

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "nav_active": "dashboard",
            "engines": engines_data,
            "snapshot": snapshot,
            "last_bench": last_bench,
        },
    )


def _get_engines_data(state) -> list[dict]:
    """Get engine info with models."""
    results = []
    for engine in state.engines:
        try:
            reachable = engine.status().reachable
            models = engine.list_running() if reachable else []
            results.append(
                {
                    "name": engine.name,
                    "url": engine.base_url,
                    "version": engine.version() if reachable else "",
                    "reachable": reachable,
                    "models": [
                        {
                            "name": m.name,
                            "size_vram": m.size_vram,
                            "size_total": m.size_total,
                            "format": m.format,
                            "quantization": m.quantization,
                            "context_length": m.context_length,
                        }
                        for m in models
                    ],
                }
            )
        except Exception:
            results.append(
                {
                    "name": engine.name,
                    "url": engine.base_url,
                    "version": "",
                    "reachable": False,
                    "models": [],
                }
            )
    return results


def _get_snapshot(state) -> dict:
    """Collect system snapshot."""
    from asiai.collectors.snapshot import collect_snapshot

    try:
        return collect_snapshot(state.engines)
    except Exception:
        return {}


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
