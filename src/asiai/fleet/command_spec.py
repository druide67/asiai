"""Single source of truth for fleet write-command timeouts (SB, 2026-07-01).

The write path nests three HTTP/subprocess layers:

    aisctl fleet push  ──HTTP──▶  asiai web (LAN edge)  ──HTTP──▶  aisctl serve
    (client, outermost)          (edge)                           (loopback) ──▶ subprocess

Each command has ONE authoritative **work budget** — the seconds the actual
``aisctl <command>`` subprocess may run before ``aisctl serve`` kills it. Every
HTTP hop *outward* must then wait **longer** than the layer it calls, or it
abandons a command the inner layer is still legitimately running.

The bug this replaces (briefing retex): the three layers each hand-maintained
their own map, and the edge/client values were made *tighter* ("fail fast at the
edge") — INVERTING the nesting. Concretely the edge waited 300s for an
``upgrade`` the loopback runs to 600s, killing a live upgrade mid-write. Here the
budget is defined once and the outer deadlines are DERIVED (budget + margin per
hop), so the ordering ``client >= edge >= loopback`` holds by construction and
cannot drift. ``tests/test_command_spec.py`` enforces it.
"""

from __future__ import annotations

# Per-command work budget: the max seconds the real ``aisctl <command>``
# subprocess may run. ``install``/``uninstall``/``upgrade`` are generous because
# they shell out to Homebrew + LaunchDaemon orchestration. This map IS the
# command whitelist (see ``ALLOWED_COMMANDS``); adding a write command = one edit
# here, consumed everywhere.
WORK_BUDGET: dict[str, float] = {
    "purge": 30.0,
    "load": 300.0,
    "unload": 60.0,
    "stop": 60.0,
    "start": 120.0,
    "restart": 120.0,
    "install": 300.0,
    "uninstall": 120.0,
    "upgrade": 600.0,
}

# The closed whitelist of forwardable write commands — derived from WORK_BUDGET
# so the timeout map and the allowlist can never disagree.
ALLOWED_COMMANDS: frozenset[str] = frozenset(WORK_BUDGET)

# Seconds each HTTP hop waits BEYOND the layer it calls (network + handler
# overhead + a safety cushion). Applied once per hop outward.
HOP_MARGIN: float = 30.0

# Headroom for a wrapped inner tool (e.g. ``aisctl upgrade --timeout N``) to
# report its OWN failure before the loopback subprocess-kill fires — so the
# operator sees the tool's real error, not a generic SIGKILL.
INNER_HEADROOM: float = 60.0


def _budget(command: str) -> float:
    try:
        return WORK_BUDGET[command]
    except KeyError:
        raise KeyError(f"unknown fleet write command: {command!r}") from None


def loopback_timeout(command: str) -> float:
    """``aisctl serve`` subprocess-kill deadline — the innermost, authoritative budget."""
    return _budget(command)


def edge_timeout(command: str) -> float:
    """``asiai web`` HTTP timeout when proxying to the loopback (one hop out)."""
    return _budget(command) + HOP_MARGIN


def client_timeout(command: str) -> float:
    """``aisctl fleet push`` HTTP timeout when calling the edge (two hops out)."""
    return _budget(command) + 2 * HOP_MARGIN


def inner_tool_timeout(command: str) -> float:
    """Deadline to pass to a wrapped tool's own ``--timeout`` so it reports before
    the loopback kills it. Floored at 1s so a tiny budget never goes <= 0."""
    return max(_budget(command) - INNER_HEADROOM, 1.0)
