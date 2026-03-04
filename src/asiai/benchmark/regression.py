"""Benchmark regression detection.

Compares current benchmark results against historical baselines stored in
SQLite to detect performance regressions.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass

from asiai.storage.db import DEFAULT_DB_PATH

logger = logging.getLogger("asiai.benchmark.regression")


@dataclass
class Regression:
    """A detected performance regression."""

    engine: str
    model: str
    metric: str  # "tok_per_sec", "ttft_ms"
    current: float
    baseline: float
    pct_change: float  # negative = regression for tok/s, positive = regression for ttft
    severity: str  # "minor" <15%, "significant" 15-30%, "major" >30%


def detect_regressions(
    current_results: list[dict],
    db_path: str = DEFAULT_DB_PATH,
    lookback_days: int = 7,
    threshold_pct: float = 10.0,
) -> list[Regression]:
    """Compare current benchmark results against historical baselines.

    Args:
        current_results: Results from the current benchmark run.
        db_path: Path to the SQLite database.
        lookback_days: How far back to look for baselines.
        threshold_pct: Minimum percentage change to flag as regression.

    Returns:
        List of detected regressions, sorted by severity.
    """
    if not current_results:
        return []

    # Group current results by (engine, model) and compute averages
    current_avgs = _compute_averages(current_results)

    # Query historical baselines
    baselines = _query_baselines(db_path, lookback_days, current_results[0].get("ts", 0))

    regressions: list[Regression] = []

    for (engine, model), cur in current_avgs.items():
        base = baselines.get((engine, model))
        if not base:
            continue

        # Check tok/s regression (lower is worse)
        if cur["tok_per_sec"] > 0 and base["tok_per_sec"] > 0:
            pct = ((cur["tok_per_sec"] - base["tok_per_sec"]) / base["tok_per_sec"]) * 100
            if pct < -threshold_pct:
                regressions.append(
                    Regression(
                        engine=engine,
                        model=model,
                        metric="tok_per_sec",
                        current=round(cur["tok_per_sec"], 1),
                        baseline=round(base["tok_per_sec"], 1),
                        pct_change=round(pct, 1),
                        severity=_classify_severity(abs(pct)),
                    )
                )

        # Check TTFT regression (higher is worse)
        if cur["ttft_ms"] > 0 and base["ttft_ms"] > 0:
            pct = ((cur["ttft_ms"] - base["ttft_ms"]) / base["ttft_ms"]) * 100
            if pct > threshold_pct:
                regressions.append(
                    Regression(
                        engine=engine,
                        model=model,
                        metric="ttft_ms",
                        current=round(cur["ttft_ms"], 1),
                        baseline=round(base["ttft_ms"], 1),
                        pct_change=round(pct, 1),
                        severity=_classify_severity(abs(pct)),
                    )
                )

    # Sort by severity (major first)
    severity_order = {"major": 0, "significant": 1, "minor": 2}
    regressions.sort(key=lambda r: severity_order.get(r.severity, 3))

    return regressions


def _compute_averages(results: list[dict]) -> dict[tuple[str, str], dict]:
    """Group results by (engine, model) and compute metric averages."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in results:
        key = (r["engine"], r["model"])
        if key not in groups:
            groups[key] = []
        groups[key].append(r)

    avgs: dict[tuple[str, str], dict] = {}
    for key, items in groups.items():
        tok_vals = [i["tok_per_sec"] for i in items if i.get("tok_per_sec", 0) > 0]
        ttft_vals = [i["ttft_ms"] for i in items if i.get("ttft_ms", 0) > 0]
        avgs[key] = {
            "tok_per_sec": sum(tok_vals) / len(tok_vals) if tok_vals else 0.0,
            "ttft_ms": sum(ttft_vals) / len(ttft_vals) if ttft_vals else 0.0,
        }
    return avgs


def _query_baselines(
    db_path: str,
    lookback_days: int,
    current_ts: int,
) -> dict[tuple[str, str], dict]:
    """Query historical averages from the database."""
    if current_ts:
        since = current_ts - (lookback_days * 86400)
    else:
        since = int(time.time()) - (lookback_days * 86400)
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT engine, model,
                          AVG(tok_per_sec) as avg_tok,
                          AVG(ttft_ms) as avg_ttft
                   FROM benchmarks
                   WHERE ts >= ? AND ts < ?
                     AND COALESCE(metrics_version, 1) = 2
                   GROUP BY engine, model""",
                (since, current_ts or int(time.time())),
            ).fetchall()

            baselines: dict[tuple[str, str], dict] = {}
            for row in rows:
                baselines[(row["engine"], row["model"])] = {
                    "tok_per_sec": row["avg_tok"] or 0.0,
                    "ttft_ms": row["avg_ttft"] or 0.0,
                }
            return baselines
        finally:
            conn.close()
    except Exception as e:
        logger.debug("Failed to query baselines from %s: %s", db_path, e)
        return {}


def _classify_severity(pct: float) -> str:
    """Classify regression severity by percentage."""
    if pct > 30:
        return "major"
    if pct > 15:
        return "significant"
    return "minor"
