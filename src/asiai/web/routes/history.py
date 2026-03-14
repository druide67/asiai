"""History route — benchmark history with charts and data table."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()


@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request) -> HTMLResponse:
    """Render the history page with charts and data table."""
    templates = request.app.state.templates

    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "nav_active": "history",
        },
    )


@router.get("/api/history")
async def api_history(
    request: Request,
    hours: int = Query(default=168, ge=1, le=8760),
    since: int = Query(default=0, ge=0),
    until: int = Query(default=0, ge=0),
) -> JSONResponse:
    """JSON API: monitoring history for charts."""
    state = request.app.state.app_state

    from asiai.storage.db import query_history

    rows = await asyncio.to_thread(query_history, state.db_path, hours, since, until)

    return JSONResponse(
        [
            {
                "ts": r["ts"],
                "cpu_load_1": r.get("cpu_load_1", 0),
                "mem_used": r.get("mem_used", 0),
                "mem_total": r.get("mem_total", 0),
                "thermal_level": r.get("thermal_level", "unknown"),
                "mem_pressure": r.get("mem_pressure", "unknown"),
                "gpu_utilization_pct": r.get("gpu_utilization_pct", -1),
                "gpu_renderer_pct": r.get("gpu_renderer_pct", -1),
                "gpu_tiler_pct": r.get("gpu_tiler_pct", -1),
                "gpu_mem_in_use": r.get("gpu_mem_in_use", 0),
                "gpu_mem_allocated": r.get("gpu_mem_allocated", 0),
            }
            for r in rows
        ]
    )


@router.get("/api/benchmarks")
async def api_benchmarks(
    request: Request,
    hours: int = Query(default=168, ge=0, le=8760),
    model: str = Query(default=""),
    engine: str = Query(default=""),
    since: int = Query(default=0, ge=0),
    until: int = Query(default=0, ge=0),
) -> JSONResponse:
    """JSON API: benchmark results for charts."""
    state = request.app.state.app_state

    from asiai.storage.db import query_benchmarks

    rows = await asyncio.to_thread(
        query_benchmarks, state.db_path, hours, model, since, until
    )

    if engine:
        rows = [r for r in rows if r.get("engine") == engine]

    return JSONResponse(
        [
            {
                "ts": r.get("ts", 0),
                "engine": r.get("engine", ""),
                "model": r.get("model", ""),
                "prompt_type": r.get("prompt_type", ""),
                "tok_per_sec": r.get("tok_per_sec", 0),
                "ttft_ms": r.get("ttft_ms", 0),
                "total_duration_ms": r.get("total_duration_ms", 0),
                "vram_bytes": r.get("vram_bytes", 0),
                "power_watts": r.get("power_watts", 0),
                "tok_per_sec_per_watt": r.get("tok_per_sec_per_watt", 0),
                "run_index": r.get("run_index", 0),
                "context_size": r.get("context_size", 0),
                "engine_version": r.get("engine_version", ""),
                "load_time_ms": r.get("load_time_ms", 0),
            }
            for r in rows
        ]
    )


@router.get("/api/benchmark-process")
async def api_benchmark_process(
    request: Request,
    hours: int = Query(default=168, ge=1, le=2160),
    engine: str = Query(default=""),
) -> JSONResponse:
    """JSON API: benchmark process metrics (CPU/RSS per run)."""
    state = request.app.state.app_state

    from asiai.storage.db import query_benchmark_process

    rows = await asyncio.to_thread(
        query_benchmark_process, state.db_path, hours, engine
    )
    return JSONResponse(rows)


@router.get("/api/engine-history")
async def api_engine_history(
    request: Request,
    hours: int = Query(default=168, ge=1, le=2160),
    engine: str = Query(default=""),
) -> JSONResponse:
    """JSON API: engine status history for observability."""
    state = request.app.state.app_state

    from asiai.storage.db import query_engine_status_history

    rows = await asyncio.to_thread(query_engine_status_history, state.db_path, hours, engine)
    return JSONResponse(rows)
