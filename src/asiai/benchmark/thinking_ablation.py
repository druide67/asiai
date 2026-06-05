"""``asiai bench --thinking-ablation`` — cost/benefit of the thinking config.

Runs one representative multi-turn agentic file-editing load (the tool-call-stress
turns, which accumulate context) under three thinking configurations and reports
the trade-off that decides production config:

* **enable-off** — no reasoning generated (preserve is moot).
* **enable-on-preserve-on** — reasoning kept in multi-turn history (Qwen3.6 default
  on froggeric-v19): coherent across turns, but context grows.
* **enable-on-preserve-off** — reasoning generated each turn but stripped from
  history (froggeric-v18 default): cheaper context, fresher each turn, less loop
  amplification.

Per config it reports tool-call quality, latency per turn, and prompt (context)
tokens at turn N. Crucially the history is rebuilt WITH ``reasoning_content`` so
``preserve_thinking`` has a real effect — the template keeps or strips it per the
flag (without this, preserve ON vs OFF would be a no-op and the numbers identical).

JSON-only (schema ``thinking-ablation-v1``); no DB write.
"""

from __future__ import annotations

import statistics
import time
from typing import Any

from asiai.benchmark.code_eval import chat
from asiai.benchmark.code_eval_scenarios import (
    STRESS_TOOLCALL_SYSTEM,
    STRESS_TOOLCALL_TURNS,
    TOOLS,
    TOOLS_BY_NAME,
)
from asiai.benchmark.output_gates import score_toolcall_turn
from asiai.collectors.system import collect_run_metadata

SCHEMA_VERSION = "thinking-ablation-v1"

# enable_thinking / preserve_thinking per cell (preserve None = not sent: moot when
# no reasoning is generated).
ABLATION_CONFIGS: list[dict[str, Any]] = [
    {"id": "enable-off", "enable_thinking": False, "preserve_thinking": None},
    {"id": "enable-on-preserve-on", "enable_thinking": True, "preserve_thinking": True},
    {"id": "enable-on-preserve-off", "enable_thinking": True, "preserve_thinking": False},
]


def _ablation_extra(
    base: dict[str, Any] | None, enable: bool, preserve: bool | None
) -> dict[str, Any]:
    eb = dict(base or {})
    ctk = dict(eb.get("chat_template_kwargs") or {})
    ctk["enable_thinking"] = enable
    if preserve is not None:
        ctk["preserve_thinking"] = preserve
    eb["chat_template_kwargs"] = ctk
    return eb


def _clean(score: dict[str, Any]) -> bool:
    return bool(
        score["json_valid"]
        and score["non_truncated"]
        and score["correct_tool"]
        and score["schema_conform"]
        and not score["empty_object_bug"]
    )


def _continue_with_reasoning(res: Any, tool_result: str) -> list[dict[str, Any]]:
    """Like ``code_eval._continue_messages`` but carries ``reasoning_content`` into
    the history so ``preserve_thinking`` actually has something to keep or strip."""
    tcs = res.tool_calls or []
    if not tcs:
        msg: dict[str, Any] = {"role": "assistant", "content": res.text or ""}
        if res.reasoning_text:
            msg["reasoning_content"] = res.reasoning_text
        return [msg]
    assistant_tcs = [
        {
            "id": tc.get("id") or f"call_{i}",
            "type": "function",
            "function": {
                "name": tc.get("name") or "",
                "arguments": tc.get("arguments_raw") or "{}",
            },
        }
        for i, tc in enumerate(tcs)
    ]
    assistant: dict[str, Any] = {
        "role": "assistant",
        "content": res.text or "",
        "tool_calls": assistant_tcs,
    }
    if res.reasoning_text:
        assistant["reasoning_content"] = res.reasoning_text
    return [
        assistant,
        *(
            {"role": "tool", "tool_call_id": atc["id"], "content": tool_result}
            for atc in assistant_tcs
        ),
    ]


def _mean(xs: list[Any]) -> float | None:
    vals = [x for x in xs if x is not None]
    return round(statistics.fmean(vals), 1) if vals else None


