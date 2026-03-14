"""MCP tools for asiai -- 11 tools exposing inference monitoring capabilities."""

from __future__ import annotations

import asyncio
import logging
import time

from mcp.server.fastmcp import Context

from asiai.mcp.server import MCPContext, mcp

logger = logging.getLogger("asiai.mcp.tools")

_BENCH_COOLDOWN_SECONDS = 60.0


def _get_ctx(ctx: Context) -> MCPContext:
    """Extract MCPContext from the MCP request context."""
    return ctx.request_context.lifespan_context


# ---------------------------------------------------------------------------
# Tool 1: check_inference_health (read-only, <500ms)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False,
        "title": "Check Inference Health",
    }
)
async def check_inference_health(ctx: Context) -> dict:
    """Quick health check of all local LLM inference engines.

    Returns status ("ok", "degraded", "error"), which engines are reachable,
    memory pressure, thermal state, and GPU utilization.
    Use this FIRST when you need to know if inference is available.
    Responds in <500ms.
    """
    from asiai.collectors.gpu import collect_gpu
    from asiai.collectors.snapshot import collect_engines_status
    from asiai.collectors.system import collect_memory, collect_thermal

    app_ctx = _get_ctx(ctx)
    statuses = collect_engines_status(app_ctx.engines)

    engines_up: dict[str, bool] = {}
    for es in statuses:
        engines_up[es["name"]] = es.get("reachable", False)

    all_reachable = all(engines_up.values()) if engines_up else False
    any_reachable = any(engines_up.values()) if engines_up else False

    if all_reachable:
        status = "ok"
    elif any_reachable:
        status = "degraded"
    else:
        status = "error"

    mem = collect_memory()
    thermal = collect_thermal()
    gpu = collect_gpu()

    return {
        "status": status,
        "ts": int(time.time()),
        "engines": engines_up,
        "memory_pressure": mem.pressure,
        "memory_used_pct": round(mem.used / mem.total * 100, 1) if mem.total > 0 else 0,
        "thermal_level": thermal.level,
        "thermal_speed_limit": thermal.speed_limit,
        "gpu_utilization_pct": gpu.utilization_pct,
    }


# ---------------------------------------------------------------------------
# Tool 2: get_inference_snapshot (read-only, ~1s)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False,
        "title": "Full Inference Snapshot",
    }
)
async def get_inference_snapshot(ctx: Context) -> dict:
    """Get complete system + inference state: CPU load, memory, thermal,
    GPU metrics, all engines with their loaded models, VRAM usage,
    TCP connections, and inference activity.

    Use this when you need detailed information about the current state
    of the machine and all inference engines. More comprehensive than
    check_inference_health but takes slightly longer (~1s).
    """
    from asiai.collectors.snapshot import collect_full_snapshot
    from asiai.storage.db import store_engine_status, store_snapshot

    app_ctx = _get_ctx(ctx)
    snapshot = collect_full_snapshot(app_ctx.engines)

    store_snapshot(app_ctx.db_path, snapshot)
    if snapshot.get("engines_status"):
        store_engine_status(app_ctx.db_path, snapshot["engines_status"])

    return snapshot


# ---------------------------------------------------------------------------
# Tool 3: list_models (read-only, <1s)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False,
        "title": "List Loaded Models",
    }
)
async def list_models(ctx: Context) -> dict:
    """List all models currently loaded across all inference engines.

    Returns each model with its engine, name, VRAM usage, format,
    quantization, and context length. Use this to know what models
    are available for benchmarking or inference.
    """
    app_ctx = _get_ctx(ctx)
    result: dict = {"engines": []}

    for engine in app_ctx.engines:
        try:
            if not engine.is_reachable():
                continue
            running = engine.list_running()
            entry = {
                "engine": engine.name,
                "url": engine.base_url,
                "version": engine.version() or "",
                "models": [
                    {
                        "name": m.name,
                        "size_vram": m.size_vram,
                        "format": m.format,
                        "quantization": m.quantization,
                        "context_length": m.context_length,
                    }
                    for m in running
                ],
            }
            result["engines"].append(entry)
        except Exception as e:
            logger.warning("Engine %s error: %s", engine.name, e)

    all_models = []
    for eng in result["engines"]:
        for m in eng["models"]:
            all_models.append({**m, "engine": eng["engine"]})
    result["all_models"] = all_models
    result["total_models"] = len(all_models)

    return result


