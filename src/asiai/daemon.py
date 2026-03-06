"""launchd daemon management for continuous monitoring.

Manages a macOS LaunchAgent that runs ``asiai monitor --quiet`` at regular intervals,
collecting system and inference metrics into SQLite.
"""

from __future__ import annotations

import logging
import os
import plistlib
import re
import shutil
import subprocess
import sys

logger = logging.getLogger("asiai.daemon")

LABEL = "com.druide67.asiai.monitor"
PLIST_DIR = os.path.expanduser("~/Library/LaunchAgents")
PLIST_PATH = os.path.join(PLIST_DIR, f"{LABEL}.plist")
DATA_DIR = os.path.expanduser("~/.local/share/asiai")
LOG_PATH = os.path.join(DATA_DIR, "daemon.stdout.log")
ERR_LOG_PATH = os.path.join(DATA_DIR, "daemon.stderr.log")


def _find_asiai_command() -> list[str]:
    """Find the best way to invoke asiai."""
    # Try shutil.which first (works when installed via pip/pipx/brew)
    path = shutil.which("asiai")
    if path:
        return [path]
    # Fallback: python -m asiai
    return [sys.executable, "-m", "asiai"]


def generate_plist(interval: int = 60) -> dict:
    """Generate a launchd plist dict for the monitoring daemon.

    Args:
        interval: Collection interval in seconds.
    """
    cmd = _find_asiai_command() + ["monitor", "--quiet"]
    return {
        "Label": LABEL,
        "ProgramArguments": cmd,
        "StartInterval": interval,
        "StandardOutPath": LOG_PATH,
        "StandardErrorPath": ERR_LOG_PATH,
        "RunAtLoad": True,
        "KeepAlive": False,
    }


def daemon_start(interval: int = 60) -> dict:
    """Install and load the launchd daemon.

    Returns:
        {"status": "started", "plist": path, "interval": seconds}
        or {"status": "error", "message": str}
    """
    try:
        # Ensure directories exist
        os.makedirs(PLIST_DIR, exist_ok=True)
        os.makedirs(DATA_DIR, exist_ok=True)

        # Stop existing daemon if running
        status = daemon_status()
        if status.get("running"):
            daemon_stop()

        # Write plist
        plist = generate_plist(interval)
        with open(PLIST_PATH, "wb") as f:
            plistlib.dump(plist, f)

        # Load via launchctl
        result = subprocess.run(
            ["launchctl", "load", PLIST_PATH],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {"status": "error", "message": result.stderr.strip()}

        return {"status": "started", "plist": PLIST_PATH, "interval": interval}
    except (OSError, subprocess.SubprocessError, plistlib.InvalidFileException) as e:
        return {"status": "error", "message": str(e)}


def daemon_stop() -> dict:
    """Unload and remove the launchd daemon.

    Returns:
        {"status": "stopped"} or {"status": "error", "message": str}
    """
    try:
        if os.path.exists(PLIST_PATH):
            subprocess.run(
                ["launchctl", "unload", PLIST_PATH],
                capture_output=True,
                text=True,
                timeout=10,
            )
            os.remove(PLIST_PATH)
        return {"status": "stopped"}
    except (OSError, subprocess.SubprocessError) as e:
        return {"status": "error", "message": str(e)}


def daemon_status() -> dict:
    """Check if the daemon is running.

    Returns:
        {"running": bool, "pid": int|None, "plist_exists": bool}
    """
    plist_exists = os.path.exists(PLIST_PATH)

    try:
        result = subprocess.run(
            ["launchctl", "list", LABEL],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # Parse PID from output
            pid = None
            m = re.search(r'"PID"\s*=\s*(\d+)', result.stdout)
            if m:
                pid = int(m.group(1))
            return {"running": True, "pid": pid, "plist_exists": plist_exists}
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("launchctl list failed: %s", e)

    return {"running": False, "pid": None, "plist_exists": plist_exists}


def daemon_logs(lines: int = 50) -> str:
    """Return the last N lines of the daemon log.

    Returns the log content as a string, or an error message.
    """
    if not os.path.exists(LOG_PATH):
        return f"No log file found at {LOG_PATH}"

    try:
        result = subprocess.run(
            ["tail", "-n", str(lines), LOG_PATH],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout
    except (OSError, subprocess.SubprocessError) as e:
        return f"Error reading logs: {e}"
