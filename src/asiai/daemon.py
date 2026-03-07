"""launchd service management for asiai.

Manages macOS LaunchAgents for two services:

- **monitor**: runs ``asiai monitor --quiet`` at regular intervals (periodic)
- **web**: runs ``asiai web --no-open`` as a long-running process (persistent)
"""

from __future__ import annotations

import logging
import os
import plistlib
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass

logger = logging.getLogger("asiai.daemon")

PLIST_DIR = os.path.expanduser("~/Library/LaunchAgents")
DATA_DIR = os.path.expanduser("~/.local/share/asiai")


@dataclass
class ServiceProfile:
    """Configuration for a launchd-managed service."""

    name: str
    label: str
    description: str
    plist_path: str
    log_path: str
    err_log_path: str


SERVICES: dict[str, ServiceProfile] = {
    "monitor": ServiceProfile(
        name="monitor",
        label="com.druide67.asiai.monitor",
        description="Monitoring daemon",
        plist_path=os.path.join(PLIST_DIR, "com.druide67.asiai.monitor.plist"),
        log_path=os.path.join(DATA_DIR, "daemon.stdout.log"),
        err_log_path=os.path.join(DATA_DIR, "daemon.stderr.log"),
    ),
    "web": ServiceProfile(
        name="web",
        label="com.druide67.asiai.web",
        description="Web dashboard",
        plist_path=os.path.join(PLIST_DIR, "com.druide67.asiai.web.plist"),
        log_path=os.path.join(DATA_DIR, "web.stdout.log"),
        err_log_path=os.path.join(DATA_DIR, "web.stderr.log"),
    ),
}

# Backward-compatibility aliases (monitor profile)
LABEL = SERVICES["monitor"].label
PLIST_PATH = SERVICES["monitor"].plist_path
LOG_PATH = SERVICES["monitor"].log_path
ERR_LOG_PATH = SERVICES["monitor"].err_log_path


def _find_asiai_command() -> list[str]:
    """Find the best way to invoke asiai."""
    # Try shutil.which first (works when installed via pip/pipx/brew)
    path = shutil.which("asiai")
    if path:
        return [path]
    # Fallback: python -m asiai
    return [sys.executable, "-m", "asiai"]


def generate_plist(service: str = "monitor", **kwargs: int | str) -> dict:
    """Generate a launchd plist dict for the given service.

    Args:
        service: Service name ("monitor" or "web").
        **kwargs: Service-specific options.
            monitor: interval (int, default 60)
            web: port (int, default 8899), host (str, default "127.0.0.1")
    """
    if service not in SERVICES:
        raise ValueError(f"Unknown service: {service}")

    profile = SERVICES[service]
    cmd = _find_asiai_command()

    if service == "monitor":
        interval = int(kwargs.get("interval", 60))
        cmd += ["monitor", "--quiet"]
        webhook_url = kwargs.get("webhook_url")
        if webhook_url:
            cmd += ["--alert-webhook", str(webhook_url)]
        return {
            "Label": profile.label,
            "ProgramArguments": cmd,
            "StartInterval": interval,
            "StandardOutPath": profile.log_path,
            "StandardErrorPath": profile.err_log_path,
            "RunAtLoad": True,
            "KeepAlive": False,
        }

    # service == "web"
    port = str(kwargs.get("port", 8899))
    host = str(kwargs.get("host", "127.0.0.1"))
    cmd += ["web", "--no-open", "--port", port, "--host", host]
    return {
        "Label": profile.label,
        "ProgramArguments": cmd,
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "StandardOutPath": profile.log_path,
        "StandardErrorPath": profile.err_log_path,
    }


