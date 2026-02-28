"""SQLite schema definitions and migrations."""

from __future__ import annotations

RETENTION_DAYS = 90

SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS metrics (
    ts INTEGER PRIMARY KEY,
    cpu_load_1 REAL,
    cpu_load_5 REAL,
    cpu_load_15 REAL,
    mem_total INTEGER,
    mem_used INTEGER,
    mem_pressure TEXT,
    thermal_level TEXT,
    thermal_speed_limit INTEGER,
    uptime INTEGER,
    inference_engine TEXT,
    engine_version TEXT
);

CREATE TABLE IF NOT EXISTS models (
    ts INTEGER,
    engine TEXT,
    name TEXT,
    size_vram INTEGER,
    size_total INTEGER,
    model_format TEXT,
    quantization TEXT,
    FOREIGN KEY(ts) REFERENCES metrics(ts)
);

CREATE INDEX IF NOT EXISTS idx_models_ts ON models(ts);
"""

# Migrations from earlier schema versions.
MIGRATIONS = [
    # v1.1: engine columns on metrics (from openclaw health agent)
    {
        "table": "metrics",
        "columns": ["inference_engine", "engine_version"],
        "sql": [
            "ALTER TABLE metrics ADD COLUMN inference_engine TEXT",
            "ALTER TABLE metrics ADD COLUMN engine_version TEXT",
        ],
    },
    # v1.1: format/quantization on models
    {
        "table": "models",
        "columns": ["model_format", "quantization"],
        "sql": [
            "ALTER TABLE models ADD COLUMN model_format TEXT",
            "ALTER TABLE models ADD COLUMN quantization TEXT",
        ],
    },
    # Rename: ollama_models -> models (if upgrading from openclaw DB)
    {
        "table": "models",
        "columns": ["engine"],
        "sql": [
            "ALTER TABLE models ADD COLUMN engine TEXT",
        ],
    },
]
