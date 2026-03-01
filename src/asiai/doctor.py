"""Diagnostic checks for asiai installation and environment.

``asiai doctor`` validates engines, system, and database health.
"""

from __future__ import annotations

import logging
import os
import platform
import sqlite3
import subprocess
import time
from dataclasses import dataclass

from asiai.collectors.system import collect_machine_info, collect_memory, collect_thermal
from asiai.engines.detect import http_get_json
from asiai.storage.db import DEFAULT_DB_PATH

logger = logging.getLogger("asiai.doctor")


@dataclass
class CheckResult:
    """Result of a single diagnostic check."""

    category: str
    name: str
    status: str  # "ok", "warn", "fail"
    message: str
    fix: str = ""


def _check_apple_silicon() -> CheckResult:
    """Verify we are running on Apple Silicon."""
    arch = platform.machine()
    if arch == "arm64":
        chip = collect_machine_info()
        return CheckResult("system", "Apple Silicon", "ok", chip)
    return CheckResult(
        "system", "Apple Silicon", "fail",
        f"Architecture: {arch} (expected arm64)",
        fix="asiai requires macOS on Apple Silicon (M1/M2/M3/M4).",
    )


def _check_ram() -> CheckResult:
    """Check total RAM >= 16 GB."""
    mem = collect_memory()
    total_gb = mem.total / (1024**3)
    if total_gb >= 16:
        pct = mem.used / mem.total * 100 if mem.total > 0 else 0
        return CheckResult(
            "system", "RAM", "ok",
            f"{total_gb:.0f} GB total, {pct:.0f}% used",
        )
    return CheckResult(
        "system", "RAM", "warn",
        f"{total_gb:.1f} GB total (16 GB recommended for LLM inference)",
    )


def _check_memory_pressure() -> CheckResult:
    """Check memory pressure level."""
    mem = collect_memory()
    if mem.pressure == "normal":
        return CheckResult("system", "Memory pressure", "ok", "normal")
    if mem.pressure == "warn":
        return CheckResult(
            "system", "Memory pressure", "warn", "warning",
            fix="Close unused applications to reduce memory pressure.",
        )
    return CheckResult(
        "system", "Memory pressure", "fail", mem.pressure,
        fix="System is under heavy memory pressure. Free up RAM.",
    )


def _check_thermal() -> CheckResult:
    """Check thermal state."""
    thermal = collect_thermal()
    if thermal.level in ("nominal", "unknown"):
        return CheckResult(
            "system", "Thermal", "ok",
            f"{thermal.level} ({thermal.speed_limit}%)",
        )
    if thermal.level == "fair":
        return CheckResult(
            "system", "Thermal", "warn",
            f"{thermal.level} ({thermal.speed_limit}%)",
        )
    return CheckResult(
        "system", "Thermal", "fail",
        f"{thermal.level} ({thermal.speed_limit}%)",
        fix="CPU is thermal throttling. Allow the machine to cool down.",
    )


def _check_ollama() -> CheckResult:
    """Check Ollama installation and reachability."""
    # Check if installed
    try:
        result = subprocess.run(
            ["which", "ollama"],
            capture_output=True, text=True, timeout=5,
        )
        installed = result.returncode == 0
    except Exception:
        installed = False

    if not installed:
        return CheckResult(
            "engine", "Ollama", "fail", "not installed",
            fix="brew install ollama",
        )

    # Check if reachable
    data, _ = http_get_json("http://localhost:11434/api/version")
    if data is None:
        return CheckResult(
            "engine", "Ollama", "warn", "installed but not running",
            fix="ollama serve",
        )

    version = data.get("version", "unknown")

    # Check if models loaded
    ps_data, _ = http_get_json("http://localhost:11434/api/ps")
    models = ps_data.get("models", []) if ps_data else []
    if models:
        names = ", ".join(m.get("name", "?") for m in models)
        msg = f"v{version} — {len(models)} model(s): {names}"
        return CheckResult("engine", "Ollama", "ok", msg)
    return CheckResult("engine", "Ollama", "ok", f"v{version} — no models loaded")


