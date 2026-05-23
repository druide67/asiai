"""Burst-concurrent benchmark — measures engine behavior under N parallel calls.

This module complements ``asiai.benchmark.agentic`` which measures single-call
performance across an agentic orchestrator prefix cache reuse pattern. Burst
mode fires N simultaneous ``/v1/chat/completions`` calls and reports the
latency distribution, aggregate throughput, and error rate.

The pattern simulates a real agentic loop dispatching multiple MCP/tool calls
in parallel within a short window (~200ms), which is the actual production
load for an agentic orchestrator dispatching many tool calls per turn. A
single-slot engine (e.g. Rapid-MLX 0.6.x) will serialize the requests
internally; a multi-slot engine (e.g. llama.cpp ``--parallel N``) will process
them concurrently — the bench exposes the difference quantitatively.

Schema:

    {
      "schema_version": "burst-v1",
      "engine": "rapidmlx",
      "model": "...",
      "base_url": "...",
      "burst_sizes": [30, 60, 80],
      "results": {
        "30": {
          "n": 30,
          "wall_time_s": 12.3,
          "latency_ms": {"p50": 1200, "p95": 4500, "p99": 5800, "max": 6200},
          "ttft_ms": {"p50": 110, "p95": 450, "p99": 800},
          "throughput_calls_per_s": 2.4,
          "throughput_tokens_aggregate_per_s": 480.0,
          "errors_count": 0,
          "error_summary": [],
          "memory_pressure_swap_delta_mb": 12.5,
          "memory_pressure_swapouts_delta": 0,
          "duplicate_processes": []
        },
        "60": {...},
        "80": {...}
      }
    }
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any

from asiai.benchmark.prompts import SYS_A
from asiai.benchmark.quality_gates import (
    MemoryWatcher,
    check_duplicate_processes,
)

logger = logging.getLogger("asiai.benchmark.burst")

SCHEMA_VERSION = "burst-v1"

# Per-call defaults: short generations to stress concurrency over throughput.
DEFAULT_MAX_TOKENS = 200
DEFAULT_TIMEOUT = 600
DEFAULT_BURST_SIZES = (30, 60)
DEFAULT_PAUSE_BETWEEN_SIZES = 5.0

# Max body size accepted from the engine, in bytes. Mirrors detect.py's
# limit so a rogue or buggy engine cannot inflate the bench process RSS.
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB

# Hard cap on a single burst size. macOS user thread limit is ~10k and the
# default ulimit -n is 256 — well above this cap stops being meaningful for
# concurrency measurement and starts being a foot-gun.
MAX_BURST_SIZE = 500


@dataclass
class BurstCallResult:
    """Result of a single call within a burst."""

    call_index: int
    ok: bool
    status_code: int
    latency_ms: float
    ttft_ms: float | None
    completion_tokens: int
    prompt_tokens: int | None
    error: str | None


@dataclass
class BurstSizeResult:
    """Aggregated stats for one burst size."""

    n: int
    wall_time_s: float
    latency_ms: dict[str, float]
    ttft_ms: dict[str, float]
    throughput_calls_per_s: float
    throughput_tokens_aggregate_per_s: float
    errors_count: int
    error_summary: list[str]
    memory_pressure_swap_delta_mb: float
    memory_pressure_swapouts_delta: int
    duplicate_processes: list[dict[str, str]] = field(default_factory=list)


def _make_user_prompt(call_index: int) -> str:
    """Generate a user prompt unique to this call_index.

    All N calls share the same ``SYS_A`` system prompt (long ~6K tokens),
    only the user message differs. This simulates the orchestrator pattern
    where the agent dispatches N tool calls with the same context but
    different parameters.
    """
    return (
        f"Burst call #{call_index}. Compute (12345 + {call_index}) * 7 and answer "
        f"with the resulting number as a single integer. Do not show any "
        f"intermediate steps, only the final integer."
    )


def _do_one_call(
    base_url: str,
    model: str,
    sys_msg: str,
    user_msg: str,
    call_index: int,
    max_tokens: int,
    timeout: int,
    extra_body: dict[str, Any] | None = None,
    stream: bool = True,
) -> BurstCallResult:
    """Single chat-completions POST. Returns latency, TTFT, token counts.

    When ``stream=True`` (the default), parses the SSE stream to capture
    per-call TTFT (time-to-first-token), which is the metric that
    distinguishes a single-slot FIFO queue from a multi-slot scheduler:
    on a single-slot engine TTFT scales linearly with call_index, on a
    multi-slot engine TTFT stays flat across calls.

    When ``stream=False``, only total latency and final usage are returned;
    ``ttft_ms`` is left as ``None``. Use this for engines whose SSE
    implementation is broken under high concurrency.
    """
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "stream": stream,
    }
    if stream:
        payload["stream_options"] = {"include_usage": True}
    if extra_body:
        # Merge engine-specific kwargs (e.g. chat_template_kwargs to disable
        # thinking mode, structured output schemas, sampler overrides).
        # Caller-provided keys override the defaults above.
        payload.update(extra_body)
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
    )

    t0 = time.perf_counter()
    if not stream:
        return _do_one_call_buffered(req, call_index, timeout, t0)
    return _do_one_call_streaming(req, call_index, timeout, t0)


def _do_one_call_buffered(
    req: urllib.request.Request,
    call_index: int,
    timeout: int,
    t0: float,
) -> BurstCallResult:
    """Buffered (non-streaming) variant — used when ``stream=False``."""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_RESPONSE_BYTES:
                return BurstCallResult(
                    call_index=call_index,
                    ok=False,
                    status_code=200,
                    latency_ms=(time.perf_counter() - t0) * 1000,
                    ttft_ms=None,
                    completion_tokens=0,
                    prompt_tokens=None,
                    error=f"response exceeded {_MAX_RESPONSE_BYTES} bytes",
                )
            data = json.loads(raw.decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        return BurstCallResult(
            call_index=call_index,
            ok=False,
            status_code=e.code,
            latency_ms=(time.perf_counter() - t0) * 1000,
            ttft_ms=None,
            completion_tokens=0,
            prompt_tokens=None,
            error=f"HTTP {e.code}",
        )
    except Exception as e:  # noqa: BLE001 — network/timeout/json grab bag
        return BurstCallResult(
            call_index=call_index,
            ok=False,
            status_code=0,
            latency_ms=(time.perf_counter() - t0) * 1000,
            ttft_ms=None,
            completion_tokens=0,
            prompt_tokens=None,
            error=type(e).__name__,
        )

    latency_ms = (time.perf_counter() - t0) * 1000
    usage = data.get("usage") or {}
    return BurstCallResult(
        call_index=call_index,
        ok=True,
        status_code=200,
        latency_ms=latency_ms,
        ttft_ms=None,
        completion_tokens=usage.get("completion_tokens", 0),
        prompt_tokens=usage.get("prompt_tokens"),
        error=None,
    )


def _do_one_call_streaming(
    req: urllib.request.Request,
    call_index: int,
    timeout: int,
    t0: float,
) -> BurstCallResult:
    """Streaming variant — captures per-call TTFT from the SSE stream."""
    first_token_time: float | None = None
    bytes_read = 0
    last_usage: dict[str, Any] | None = None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                bytes_read += len(raw)
                if bytes_read > _MAX_RESPONSE_BYTES:
                    return BurstCallResult(
                        call_index=call_index,
                        ok=False,
                        status_code=200,
                        latency_ms=(time.perf_counter() - t0) * 1000,
                        ttft_ms=None,
                        completion_tokens=0,
                        prompt_tokens=None,
                        error=f"response exceeded {_MAX_RESPONSE_BYTES} bytes",
                    )
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                payload_str = line[len("data:") :].strip()
                if payload_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload_str)
                except json.JSONDecodeError:
                    continue
                if chunk.get("usage"):
                    last_usage = chunk["usage"]
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {}) or {}
                # Qwen3 family emits reasoning_content before content under
                # thinking mode; both count toward first-token-emitted.
                content = (
                    (delta.get("content") or "")
                    + (delta.get("reasoning_content") or "")
                    + (delta.get("reasoning") or "")
                )
                if content and first_token_time is None:
                    first_token_time = time.perf_counter() - t0
    except urllib.error.HTTPError as e:
        return BurstCallResult(
            call_index=call_index,
            ok=False,
            status_code=e.code,
            latency_ms=(time.perf_counter() - t0) * 1000,
            ttft_ms=None,
            completion_tokens=0,
            prompt_tokens=None,
            error=f"HTTP {e.code}",
        )
    except Exception as e:  # noqa: BLE001 — network/timeout/SSE parse grab bag
        return BurstCallResult(
            call_index=call_index,
            ok=False,
            status_code=0,
            latency_ms=(time.perf_counter() - t0) * 1000,
            ttft_ms=None,
            completion_tokens=0,
            prompt_tokens=None,
            error=type(e).__name__,
        )

    latency_ms = (time.perf_counter() - t0) * 1000
    usage = last_usage or {}
    return BurstCallResult(
        call_index=call_index,
        ok=True,
        status_code=200,
        latency_ms=latency_ms,
        ttft_ms=(first_token_time * 1000) if first_token_time else None,
        completion_tokens=usage.get("completion_tokens", 0),
        prompt_tokens=usage.get("prompt_tokens"),
        error=None,
    )


def _quantile(values: list[float], q: float, *, presorted: bool = False) -> float:
    """Compute quantile q ∈ [0,1] of a non-empty list (linear interpolation).

    Pass ``presorted=True`` when calling repeatedly on the same data to skip
    the sort cost — caller is responsible for passing an already-sorted list.
    """
    if not values:
        return 0.0
    sorted_vals = values if presorted else sorted(values)
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def _aggregate_size(
    call_results: list[BurstCallResult],
    wall_time_s: float,
    swap_delta_mb: float,
    swapouts_delta: int,
    duplicates: list[dict[str, str]],
) -> BurstSizeResult:
    """Compute per-size aggregate stats from N call results."""
    n = len(call_results)
    ok_results = [r for r in call_results if r.ok]
    err_results = [r for r in call_results if not r.ok]
    latencies = [r.latency_ms for r in ok_results]
    ttfts = [r.ttft_ms for r in ok_results if r.ttft_ms is not None]
    total_tokens = sum(r.completion_tokens for r in ok_results)

    if latencies:
        sorted_lat = sorted(latencies)
        latency_stats = {
            "p50": _quantile(sorted_lat, 0.50, presorted=True),
            "p95": _quantile(sorted_lat, 0.95, presorted=True),
            "p99": _quantile(sorted_lat, 0.99, presorted=True),
            "max": sorted_lat[-1],
        }
    else:
        latency_stats = {"p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}

    if ttfts:
        sorted_ttft = sorted(ttfts)
        ttft_stats = {
            "p50": _quantile(sorted_ttft, 0.50, presorted=True),
            "p95": _quantile(sorted_ttft, 0.95, presorted=True),
            "p99": _quantile(sorted_ttft, 0.99, presorted=True),
        }
    else:
        ttft_stats = {"p50": 0.0, "p95": 0.0, "p99": 0.0}

    error_summary: dict[str, int] = {}
    for r in err_results:
        key = r.error or "unknown"
        error_summary[key] = error_summary.get(key, 0) + 1
    err_summary_list = [f"{k}: {v}" for k, v in sorted(error_summary.items())]

    throughput_calls_per_s = (len(ok_results) / wall_time_s) if wall_time_s > 0 else 0.0
    throughput_tokens_per_s = (total_tokens / wall_time_s) if wall_time_s > 0 else 0.0

    return BurstSizeResult(
        n=n,
        wall_time_s=wall_time_s,
        latency_ms=latency_stats,
        ttft_ms=ttft_stats,
        throughput_calls_per_s=throughput_calls_per_s,
        throughput_tokens_aggregate_per_s=throughput_tokens_per_s,
        errors_count=len(err_results),
        error_summary=err_summary_list,
        memory_pressure_swap_delta_mb=swap_delta_mb,
        memory_pressure_swapouts_delta=swapouts_delta,
        duplicate_processes=duplicates,
    )


def _run_one_burst_pass(
    *,
    base_url: str,
    engine: str,
    model: str,
    size: int,
    sys_msg: str,
    max_tokens: int,
    timeout: int,
    extra_body: dict[str, Any] | None,
    stream: bool,
) -> dict[str, Any]:
    """One pass of N concurrent calls. Returns aggregated stats as a dict."""
    duplicates_before = check_duplicate_processes(engine)

    with MemoryWatcher() as mem_watcher:
        t0 = time.perf_counter()
        call_results: list[BurstCallResult] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=size) as pool:
            futures = [
                pool.submit(
                    _do_one_call,
                    base_url,
                    model,
                    sys_msg,
                    _make_user_prompt(i),
                    i,
                    max_tokens,
                    timeout,
                    extra_body,
                    stream,
                )
                for i in range(size)
            ]
            # Defensive timeout: per-call urlopen has its own timeout, but a
            # silently-dropped TCP connection (no FIN received) can leave a
            # future never-completing. Cap the wait at per-call timeout + 30s
            # margin so the bench never hangs indefinitely.
            try:
                for fut in concurrent.futures.as_completed(futures, timeout=timeout + 30):
                    call_results.append(fut.result())
            except concurrent.futures.TimeoutError:
                logger.warning(
                    "burst size=%d: as_completed hit %.0fs timeout, collecting partial results",
                    size,
                    timeout + 30,
                )
                for fut in futures:
                    if fut.done():
                        try:
                            call_results.append(fut.result())
                        except Exception as e:  # noqa: BLE001
                            logger.debug("future raised: %s", e)
        wall_time_s = time.perf_counter() - t0

    call_results.sort(key=lambda r: r.call_index)
    size_result = _aggregate_size(
        call_results,
        wall_time_s=wall_time_s,
        swap_delta_mb=mem_watcher.result.max_swap_delta_mb,
        swapouts_delta=mem_watcher.result.max_swapouts_delta,
        duplicates=duplicates_before,
    )
    return asdict(size_result)


def _aggregate_passes(passes: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate multiple burst passes into a single result with variance.

    For each numeric metric, reports median + min + max across passes.
    Per-pass details are preserved under ``passes`` for full traceability.
    """
    n = len(passes)
    if n == 0:
        return {"passes": []}

    def _agg(values: list[float]) -> dict[str, float]:
        if not values:
            return {"median": 0.0, "min": 0.0, "max": 0.0}
        sorted_vals = sorted(values)
        return {
            "median": _quantile(sorted_vals, 0.50, presorted=True),
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
        }

    def _extract(path: list[str]) -> list[float]:
        out: list[float] = []
        for p in passes:
            v = p
            for key in path:
                v = v.get(key, 0.0) if isinstance(v, dict) else 0.0
            if isinstance(v, (int, float)):
                out.append(float(v))
        return out

    return {
        "n_passes": n,
        "n": passes[0]["n"],
        "wall_time_s": _agg(_extract(["wall_time_s"])),
        "latency_ms": {
            "p50": _agg(_extract(["latency_ms", "p50"])),
            "p95": _agg(_extract(["latency_ms", "p95"])),
            "p99": _agg(_extract(["latency_ms", "p99"])),
            "max": _agg(_extract(["latency_ms", "max"])),
        },
        "ttft_ms": {
            "p50": _agg(_extract(["ttft_ms", "p50"])),
            "p95": _agg(_extract(["ttft_ms", "p95"])),
            "p99": _agg(_extract(["ttft_ms", "p99"])),
        },
        "throughput_calls_per_s": _agg(_extract(["throughput_calls_per_s"])),
        "throughput_tokens_aggregate_per_s": _agg(_extract(["throughput_tokens_aggregate_per_s"])),
        "errors_count": _agg(_extract(["errors_count"])),
        "memory_pressure_swap_delta_mb": _agg(_extract(["memory_pressure_swap_delta_mb"])),
        "memory_pressure_swapouts_delta": _agg(_extract(["memory_pressure_swapouts_delta"])),
        "passes": passes,
    }


