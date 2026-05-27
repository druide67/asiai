"""Shared loopback secret between ``asiai web`` and ``aisctl serve``.

The file ``~/.local/state/asiai/aisctl-serve-token`` (0o600) holds a
random secret written by ``aisctl serve`` at startup. ``asiai web``
reads it when proxying write commands to the loopback ``aisctl serve``
endpoint at ``127.0.0.1:8898``.

Rationale: ``aisctl serve`` listens only on the loopback interface, but
on a multi-user macOS host any local user could still POST directly to
127.0.0.1 and bypass ``asiai web``'s Bearer auth + whitelist + audit.
Requiring this shared secret on the loopback hop reduces an other-user
attacker to a file-read primitive (they'd need to read a 0o600 file in
the *server* user's HOME, which already implies HOME compromise).

The secret is rotated on every ``aisctl serve`` startup and the file is
removed on graceful shutdown.
"""

from __future__ import annotations

import contextlib
import logging
import os
import secrets
import tempfile

logger = logging.getLogger("asiai.auth.loopback")

STATE_DIR = os.path.expanduser("~/.local/state/asiai")
TOKEN_PATH = os.path.join(STATE_DIR, "aisctl-serve-token")

INTERNAL_TOKEN_PREFIX = "aint_"


def _new_internal_token() -> str:
    return INTERNAL_TOKEN_PREFIX + secrets.token_urlsafe(32)


def write_token() -> str:
    """Generate, persist, and return a fresh loopback token (0o600).

    Caller (``aisctl serve``) writes this at startup. The file is
    symlink-resistant (refuses to write through a symlink).
    """
    os.makedirs(STATE_DIR, exist_ok=True)
    if os.path.islink(STATE_DIR):
        raise OSError(f"Refusing to write: {STATE_DIR} is a symlink")
    if os.path.lexists(TOKEN_PATH) and os.path.islink(TOKEN_PATH):
        raise OSError(f"Refusing to write: {TOKEN_PATH} is a symlink")
    token = _new_internal_token()
    fd, tmp_path = tempfile.mkstemp(dir=STATE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(token)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, TOKEN_PATH)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise
    return token


def read_token() -> str | None:
    """Return the current loopback token or None if absent."""
    try:
        with open(TOKEN_PATH) as f:
            tok = f.read().strip()
    except FileNotFoundError:
        return None
    except OSError as e:
        logger.warning("Failed to read loopback token %s: %s", TOKEN_PATH, e)
        return None
    if not tok.startswith(INTERNAL_TOKEN_PREFIX):
        logger.warning("Loopback token at %s has unexpected prefix", TOKEN_PATH)
        return None
    return tok


def remove_token() -> None:
    """Best-effort remove the token file (graceful shutdown hook)."""
    with contextlib.suppress(OSError):
        os.unlink(TOKEN_PATH)
