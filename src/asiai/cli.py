"""CLI entry point for asiai."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

from asiai import __version__


def _discover_engines(urls: list[str] | None = None) -> list:
    """Detect inference engines and return instantiated adapters."""
    from asiai.engines.detect import detect_engines
    from asiai.engines.lmstudio import LMStudioEngine
    from asiai.engines.ollama import OllamaEngine

    engine_map = {
        "ollama": OllamaEngine,
        "lmstudio": LMStudioEngine,
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
        results.append({
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
        })

    render_detect(results)
    return 0


def cmd_models(args: argparse.Namespace) -> int:
    """Handle 'models' command."""
    from asiai.display.formatters import bold, dim, format_bytes, green

    urls = _parse_urls(args.url)
    engines = _discover_engines(urls)

    if not engines:
        print(dim("No inference engines detected."))
        return 1

    for engine in engines:
        print(bold(f"{engine.name}") + f"  {dim(engine.base_url)}")
        running = engine.list_running()
        if running:
            for m in running:
                vram = format_bytes(m.size_vram) if m.size_vram else ""
                quant = m.quantization or ""
                print(f"  {green('●')} {m.name:<40} {vram:>10} {quant}")
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
            print("Error: --compare requires exactly 2 timestamps", file=sys.stderr)
            return 1
        data = query_compare(db_path, int(parts[0]), int(parts[1]))
        render_compare(data)
        return 0

    # Default: snapshot (with optional --watch)
    if args.watch:
        try:
            while True:
                subprocess.run(["clear"], check=False)
                snap = collect_snapshot(engines)
                store_snapshot(db_path, snap)
                render_snapshot(snap)
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print()
            return 0
    else:
        snap = collect_snapshot(engines)
        store_snapshot(db_path, snap)
        render_snapshot(snap)
        return 0


def cmd_bench(args: argparse.Namespace) -> int:
    """Handle 'bench' command."""
    from asiai.benchmark.reporter import aggregate_results
    from asiai.benchmark.runner import find_common_model, run_benchmark
    from asiai.display.cli_renderer import render_bench, render_bench_history
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
        print("No inference engines detected.", file=sys.stderr)
        return 1

    # Filter engines if --engines specified
    if args.engines:
        wanted = {e.strip().lower() for e in args.engines.split(",")}
        engines = [e for e in engines if e.name in wanted]
        if not engines:
            print(f"None of the specified engines found: {args.engines}", file=sys.stderr)
            return 1

    # Determine model
    model = find_common_model(engines, args.model or "")
    if not model:
        print("No model to benchmark. Load a model or use --model.", file=sys.stderr)
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
    bench_run = run_benchmark(engines, model, prompt_names)

    # Store results
    if bench_run.results:
        store_benchmark(db_path, bench_run.results)

    # Display errors
    for err in bench_run.errors:
        print(f"  Warning: {err}", file=sys.stderr)

    # Aggregate and render
    report = aggregate_results(bench_run.results)
    render_bench(report)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="asiai",
        description="Multi-engine LLM benchmark & monitoring CLI for Apple Silicon.",
    )
    parser.add_argument("--version", action="version", version=f"asiai {__version__}")
    parser.add_argument(
        "--url", metavar="URL",
        help="Inference server URL(s), comma-separated (default: auto-detect)",
    )

    subparsers = parser.add_subparsers(dest="command")

    # detect
    detect_parser = subparsers.add_parser("detect", help="Detect installed inference engines")
    detect_parser.add_argument("--url", metavar="URL", help="URL(s) to scan")

    # models
    models_parser = subparsers.add_parser("models", help="List loaded models across engines")
    models_parser.add_argument("--url", metavar="URL", help="URL(s) to scan")

    # monitor
    monitor_parser = subparsers.add_parser(
        "monitor", help="Monitor system and inference metrics",
    )
    monitor_parser.add_argument("--url", metavar="URL", help="URL(s) to scan")
    monitor_parser.add_argument("--db", metavar="PATH", help="SQLite database path")
    monitor_parser.add_argument(
        "--watch", "-w", type=int, metavar="SEC",
        help="Refresh every SEC seconds",
    )
    monitor_parser.add_argument(
        "--history", "-H", metavar="PERIOD",
        help="Show history (e.g. 24h, 1h)",
    )
    monitor_parser.add_argument(
        "--analyze", "-a", type=int, nargs="?", const=24, metavar="HOURS",
        help="Comprehensive analysis (default: 24h)",
    )
    monitor_parser.add_argument(
        "--compare", "-c", nargs=2, metavar="TS",
        help="Compare two timestamps",
    )

    # bench
    bench_parser = subparsers.add_parser("bench", help="Benchmark models across engines")
    bench_parser.add_argument("--url", metavar="URL", help="URL(s) to scan")
    bench_parser.add_argument("--model", "-m", help="Model to benchmark (default: auto-detect)")
    bench_parser.add_argument("--db", metavar="PATH", help="SQLite database path")
    bench_parser.add_argument(
        "--engines", "-e", metavar="LIST",
        help="Engines to benchmark, comma-separated (e.g. ollama,lmstudio)",
    )
    bench_parser.add_argument(
        "--prompts", "-p", metavar="LIST",
        help="Prompt types, comma-separated (code,tool_call,reasoning,long_gen)",
    )
    bench_parser.add_argument(
        "--history", "-H", metavar="PERIOD",
        help="Show past benchmarks (e.g. 7d, 24h)",
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
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    print(f"asiai {__version__} — command '{args.command}' not yet implemented.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
