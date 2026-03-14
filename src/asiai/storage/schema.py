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
    engine_version TEXT,
    gpu_utilization_pct REAL DEFAULT -1,
    gpu_renderer_pct REAL DEFAULT -1,
    gpu_tiler_pct REAL DEFAULT -1,
    gpu_mem_in_use INTEGER DEFAULT 0,
    gpu_mem_allocated INTEGER DEFAULT 0
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

CREATE TABLE IF NOT EXISTS engine_status (
    ts INTEGER NOT NULL,
    engine TEXT NOT NULL,
    reachable INTEGER NOT NULL DEFAULT 0,
    version TEXT DEFAULT '',
    models_loaded INTEGER DEFAULT 0,
    vram_total INTEGER DEFAULT 0,
    url TEXT DEFAULT '',
    tcp_connections INTEGER DEFAULT 0,
    requests_processing INTEGER DEFAULT 0,
    tokens_predicted_total INTEGER DEFAULT 0,
    kv_cache_usage_ratio REAL DEFAULT -1
);

CREATE INDEX IF NOT EXISTS idx_engine_status_ts ON engine_status(ts);
CREATE INDEX IF NOT EXISTS idx_engine_status_engine ON engine_status(engine);

CREATE TABLE IF NOT EXISTS benchmark_process (
    ts INTEGER NOT NULL,
    engine TEXT NOT NULL,
    run_index INTEGER DEFAULT 0,
    proc_cpu_pct REAL DEFAULT 0,
    proc_mem_pct REAL DEFAULT 0,
    proc_rss_bytes INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_bench_proc_ts ON benchmark_process(ts);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    details TEXT,
    webhook_sent INTEGER DEFAULT 0,
    webhook_status INTEGER
);

CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(ts);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);

CREATE TABLE IF NOT EXISTS community_submissions (
    id TEXT PRIMARY KEY,
    ts INTEGER NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    response_status INTEGER,
    error TEXT DEFAULT '',
    payload_hash TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_community_ts ON community_submissions(ts);
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
    # v0.3.1: metrics version for regression comparison
    {
        "table": "benchmarks",
        "columns": ["metrics_version"],
        "sql": [
            "ALTER TABLE benchmarks ADD COLUMN metrics_version INTEGER DEFAULT 1",
        ],
    },
    # v0.3.2: benchmark metadata for reproducibility
    {
        "table": "benchmarks",
        "columns": [
            "engine_version",
            "model_format",
            "model_quantization",
            "generation_duration_ms",
            "hw_chip",
            "os_version",
        ],
        "sql": [
            "ALTER TABLE benchmarks ADD COLUMN engine_version TEXT DEFAULT ''",
            "ALTER TABLE benchmarks ADD COLUMN model_format TEXT DEFAULT ''",
            "ALTER TABLE benchmarks ADD COLUMN model_quantization TEXT DEFAULT ''",
            "ALTER TABLE benchmarks ADD COLUMN generation_duration_ms REAL DEFAULT 0",
            "ALTER TABLE benchmarks ADD COLUMN hw_chip TEXT DEFAULT ''",
            "ALTER TABLE benchmarks ADD COLUMN os_version TEXT DEFAULT ''",
        ],
    },
    # v0.5: engine_status table (created in SCHEMA_SQL, migration is a no-op marker)
    {
        "table": "engine_status",
        "columns": ["ts"],
        "sql": [],
    },
    # v1.0: GPU utilization on metrics
    {
        "table": "metrics",
        "columns": [
            "gpu_utilization_pct",
            "gpu_renderer_pct",
            "gpu_tiler_pct",
            "gpu_mem_in_use",
            "gpu_mem_allocated",
        ],
        "sql": [
            "ALTER TABLE metrics ADD COLUMN gpu_utilization_pct REAL DEFAULT -1",
            "ALTER TABLE metrics ADD COLUMN gpu_renderer_pct REAL DEFAULT -1",
            "ALTER TABLE metrics ADD COLUMN gpu_tiler_pct REAL DEFAULT -1",
            "ALTER TABLE metrics ADD COLUMN gpu_mem_in_use INTEGER DEFAULT 0",
            "ALTER TABLE metrics ADD COLUMN gpu_mem_allocated INTEGER DEFAULT 0",
        ],
    },
    # v1.0: inference activity on engine_status
    {
        "table": "engine_status",
        "columns": [
            "tcp_connections",
            "requests_processing",
            "tokens_predicted_total",
            "kv_cache_usage_ratio",
        ],
        "sql": [
            "ALTER TABLE engine_status ADD COLUMN tcp_connections INTEGER DEFAULT 0",
            "ALTER TABLE engine_status ADD COLUMN requests_processing INTEGER DEFAULT 0",
            "ALTER TABLE engine_status ADD COLUMN tokens_predicted_total INTEGER DEFAULT 0",
            "ALTER TABLE engine_status ADD COLUMN kv_cache_usage_ratio REAL DEFAULT -1",
        ],
    },
    # v1.1: benchmark context & hardware identity
    {
        "table": "benchmarks",
        "columns": ["context_size", "gpu_cores", "ram_gb"],
        "sql": [
            "ALTER TABLE benchmarks ADD COLUMN context_size INTEGER DEFAULT 0",
            "ALTER TABLE benchmarks ADD COLUMN gpu_cores INTEGER DEFAULT 0",
            "ALTER TABLE benchmarks ADD COLUMN ram_gb INTEGER DEFAULT 0",
        ],
    },
    # v1.2: benchmark process metrics (separate table, 7d retention)
    {
        "table": "benchmark_process",
        "columns": ["ts"],
        "sql": [],
    },
]
