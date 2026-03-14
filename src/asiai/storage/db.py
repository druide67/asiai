"""SQLite database operations for metrics persistence."""

from __future__ import annotations

import logging
import os
import sqlite3
import time

from asiai.storage.schema import MIGRATIONS, RETENTION_DAYS, SCHEMA_SQL

logger = logging.getLogger("asiai.storage.db")

# Default DB location follows XDG conventions on macOS.
DEFAULT_DB_PATH = os.path.expanduser("~/.local/share/asiai/metrics.db")


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Create schema and run migrations. Uses WAL mode for concurrent reads."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA_SQL)

        # Run migrations for columns that may not exist yet
        for migration in MIGRATIONS:
            existing = {
                row[1]
                for row in conn.execute(f"PRAGMA table_info({migration['table']})").fetchall()
            }
            for col, sql in zip(migration["columns"], migration["sql"]):
                if col not in existing:
                    try:
                        conn.execute(sql)
                        logger.info("Migration: %s", sql)
                    except sqlite3.OperationalError as exc:
                        logger.warning("Migration failed: %s — %s", sql, exc)

        conn.commit()
    finally:
        conn.close()


def store_snapshot(db_path: str, snap: dict) -> None:
    """Persist a metrics snapshot to SQLite."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO metrics
               (ts, cpu_load_1, cpu_load_5, cpu_load_15,
                mem_total, mem_used, mem_pressure,
                thermal_level, thermal_speed_limit, uptime,
                inference_engine, engine_version,
                gpu_utilization_pct, gpu_renderer_pct, gpu_tiler_pct,
                gpu_mem_in_use, gpu_mem_allocated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                snap["ts"],
                snap["cpu_load_1"],
                snap["cpu_load_5"],
                snap["cpu_load_15"],
                snap["mem_total"],
                snap["mem_used"],
                snap["mem_pressure"],
                snap["thermal_level"],
                snap["thermal_speed_limit"],
                snap["uptime"],
                snap.get("inference_engine"),
                snap.get("engine_version"),
                snap.get("gpu_utilization_pct", -1),
                snap.get("gpu_renderer_pct", -1),
                snap.get("gpu_tiler_pct", -1),
                snap.get("gpu_mem_in_use", 0),
                snap.get("gpu_mem_allocated", 0),
            ),
        )
        for model in snap.get("models", []):
            conn.execute(
                """INSERT INTO models
                   (ts, engine, name, size_vram, size_total, model_format, quantization)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    snap["ts"],
                    model.get("engine", ""),
                    model["name"],
                    model.get("size_vram", 0),
                    model.get("size_total", 0),
                    model.get("format", ""),
                    model.get("quantization", ""),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def purge_old(db_path: str, days: int = RETENTION_DAYS) -> int:
    """Delete entries older than `days` days. Returns number of deleted rows."""
    cutoff = int(time.time()) - (days * 86400)
    # Process metrics have shorter retention (7 days)
    proc_cutoff = int(time.time()) - (7 * 86400)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM benchmarks WHERE ts < ?", (cutoff,))
        conn.execute("DELETE FROM models WHERE ts < ?", (cutoff,))
        conn.execute("DELETE FROM benchmark_process WHERE ts < ?", (proc_cutoff,))
        cursor = conn.execute("DELETE FROM metrics WHERE ts < ?", (cutoff,))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def query_history(db_path: str, hours: int = 24, since: int = 0, until: int = 0) -> list[dict]:
    """Return metrics entries for a time range.

    If since/until are provided (unix timestamps), they take precedence over hours.
    """
    if since > 0:
        ts_start = since
        ts_end = until if until > 0 else int(time.time())
    else:
        ts_start = int(time.time()) - (hours * 3600)
        ts_end = int(time.time())
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        # Single query with LEFT JOIN to avoid N+1 (was 1+N queries before)
        rows = conn.execute(
            "SELECT m.*, "
            "mo.engine AS mo_engine, mo.name AS mo_name, "
            "mo.size_vram AS mo_size_vram, mo.size_total AS mo_size_total, "
            "mo.model_format AS mo_model_format, mo.quantization AS mo_quantization "
            "FROM metrics m "
            "LEFT JOIN models mo ON mo.ts = m.ts "
            "WHERE m.ts >= ? AND m.ts <= ? "
            "ORDER BY m.ts",
            (ts_start, ts_end),
        ).fetchall()

        # Group models by timestamp
        result: dict[int, dict] = {}
        for row in rows:
            ts = row["ts"]
            if ts not in result:
                entry = {k: row[k] for k in row.keys() if not k.startswith("mo_")}
                entry["models"] = []
                result[ts] = entry
            if row["mo_name"] is not None:
                result[ts]["models"].append(
                    {
                        "engine": row["mo_engine"],
                        "name": row["mo_name"],
                        "size_vram": row["mo_size_vram"],
                        "size_total": row["mo_size_total"],
                        "model_format": row["mo_model_format"],
                        "quantization": row["mo_quantization"],
                    }
                )
        return list(result.values())
    finally:
        conn.close()


