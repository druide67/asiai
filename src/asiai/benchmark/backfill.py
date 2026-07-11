"""Backfill ``bench_runs`` session rows from historic raw ``benchmarks`` rows.

The fine-grained ``benchmarks`` table has carried one row per timed run since
the beginning; the session-level ``bench_runs`` table only arrived in 1.24.0
(and compare sessions only joined it later). This module rebuilds the missing
session rows so History covers the whole archive, not just post-1.24 runs.

Session detection is exact, not heuristic: the runner stamps the session
start timestamp on every row it writes, so one distinct ``ts`` value == one
bench invocation. That same ``ts`` is the idempotence key — a session whose
timestamp already has a standard ``bench_runs`` row (live-persisted or
previously backfilled) is never written twice.

Honesty rules for a payload rebuilt post-hoc (omission, never invention):

- it is MARKED ``"reconstructed": true`` — ``bench_runs.payload`` is verbatim
  by contract, so a rebuilt payload must say what it is;
- nothing unmeasured is invented: no memory-pressure gate (the MemoryWatcher
  alert was never persisted), no run errors, and ``asiai_version`` is the one
  recorded on the raw rows — absent when they predate that column, never
  today's version.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from asiai.benchmark.persist import persist_standard_session
from asiai.benchmark.reporter import build_export_payload, build_report, slot_label
from asiai.storage.db import query_bench_runs, query_benchmarks

# Raw-row fields the aggregator subscripts or compares directly — a NULL in
# any of them (old or third-party DBs) would crash the whole backfill with a
# TypeError, so coerce to the neutral "not measured" zero.
_REQUIRED_NUMERIC = (
    "tok_per_sec",
    "ttft_ms",
    "ttft_client_ms",
    "tokens_generated",
    "total_duration_ms",
    "power_watts",
    "soc_watts",
)


@dataclass
class Session:
    """One detected raw-run session and what backfill would do with it."""

    ts: int
    rows: list[dict] = field(repr=False, default_factory=list)
    report: dict = field(repr=False, default_factory=dict)
    exists: bool = False  # bench_runs already has a standard row at this ts
    created_id: int | None = None

    @property
    def session_type(self) -> str:
        return str(self.report.get("session_type", "engine"))

    @property
    def slot_names(self) -> list[str]:
        session_type = self.session_type
        return [slot_label(s, session_type) for s in self.report.get("slots", [])]


def _sanitize(row: dict) -> dict:
    clean = dict(row)
    for key in _REQUIRED_NUMERIC:
        if clean.get(key) is None:
            clean[key] = 0.0
    return clean


def detect_sessions(db_path: str) -> list[Session]:
    """Group all raw benchmark rows into sessions (one per distinct ts)."""
    by_ts: dict[int, list[dict]] = {}
    for row in query_benchmarks(db_path):  # hours=0 → the whole archive
        by_ts.setdefault(int(row.get("ts") or 0), []).append(_sanitize(row))
    existing = {
        int(r["ts"]) for r in query_bench_runs(db_path, bench_type="standard", limit=1_000_000)
    }
    return [
        Session(ts=ts, rows=rows, report=build_report(rows), exists=ts in existing)
        for ts, rows in sorted(by_ts.items())
        if ts > 0
    ]


def build_session_payload(session: Session) -> dict:
    """Rebuild the session payload through the real producer chain."""
    payload = build_export_payload(session.rows, session.report)
    payload["reconstructed"] = True
    # The version that RAN the bench, not the one doing the backfill.
    payload["asiai_version"] = next(
        (str(r["asiai_version"]) for r in session.rows if r.get("asiai_version")), ""
    )
    return payload


def backfill_bench_runs(db_path: str, apply: bool = False) -> list[Session]:
    """Detect missing session rows; write them when ``apply`` is True.

    Returns the full session inventory (existing sessions included) so the
    caller can render what was — or would be — created.
    """
    sessions = detect_sessions(db_path)
    if not apply:
        return sessions
    for session in sessions:
        if session.exists:
            continue
        session.created_id = persist_standard_session(db_path, build_session_payload(session))
    return sessions
