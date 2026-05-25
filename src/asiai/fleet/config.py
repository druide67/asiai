"""Fleet configuration file: declarative list of asiai nodes to observe.

Stored at ``~/.config/asiai/fleet.json``. Each node is one remote
``asiai web`` instance that this host will poll for status. The file is
intentionally hand-editable but is also managed by the
``asiai fleet add/remove`` commands.

Schema:

    {
      "version": 1,
      "nodes": [
        {
          "nickname": "studio-main",
          "asiai_url": "http://192.0.2.10:8899",
          "role": "workstation",
          "auth_token": null,
          "added_at": 1748191200,
          "last_seen": null,
          "last_status": null
        }
      ]
    }

The ``auth_token`` field is reserved for Phase 2 (write commands). Leave
it ``null`` until then.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
from typing import Any
from urllib.parse import urlparse

from asiai._filelock import file_lock as _shared_file_lock

logger = logging.getLogger("asiai.fleet.config")

CONFIG_DIR = os.path.expanduser("~/.config/asiai")
CONFIG_PATH = os.path.join(CONFIG_DIR, "fleet.json")
LOCK_PATH = os.path.join(CONFIG_DIR, "fleet.lock")

# Nicknames are user-chosen short ids stored in fleet.json and used as
# path segments in REST endpoints. Restrict to printable ASCII letters,
# digits, dot, underscore, dash; starts with a letter/digit; max 64 chars.
# This rejects path-traversal patterns (../), control chars (\n, \r, \x00),
# and anything that could blind a terminal or inject into logs.
_NICKNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.\-]{0,63}$")

# Only allow http/https URLs to defend against urllib's broader scheme
# support (file://, ftp://, javascript:, etc.) which would otherwise
# turn a fleet node into a generic local-file read or SSRF probe.
_ALLOWED_URL_SCHEMES = ("http", "https")

# Hard cap on the number of nodes in a single fleet. Each poll fans out
# one HTTP request per node; thousands of nodes would amplify a single
# /api/v1/fleet/snapshot GET into a LAN-wide DoS. 256 is well above any
# realistic home-lab and small-office deployment.
MAX_NODES = 256

# The current on-disk schema version. ``load_fleet`` accepts any
# version <= SCHEMA_VERSION; an unknown future version logs a warning
# and falls back to best-effort parsing so a forward-compatible asiai
# does not crash on a file written by an older release.
SCHEMA_VERSION = 1


def _empty() -> dict[str, Any]:
    """Return a fresh empty config (callable so callers cannot mutate a shared default)."""
    return {"version": SCHEMA_VERSION, "nodes": []}


def _file_lock():
    """Cross-process exclusive lock around the fleet config file.

    Thin wrapper around :func:`asiai._filelock.file_lock`; both
    ``CONFIG_DIR`` and ``LOCK_PATH`` are resolved at call time so tests
    that monkey-patch them keep working.
    """
    return _shared_file_lock(LOCK_PATH, parent_dir=CONFIG_DIR)


def load_fleet() -> dict[str, Any]:
    """Load fleet config from disk. Returns empty config on any failure.

    Performs best-effort schema-version awareness: if the file declares
    a version newer than this asiai release knows about, we log a
    warning and still return the data — forward-compatible. Unknown
    fields are preserved through the next save (Python dict is permissive).
    """
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
        if not isinstance(data, dict) or "nodes" not in data:
            logger.warning("Invalid fleet config format in %s", CONFIG_PATH)
            return _empty()
        if not isinstance(data["nodes"], list):
            logger.warning("fleet.json nodes is not a list")
            return _empty()
        observed = data.get("version", SCHEMA_VERSION)
        if not isinstance(observed, int) or observed > SCHEMA_VERSION:
            logger.warning(
                "fleet.json version=%r is newer than this asiai's "
                "SCHEMA_VERSION=%d; reading best-effort.",
                observed,
                SCHEMA_VERSION,
            )
        return data
    except FileNotFoundError:
        return _empty()
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load fleet config %s: %s", CONFIG_PATH, e)
        return _empty()


def save_fleet(config: dict[str, Any]) -> bool:
    """Atomic write fleet config. Returns True on success.

    The saved file is chmod'd to 0o600 because it may contain auth tokens
    or hostnames the user would rather not leak to other accounts on the
    machine.

    Refuses to write if ``CONFIG_DIR`` or ``CONFIG_PATH`` is a symlink:
    on a multi-user host, an attacker could symlink the config to a
    file they want overwritten and harvest the ``os.replace`` operation
    to clobber it. The check is best-effort — TOCTOU exists but the
    window is very narrow.
    """
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
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except OSError as e:
        logger.error("Failed to save fleet config: %s", e)
        return False


def get_nodes() -> list[dict[str, Any]]:
    """Return the list of configured nodes (defensive copy)."""
    return list(load_fleet().get("nodes", []))


def redact_node(node: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``node`` with secret-bearing fields removed.

    Currently strips ``auth_token``. Use this whenever a node is about to
    be displayed, serialized to JSON for output, or echoed in an HTTP
    response — secrets should stay in ``fleet.json`` (0o600) and never
    leak into terminals, logs, or HTML.

    Returns an empty dict if ``node`` is not a mapping (defensive guard
    against a manually-edited fleet.json containing non-dict entries).
    """
    if not isinstance(node, dict):
        return {}
    return {k: v for k, v in node.items() if k != "auth_token"}