# ---------------------------------------------------------------------------
# Tool 4: detect_engines (read-only, 1-3s)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False,
        "title": "Detect Inference Engines",
    }
)
async def detect_engines(
    ctx: Context,
    urls: list[str] | None = None,
) -> dict:
    """Auto-detect running LLM inference engines on this Mac.

    Scans default ports (Ollama:11434, LM Studio:1234, mlx-lm:8080,
    llama.cpp:8080, oMLX/vllm-mlx:8000, Exo:52415) or custom URLs.
    Also refreshes the server's internal engine list.

    Args:
        urls: Optional list of URLs to scan instead of defaults.
             Example: ["http://localhost:11434", "http://192.168.0.16:11434"]
    """
    from asiai.cli import _discover_engines

    engines = _discover_engines(urls)
    app_ctx = _get_ctx(ctx)
    app_ctx.engines = engines

    results = []
    for engine in engines:
        try:
            models = engine.list_running()
            results.append(
                {
                    "engine": engine.name,
                    "version": engine.version() or "",
                    "url": engine.base_url,
                    "models_loaded": len(models),
                    "models": [m.name for m in models],
                }
            )
        except Exception as e:
            results.append(
                {
                    "engine": engine.name,
                    "url": engine.base_url,
                    "error": str(e),
                }
            )

    return {
        "engines_found": len(engines),
        "engines": results,
    }


# ---------------------------------------------------------------------------
# Tool 5: run_benchmark (ACTIVE, 30-120s, rate-limited)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
        "title": "Run Inference Benchmark",
    }
)
async def run_benchmark(
    ctx: Context,
    model: str = "",
    engines: str = "",
    prompts: str = "",
    runs: int = 3,
    context_size: str = "",
    card: bool = False,
) -> dict:
    """Run a performance benchmark on local LLM inference engines.

    WARNING: This is an ACTIVE operation that takes 30-120 seconds.
    It sends prompts to inference engines and measures tok/s, TTFT,
    and throughput. Only use when the user explicitly asks for a benchmark.

    Args:
        model: Model name to benchmark. If empty, auto-detects the first loaded model.
        engines: Comma-separated engine filter (e.g. "ollama,lmstudio"). Empty = all.
        prompts: Comma-separated prompt types: "code", "tool_call", "reasoning", "long_gen".
                 Empty = all standard prompts.
        runs: Number of runs per prompt for variance measurement (1-10, default 3).
        context_size: Context fill size for stress testing (e.g. "64k", "128k"). Empty = standard.
        card: Generate a shareable benchmark card (SVG image saved on the MCP server
              filesystem). The returned card_path is local to the server machine.

    Returns:
        Aggregated benchmark report with per-engine tok/s, TTFT, CI 95%,
        stability rating, and winner determination. If card=True, includes card_path
        (absolute path on the server, e.g. ~/.local/share/asiai/cards/...).
    """
    from asiai.benchmark.reporter import aggregate_results
    from asiai.benchmark.runner import find_common_model
    from asiai.benchmark.runner import run_benchmark as _run_bench
    from asiai.storage.db import store_benchmark

    app_ctx = _get_ctx(ctx)

    # Rate limiting: minimum 60s between benchmarks
    now = time.time()
    elapsed = now - app_ctx.last_bench_ts
    if elapsed < _BENCH_COOLDOWN_SECONDS:
        remaining = int(_BENCH_COOLDOWN_SECONDS - elapsed)
        return {
            "error": f"Rate limited. Please wait {remaining}s before the next benchmark.",
            "cooldown_remaining_seconds": remaining,
        }

    if not app_ctx.engines:
        return {"error": "No inference engines detected. Run detect_engines first."}

    # Filter engines
    target_engines = app_ctx.engines
    if engines:
        wanted = {e.strip().lower() for e in engines.split(",")}
        target_engines = [e for e in target_engines if e.name in wanted]
        if not target_engines:
            return {"error": f"None of the specified engines found: {engines}"}

    # Resolve model
    resolved_model = find_common_model(target_engines, model)
    if not resolved_model:
        return {
            "error": "No model available for benchmarking. Load a model first.",
            "suggestion": "Use list_models to see what's loaded.",
        }

    # Parse prompt types
    prompt_names = [p.strip() for p in prompts.split(",")] if prompts else None

    # Clamp runs
    runs = max(1, min(runs, 10))

    # Parse context size
    ctx_size = 0
    if context_size:
        from asiai.benchmark.prompts import parse_context_size

        ctx_size = parse_context_size(context_size)

    # Run benchmark in thread pool to avoid blocking the event loop
    bench_run = await asyncio.to_thread(
        _run_bench,
        target_engines,
        resolved_model,
        prompt_names,
        runs=runs,
        power=False,  # No sudo in MCP context
        context_size=ctx_size,
    )

    app_ctx.last_bench_ts = time.time()

    # Store results
    if bench_run.results:
        store_benchmark(app_ctx.db_path, bench_run.results)
        from asiai.storage.db import store_benchmark_process

        store_benchmark_process(app_ctx.db_path, bench_run.results)

    # Aggregate
    report = aggregate_results(bench_run.results)
    report["model"] = resolved_model
    report["errors"] = bench_run.errors
    report["total_runs"] = len(bench_run.results)

    # Generate benchmark card if requested
    if card and bench_run.results:
        from asiai.benchmark.card import (
            extract_card_metadata,
            generate_card_svg,
            save_card,
        )

        first_result = bench_run.results[0]
        eng_vers, pw_data, eng_quants = extract_card_metadata(
            bench_run.results
        )
        svg = generate_card_svg(
            report,
            hw_chip=first_result.get("hw_chip", ""),
            model_quantization=first_result.get("model_quantization", ""),
            ram_gb=first_result.get("ram_gb", 0),
            gpu_cores=first_result.get("gpu_cores", 0),
            context_size=first_result.get("context_size", 0),
            engine_versions=eng_vers,
            power_data=pw_data,
            engine_quants=eng_quants,
        )
        svg_path = save_card(svg, fmt="svg")
        report["card_path"] = str(svg_path)

    return report