def store_benchmark(db_path: str, results: list[dict]) -> None:
    """Persist benchmark results to SQLite."""
    conn = sqlite3.connect(db_path)
    try:
        for r in results:
            conn.execute(
                """INSERT INTO benchmarks
                   (ts, engine, model, prompt_type,
                    tokens_generated, tok_per_sec, ttft_ms, total_duration_ms,
                    vram_bytes, mem_used, thermal_level, thermal_speed_limit,
                    run_index, power_watts, tok_per_sec_per_watt, load_time_ms,
                    metrics_version,
                    engine_version, model_format, model_quantization,
                    generation_duration_ms, hw_chip, os_version,
                    context_size, gpu_cores, ram_gb)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    r["ts"],
                    r["engine"],
                    r["model"],
                    r["prompt_type"],
                    r.get("tokens_generated", 0),
                    r.get("tok_per_sec", 0.0),
                    r.get("ttft_ms", 0.0),
                    r.get("total_duration_ms", 0.0),
                    r.get("vram_bytes", 0),
                    r.get("mem_used", 0),
                    r.get("thermal_level", ""),
                    r.get("thermal_speed_limit", -1),
                    r.get("run_index", 0),
                    r.get("power_watts", 0.0),
                    r.get("tok_per_sec_per_watt", 0.0),
                    r.get("load_time_ms", 0.0),
                    2,  # metrics_version: 2 = tok/s excludes TTFT
                    r.get("engine_version", ""),
                    r.get("model_format", ""),
                    r.get("model_quantization", ""),
                    r.get("generation_duration_ms", 0.0),
                    r.get("hw_chip", ""),
                    r.get("os_version", ""),
                    r.get("context_size", 0),
                    r.get("gpu_cores", 0),
                    r.get("ram_gb", 0),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def store_benchmark_process(db_path: str, results: list[dict]) -> None:
    """Persist per-run process metrics to the benchmark_process table."""
    conn = sqlite3.connect(db_path)
    try:
        for r in results:
            cpu = r.get("proc_cpu_pct", 0.0)
            rss = r.get("proc_rss_bytes", 0)
            if cpu <= 0 and rss <= 0:
                continue
            conn.execute(
                """INSERT INTO benchmark_process
                   (ts, engine, run_index, proc_cpu_pct, proc_mem_pct,
                    proc_rss_bytes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    r["ts"],
                    r["engine"],
                    r.get("run_index", 0),
                    cpu,
                    r.get("proc_mem_pct", 0.0),
                    rss,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def query_benchmark_process(db_path: str, hours: int = 168, engine: str = "") -> list[dict]:
    """Query benchmark process metrics for a time range."""
    since = int(time.time()) - (hours * 3600)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        query = (
            "SELECT ts, engine, run_index, proc_cpu_pct, proc_mem_pct, "
            "proc_rss_bytes FROM benchmark_process WHERE ts >= ?"
        )
        params: list = [since]
        if engine:
            query += " AND engine = ?"
            params.append(engine)
        query += " ORDER BY ts"
        return [dict(row) for row in conn.execute(query, params).fetchall()]
    finally:
        conn.close()


def query_benchmarks(
    db_path: str, hours: int = 0, model: str = "", since: int = 0, until: int = 0
) -> list[dict]:
    """Query past benchmark results.

    Args:
        hours: If > 0, limit to last N hours. If 0, return all.
        model: If non-empty, filter by model name.
        since: Unix timestamp start (overrides hours if > 0).
        until: Unix timestamp end (defaults to now).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        query = "SELECT * FROM benchmarks WHERE 1=1"
        params: list = []

        if since > 0:
            query += " AND ts >= ?"
            params.append(since)
            ts_end = until if until > 0 else int(time.time())
            query += " AND ts <= ?"
            params.append(ts_end)
        elif hours > 0:
            ts_since = int(time.time()) - (hours * 3600)
            query += " AND ts >= ?"
            params.append(ts_since)

        if model:
            query += " AND model = ?"
            params.append(model)

        query += " ORDER BY ts DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def store_engine_status(db_path: str, statuses: list[dict]) -> None:
    """Persist engine reachability status to SQLite."""
    conn = sqlite3.connect(db_path)
    try:
        ts = int(time.time())
        for s in statuses:
            conn.execute(
                """INSERT INTO engine_status
                   (ts, engine, reachable, version, models_loaded, vram_total, url,
                    tcp_connections, requests_processing,
                    tokens_predicted_total, kv_cache_usage_ratio)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ts,
                    s["name"],
                    1 if s.get("reachable") else 0,
                    s.get("version", ""),
                    len(s.get("models", [])),
                    s.get("vram_total", 0),
                    s.get("url", ""),
                    s.get("tcp_connections", 0),
                    s.get("requests_processing", 0),
                    s.get("tokens_predicted_total", 0),
                    s.get("kv_cache_usage_ratio", -1),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def query_engine_uptime(db_path: str, engine: str, hours: int = 24) -> float:
    """Calculate engine uptime percentage over the last N hours.

    Returns a float between 0.0 and 100.0.
    """
    since = int(time.time()) - (hours * 3600)
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) as total, SUM(reachable) as up "
            "FROM engine_status WHERE engine = ? AND ts >= ?",
            (engine, since),
        ).fetchone()
        if row and row[0] > 0:
            return (row[1] / row[0]) * 100.0
        return 0.0
    finally:
        conn.close()


