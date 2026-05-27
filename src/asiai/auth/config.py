"""Auth configuration: API tokens for fleet write commands.

Stored at ``~/.config/asiai/auth.json`` (0o600). The file holds a list
of tokens that orchestrators may present in
``Authorization: Bearer <secret>`` when calling write endpoints.

Secrets are NEVER stored in plaintext. Each entry keeps a salted SHA-256
hash; the plaintext is shown to the user exactly once at
``asiai auth init``/``asiai auth rotate`` time.

The shared loopback secret between ``asiai web`` and ``aisctl serve``
lives in a separate runtime file (``~/.local/state/asiai/aisctl-serve-token``)
managed by :mod:`asiai.auth.loopback`.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import tempfile
import time
from typing import Any

from asiai._filelock import file_lock as _shared_file_lock

logger = logging.getLogger("asiai.auth.config")

CONFIG_DIR = os.path.expanduser("~/.config/asiai")
CONFIG_PATH = os.path.join(CONFIG_DIR, "auth.json")
LOCK_PATH = os.path.join(CONFIG_DIR, "auth.lock")

SCHEMA_VERSION = 1

# Public prefix for API tokens so users can recognize them in env vars,
# scripts, and pasted CLI output. The prefix has no cryptographic value;
# it's a UX affordance + a cheap filter to reject obviously-wrong inputs.
TOKEN_PREFIX = "asai_"

_TOKEN_ID_RE = re.compile(r"^tok_[a-f0-9]{12}$")
_LABEL_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.\- ]{0,63}$")

MAX_TOKENS = 32


def _empty() -> dict[str, Any]:
    return {"version": SCHEMA_VERSION, "tokens": []}


def _file_lock():
    """Cross-process exclusive lock on the auth config.

    Thin wrapper around :func:`asiai._filelock.file_lock` so other modules
    that monkey-patch ``CONFIG_DIR`` / ``LOCK_PATH`` (tests) keep working.
    """
    return _shared_file_lock(LOCK_PATH, parent_dir=CONFIG_DIR)


def load_auth() -> dict[str, Any]:
    """Load auth config or return empty on any failure."""
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _empty()
        if not isinstance(data.get("tokens"), list):
            data["tokens"] = []
        return data
    except FileNotFoundError:
        return _empty()
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load auth config %s: %s", CONFIG_PATH, e)
        return _empty()


def save_auth(config: dict[str, Any]) -> bool:
    """Atomic write of auth config. 0o600 + symlink-resistant."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        if os.path.islink(CONFIG_DIR):
            logger.error("Refusing to write: %s is a symlink", CONFIG_DIR)
            return False
        if os.path.lexists(CONFIG_PATH) and os.path.islink(CONFIG_PATH):
            logger.error("Refusing to write: %s is a symlink", CONFIG_PATH)
            return False
        fd, tmp_path = tempfile.mkstemp(dir=CONFIG_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(config, f, indent=2)
                f.write("\n")
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, CONFIG_PATH)
            return True
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise
    except OSError as e:
        logger.error("Failed to save auth config: %s", e)
        return False


def _hash_secret(secret: str, salt_hex: str | None = None) -> str:
    """Return ``sha256$<salt_hex>$<hash_hex>`` for a secret.

    The salt protects against rainbow tables even though our 32-byte
    random secrets are infeasible to brute-force; cheap defense in depth.
    """
    if salt_hex is None:
        salt_hex = secrets.token_hex(16)
    h = hashlib.sha256()
    h.update(bytes.fromhex(salt_hex))
    h.update(secret.encode("utf-8"))
    return f"sha256${salt_hex}${h.hexdigest()}"


def _verify_hash(secret: str, stored: str) -> bool:
    """Constant-time compare of ``secret`` against a stored hash."""
    try:
        algo, salt_hex, _expected = stored.split("$", 2)
    except ValueError:
        return False
    if algo != "sha256":
        return False
    candidate = _hash_secret(secret, salt_hex=salt_hex)
    return hmac.compare_digest(candidate, stored)


def _new_token_id() -> str:
    return "tok_" + secrets.token_hex(6)


def _new_secret() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def _validate_label(label: str) -> str:
    label = (label or "").strip()
    if not label:
        return ""
    if not _LABEL_RE.match(label):
        raise ValueError(
            "label must match [a-zA-Z0-9][a-zA-Z0-9_.\\- ]{0,63} "
            "(letters/digits/dot/underscore/dash/space; max 64 chars)"
        )
    return label


