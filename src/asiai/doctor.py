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
from asiai.engines.config import load_config
from asiai.engines.detect import _lmstudio_version_from_app, http_get_json
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
        "system",
        "Apple Silicon",
        "fail",
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
            "system",
            "RAM",
            "ok",
            f"{total_gb:.0f} GB total, {pct:.0f}% used",
        )
    return CheckResult(
        "system",
        "RAM",
        "warn",
        f"{total_gb:.1f} GB total (16 GB recommended for LLM inference)",
    )


def _check_memory_pressure() -> CheckResult:
    """Check memory pressure level."""
    mem = collect_memory()
    if mem.pressure == "normal":
        return CheckResult("system", "Memory pressure", "ok", "normal")
    if mem.pressure == "warn":
        return CheckResult(
            "system",
            "Memory pressure",
            "warn",
            "warning",
            fix="Close unused applications to reduce memory pressure.",
        )
    return CheckResult(
        "system",
        "Memory pressure",
        "fail",
        mem.pressure,
        fix="System is under heavy memory pressure. Free up RAM.",
    )


def _check_thermal() -> CheckResult:
    """Check thermal state."""
    thermal = collect_thermal()
    if thermal.level in ("nominal", "unknown"):
        return CheckResult(
            "system",
            "Thermal",
            "ok",
            f"{thermal.level} ({thermal.speed_limit}%)",
        )
    if thermal.level == "fair":
        return CheckResult(
            "system",
            "Thermal",
            "warn",
            f"{thermal.level} ({thermal.speed_limit}%)",
        )
    return CheckResult(
        "system",
        "Thermal",
        "fail",
        f"{thermal.level} ({thermal.speed_limit}%)",
        fix="CPU is thermal throttling. Allow the machine to cool down.",
    )


def _get_engine_urls(engine_name: str, default_url: str) -> list[str]:
    """Get URLs for an engine: config URLs first, then the default."""
    config = load_config()
    urls = []
    for entry in config.get("engines", []):
        if entry.get("engine") == engine_name:
            urls.append(entry["url"])
    if default_url not in urls:
        urls.append(default_url)
    return urls


