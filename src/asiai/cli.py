"""CLI entry point for asiai."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

from asiai import __version__


def _discover_engines(urls: list[str] | None = None) -> list:
    """Detect inference engines and return instantiated adapters."""
    from asiai.engines.detect import detect_engines
    from asiai.engines.exo import ExoEngine
    from asiai.engines.llamacpp import LlamaCppEngine
    from asiai.engines.lmstudio import LMStudioEngine
    from asiai.engines.mlxlm import MlxLmEngine
    from asiai.engines.ollama import OllamaEngine
    from asiai.engines.vllm_mlx import VllmMlxEngine

    engine_map = {
        "ollama": OllamaEngine,
        "lmstudio": LMStudioEngine,
        "mlxlm": MlxLmEngine,
        "llamacpp": LlamaCppEngine,
        "vllm_mlx": VllmMlxEngine,
        "exo": ExoEngine,
    }

    found = detect_engines(urls)
    engines = []
    for url, name, _version in found:
        cls = engine_map.get(name)
        if cls:
            engines.append(cls(url))
    return engines


def _parse_urls(url_arg: str | None) -> list[str] | None:
    """Parse comma-separated URL argument."""
    if url_arg:
        return [u.strip() for u in url_arg.split(",") if u.strip()]
    return None


def cmd_detect(args: argparse.Namespace) -> int:
    """Handle 'detect' command."""
    from asiai.display.cli_renderer import render_detect

    urls = _parse_urls(args.url)
    engines = _discover_engines(urls)

    results = []
    for engine in engines:
        models = engine.list_running()
        results.append(
            {
                "name": engine.name,
                "version": engine.version(),
                "url": engine.base_url,
                "models": [
                    {
                        "name": m.name,
                        "size_vram": m.size_vram,
                        "format": m.format,
                        "quantization": m.quantization,
                    }
                    for m in models
                ],
            }
        )

    render_detect(results)
    return 0


def cmd_models(args: argparse.Namespace) -> int:
    """Handle 'models' command."""
    from asiai.display.formatters import bold, dim, format_bytes, green

    urls = _parse_urls(args.url)
    engines = _discover_engines(urls)

    if not engines:
        if getattr(args, "json_output", False):
            print(json.dumps({"engines": []}, indent=2))
        else:
            print(dim("No inference engines detected."))
        return 1

    if getattr(args, "json_output", False):
        data = {"engines": []}
        for engine in engines:
            running = engine.list_running()
            entry = {
                "name": engine.name,
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
            data["engines"].append(entry)
        print(json.dumps(data, indent=2))
        return 0

    for engine in engines:
        ver = engine.version()
        ver_str = f"  {dim('v' + ver)}" if ver else ""
        print(bold(f"{engine.name}") + ver_str + f"  {dim(engine.base_url)}")
        running = engine.list_running()
        if running:
            for m in running:
                vram = format_bytes(m.size_vram) if m.size_vram else ""
                quant = m.quantization or ""
                ctx = ""
                if m.context_length > 0:
                    if m.context_length >= 1024:
                        ctx = f"{m.context_length // 1024}k ctx"
                    else:
                        ctx = f"{m.context_length} ctx"
                print(f"  {green('●')} {m.name:<40} {vram:>10} {quant:>6}  {dim(ctx)}")
        else:
            print(dim("  No models loaded."))
        print()

    return 0


def cmd_monitor(args: argparse.Namespace) -> int:
    """Handle 'monitor' command."""
    from asiai.collectors.snapshot import collect_snapshot
    from asiai.display.cli_renderer import (
        render_analyze,
        render_compare,
        render_history,
        render_snapshot,
    )
    from asiai.storage.db import (
        DEFAULT_DB_PATH,
        init_db,
        query_compare,
        query_history,
        store_snapshot,
    )

    urls = _parse_urls(args.url)
    engines = _discover_engines(urls)
    db_path = args.db or DEFAULT_DB_PATH

    # Initialize DB
    init_db(db_path)

    if args.history:
        # Parse hours from period string (e.g. "24h", "1h", "48")
        period = args.history.rstrip("h")
        hours = int(period) if period.isdigit() else 24
        data = query_history(db_path, hours)
        render_history(data, hours)
        return 0

    if args.analyze is not None:
        hours = args.analyze if args.analyze > 0 else 24
        data = query_history(db_path, hours)
        render_analyze(data, hours)
        return 0

    if args.compare:
        parts = args.compare
        if len(parts) != 2:
            from asiai.display.formatters import red

            print(red("Error: --compare requires exactly 2 timestamps"), file=sys.stderr)
            return 1
        data = query_compare(db_path, int(parts[0]), int(parts[1]))
        render_compare(data)
        return 0

    quiet = getattr(args, "quiet", False)
    json_output = getattr(args, "json_output", False)
    webhook_url = getattr(args, "alert_webhook", None)

    if args.watch is not None and args.watch < 1:
        args.watch = 1

    prev_snapshot: dict | None = None

    # Default: snapshot (with optional --watch)
    if args.watch:
        try:
            while True:
                if not quiet:
                    subprocess.run(["clear"], check=False)
                snap = collect_snapshot(engines)
                store_snapshot(db_path, snap)
                if webhook_url:
                    from asiai.alerting import check_and_alert

                    check_and_alert(snap, prev_snapshot, webhook_url, db_path)
                    prev_snapshot = snap
                if json_output:
                    print(json.dumps(snap, indent=2))
                elif not quiet:
                    render_snapshot(snap)
                time.sleep(args.watch)
        except KeyboardInterrupt:
            if not quiet:
                print()
            return 0
    else:
        snap = collect_snapshot(engines)
        store_snapshot(db_path, snap)
        if webhook_url:
            from asiai.alerting import check_and_alert

            check_and_alert(snap, prev_snapshot, webhook_url, db_path)
        if json_output:
            print(json.dumps(snap, indent=2))
        elif not quiet:
            render_snapshot(snap)
        return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Handle 'doctor' command."""
    from asiai.display.cli_renderer import render_doctor
    from asiai.doctor import run_checks

    db_path = args.db or None
    checks = run_checks(db_path) if db_path else run_checks()
    render_doctor(checks)

    # Return non-zero if any check failed
    if any(c.status == "fail" for c in checks):
        return 1
    return 0


