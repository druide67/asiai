"""CLI entry point for asiai."""

import argparse
import sys

from asiai import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="asiai",
        description="Multi-engine LLM benchmark & monitoring CLI for Apple Silicon.",
    )
    parser.add_argument("--version", action="version", version=f"asiai {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # detect
    subparsers.add_parser("detect", help="Detect installed inference engines")

    # bench
    bench_parser = subparsers.add_parser("bench", help="Benchmark models across engines")
    bench_parser.add_argument("--engines", default="ollama,lmstudio", help="Engines to benchmark")
    bench_parser.add_argument("--model", help="Model to benchmark")

    # monitor
    monitor_parser = subparsers.add_parser("monitor", help="Monitor system and inference metrics")
    monitor_parser.add_argument("--watch", type=int, metavar="SEC", help="Refresh interval")
    monitor_parser.add_argument("--history", metavar="PERIOD", help="Show history (e.g. 24h)")

    # models
    subparsers.add_parser("models", help="List loaded models across engines")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    print(f"asiai {__version__} — command '{args.command}' not yet implemented.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