def find_node(nickname: str) -> dict[str, Any] | None:
    """Return the node entry with the given nickname, or None."""
    for n in get_nodes():
        if n.get("nickname") == nickname:
            return n
    return None


def _validate_nickname(nickname: str) -> str:
    """Return a sanitized nickname or raise ValueError.

    Trim outer whitespace then enforce the ``_NICKNAME_RE`` shape so we
    cannot store nicknames that would break URLs, inject CRLF/ANSI into
    logs, or alias each other via trailing whitespace.
    """
    nickname = nickname.strip()
    if not nickname:
        raise ValueError("nickname must be non-empty")
    if not _NICKNAME_RE.match(nickname):
        raise ValueError(
            "nickname must match [a-zA-Z0-9][a-zA-Z0-9_.-]{0,63} "
            "(start with a letter/digit, only letters/digits/dot/underscore/dash, "
            "max 64 chars)"
        )
    return nickname


def _validate_url(asiai_url: str) -> str:
    """Return a sanitized URL or raise ValueError.

    Only ``http`` and ``https`` schemes are accepted; this prevents an
    operator (or attacker with access to fleet.json) from registering
    a ``file://`` or ``ftp://`` URL that ``urllib.request.urlopen``
    would happily resolve.
    """
    asiai_url = asiai_url.strip().rstrip("/")
    if not asiai_url:
        raise ValueError("asiai_url must be non-empty")
    parsed = urlparse(asiai_url)
    if parsed.scheme not in _ALLOWED_URL_SCHEMES:
        raise ValueError(f"asiai_url scheme must be http or https, got '{parsed.scheme}'")
    if not parsed.hostname:
        raise ValueError("asiai_url must include a hostname")
    return asiai_url


def upsert_node(
    nickname: str,
    asiai_url: str,
    role: str = "",
    auth_token: str | None = None,
) -> dict[str, Any]:
    """Add or update a node by nickname. Returns the saved entry.

    Raises ``ValueError`` if nickname or url fail validation. The whole
    read-modify-write is protected by a file lock so concurrent
    ``fleet add`` / ``fleet status`` cannot lose an entry.
    """
    nickname = _validate_nickname(nickname)
    asiai_url = _validate_url(asiai_url)

    with _file_lock():
        config = load_fleet()
        now = int(time.time())
        for entry in config["nodes"]:
            if entry.get("nickname") == nickname:
                entry["asiai_url"] = asiai_url
                entry["role"] = role
                entry["auth_token"] = auth_token
                save_fleet(config)
                return entry

        if len(config["nodes"]) >= MAX_NODES:
            raise ValueError(
                f"fleet is at the {MAX_NODES}-node cap; remove an existing entry before adding more"
            )

        entry = {
            "nickname": nickname,
            "asiai_url": asiai_url,
            "role": role,
            "auth_token": auth_token,
            "added_at": now,
            "last_seen": None,
            "last_status": None,
        }
        config["nodes"].append(entry)
        save_fleet(config)
        return entry


def remove_node(nickname: str) -> bool:
    """Remove a node by nickname. Returns True if a node was removed."""
    with _file_lock():
        config = load_fleet()
        before = len(config["nodes"])
        config["nodes"] = [n for n in config["nodes"] if n.get("nickname") != nickname]
        if len(config["nodes"]) < before:
            save_fleet(config)
            return True
        return False


def touch_node_status(nickname: str, ok: bool, error: str | None = None) -> None:
    """Update last_seen + last_status fields after a poll attempt.

    Best-effort: failures to save are logged but do not raise.
    """
    with _file_lock():
        config = load_fleet()
        now = int(time.time())
        for entry in config["nodes"]:
            if entry.get("nickname") == nickname:
                entry["last_seen"] = now
                entry["last_status"] = "ok" if ok else (error or "error")
                save_fleet(config)
                return
