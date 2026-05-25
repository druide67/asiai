"""Append-only JSONL audit log for fleet write commands.

Stored at ``~/.local/share/asiai/fleet-audit.jsonl`` (0o600). One JSON
object per line; rotated at ``ROTATE_BYTES`` by renaming the current
file to ``<path>.1`` (old .1 is overwritten).

Best-effort: write failures are logged and swallowed so a full disk
never breaks an auth path.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import logging
import os
import threading
import time
from typing import Any

logger = logging.getLogger("asiai.auth.audit")

AUDIT_DIR = os.path.expanduser("~/.local/share/asiai")
AUDIT_PATH = os.path.join(AUDIT_DIR, "fleet-audit.jsonl")
ROTATE_BYTES = 10 * 1024 * 1024  # 10 MB

_lock = threading.Lock()


def _ensure_dir() -> None:
    os.makedirs(AUDIT_DIR, exist_ok=True)


def _rotate_if_needed() -> None:
    """Rename to ``.1`` once the file exceeds ROTATE_BYTES.

    Single backup only; older lines are discarded on the next rotation.
    For long-term audit, ship the file off-host (rsyslog, fluent-bit, ...).
    """
    try:
        size = os.path.getsize(AUDIT_PATH)
    except OSError:
        return
    if size < ROTATE_BYTES:
        return
    backup = AUDIT_PATH + ".1"
    try:
        if os.path.exists(backup):
            os.unlink(backup)
        os.rename(AUDIT_PATH, backup)
    except OSError as e:
        logger.warning("Audit log rotation failed: %s", e)


def log_event(**fields: Any) -> None:
    """Append one audit event. Never raises.

    Standard fields the caller should provide for write commands:
        - source_ip (str): peer IP that sent the request
        - token_id (str | None): which token authenticated (None if rejected)
        - nickname (str): fleet node nickname (or "<self>")
        - command (str): e.g. "purge", "stop", "restart"
        - args (dict): command arguments (no secrets — caller strips them)
        - status (str): "ok" | "denied" | "error"
        - http_status (int): HTTP status returned
        - duration_ms (int): wall time for the command
        - error (str | None): error message if any
    """
    record = {"ts": int(time.time()), **fields}
    try:
        with _lock:
            _ensure_dir()
            _rotate_if_needed()
            first_create = not os.path.exists(AUDIT_PATH)
            with open(AUDIT_PATH, "a") as f:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                except OSError:
                    pass
                try:
                    f.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")
                finally:
                    with contextlib.suppress(OSError):
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            if first_create:
                with contextlib.suppress(OSError):
                    os.chmod(AUDIT_PATH, 0o600)
    except OSError as e:
        logger.warning("Audit log write failed: %s", e)
