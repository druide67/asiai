"""In-memory Prometheus counters for the Phase 2 fleet write surface.

Exposed by ``/metrics`` via :func:`format_fleet_metrics`. Counters reset
on every ``asiai web`` restart, which is acceptable — Prometheus scrapes
absolute deltas and the audit log carries the persistent forensic
record.
"""

from __future__ import annotations

import threading
from collections import defaultdict

_lock = threading.Lock()

# (command, status) → count. ``command`` is the validated whitelist
# value, or ``"<none>"`` when the request was rejected before the
# payload was parsed (missing Bearer, bad nickname, oversize body, etc).
_FLEET_COMMAND_TOTAL: dict[tuple[str, str], int] = defaultdict(int)

# (token_id, error) → count when status != "ok". ``error`` is the
# coarse-grained tag (``rate_limited``, ``invalid_token``, ``bad_args``,
# ``aisctl_serve_unavailable``, ``upstream_error``).
_FLEET_DENIED_TOTAL: dict[tuple[str, str], int] = defaultdict(int)

# (command,) → cumulative latency (ms). Paired with the total counter
# to compute average latency externally. Exposing a histogram would
# require a vendored bucket library; the cumulative + count pair is
# enough for "avg latency over the scrape window" calculations.
_FLEET_LATENCY_MS_TOTAL: dict[str, int] = defaultdict(int)

# Current concurrency on the loopback aisctl serve. Decremented when the
# request returns. Useful for setting an alert "saturated for >N seconds".
_AISCTL_INFLIGHT: int = 0


def record(
    *,
    command: str | None,
    status: str,
    duration_ms: int = 0,
    error: str | None = None,
    token_id: str | None = None,
) -> None:
    """Atomically bump the counters for one fleet command attempt.

    ``status`` is one of ``"ok"``, ``"denied"``, ``"error"`` (matching
    the audit log enum). ``error`` is the coarse-grained tag from the
    audit log; ``token_id`` is the authenticated token id when known.
    """
    cmd = command or "<none>"
    with _lock:
        _FLEET_COMMAND_TOTAL[(cmd, status)] += 1
        if duration_ms:
            _FLEET_LATENCY_MS_TOTAL[cmd] += duration_ms
        if status != "ok" and error:
            tag = token_id or "<anon>"
            _FLEET_DENIED_TOTAL[(tag, error)] += 1


def aisctl_inflight_inc() -> None:
    """Mark a proxy call as in-flight on the loopback (concurrency gauge)."""
    global _AISCTL_INFLIGHT
    with _lock:
        _AISCTL_INFLIGHT += 1


def aisctl_inflight_dec() -> None:
    """Mark a proxy call as completed (gauge bookkeeping)."""
    global _AISCTL_INFLIGHT
    with _lock:
        _AISCTL_INFLIGHT = max(0, _AISCTL_INFLIGHT - 1)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def format_fleet_metrics() -> str:
    """Render the Phase 2 fleet counters in Prometheus text format."""
    with _lock:
        cmd_total = dict(_FLEET_COMMAND_TOTAL)
        denied_total = dict(_FLEET_DENIED_TOTAL)
        latency_total = dict(_FLEET_LATENCY_MS_TOTAL)
        inflight = _AISCTL_INFLIGHT

    lines: list[str] = []

    lines.append("# HELP asiai_fleet_command_total Fleet write requests by command and status.")
    lines.append("# TYPE asiai_fleet_command_total counter")
    for (cmd, status), count in sorted(cmd_total.items()):
        lines.append(
            f'asiai_fleet_command_total{{command="{_escape(cmd)}",status="{_escape(status)}"}} '
            f"{count}"
        )

    lines.append(
        "# HELP asiai_fleet_denied_total Fleet write requests rejected, by token id and reason."
    )
    lines.append("# TYPE asiai_fleet_denied_total counter")
    for (token_id, error), count in sorted(denied_total.items()):
        lines.append(
            f'asiai_fleet_denied_total{{token_id="{_escape(token_id)}",error="{_escape(error)}"}} '
            f"{count}"
        )

    lines.append(
        "# HELP asiai_fleet_latency_ms_total Cumulative wall time (ms) of fleet command "
        "requests, by command."
    )
    lines.append("# TYPE asiai_fleet_latency_ms_total counter")
    for cmd, ms in sorted(latency_total.items()):
        lines.append(f'asiai_fleet_latency_ms_total{{command="{_escape(cmd)}"}} {ms}')

    lines.append(
        "# HELP asiai_aisctl_inflight Number of in-flight proxy calls to the loopback aisctl serve."
    )
    lines.append("# TYPE asiai_aisctl_inflight gauge")
    lines.append(f"asiai_aisctl_inflight {inflight}")

    return "\n".join(lines) + "\n"


def reset_for_tests() -> None:
    """Clear all counters. Use in test fixtures only."""
    global _AISCTL_INFLIGHT
    with _lock:
        _FLEET_COMMAND_TOTAL.clear()
        _FLEET_DENIED_TOTAL.clear()
        _FLEET_LATENCY_MS_TOTAL.clear()
        _AISCTL_INFLIGHT = 0
