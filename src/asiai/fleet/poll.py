"""Parallel HTTP poll of asiai web nodes (fan-out / fan-in).

Polls each configured node's ``GET /api/v1/snapshot`` concurrently using
a ThreadPoolExecutor and ``urllib.request`` (stdlib only, no asyncio
dependency). The pattern mirrors ``asiai.benchmark.burst._run_one_burst_pass``
which already handles defensive timeouts and partial-result collection.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger("asiai.fleet.poll")

# Snapshot bodies are typically a few KB. Cap at 5 MB to defend against
# a misbehaving or hostile node sending unbounded data.
_MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB

DEFAULT_TIMEOUT = 5.0
DEFAULT_MAX_WORKERS = 16

# Coarse-grained error categories, used to:
# - normalize what we surface on the public HTTP API (so a probe can't
#   fingerprint the LAN by replaying queries and reading exception
#   type names like "ConnectionRefusedError" vs "TimeoutError").
# - power UI badges that distinguish "Mac is unreachable" from "Mac
#   responds but the snapshot endpoint errored".
ERROR_TIMEOUT = "timeout"
ERROR_REFUSED = "refused"
ERROR_DNS = "dns"
ERROR_HTTP_4XX = "http_4xx"
ERROR_HTTP_5XX = "http_5xx"
ERROR_PARSE = "parse"
ERROR_UNSUPPORTED_SCHEME = "unsupported_scheme"
ERROR_OVERSIZED = "oversized_response"
ERROR_OTHER = "other"


def classify_error(exception_name: str, http_status: int | None = None) -> str:
    """Map a raw exception class name + HTTP status to a coarse category."""
    if http_status is not None:
        if 400 <= http_status < 500:
            return ERROR_HTTP_4XX
        if 500 <= http_status < 600:
            return ERROR_HTTP_5XX
    name = exception_name.lower()
    if "timeout" in name:
        return ERROR_TIMEOUT
    if "connectionrefused" in name or "refused" in name:
        return ERROR_REFUSED
    if "gaierror" in name or "nameresolution" in name or "dns" in name:
        return ERROR_DNS
    if "json" in name or "decode" in name or "parse" in name:
        return ERROR_PARSE
    return ERROR_OTHER


@dataclass
class NodePoll:
    """Result of polling a single fleet node.

    ``error`` carries the raw Python exception class name for debugging.
    ``error_class`` is a coarse category (see ``ERROR_*`` constants) that
    is safe to expose on the public HTTP API and to drive UI badges.
    """

    nickname: str
    url: str
    ok: bool
    latency_ms: float
    snapshot: dict[str, Any] | None
    error: str | None
    reached_at: int
    error_class: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def poll_one(
    nickname: str,
    url: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> NodePoll:
    """Poll a single node's ``/api/v1/snapshot``.

    Always returns a NodePoll — never raises. Network/parse errors are
    captured in the ``error`` field; ``ok`` is False in that case and
    ``snapshot`` is None.
    """
    reached_at = int(time.time())
    t0 = time.perf_counter()
    if not url:
        return NodePoll(
            nickname=nickname,
            url=url,
            ok=False,
            latency_ms=0.0,
            snapshot=None,
            error="empty asiai_url",
            reached_at=reached_at,
        )
    # Defense in depth: even though upsert_node validates URL scheme, a
    # hand-edited fleet.json could smuggle file:// or ftp:// past the
    # CLI. urllib.urlopen happily resolves those, which would turn a
    # fleet node into a local-file read or SSRF probe.
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        logger.debug("poll %s rejected unsupported scheme %r", nickname, parsed.scheme)
        return NodePoll(
            nickname=nickname,
            url=url,
            ok=False,
            latency_ms=0.0,
            snapshot=None,
            error=f"unsupported URL scheme '{parsed.scheme}'",
            error_class=ERROR_UNSUPPORTED_SCHEME,
            reached_at=reached_at,
        )
    snapshot_url = f"{url.rstrip('/')}/api/v1/snapshot"

    try:
        req = urllib.request.Request(snapshot_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_RESPONSE_BYTES:
                logger.debug("poll %s response exceeded %d bytes", nickname, _MAX_RESPONSE_BYTES)
                return NodePoll(
                    nickname=nickname,
                    url=url,
                    ok=False,
                    latency_ms=(time.perf_counter() - t0) * 1000,
                    snapshot=None,
                    error=f"response exceeded {_MAX_RESPONSE_BYTES} bytes",
                    error_class=ERROR_OVERSIZED,
                    reached_at=reached_at,
                )
            data = json.loads(raw.decode("utf-8", errors="replace"))
            if not isinstance(data, dict):
                logger.debug("poll %s snapshot body is not a JSON object", nickname)
                return NodePoll(
                    nickname=nickname,
                    url=url,
                    ok=False,
                    latency_ms=(time.perf_counter() - t0) * 1000,
                    snapshot=None,
                    error="snapshot body is not a JSON object",
                    error_class=ERROR_PARSE,
                    reached_at=reached_at,
                )
    except urllib.error.HTTPError as e:
        logger.debug("poll %s HTTP %d", nickname, e.code)
        return NodePoll(
            nickname=nickname,
            url=url,
            ok=False,
            latency_ms=(time.perf_counter() - t0) * 1000,
            snapshot=None,
            error=f"HTTP {e.code}",
            error_class=classify_error("", http_status=e.code),
            reached_at=reached_at,
        )
    except Exception as e:  # noqa: BLE001 — network/timeout/json grab bag
        exc_name = type(e).__name__
        logger.debug("poll %s failed: %s: %s", nickname, exc_name, e)
        return NodePoll(
            nickname=nickname,
            url=url,
            ok=False,
            latency_ms=(time.perf_counter() - t0) * 1000,
            snapshot=None,
            error=exc_name,
            error_class=classify_error(exc_name),
            reached_at=reached_at,
        )

    return NodePoll(
        nickname=nickname,
        url=url,
        ok=True,
        latency_ms=(time.perf_counter() - t0) * 1000,
        snapshot=data,
        error=None,
        reached_at=reached_at,
    )


def poll_all(
    nodes: list[dict[str, Any]],
    timeout: float = DEFAULT_TIMEOUT,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> list[NodePoll]:
    """Poll all nodes in parallel via a ThreadPoolExecutor.

    Each input node dict must have ``nickname`` and ``asiai_url`` keys
    (same shape as entries from ``fleet.config.get_nodes()``). Returns
    one NodePoll per input node, in the same order.

    A defensive ``as_completed`` timeout of ``timeout + 5s`` ensures the
    aggregate call returns even if a TCP connection silently dies without
    a FIN (matches the burst.py pattern).
    """
    if not nodes:
        return []

    n = len(nodes)
    workers = min(max_workers, n)
    results_by_idx: dict[int, NodePoll] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_idx = {
            pool.submit(
                poll_one,
                node.get("nickname", f"node-{i}"),
                node.get("asiai_url", ""),
                timeout,
            ): i
            for i, node in enumerate(nodes)
        }
        try:
            for fut in concurrent.futures.as_completed(future_to_idx, timeout=timeout + 5):
                i = future_to_idx[fut]
                results_by_idx[i] = fut.result()
        except concurrent.futures.TimeoutError:
            logger.warning(
                "fleet poll hit %.1fs aggregate timeout, collecting partial results",
                timeout + 5,
            )
            for fut, i in future_to_idx.items():
                if fut.done() and i not in results_by_idx:
                    try:
                        results_by_idx[i] = fut.result()
                    except Exception as e:  # noqa: BLE001
                        logger.debug("future raised: %s", e)

    # Fill in dummy NodePoll for nodes whose future never completed.
    now = int(time.time())
    for i, node in enumerate(nodes):
        if i not in results_by_idx:
            results_by_idx[i] = NodePoll(
                nickname=node.get("nickname", f"node-{i}"),
                url=node.get("asiai_url", ""),
                ok=False,
                latency_ms=0.0,
                snapshot=None,
                error="aggregate timeout",
                error_class=ERROR_TIMEOUT,
                reached_at=now,
            )

    return [results_by_idx[i] for i in range(n)]
