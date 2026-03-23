"""Monitor route — real-time system monitoring via SSE."""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from asiai.web.state import AppState

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()


@router.get("/monitor", response_class=HTMLResponse)
async def monitor_page(request: Request) -> HTMLResponse:
    """Render the monitor page."""
    state = request.app.state.app_state
    templates = request.app.state.templates

    snapshot = await asyncio.to_thread(_get_snapshot, state)

    return templates.TemplateResponse(
        request,
        "monitor.html",
        {
            "nav_active": "monitor",
            "snapshot": snapshot,
        },
    )


@router.get("/monitor/stream")
async def monitor_stream(request: Request) -> Response:
    """SSE endpoint for real-time monitoring data."""
    from starlette.responses import StreamingResponse

    state = request.app.state.app_state

    if not state.acquire_sse():
        return JSONResponse({"error": "Too many SSE connections"}, status_code=429)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                snapshot = await asyncio.to_thread(_get_snapshot, state)
                data = json.dumps(
                    {
                        "cpu_load_1": snapshot.get("cpu_load_1", 0),
                        "cpu_load_5": snapshot.get("cpu_load_5", 0),
                        "cpu_load_15": snapshot.get("cpu_load_15", 0),
                        "cpu_cores": snapshot.get("cpu_cores", 1),
                        "mem_total": snapshot.get("mem_total", 0),
                        "mem_used": snapshot.get("mem_used", 0),
                        "mem_pressure": snapshot.get("mem_pressure", "unknown"),
                        "thermal_level": snapshot.get("thermal_level", "unknown"),
                        "thermal_speed_limit": snapshot.get("thermal_speed_limit", -1),
                        "uptime": snapshot.get("uptime", 0),
                        "models": snapshot.get("models", []),
                        "gpu_utilization_pct": snapshot.get("gpu_utilization_pct", -1),
                        "gpu_renderer_pct": snapshot.get("gpu_renderer_pct", -1),
                        "gpu_tiler_pct": snapshot.get("gpu_tiler_pct", -1),
                        "gpu_mem_in_use": snapshot.get("gpu_mem_in_use", 0),
                        "gpu_mem_allocated": snapshot.get("gpu_mem_allocated", 0),
                        "ts": int(time.time()),
                    }
                )
                yield f"data: {data}\n\n"
                await asyncio.sleep(5)
        finally:
            state.release_sse()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _get_snapshot(state: AppState) -> dict:
    """Collect system snapshot."""
    from asiai.collectors.snapshot import collect_snapshot

    try:
        return collect_snapshot(state.engines, ioreport_sampler=state.ioreport_sampler)
    except Exception:
        return {}