def cmd_tui(args: argparse.Namespace) -> int:
    """Handle 'tui' command."""
    try:
        from asiai.display.tui import run_tui
    except ImportError:
        from asiai.display.formatters import dim, red

        print(red("Textual is required for the TUI."), file=sys.stderr)
        print(dim("Install with: pip install asiai[tui]"), file=sys.stderr)
        return 1

    from asiai.storage.db import DEFAULT_DB_PATH, init_db

    urls = _parse_urls(args.url)
    engines = _discover_engines(urls)
    db_path = args.db or DEFAULT_DB_PATH
    init_db(db_path)
    try:
        run_tui(engines=engines, db_path=db_path)
    except ImportError:
        from asiai.display.formatters import dim, red

        print(red("Textual is required for the TUI."), file=sys.stderr)
        print(dim("Install with: pip install asiai[tui]"), file=sys.stderr)
        return 1
    return 0


def cmd_daemon(args: argparse.Namespace) -> int:
    """Handle 'daemon' command."""
    from asiai.daemon import (
        SERVICES,
        _read_plist_config,
        daemon_logs,
        daemon_start,
        daemon_status_all,
        daemon_stop,
        daemon_stop_all,
    )
    from asiai.display.formatters import bold, dim, green, red, yellow

    action = args.action
    if not action:
        print(dim("Usage: asiai daemon {start|stop|status|logs}"), file=sys.stderr)
        return 1

    if action == "start":
        service = getattr(args, "service", "monitor")
        kwargs: dict = {}
        if service == "monitor":
            kwargs["interval"] = getattr(args, "interval", 60)
            webhook = getattr(args, "alert_webhook", None)
            if webhook:
                kwargs["webhook_url"] = webhook
        elif service == "web":
            kwargs["port"] = getattr(args, "port", 8899)
            kwargs["host"] = getattr(args, "host", "127.0.0.1")
            if kwargs["host"] != "127.0.0.1":
                print(yellow(f"Warning: binding to {kwargs['host']} exposes the dashboard."))
                print(yellow("No authentication is configured. Use with caution."))

        result = daemon_start(service, **kwargs)
        if result["status"] == "started":
            profile = SERVICES[service]
            print(green(f"{profile.description} started"))
            print(f"  Plist: {result['plist']}")
            if service == "monitor":
                print(f"  Interval: {result.get('interval', 60)}s")
                if kwargs.get("webhook_url"):
                    print(f"  Webhook: {kwargs['webhook_url']}")
            elif service == "web":
                host = result.get("host", "127.0.0.1")
                port = result.get("port", 8899)
                print(f"  URL: http://{host}:{port}")
        else:
            print(red(f"Error: {result['message']}"), file=sys.stderr)
            return 1

    elif action == "stop":
        if getattr(args, "stop_all", False):
            results = daemon_stop_all()
            for svc_name, result in results.items():
                profile = SERVICES[svc_name]
                print(f"  {profile.description}: {result['status']}")
        else:
            service = getattr(args, "service", "monitor")
            result = daemon_stop(service)
            profile = SERVICES[service]
            if result["status"] == "stopped":
                print(green(f"{profile.description} stopped"))
            else:
                print(red(f"Error: {result['message']}"), file=sys.stderr)
                return 1

    elif action == "status":
        statuses = daemon_status_all()
        print(bold("Services"))
        for svc_name, status in statuses.items():
            profile = SERVICES[svc_name]
            if status["running"]:
                pid_str = f" (PID {status['pid']})" if status["pid"] else ""
                extra = ""
                config = _read_plist_config(svc_name)
                if svc_name == "monitor" and config.get("interval"):
                    extra = f"  every {config['interval']}s"
                    if config.get("webhook_url"):
                        extra += f"  webhook: {config['webhook_url']}"
                elif svc_name == "web":
                    host = config.get("host", "127.0.0.1")
                    port = config.get("port", 8899)
                    extra = f"  http://{host}:{port}"
                print(f"  {green('●')} {bold(profile.description)}{pid_str}{dim(extra)}")
            else:
                if status["plist_exists"]:
                    detail = dim("  installed but not running")
                else:
                    detail = dim("  not installed")
                print(f"  {dim('○')} {dim(profile.description)}{detail}")

    elif action == "logs":
        service = getattr(args, "service", "monitor")
        lines = getattr(args, "lines", 50)
        output = daemon_logs(service, lines)
        print(output)

    return 0