# ---------------------------------------------------------------------------
# Tool 6: get_recommendations (read-only, <1s)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False,
        "title": "Get Engine Recommendations",
    }
)
async def get_recommendations(
    ctx: Context,
    use_case: str = "throughput",
    model: str = "",
    include_community: bool = False,
) -> dict:
    """Get hardware-aware engine and model recommendations for this Mac.

    Analyzes local benchmark history, hardware specs, and optionally
    community data to recommend the best engine+model combinations.

    Args:
        use_case: Optimize for "throughput" (max tok/s), "latency" (min TTFT),
                  or "efficiency" (tok/s per watt). Default: throughput.
        model: Filter recommendations to a specific model name.
        include_community: Include community benchmark data in analysis.

    Returns:
        Ranked list of recommendations with scores, reasons, and caveats.
    """
    from asiai.advisor.recommender import recommend
    from asiai.collectors.system import collect_hw_chip, collect_memory

    app_ctx = _get_ctx(ctx)

    chip = collect_hw_chip()
    mem = collect_memory()
    ram_gb = round(mem.total / (1024**3))

    community_url = ""
    if include_community:
        from asiai.community import get_api_url

        community_url = get_api_url()

    recs = recommend(
        chip=chip,
        ram_gb=ram_gb,
        use_case=use_case,
        model_filter=model,
        db_path=app_ctx.db_path,
        community_url=community_url,
    )

    return {
        "chip": chip,
        "ram_gb": ram_gb,
        "use_case": use_case,
        "recommendations": [
            {
                "rank": i + 1,
                "engine": r.engine,
                "model": r.model,
                "score": r.score,
                "median_tok_s": r.median_tok_s,
                "median_ttft_ms": r.median_ttft_ms,
                "vram_bytes": r.vram_bytes,
                "source": r.source,
                "confidence": r.confidence,
                "reason": r.reason,
                "caveats": r.caveats,
            }
            for i, r in enumerate(recs[:10])
        ],
    }


# ---------------------------------------------------------------------------
# Tool 7: diagnose (read-only, 2-5s)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False,
        "title": "Run Diagnostics",
    }
)
async def diagnose(ctx: Context) -> dict:
    """Run comprehensive diagnostic checks on the asiai installation.

    Checks: Apple Silicon hardware, RAM, memory pressure, thermal state,
    each engine (Ollama, LM Studio, mlx-lm, llama.cpp, vllm-mlx, Exo),
    database integrity, daemon status, and alerting configuration.

    Each check returns status ("ok", "warn", "fail") with a message
    and optional fix suggestion.

    Use this when something seems wrong or the user reports issues.
    """
    from asiai.doctor import run_checks

    app_ctx = _get_ctx(ctx)
    checks = run_checks(app_ctx.db_path)

    results = []
    summary: dict[str, int] = {"ok": 0, "warn": 0, "fail": 0}
    for c in checks:
        summary[c.status] = summary.get(c.status, 0) + 1
        entry: dict = {
            "category": c.category,
            "name": c.name,
            "status": c.status,
            "message": c.message,
        }
        if c.fix:
            entry["fix"] = c.fix
        results.append(entry)

    return {
        "summary": summary,
        "healthy": summary["fail"] == 0,
        "checks": results,
    }


# ---------------------------------------------------------------------------
# Tool 8: get_metrics_history (read-only, <500ms)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False,
        "title": "Get System Metrics History",
    }
)
async def get_metrics_history(
    ctx: Context,
    hours: int = 24,
) -> dict:
    """Query historical system metrics (CPU, RAM, thermal, GPU) from the local database.

    Requires that asiai monitor has been collecting data (via daemon or manual runs).

    Args:
        hours: Number of hours of history to return (1-168, default 24).

    Returns:
        List of timestamped metric entries with system and GPU data.
    """
    from asiai.storage.db import query_history

    app_ctx = _get_ctx(ctx)
    hours = max(1, min(hours, 168))

    data = query_history(app_ctx.db_path, hours)

    return {
        "hours": hours,
        "entries": len(data),
        "history": data,
    }


