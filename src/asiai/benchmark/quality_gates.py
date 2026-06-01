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

import json
import logging
import re
import subprocess
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from asiai.collectors import ioreport as _ioreport
from asiai.collectors import system as _system


def _bytes_to_mb(b: int) -> float | None:
    """Bytes -> MB (1 decimal), or None when there is no reading (<= 0)."""
    return round(b / (1024 * 1024), 1) if b and b > 0 else None


def _engine_match_key(engine_name: str | None) -> str:
    """Canonical key to match an engine against ``collect_engine_processes()``.

    Aux llama.cpp instances (``llamacpp-aux``, ``llamacpp-aux-N``) alias to the
    ``llamacpp`` key that collector emits; everything else is lowercased with
    ``-``/``_`` stripped.
    """
    if not engine_name:
        return ""
    name = "llamacpp" if engine_name.startswith("llamacpp-aux") else engine_name
    return name.lower().replace("-", "").replace("_", "")


# The probe resolves IOReport / thermal / powermetrics through their source
# modules at call time (``_ioreport.ioreport_available``,
# ``_ioreport.IOReportSampler``, ``_system.collect_thermal``, and a lazily
# imported ``asiai.collectors.power.PowerMonitor``). A single set of patch
# targets (``asiai.collectors.*``) therefore works for the standard runner
# tests and the agentic/burst tests alike.

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
    "rapidmlx": "rapid-mlx",
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


# --- Power + thermal probe (per-run window sampler) ----------------------