def cmd_web(args: argparse.Namespace) -> int:
    """Handle 'web' command."""
    try:
        import uvicorn  # noqa: F401

        has_fastapi = True
    except ImportError:
        has_fastapi = False

    if not has_fastapi:
        from asiai.display.formatters import dim, red

        print(red("FastAPI is required for the web dashboard."), file=sys.stderr)
        print(dim("Install with: pip install asiai[web]"), file=sys.stderr)
        return 1

    from asiai.storage.db import DEFAULT_DB_PATH, init_db
    from asiai.web.app import create_app
    from asiai.web.state import AppState

    urls = _parse_urls(args.url)
    engines = _discover_engines(urls)
    db_path = args.db or DEFAULT_DB_PATH
    init_db(db_path)

    state = AppState(engines=engines, db_path=db_path)
    app = create_app(state)

    host = args.host
    port = args.port

    # Open browser unless --no-open
    if not args.no_open:
        import threading
        import webbrowser

        def _open_browser():
            import time as _time

            _time.sleep(1.5)
            webbrowser.open(f"http://{host}:{port}")

        threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    """Handle 'bench' command."""
    from asiai.benchmark.regression import detect_regressions
    from asiai.benchmark.reporter import aggregate_results, export_benchmark
    from asiai.benchmark.runner import find_common_model, run_benchmark
    from asiai.display.cli_renderer import render_bench, render_bench_history, render_regressions
    from asiai.display.formatters import red, yellow
    from asiai.storage.db import (
        DEFAULT_DB_PATH,
        init_db,
        query_benchmarks,
        store_benchmark,
    )

    db_path = args.db or DEFAULT_DB_PATH
    init_db(db_path)

    # History mode
    if args.history:
        period = args.history.rstrip("dh")
        if args.history.endswith("d"):
            hours = int(period) * 24 if period.isdigit() else 168
        else:
            hours = int(period) if period.isdigit() else 24
        rows = query_benchmarks(db_path, hours=hours, model=args.model or "")
        render_bench_history(rows)
        return 0

    # Benchmark mode
    urls = _parse_urls(args.url)
    engines = _discover_engines(urls)

    if not engines:
        print(red("✗ No inference engines detected."), file=sys.stderr)
        return 1

    # Filter engines if --engines specified
    if args.engines:
        wanted = {e.strip().lower() for e in args.engines.split(",")}
        engines = [e for e in engines if e.name in wanted]
        if not engines:
            print(red(f"✗ None of the specified engines found: {args.engines}"), file=sys.stderr)
            return 1

    # Determine model
    model = find_common_model(engines, args.model or "")
    if not model:
        print(yellow("⚠ No model to benchmark. Load a model or use --model."), file=sys.stderr)
        return 1

    # Parse prompt types
    prompt_names = None
    if args.prompts:
        prompt_names = [p.strip() for p in args.prompts.split(",")]

    # Show what we are about to do
    engine_names = ", ".join(e.name for e in engines)
    print(f"Benchmarking {model} on {engine_names}...")
    print()

    # Run benchmark
    runs = max(1, min(getattr(args, "runs", 1), 100))
    power = getattr(args, "power", False)
    context_size = 0
    if getattr(args, "context_size", None):
        from asiai.benchmark.prompts import parse_context_size

        context_size = parse_context_size(args.context_size)
    bench_run = run_benchmark(
        engines,
        model,
        prompt_names,
        runs=runs,
        power=power,
        context_size=context_size,
    )

    # Store results
    if bench_run.results:
        store_benchmark(db_path, bench_run.results)

    # Display errors
    for err in bench_run.errors:
        print(f"  {yellow('⚠')} {err}", file=sys.stderr)

    # Aggregate and render
    report = aggregate_results(bench_run.results)
    report["model"] = model  # Use user-requested name, not engine-resolved
    render_bench(report)

    # Export to JSON if requested
    export_path = getattr(args, "export", None)
    if export_path and bench_run.results:
        path = export_benchmark(bench_run.results, report, export_path)
        from asiai.display.formatters import green

        print(f"  {green('✓')} Exported to {path}")

    # Check for regressions against historical data
    if bench_run.results:
        regressions = detect_regressions(bench_run.results, db_path)
        if regressions:
            render_regressions(regressions)

    # Community share (opt-in)
    if getattr(args, "share", False) and bench_run.results:
        from asiai.community import build_submission, submit_benchmark
        from asiai.display.formatters import dim, green

        payload = build_submission(bench_run.results, report)
        result = submit_benchmark(payload, db_path=db_path)
        if result.success:
            print(f"  {green('✓')} Shared to community ({result.submission_id[:8]}...)")
        else:
            print(f"  {dim('⚠ Share failed: ' + result.error)}")

    return 0


