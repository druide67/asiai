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

CREATE TABLE IF NOT EXISTS benchmarks (
    ts INTEGER NOT NULL,
    engine TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_type TEXT NOT NULL,
    tokens_generated INTEGER,
    tok_per_sec REAL,
    ttft_ms REAL,
    total_duration_ms REAL,
    vram_bytes INTEGER,
    mem_used INTEGER,
    thermal_level TEXT,
    thermal_speed_limit INTEGER
);

CREATE INDEX IF NOT EXISTS idx_benchmarks_ts ON benchmarks(ts);
CREATE INDEX IF NOT EXISTS idx_benchmarks_model ON benchmarks(model);
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
    # v0.3: multi-run benchmark variance
    {
        "table": "benchmarks",
        "columns": ["run_index"],
        "sql": [
            "ALTER TABLE benchmarks ADD COLUMN run_index INTEGER DEFAULT 0",
        ],
    },
    # v0.3: power metrics (tok/s per watt)
    {
        "table": "benchmarks",
        "columns": ["power_watts", "tok_per_sec_per_watt"],
        "sql": [
            "ALTER TABLE benchmarks ADD COLUMN power_watts REAL DEFAULT 0",
            "ALTER TABLE benchmarks ADD COLUMN tok_per_sec_per_watt REAL DEFAULT 0",
        ],
    },
    # v0.3: model load time
    {
        "table": "benchmarks",
        "columns": ["load_time_ms"],
        "sql": [
            "ALTER TABLE benchmarks ADD COLUMN load_time_ms REAL DEFAULT 0",
        ],
    },
]