class PowerThermalProbe:
    """Single power/thermal instrument shared by all three bench modes.

    IOReport by default (no sudo); pass ``cross_validate=True`` to also run
    ``powermetrics`` and resolve a ``power_source`` — used only by the
    standard runner for leaderboard provenance.

    Single-call benches (agentic, burst) keep calling ``PowerThermalProbe()``
    with the defaults: IOReport alone is within ~1.5% of powermetrics under
    load and needs no privileges, so those modes pay nothing for the
    cross-validation fields.

    Usage (per-window, agentic/burst)::

        probe = PowerThermalProbe()
        probe.start()                 # reset the IOReport energy baseline
        ...run one request...
        reading = probe.read()        # mean GPU watts over the window + thermal
        probe.close()

    Usage (standard runner, with sudo cross-check)::

        probe = PowerThermalProbe(cross_validate=True)
        probe.start()                 # reset IOReport baseline + start powermetrics
        ...run this engine's measured runs...
        reading = probe.read_aggregate()  # 5-field dict with power_source
        probe.close()

    ``read()`` returns ``gpu_watts`` (mean over the window since the last
    ``start()``/``read()``) and ``thermal_speed_limit`` (100 = no throttle,
    <100 = CPU/GPU throttled). Both default to ``None`` when the data source
    is unavailable so callers never crash on a missing channel.

    Args:
        cross_validate: When True, also start a ``PowerMonitor`` (powermetrics,
            sudo) alongside the IOReport sampler so ``read_aggregate()`` can
            report a ``power_source`` provenance. The IOReport arm is identical
            regardless of this flag.
        power_monitor_factory: Optional zero-arg callable returning a
            ``PowerMonitor``-like object. Injection seam for tests; defaults to
            ``asiai.collectors.power.PowerMonitor`` (resolved lazily so the
            standard-runner test patches on that module path still bite).
    """

    def __init__(
        self,
        cross_validate: bool = False,
        power_monitor_factory: Any = None,
        engine_name: str | None = None,
    ) -> None:
        self._engine_name = engine_name
        self._sampler: _ioreport.IOReportSampler | None = None
        if _ioreport.ioreport_available():
            try:
                self._sampler = _ioreport.IOReportSampler()
            except Exception:  # noqa: BLE001 — ctypes/IOReport grab bag
                logger.debug("IOReport sampler init failed", exc_info=True)
                self._sampler = None
        self._cross_validate = cross_validate
        self._power_monitor_factory = power_monitor_factory
        self._monitor: Any = None

    @property
    def available(self) -> bool:
        return self._sampler is not None

    def _make_monitor(self) -> Any:
        """Build a PowerMonitor, honoring the injected factory if any.

        The default path imports ``PowerMonitor`` lazily from
        ``asiai.collectors.power`` so a ``@patch("asiai.collectors.power.PowerMonitor")``
        in the standard-runner tests resolves to the mock.
        """
        if self._power_monitor_factory is not None:
            return self._power_monitor_factory()
        from asiai.collectors.power import PowerMonitor

        return PowerMonitor()

    def start(self) -> None:
        """Reset the energy/time baseline (and start powermetrics if cross-validating)."""
        if self._sampler is not None:
            try:
                self._sampler.sample()  # discard one sample to reset the baseline
            except Exception:  # noqa: BLE001
                logger.debug("IOReport baseline sample failed", exc_info=True)
        if self._cross_validate and self._monitor is None:
            try:
                monitor = self._make_monitor()
                if monitor.start():
                    self._monitor = monitor
            except Exception:  # noqa: BLE001 — powermetrics/sudo grab bag
                logger.debug("powermetrics monitor start failed", exc_info=True)
                self._monitor = None

    def _read_ioreport_watts(self) -> float | None:
        """Mean GPU watts (IOReport) since the last start()/read(), or None."""
        if self._sampler is None:
            return None
        try:
            return self._sampler.sample().gpu_watts
        except Exception:  # noqa: BLE001
            logger.debug("IOReport read failed", exc_info=True)
            return None

    def _read_thermal(self) -> int | None:
        """Current thermal speed limit (100 = no throttle), or None if unknown."""
        try:
            sl = _system.collect_thermal().speed_limit
            return sl if sl >= 0 else None
        except Exception:  # noqa: BLE001
            logger.debug("thermal read failed", exc_info=True)
            return None

    @property
    def engine_name(self) -> str | None:
        """The bench target engine name this probe was created for (or None)."""
        return self._engine_name

    def _read_engine_proc(self) -> Any:
        """The bench target engine's aggregated process info, or ``None``.

        ``None`` when no ``engine_name`` was given or no matching process runs.
        """
        if not self._engine_name:
            return None
        try:
            procs = _system.collect_engine_processes()
        except Exception:  # noqa: BLE001
            logger.debug("engine footprint read failed", exc_info=True)
            return None
        target = _engine_match_key(self._engine_name)
        for p in procs:
            if _engine_match_key(p.name) == target:
                return p
        return None

    def _read_engine_rss_mb(self) -> float | None:
        """True RSS (MB) of the bench target engine — the honest, cross-family RAM.

        ``resident_size`` counts every resident physical page, INCLUDING the
        resident file-backed GGUF weight pages that ``phys_footprint`` excludes,
        so it is comparable across llama.cpp (GGUF mmap) and MLX (anonymous +
        Metal) families on Apple Silicon unified memory. SSD-paged cold KV
        (oMLX) is naturally excluded (those pages aren't resident). ``None``
        when no ``engine_name`` was given or no matching process is running.
        """
        p = self._read_engine_proc()
        if p is not None and p.resident_bytes > 0:
            return round(p.resident_bytes / (1024 * 1024), 1)
        return None

    def _read_engine_phys_footprint_mb(self) -> float | None:
        """Physical footprint (MB) — dirty + compressed + iokit/Metal, EXCLUDES
        clean file-backed mmap. For GGUF this is ~KV + runtime (the dynamic
        part), so ``engine_rss_mb − engine_phys_footprint_mb ≈ resident weights``.
        Kept as a second column for continuity and the KV/runtime breakdown.
        """
        p = self._read_engine_proc()
        if p is not None and p.rss_bytes > 0:
            return round(p.rss_bytes / (1024 * 1024), 1)
        return None

    def read(self) -> dict[str, Any]:
        """Return mean GPU watts since the last start()/read() + thermal + memory.

        Per-window shape used by agentic/burst: ``gpu_watts``,
        ``thermal_speed_limit``, ``engine_rss_mb`` (true RSS, headline) and
        ``engine_phys_footprint_mb`` (no powermetrics provenance fields — those
        modes pay nothing for cross-validation). One ``ps`` snapshot feeds both
        memory fields.
        """
        p = self._read_engine_proc()
        return {
            "gpu_watts": self._read_ioreport_watts(),
            "thermal_speed_limit": self._read_thermal(),
            "engine_rss_mb": _bytes_to_mb(p.resident_bytes) if p is not None else None,
            "engine_phys_footprint_mb": _bytes_to_mb(p.rss_bytes) if p is not None else None,
        }

    def read_aggregate(self) -> dict[str, Any]:
        """Return the 5-field power provenance dict used by the standard runner.

        Reads the IOReport sampler once for ``io_gpu_watts``, stops the
        ``PowerMonitor`` (if cross-validating) for ``pm_gpu_watts``, then
        applies the runner's precedence ladder:

        * io>0 and pm>0  => gpu_watts=io,  source='both'   (prefer IOReport)
        * io>0 only      => gpu_watts=io,  source='ioreport'
        * pm>0 only      => gpu_watts=pm,  source='powermetrics'
        * neither        => gpu_watts=0.0, source=''
        """
        io_gpu_watts = self._read_ioreport_watts() or 0.0
        pm_gpu_watts = 0.0
        if self._monitor is not None:
            try:
                pm_gpu_watts = self._monitor.stop().gpu_watts
            except Exception:  # noqa: BLE001
                logger.debug("powermetrics stop failed", exc_info=True)
            finally:
                self._monitor = None

        if io_gpu_watts > 0 and pm_gpu_watts > 0:
            gpu_watts = io_gpu_watts  # prefer IOReport (no sudo)
            power_source = "both"
        elif io_gpu_watts > 0:
            gpu_watts = io_gpu_watts
            power_source = "ioreport"
        elif pm_gpu_watts > 0:
            gpu_watts = pm_gpu_watts
            power_source = "powermetrics"
        else:
            gpu_watts = 0.0
            power_source = ""

        p = self._read_engine_proc()
        return {
            "gpu_watts": gpu_watts,
            "power_watts_ioreport": io_gpu_watts,
            "power_watts_powermetrics": pm_gpu_watts,
            "power_source": power_source,
            "thermal_speed_limit": self._read_thermal(),
            "engine_rss_mb": _bytes_to_mb(p.resident_bytes) if p is not None else None,
            "engine_phys_footprint_mb": _bytes_to_mb(p.rss_bytes) if p is not None else None,
        }

    def close(self) -> None:
        if self._sampler is not None:
            try:
                self._sampler.close()
            except Exception:  # noqa: BLE001
                logger.debug("IOReport close failed", exc_info=True)
            self._sampler = None
        if self._monitor is not None:
            # Cross-validation path closed without read_aggregate(): release
            # the powermetrics subprocess so it doesn't linger.
            try:
                self._monitor.stop()
            except Exception:  # noqa: BLE001
                logger.debug("powermetrics close failed", exc_info=True)
            self._monitor = None


