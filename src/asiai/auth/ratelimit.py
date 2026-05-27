"""Per-token sliding-window rate limit for fleet write commands.

Memory-only (no persistence). The bucket dict resets on every
``asiai web`` restart, which is acceptable: the limit defends against
brute-force enumeration and runaway scripts, not multi-day campaigns
(audit log covers that).
"""

from __future__ import annotations

import collections
import threading
import time


class TokenRateLimiter:
    """Per-token sliding window: ``limit`` events per ``window_seconds``.

    Returns ``(allowed, remaining, retry_after_seconds)`` from ``check``.
    Two concurrent calls for the same token serialize behind a single
    lock; that's fine for the volumes we expect (a handful of
    orchestrators).
    """

    def __init__(self, limit: int = 30, window_seconds: float = 60.0):
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._limit = limit
        self._window = window_seconds
        self._buckets: dict[str, collections.deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, token_id: str) -> tuple[bool, int, float]:
        """Try to consume one slot for ``token_id``.

        Returns:
            allowed: True if under the limit, False otherwise.
            remaining: slots still available in the current window
                (0 if not allowed).
            retry_after_seconds: 0 when allowed; otherwise the wait
                until the oldest entry in the window expires (minimum
                0.1s to avoid tight-loop retries).
        """
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.setdefault(token_id, collections.deque())
            cutoff = now - self._window
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self._limit:
                retry_after = bucket[0] + self._window - now
                return (False, 0, max(0.1, retry_after))
            bucket.append(now)
            return (True, self._limit - len(bucket), 0.0)

    def reset(self, token_id: str | None = None) -> None:
        """Drop bucket(s). ``None`` clears all buckets (tests use this)."""
        with self._lock:
            if token_id is None:
                self._buckets.clear()
            else:
                self._buckets.pop(token_id, None)

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def window_seconds(self) -> float:
        return self._window
