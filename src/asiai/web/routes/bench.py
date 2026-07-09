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

    # Mode form option lists (closed sets, also validated server-side).
    from asiai.benchmark.code_eval import ALL_SUITES as CODE_SUITES
    from asiai.benchmark.instruct_eval import ALL_SCENARIOS as INSTRUCT_SCENARIOS
    from asiai.benchmark.language_eval import ALL_SUITES as LANGUAGE_SUITES
    from asiai.benchmark.language_profiles import PROFILES as LANGUAGE_PROFILES

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
            "code_suites": sorted(CODE_SUITES),
            "instruct_scenarios": sorted(INSTRUCT_SCENARIOS),
            "language_suites": sorted(LANGUAGE_SUITES),
            "languages": sorted(LANGUAGE_PROFILES),
        },
    )


def _validate_judge_url(raw: str) -> tuple[str | None, str]:
    """Accept a judge URL from the web form ONLY when it targets loopback.

    The server calls the judge with its env API key in the Authorization
    header. From the CLI that is an operator's own shell; from a
    LAN-facing web bind it would let any LAN peer point the server (and
    its key) at an arbitrary host — an SSRF that exfiltrates the key.
    Loopback judges (the local-LLM case) stay usable; remote judges are
    a CLI-only feature by design.
    """
    from urllib.parse import urlsplit

    if not raw:
        return None, ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None, "invalid judge URL"
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None, "invalid judge URL"
    if parts.hostname not in ("127.0.0.1", "localhost", "::1"):
        return (
            None,
            "judge_url must target loopback from the web form — use the CLI for remote judges",
        )
    return raw, ""


# Bench modes runnable from the web beyond the standard throughput bench.
# Keys match bench_runs.bench_type; values declare the form fields each
# mode accepts (everything else in the form is ignored server-side).
_WEB_BENCH_MODES = frozenset(
    {"agentic", "burst", "code", "language", "instruct", "thinking-ablation"}
)


@router.post("/bench/run")
async def bench_run(request: Request) -> JSONResponse:
    """Start a benchmark in a background thread."""
    state = request.app.state.app_state
    form = await request.form()

    if state.get_bench_snapshot()["running"]:
        return JSONResponse({"error": "Benchmark already running"}, status_code=409)

    bench_type = (form.get("bench_type") or "").strip()
    if bench_type and bench_type not in _WEB_BENCH_MODES:
        return JSONResponse({"error": "unknown bench type"}, status_code=422)
    if bench_type:
        return _start_mode_bench(state, bench_type, form)

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

    # Reset status (atomic check-and-set closes the 409 TOCTOU window)
    if not state.try_start_bench(progress="Starting benchmark..."):
        return JSONResponse({"error": "Benchmark already running"}, status_code=409)

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


@router.get("/bench/report/{run_id}.md")
async def bench_report_md(request: Request, run_id: int) -> Response:
    """Markdown report for any persisted bench run (any type)."""
    state = request.app.state.app_state

    from asiai.storage.db import get_bench_run

    row = await asyncio.to_thread(get_bench_run, state.db_path, run_id)
    if row is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        payload = json.loads(row["payload"])
        from asiai.benchmark.report_md import render_markdown
        from asiai.benchmark.result_model import build_result

        md = render_markdown(build_result(row["bench_type"], payload))
    except (ValueError, TypeError) as e:
        return JSONResponse({"error": f"cannot render report: {e}"}, status_code=422)
    return Response(
        md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"inline; filename=bench-run-{run_id}.md"},
    )