def summarize_thermal(runs: list) -> dict[str, Any]:
    """Summarize per-run thermal speed limits into a quality-gate entry.

    Returns the minimum observed speed limit and whether any run was
    throttled (<100). ``observed`` is False when no run reported a limit,
    so consumers can distinguish "not throttled" from "not measured."
    """
    limits = [
        getattr(r, "thermal_speed_limit", None)
        for r in runs
        if getattr(r, "thermal_speed_limit", None) is not None
    ]
    if not limits:
        return {"observed": False, "min_speed_limit": None, "throttled": False}
    min_limit = min(limits)
    return {
        "observed": True,
        "min_speed_limit": min_limit,
        "throttled": min_limit < 100,
    }


def read_kv_cache_tokens(base_url: str | None, timeout: float = 2.0) -> int | None:
    """KV-cache tokens currently held by the engine, via its Prometheus ``/metrics``.

    Reads ``llamacpp:kv_cache_tokens`` — the KV-cache *occupancy* (memory that
    grows with context length and ``--parallel`` slots), complementing the
    global footprint (``engine_rss_mb``).

    Caveat: llama.cpp **removed** ``kv_cache_usage_ratio`` / ``kv_cache_tokens``
    from ``/metrics`` in recent builds (KV-cache refactor → unified memory), so
    modern llama.cpp returns None here; ollama (older bundled llama.cpp) and
    legacy builds may still expose it. MLX engines have no metrics endpoint.
    The modern KV-occupancy source is ``/slots`` (``n_past``, only while
    processing) sampled by a background thread — a follow-up (#19).

    Best-effort: never raises. Returns *tokens*, not bytes (a bytes split needs
    per-engine model metadata), and a live snapshot.
    """
    if not base_url or not base_url.startswith(("http://", "https://")):
        return None
    url = base_url.rstrip("/") + "/metrics"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read(1_000_000).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 — network/timeout/HTTP grab bag
        return None
    for line in body.splitlines():
        if line.startswith("llamacpp:kv_cache_tokens"):
            try:
                return int(float(line.split()[-1]))
            except (ValueError, IndexError):
                return None
    return None


# --- KV-cache occupancy sampler (background, per-run) ---------------------

DEFAULT_KV_POLL_INTERVAL_SEC = 0.4


@dataclass
class KVCacheWatchResult:
    samples: list[int] = field(default_factory=list)
    max_kv_tokens: int = 0