def _create_token_unlocked(config: dict[str, Any], label: str) -> tuple[str, str]:
    label = _validate_label(label)
    live = [t for t in config["tokens"] if isinstance(t, dict) and t.get("revoked_at") is None]
    if len(live) >= MAX_TOKENS:
        raise ValueError(
            f"reached {MAX_TOKENS}-token cap; revoke an existing token before creating a new one"
        )
    token_id = _new_token_id()
    while any(isinstance(t, dict) and t.get("id") == token_id for t in config["tokens"]):
        token_id = _new_token_id()
    secret = _new_secret()
    config["tokens"].append(
        {
            "id": token_id,
            "secret_hash": _hash_secret(secret),
            "label": label,
            "created_at": int(time.time()),
            "last_used_at": None,
            "revoked_at": None,
        }
    )
    return (token_id, secret)


def create_token(label: str = "") -> tuple[str, str]:
    """Create a new token. Returns ``(token_id, secret_plaintext)``.

    The caller MUST display ``secret_plaintext`` to the user exactly once
    and discard it; it is hashed and cannot be recovered from disk.
    """
    with _file_lock():
        config = load_auth()
        token_id, secret = _create_token_unlocked(config, label)
        if not save_auth(config):
            raise OSError("Failed to save auth config")
        return (token_id, secret)


def init_auth(*, force: bool = False) -> tuple[bool, str | None, str | None]:
    """Initialize auth.json if missing. Returns ``(created, token_id, secret)``.

    If the file already holds at least one live token and ``force`` is
    False, returns ``(False, None, None)``. ``force=True`` always creates
    a new token but keeps the existing ones (use ``rotate_token`` to
    revoke + replace one).
    """
    with _file_lock():
        config = load_auth()
        has_live = any(
            isinstance(t, dict) and t.get("revoked_at") is None for t in config.get("tokens", [])
        )
        if has_live and not force:
            return (False, None, None)
        token_id, secret = _create_token_unlocked(config, label="initial")
        if not save_auth(config):
            return (False, None, None)
        return (True, token_id, secret)


def revoke_token(token_id: str) -> bool:
    """Mark a live token as revoked. Returns True on success."""
    with _file_lock():
        config = load_auth()
        for t in config["tokens"]:
            if isinstance(t, dict) and t.get("id") == token_id and t.get("revoked_at") is None:
                t["revoked_at"] = int(time.time())
                save_auth(config)
                return True
        return False


def rotate_token(token_id: str, label: str | None = None) -> tuple[str, str] | None:
    """Revoke + replace a token. Returns ``(new_id, new_secret)`` or None.

    On replacement failure (cap reached, save failed), the original token
    stays live so the user is never left without access.
    """
    with _file_lock():
        config = load_auth()
        target = None
        for t in config["tokens"]:
            if isinstance(t, dict) and t.get("id") == token_id and t.get("revoked_at") is None:
                target = t
                break
        if target is None:
            return None
        new_label = label if label is not None else target.get("label", "")
        target["revoked_at"] = int(time.time())
        try:
            new_id, secret = _create_token_unlocked(config, new_label)
        except ValueError:
            target["revoked_at"] = None
            return None
        if not save_auth(config):
            target["revoked_at"] = None
            return None
        return (new_id, secret)


def list_tokens() -> list[dict[str, Any]]:
    """Return public token metadata (no hashes, no secrets)."""
    out: list[dict[str, Any]] = []
    for t in load_auth().get("tokens", []):
        if not isinstance(t, dict):
            continue
        out.append(
            {
                "id": t.get("id"),
                "label": t.get("label", ""),
                "created_at": t.get("created_at"),
                "last_used_at": t.get("last_used_at"),
                "revoked_at": t.get("revoked_at"),
            }
        )
    return out


def verify_token(secret: str) -> str | None:
    """Return the token id if ``secret`` matches a live token, else None.

    The whole read/verify/touch sequence runs under ``_file_lock`` so a
    concurrent ``rotate_token`` / ``revoke_token`` cannot invalidate the
    token between the hash check and the ``last_used_at`` update — the
    older two-phase implementation left a small TOCTOU window where the
    touch would race the revocation. The lock is short-held (one hash
    comparison + one save) so it does not bottleneck the request path.
    """
    if not isinstance(secret, str) or not secret:
        return None
    if not secret.startswith(TOKEN_PREFIX):
        return None
    with _file_lock():
        config = load_auth()
        matched: dict[str, Any] | None = None
        for t in config.get("tokens", []):
            if not isinstance(t, dict):
                continue
            if t.get("revoked_at") is not None:
                continue
            stored = t.get("secret_hash")
            if not isinstance(stored, str):
                continue
            if _verify_hash(secret, stored):
                matched = t
                break
        if matched is None:
            return None
        matched["last_used_at"] = int(time.time())
        save_auth(config)
        tid = matched.get("id")
        return tid if isinstance(tid, str) else None
