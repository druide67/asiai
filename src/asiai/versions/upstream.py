"""Opt-in upstream version fetches (PyPI + GitHub releases).

Network-bound and therefore only used when the caller passes
``--check-upstream``. Reuses the defensive urllib shell from
``asiai.fleet.poll``: explicit scheme guard, a response-size cap, a
per-call timeout, and a never-raise contract (failures return ``None``).

stdlib only — no new dependencies.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse

logger = logging.getLogger("asiai.versions.upstream")

# Release/metadata JSON is small; 2 MB is a generous cap that still defends
# against an unbounded or hostile response.
_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
DEFAULT_TIMEOUT = 5.0
DEFAULT_MAX_WORKERS = 8

_USER_AGENT = "asiai-versions/1"


def _get_json(url: str, timeout: float, headers: dict[str, str] | None = None) -> dict | None:
    """GET *url* and parse a JSON object. Returns None on any failure.

    Mirrors ``fleet.poll.poll_one``'s defenses: scheme allowlist, size cap,
    broad exception capture. Never raises.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        logger.debug("rejected unsupported scheme %r for %s", parsed.scheme, url)
        return None
    req_headers = {"Accept": "application/json", "User-Agent": _USER_AGENT}
    if headers:
        req_headers.update(headers)
    try:
        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — scheme guarded above
            raw = resp.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_RESPONSE_BYTES:
                logger.debug("response from %s exceeded %d bytes", url, _MAX_RESPONSE_BYTES)
                return None
            data = json.loads(raw.decode("utf-8", errors="replace"))
            if not isinstance(data, dict):
                return None
            return data
    except urllib.error.HTTPError as e:
        logger.debug("%s -> HTTP %s", url, e.code)
        return None
    except Exception as e:  # noqa: BLE001 — network/timeout/json grab bag
        logger.debug("%s failed: %s: %s", url, type(e).__name__, e)
        return None


def pypi_latest(package: str, timeout: float = DEFAULT_TIMEOUT) -> str | None:
    """Latest released version of *package* on PyPI, or None."""
    if not package:
        return None
    data = _get_json(f"https://pypi.org/pypi/{package}/json", timeout)
    if not data:
        return None
    info = data.get("info")
    if isinstance(info, dict):
        version = info.get("version")
        if isinstance(version, str) and version:
            return version
    return None


def github_latest_release(
    repo: str,
    timeout: float = DEFAULT_TIMEOUT,
    token: str | None = None,
) -> str | None:
    """Latest release ``tag_name`` for *repo* (``owner/name``), or None.

    Honors a GitHub token (argument or ``GITHUB_TOKEN`` env) to lift the
    60 req/h unauthenticated rate limit to 5000 req/h. On rate-limit or any
    error the function degrades to None rather than raising — the caller
    records ``available=None`` with an explanatory note.
    """
    if not repo:
        return None
    tok = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    data = _get_json(
        f"https://api.github.com/repos/{repo}/releases/latest",
        timeout,
        headers=headers,
    )
    if not data:
        return None
    tag = data.get("tag_name")
    if isinstance(tag, str) and tag:
        return tag
    return None


def fetch_all(
    jobs: list[tuple[str, str, str]],
    timeout: float = DEFAULT_TIMEOUT,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> dict[str, str | None]:
    """Fetch many upstream versions concurrently.

    *jobs* is a list of ``(engine_name, source, target)`` where ``source``
    is ``"pypi"`` or ``"github"`` and ``target`` is the package or repo.
    Returns ``{engine_name: version_or_None}``. Mirrors the ThreadPool +
    ``as_completed`` defensive pattern of ``fleet.poll.poll_all``.
    """
    if not jobs:
        return {}

    def _one(source: str, target: str) -> str | None:
        if source == "pypi":
            return pypi_latest(target, timeout)
        if source == "github":
            return github_latest_release(target, timeout)
        return None

    results: dict[str, str | None] = {name: None for name, _, _ in jobs}
    workers = min(max_workers, len(jobs))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_name = {pool.submit(_one, source, target): name for name, source, target in jobs}
        try:
            for fut in concurrent.futures.as_completed(future_to_name, timeout=timeout + 5):
                name = future_to_name[fut]
                try:
                    results[name] = fut.result()
                except Exception as e:  # noqa: BLE001
                    logger.debug("upstream fetch for %s raised: %s", name, e)
        except concurrent.futures.TimeoutError:
            logger.warning("upstream fetch hit %.1fs aggregate timeout", timeout + 5)
    return results
