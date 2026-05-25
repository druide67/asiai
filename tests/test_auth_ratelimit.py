"""Unit tests for asiai.auth.ratelimit."""

from __future__ import annotations

import threading
import time

import pytest

from asiai.auth.ratelimit import TokenRateLimiter


class TestTokenRateLimiter:
    def test_under_limit_allowed(self):
        rl = TokenRateLimiter(limit=5, window_seconds=60.0)
        for _ in range(5):
            allowed, _, _ = rl.check("tok_a")
            assert allowed

    def test_over_limit_denied(self):
        rl = TokenRateLimiter(limit=3, window_seconds=60.0)
        for _ in range(3):
            rl.check("tok_a")
        allowed, remaining, retry_after = rl.check("tok_a")
        assert allowed is False
        assert remaining == 0
        assert retry_after > 0

    def test_per_token_isolation(self):
        rl = TokenRateLimiter(limit=2, window_seconds=60.0)
        rl.check("tok_a")
        rl.check("tok_a")
        # tok_b is still fresh.
        allowed, _, _ = rl.check("tok_b")
        assert allowed is True
        # tok_a is now over.
        allowed, _, _ = rl.check("tok_a")
        assert allowed is False

    def test_sliding_window_expires_old_entries(self):
        # 0.2s window to keep the test fast.
        rl = TokenRateLimiter(limit=2, window_seconds=0.2)
        rl.check("tok_a")
        rl.check("tok_a")
        allowed, _, _ = rl.check("tok_a")
        assert allowed is False
        time.sleep(0.25)
        allowed, _, _ = rl.check("tok_a")
        assert allowed is True

    def test_retry_after_at_least_minimum(self):
        rl = TokenRateLimiter(limit=1, window_seconds=60.0)
        rl.check("tok_a")
        _, _, retry_after = rl.check("tok_a")
        assert retry_after >= 0.1

    def test_reset_token(self):
        rl = TokenRateLimiter(limit=1, window_seconds=60.0)
        rl.check("tok_a")
        allowed, _, _ = rl.check("tok_a")
        assert allowed is False
        rl.reset("tok_a")
        allowed, _, _ = rl.check("tok_a")
        assert allowed is True

    def test_reset_all(self):
        rl = TokenRateLimiter(limit=1, window_seconds=60.0)
        rl.check("tok_a")
        rl.check("tok_b")
        rl.reset()
        assert rl.check("tok_a")[0]
        assert rl.check("tok_b")[0]

    def test_thread_safety_under_burst(self):
        rl = TokenRateLimiter(limit=20, window_seconds=60.0)
        results: list[bool] = []
        lock = threading.Lock()

        def worker():
            allowed, _, _ = rl.check("tok_a")
            with lock:
                results.append(allowed)

        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # Exactly 20 calls succeeded; the rest were denied.
        assert sum(results) == 20
        assert sum(1 for r in results if not r) == 30

    def test_invalid_limit_raises(self):
        with pytest.raises(ValueError):
            TokenRateLimiter(limit=0, window_seconds=60.0)
        with pytest.raises(ValueError):
            TokenRateLimiter(limit=10, window_seconds=0)
