"""Agentic-mode benchmark — 8-run protocol with explicit prefix cache reuse test.

Validates how well an engine reuses cached prefix tokens across consecutive
requests with shared system prompts but different user messages — the
characteristic load pattern of multi-turn agent workflows (60-80 tool calls
per task, each with the same long system prompt and a different user message).

Protocol:

    Run 1 (cold)          sys=SYS_A   user=USER_X   max=400
    Run 2 (warm)          sys=SYS_A   user=USER_X   max=400   (re-uses cache)
    Run 3 (prefix-test-1) sys=SYS_A   user=USER_Y   max=400   (sys hit, user new)
    Run 4 (prefix-test-2) sys=SYS_A   user=USER_X   max=400   (full re-use)
    Run 5 (prefix-test-3) sys=SYS_A   user=USER_Y   max=400   (sys hit, user new again)
    Run 6 (cold-prefix)   sys=SYS_B   user=USER_X   max=400   (sys differs => cold)
    Run 7 (long-context)  sys=SYS_A   user=USER_L   max=200
    Run 8 (long-prefix)   sys=SYS_A   user=USER_L   max=200   (cache hit on USER_L)

The protocol relies on cached_tokens reported by the engine's streaming
``usage.prompt_tokens_details.cached_tokens`` field when available (llama.cpp
and mlx-lm expose it; vllm-mlx, omlx, LM Studio do not — for those a TTFT
ratio proxy is used).

Verdict for prefix_cache_reuse:
    yes     — average cached / prompt on prefix-test runs >= 0.5
    partial — average cached / prompt on prefix-test runs >= 0.1
    no      — neither (or no cached_tokens reported AND TTFT_prefix > TTFT_cold/2)
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

from asiai.benchmark.prompts import (
    SYS_A,
    SYS_B,
    USER_L,
    USER_X,
    USER_Y,
)
from asiai.benchmark.quality_gates import (
    EngineMemorySampler,
    KVCacheSampler,
    MemoryWatcher,
    PowerThermalProbe,
    check_duplicate_processes,
    detect_early_stop,
    summarize_thermal,
)

logger = logging.getLogger("asiai.benchmark.agentic")

SCHEMA_VERSION = "agentic-v2"

# Caveat on token counts: other tokenizers compress differently. Llama-3
# averages ~4.0 chars/token on the same prose; the long-context phase
# (USER_L) would expand to ~66K tokens and may overflow a 32K context
# window. When benchmarking non-Qwen architectures, either pass
# ``--agentic-skip-long`` or verify the engine's max context against the
# actual token counts reported on the cold run.


@dataclass(frozen=True)
class AgenticPhase:
    name: str
    sys_msg: str
    user_msg: str
    max_tokens: int


PHASES: tuple[AgenticPhase, ...] = (
    AgenticPhase("cold", SYS_A, USER_X, 400),
    AgenticPhase("warm", SYS_A, USER_X, 400),
    AgenticPhase("prefix-test-1", SYS_A, USER_Y, 400),
    AgenticPhase("prefix-test-2", SYS_A, USER_X, 400),
    AgenticPhase("prefix-test-3", SYS_A, USER_Y, 400),
    AgenticPhase("cold-prefix", SYS_B, USER_X, 400),
    AgenticPhase("long-context", SYS_A, USER_L, 200),
    AgenticPhase("long-prefix", SYS_A, USER_L, 200),
)


@dataclass
class AgenticRun:
    phase: str
    ttft_ms: int | None = None
    wall_total_ms: int = 0
    completion_tokens: int = 0
    prompt_tokens: int | None = None
    cached_tokens: int | None = None
    decode_tok_s: float | None = None
    gpu_watts: float | None = None
    tok_s_per_watt: float | None = None
    thermal_speed_limit: int | None = None
    engine_rss_mb: float | None = None  # true RSS peak (headline, cross-family RAM)
    engine_phys_footprint_mb: float | None = None  # phys_footprint peak (KV+runtime for GGUF)
    kv_cache_tokens: int | None = None  # KV occupancy via /slots (≠ cached_tokens prefix-hit)
    sys_chars: int = 0
    user_chars: int = 0
    max_tokens_requested: int = 0
    error: str | None = None
    error_body: str | None = None


def _do_single_run(
    base_url: str,
    model: str,
    phase_name: str,
    sys_msg: str,
    user_msg: str,
    max_tokens: int,
    timeout: int = 900,
    extra_body: dict[str, Any] | None = None,
    probe: PowerThermalProbe | None = None,
) -> AgenticRun:
    """Send a single chat completion and parse SSE stream for usage.

    ``phase_name`` is recorded on the returned ``AgenticRun`` so error
    branches stay traceable without relying on the caller to backfill
    the field after the function returns.

    ``extra_body`` is merged into the request payload (caller keys override
    the defaults below). Use it for engine-specific kwargs like
    ``chat_template_kwargs={"enable_thinking": False}`` on Qwen3 family,
    which is mandatory to avoid the thinking-mode loop on Qwopus finetunes.
    """
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if extra_body:
        payload.update(extra_body)
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
    )

    t0 = time.perf_counter()
    first_token_time: float | None = None
    completion_chunks = 0
    last_usage: dict[str, Any] | None = None

    run = AgenticRun(
        phase=phase_name,
        sys_chars=len(sys_msg),
        user_chars=len(user_msg),
        max_tokens_requested=max_tokens,
    )

    # Reset the power/energy baseline right before the request so the window
    # measured by ``probe.read()`` covers this run's prefill + decode only.
    # KVCacheSampler polls /slots during the stream to capture the KV peak.
    kv_sampler = KVCacheSampler(base_url) if probe is not None else None
    mem_sampler = (
        EngineMemorySampler(probe.engine_name) if probe is not None and probe.engine_name else None
    )

    # An ExitStack guarantees both samplers are stopped (and their daemon
    # threads joined) on every exit path — success, HTTPError, or any other
    # exception — so a failed run can't leak a sampler thread into the next
    # engine's measurement window. The probe's lifecycle is owned by the caller
    # (read() below, close() upstream), so it is started here but not registered
    # with the stack.
    with contextlib.ExitStack() as stack:
        if probe is not None:
            probe.start()
        if kv_sampler is not None:
            stack.enter_context(kv_sampler)
        if mem_sampler is not None:
            stack.enter_context(mem_sampler)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                for raw in resp:
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
                    # Qwen3.x thinking mode emits reasoning BEFORE content.
                    # llama.cpp uses `reasoning_content`, mlx-lm uses `reasoning`.
                    # Both contribute to TTFT (first token emitted server-side).
                    content = (
                        (delta.get("content") or "")
                        + (delta.get("reasoning_content") or "")
                        + (delta.get("reasoning") or "")
                    )
                    if content:
                        if first_token_time is None:
                            first_token_time = time.perf_counter() - t0
                        completion_chunks += 1
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")[:500]
            run.error = f"HTTP {e.code}"
            run.error_body = body_text
            return run
        except Exception as e:  # noqa: BLE001 — network/json/timeout grab bag
            run.error = type(e).__name__
            run.error_body = str(e)[:300]
            return run

        # Capture the end time while the samplers are still running: the
        # ExitStack join (up to join_timeout each) fires when this block closes
        # and must not be folded into the decode window computed below.
        t_end = time.perf_counter() - t0

    run.wall_total_ms = int(t_end * 1000)
    run.ttft_ms = int(first_token_time * 1000) if first_token_time else None

    completion_tokens = (last_usage or {}).get("completion_tokens", completion_chunks)
    run.completion_tokens = completion_tokens
    run.prompt_tokens = (last_usage or {}).get("prompt_tokens")

    cached: int | None = None
    if last_usage:
        details = last_usage.get("prompt_tokens_details") or {}
        cached = details.get("cached_tokens")
        if cached is None:
            cached = last_usage.get("cached_tokens")
    run.cached_tokens = cached

    if (
        first_token_time
        and completion_tokens
        and t_end > first_token_time
        and completion_tokens > 1
    ):
        run.decode_tok_s = round((completion_tokens - 1) / (t_end - first_token_time), 2)

    # Mean GPU watts over the run window (prefill + decode) + thermal state.
    # tok/s/W uses decode_tok_s as the throughput numerator; on the short
    # phases (400 tokens) decode dominates the window so this is a fair
    # efficiency proxy, with the caveat that prefill power is folded in.
    if probe is not None:
        reading = probe.read()
        run.gpu_watts = reading["gpu_watts"]
        run.thermal_speed_limit = reading["thermal_speed_limit"]
        # RAM footprint: prefer the peak sampled mid-generation (GGUF clean
        # weight pages are reclaimable, so the post-run snapshot can dip);
        # fall back to the snapshot when the sampler caught nothing.
        mem_rss = mem_sampler.result.max_rss_mb if mem_sampler else 0.0
        mem_phys = mem_sampler.result.max_phys_footprint_mb if mem_sampler else 0.0
        run.engine_rss_mb = mem_rss or reading["engine_rss_mb"]
        run.engine_phys_footprint_mb = mem_phys or reading["engine_phys_footprint_mb"]
        # KV-cache occupancy peak sampled during the run via /slots (llama.cpp).
        # None for MLX engines (no /slots). No synchronous /metrics fallback:
        # the kv_cache counter was removed from modern llama.cpp and the call
        # only added up to 2 s of inter-run dead-time.
        kv_peak = kv_sampler.result.max_kv_tokens if kv_sampler else 0
        run.kv_cache_tokens = kv_peak or None
        if run.gpu_watts and run.decode_tok_s:
            run.tok_s_per_watt = round(run.decode_tok_s / run.gpu_watts, 3)

    return run


def _compute_verdict(runs: list[AgenticRun]) -> str:
    """Decide prefix_cache_reuse verdict from completed runs."""
    cold_runs = [r for r in runs if r.phase == "cold" and r.error is None]
    prefix_runs = [
        r for r in runs if r.phase in ("prefix-test-1", "prefix-test-3") and r.error is None
    ]
    if not cold_runs or not prefix_runs:
        return "unknown"

    # Pair (cached, prompt) per run so the ratio is computed on matching
    # samples — averaging cached_vals and prompt_vals independently would
    # mix sample sets of different sizes if an engine reports cached_tokens
    # on some runs but not others.
    paired = [
        (r.cached_tokens, r.prompt_tokens)
        for r in prefix_runs
        if r.cached_tokens is not None and r.prompt_tokens
    ]
    if paired:
        avg_cached = sum(c for c, _ in paired) / len(paired)
        avg_prompt = sum(p for _, p in paired) / len(paired)
        ratio = avg_cached / avg_prompt if avg_prompt else 0
        if ratio >= 0.5:
            return "yes"
        if ratio >= 0.1:
            return "partial"
        return "no"

    ttft_cold = cold_runs[0].ttft_ms
    ttft_prefix_vals = [r.ttft_ms for r in prefix_runs if r.ttft_ms is not None]
    if ttft_cold and ttft_prefix_vals:
        ttft_prefix = sum(ttft_prefix_vals) / len(ttft_prefix_vals)
        if ttft_prefix < ttft_cold / 5:
            return "yes"
        if ttft_prefix < ttft_cold / 2:
            return "partial"
        return "no"

    return "unknown"


def run_agentic_bench(
    base_url: str,
    engine_name: str,
    model: str,
    pause: float = 2.0,
    skip_long: bool = False,
    only: list[str] | None = None,
    timeout: int = 900,
    out_path: str | None = None,
    on_run: Any = None,
    include_host: bool = False,
    skip_quality_gates: bool = False,
    extra_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute the 8-run agentic protocol against ``base_url``.

    Args:
        base_url: HTTP base URL of an OpenAI-compatible engine.
        engine_name: Label written to results (e.g. ``llamacpp-b9200``).
        model: Model identifier the engine accepts in ``messages.model``.
        pause: Seconds between consecutive runs (default 2.0).
        skip_long: Skip phases 7-8 (50K user) to shorten total runtime.
        only: Optional list of phase names to run (default: all).
        timeout: Per-run HTTP timeout in seconds (default 900).
        out_path: If provided, write JSON results to this path.
        on_run: Optional callback ``on_run(AgenticRun)`` invoked after each run.
        include_host: When True, record the machine hostname in the result
            JSON under ``host``. Off by default since the JSON is often
            shared publicly and the hostname is not relevant for engine
            comparison.
        skip_quality_gates: Disable early-stop / memory pressure / duplicate
            process checks. Off by default. Useful for unit tests that mock
            ``_do_single_run`` and don't want a real thread or ``ps`` call.

    Returns the result dict with ``schema_version``, ``runs``,
    ``prefix_cache_reuse_verdict``, ``quality_gates``, and engine metadata.
    """
    selected = list(PHASES)
    if skip_long:
        selected = [p for p in selected if "long" not in p.name]
    if only:
        allowed = set(only)
        selected = [p for p in selected if p.name in allowed]

    duplicates = [] if skip_quality_gates else check_duplicate_processes(engine_name)

    runs: list[AgenticRun] = []
    started = int(time.time())

    watcher = None if skip_quality_gates else MemoryWatcher()
    probe = None if skip_quality_gates else PowerThermalProbe(engine_name=engine_name)
    # Equivalent to ``with watcher`` but lets us skip cleanly when None.
    if watcher is not None:
        watcher.__enter__()
    try:
        for phase in selected:
            logger.info("[%s] starting", phase.name)
            run = _do_single_run(
                base_url=base_url,
                model=model,
                phase_name=phase.name,
                sys_msg=phase.sys_msg,
                user_msg=phase.user_msg,
                max_tokens=phase.max_tokens,
                timeout=timeout,
                extra_body=extra_body,
                probe=probe,
            )
            runs.append(run)
            if on_run:
                try:
                    on_run(run)
                except Exception:  # noqa: BLE001 — never let observer break bench
                    logger.exception("on_run callback failed")
            time.sleep(pause)
    finally:
        if watcher is not None:
            watcher.__exit__(None, None, None)
        if probe is not None:
            probe.close()

    verdict = _compute_verdict(runs)
    quality_gates: dict[str, Any] = {
        "early_stop": detect_early_stop(runs),
        "duplicate_processes": duplicates,
        "thermal": summarize_thermal(runs),
    }
    if watcher is not None:
        mw = watcher.result
        quality_gates["memory_pressure"] = {
            "baseline_swap_mb": mw.baseline_swap_mb,
            "baseline_swapouts": mw.baseline_swapouts,
            "max_swap_delta_mb": round(mw.max_swap_delta_mb, 2),
            "max_swapouts_delta": mw.max_swapouts_delta,
            "alerted": mw.alerted,
            "alert_reason": mw.alert_reason,
            "swap_delta_threshold_mb": mw.swap_delta_threshold_mb,
            "swapouts_delta_threshold": mw.swapouts_delta_threshold,
            "samples_count": len(mw.samples),
        }

    out = {
        "schema_version": SCHEMA_VERSION,
        "engine": engine_name,
        "model": model,
        "base_url": base_url,
        "started_at": started,
        "finished_at": int(time.time()),
        "prefix_cache_reuse_verdict": verdict,
        "quality_gates": quality_gates,
        "extra_body": extra_body or {},
        "runs": [asdict(r) for r in runs],
    }
    if include_host:
        out["host"] = os.uname().nodename
    if out_path:
        with open(out_path, "w") as f:
            json.dump(out, f, indent=2)
    return out


__all__ = [
    "AgenticPhase",
    "AgenticRun",
    "PHASES",
    "SCHEMA_VERSION",
    "SYS_A",
    "SYS_B",
    "USER_X",
    "USER_Y",
    "USER_L",
    "run_agentic_bench",
]