def _check_lmstudio() -> CheckResult:
    """Check LM Studio installation and reachability."""
    app_path = "/Applications/LM Studio.app"
    installed = os.path.exists(app_path)

    if not installed:
        return CheckResult(
            "engine", "LM Studio", "fail", "not installed",
            fix="brew install --cask lm-studio",
        )

    # Check if server is running
    data, headers = http_get_json("http://localhost:1234/v1/models")
    if data is None:
        return CheckResult(
            "engine", "LM Studio", "warn",
            "installed but server not running",
            fix="Open LM Studio → start local server, or: ~/.lmstudio/bin/lms server start",
        )

    version = headers.get("x-lm-studio-version", "")
    if not version:
        ver_data, _ = http_get_json("http://localhost:1234/lms/version")
        version = ver_data.get("version", "") if ver_data else ""

    models = data.get("data", [])
    if models:
        names = ", ".join(m.get("id", "?") for m in models)
        return CheckResult(
            "engine", "LM Studio", "ok",
            f"v{version} — {len(models)} model(s): {names}",
        )
    return CheckResult(
        "engine", "LM Studio", "ok",
        f"v{version} — no models loaded",
    )


def _check_mlxlm() -> CheckResult:
    """Check mlx-lm installation and reachability."""
    # Check if installed via brew
    try:
        result = subprocess.run(
            ["brew", "list", "--versions", "mlx-lm"],
            capture_output=True, text=True, timeout=10,
        )
        brew_out = result.stdout.strip()
    except Exception:
        brew_out = ""

    if not brew_out:
        return CheckResult(
            "engine", "mlx-lm", "fail", "not installed",
            fix="brew install mlx-lm",
        )

    # Parse version
    parts = brew_out.split()
    version = parts[-1] if len(parts) >= 2 else "unknown"

    # Check if server is running on port 8080
    data, _ = http_get_json("http://localhost:8080/v1/models")
    if data is None:
        return CheckResult(
            "engine", "mlx-lm", "warn",
            f"v{version} installed but server not running",
            fix="mlx_lm.server --host 0.0.0.0 --port 8080",
        )

    models = data.get("data", [])
    if models:
        names = ", ".join(m.get("id", "?") for m in models)
        return CheckResult(
            "engine", "mlx-lm", "ok",
            f"v{version} — {len(models)} model(s): {names}",
        )
    return CheckResult(
        "engine", "mlx-lm", "ok",
        f"v{version} — no models loaded",
    )


def _check_db(db_path: str = DEFAULT_DB_PATH) -> CheckResult:
    """Check database existence, integrity, and freshness."""
    if not os.path.exists(db_path):
        return CheckResult(
            "database", "SQLite", "warn",
            "database does not exist yet",
            fix="Run 'asiai monitor' to create it.",
        )

    try:
        conn = sqlite3.connect(db_path)
        try:
            # Integrity check
            result = conn.execute("PRAGMA integrity_check").fetchone()
            if result[0] != "ok":
                return CheckResult(
                    "database", "SQLite", "fail",
                    f"integrity check failed: {result[0]}",
                )

            # Size
            size = os.path.getsize(db_path)

            # Freshness: last metrics entry
            row = conn.execute(
                "SELECT MAX(ts) FROM metrics"
            ).fetchone()
            last_ts = row[0] if row and row[0] else 0
        finally:
            conn.close()
    except Exception as e:
        return CheckResult(
            "database", "SQLite", "fail",
            f"cannot open database: {e}",
        )

    # Format size
    if size < 1024:
        size_str = f"{size} B"
    elif size < 1024 * 1024:
        size_str = f"{size / 1024:.1f} KB"
    else:
        size_str = f"{size / (1024 * 1024):.1f} MB"

    if last_ts:
        age = int(time.time()) - last_ts
        if age < 3600:
            freshness = f"{age // 60}m ago"
        elif age < 86400:
            freshness = f"{age // 3600}h ago"
        else:
            freshness = f"{age // 86400}d ago"
    else:
        freshness = "no data"

    msg = f"{size_str}, last entry: {freshness}"
    status = "ok"
    if last_ts == 0:
        status = "warn"
        msg += " — run 'asiai monitor' to collect data"

    return CheckResult("database", "SQLite", status, msg)


def run_checks(db_path: str = DEFAULT_DB_PATH) -> list[CheckResult]:
    """Run all diagnostic checks and return results."""
    checks: list[CheckResult] = []

    # System checks
    checks.append(_check_apple_silicon())
    checks.append(_check_ram())
    checks.append(_check_memory_pressure())
    checks.append(_check_thermal())

    # Engine checks
    checks.append(_check_ollama())
    checks.append(_check_lmstudio())
    checks.append(_check_mlxlm())

    # Database checks
    checks.append(_check_db(db_path))

    return checks
