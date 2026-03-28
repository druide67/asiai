"""Benchmark route — run benchmarks from the web with live SSE progress."""

from __future__ import annotations

import asyncio
import json
import logging
import threading

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/bench", response_class=HTMLResponse)
async def bench_page(request: Request) -> HTMLResponse:
    """Render the benchmark page with form and results area."""
    state = request.app.state.app_state
    templates = request.app.state.templates

    engines_data, prompts, power_available = await asyncio.gather(
        asyncio.to_thread(_get_engines_for_form, state),
        asyncio.to_thread(_get_prompts),
        asyncio.to_thread(_check_power_available),
    )

    # Check if IOReport provides always-on power (no sudo)
    ioreport_power = False
    try:
        from asiai.collectors.ioreport import ioreport_available

        ioreport_power = ioreport_available()
    except Exception:
        pass

    return templates.TemplateResponse(
        request,
        "bench.html",
        {
            "nav_active": "bench",
            "engines": engines_data,
            "prompts": prompts,
            "bench_running": state.get_bench_snapshot()["running"],
            "power_available": power_available,
            "ioreport_power": ioreport_power,
        },
    )


@router.post("/bench/run")
async def bench_run(request: Request) -> JSONResponse:
    """Start a benchmark in a background thread."""
    state = request.app.state.app_state
    form = await request.form()

    if state.get_bench_snapshot()["running"]:
        return JSONResponse({"error": "Benchmark already running"}, status_code=409)

    # Parse form data
    compare_mode = form.get("compare_mode") == "on"
    compare_models = form.getlist("compare_models")
    model = form.get("model_custom") or form.get("model", "")
    engine_names = form.getlist("engines")
    prompt_names = form.getlist("prompts")
    quick = bool(form.get("quick"))
    try:
        runs = int(form.get("runs", 3))
    except (TypeError, ValueError):
        return JSONResponse({"error": "Invalid runs value"}, status_code=422)
    if runs < 1 or runs > 100:
        return JSONResponse({"error": "runs must be between 1 and 100"}, status_code=422)
    power = form.get("power") == "on"
    # Card & share: quick mode always enables both; advanced form uses checkboxes
    generate_card = bool(form.get("card")) or quick
    share = bool(form.get("share")) or quick

    # Quick mode overrides
    if quick:
        prompt_names = ["code"]
        runs = 1

    # Parse context_size
    context_size_map = {"4k": 4096, "16k": 16384, "32k": 32768, "64k": 65536}
    context_size_raw = form.get("context_size", "")
    context_size = context_size_map.get(context_size_raw, 0)

    # Reset status
    state.reset_bench(running=True, progress="Starting benchmark...")

    # Run in background thread
    thread = threading.Thread(
        target=_run_benchmark_thread,
        args=(
            state,
            model,
            engine_names,
            prompt_names or None,
            runs,
            power,
            context_size,
            generate_card,
            share,
            compare_models if compare_mode else None,
        ),
        daemon=True,
    )
    thread.start()

    return JSONResponse({"status": "started"})