def query_engine_status_history(db_path: str, hours: int = 24, engine: str = "") -> list[dict]:
    """Return engine_status rows for the last N hours, optionally filtered by engine."""
    since = int(time.time()) - (hours * 3600)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        query = (
            "SELECT ts, engine, reachable, version, models_loaded, vram_total, "
            "tcp_connections, requests_processing, tokens_predicted_total, "
            "kv_cache_usage_ratio FROM engine_status WHERE ts >= ?"
        )
        params: list = [since]
        if engine:
            query += " AND engine = ?"
            params.append(engine)
        query += " ORDER BY ts"
        return [dict(row) for row in conn.execute(query, params).fetchall()]
    finally:
        conn.close()


def query_latest_benchmarks(db_path: str) -> list[dict]:
    """Return the most recent benchmark result per engine+model pair."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT engine, model, tok_per_sec, ttft_ms, power_watts
               FROM benchmarks
               WHERE (engine, model, ts) IN (
                   SELECT engine, model, MAX(ts)
                   FROM benchmarks
                   GROUP BY engine, model
               )"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def store_alert(db_path: str, alert: dict) -> None:
    """Persist an alert to SQLite."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """INSERT INTO alerts
               (ts, alert_type, severity, message, details, webhook_sent, webhook_status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                alert["ts"],
                alert["alert_type"],
                alert["severity"],
                alert["message"],
                alert.get("details", ""),
                1 if alert.get("webhook_sent") else 0,
                alert.get("webhook_status"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def query_recent_alerts(db_path: str, alert_type: str, seconds: int = 300) -> list[dict]:
    """Return alerts of a given type within the last N seconds (for cooldown)."""
    since = int(time.time()) - seconds
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE alert_type = ? AND ts >= ? ORDER BY ts DESC",
            (alert_type, since),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def query_alert_history(db_path: str, hours: int = 24) -> list[dict]:
    """Return all alerts from the last N hours."""
    since = int(time.time()) - (hours * 3600)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE ts >= ? ORDER BY ts DESC",
            (since,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def store_community_submission(db_path: str, submission: dict) -> None:
    """Record a community benchmark submission attempt."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO community_submissions
               (id, ts, model, status, response_status, error, payload_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                submission["id"],
                submission["ts"],
                submission["model"],
                submission.get("status", "pending"),
                submission.get("response_status"),
                submission.get("error", ""),
                submission.get("payload_hash", ""),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def query_compare(db_path: str, before_ts: int, after_ts: int) -> dict:
    """Compare metrics at two timestamps (nearest match)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:

        def nearest(ts: int) -> dict | None:
            row = conn.execute(
                "SELECT * FROM metrics ORDER BY ABS(ts - ?) LIMIT 1", (ts,)
            ).fetchone()
            if not row:
                return None
            entry = dict(row)
            # Single extra query per point (only 2 points total in compare)
            models = conn.execute(
                "SELECT engine, name, size_vram, size_total, model_format, quantization "
                "FROM models WHERE ts = ?",
                (row["ts"],),
            ).fetchall()
            entry["models"] = [dict(m) for m in models]
            return entry

        return {"before": nearest(before_ts), "after": nearest(after_ts)}
    finally:
        conn.close()
