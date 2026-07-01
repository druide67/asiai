"""Ephemeral shell-bound operator login for the web dashboard.

The dashboard needs to authenticate a HUMAN before any browser-driven
write ships (the machine Bearer in :mod:`asiai.auth.config` authenticates
node-to-node orchestrators, not people). Rather than storing a human
password, the shell — the boundary the operator already trusts — is the
authenticator:

1. ``asiai auth login`` (CLI, this user's shell) generates a single-use,
   high-entropy code and persists its salted hash to a 0o600 state file
   with a short TTL.
2. The operator pastes the code into the ``/login`` form.
3. The web edge verifies it (constant-time), deletes the file
   (single-use), and issues a server-side session: an opaque id in an
   ``HttpOnly; SameSite=Lax`` cookie, backed by an in-memory store.

No human credential ever lives on disk; only a short-lived hash does.
The in-memory store is safe because ``asiai web`` runs a single uvicorn
process — a restart logs the operator out, which is a feature.

Credential audiences, for the audit trail:
- MACHINE  — ``asai_`` Bearer tokens (:mod:`asiai.auth.config`)
- OPERATOR — this module's sessions (a human at a browser)
- LOOPBACK — ``aint_`` shared secret (:mod:`asiai.auth.loopback`)
"""

from __future__ import annotations

import contextlib
import hmac
import json
import logging
import os
import secrets
import tempfile
import threading
import time
from dataclasses import dataclass, field

from asiai.auth.config import _hash_secret, _verify_hash

logger = logging.getLogger("asiai.auth.operator")

STATE_DIR = os.path.expanduser("~/.local/state/asiai")
LOGIN_CODE_PATH = os.path.join(STATE_DIR, "operator-login-code.json")

# Public prefix so a pasted code is recognizable, mirroring ``asai_`` /
# ``aint_``. No cryptographic value.
LOGIN_CODE_PREFIX = "aop_"

DEFAULT_LOGIN_CODE_TTL = 60.0
MAX_LOGIN_CODE_TTL = 300.0

# Absolute session lifetime. No idle timeout: one operator, sessions die
# on expiry, logout, or process restart.
SESSION_TTL = 12 * 3600.0

SESSION_COOKIE = "asiai_operator"


def _new_login_code() -> str:
    # 24 bytes -> ~192 bits; paste-friendly, brute-force-proof even
    # without the rate limit on the login route.
    return LOGIN_CODE_PREFIX + secrets.token_urlsafe(24)


def clamp_login_ttl(ttl: float) -> float:
    """Clamp a requested code TTL to ``[1, MAX_LOGIN_CODE_TTL]`` seconds.

    Exposed so the CLI reports the *effective* expiry rather than the raw
    request — a code minted with ``--ttl 600`` really dies at
    ``MAX_LOGIN_CODE_TTL``, and telling the operator otherwise sends them
    to a login that fails past the true window.
    """
    return min(max(float(ttl), 1.0), MAX_LOGIN_CODE_TTL)


def create_login_code(ttl: float = DEFAULT_LOGIN_CODE_TTL) -> str:
    """Generate a single-use login code and persist its salted hash.

    Returns the plaintext code (shown once by the CLI, never stored).
    Writing the 0o600 file is the shell-boundary proof: only this user
    can mint a code the web edge will accept.
    """
    ttl = clamp_login_ttl(ttl)
    code = _new_login_code()
    now = time.time()
    payload = {
        "version": 1,
        "code_hash": _hash_secret(code),
        "created_at": now,
        "expires_at": now + ttl,
    }
    os.makedirs(STATE_DIR, exist_ok=True)
    if os.path.islink(STATE_DIR):
        raise OSError(f"Refusing to write: {STATE_DIR} is a symlink")
    if os.path.lexists(LOGIN_CODE_PATH) and os.path.islink(LOGIN_CODE_PATH):
        raise OSError(f"Refusing to write: {LOGIN_CODE_PATH} is a symlink")
    fd, tmp_path = tempfile.mkstemp(dir=STATE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, LOGIN_CODE_PATH)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise
    return code


def consume_login_code(code: str) -> bool:
    """Verify ``code`` against the pending login-code file.

    On success the file is deleted (single-use). On a wrong code the
    file is kept — the rate limit on the login route is the brute-force
    defense, and burning the code on a typo would let any LAN host DoS
    the operator's login window. An expired file is cleaned up.
    """
    if not isinstance(code, str) or not code.startswith(LOGIN_CODE_PREFIX):
        return False
    try:
        with open(LOGIN_CODE_PATH) as f:
            payload = json.load(f)
    except FileNotFoundError:
        return False
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read login-code file %s: %s", LOGIN_CODE_PATH, e)
        return False
    if not isinstance(payload, dict):
        return False
    expires_at = payload.get("expires_at")
    stored = payload.get("code_hash")
    if not isinstance(expires_at, (int, float)) or not isinstance(stored, str):
        return False
    if time.time() > expires_at:
        with contextlib.suppress(OSError):
            os.unlink(LOGIN_CODE_PATH)
        return False
    if not _verify_hash(code, stored):
        return False
    with contextlib.suppress(OSError):
        os.unlink(LOGIN_CODE_PATH)
    return True


@dataclass
class OperatorSession:
    """One authenticated operator session."""

    created_at: float
    expires_at: float
    csrf_secret: str
    last_seen: float = field(default=0.0)


class OperatorSessionStore:
    """In-memory operator sessions keyed by opaque session id.

    Thread-safe (sync route handlers run in Starlette's threadpool).
    Sessions expire on an absolute TTL; a process restart drops them
    all, which is the intended revoke-everything lever.
    """

    def __init__(self, ttl: float = SESSION_TTL):
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        self._ttl = ttl
        self._sessions: dict[str, OperatorSession] = {}
        self._lock = threading.Lock()

    def create(self) -> tuple[str, OperatorSession]:
        """Mint a new session. Returns ``(session_id, session)``."""
        now = time.time()
        session = OperatorSession(
            created_at=now,
            expires_at=now + self._ttl,
            csrf_secret=secrets.token_urlsafe(32),
            last_seen=now,
        )
        session_id = secrets.token_urlsafe(32)
        with self._lock:
            self._purge_expired_unlocked(now)
            self._sessions[session_id] = session
        return (session_id, session)

    def get(self, session_id: str | None) -> OperatorSession | None:
        """Return the live session for ``session_id`` or None."""
        if not session_id:
            return None
        now = time.time()
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if now > session.expires_at:
                del self._sessions[session_id]
                return None
            session.last_seen = now
            return session

    def revoke(self, session_id: str | None) -> bool:
        """Drop a session. Returns True if it existed."""
        if not session_id:
            return False
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def verify_csrf(self, session: OperatorSession, token: str | None) -> bool:
        """Constant-time check of a submitted CSRF token."""
        if not isinstance(token, str) or not token:
            return False
        return hmac.compare_digest(token, session.csrf_secret)

    def count(self) -> int:
        with self._lock:
            self._purge_expired_unlocked(time.time())
            return len(self._sessions)

    def _purge_expired_unlocked(self, now: float) -> None:
        expired = [sid for sid, s in self._sessions.items() if now > s.expires_at]
        for sid in expired:
            del self._sessions[sid]
