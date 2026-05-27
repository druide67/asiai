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
# Number of rotated backups to keep (``.1`` is the most recent, ``.N`` the
# oldest). Two backups makes the audit log ~30 MB worst case while
# materially raising the cost of "spam to evict evidence" attacks: an
# attacker needs to flood ~30 MB worth of audit lines, not 10 MB, before
# their original intrusion line falls off the retained set.
ROTATE_KEEP = 2

_lock = threading.Lock()


def _ensure_dir() -> None:
    os.makedirs(AUDIT_DIR, exist_ok=True)


def _rotate_if_needed() -> None:
    """Rotate the audit log once it exceeds ROTATE_BYTES.

    The most recent backup becomes ``.1``, the previous ``.1`` becomes
    ``.2``, ..., and the ``.ROTATE_KEEP`` backup is discarded. This is a
    Unix-style rolling rotation. The cost of an attacker who wants to
    erase their tracks by spamming the log to evict it scales linearly
    with ``ROTATE_KEEP`` — see :data:`ROTATE_KEEP` for the rationale.

    For long-term audit, ship the file off-host (rsyslog, fluent-bit,
    vector) — local rotation only buys you a window large enough for an
    operator to notice + react.
    """
    try:
        size = os.path.getsize(AUDIT_PATH)
    except OSError:
        return
    if size < ROTATE_BYTES:
        return
    try:
        # Shift existing backups down: .2 -> .3, .1 -> .2.
        for i in range(ROTATE_KEEP, 0, -1):
            src = AUDIT_PATH if i == 1 else f"{AUDIT_PATH}.{i - 1}"
            dst = f"{AUDIT_PATH}.{i}"
            if not os.path.exists(src):
                continue
            if os.path.exists(dst):
                # Either we're at the cap and dropping the oldest, or we
                # have a leftover from a previous run.
                if i == ROTATE_KEEP:
                    os.unlink(dst)
                else:
                    # An intermediate .N already exists — shouldn't
                    # happen after a successful rotation but defend
                    # against partial states by unlinking it before
                    # renaming.
                    os.unlink(dst)
            os.rename(src, dst)
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
