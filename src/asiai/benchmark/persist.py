"""Persist any bench type's payload into the ``bench_runs`` table.

Every bench mode already produces a self-describing JSON payload (the same
dict written by ``--*-output``). This module promotes the common columns
plus a per-type normalized headline (``score_primary`` + ``score_label``)
and stores the payload verbatim, so History can chart any type over time
without ever re-parsing mode-specific JSON at query time.

The headline label is explicit ON PURPOSE: scores of different bench types
are never comparable to each other, and a naked number would invite exactly
that comparison.

Best-effort by design: a finished bench must never be lost to a persistence
error, so :func:`persist_bench_run` logs and returns ``None`` on failure
instead of raising.
"""

from __future__ import annotations

import json
import logging
import statistics
from typing import Any

from asiai.storage.db import store_bench_run

logger = logging.getLogger("asiai.benchmark.persist")


def _num(value: Any) -> float | None:
    """Coerce to float, or None — headline scores must never invent a 0."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _headline_standard(payload: dict) -> tuple[float | None, str, int]:
    bench = payload.get("benchmark") or {}
    engines = bench.get("engines") or {}
    # The export payload's winner is _determine_winner's dict
    # ({"name", "tok_s_delta", ...}); tolerate a bare name string too.
    winner = bench.get("winner")
    winner_name = winner.get("name") if isinstance(winner, dict) else winner
    if winner_name and _is_ci95_tie(engines):
        # Mirror of from_standard's tie detection: a headline labeled
        # "winner_..." next to a "no winner declared" report would be
        # self-contradicting — a tie falls back to the best median.
        winner_name = None
    if winner_name and winner_name in engines:
        return _num(engines[winner_name].get("median_tok_s")), "winner_median_tok_s", 0
    # No winner (single engine, or validity gate refused a ranking):
    # fall back to the best median rather than nothing.
    medians = [m for e in engines.values() if (m := _num(e.get("median_tok_s"))) is not None]
    return (max(medians) if medians else None), "best_median_tok_s", 0


def _is_ci95_tie(engines: dict) -> bool:
    """True when the top-2 medians sit inside each other's CI95."""
    ranked = sorted(
        (
            (m, e.get("ci95"))
            for e in engines.values()
            if (m := _num(e.get("median_tok_s"))) is not None
        ),
        key=lambda t: t[0],
        reverse=True,
    )
    if len(ranked) < 2:
        return False
    (_v1, ci1), (_v2, ci2) = ranked[0], ranked[1]
    if not (isinstance(ci1, (list, tuple)) and len(ci1) == 2 and any(_num(c) for c in ci1)):
        return False
    if not (isinstance(ci2, (list, tuple)) and len(ci2) == 2 and any(_num(c) for c in ci2)):
        return False
    lo1 = min(float(ci1[0]), float(ci1[1]))
    hi2 = max(float(ci2[0]), float(ci2[1]))
    return lo1 <= hi2


def _headline_agentic(payload: dict) -> tuple[float | None, str, int]:
    reuse = payload.get("prefix_cache_reuse") or {}
    gates = payload.get("quality_gates") or {}
    failed = 0
    if (gates.get("early_stop") or {}).get("detected"):
        failed += 1
    if (gates.get("memory_pressure") or {}).get("alerted"):
        failed += 1
    if gates.get("duplicate_processes"):
        failed += 1
    # _summarize_output emits output_valid_pct + min_valid_pct — the gate
    # fails on the SAME threshold the bench itself uses for its verdict.
    validity = gates.get("output_validity") or {}
    pct_valid = _num(validity.get("output_valid_pct"))
    min_valid = _num(validity.get("min_valid_pct"))
    if pct_valid is not None and pct_valid < (min_valid if min_valid is not None else 100):
        failed += 1
    return _num(reuse.get("reuse_fraction")), "reuse_fraction", failed


def _headline_burst(payload: dict) -> tuple[float | None, str, int]:
    results = payload.get("results") or {}
    failed = 0
    max_size: int | None = None
    for size_str, data in results.items():
        try:
            size = int(size_str)
        except (TypeError, ValueError):
            continue
        # runs>1 folds errors_count into {"median","min","max"} — always
        # truthy as a dict, so unwrap to max ("at least one pass errored").
        errors = data.get("errors_count")
        if isinstance(errors, dict):
            errors = errors.get("max", 0)
        if _num(errors):
            failed += 1
        if max_size is None or size > max_size:
            max_size = size
    if max_size is None:
        return None, "p95_ms_at_max_burst", failed
    lat = (results.get(str(max_size)) or {}).get("latency_ms") or {}
    p95 = lat.get("p95")
    if isinstance(p95, dict):  # runs>1 → {median,min,max}
        p95 = p95.get("median")
    return _num(p95), f"p95_ms_at_burst_{max_size}", failed


