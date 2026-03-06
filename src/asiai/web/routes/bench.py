"""Benchmark route — run benchmarks from the web with live SSE progress."""

from __future__ import annotations

import asyncio
import json
import logging
import threading

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/bench", response_class=HTMLResponse)
async def bench_page(request: Request):
    """Render the benchmark page with form and results area."""
    state = request.app.state.app_state
    templates = request.app.state.templates

    engines_data, prompts = await asyncio.gather(
        asyncio.to_thread(_get_engines_for_form, state),
        asyncio.to_thread(_get_prompts),
    )

    return templates.TemplateResponse(
        request,
        "bench.html",
        {
            "nav_active": "bench",
            "engines": engines_data,
            "prompts": prompts,
            "bench_running": state.get_bench_snapshot()["running"],
        },
    )


@router.post("/bench/run")
async def bench_run(request: Request):
    """Start a benchmark in a background thread."""
    state = request.app.state.app_state
    form = await request.form()

    if state.get_bench_snapshot()["running"]:
        return JSONResponse({"error": "Benchmark already running"}, status_code=409)

    # Parse form data
    model = form.get("model", "")
    engine_names = form.getlist("engines")
    prompt_names = form.getlist("prompts")
    try:
        runs = int(form.get("runs", 3))
    except (TypeError, ValueError):
        return JSONResponse({"error": "Invalid runs value"}, status_code=422)
    if runs < 1 or runs > 100:
        return JSONResponse({"error": "runs must be between 1 and 100"}, status_code=422)
    power = form.get("power") == "on"

    # Reset status
    state.reset_bench(running=True, progress="Starting benchmark...")

    # Run in background thread
    thread = threading.Thread(
        target=_run_benchmark_thread,
        args=(state, model, engine_names, prompt_names or None, runs, power),
        daemon=True,
    )
    thread.start()

    return JSONResponse({"status": "started"})


@router.get("/bench/stream")
async def bench_stream(request: Request):
    """SSE endpoint for benchmark progress."""
    from starlette.responses import StreamingResponse

    state = request.app.state.app_state

    if not state.acquire_sse():
        return JSONResponse({"error": "Too many SSE connections"}, status_code=429)

    async def event_generator():
        try:
            last_progress = ""
            while True:
                if await request.is_disconnected():
                    break
                snap = state.get_bench_snapshot()
                current = json.dumps(snap)
                if current != last_progress:
                    yield f"data: {current}\n\n"
                    last_progress = current
                if snap["done"]:
                    break
                await asyncio.sleep(0.5)
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


@router.get("/bench/export")
async def bench_export(request: Request):
    """Export last benchmark results as JSON."""
    state = request.app.state.app_state

    rows = await asyncio.to_thread(_get_latest_bench_rows, state)
    if not rows:
        return JSONResponse({"error": "No benchmark data"}, status_code=404)

    import tempfile

    from asiai.benchmark.reporter import aggregate_results, export_benchmark

    report = aggregate_results(rows)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = f"{tmp_dir}/export.json"
        export_benchmark(rows, report, tmp_path)
        with open(tmp_path) as f:
            export_data = json.load(f)

    return JSONResponse(
        export_data,
        headers={"Content-Disposition": "attachment; filename=asiai-bench.json"},
    )


def _run_benchmark_thread(
    state, model: str, engine_names: list[str], prompt_names: list[str] | None,
    runs: int, power: bool,
) -> None:
    """Run benchmark in background thread, updating state.bench_status."""
    try:
        from asiai.benchmark.reporter import aggregate_results
        from asiai.benchmark.runner import find_common_model, run_benchmark
        from asiai.storage.db import store_benchmark

        # Filter engines
        engines = state.engines
        if engine_names:
            wanted = {n.lower() for n in engine_names}
            engines = [e for e in engines if e.name in wanted]

        if not engines:
            state.update_bench(error="No engines available", running=False, done=True)
            return

        # Resolve model
        actual_model = find_common_model(engines, model)
        if not actual_model:
            state.update_bench(error="No model available to benchmark", running=False, done=True)
            return

        state.update_bench(progress=f"Benchmarking {actual_model}...", total_runs=runs)

        bench_run = run_benchmark(
            engines, actual_model, prompt_names, runs=runs, power=power,
        )

        # Store results
        if bench_run.results:
            store_benchmark(state.db_path, bench_run.results)

        # Aggregate
        report = aggregate_results(bench_run.results)
        report["model"] = actual_model

        state.update_bench(progress="Benchmark complete", running=False, done=True)

    except Exception as e:
        logger.exception("Benchmark failed")
        state.update_bench(error=str(e), running=False, done=True)


def _get_engines_for_form(state) -> list[dict]:
    """Get engine names and their running models for the bench form."""
    results = []
    for engine in state.engines:
        try:
            reachable = engine.status().reachable
            models = [m.name for m in engine.list_running()] if reachable else []
            results.append(
                {"name": engine.name, "reachable": reachable, "models": models}
            )
        except Exception:
            results.append({"name": engine.name, "reachable": False, "models": []})
    return results


def _get_prompts() -> list[dict]:
    """Get available benchmark prompts."""
    from asiai.benchmark.prompts import PROMPTS

    return [
        {"name": p.name, "label": p.label, "max_tokens": p.max_tokens}
        for p in PROMPTS.values()
    ]


def _get_latest_bench_rows(state) -> list[dict]:
    """Get the latest benchmark session rows from DB."""
    from asiai.storage.db import query_benchmarks

    rows = query_benchmarks(state.db_path, hours=24)
    if not rows:
        return []
    latest_ts = max(r["ts"] for r in rows)
    return [r for r in rows if r["ts"] == latest_ts]