def cmd_leaderboard(args: argparse.Namespace) -> int:
    """Handle 'leaderboard' command."""
    from asiai.community import fetch_leaderboard
    from asiai.display.formatters import bold, dim, green

    chip = getattr(args, "chip", "")
    model = getattr(args, "model", "")

    entries = fetch_leaderboard(chip=chip, model=model)
    if not entries:
        print(dim("No community data available (server may be unreachable)."))
        return 1

    print(bold("Community Leaderboard"))
    if chip:
        print(dim(f"  Chip: {chip}"))
    if model:
        print(dim(f"  Model: {model}"))
    print()

    # Table header
    print(f"  {'Engine':<12} {'Model':<30} {'tok/s':>8} {'TTFT':>8} {'Samples':>8}")
    print(f"  {'─' * 12} {'─' * 30} {'─' * 8} {'─' * 8} {'─' * 8}")
    for entry in entries:
        eng = entry.get("engine", "?")
        mdl = entry.get("model", "?")
        tok = entry.get("median_tok_s", 0.0)
        ttft = entry.get("median_ttft_ms", 0.0)
        samples = entry.get("samples", entry.get("submissions", 0))
        print(f"  {green(eng):<12} {mdl:<30} {tok:>8.1f} {ttft:>7.0f}ms {samples:>8}")

    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Handle 'compare' command."""
    from asiai.benchmark.reporter import aggregate_results
    from asiai.community import fetch_comparison
    from asiai.display.formatters import bold, dim, green, red
    from asiai.storage.db import DEFAULT_DB_PATH, init_db, query_benchmarks

    db_path = args.db or DEFAULT_DB_PATH
    init_db(db_path)

    chip = getattr(args, "chip", "")
    model = getattr(args, "model", "")

    if not chip:
        from asiai.collectors.system import collect_machine_info

        chip = collect_machine_info().split(" — ")[0] if " — " in collect_machine_info() else ""
        if not chip:
            from asiai.collectors.system import collect_hw_chip

            chip = collect_hw_chip()

    # Get local data
    rows = query_benchmarks(db_path, model=model)
    if not rows:
        print(dim("No local benchmarks found. Run 'asiai bench' first."))
        return 1

    local_report = aggregate_results(rows)
    comparison = fetch_comparison(chip, model or local_report.get("model", ""), local_report)

    if not comparison:
        print(dim("Could not fetch community data for comparison."))
        return 1

    print(bold(f"Your {chip} vs Community"))
    print()
    for eng_name, data in comparison.get("engines", {}).items():
        local_tok = data.get("local_median_tok_s", 0)
        comm_tok = data.get("community_median_tok_s", 0)
        delta_pct = data.get("delta_pct", 0)
        samples = data.get("community_samples", 0)

        if delta_pct > 0:
            delta_str = green(f"+{delta_pct:.1f}%")
        elif delta_pct < 0:
            delta_str = red(f"{delta_pct:.1f}%")
        else:
            delta_str = dim("=")

        print(
            f"  {eng_name:<12}  "
            f"you: {local_tok:.1f} tok/s  "
            f"community: {comm_tok:.1f} tok/s  "
            f"{delta_str}  "
            f"{dim(f'({samples} samples)')}"
        )

    return 0


def cmd_recommend(args: argparse.Namespace) -> int:
    """Handle 'recommend' command."""
    from asiai.advisor.recommender import recommend
    from asiai.collectors.system import collect_hw_chip, collect_memory
    from asiai.display.formatters import bold, dim, green, yellow
    from asiai.storage.db import DEFAULT_DB_PATH, init_db

    db_path = args.db or DEFAULT_DB_PATH
    init_db(db_path)

    chip = collect_hw_chip()
    mem = collect_memory()
    ram_gb = round(mem.total / (1024**3))

    use_case = getattr(args, "use_case", "throughput")
    model_filter = getattr(args, "model", "") or ""
    community = getattr(args, "community", False)
    community_url = ""
    if community:
        from asiai.community import get_api_url

        community_url = get_api_url()

    recs = recommend(
        chip=chip,
        ram_gb=ram_gb,
        use_case=use_case,
        model_filter=model_filter,
        db_path=db_path,
        community_url=community_url,
    )

    if not recs:
        print(dim("No recommendations available. Run 'asiai bench' first."))
        return 1

    print(bold(f"Recommendations for {chip} ({ram_gb} GB)"))
    if use_case != "throughput":
        print(dim(f"  Optimizing for: {use_case}"))
    print()

    for i, rec in enumerate(recs[:10], 1):
        score_color = green if rec.score >= 70 else (yellow if rec.score >= 40 else dim)
        conf_str = dim(f"[{rec.confidence}]")
        src_str = dim(f"({rec.source})")

        tok_str = f"{rec.median_tok_s:.1f} tok/s" if rec.median_tok_s else ""
        ttft_str = f"{rec.median_ttft_ms:.0f}ms TTFT" if rec.median_ttft_ms else ""
        metrics = ", ".join(filter(None, [tok_str, ttft_str]))

        line = f"  {i:>2}. {score_color(f'{rec.score:.0f}')} {rec.engine:<12} {rec.model:<30}"
        print(f"{line} {metrics}")
        print(f"      {dim(rec.reason)} {conf_str} {src_str}")
        for caveat in rec.caveats:
            print(f"      {yellow('⚠')} {caveat}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="asiai",
        description="Multi-engine LLM benchmark & monitoring CLI for Apple Silicon.",
    )
    parser.add_argument("--version", action="version", version=f"asiai {__version__}")
    parser.add_argument(
        "--url",
        metavar="URL",
        help="Inference server URL(s), comma-separated (default: auto-detect)",
    )

    subparsers = parser.add_subparsers(dest="command")

    # detect
    detect_parser = subparsers.add_parser("detect", help="Detect installed inference engines")
    detect_parser.add_argument("--url", metavar="URL", help="URL(s) to scan")

    # models
    models_parser = subparsers.add_parser("models", help="List loaded models across engines")
    models_parser.add_argument("--url", metavar="URL", help="URL(s) to scan")
    models_parser.add_argument(
        "--json", action="store_true", dest="json_output", help="Output as JSON"
    )

    # monitor
    monitor_parser = subparsers.add_parser(
        "monitor",
        help="Monitor system and inference metrics",
    )
    monitor_parser.add_argument("--url", metavar="URL", help="URL(s) to scan")
    monitor_parser.add_argument("--db", metavar="PATH", help="SQLite database path")
    monitor_parser.add_argument(
        "--watch",
        "-w",
        type=int,
        metavar="SEC",
        help="Refresh every SEC seconds",
    )
    monitor_parser.add_argument(
        "--history",
        "-H",
        metavar="PERIOD",
        help="Show history (e.g. 24h, 1h)",
    )
    monitor_parser.add_argument(
        "--analyze",
        "-a",
        type=int,
        nargs="?",
        const=24,
        metavar="HOURS",
        help="Comprehensive analysis (default: 24h)",
    )
    monitor_parser.add_argument(
        "--compare",
        "-c",
        nargs=2,
        metavar="TS",
        help="Compare two timestamps",
    )
    monitor_parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Collect and store without output (for daemon use)",
    )
    monitor_parser.add_argument(
        "--json", action="store_true", dest="json_output", help="Output as JSON"
    )
    monitor_parser.add_argument(
        "--alert-webhook",
        metavar="URL",
        help="POST alerts to webhook URL on state transitions",
    )

    # doctor
    doctor_parser = subparsers.add_parser("doctor", help="Diagnose installation and environment")
    doctor_parser.add_argument("--db", metavar="PATH", help="SQLite database path")

    # daemon
    daemon_parser = subparsers.add_parser("daemon", help="Manage background services")
    daemon_sub = daemon_parser.add_subparsers(dest="action")
    daemon_start_p = daemon_sub.add_parser("start", help="Start a background service")
    daemon_start_p.add_argument(
        "service",
        nargs="?",
        default="monitor",
        choices=["monitor", "web"],
        help="Service to start (default: monitor)",
    )
    daemon_start_p.add_argument(
        "--interval",
        "-i",
        type=int,
        default=60,
        metavar="SEC",
        help="Monitor collection interval in seconds (default: 60)",
    )
    daemon_start_p.add_argument(
        "--port", type=int, default=8899, help="Web dashboard port (default: 8899)"
    )
    daemon_start_p.add_argument(
        "--host", default="127.0.0.1", help="Web dashboard host (default: 127.0.0.1)"
    )
    daemon_start_p.add_argument(
        "--alert-webhook",
        metavar="URL",
        help="POST alerts to webhook URL (monitor service only)",
    )
    daemon_stop_p = daemon_sub.add_parser("stop", help="Stop a background service")
    daemon_stop_p.add_argument(
        "service",
        nargs="?",
        default="monitor",
        choices=["monitor", "web"],
        help="Service to stop (default: monitor)",
    )
    daemon_stop_p.add_argument(
        "--all", action="store_true", dest="stop_all", help="Stop all services"
    )
    daemon_sub.add_parser("status", help="Show all service statuses")
    daemon_logs_p = daemon_sub.add_parser("logs", help="Show service logs")
    daemon_logs_p.add_argument(
        "service",
        nargs="?",
        default="monitor",
        choices=["monitor", "web"],
        help="Service to show logs for (default: monitor)",
    )
    daemon_logs_p.add_argument(
        "--lines",
        "-n",
        type=int,
        default=50,
        metavar="N",
        help="Number of log lines to show (default: 50)",
    )

    # tui
    tui_parser = subparsers.add_parser("tui", help="Interactive TUI dashboard (requires textual)")
    tui_parser.add_argument("--url", metavar="URL", help="URL(s) to scan")
    tui_parser.add_argument("--db", metavar="PATH", help="SQLite database path")

    # web
    web_parser = subparsers.add_parser("web", help="Launch web dashboard (requires fastapi)")
    web_parser.add_argument("--url", metavar="URL", help="URL(s) to scan")
    web_parser.add_argument("--db", metavar="PATH", help="SQLite database path")
    web_parser.add_argument("--port", type=int, default=8899, help="Port (default: 8899)")
    web_parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    web_parser.add_argument(
        "--no-open", action="store_true", help="Don't open browser automatically"
    )

    # bench
    bench_parser = subparsers.add_parser("bench", help="Benchmark models across engines")
    bench_parser.add_argument("--url", metavar="URL", help="URL(s) to scan")
    bench_parser.add_argument("--model", "-m", help="Model to benchmark (default: auto-detect)")
    bench_parser.add_argument("--db", metavar="PATH", help="SQLite database path")
    bench_parser.add_argument(
        "--engines",
        "-e",
        metavar="LIST",
        help="Engines to benchmark, comma-separated (e.g. ollama,lmstudio)",
    )
    bench_parser.add_argument(
        "--prompts",
        "-p",
        metavar="LIST",
        help="Prompt types, comma-separated (code,tool_call,reasoning,long_gen)",
    )
    bench_parser.add_argument(
        "--runs",
        "-r",
        type=int,
        default=3,
        metavar="N",
        help="Number of runs per prompt for variance measurement (default: 3)",
    )
    bench_parser.add_argument(
        "--power",
        "-P",
        action="store_true",
        help="Measure GPU power consumption (requires sudo)",
    )
    bench_parser.add_argument(
        "--context-size",
        "-C",
        metavar="SIZE",
        help="Fill context with N tokens to stress-test TTFT (e.g. 64k, 128k, 4096)",
    )
    bench_parser.add_argument(
        "--export",
        "-E",
        metavar="FILE",
        help="Export results to JSON file (e.g. bench.json)",
    )
    bench_parser.add_argument(
        "--history",
        "-H",
        metavar="PERIOD",
        help="Show past benchmarks (e.g. 7d, 24h)",
    )
    bench_parser.add_argument(
        "--share",
        action="store_true",
        help="Share results to community benchmark database",
    )

    # leaderboard
    leaderboard_parser = subparsers.add_parser(
        "leaderboard", help="Show community benchmark leaderboard"
    )
    leaderboard_parser.add_argument("--chip", help="Filter by chip (e.g. 'Apple M4 Pro')")
    leaderboard_parser.add_argument("--model", "-m", help="Filter by model name")

    # compare
    compare_parser = subparsers.add_parser(
        "compare", help="Compare your benchmarks against community data"
    )
    compare_parser.add_argument("--chip", help="Hardware chip (default: auto-detect)")
    compare_parser.add_argument("--model", "-m", help="Model to compare")
    compare_parser.add_argument("--db", metavar="PATH", help="SQLite database path")

    # recommend
    recommend_parser = subparsers.add_parser(
        "recommend", help="Get engine recommendations for your hardware"
    )
    recommend_parser.add_argument("--model", "-m", help="Filter by model name")
    recommend_parser.add_argument("--db", metavar="PATH", help="SQLite database path")
    recommend_parser.add_argument(
        "--use-case",
        choices=["throughput", "latency", "efficiency"],
        default="throughput",
        help="Optimize for (default: throughput)",
    )
    recommend_parser.add_argument(
        "--community",
        action="store_true",
        help="Include community data in recommendations",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    commands = {
        "detect": cmd_detect,
        "models": cmd_models,
        "monitor": cmd_monitor,
        "bench": cmd_bench,
        "doctor": cmd_doctor,
        "daemon": cmd_daemon,
        "tui": cmd_tui,
        "web": cmd_web,
        "leaderboard": cmd_leaderboard,
        "compare": cmd_compare,
        "recommend": cmd_recommend,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    print(f"asiai {__version__} — command '{args.command}' not yet implemented.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
