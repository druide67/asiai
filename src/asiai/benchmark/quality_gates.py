"""Quality gates for the agentic-mode benchmark.

Three orthogonal methodological checks invalidate results when they trip:

1. Early-stop. ``completion_tokens`` significantly below ``max_tokens``
   requested on multiple runs. Catches engine bugs (e.g. speculative
   decoding implementations that accept a drafted EOS token incorrectly
   under prefix cache reuse) that would otherwise just look like "fast"
   engines.
2. Memory pressure during the bench. Swap usage or swapouts increasing
   while the engine streams indicates the OS is paging the model or KV
   cache to disk. Throughput numbers are no longer representative of
   the engine itself.
3. Duplicate engine processes. Two instances bound to different ports
   compete for GPU and confuse hostname/process attribution downstream.

The agentic benchmark embeds these checks into its result JSON under the
``quality_gates`` key. Consumers should refuse to publish a result when
any gate is tripped — or at least surface a warning so the data point
isn't compared as-is against clean runs.
"""

from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("asiai.benchmark.quality_gates")


# --- Early-stop detection -------------------------------------------------

DEFAULT_EARLY_STOP_RATIO = 0.5
DEFAULT_EARLY_STOP_MIN_RUNS = 2


def detect_early_stop(
    runs: list,
    ratio_threshold: float = DEFAULT_EARLY_STOP_RATIO,
    min_runs: int = DEFAULT_EARLY_STOP_MIN_RUNS,
) -> dict[str, Any]:
    """Flag runs where ``completion_tokens < max_tokens_requested * ratio``.

    Args:
        runs: iterable of ``AgenticRun`` instances.
        ratio_threshold: a run is "truncated" when completion / requested
            falls below this ratio. Default 0.5.
        min_runs: minimum number of truncated runs needed to set
            ``detected = True``. Default 2 — a single early stop could be
            a fluke (network blip, transient overload).

    Returns dict with ``detected`` (bool), ``truncated_runs`` (list of
    per-phase details), and the thresholds used (so consumers can re-judge
    with different criteria without re-running the bench).
    """
    truncated: list[dict[str, Any]] = []
    for run in runs:
        if getattr(run, "error", None):
            continue
        requested = getattr(run, "max_tokens_requested", 0) or 0
        completion = getattr(run, "completion_tokens", None)
        if not requested or completion is None:
            continue
        if completion < requested * ratio_threshold:
            truncated.append(
                {
                    "phase": run.phase,
                    "completion_tokens": completion,
                    "max_tokens_requested": requested,
                    "ratio": round(completion / requested, 3) if requested else 0.0,
                }
            )
    return {
        "detected": len(truncated) >= min_runs,
        "truncated_runs": truncated,
        "ratio_threshold": ratio_threshold,
        "min_runs": min_runs,
    }


# --- Duplicate process detection -----------------------------------------

# Engine name → ps command substring. Patterns must be unique enough that
# the matcher won't false-positive on a different engine (e.g. "ollama"
# alone would match "ollama serve" but also a directory named "ollama").
_ENGINE_PROCESS_PATTERNS = {
    "ollama": "ollama serve",
    "llamacpp": "llama-server",
    "llamacpp-aux": "llama-server",
    "lmstudio": "LM Studio",
    "mlx-lm": "mlx_lm.server",
    "omlx": "mlx_omni_server",
    "vmlx": "vmlx serve",
    "turboquant": "turbo-server",
    "vllm-mlx": "vllm-mlx",
}


