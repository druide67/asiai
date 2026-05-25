"""CLI handlers for ``asiai fleet`` subcommands.

Sub-subcommand pattern (action dispatch on ``args.action``), mirroring
``cmd_daemon`` in ``asiai.cli``.
"""

from __future__ import annotations

import argparse
import json as _json
import sys
import time
from typing import Any

from asiai.display.formatters import bold, dim, green, red, yellow
from asiai.fleet import config as fleet_config
from asiai.fleet.poll import poll_all, poll_one


def _format_age(unix_ts: int | None) -> str:
    """Return a human-readable relative age, e.g. '12s ago' or 'never'."""
    if unix_ts is None:
        return "never"
    delta = int(time.time()) - int(unix_ts)
    if delta < 60:
        return f"{delta}s ago"
    if delta < 3600:
        return f"{delta // 60}m ago"
    if delta < 86400:
        return f"{delta // 3600}h ago"
    return f"{delta // 86400}d ago"


def _color_age(unix_ts: int | None) -> str:
    """Render age with a color hint based on freshness."""
    label = _format_age(unix_ts)
    if unix_ts is None:
        return dim(label)
    delta = int(time.time()) - int(unix_ts)
    if delta < 30:
        return green(label)
    if delta < 300:
        return yellow(label)
    return red(label)


def _cmd_add(args: argparse.Namespace) -> int:
    nickname = args.nickname
    url = args.url
    role = args.role or ""
    auth_token = getattr(args, "auth_token", None) or None
    try:
        entry = fleet_config.upsert_node(nickname, url, role=role, auth_token=auth_token)
    except ValueError as e:
        print(red(f"✗ {e}"), file=sys.stderr)
        return 1
    print(green(f"✓ added node '{entry['nickname']}'"))
    print(f"  url:  {entry['asiai_url']}")
    if entry["role"]:
        print(f"  role: {entry['role']}")
    if auth_token:
        print(dim("  auth: configured (writes enabled via 'aisctl fleet push')"))
    print(
        dim(
            "  remember to start `asiai web --host 0.0.0.0` on the remote "
            "so that this host can reach /api/v1/snapshot."
        )
    )
    return 0


def _cmd_remove(args: argparse.Namespace) -> int:
    if fleet_config.remove_node(args.nickname):
        print(green(f"✓ removed node '{args.nickname}'"))
        return 0
    print(red(f"✗ no node named '{args.nickname}'"), file=sys.stderr)
    return 1


def _cmd_list(args: argparse.Namespace) -> int:
    nodes = fleet_config.get_nodes()
    if args.json:
        # Strip auth_token so it never leaks into terminals, CI logs, or
        # shell history when piping to jq / files. The on-disk fleet.json
        # remains the only place tokens live (and it is 0o600).
        redacted = [fleet_config.redact_node(n) for n in nodes]
        print(_json.dumps({"nodes": redacted}, indent=2))
        return 0
    if not nodes:
        print(dim("No nodes configured. Add one with `asiai fleet add`."))
        return 0
    # Header
    print(bold(f"  {'NICKNAME':<20} {'URL':<35} {'ROLE':<15} {'LAST SEEN':<15} STATUS"))
    for n in nodes:
        print(
            f"  {n.get('nickname', ''):<20} "
            f"{n.get('asiai_url', ''):<35} "
            f"{n.get('role') or '-':<15} "
            f"{_format_age(n.get('last_seen')):<15} "
            f"{n.get('last_status') or '-'}"
        )
    return 0


def _summarize_snapshot(snapshot: dict[str, Any] | None) -> str:
    """Return a compact one-liner summary of a node snapshot.

    The remote ``/api/v1/snapshot`` exposes engines under the
    ``engines_status`` key (see ``asiai.collectors.snapshot.collect_full_snapshot``).
    Each entry is a dict with ``name``, ``reachable``, and a ``models`` list
    of currently-loaded models. We summarise as "N/M reachable, K models"
    so the operator sees both engine health and the load footprint at a
    glance.
    """
    if not snapshot:
        return ""
    engines = snapshot.get("engines_status") or []
    if not isinstance(engines, list) or not engines:
        return "no engine data"
    reachable = [e for e in engines if isinstance(e, dict) and e.get("reachable")]
    model_count = sum(len(e.get("models") or []) for e in engines if isinstance(e, dict))
    if model_count:
        return f"{len(reachable)}/{len(engines)} engines, {model_count} models loaded"
    return f"{len(reachable)}/{len(engines)} engines reachable"


