"""REST API endpoints for programmatic access."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

router = APIRouter(prefix="/api", tags=["api"])


def _get_or_refresh_snapshot(state) -> dict:
    """Get cached snapshot or collect a fresh one."""
    cached = state.get_cached_snapshot(max_age=5.0)
    if cached:
        return cached

    from asiai.collectors.snapshot import collect_full_snapshot

    snapshot = collect_full_snapshot(state.engines)
    state.set_snapshot_cache(snapshot)

    # Persist engine status
    from asiai.storage.db import store_engine_status

    if snapshot.get("engines_status"):
        store_engine_status(state.db_path, snapshot["engines_status"])

    return snapshot


@router.get("/snapshot")
async def api_snapshot(request: Request) -> JSONResponse:
    """Full system + engine snapshot. Cached 5s."""
    state = request.app.state.app_state
    snapshot = _get_or_refresh_snapshot(state)
    return JSONResponse(snapshot)


@router.get("/status")
async def api_status(request: Request) -> JSONResponse:
    """Lightweight health check. Cached 10s. Target < 500ms."""
    state = request.app.state.app_state

    cached = state.get_cached_snapshot(max_age=10.0)
    if cached:
        snapshot = cached
    else:
        from asiai.collectors.snapshot import collect_full_snapshot

        snapshot = collect_full_snapshot(state.engines)
        state.set_snapshot_cache(snapshot)

    # Build lightweight response
    engines_up = {}
    for es in snapshot.get("engines_status", []):
        engines_up[es["name"]] = es.get("reachable", False)

    all_reachable = all(engines_up.values()) if engines_up else False
    any_reachable = any(engines_up.values()) if engines_up else False

    if all_reachable:
        status = "ok"
    elif any_reachable:
        status = "degraded"
    else:
        status = "error"

    return JSONResponse(
        {
            "status": status,
            "ts": snapshot.get("ts", int(time.time())),
            "uptime": snapshot.get("uptime", 0),
            "engines": engines_up,
            "memory_pressure": snapshot.get("mem_pressure", "unknown"),
            "thermal_level": snapshot.get("thermal_level", "unknown"),
        }
    )


@router.get("/metrics")
async def api_metrics(request: Request) -> Response:
    """Prometheus exposition format endpoint."""
    state = request.app.state.app_state
    snapshot = _get_or_refresh_snapshot(state)

    # Get latest benchmark results if available
    benchmarks = None
    try:
        from asiai.storage.db import query_latest_benchmarks

        benchmarks = query_latest_benchmarks(state.db_path)
    except Exception:
        pass

    from asiai.web.prometheus import format_prometheus

    body = format_prometheus(snapshot, benchmarks)
    return Response(
        content=body,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