@router.get("/bench/stream")
async def bench_stream(request: Request) -> Response:
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
async def bench_export(request: Request) -> JSONResponse:
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
    state,
    model: str,
    engine_names: list[str],
    prompt_names: list[str] | None,
    runs: int,
    power: bool,
    context_size: int = 0,
    generate_card: bool = True,
    share: bool = True,
    compare_models: list[str] | None = None,
) -> None:
    """Run benchmark in background thread, updating state.bench_status."""
    try:
        import os

        from asiai.benchmark.reporter import aggregate_results
        from asiai.benchmark.runner import BenchmarkSlot, find_common_model, run_benchmark
        from asiai.storage.db import store_benchmark

        # Filter engines
        engines = state.engines
        if engine_names:
            wanted = {n.lower() for n in engine_names}
            engines = [e for e in engines if e.name in wanted]

        if not engines and not compare_models:
            state.update_bench(error="No engines available", running=False, done=True)
            return

        # Compare mode: build slots from "model@engine" strings
        if compare_models:
            engine_map = {e.name: e for e in state.engines}
            slots = []
            for entry in compare_models:
                if "@" in entry:
                    m, e = entry.rsplit("@", 1)
                    eng = engine_map.get(e)
                    if eng:
                        slots.append(BenchmarkSlot(engine=eng, model=m))
                else:
                    # model only — use all engines
                    for eng in engines:
                        slots.append(BenchmarkSlot(engine=eng, model=entry))

            if not slots:
                state.update_bench(
                    error="No valid model@engine pairs",
                    running=False,
                    done=True,
                )
                return

            actual_model = slots[0].model
            state.update_bench(
                progress=f"Comparing {len(slots)} model×engine slots...",
                total_runs=runs,
            )

            bench_run = run_benchmark(
                None,
                None,
                prompt_names,
                runs=runs,
                power=power,
                context_size=context_size,
                slots=slots,
                progress_cb=lambda msg: state.update_bench(progress=msg),
            )
        else:
            # Standard mode: single model across engines
            actual_model = find_common_model(engines, model)
            if not actual_model:
                state.update_bench(
                    error="No model available to benchmark",
                    running=False,
                    done=True,
                )
                return

            state.update_bench(
                progress=f"Benchmarking {actual_model}...",
                total_runs=runs,
            )

            bench_run = run_benchmark(
                engines,
                actual_model,
                prompt_names,
                runs=runs,
                power=power,
                context_size=context_size,
                progress_cb=lambda msg: state.update_bench(progress=msg),
            )

        # Store results
        if bench_run.results:
            store_benchmark(state.db_path, bench_run.results)
            from asiai.storage.db import store_benchmark_process

            store_benchmark_process(state.db_path, bench_run.results)

        # Aggregate
        report = aggregate_results(bench_run.results)
        report["model"] = actual_model

        # --- Card generation (never blocks benchmark completion) ---
        if not generate_card:
            state.update_bench(progress="Benchmark complete", running=False, done=True)
            return
        try:
            from asiai.benchmark.card import (
                convert_svg_to_png,
                download_card_png,
                extract_card_metadata,
                generate_card_svg,
                get_share_url,
                save_card,
            )

            first = bench_run.results[0] if bench_run.results else {}
            eng_vers, pw_data, eng_quants = extract_card_metadata(bench_run.results)
            svg = generate_card_svg(
                report,
                hw_chip=first.get("hw_chip", ""),
                model_quantization=first.get("model_quantization", ""),
                ram_gb=first.get("ram_gb", 0),
                gpu_cores=first.get("gpu_cores", 0),
                context_size=first.get("context_size", 0),
                engine_versions=eng_vers,
                power_data=pw_data,
                engine_quants=eng_quants,
            )
            svg_path = save_card(svg, fmt="svg")
            svg_filename = os.path.basename(svg_path)

            png_filename = ""
            share_url = ""

            # Try share → API PNG (network)
            if share:
                try:
                    import base64

                    from asiai.community import build_submission, submit_benchmark

                    payload = build_submission(bench_run.results, report)
                    # Include locally-rendered PNG (macOS sips)
                    local_png = convert_svg_to_png(svg_path)
                    if local_png:
                        try:
                            with open(local_png, "rb") as pf:
                                payload["card_png_b64"] = base64.b64encode(pf.read()).decode(
                                    "ascii"
                                )
                        except OSError:
                            pass
                    result = submit_benchmark(payload, db_path=state.db_path)
                    if result.success:
                        share_url = get_share_url(result.submission_id)
                        png_path = download_card_png(result.submission_id)
                        if png_path:
                            png_filename = os.path.basename(png_path)
                except Exception:
                    pass  # network unavailable

            # Fallback: sips local (macOS native)
            if not png_filename:
                png_path = convert_svg_to_png(svg_path)
                if png_path:
                    png_filename = os.path.basename(png_path)

            state.update_bench(
                card_svg_url=f"/cards/{svg_filename}",
                card_png_url=f"/cards/{png_filename}" if png_filename else "",
                share_url=share_url,
            )
        except Exception as exc:
            logger.warning("Card generation failed: %s", exc)
            state.update_bench(card_error=str(exc))

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
            results.append({"name": engine.name, "reachable": reachable, "models": models})
        except Exception:
            results.append({"name": engine.name, "reachable": False, "models": []})
    return results


def _get_prompts() -> list[dict]:
    """Get available benchmark prompts."""
    from asiai.benchmark.prompts import PROMPTS

    return [
        {"name": p.name, "label": p.label, "max_tokens": p.max_tokens} for p in PROMPTS.values()
    ]


def _get_latest_bench_rows(state) -> list[dict]:
    """Get the latest benchmark session rows from DB."""
    from asiai.storage.db import query_benchmarks

    rows = query_benchmarks(state.db_path, hours=24)
    if not rows:
        return []
    latest_ts = max(r["ts"] for r in rows)
    return [r for r in rows if r["ts"] == latest_ts]


def _check_power_available() -> bool:
    """Check if power monitoring is available (IOReport or sudo powermetrics)."""
    # IOReport: no sudo needed, preferred
    try:
        from asiai.collectors.ioreport import ioreport_available

        if ioreport_available():
            return True
    except Exception:
        pass

    # Fallback: sudo powermetrics
    import subprocess

    try:
        result = subprocess.run(
            ["sudo", "-n", "powermetrics", "--help"],
            capture_output=True,
            timeout=3,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