def _run_one_config(
    base_url: str,
    model: str,
    cfg: dict[str, Any],
    *,
    extra_body: dict[str, Any] | None,
    timeout: int,
    on_progress: Any,
) -> dict[str, Any]:
    eb = _ablation_extra(extra_body, cfg["enable_thinking"], cfg["preserve_thinking"])
    messages: list[dict[str, Any]] = [{"role": "system", "content": STRESS_TOOLCALL_SYSTEM}]
    per_turn: list[dict[str, Any]] = []
    for idx, turn in enumerate(STRESS_TOOLCALL_TURNS):
        messages.append({"role": "user", "content": turn["user"]})
        res = chat(
            base_url, model, messages, tools=TOOLS, max_tokens=1024, extra_body=eb, timeout=timeout
        )
        score = score_toolcall_turn(
            res, turn["expected_tool"], TOOLS_BY_NAME[turn["expected_tool"]]
        )
        per_turn.append(
            {
                "turn": idx,
                "clean": _clean(score),
                "latency_ms": res.latency_ms,
                "prompt_tokens": res.prompt_tokens,
                "completion_tokens": res.completion_tokens,
                "reasoning_chars": len(res.reasoning_text or ""),
                "error": res.error,
            }
        )
        messages.extend(_continue_with_reasoning(res, turn["tool_result"]))
        if on_progress:
            on_progress(
                f"  [{cfg['id']} t{idx + 1}/{len(STRESS_TOOLCALL_TURNS)}] "
                f"clean={per_turn[-1]['clean']} lat={res.latency_ms}ms "
                f"ctx={res.prompt_tokens}"
            )
    n = len(per_turn)
    ctx_first = per_turn[0]["prompt_tokens"] if per_turn else None
    ctx_last = per_turn[-1]["prompt_tokens"] if per_turn else None
    growth = (ctx_last - ctx_first) if (ctx_last is not None and ctx_first is not None) else None
    return {
        "config": cfg["id"],
        "enable_thinking": cfg["enable_thinking"],
        "preserve_thinking": cfg["preserve_thinking"],
        "turns": n,
        "pct_clean": (round(100.0 * sum(1 for t in per_turn if t["clean"]) / n, 1) if n else None),
        "latency_ms_mean": _mean([t["latency_ms"] for t in per_turn]),
        "ctx_tokens_first_turn": ctx_first,
        "ctx_tokens_last_turn": ctx_last,
        "ctx_growth": growth,
        "completion_tokens_mean": _mean([t["completion_tokens"] for t in per_turn]),
        "reasoning_chars_mean": _mean([t["reasoning_chars"] for t in per_turn]),
        "per_turn": per_turn,
    }


def run_thinking_ablation(
    base_url: str,
    engine_name: str,
    model: str,
    *,
    configs: list[dict[str, Any]] | None = None,
    extra_body: dict[str, Any] | None = None,
    timeout: int = 900,
    out_path: str | None = None,
    include_host: bool = False,
    engine_version: str = "",
    on_progress: Any = None,
) -> dict[str, Any]:
    """Run the tool-call-stress load under each thinking config → ablation dict."""
    started = int(time.time())
    cfgs = configs or ABLATION_CONFIGS
    cells = [
        _run_one_config(
            base_url, model, c, extra_body=extra_body, timeout=timeout, on_progress=on_progress
        )
        for c in cfgs
    ]
    out = {
        "schema_version": SCHEMA_VERSION,
        "engine": engine_name,
        "model": model,
        "base_url": base_url,
        "started_at": started,
        "finished_at": int(time.time()),
        "load": "tool-call-stress",
        "cells": cells,
    }
    out.update(
        collect_run_metadata(
            engine_version=engine_version,
            bench_mode="thinking-ablation",
            include_host=include_host,
        )
    )
    if out_path:
        import json

        with open(out_path, "w") as f:
            json.dump(out, f, indent=2)
    return out


__all__ = ["ABLATION_CONFIGS", "SCHEMA_VERSION", "run_thinking_ablation"]