class KVCacheSampler:
    """Background sampler for llama.cpp KV-cache occupancy via ``GET /slots``.

    Same skeleton as :class:`MemoryWatcher` (daemon thread + context manager),
    but tuned for the KV: a much tighter poll interval (the cache grows fast
    during a run, so a single post-run snapshot misses it — it lands on idle),
    scoped to a single run, and it keeps the *peak*.

    Each poll sums ``n_prompt_tokens`` (prompt + decoded = tokens held in the
    slot's KV, confirmed on llama.cpp b9430) over slots with
    ``is_processing == True``. Under ``--parallel N`` the N active slots each
    hold a KV, so the sum is the real total occupancy — the metric that drives
    OOM/swap.

    Graceful: ``/slots`` absent/disabled (some builds gate it behind a flag, or
    MLX engines without the endpoint) or any error → ``max_kv_tokens`` stays 0
    (callers map 0 → None).
    """

    def __init__(self, base_url: str | None, interval: float = DEFAULT_KV_POLL_INTERVAL_SEC):
        self.base_url = base_url
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.result = KVCacheWatchResult()
        self._enabled = bool(base_url) and base_url.startswith(("http://", "https://"))

    def _poll_once(self) -> int | None:
        url = self.base_url.rstrip("/") + "/slots"
        try:
            with urllib.request.urlopen(url, timeout=2.0) as resp:
                slots = json.loads(resp.read(2_000_000).decode("utf-8", errors="replace"))
        except Exception:  # noqa: BLE001 — /slots disabled, network, json
            return None
        if not isinstance(slots, list):
            return None
        total = 0
        for s in slots:
            if isinstance(s, dict) and s.get("is_processing"):
                n = s.get("n_prompt_tokens")
                if isinstance(n, int) and n > 0:
                    total += n
        return total

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            total = self._poll_once()
            if total is not None:
                self.result.samples.append(total)
                if total > self.result.max_kv_tokens:
                    self.result.max_kv_tokens = total

    def __enter__(self) -> KVCacheSampler:
        if self._enabled:
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)


# --- Engine RAM footprint sampler (background, per-run) -------------------

DEFAULT_ENGINE_MEM_POLL_INTERVAL_SEC = 1.0


@dataclass
class EngineMemoryWatchResult:
    max_rss_mb: float = 0.0
    max_phys_footprint_mb: float = 0.0


class EngineMemorySampler:
    """Background sampler for the bench target engine's RAM footprint.

    Same skeleton as :class:`MemoryWatcher` / :class:`KVCacheSampler` (daemon
    thread + context manager). Polls ``collect_engine_processes()`` and keeps
    the PEAK over the run window of both the true RSS (``resident_size`` — the
    honest, cross-family figure that counts resident GGUF weight pages) and the
    phys_footprint.

    Why the peak rather than a post-run snapshot: GGUF weight pages are clean +
    file-backed, hence reclaimable, so a lone snapshot can dip below real
    residency if the OS evicts under pressure. The max over the window, sampled
    mid-generation, is the honest reading.

    Graceful: no ``engine_name`` or no matching process → peaks stay 0.0
    (callers map 0 → None).
    """

    def __init__(
        self, engine_name: str | None, interval: float = DEFAULT_ENGINE_MEM_POLL_INTERVAL_SEC
    ):
        self.engine_name = engine_name
        self.interval = interval
        self._target = _engine_match_key(engine_name)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.result = EngineMemoryWatchResult()
        self._enabled = bool(self._target)

    def _poll_once(self) -> None:
        try:
            procs = _system.collect_engine_processes()
        except Exception:  # noqa: BLE001 — ps failure, never fatal
            return
        for p in procs:
            if _engine_match_key(p.name) == self._target:
                rss = _bytes_to_mb(p.resident_bytes)
                phys = _bytes_to_mb(p.rss_bytes)
                if rss and rss > self.result.max_rss_mb:
                    self.result.max_rss_mb = rss
                if phys and phys > self.result.max_phys_footprint_mb:
                    self.result.max_phys_footprint_mb = phys
                return

    def _loop(self) -> None:
        self._poll_once()  # immediate first sample
        while not self._stop.wait(self.interval):
            self._poll_once()

    def __enter__(self) -> EngineMemorySampler:
        if self._enabled:
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)


__all__ = [
    "DEFAULT_EARLY_STOP_MIN_RUNS",
    "DEFAULT_EARLY_STOP_RATIO",
    "DEFAULT_ENGINE_MEM_POLL_INTERVAL_SEC",
    "DEFAULT_KV_POLL_INTERVAL_SEC",
    "DEFAULT_POLL_INTERVAL_SEC",
    "DEFAULT_SWAP_DELTA_THRESHOLD_MB",
    "DEFAULT_SWAPOUTS_DELTA_THRESHOLD",
    "EngineMemorySampler",
    "EngineMemoryWatchResult",
    "KVCacheSampler",
    "KVCacheWatchResult",
    "MemorySample",
    "MemoryWatcher",
    "MemoryWatchResult",
    "PowerThermalProbe",
    "check_duplicate_processes",
    "detect_early_stop",
    "read_kv_cache_tokens",
    "summarize_thermal",
]
