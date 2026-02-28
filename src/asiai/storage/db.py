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
                for row in conn.execute(
                    f"PRAGMA table_info({migration['table']})"
                ).fetchall()
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
                snap["cpu_load_1"], snap["cpu_load_5"], snap["cpu_load_15"],
                snap["mem_total"], snap["mem_used"], snap["mem_pressure"],
                snap["thermal_level"], snap["thermal_speed_limit"],
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
        rows = conn.execute(
            "SELECT * FROM metrics WHERE ts >= ? ORDER BY ts", (since,)
        ).fetchall()
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