def _cmd_status(args: argparse.Namespace) -> int:
    nodes = fleet_config.get_nodes()
    if not nodes:
        print(dim("No nodes configured. Add one with `asiai fleet add`."))
        return 0

    polls = poll_all(nodes, timeout=args.timeout)

    # Persist status back to fleet.json
    for p in polls:
        fleet_config.touch_node_status(p.nickname, ok=p.ok, error=p.error)

    if args.json:
        print(
            _json.dumps(
                {
                    "polled_at": int(time.time()),
                    "nodes": [p.to_dict() for p in polls],
                },
                indent=2,
            )
        )
        return 0

    print(bold(f"  {'NICKNAME':<20} {'STATUS':<10} {'LATENCY':<10} {'AGE':<15} SUMMARY"))
    any_failed = False
    for p in polls:
        status_str = green("ok") if p.ok else red("DOWN")
        latency = f"{p.latency_ms:.0f}ms" if p.ok else "-"
        summary = _summarize_snapshot(p.snapshot) if p.ok else (p.error or "")
        print(
            f"  {p.nickname:<20} {status_str:<10} {latency:<10} "
            f"{_color_age(p.reached_at):<15} {summary}"
        )
        if not p.ok:
            any_failed = True
    return 1 if any_failed else 0


def _cmd_ping(args: argparse.Namespace) -> int:
    node = fleet_config.find_node(args.nickname)
    if not node:
        print(red(f"✗ no node named '{args.nickname}'"), file=sys.stderr)
        return 1
    p = poll_one(node["nickname"], node["asiai_url"], timeout=args.timeout)
    fleet_config.touch_node_status(p.nickname, ok=p.ok, error=p.error)
    if p.ok:
        print(green(f"✓ {p.nickname} reachable in {p.latency_ms:.0f}ms"))
        print(f"  summary: {_summarize_snapshot(p.snapshot)}")
        return 0
    print(red(f"✗ {p.nickname} unreachable: {p.error}"), file=sys.stderr)
    return 1


def cmd_fleet(args: argparse.Namespace) -> int:
    """Top-level dispatcher for ``asiai fleet {add,remove,list,status,ping}``."""
    action = getattr(args, "action", None)
    if not action:
        print(
            dim("Usage: asiai fleet {add|remove|list|status|ping}"),
            file=sys.stderr,
        )
        return 1
    dispatch = {
        "add": _cmd_add,
        "remove": _cmd_remove,
        "list": _cmd_list,
        "status": _cmd_status,
        "ping": _cmd_ping,
    }
    handler = dispatch.get(action)
    if handler is None:
        print(red(f"✗ unknown action: {action}"), file=sys.stderr)
        return 1
    return handler(args)


def add_fleet_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``asiai fleet`` subcommand on the main parser."""
    fleet_parser = subparsers.add_parser(
        "fleet",
        help="Observe multiple asiai instances across hosts (Phase 1 read-only)",
    )
    fleet_sub = fleet_parser.add_subparsers(dest="action")

    p_add = fleet_sub.add_parser("add", help="Add a node to the fleet")
    p_add.add_argument("nickname", help="Unique short name for this node")
    p_add.add_argument(
        "--url",
        required=True,
        help="Base URL of the remote asiai web instance (e.g. http://192.0.2.1:8899)",
    )
    p_add.add_argument(
        "--role",
        default="",
        help="Free-text role label (e.g. 'workstation', 'spare')",
    )
    p_add.add_argument(
        "--auth-token",
        default=None,
        help="Bearer token for Phase 2 write commands (the remote node "
        "must have a matching token registered via 'asiai auth init').",
    )

    p_remove = fleet_sub.add_parser("remove", help="Remove a node from the fleet")
    p_remove.add_argument("nickname", help="Nickname of the node to remove")

    p_list = fleet_sub.add_parser("list", help="List configured nodes")
    p_list.add_argument("--json", action="store_true", help="Emit JSON instead of a table")

    p_status = fleet_sub.add_parser(
        "status", help="Poll all nodes in parallel and print a status table"
    )
    p_status.add_argument(
        "--timeout", type=float, default=5.0, help="Per-node HTTP timeout in seconds"
    )
    p_status.add_argument("--json", action="store_true", help="Emit JSON instead of a table")

    p_ping = fleet_sub.add_parser("ping", help="Poll a single node")
    p_ping.add_argument("nickname", help="Nickname of the node to ping")
    p_ping.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout in seconds")
