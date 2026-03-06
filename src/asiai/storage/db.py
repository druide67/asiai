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
                    except sqlite3.OperationalError:
                        pass  # Column already exists or table missing

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
                inference_engine, engine_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DELETE FROM benchmarks WHERE ts < ?", (cutoff,))
        conn.execute("DELETE FROM models WHERE ts < ?", (cutoff,))
        cursor = conn.execute("DELETE FROM metrics WHERE ts < ?", (cutoff,))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def query_history(db_path: str, hours: int = 24) -> list[dict]:
    """Return metrics entries for the last `hours` hours."""
    since = int(time.time()) - (hours * 3600)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM metrics WHERE ts >= ? ORDER BY ts", (since,)).fetchall()
        result = []
        for row in rows:
            entry = dict(row)
            models = conn.execute(
                "SELECT engine, name, size_vram, size_total, model_format, quantization "
                "FROM models WHERE ts = ?",
                (row["ts"],),
            ).fetchall()
            entry["models"] = [dict(m) for m in models]
            result.append(entry)
        return result
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
                    generation_duration_ms, hw_chip, os_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?)""",
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
                ),
            )
        conn.commit()
    finally:
        conn.close()


def query_benchmarks(db_path: str, hours: int = 0, model: str = "") -> list[dict]:
    """Query past benchmark results.

    Args:
        hours: If > 0, limit to last N hours. If 0, return all.
        model: If non-empty, filter by model name.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        query = "SELECT * FROM benchmarks WHERE 1=1"
        params: list = []

        if hours > 0:
            since = int(time.time()) - (hours * 3600)
            query += " AND ts >= ?"
            params.append(since)

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
                   (ts, engine, reachable, version, models_loaded, vram_total, url)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    ts,
                    s["name"],
                    1 if s.get("reachable") else 0,
                    s.get("version", ""),
                    len(s.get("models", [])),
                    s.get("vram_total", 0),
                    s.get("url", ""),
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


def query_compare(db_path: str, before_ts: int, after_ts: int) -> dict:
    """Compare metrics at two timestamps (nearest match)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:

        def nearest(ts: int) -> dict | None:
            row = conn.execute(
                "SELECT * FROM metrics ORDER BY ABS(ts - ?) LIMIT 1", (ts,)
            ).fetchone()
            if row:
                entry = dict(row)
                models = conn.execute(
                    "SELECT engine, name, size_vram, size_total, model_format, quantization "
                    "FROM models WHERE ts = ?",
                    (row["ts"],),
                ).fetchall()
                entry["models"] = [dict(m) for m in models]
                return entry
            return None

        return {"before": nearest(before_ts), "after": nearest(after_ts)}
    finally:
        conn.close()
