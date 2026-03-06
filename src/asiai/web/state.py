"""Shared application state for the web dashboard."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class BenchStatus:
    """Current benchmark status for SSE progress."""

    running: bool = False
    progress: str = ""
    engine: str = ""
    prompt: str = ""
    run_index: int = 0
    total_runs: int = 0
    error: str = ""
    done: bool = False

    def snapshot(self) -> dict:
        """Return a dict snapshot of all fields (thread-safe read helper)."""
        return {
            "running": self.running,
            "progress": self.progress,
            "engine": self.engine,
            "prompt": self.prompt,
            "run_index": self.run_index,
            "total_runs": self.total_runs,
            "done": self.done,
            "error": self.error,
        }


@dataclass
class AppState:
    """Global mutable state shared across routes."""

    engines: list = field(default_factory=list)
    db_path: str = ""
    last_engine_refresh: float = 0.0
    engine_cache: list = field(default_factory=list)
    bench_status: BenchStatus = field(default_factory=BenchStatus)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _bench_lock: threading.Lock = field(default_factory=threading.Lock)
    _sse_connections: int = 0
    max_sse_connections: int = 10

    def refresh_engines_if_stale(self, max_age: float = 30.0) -> list:
        """Return cached engines, refreshing if older than max_age seconds."""
        now = time.time()
        if now - self.last_engine_refresh > max_age:
            with self._lock:
                if now - self.last_engine_refresh > max_age:
                    self.engine_cache = list(self.engines)
                    self.last_engine_refresh = now
        return self.engine_cache

    def get_bench_snapshot(self) -> dict:
        """Thread-safe snapshot of bench status."""
        with self._bench_lock:
            return self.bench_status.snapshot()

    def update_bench(self, **kwargs) -> None:
        """Thread-safe update of bench status fields."""
        with self._bench_lock:
            for key, value in kwargs.items():
                setattr(self.bench_status, key, value)

    def reset_bench(self, **kwargs) -> None:
        """Thread-safe reset of bench status to a new BenchStatus."""
        with self._bench_lock:
            self.bench_status = BenchStatus(**kwargs)

    def acquire_sse(self) -> bool:
        """Try to acquire an SSE connection slot. Returns False if at limit."""
        with self._lock:
            if self._sse_connections >= self.max_sse_connections:
                return False
            self._sse_connections += 1
            return True

    def release_sse(self) -> None:
        """Release an SSE connection slot."""
        with self._lock:
            self._sse_connections = max(0, self._sse_connections - 1)