def _headline_code(payload: dict) -> tuple[float | None, str, int]:
    cr = payload.get("code_results") or {}
    # Deterministic suites only — judge scores are a different scale and
    # optional, so they never silently blend into the headline.
    keys = ("tool_call", "tool_call_stress", "recovery", "thinking")
    fields = {
        "tool_call": "pct_clean",
        "tool_call_stress": "pct_clean",
        "recovery": "pct_recovered",
        "thinking": "pct_no_think_leak",
    }
    vals = [
        v
        for k in keys
        if isinstance(cr.get(k), dict)
        if (v := _num(cr[k].get(fields[k]))) is not None
    ]
    return (round(statistics.mean(vals), 1) if vals else None), "mean_pct_clean_deterministic", 0


def _headline_language(payload: dict) -> tuple[float | None, str, int]:
    lr = payload.get("language_results") or {}
    adh = lr.get("adherence") or {}
    return _num(adh.get("pct_in_language")), "pct_in_language", 0


def _headline_instruct(payload: dict) -> tuple[float | None, str, int]:
    ir = payload.get("instruct_results") or {}
    vf = ir.get("verifiable") or {}
    score = _num(vf.get("prompt_level_strict"))
    if score is not None:
        return score, "prompt_strict_pct", 0
    # Agentic-deliverable-only run: use delivery rate of the first block.
    for key in ("research_brief", "research_brief_deep", "order_control"):
        block = ir.get(key) or {}
        delivered = _num(block.get("pct_primary_delivered"))
        if delivered is not None:
            return delivered, f"pct_primary_delivered_{key}", 0
    return None, "prompt_strict_pct", 0


def _headline_thinking(payload: dict) -> tuple[float | None, str, int]:
    cells = payload.get("cells") or []
    vals = [v for c in cells if isinstance(c, dict) if (v := _num(c.get("pct_clean"))) is not None]
    return (min(vals) if vals else None), "min_pct_clean", 0


_HEADLINES = {
    "standard": _headline_standard,
    "agentic": _headline_agentic,
    "burst": _headline_burst,
    "code": _headline_code,
    "language": _headline_language,
    "instruct": _headline_instruct,
    "thinking-ablation": _headline_thinking,
}


def extract_headline(bench_type: str, payload: dict) -> tuple[float | None, str, int]:
    """Return ``(score_primary, score_label, gates_failed)`` for a payload."""
    fn = _HEADLINES.get(bench_type)
    if fn is None:
        return None, "", 0
    try:
        return fn(payload)
    except Exception as exc:  # payload shape drift must not lose the run
        logger.warning("Headline extraction failed for %s: %s", bench_type, exc)
        return None, "", 0


def persist_standard_session(db_path: str, payload: dict) -> int | None:
    """Persist a standard-mode session row, skipping empty shells.

    A model-compare session built through ``build_report`` has no
    ``benchmark.engines`` — persisting it would write a ghost row
    (engine="", model="", score NULL). Compare-session history is a
    follow-up; until then, skip rather than pollute.
    """
    if not (payload.get("benchmark") or {}).get("engines"):
        logger.debug("Skipping bench_runs session row: no engines in payload")
        return None
    return persist_bench_run(db_path, "standard", payload)


def persist_bench_run(db_path: str, bench_type: str, payload: dict) -> int | None:
    """Store one complete bench run; returns the row id, or None on failure."""
    try:
        score, label, gates_failed = extract_headline(bench_type, payload)
        if score is None:
            label = ""  # a label without a score would mislabel the NULL
        extra_body = payload.get("extra_body") or {}
        # The standard session payload (export schema v2) nests hardware
        # under "machine"; the six mode payloads carry it at top level.
        machine = payload.get("machine") or {}
        row = {
            "ts": payload.get("started_at") or payload.get("timestamp") or 0,
            "finished_ts": payload.get("finished_at", 0),
            "bench_type": bench_type,
            "engine": _first_engine(payload),
            "engine_version": payload.get("engine_version") or "",
            "model": _model_name(payload),
            "asiai_version": payload.get("asiai_version") or "",
            "schema_version": str(payload.get("schema_version", "")),
            "dataset_version": str(payload.get("dataset_version", "")),
            "hw_chip": payload.get("hw_chip") or machine.get("chip") or "",
            "machine_model": payload.get("machine_model") or "",
            "os_version": payload.get("os_version") or machine.get("os_version") or "",
            "ram_gb": payload.get("ram_gb") or machine.get("ram_gb") or 0,
            "powermode": payload.get("powermode"),
            "extra_body": json.dumps(extra_body, sort_keys=True) if extra_body else "",
            "score_primary": score,
            "score_label": label,
            "gates_failed": gates_failed,
            "payload": json.dumps(payload, default=str, ensure_ascii=False),
        }
        return store_bench_run(db_path, row)
    except Exception as exc:
        logger.warning("Failed to persist %s bench run: %s", bench_type, exc)
        return None


def _first_engine(payload: dict) -> str:
    if payload.get("engine"):
        return str(payload["engine"])
    # Standard session payload nests engines under benchmark.engines.
    engines = (payload.get("benchmark") or {}).get("engines") or {}
    return ",".join(sorted(engines)) if engines else ""


def _model_name(payload: dict) -> str:
    if payload.get("model"):
        return str(payload["model"])
    return str((payload.get("benchmark") or {}).get("model") or "")