@router.get("/bench/card/{run_id}.svg")
async def bench_card_svg(request: Request, run_id: int) -> Response:
    """Adaptive SVG card for any persisted bench run (any type)."""
    state = request.app.state.app_state

    from asiai.storage.db import get_bench_run

    row = await asyncio.to_thread(get_bench_run, state.db_path, run_id)
    if row is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        payload = json.loads(row["payload"])
        from asiai.benchmark.cards import generate_card
        from asiai.benchmark.result_model import build_result

        svg = generate_card(build_result(row["bench_type"], payload))
    except (ValueError, TypeError) as e:
        return JSONResponse({"error": f"cannot render card: {e}"}, status_code=422)
    return Response(
        svg,
        media_type="image/svg+xml",
        headers={"Content-Disposition": f'inline; filename="bench-card-{run_id}.svg"'},
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


def _start_mode_bench(state, bench_type: str, form) -> JSONResponse:
    """Validate a mode form and launch its background thread."""
    engine_name = (form.get("mode_engine") or "").strip().lower()
    engine = next((e for e in state.engines if e.name == engine_name), None)
    if engine is None:
        return JSONResponse({"error": "select one engine"}, status_code=422)

    model = (form.get("mode_model") or "").strip()

    extra_body = None
    raw_extra = (form.get("mode_extra_body") or "").strip()
    if raw_extra:
        try:
            extra_body = json.loads(raw_extra)
            if not isinstance(extra_body, dict):
                raise ValueError("must be a JSON object")
        except ValueError as e:
            return JSONResponse({"error": f"extra_body: {e}"}, status_code=422)

    try:
        runs = max(1, min(int(form.get("mode_runs") or 1), 10))
    except (TypeError, ValueError):
        return JSONResponse({"error": "invalid runs"}, status_code=422)

    opts: dict = {"runs": runs, "extra_body": extra_body}
    if bench_type == "burst":
        from asiai.benchmark.burst import parse_burst_sizes

        try:
            opts["burst_sizes"] = parse_burst_sizes((form.get("burst_sizes") or "").strip() or None)
            opts["max_tokens"] = max(1, min(int(form.get("burst_max_tokens") or 64), 4096))
        except (TypeError, ValueError) as e:
            return JSONResponse({"error": f"burst options: {e}"}, status_code=422)
    elif bench_type == "code":
        from asiai.benchmark.code_eval import ALL_SUITES

        suites = [s for s in form.getlist("code_suites") if s in ALL_SUITES]
        if not suites:
            return JSONResponse({"error": "select at least one suite"}, status_code=422)
        opts["suites"] = suites
        judge_url, judge_err = _validate_judge_url((form.get("judge_url") or "").strip())
        if judge_err:
            return JSONResponse({"error": judge_err}, status_code=422)
        opts["judge_url"] = judge_url
        opts["judge_model"] = (form.get("judge_model") or "").strip() or None
    elif bench_type == "language":
        from asiai.benchmark.language_eval import ALL_SUITES as LANG_SUITES
        from asiai.benchmark.language_profiles import PROFILES

        lang = (form.get("language") or "").strip().lower()
        if lang not in PROFILES:
            return JSONResponse({"error": "unknown language"}, status_code=422)
        opts["language"] = lang
        opts["suites"] = [s for s in form.getlist("language_suites") if s in LANG_SUITES]
        judge_url, judge_err = _validate_judge_url((form.get("judge_url") or "").strip())
        if judge_err:
            return JSONResponse({"error": judge_err}, status_code=422)
        opts["judge_url"] = judge_url
        opts["judge_model"] = (form.get("judge_model") or "").strip() or None
    elif bench_type == "instruct":
        from asiai.benchmark.instruct_eval import ALL_SCENARIOS

        # Empty selection = the runner's own default set — never pass None
        # (it would OVERRIDE the parameter default and crash the runner).
        opts["scenarios"] = [s for s in form.getlist("instruct_scenarios") if s in ALL_SCENARIOS]
    elif bench_type == "agentic":
        opts["skip_long"] = form.get("agentic_skip_long") == "on"

    if not state.try_start_bench(progress=f"Starting {bench_type} bench..."):
        return JSONResponse({"error": "Benchmark already running"}, status_code=409)
    state.update_bench(bench_type=bench_type)

    thread = threading.Thread(
        target=_run_mode_thread,
        args=(state, bench_type, engine, model, opts),
        daemon=True,
    )
    thread.start()
    return JSONResponse({"status": "started", "bench_type": bench_type})


def _run_mode_thread(state, bench_type: str, engine, model: str, opts: dict) -> None:
    """Run a non-standard bench mode in a background thread."""
    try:
        import os

        def progress(msg) -> None:
            state.update_bench(progress=str(msg))

        if not model:
            running = engine.list_running()
            if not running:
                state.update_bench(
                    error=f"No model loaded on {engine.name} — load one or name a model",
                    running=False,
                    done=True,
                )
                return
            model = running[0].name

        try:
            engine_version = engine.version() or ""
        except Exception:
            engine_version = ""

        # Judge API key comes from the server environment ONLY — the form
        # never carries a secret (secrets discipline).
        judge_api_key = os.environ.get("ASIAI_JUDGE_API_KEY") or os.environ.get("OPENAI_API_KEY")

        extra_body = opts.get("extra_body")
        runs = opts.get("runs", 1)
        if bench_type == "agentic":
            from asiai.benchmark.agentic import run_agentic_bench

            payload = run_agentic_bench(
                base_url=engine.base_url,
                engine_name=engine.name,
                model=model,
                skip_long=bool(opts.get("skip_long")),
                extra_body=extra_body,
                repeats=runs,
                engine_version=engine_version,
                on_run=lambda run: progress(f"[{run.phase}] done"),
            )
        elif bench_type == "burst":
            from asiai.benchmark.burst import run_burst

            payload = run_burst(
                base_url=engine.base_url,
                engine=engine.name,
                model=model,
                burst_sizes=opts["burst_sizes"],
                max_tokens=opts["max_tokens"],
                extra_body=extra_body,
                runs=runs,
                engine_version=engine_version,
            )
        elif bench_type == "code":
            from asiai.benchmark.code_eval import run_code_eval

            payload = run_code_eval(
                base_url=engine.base_url,
                engine_name=engine.name,
                model=model,
                suites=opts["suites"],
                repeats=runs,
                extra_body=extra_body,
                judge_url=opts.get("judge_url"),
                judge_model=opts.get("judge_model"),
                judge_api_key=judge_api_key,
                engine_version=engine_version,
                on_progress=progress,
            )
        elif bench_type == "language":
            from asiai.benchmark.language_eval import run_language_eval

            kwargs = dict(
                base_url=engine.base_url,
                engine_name=engine.name,
                model=model,
                language=opts["language"],
                extra_body=extra_body,
                judge_url=opts.get("judge_url"),
                judge_model=opts.get("judge_model"),
                judge_api_key=judge_api_key,
                engine_version=engine_version,
                on_progress=progress,
            )
            if opts.get("suites"):
                # Empty = the runner's default set; None would crash it.
                kwargs["suites"] = opts["suites"]
            payload = run_language_eval(**kwargs)
        elif bench_type == "instruct":
            from asiai.benchmark.instruct_eval import run_instruct_eval

            kwargs = dict(
                base_url=engine.base_url,
                engine_name=engine.name,
                model=model,
                repeats=runs,
                extra_body=extra_body,
                engine_version=engine_version,
                on_progress=progress,
            )
            if opts.get("scenarios"):
                # Empty = the runner's default set; None would crash it.
                kwargs["scenarios"] = opts["scenarios"]
            payload = run_instruct_eval(**kwargs)
        else:  # thinking-ablation (closed set — validated at the route)
            from asiai.benchmark.thinking_ablation import run_thinking_ablation

            payload = run_thinking_ablation(
                base_url=engine.base_url,
                engine_name=engine.name,
                model=model,
                extra_body=extra_body,
                engine_version=engine_version,
                on_progress=progress,
            )

        from asiai.benchmark.persist import persist_bench_run

        run_id = persist_bench_run(state.db_path, bench_type, payload)
        state.update_bench(
            progress=f"{bench_type} bench complete",
            result_run_id=int(run_id or 0),
            running=False,
            done=True,
        )
    except Exception as e:
        logger.exception("Mode bench failed")
        state.update_bench(error=str(e), running=False, done=True)


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

        # Session-level bench_runs row (same as the CLI path — the web
        # must not be an amnesiac producer).
        if bench_run.results:
            from asiai.benchmark.persist import persist_standard_session
            from asiai.benchmark.reporter import build_export_payload

            persist_standard_session(state.db_path, build_export_payload(bench_run.results, report))

        # --- Card generation (never blocks benchmark completion) ---
        if not generate_card:
            state.update_bench(progress="Benchmark complete", running=False, done=True)
            return
        try:
            from asiai.benchmark.card import (
                convert_svg_to_png,
                download_card_png,
                get_share_url,
                save_card,
            )

            # Aliased: the thread's own `generate_card` parameter is the
            # form's boolean toggle — importing the renderer under the
            # same name would silently shadow it.
            from asiai.benchmark.cards import generate_card as render_card
            from asiai.benchmark.reporter import build_export_payload
            from asiai.benchmark.result_model import build_result

            if not bench_run.results:
                raise ValueError("no results to render")
            svg = render_card(
                build_result("standard", build_export_payload(bench_run.results, report))
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
