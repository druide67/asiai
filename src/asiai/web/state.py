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


@dataclass
class AppState:
    """Global mutable state shared across routes."""

    engines: list = field(default_factory=list)
    db_path: str = ""
    last_engine_refresh: float = 0.0
    engine_cache: list = field(default_factory=list)
    bench_status: BenchStatus = field(default_factory=BenchStatus)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def refresh_engines_if_stale(self, max_age: float = 30.0) -> list:
        """Return cached engines, refreshing if older than max_age seconds."""
        now = time.time()
        if now - self.last_engine_refresh > max_age:
            with self._lock:
                if now - self.last_engine_refresh > max_age:
                    self.engine_cache = list(self.engines)
                    self.last_engine_refresh = now
        return self.engine_cache