# ---------------------------------------------------------------------------
# Tool 9: get_benchmark_history (read-only, <500ms)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False,
        "title": "Get Benchmark History",
    }
)
async def get_benchmark_history(
    ctx: Context,
    hours: int = 0,
    model: str = "",
) -> dict:
    """Query past benchmark results from the local database.

    Args:
        hours: Limit to last N hours. 0 = all history (default).
        model: Filter by model name (e.g. "qwen3.5:35b"). Empty = all models.

    Returns:
        List of benchmark result entries with tok/s, TTFT, engine,
        model, VRAM, thermal state, and timestamps.
    """
    from asiai.storage.db import query_benchmarks

    app_ctx = _get_ctx(ctx)

    rows = query_benchmarks(app_ctx.db_path, hours=hours, model=model)

    return {
        "total_results": len(rows),
        "filters": {"hours": hours or "all", "model": model or "all"},
        "results": rows,
    }


# ---------------------------------------------------------------------------
# Tool 10: refresh_engines (side-effect: re-detects engines, <2s)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": False,
        "title": "Refresh Engine Detection",
    }
)
async def refresh_engines(ctx: Context) -> dict:
    """Re-detect inference engines without restarting the MCP server.

    Use this after starting or stopping an engine (Ollama, LM Studio, etc.)
    so that subsequent tool calls see the updated engine list.

    Returns:
        Updated list of detected engines with names and URLs.
    """
    from asiai.cli import _discover_engines

    app_ctx = _get_ctx(ctx)
    engines = await asyncio.to_thread(_discover_engines)
    app_ctx.engines = engines

    return {
        "engines_detected": len(engines),
        "engines": [
            {"name": e.name, "url": e.url}
            for e in engines
        ],
    }


# ---------------------------------------------------------------------------
# Tool 11: compare_engines (read-only, <1s)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "openWorldHint": False,
        "title": "Compare Engines for a Model",
    }
)
async def compare_engines(
    ctx: Context,
    model: str = "",
    hours: int = 0,
) -> dict:
    """Compare inference engines side-by-side for a given model.

    Analyzes local benchmark history and returns a ranked comparison
    with tok/s, TTFT, VRAM, stability, and a verdict indicating
    the winner and by how much.

    Args:
        model: Model name to compare across engines (e.g. "qwen3.5:35b").
               If empty, uses the most recently benchmarked model.
        hours: Limit analysis to last N hours. 0 = all history (default).

    Returns:
        Ranked engine comparison with winner verdict.
    """
    from asiai.benchmark.reporter import aggregate_results
    from asiai.storage.db import query_benchmarks

    app_ctx = _get_ctx(ctx)
    rows = query_benchmarks(app_ctx.db_path, hours=hours, model=model)

    if not rows:
        return {
            "error": "No benchmark data found.",
            "suggestion": "Run a benchmark first: run_benchmark tool.",
        }

    report = aggregate_results(rows)
    engines_data = report.get("engines", {})

    if len(engines_data) < 2:
        return {
            "error": "Need benchmarks from at least 2 engines to compare.",
            "engines_found": list(engines_data.keys()),
            "suggestion": "Load the same model on multiple engines and benchmark.",
        }

    # Build ranked comparison
    ranked = sorted(
        engines_data.items(),
        key=lambda x: x[1].get("avg_tok_s", 0),
        reverse=True,
    )

    comparison = []
    for rank, (name, data) in enumerate(ranked, 1):
        comparison.append({
            "rank": rank,
            "engine": name,
            "avg_tok_s": round(data.get("avg_tok_s", 0), 1),
            "avg_ttft_ms": round(data.get("avg_ttft_ms", 0), 1),
            "vram_bytes": data.get("vram_bytes", 0),
            "stability": data.get("stability", "unknown"),
            "runs_count": data.get("runs_count", 0),
        })

    # Verdict
    best = ranked[0]
    second = ranked[1]
    best_tok = best[1].get("avg_tok_s", 0)
    second_tok = second[1].get("avg_tok_s", 0)
    speedup = round(best_tok / second_tok, 1) if second_tok > 0 else 0

    verdict = (
        f"{best[0]} is {speedup}x faster than {second[0]} "
        f"({best_tok:.1f} vs {second_tok:.1f} tok/s)"
    )

    return {
        "model": report.get("model", model),
        "comparison": comparison,
        "verdict": verdict,
        "winner": report.get("winner"),
    }