def run_burst(
    *,
    base_url: str,
    engine: str,
    model: str,
    burst_sizes: tuple[int, ...] = DEFAULT_BURST_SIZES,
    pause_between_sizes: float = DEFAULT_PAUSE_BETWEEN_SIZES,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: int = DEFAULT_TIMEOUT,
    sys_msg: str | None = None,
    extra_body: dict[str, Any] | None = None,
    stream: bool = True,
    runs: int = 1,
) -> dict[str, Any]:
    """Run the burst-mode benchmark over multiple burst sizes.

    Args:
        base_url: Engine OpenAI-compat base URL (e.g. ``http://127.0.0.1:8004``)
        engine: Engine name string for the output JSON (e.g. ``rapidmlx``)
        model: Model id to send in API requests
        burst_sizes: Tuple of concurrent-call counts to test (default (30, 60))
        pause_between_sizes: Seconds to sleep between size measurements (cooldown)
        max_tokens: Per-call max_tokens (default 200 — short to focus on throughput)
        timeout: Per-call HTTP timeout in seconds
        sys_msg: Override system prompt (default uses prompts.SYS_A, ~6K tokens)
        extra_body: OpenAI-compat extra_body kwargs merged into the payload.
            Useful for engine-specific options like
            ``{"chat_template_kwargs": {"enable_thinking": False}}`` to
            disable Qwen3 thinking mode, or sampler overrides.
        stream: When True (default), capture per-call TTFT from SSE stream.
        runs: Number of independent passes per burst size (default 1).
            Use 3-5 for production-grade measurements with variance reporting.
            Per-run results are stored under ``results[<size>]["passes"]``,
            and aggregate p50/min/max across passes under ``results[<size>]``.

    Returns:
        dict matching the burst-v1 schema, ready for ``json.dump``.

    Note on dispatch simultaneity: the ThreadPoolExecutor pool spins up
    workers as ``pool.submit()`` is called, so on a cold burst the actual
    dispatch span can be 50ms-1s for size=60-80 depending on OS scheduling.
    For sub-200ms dispatch precision, a ``threading.Barrier``-coordinated
    release would be required (planned for a future revision).
    """
    if runs < 1:
        raise ValueError(f"runs must be >= 1, got {runs}")
    if not burst_sizes:
        raise ValueError("burst_sizes must be a non-empty tuple")
    if min(burst_sizes) < 1:
        raise ValueError("burst sizes must be >= 1")

    if sys_msg is None:
        sys_msg = SYS_A

    started_at = int(time.time())
    results: dict[str, Any] = {}

    for size in burst_sizes:
        logger.info("burst size=%d starting (runs=%d)", size, runs)

        pass_results: list[dict[str, Any]] = []
        for run_idx in range(runs):
            pass_dict = _run_one_burst_pass(
                base_url=base_url,
                engine=engine,
                model=model,
                size=size,
                sys_msg=sys_msg,
                max_tokens=max_tokens,
                timeout=timeout,
                extra_body=extra_body,
                stream=stream,
            )
            pass_dict["run_index"] = run_idx
            pass_results.append(pass_dict)
            logger.info(
                "burst size=%d run=%d/%d wall=%.1fs p50=%.0fms p95=%.0fms errors=%d",
                size,
                run_idx + 1,
                runs,
                pass_dict["wall_time_s"],
                pass_dict["latency_ms"]["p50"],
                pass_dict["latency_ms"]["p95"],
                pass_dict["errors_count"],
            )
            if run_idx < runs - 1 and pause_between_sizes > 0:
                time.sleep(pause_between_sizes)

        if len(pass_results) == 1:
            results[str(size)] = pass_results[0]
        else:
            results[str(size)] = _aggregate_passes(pass_results)

        # Cooldown between sizes (let engine flush KV pool / reclaim memory)
        if size != burst_sizes[-1] and pause_between_sizes > 0:
            time.sleep(pause_between_sizes)

    finished_at = int(time.time())

    return {
        "schema_version": SCHEMA_VERSION,
        "engine": engine,
        "model": model,
        "base_url": base_url,
        "started_at": started_at,
        "finished_at": finished_at,
        "burst_sizes": list(burst_sizes),
        "max_tokens_per_call": max_tokens,
        "system_prompt_chars": len(sys_msg),
        "extra_body": extra_body or {},
        "streaming": stream,
        "runs": runs,
        "results": results,
    }


def parse_burst_sizes(value: str) -> tuple[int, ...]:
    """Parse comma-separated burst sizes string (e.g. ``"30,60,80"``).

    Each size must be in [1, MAX_BURST_SIZE] to avoid foot-gun thread
    explosions (macOS user thread limit ~10k, default ulimit -n 256).
    """
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if not parts:
        raise ValueError("empty burst sizes")
    sizes = tuple(int(p) for p in parts)
    for s in sizes:
        if s < 1:
            raise ValueError(f"burst size must be >= 1, got {s}")
        if s > MAX_BURST_SIZE:
            raise ValueError(
                f"burst size {s} exceeds MAX_BURST_SIZE={MAX_BURST_SIZE} "
                "(macOS thread/FD limit foot-gun)"
            )
    return sizes
