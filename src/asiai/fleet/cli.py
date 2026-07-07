"""CLI handlers for ``asiai fleet`` subcommands.

Sub-subcommand pattern (action dispatch on ``args.action``), mirroring
``cmd_daemon`` in ``asiai.cli``.
"""

from __future__ import annotations

import argparse
import json as _json
import os
import re
import sys
import time
from typing import Any

from asiai.auth import audit
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


# Hard cap on --limit, and the pool size fetched when a filter narrows
# the view (filters discard events, so we read a larger window and trim
# back down to --limit afterwards). read_tail() is O(pool), the journal
# rotates at 10 MB — 1000 lines is a cheap upper bound.
_AUDIT_LIMIT_CAP = 1000

_SINCE_RE = re.compile(r"(\d+)([smhd])")
_SINCE_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def _parse_since(text: str) -> int:
    """Parse a relative duration like '30m', '2h' or '1d' into seconds."""
    m = _SINCE_RE.fullmatch(text.strip())
    if not m:
        raise ValueError(f"invalid --since value {text!r} (expected e.g. 30m, 2h, 1d)")
    return int(m.group(1)) * _SINCE_UNITS[m.group(2)]


# Control chars (ANSI escapes, CR/LF, NUL...) never reach the terminal:
# the journal's writers already validate what lands in the fields we
# print, but a forensics tool must survive — not amplify — a damaged or
# hand-edited journal. Coercion also freezes the anti-injection
# guarantee if a free-text field (e.g. `error`) joins the table later.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def _cell(value: Any) -> str:
    """Coerce any journal value into a printable single-line cell."""
    if value is None or value == "":
        return "-"
    return _CONTROL_CHARS_RE.sub("?", str(value))


def _format_audit_row(event: dict[str, Any]) -> str:
    ts = event.get("ts")
    when = "-"
    if isinstance(ts, (int, float)):
        try:
            when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
        except (OverflowError, OSError, ValueError):
            when = "-"  # out-of-range ts in a malformed line — keep the row
    action = _cell(event.get("command") or event.get("event"))
    status = _cell(event.get("status"))
    if status == "ok":
        status_str = green(status)
    elif status == "denied":
        status_str = red(status)
    else:
        status_str = yellow(status)
    return (
        f"  {when:<20} "
        f"{_cell(event.get('actor_type')):<9} "
        f"{action:<22} "
        f"{_cell(event.get('nickname')):<12} "
        f"{status_str:<7} "
        f"{_cell(event.get('http_status')):<5} "
        f"{_cell(event.get('source_ip'))}"
    )


def _cmd_audit(args: argparse.Namespace) -> int:
    """Show the LOCAL node's fleet audit journal (the file this host owns).

    This is a direct read of ``~/.local/share/asiai/fleet-audit.jsonl`` —
    same trust boundary as the file's owner opening it in a pager, so no
    redaction is applied (unlike the one-shot MCP exchange, whose output
    feeds an LLM context). Run it on the hub to see fleet-wide writes.
    """
    limit = max(1, min(args.limit, _AUDIT_LIMIT_CAP))
    since_cutoff: int | None = None
    if args.since:
        try:
            since_cutoff = int(time.time()) - _parse_since(args.since)
        except ValueError as e:
            print(red(f"✗ {e}"), file=sys.stderr)
            return 1

    # "Can't read the journal" must never look like "nothing happened":
    # read_tail() swallows OSErrors into [], which is right for the web
    # routes but would be a silent false negative in a forensics CLI.
    if not os.path.exists(audit.AUDIT_PATH):
        print(dim(f"No audit journal yet at {audit.AUDIT_PATH}."))
        return 0
    if not os.access(audit.AUDIT_PATH, os.R_OK):
        print(red(f"✗ cannot read audit journal: {audit.AUDIT_PATH}"), file=sys.stderr)
        return 1

    filtered = bool(args.actor or args.status or since_cutoff is not None)
    events = audit.read_tail(_AUDIT_LIMIT_CAP if filtered else limit)
    if args.actor:
        events = [e for e in events if e.get("actor_type") == args.actor]
    if args.status:
        events = [e for e in events if e.get("status") == args.status]
    if since_cutoff is not None:
        events = [
            e for e in events if isinstance(e.get("ts"), (int, float)) and e["ts"] >= since_cutoff
        ]
    events = events[:limit]

    # A filtered view only searches the newest _AUDIT_LIMIT_CAP events —
    # say so, because for an audit tool a silent false negative ("no
    # denials!" when the denial simply aged out of the window) is the
    # worst failure mode.
    window_note = f"(searched the newest {_AUDIT_LIMIT_CAP} journal events)" if filtered else None

    if args.json:
        payload: dict[str, Any] = {"events": events}
        if window_note:
            payload["search_window"] = _AUDIT_LIMIT_CAP
        print(_json.dumps(payload, indent=2, default=str))
        return 0
    if not events:
        print(dim("No matching audit events." + (f" {window_note}" if window_note else "")))
        return 0
    # Oldest first, like `tail`: the most recent event lands next to the
    # prompt (read_tail returns newest first).
    events.reverse()
    print(
        bold(
            f"  {'TIME':<20} {'ACTOR':<9} {'ACTION':<22} {'NODE':<12} {'STATUS':<7} {'HTTP':<5} IP"
        )
    )
    for e in events:
        print(_format_audit_row(e))
    if window_note:
        print(dim(f"  {window_note}"))
    return 0


def cmd_fleet(args: argparse.Namespace) -> int:
    """Top-level dispatcher for ``asiai fleet {add,remove,list,status,ping,audit}``."""
    action = getattr(args, "action", None)
    if not action:
        print(
            dim("Usage: asiai fleet {add|remove|list|status|ping|audit}"),
            file=sys.stderr,
        )
        return 1
    dispatch = {
        "add": _cmd_add,
        "remove": _cmd_remove,
        "list": _cmd_list,
        "status": _cmd_status,
        "ping": _cmd_ping,
        "audit": _cmd_audit,
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

    p_audit = fleet_sub.add_parser(
        "audit",
        help="Show this host's fleet audit journal (run on the hub for fleet-wide writes)",
    )
    p_audit.add_argument(
        "--limit",
        type=int,
        default=50,
        help=f"Max events to show (default 50, cap {_AUDIT_LIMIT_CAP})",
    )
    p_audit.add_argument(
        "--actor",
        choices=[audit.ACTOR_MACHINE, audit.ACTOR_OPERATOR, audit.ACTOR_LOOPBACK],
        default=None,
        help="Filter by credential audience (machine=asai_ token, operator=dashboard session, "
        f"loopback=aint_ secret); searches the newest {_AUDIT_LIMIT_CAP} events",
    )
    p_audit.add_argument(
        "--status",
        choices=["ok", "denied", "error"],
        default=None,
        help=f"Filter by outcome; searches the newest {_AUDIT_LIMIT_CAP} events",
    )
    p_audit.add_argument(
        "--since",
        default=None,
        help="Only events newer than a relative duration, e.g. 30m, 2h, 1d; "
        f"searches the newest {_AUDIT_LIMIT_CAP} events",
    )
    p_audit.add_argument(
        "--json", action="store_true", help="Emit raw events as JSON (newest first)"
    )