def _check_ollama() -> CheckResult:
    """Check Ollama installation and reachability."""
    # Check if installed (binary in PATH)
    try:
        result = subprocess.run(
            ["which", "ollama"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        installed = result.returncode == 0
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("Ollama 'which' check failed: %s", e)
        installed = False

    # Check if reachable on any known port
    urls = _get_engine_urls("ollama", "http://localhost:11434")
    data = None
    reachable_url = ""
    for url in urls:
        data, _ = http_get_json(f"{url}/api/version")
        if data is not None:
            reachable_url = url
            break

    # Binary OR port: either one means it's available
    if not installed and data is None:
        return CheckResult(
            "engine",
            "Ollama",
            "fail",
            "not installed",
            fix="brew install ollama",
        )

    if data is None:
        return CheckResult(
            "engine",
            "Ollama",
            "warn",
            "installed but not running",
            fix="ollama serve",
        )

    version = data.get("version", "unknown")

    # Check if models loaded
    ps_data, _ = http_get_json(f"{reachable_url}/api/ps")
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

    # Check if server is running on any known port
    urls = _get_engine_urls("lmstudio", "http://localhost:1234")
    data = None
    headers = {}
    reachable_url = ""
    for url in urls:
        data, headers = http_get_json(f"{url}/v1/models")
        if data is not None:
            reachable_url = url
            break

    if data is None:
        if not installed:
            return CheckResult(
                "engine",
                "LM Studio",
                "fail",
                "not installed",
                fix="brew install --cask lm-studio",
            )
        return CheckResult(
            "engine",
            "LM Studio",
            "warn",
            "installed but server not running",
            fix="Open LM Studio → start local server, or: ~/.lmstudio/bin/lms server start",
        )

    version = headers.get("x-lm-studio-version", "")
    if not version:
        ver_data, _ = http_get_json(f"{reachable_url}/lms/version")
        if ver_data and isinstance(ver_data, dict) and "version" in ver_data:
            version = ver_data["version"]
    if not version:
        version = _lmstudio_version_from_app()

    models = data.get("data", [])
    if models:
        names = ", ".join(m.get("id", "?") for m in models)
        return CheckResult(
            "engine",
            "LM Studio",
            "ok",
            f"v{version} — {len(models)} model(s): {names}",
        )
    return CheckResult(
        "engine",
        "LM Studio",
        "ok",
        f"v{version} — no models loaded",
    )


def _check_mlxlm() -> CheckResult:
    """Check mlx-lm installation and reachability."""
    # Check if installed via brew
    try:
        result = subprocess.run(
            ["brew", "list", "--versions", "mlx-lm"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        brew_out = result.stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("mlx-lm brew check failed: %s", e)
        brew_out = ""

    # Parse version
    parts = brew_out.split() if brew_out else []
    version = parts[-1] if len(parts) >= 2 else ""
    installed = bool(brew_out)

    # Check if server is running on any known port
    urls = _get_engine_urls("mlxlm", "http://localhost:8080")
    data = None
    for url in urls:
        data, _ = http_get_json(f"{url}/v1/models")
        if data is not None:
            break

    if not installed and data is None:
        return CheckResult(
            "engine",
            "mlx-lm",
            "fail",
            "not installed",
            fix="brew install mlx-lm",
        )

    if data is None:
        return CheckResult(
            "engine",
            "mlx-lm",
            "warn",
            f"v{version} installed but not running" if version else "installed but not running",
            fix="mlx_lm.server --host 0.0.0.0 --port 8080",
        )

    models = data.get("data", [])
    if models:
        names = ", ".join(m.get("id", "?") for m in models)
        return CheckResult(
            "engine",
            "mlx-lm",
            "ok",
            f"v{version} — {len(models)} model(s): {names}",
        )
    return CheckResult(
        "engine",
        "mlx-lm",
        "ok",
        f"v{version} — no models loaded",
    )


def _check_llamacpp() -> CheckResult:
    """Check llama.cpp installation and reachability."""
    # Check if installed via brew
    try:
        result = subprocess.run(
            ["brew", "list", "--versions", "llama.cpp"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        brew_out = result.stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("llama.cpp brew check failed: %s", e)
        brew_out = ""

    parts = brew_out.split() if brew_out else []
    version = parts[-1] if len(parts) >= 2 else ""
    installed = bool(brew_out)

    # Check if server is running on any known port
    urls = _get_engine_urls("llamacpp", "http://localhost:8080")
    data = None
    reachable_url = ""
    for url in urls:
        data, _ = http_get_json(f"{url}/health")
        if data is not None and data.get("status") == "ok":
            reachable_url = url
            break
        data = None  # reset if health not ok

    if not installed and data is None:
        return CheckResult(
            "engine",
            "llama.cpp",
            "fail",
            "not installed",
            fix="brew install llama.cpp",
        )

    if data is None:
        return CheckResult(
            "engine",
            "llama.cpp",
            "warn",
            f"v{version} installed but not running" if version else "installed but not running",
            fix="llama-server -m model.gguf --port 8080",
        )

    # Get model info via /v1/models
    models_data, _ = http_get_json(f"{reachable_url}/v1/models")
    models = models_data.get("data", []) if models_data else []
    if models:
        names = ", ".join(m.get("id", "?") for m in models)
        return CheckResult(
            "engine",
            "llama.cpp",
            "ok",
            f"v{version} — {len(models)} model(s): {names}",
        )
    return CheckResult(
        "engine",
        "llama.cpp",
        "ok",
        f"v{version} — server running",
    )


def _check_vllm_mlx() -> CheckResult:
    """Check vllm-mlx installation and reachability."""
    # Check if installed via pip
    try:
        result = subprocess.run(
            ["pip", "show", "vllm-mlx"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        pip_out = result.stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("vllm-mlx pip check failed: %s", e)
        pip_out = ""

    version = ""
    if pip_out:
        for line in pip_out.splitlines():
            if line.startswith("Version:"):
                version = line.split(":", 1)[1].strip()
                break

    installed = bool(version)

    # Check if server is running on any known port
    urls = _get_engine_urls("vllm_mlx", "http://localhost:8000")
    data = None
    reachable_url = ""
    for url in urls:
        data, _ = http_get_json(f"{url}/version")
        if data is not None:
            reachable_url = url
            break

    if not installed and data is None:
        return CheckResult(
            "engine",
            "vllm-mlx",
            "fail",
            "not installed",
            fix="pip install vllm-mlx",
        )

    if data is None:
        return CheckResult(
            "engine",
            "vllm-mlx",
            "warn",
            f"v{version} installed but not running" if version else "installed but not running",
            fix="vllm serve <model> --port 8000",
        )

    server_version = data.get("version", version)
    models_data, _ = http_get_json(f"{reachable_url}/v1/models")
    models = models_data.get("data", []) if models_data else []
    if models:
        names = ", ".join(m.get("id", "?") for m in models)
        return CheckResult(
            "engine",
            "vllm-mlx",
            "ok",
            f"v{server_version} — {len(models)} model(s): {names}",
        )
    return CheckResult(
        "engine",
        "vllm-mlx",
        "ok",
        f"v{server_version} — server running",
    )


def _check_omlx() -> CheckResult:
    """Check oMLX installation and reachability."""
    # Check if installed via which or .app
    installed = False
    try:
        result = subprocess.run(
            ["which", "omlx"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        installed = result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        pass

    if not installed:
        if os.path.exists("/Applications/oMLX.app"):
            installed = True

    # Check if reachable on any known port (config + default)
    urls = _get_engine_urls("omlx", "http://localhost:8000")
    data = None
    reachable_url = ""
    for url in urls:
        data, _ = http_get_json(f"{url}/v1/models")
        if data is not None:
            reachable_url = url
            break

    # Binary OR port
    if not installed and data is None:
        return CheckResult(
            "engine",
            "oMLX",
            "fail",
            "not installed",
            fix="brew tap jundot/omlx && brew install omlx",
        )

    if data is None:
        return CheckResult(
            "engine",
            "oMLX",
            "warn",
            "installed but server not running",
            fix="open /Applications/oMLX.app",
        )

    port_info = ""
    if reachable_url and reachable_url != "http://localhost:8000":
        port_info = f" (port {reachable_url.rsplit(':', 1)[-1]})"

    models = data.get("data", [])
    if models:
        names = ", ".join(m.get("id", "?") for m in models)
        return CheckResult(
            "engine",
            "oMLX",
            "ok",
            f"{len(models)} model(s): {names}{port_info}",
        )
    return CheckResult("engine", "oMLX", "ok", f"running — no models loaded{port_info}")


def _check_exo() -> CheckResult:
    """Check Exo installation and reachability."""
    # Check if installed
    try:
        result = subprocess.run(
            ["which", "exo"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        installed = result.returncode == 0
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("Exo 'which' check failed: %s", e)
        installed = False

    # Check if reachable on any known port
    urls = _get_engine_urls("exo", "http://localhost:52415")
    data = None
    for url in urls:
        data, _ = http_get_json(f"{url}/v1/models")
        if data is not None:
            break

    if not installed and data is None:
        return CheckResult(
            "engine",
            "Exo",
            "fail",
            "not installed",
            fix="pip install exo-inference",
        )

    if data is None:
        return CheckResult(
            "engine",
            "Exo",
            "warn",
            "installed but not running",
            fix="exo",
        )

    models = data.get("data", [])
    if models:
        names = ", ".join(m.get("id", "?") for m in models)
        return CheckResult("engine", "Exo", "ok", f"{len(models)} model(s): {names}")
    return CheckResult("engine", "Exo", "ok", "running — no models loaded")


def _check_db(db_path: str = DEFAULT_DB_PATH) -> CheckResult:
    """Check database existence, integrity, and freshness."""
    if not os.path.exists(db_path):
        return CheckResult(
            "database",
            "SQLite",
            "warn",
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
                    "database",
                    "SQLite",
                    "fail",
                    f"integrity check failed: {result[0]}",
                )

            # Size
            size = os.path.getsize(db_path)

            # Freshness: last metrics entry
            row = conn.execute("SELECT MAX(ts) FROM metrics").fetchone()
            last_ts = row[0] if row and row[0] else 0
        finally:
            conn.close()
    except (sqlite3.Error, OSError) as e:
        return CheckResult(
            "database",
            "SQLite",
            "fail",
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


def _check_daemon() -> list[CheckResult]:
    """Check LaunchAgent status for all services."""
    from asiai.daemon import SERVICES, daemon_status

    results = []
    for name, profile in SERVICES.items():
        status = daemon_status(name)
        if status["running"]:
            pid_str = f" PID {status['pid']}" if status["pid"] else ""
            results.append(
                CheckResult(
                    "daemon",
                    profile.description,
                    "ok",
                    f"running{pid_str}",
                )
            )
        elif status["plist_exists"]:
            results.append(
                CheckResult(
                    "daemon",
                    profile.description,
                    "warn",
                    "plist installed but not running",
                    fix=f"asiai daemon start {name}",
                )
            )
        else:
            results.append(
                CheckResult(
                    "daemon",
                    profile.description,
                    "ok",
                    "not installed",
                )
            )
    return results


_OLLAMA_PARAMS: dict[str, str] = {
    "OLLAMA_HOST": "127.0.0.1:11434",
    "OLLAMA_NUM_PARALLEL": "1",
    "OLLAMA_MAX_LOADED_MODELS": "auto",
    "OLLAMA_KEEP_ALIVE": "5m",
    "OLLAMA_FLASH_ATTENTION": "0",
}


def _check_ollama_config() -> list[CheckResult]:
    """Report key Ollama runtime parameters from the running process."""
    results: list[CheckResult] = []

    # Find Ollama PID via port
    try:
        lsof = subprocess.run(
            ["lsof", "-ti", ":11434"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        pid = lsof.stdout.strip().splitlines()[0] if lsof.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError, IndexError):
        pid = ""

    if not pid:
        return results

    # Read env vars from running process
    try:
        ps = subprocess.run(
            ["ps", "eww", "-p", pid],
            capture_output=True,
            text=True,
            timeout=5,
        )
        env_line = ps.stdout if ps.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        env_line = ""

    # Parse OLLAMA_* vars
    env_vars: dict[str, str] = {}
    for token in env_line.split():
        if token.startswith("OLLAMA_") and "=" in token:
            k, _, v = token.partition("=")
            env_vars[k] = v

    # Report each key param
    parts = []
    for key, default in _OLLAMA_PARAMS.items():
        val = env_vars.get(key, default)
        short = key.replace("OLLAMA_", "").lower()
        if val != default:
            parts.append(f"{short}={val}")
        else:
            parts.append(f"{short}={val} (default)")

    results.append(CheckResult("engine", "Ollama config", "ok", ", ".join(parts)))
    return results


def _check_alerting() -> list[CheckResult]:
    """Check alerting webhook configuration."""
    from asiai.daemon import _read_plist_config

    results = []
    config = _read_plist_config("monitor")
    webhook_url = config.get("webhook_url")

    if not webhook_url:
        results.append(
            CheckResult(
                "alerting",
                "Webhook",
                "ok",
                "not configured",
                fix="asiai daemon start monitor --alert-webhook URL",
            )
        )
        return results

    results.append(CheckResult("alerting", "Webhook URL", "ok", webhook_url))

    # Test connectivity
    try:
        import urllib.request

        req = urllib.request.Request(webhook_url, method="HEAD")
        with urllib.request.urlopen(req, timeout=5) as resp:
            results.append(
                CheckResult("alerting", "Webhook reachable", "ok", f"HTTP {resp.status}")
            )
    except Exception as e:
        results.append(
            CheckResult(
                "alerting",
                "Webhook reachable",
                "warn",
                str(e),
                fix="Check webhook URL and network connectivity.",
            )
        )

    return results


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
    checks.extend(_check_ollama_config())
    checks.append(_check_lmstudio())
    checks.append(_check_mlxlm())
    checks.append(_check_llamacpp())
    checks.append(_check_vllm_mlx())
    checks.append(_check_omlx())
    checks.append(_check_exo())

    # Database checks
    checks.append(_check_db(db_path))

    # Daemon checks
    checks.extend(_check_daemon())

    # Alerting checks
    checks.extend(_check_alerting())

    return checks