def daemon_start(service: str = "monitor", **kwargs: int | str) -> dict:
    """Install and load a launchd service.

    Returns:
        {"status": "started", "plist": path, ...}
        or {"status": "error", "message": str}
    """
    if service not in SERVICES:
        return {"status": "error", "message": f"Unknown service: {service}"}

    profile = SERVICES[service]
    try:
        os.makedirs(PLIST_DIR, exist_ok=True)
        os.makedirs(DATA_DIR, exist_ok=True)

        # Stop existing if running
        status = daemon_status(service)
        if status.get("running"):
            daemon_stop(service)

        plist = generate_plist(service, **kwargs)
        with open(profile.plist_path, "wb") as f:
            plistlib.dump(plist, f)

        result = subprocess.run(
            ["launchctl", "load", profile.plist_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {"status": "error", "message": result.stderr.strip()}

        info: dict = {"status": "started", "plist": profile.plist_path}
        if service == "monitor":
            info["interval"] = int(kwargs.get("interval", 60))
        elif service == "web":
            info["port"] = int(kwargs.get("port", 8899))
            info["host"] = str(kwargs.get("host", "127.0.0.1"))
        return info
    except (OSError, subprocess.SubprocessError, plistlib.InvalidFileException) as e:
        return {"status": "error", "message": str(e)}


def daemon_stop(service: str = "monitor") -> dict:
    """Unload and remove a launchd service.

    Returns:
        {"status": "stopped", "service": name} or {"status": "error", "message": str}
    """
    if service not in SERVICES:
        return {"status": "error", "message": f"Unknown service: {service}"}

    profile = SERVICES[service]
    try:
        if os.path.exists(profile.plist_path):
            subprocess.run(
                ["launchctl", "unload", profile.plist_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            os.remove(profile.plist_path)
        return {"status": "stopped", "service": service}
    except (OSError, subprocess.SubprocessError) as e:
        return {"status": "error", "message": str(e)}


def daemon_stop_all() -> dict[str, dict]:
    """Stop all registered services."""
    return {name: daemon_stop(name) for name in SERVICES}


def daemon_status(service: str = "monitor") -> dict:
    """Check if a service is running.

    Returns:
        {"running": bool, "pid": int|None, "plist_exists": bool}
    """
    if service not in SERVICES:
        return {"running": False, "pid": None, "plist_exists": False}

    profile = SERVICES[service]
    plist_exists = os.path.exists(profile.plist_path)

    try:
        result = subprocess.run(
            ["launchctl", "list", profile.label],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            pid = None
            m = re.search(r'"PID"\s*=\s*(\d+)', result.stdout)
            if m:
                pid = int(m.group(1))
            return {"running": True, "pid": pid, "plist_exists": plist_exists}
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("launchctl list failed: %s", e)

    return {"running": False, "pid": None, "plist_exists": plist_exists}


def daemon_status_all() -> dict[str, dict]:
    """Check status of all registered services."""
    return {name: daemon_status(name) for name in SERVICES}


def daemon_logs(service: str = "monitor", lines: int = 50) -> str:
    """Return the last N lines of a service log.

    Returns the log content as a string, or an error message.
    """
    if service not in SERVICES:
        return f"Unknown service: {service}"

    profile = SERVICES[service]
    if not os.path.exists(profile.log_path):
        return f"No log file found at {profile.log_path}"

    try:
        result = subprocess.run(
            ["tail", "-n", str(lines), profile.log_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout
    except (OSError, subprocess.SubprocessError) as e:
        return f"Error reading logs: {e}"


def _read_plist_config(service: str) -> dict:
    """Read configuration from an installed plist.

    Returns extracted config (port, host, interval) or empty dict.
    """
    if service not in SERVICES:
        return {}

    profile = SERVICES[service]
    if not os.path.exists(profile.plist_path):
        return {}

    try:
        with open(profile.plist_path, "rb") as f:
            plist = plistlib.load(f)
    except (OSError, plistlib.InvalidFileException):
        return {}

    args = plist.get("ProgramArguments", [])
    config: dict = {}

    if service == "web":
        for i, arg in enumerate(args):
            if arg == "--port" and i + 1 < len(args):
                config["port"] = int(args[i + 1])
            if arg == "--host" and i + 1 < len(args):
                config["host"] = args[i + 1]
    elif service == "monitor":
        config["interval"] = plist.get("StartInterval", 60)
        for i, arg in enumerate(args):
            if arg == "--alert-webhook" and i + 1 < len(args):
                config["webhook_url"] = args[i + 1]

    return config
