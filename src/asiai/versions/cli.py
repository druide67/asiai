"""CLI surface for ``asiai versions``.

``collect_reports`` is the pure orchestrator (no printing) reused by the
CLI command, the ``doctor`` recap, and the web routes. ``cmd_versions`` is
the argparse handler; ``add_versions_subparser`` wires it into the main
parser, mirroring ``asiai.fleet.cli.add_fleet_subparser``.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json as _json

from asiai.versions.collectors import brew_outdated, installed_version, running_versions
from asiai.versions.compare import derive_status
from asiai.versions.models import EngineVersionReport
from asiai.versions.registry import load_specs, provider_keys
from asiai.versions.upstream import fetch_all


def collect_reports(
    check_upstream: bool = False,
    engine: str | None = None,
    urls: list[str] | None = None,
    timeout: float = 5.0,
) -> list[EngineVersionReport]:
    """Build per-engine version reports.

    Offline by default: running detection + installed lookup + a single
    ``brew outdated`` call. When *check_upstream* is True, engines that have
    no brew source but do have a PyPI package or GitHub repo are resolved
    over the network (brew-backed engines stay on brew, which is
    authoritative for them).

    Pure/testable — never prints. Returns reports sorted by engine name.
    """
    specs = load_specs()
    pkeys = provider_keys()
    if engine:
        specs = {k: v for k, v in specs.items() if k == engine}

    running = running_versions(urls)
    outdated = brew_outdated()  # offline, single subprocess

    # Resolve installed versions concurrently — each lookup shells out to
    # brew/pip/PlistBuddy (I/O-bound), and there are ~10 engines, so a
    # sequential loop is the dominant cost (e.g. it makes `asiai doctor`
    # blow past its timeout). A small thread pool keeps it snappy.
    items = sorted(specs.items())
    installed_by_name: dict[str, str | None] = {}
    if items:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(items))) as pool:
            futures = {pool.submit(installed_version, spec): name for name, spec in items}
            for fut in concurrent.futures.as_completed(futures):
                name = futures[fut]
                try:
                    installed_by_name[name] = fut.result()
                except Exception:  # noqa: BLE001 — a bad spec must not sink the report
                    installed_by_name[name] = None

    reports: list[EngineVersionReport] = []
    upstream_jobs: list[tuple[str, str, str]] = []

    for name, spec in items:
        inst = installed_by_name.get(name)
        run = running.get(name)
        notes = "no_upstream" if spec.no_upstream else ""

        avail: str | None = None
        has_brew = bool(spec.brew_formula or spec.brew_cask)
        if spec.brew_formula and spec.brew_formula in outdated:
            avail = outdated[spec.brew_formula]
        elif spec.brew_cask and spec.brew_cask in outdated:
            avail = outdated[spec.brew_cask]
        elif has_brew and inst:
            # Installed via brew and not listed as outdated -> already latest.
            avail = inst

        report = EngineVersionReport(
            engine_name=name,
            display=spec.display or name,
            running=run,
            installed=inst,
            available=avail,
            changelog_url=spec.changelog_url(),
            source="aisrv" if name in pkeys else "internal",
            notes=notes,
            version_scheme=spec.version_scheme,
        )

        # Network resolution only for non-brew engines, and only when asked.
        if check_upstream and not spec.no_upstream and avail is None and not has_brew:
            if spec.pip_package:
                upstream_jobs.append((name, "pypi", spec.pip_package))
            elif spec.github_repo:
                upstream_jobs.append((name, "github", spec.github_repo))

        reports.append(report)

    if upstream_jobs:
        fetched = fetch_all(upstream_jobs, timeout=timeout)
        by_name = {r.engine_name: r for r in reports}
        for ename, version in fetched.items():
            if version and ename in by_name:
                by_name[ename].available = version
            elif ename in by_name and by_name[ename].available is None:
                # Fetch attempted but failed (rate-limit / network).
                note = "upstream unavailable"
                existing = by_name[ename].notes
                by_name[ename].notes = f"{existing}; {note}".lstrip("; ") if existing else note

    for r in reports:
        r.status = derive_status(r, r.version_scheme)

    return reports


def cmd_versions(args: argparse.Namespace) -> int:
    """Handler for ``asiai versions``."""
    from asiai.cli import _parse_urls

    urls = _parse_urls(getattr(args, "url", None))
    reports = collect_reports(
        check_upstream=getattr(args, "check_upstream", False),
        engine=getattr(args, "engine", None),
        urls=urls,
        timeout=getattr(args, "timeout", 5.0),
    )

    if getattr(args, "json_output", False):
        print(_json.dumps({"engines": [r.to_dict() for r in reports]}, indent=2))
        return 0

    from asiai.display.cli_renderer import render_versions

    render_versions(reports, check_upstream=getattr(args, "check_upstream", False))
    return 0


def add_versions_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``versions`` subcommand on the main parser."""
    p = subparsers.add_parser(
        "versions",
        help="Compare running / installed / available engine versions",
    )
    p.add_argument(
        "--check-upstream",
        action="store_true",
        dest="check_upstream",
        help="Query PyPI/GitHub for the latest upstream versions (network, opt-in)",
    )
    p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit a JSON document instead of a table",
    )
    p.add_argument("--engine", metavar="NAME", help="Filter to a single engine")
    p.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Per-request timeout in seconds for upstream fetches (default: 5)",
    )
    p.add_argument("--url", metavar="URL", help="Engine URL(s) for running detection")