def check_duplicate_processes(engine_name: str) -> list[dict[str, str]]:
    """Return matching process entries when ≥2 share the engine pattern.

    The single-process case (the expected one) returns an empty list so
    consumers can treat a non-empty return as "abnormal."
    """
    pattern = _ENGINE_PROCESS_PATTERNS.get(engine_name, engine_name)
    try:
        ps_out = subprocess.run(
            ["ps", "axo", "pid,command"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("ps failed: %s", e)
        return []
    matches: list[dict[str, str]] = []
    for line in ps_out.splitlines()[1:]:
        if pattern in line:
            parts = line.split(None, 1)
            if len(parts) == 2:
                # Truncate command to 200 chars to keep JSON compact.
                matches.append({"pid": parts[0], "command": parts[1][:200]})
    return matches if len(matches) > 1 else []


# --- Memory pressure monitor (background thread) -------------------------

DEFAULT_SWAP_DELTA_THRESHOLD_MB = 500.0
DEFAULT_SWAPOUTS_DELTA_THRESHOLD = 1000
DEFAULT_POLL_INTERVAL_SEC = 15.0


@dataclass
class MemorySample:
    timestamp: float
    swap_used_mb: float
    swapouts: int
    pages_free_bytes: int
    pages_compressed_bytes: int


@dataclass
class MemoryWatchResult:
    baseline_swap_mb: float
    baseline_swapouts: int
    swap_delta_threshold_mb: float
    swapouts_delta_threshold: int
    samples: list[MemorySample] = field(default_factory=list)
    max_swap_delta_mb: float = 0.0
    max_swapouts_delta: int = 0
    alerted: bool = False
    alert_reason: str | None = None


def _vm_stat_sample() -> tuple[int, int, int, int]:
    """Return (pages_free, pages_occupied_by_compressor, swapouts, page_size).

    Returns zeros on failure so a one-off subprocess hiccup doesn't crash
    the bench loop.
    """
    try:
        out = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("vm_stat failed: %s", e)
        return 0, 0, 0, 16384

    page_size = 16384
    m = re.search(r"page size of (\d+) bytes", out)
    if m:
        page_size = int(m.group(1))

    def grab(label: str) -> int:
        m2 = re.search(rf"{label}:\s+(\d+)", out)
        return int(m2.group(1)) if m2 else 0

    return grab("Pages free"), grab("Pages occupied by compressor"), grab("Swapouts"), page_size


def _swap_used_mb() -> float:
    """Parse ``sysctl -n vm.swapusage`` for the 'used' field in MB.

    macOS prints French locale ('used = 6890,38M') when LC_ALL=fr_FR.UTF-8
    so the regex accepts both comma and dot as decimal separators.
    """
    try:
        out = subprocess.run(
            ["sysctl", "-n", "vm.swapusage"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return 0.0
    m = re.search(r"used\s*=\s*([\d.,]+)M", out)
    if not m:
        return 0.0
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return 0.0


class MemoryWatcher:
    """Background thread polling vm_stat + vm.swapusage at fixed interval.

    Used as a context manager around the bench loop. Records samples and
    compares against the baseline taken at ``__init__``. ``result.alerted``
    flips to True the first time swap or swapouts exceed their thresholds;
    samples keep accumulating either way so the caller can render a graph.

    The watcher does NOT abort the bench — it observes. The agentic
    benchmark surfaces the alert in the output JSON; consumers decide
    whether to discard or annotate the result.
    """

    def __init__(
        self,
        interval: float = DEFAULT_POLL_INTERVAL_SEC,
        swap_delta_threshold_mb: float = DEFAULT_SWAP_DELTA_THRESHOLD_MB,
        swapouts_delta_threshold: int = DEFAULT_SWAPOUTS_DELTA_THRESHOLD,
    ):
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        free, compressed, swapouts, page_size = _vm_stat_sample()
        swap_mb = _swap_used_mb()
        self._page_size = page_size  # cached so loop doesn't re-parse
        self.result = MemoryWatchResult(
            baseline_swap_mb=swap_mb,
            baseline_swapouts=swapouts,
            swap_delta_threshold_mb=swap_delta_threshold_mb,
            swapouts_delta_threshold=swapouts_delta_threshold,
        )
        self.result.samples.append(
            MemorySample(
                timestamp=time.time(),
                swap_used_mb=swap_mb,
                swapouts=swapouts,
                pages_free_bytes=free * page_size,
                pages_compressed_bytes=compressed * page_size,
            )
        )

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            free, compressed, swapouts, _ = _vm_stat_sample()
            swap_mb = _swap_used_mb()
            sample = MemorySample(
                timestamp=time.time(),
                swap_used_mb=swap_mb,
                swapouts=swapouts,
                pages_free_bytes=free * self._page_size,
                pages_compressed_bytes=compressed * self._page_size,
            )
            self.result.samples.append(sample)
            swap_delta = sample.swap_used_mb - self.result.baseline_swap_mb
            out_delta = sample.swapouts - self.result.baseline_swapouts
            if swap_delta > self.result.max_swap_delta_mb:
                self.result.max_swap_delta_mb = swap_delta
            if out_delta > self.result.max_swapouts_delta:
                self.result.max_swapouts_delta = out_delta
            if not self.result.alerted and (
                swap_delta >= self.result.swap_delta_threshold_mb
                or out_delta >= self.result.swapouts_delta_threshold
            ):
                self.result.alerted = True
                self.result.alert_reason = (
                    f"swap_delta={swap_delta:.0f}MB "
                    f"swapouts_delta={out_delta} (thresholds "
                    f"{self.result.swap_delta_threshold_mb:.0f}MB / "
                    f"{self.result.swapouts_delta_threshold})"
                )
                logger.warning("memory pressure alert: %s", self.result.alert_reason)

    def __enter__(self) -> MemoryWatcher:
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)


__all__ = [
    "DEFAULT_EARLY_STOP_MIN_RUNS",
    "DEFAULT_EARLY_STOP_RATIO",
    "DEFAULT_POLL_INTERVAL_SEC",
    "DEFAULT_SWAP_DELTA_THRESHOLD_MB",
    "DEFAULT_SWAPOUTS_DELTA_THRESHOLD",
    "MemorySample",
    "MemoryWatcher",
    "MemoryWatchResult",
    "check_duplicate_processes",
    "detect_early_stop",
]
