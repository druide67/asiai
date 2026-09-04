"""Unified, render-agnostic model of a bench result — any bench type.

One dataclass family (``BenchResult``) that every renderer (markdown
report, SVG card, terminal) consumes, built from the same payloads that
``bench_runs`` persists. The adapters here are the ONLY place where
mode-specific payload shapes are interpreted for presentation.

Fairness is structural, not editorial: every ``MetricValue`` carries its
sample count, optional CI95 and a caveat; ``BenchResult`` always carries
the run conditions and provenance. A renderer cannot show a naked number
because the model never hands it one.
"""

from __future__ import annotations

import os.path
from dataclasses import dataclass, field
from typing import Any

from asiai.benchmark.persist import extract_headline


@dataclass(frozen=True)
class MetricValue:
    """One displayed measurement, with its honesty attached."""

    key: str
    label: str
    value: float | str | None
    unit: str = ""
    ci95: tuple[float, float] | None = None
    n: int = 0  # measurements behind the value (0 = unknown)
    direction: str = "neutral"  # higher | lower | neutral
    caveat: str = ""  # e.g. "estimated", "client-measured", "judge offline"


@dataclass(frozen=True)
class Gate:
    """One quality gate outcome."""

    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class Subject:
    """One compared thing (an engine, a config cell, a burst size...)."""

    label: str
    engine: str = ""
    model: str = ""
    hero: MetricValue | None = None
    metrics: list[MetricValue] = field(default_factory=list)


@dataclass(frozen=True)
class BenchResult:
    """The complete, render-ready view of one bench run."""

    bench_type: str
    title: str
    subjects: list[Subject]
    winner: str | None  # Subject.label, None if not comparative / gate-refused
    winner_note: str = ""  # e.g. "ranking refused: output validity gate"
    co_leaders: list[str] = field(default_factory=list)  # tie within CI95
    conditions: dict[str, str] = field(default_factory=dict)
    gates: list[Gate] = field(default_factory=list)
    provenance: dict[str, str] = field(default_factory=dict)
    headline: MetricValue | None = None  # the bench_runs score_primary, labeled
    raw: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Shared extraction helpers
# ---------------------------------------------------------------------------


def _num(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _fmt(value: Any) -> str:
    return "" if value is None else str(value)


def _provenance(payload: dict) -> dict[str, str]:
    machine = payload.get("machine") or {}
    out = {
        "asiai_version": _fmt(payload.get("asiai_version")),
        "engine_version": _fmt(payload.get("engine_version")),
        "hw_chip": _fmt(payload.get("hw_chip") or machine.get("chip")),
        "machine_model": _fmt(payload.get("machine_model")),
        "os_version": _fmt(payload.get("os_version") or machine.get("os_version")),
        "ram_gb": _fmt(payload.get("ram_gb") or machine.get("ram_gb")),
        "schema_version": _fmt(payload.get("schema_version")),
        "dataset_version": _fmt(payload.get("dataset_version")),
        "started_at": _fmt(payload.get("started_at") or payload.get("timestamp")),
    }
    if payload.get("reconstructed"):
        # Backfilled session: the payload was rebuilt post-hoc from the raw
        # per-run rows — say so wherever provenance is shown.
        out["reconstructed"] = "payload rebuilt post-hoc from raw per-run rows"
    return {k: v for k, v in out.items() if v}


def _base_conditions(payload: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    extra = payload.get("extra_body")
    if extra:
        out["extra_body"] = _fmt(extra)
    pm = payload.get("powermode")
    if pm is not None:
        out["powermode"] = str(pm)
    return out


def _headline_metric(bench_type: str, payload: dict) -> MetricValue | None:
    score, label, _gates = extract_headline(bench_type, payload)
    if score is None:
        return None
    return MetricValue(key="headline", label=label, value=score, direction="neutral")


def _pct(key: str, label: str, value: Any, *, n: int = 0, caveat: str = "") -> MetricValue:
    return MetricValue(
        key=key, label=label, value=_num(value), unit="%", n=n, direction="higher", caveat=caveat
    )


_MODEL_NAME_SEPARATORS = "-_./@: "


def _basename_if_path(name: str) -> str:
    """An absolute filesystem path becomes its file name.

    A card is made to be published. When the model is given as a path — which is
    how every llama.cpp bench addresses it — printing it whole puts the operator's
    home directory on a public image: on 2026-08-15 a batch of seven cards left
    for social media titled `/Users/<user>/llms/gguf/...`, caught at review. The
    file name identifies the model exactly as well and leaks nothing.

    Only rooted paths are touched: a Hugging Face id (`org/model`) contains a
    slash too, and cutting it to `model` would drop the publisher, which is part
    of the identity a bench must state.
    """
    return name.rsplit("/", 1)[-1] if name.startswith(("/", "~")) else name


def display_model(models: list[str]) -> str:
    """One display name for a set of model names.

    A single distinct name is returned as-is. Several names collapse to the
    common family prefix when it is clean — cut at a separator boundary and
    long enough to mean something — else the generic "N-model comparison".
    A fabricated family name would be worse than the generic label.
    """
    distinct = sorted({_basename_if_path(m) for m in models if m})
    if not distinct:
        return ""
    if len(distinct) == 1:
        return distinct[0]
    prefix = os.path.commonprefix(distinct)
    # Never end mid-token: unless the prefix IS one of the names, cut back
    # to the last separator, then strip trailing separators.
    if prefix not in distinct and not prefix.endswith(tuple(_MODEL_NAME_SEPARATORS)):
        cut = max(prefix.rfind(c) for c in _MODEL_NAME_SEPARATORS)
        prefix = prefix[: cut + 1] if cut >= 0 else ""
    prefix = prefix.rstrip(_MODEL_NAME_SEPARATORS)
    if len(prefix) >= 6:
        return f"{prefix} ({len(distinct)} models)"
    return f"{len(distinct)}-model comparison"


# ---------------------------------------------------------------------------
# Per-type adapters
# ---------------------------------------------------------------------------


def from_standard(payload: dict) -> BenchResult:
    bench = payload.get("benchmark") or {}
    engines: dict[str, dict] = bench.get("engines") or {}
    subjects: list[Subject] = []
    quants: set[str] = set()
    for name in sorted(engines):
        e = engines[name]
        runs_n = int(e.get("runs_count") or 0)
        ci = e.get("ci95") or []
        # sorted() guards a malformed [hi, lo] pair — an inverted CI would
        # both miss real ties and print a negative ± on the hero.
        ci95 = (
            tuple(sorted((float(ci[0]), float(ci[1]))))
            if len(ci) == 2 and any(_num(c) for c in ci)
            else None
        )
        hero = MetricValue(
            key="median_tok_s",
            label="median tok/s",
            value=_num(e.get("median_tok_s")),
            unit="tok/s",
            ci95=ci95,
            n=runs_n,
            direction="higher",
        )
        pct_tok = e.get("percentiles_tok_s") or {}
        metrics = [
            MetricValue(
                "median_ttft_ms",
                "median TTFT",
                _num(e.get("median_ttft_ms")),
                "ms",
                n=runs_n,
                direction="lower",
            ),
            MetricValue(
                "p90_tok_s",
                "p90 tok/s",
                _num(pct_tok.get("p90")),
                "tok/s",
                n=runs_n,
                direction="higher",
            ),
            MetricValue(
                "vram_gb",
                "VRAM",
                round(e["vram_bytes"] / 1024**3, 1) if _num(e.get("vram_bytes")) else None,
                "GB",
                direction="lower",
            ),
            MetricValue("stability", "stability", e.get("stability") or None, n=runs_n),
            MetricValue(
                "output_valid_pct",
                "output valid",
                _num(e.get("output_valid_pct")),
                "%",
                n=runs_n,
                direction="higher",
            ),
            MetricValue("quantization", "quantization", e.get("model_quantization") or None),
            MetricValue("engine_version", "engine version", e.get("engine_version") or None),
        ]
        for key, label, unit, direction in (
            ("avg_soc_watts", "SoC power", "W", "lower"),
            ("avg_tok_s_per_soc_watt", "tok/s per SoC watt", "", "higher"),
            ("avg_energy_per_token_j", "energy per token", "J", "lower"),
            ("avg_power_watts", "GPU power", "W", "lower"),
        ):
            if _num(e.get(key)) is not None:
                metrics.append(MetricValue(key, label, _num(e.get(key)), unit, direction=direction))
        subjects.append(
            Subject(
                label=name,
                # Compare payloads carry the slot's own engine/model; the
                # session-level model (engine comparison) stays authoritative
                # when present — it is the user-requested name.
                engine=str(e.get("engine") or name),
                model=str(bench.get("model") or e.get("model") or ""),
                hero=hero,
                metrics=[m for m in metrics if m.value is not None],
            )
        )
        if e.get("model_quantization"):
            quants.add(str(e["model_quantization"]))

    winner = bench.get("winner")
    winner_name = winner.get("name") if isinstance(winner, dict) else winner
    winner_note = ""
    co_leaders: list[str] = []
    if winner_name and len(subjects) >= 2:
        # Statistical-honesty check: if the top two medians sit inside each
        # other's CI95, the ranking is noise — withhold the crown and report
        # a tie instead. Only applies when BOTH carry a CI (multi-run).
        ranked = sorted(
            (s for s in subjects if s.hero and isinstance(s.hero.value, (int, float))),
            key=lambda s: float(s.hero.value),  # type: ignore[arg-type]
            reverse=True,
        )
        if len(ranked) >= 2:
            top, second = ranked[0], ranked[1]
            if top.hero.ci95 and second.hero.ci95:
                lo1, _hi1 = top.hero.ci95
                _lo2, hi2 = second.hero.ci95
                if lo1 <= hi2:  # intervals overlap → tie
                    delta = float(top.hero.value) - float(second.hero.value)
                    co_leaders = sorted([top.label, second.label])
                    winner_name = None
                    winner_note = (
                        f"Δ {delta:.1f} tok/s is inside the combined CI95 — the "
                        "ranking is withheld. Co-leaders listed alphabetically."
                    )
    if not winner_name and not co_leaders and len(subjects) >= 2:
        winner_note = "ranking refused or unavailable (validity gate / insufficient data)"

    conditions = _base_conditions(payload)
    conditions.update(
        {
            k: v
            for k, v in {
                "context_size": _fmt(bench.get("context_size") or ""),
                "prompts": ", ".join(bench.get("prompts") or []),
                "runs_per_prompt": _fmt(bench.get("runs_per_prompt") or ""),
                "quantizations": ", ".join(sorted(quants)),
            }.items()
            if v
        }
    )

    # Session-level quality gates (thermal from per-run samples, memory
    # pressure from the run's MemoryWatcher) — present only when measured.
    gates: list[Gate] = []
    qg = payload.get("quality_gates") or {}
    thermal = qg.get("thermal") or {}
    if thermal.get("observed"):
        detail = f"worst {thermal.get('worst_level', '?')}"
        msl = _num(thermal.get("min_speed_limit"))
        if msl is not None and msl < 100:  # only when it actually limited
            detail += f", min speed limit {msl:g}%"
        gates.append(Gate("thermal", not thermal.get("throttled"), detail))
    mp = qg.get("memory_pressure")
    if mp is not None:
        gates.append(Gate("memory_pressure", not mp.get("alerted"), _fmt(mp.get("alert_reason"))))

    model_display = str(bench.get("model") or "") or display_model(
        [s.model for s in subjects],
    )
    return BenchResult(
        bench_type="standard",
        title=f"Throughput — {model_display or '?'}",
        subjects=subjects,
        winner=winner_name,
        winner_note=winner_note,
        co_leaders=co_leaders,
        conditions=conditions,
        gates=gates,
        provenance=_provenance(payload),
        headline=_headline_metric("standard", payload),
        raw=payload,
    )


def from_agentic(payload: dict) -> BenchResult:
    reuse = payload.get("prefix_cache_reuse") or {}
    gates_block = payload.get("quality_gates") or {}
    phase_stats = payload.get("phase_stats") or {}
    footprint = payload.get("footprint") or {}

    metrics: list[MetricValue] = [
        MetricValue(
            "verdict",
            "prefix-cache verdict",
            payload.get("prefix_cache_reuse_verdict"),
            caveat="engine-family-specific — compare the raw signal, not the verdict",
        ),
        MetricValue("cache_source", "cache signal source", reuse.get("cache_source")),
    ]
    for phase in sorted(phase_stats):
        st = phase_stats[phase] or {}
        ttft = st.get("ttft_ms") or {}
        decode = st.get("decode_tok_s") or {}
        if _num(ttft.get("median")) is not None:
            metrics.append(
                MetricValue(
                    f"ttft_{phase}",
                    f"TTFT ({phase})",
                    _num(ttft.get("median")),
                    "ms",
                    n=int(ttft.get("n") or 0),
                    direction="lower",
                    caveat=f"CV={ttft.get('cv')}" if ttft.get("cv") is not None else "",
                )
            )
        if _num(decode.get("median")) is not None:
            metrics.append(
                MetricValue(
                    f"decode_{phase}",
                    f"decode tok/s ({phase})",
                    _num(decode.get("median")),
                    "tok/s",
                    n=int(decode.get("n") or 0),
                    direction="higher",
                )
            )
    for key, label in (
        ("engine_rss_peak_mb", "engine RSS peak"),
        ("engine_rss_warm_mb", "engine RSS warm"),
    ):
        if _num(footprint.get(key)) is not None:
            metrics.append(
                MetricValue(key, label, _num(footprint.get(key)), "MB", direction="lower")
            )

    gates: list[Gate] = []
    es = gates_block.get("early_stop") or {}
    if es:
        truncated = ", ".join(t.get("phase", "?") for t in es.get("truncated_runs", []))
        gates.append(Gate("early_stop", not es.get("detected"), truncated))
    mp = gates_block.get("memory_pressure") or {}
    if mp:
        gates.append(Gate("memory_pressure", not mp.get("alerted"), _fmt(mp.get("alert_reason"))))
    dups = gates_block.get("duplicate_processes")
    if dups is not None:
        gates.append(
            Gate("duplicate_processes", not dups, f"{len(dups)} duplicate(s)" if dups else "")
        )
    validity = gates_block.get("output_validity") or {}
    pct_valid = _num(validity.get("output_valid_pct"))
    if pct_valid is not None:
        min_pct = _num(validity.get("min_valid_pct")) or 0
        gates.append(Gate("output_validity", pct_valid >= min_pct, f"{pct_valid}% valid"))
    sr = gates_block.get("session_replay") or {}
    if sr:
        # This detection existed for one full campaign (2026-09-02) without ever
        # being able to FAIL anything: agentic.py computed it, run-cell.sh listed
        # it in --fail-on-gate, and this function silently never built the Gate —
        # the enforcement chain was severed in the middle and no piece errored.
        # A control cell with 5 replayed runs passed green. The gate a caller
        # names in --fail-on-gate must exist here, or the flag lies.
        n = len(sr.get("replay_runs") or [])
        gates.append(Gate("session_replay", not sr.get("detected"), f"{n} replayed run(s)"))
    bank = gates_block.get("bank_preload") or {}
    if bank:
        gates.append(
            Gate(
                "bank_preload",
                not bank.get("detected"),
                _fmt(bank.get("reason")),
            )
        )
    thermal = gates_block.get("thermal") or {}
    if thermal.get("observed"):
        gates.append(
            Gate(
                "thermal",
                not thermal.get("throttled"),
                f"min speed limit {thermal.get('min_speed_limit')}%",
            )
        )
    # Both of these were computed and stored but never surfaced as gates, so a
    # run whose engine spent its whole token budget reasoning — or one measured
    # next to a second resident engine — reported clean everywhere a reader
    # actually looks.
    thinking = gates_block.get("thinking") or {}
    if thinking:
        status = thinking.get("status")
        # ``comparable`` is absent from pre-existing exports; fall back to the
        # signal it was derived from rather than defaulting the gate to green.
        comparable = thinking.get("comparable")
        if comparable is None:
            comparable = not thinking.get("reasoning_detected")
        gates.append(Gate("thinking", bool(comparable), _fmt(status)))
    others = gates_block.get("other_engines_resident")
    if others is not None:
        names = ", ".join(sorted({o.get("engine", "?") for o in others}))
        gates.append(Gate("other_engines_resident", not others, names))

    rf = _num(reuse.get("reuse_fraction"))
    hero = MetricValue(
        "reuse_fraction",
        "prefix-cache reuse fraction",
        rf,
        n=int(payload.get("repeats") or 1),
        direction="higher",
    )
    conditions = _base_conditions(payload)
    if payload.get("cold_warm_repeats"):
        conditions["cold_warm_repeats"] = "true (verdict rests on repeat 0's cold run)"
    # Decode throughput falls off with depth, so a tok/s figure is meaningless
    # without it. Reported as a condition, next to the other things a reader
    # needs before comparing two numbers.
    depth = payload.get("context_depth") or {}
    if depth.get("median") is not None:
        # Report per phase group. The all-phases spread mixes ~7.5K and ~56K
        # prompts and reads as several hundred percent, which says nothing
        # about whether two engines were asked the same question.
        parts = []
        for key, label in (("short", "short phases"), ("long", "long phases")):
            grp = depth.get(key) or {}
            if grp.get("median") is not None:
                spread = grp.get("spread_pct")
                parts.append(
                    f"{label} {grp['median']} tokens (n={grp.get('n', 0)}"
                    + (f", spread {spread}%" if spread is not None else "")
                    + ")"
                )
        if not parts:  # exports predating the split
            spread = depth.get("spread_pct")
            parts.append(
                f"{depth['median']} prompt tokens (median, n={depth.get('n', 0)}"
                + (f", spread {spread}%" if spread is not None else "")
                + ")"
            )
        conditions["context_depth"] = " · ".join(parts)

    return BenchResult(
        bench_type="agentic",
        title=f"Agentic prefix-cache — {payload.get('model', '?')} on {payload.get('engine', '?')}",
        subjects=[
            Subject(
                label=_fmt(payload.get("engine")),
                engine=_fmt(payload.get("engine")),
                model=_fmt(payload.get("model")),
                hero=hero,
                metrics=metrics,
            )
        ],
        winner=None,
        conditions=conditions,
        gates=gates,
        provenance=_provenance(payload),
        headline=_headline_metric("agentic", payload),
        raw=payload,
    )


def from_burst(payload: dict) -> BenchResult:
    results: dict = payload.get("results") or {}
    subjects: list[Subject] = []
    gates: list[Gate] = []

    def _scalar(v: Any) -> float | None:
        # runs>1 folds each stat into {median,min,max}: report the median.
        if isinstance(v, dict):
            return _num(v.get("median"))
        return _num(v)

    for size_str in sorted(results, key=lambda s: int(s) if str(s).isdigit() else 0):
        data = results[size_str] or {}
        lat = data.get("latency_ms") or {}
        n_passes = int(data.get("n_passes") or 1)
        hero = MetricValue(
            "p95_ms",
            "p95 latency",
            _scalar(lat.get("p95")),
            "ms",
            n=n_passes,
            direction="lower",
        )
        metrics = [
            MetricValue(
                "p50_ms",
                "p50 latency",
                _scalar(lat.get("p50")),
                "ms",
                n=n_passes,
                direction="lower",
            ),
            MetricValue(
                "p99_ms",
                "p99 latency",
                _scalar(lat.get("p99")),
                "ms",
                n=n_passes,
                direction="lower",
            ),
            MetricValue(
                "max_ms",
                "max latency",
                _scalar(lat.get("max")),
                "ms",
                n=n_passes,
                direction="lower",
            ),
            MetricValue(
                "agg_tok_s",
                "aggregate tok/s",
                _scalar(data.get("throughput_tokens_aggregate_per_s")),
                "tok/s",
                n=n_passes,
                direction="higher",
            ),
            MetricValue(
                "calls_per_s",
                "calls/s",
                _scalar(data.get("throughput_calls_per_s")),
                "",
                n=n_passes,
                direction="higher",
            ),
            MetricValue(
                "ttft_p50_ms",
                "p50 TTFT",
                _scalar((data.get("ttft_ms") or {}).get("p50")),
                "ms",
                n=n_passes,
                direction="lower",
            ),
            MetricValue(
                "ttft_p95_ms",
                "p95 TTFT",
                _scalar((data.get("ttft_ms") or {}).get("p95")),
                "ms",
                n=n_passes,
                direction="lower",
            ),
            MetricValue(
                "wall_s",
                "wall time",
                _scalar(data.get("wall_time_s")),
                "s",
                n=n_passes,
                direction="lower",
            ),
        ]
        subjects.append(
            Subject(
                label=f"burst-{size_str}",
                engine=_fmt(payload.get("engine")),
                model=_fmt(payload.get("model")),
                hero=hero,
                metrics=[m for m in metrics if m.value is not None],
            )
        )
        errors = data.get("errors_count")
        if isinstance(errors, dict):
            errors = errors.get("max")
        if _num(errors):
            gates.append(Gate(f"{int(errors)} errors @{size_str}", False, "errors during burst"))
        else:
            gates.append(Gate(f"no errors @{size_str}", True, ""))
        swap = _scalar(data.get("memory_pressure_swap_delta_mb"))
        if swap and swap > 0:
            gates.append(Gate(f"swap +{swap:.0f} MB @{size_str}", False, "swap pressure"))

    conditions = _base_conditions(payload)
    for key, label in (
        ("burst_sizes", "burst_sizes"),
        ("max_tokens_per_call", "max_tokens_per_call"),
        ("streaming", "streaming"),
        ("runs", "runs"),
    ):
        if payload.get(key) is not None:
            conditions[label] = _fmt(payload.get(key))

    return BenchResult(
        bench_type="burst",
        title=f"Burst concurrency — {payload.get('model', '?')} on {payload.get('engine', '?')}",
        subjects=subjects,
        winner=None,
        conditions=conditions,
        gates=gates,
        provenance=_provenance(payload),
        headline=_headline_metric("burst", payload),
        raw=payload,
    )


_CODE_SUITE_FIELDS: dict[str, tuple[tuple[str, str], ...]] = {
    "tool_call": (
        ("pct_clean", "clean"),
        ("pct_json_valid", "JSON valid"),
        ("pct_non_truncated", "non-truncated"),
        ("pct_schema_conform", "schema conform"),
        ("pct_correct_tool", "correct tool"),
        ("pct_emitted", "emitted"),
        ("edit_turns_pct_clean", "edit turns clean"),
    ),
    "tool_call_stress": (
        ("pct_clean", "clean"),
        ("pct_json_valid", "JSON valid"),
        ("pct_non_truncated", "non-truncated"),
        ("pct_schema_conform", "schema conform"),
        ("pct_correct_tool", "correct tool"),
        ("pct_emitted", "emitted"),
    ),
    "recovery": (
        ("pct_recovered", "recovered"),
        ("pct_looped", "looped"),
        ("pct_repeated_failing_call", "repeated failing call"),
    ),
    "thinking": (
        ("pct_no_think_leak", "no think leak"),
        ("pct_nonempty_short_budget", "non-empty short budget"),
        ("pct_thinking_off_honoured", "thinking-off honoured"),
    ),
}


def from_code(payload: dict) -> BenchResult:
    cr = payload.get("code_results") or {}
    repeats = int(payload.get("repeats") or 1)
    subjects: list[Subject] = []
    for suite, fields in _CODE_SUITE_FIELDS.items():
        block = cr.get(suite)
        if not isinstance(block, dict):
            continue
        n_turns = int(block.get("turns_scored") or 0) or repeats
        metrics = [_pct(k, lbl, block.get(k), n=n_turns) for k, lbl in fields]
        bug = block.get("count_empty_object_bug")
        if bug is not None:
            metrics.append(
                MetricValue(
                    "count_empty_object_bug",
                    "empty-object bugs",
                    _num(bug),
                    n=repeats,
                    direction="lower",
                )
            )
        hero = metrics[0] if metrics else None
        subjects.append(
            Subject(
                label=suite,
                engine=_fmt(payload.get("engine")),
                model=_fmt(payload.get("model")),
                hero=hero,
                metrics=[m for m in metrics if m.value is not None],
            )
        )
    # Judge suites: a first-class subject either way — graded runs carry a
    # labeled judge score, ungraded runs a hero-less subject that renderers
    # MUST show as "not graded" (missing ≠ zero), never blended into the
    # deterministic headline.
    gates: list[Gate] = []
    for suite in ("coding", "coding_hard"):
        block = cr.get(suite)
        if not isinstance(block, dict):
            continue
        tasks = block.get("tasks") or []
        judged = sum(1 for t in tasks if (t.get("judge") or {}).get("scores"))
        errored = sum(1 for t in tasks if (t.get("judge") or {}).get("error"))
        all_scores = [
            _num(v)
            for t in tasks
            for v in ((t.get("judge") or {}).get("scores") or {}).values()
            if _num(v) is not None
        ]
        hero = None
        if all_scores:
            hero = MetricValue(
                "judge_score",
                "judge score",
                round(sum(all_scores) / len(all_scores) * 10, 1),
                "%",
                n=judged,
                direction="higher",
                caveat="LLM-judged (0-10 criteria scaled to %)",
            )
        subjects.append(
            Subject(
                label=suite.replace("_", "-"),
                engine=_fmt(payload.get("engine")),
                model=_fmt(payload.get("model")),
                hero=hero,
                metrics=[
                    MetricValue(
                        "transcripts",
                        "transcripts captured",
                        float(len(tasks)),
                        n=len(tasks),
                        direction="neutral",
                    )
                ],
            )
        )
        if judged == 0 and tasks:
            gates.append(
                Gate(f"{suite}_judge", True, "judge offline — transcripts captured, not graded")
            )
        elif errored:
            gates.append(Gate(f"{suite}_judge", False, f"{errored} judge errors"))
        elif judged:
            gates.append(Gate(f"{suite}_judge", True, f"judged {judged}/{len(tasks)} tasks"))

    return BenchResult(
        bench_type="code",
        title=f"Dev quality — {payload.get('model', '?')} on {payload.get('engine', '?')}",
        subjects=subjects,
        winner=None,
        conditions={
            **_base_conditions(payload),
            "suites": ", ".join(payload.get("suites") or []),
            **({"runs_per_prompt": str(payload["repeats"])} if payload.get("repeats") else {}),
        },
        gates=gates,
        provenance=_provenance(payload),
        headline=_headline_metric("code", payload),
        raw=payload,
    )


def from_language(payload: dict) -> BenchResult:
    lr = payload.get("language_results") or {}
    metrics: list[MetricValue] = []
    adh = lr.get("adherence") or {}
    if adh:
        metrics += [
            _pct("pct_in_language", "in language", adh.get("pct_in_language")),
            MetricValue(
                "mean_adherence_ratio",
                "mean adherence ratio",
                _num(adh.get("mean_adherence_ratio")),
                direction="higher",
            ),
            _pct("pct_non_degenerate", "non-degenerate", adh.get("pct_non_degenerate")),
            MetricValue(
                "mean_accent_density",
                "accent density",
                _num(adh.get("mean_accent_density")),
                direction="neutral",
            ),
        ]
    dia = lr.get("diacritics") or {}
    if dia and not dia.get("skipped"):
        metrics += [
            _pct("pct_traps_passed", "diacritic traps passed", dia.get("pct_traps_passed")),
            MetricValue(
                "count_ascii_stripped",
                "ASCII-stripped answers",
                _num(dia.get("count_ascii_stripped")),
                direction="lower",
            ),
        ]
    gates: list[Gate] = []
    if payload.get("fully_populated") is False:
        gates.append(
            Gate(
                "dataset_coverage",
                False,
                "partial coverage: adherence only, diacritic traps not populated",
            )
        )
    flu = lr.get("fluency") or {}
    if flu.get("error"):
        gates.append(Gate("fluency_judge", False, _fmt(flu.get("error"))))
    elif flu.get("skipped"):
        gates.append(Gate("fluency_judge", True, "judge offline — fluency not scored"))
    elif flu.get("scores"):
        gates.append(Gate("fluency_judge", True, f"scored by {_fmt(flu.get('judge_model'))}"))

    lang = _fmt(payload.get("language_name") or payload.get("language"))
    # Reuse the instance already in metrics so the renderer never
    # prints the same metric twice (dedup is by identity).
    hero = metrics[0] if metrics else None
    return BenchResult(
        bench_type="language",
        title=f"Language retention ({lang}) — {payload.get('model', '?')}",
        subjects=[
            Subject(
                label=lang or "language",
                engine=_fmt(payload.get("engine")),
                model=_fmt(payload.get("model")),
                hero=hero,
                metrics=[m for m in metrics if m.value is not None],
            )
        ],
        winner=None,
        conditions={**_base_conditions(payload), "suites": ", ".join(payload.get("suites") or [])},
        gates=gates,
        provenance=_provenance(payload),
        headline=_headline_metric("language", payload),
        raw=payload,
    )


_INSTRUCT_BLOCKS: tuple[tuple[str, str], ...] = (
    ("verifiable", "verifiable (IFEval-style)"),
    ("research_brief", "research brief"),
    ("research_brief_deep", "research brief (deep)"),
    ("order_control", "order control"),
    ("loop_search_short", "loop search (short)"),
    ("loop_search_unconfirmable", "loop search (unconfirmable)"),
    ("honesty_audit", "honesty audit"),
    ("multi_file_scope", "multi-file scope"),
    ("constraint_preservation", "constraint preservation"),
)


def from_instruct(payload: dict) -> BenchResult:
    ir = payload.get("instruct_results") or {}
    subjects: list[Subject] = []
    for key, label in _INSTRUCT_BLOCKS:
        block = ir.get(key)
        if not isinstance(block, dict):
            continue
        n = int(block.get("prompts_scored") or 0)
        metrics = [
            _pct(k, k.replace("pct_", "").replace("_", " "), v, n=n)
            if k.startswith("pct_")
            else MetricValue(k, k.replace("_", " "), _num(v), n=n, direction="higher")
            for k, v in block.items()
            if k.startswith(("pct_", "mean_", "prompt_level_", "instruction_level_"))
            and _num(v) is not None
        ]
        hero = next(
            (m for m in metrics if m.key in ("prompt_level_strict", "pct_primary_delivered")),
            metrics[0] if metrics else None,
        )
        subjects.append(
            Subject(
                label=label,
                engine=_fmt(payload.get("engine")),
                model=_fmt(payload.get("model")),
                hero=hero,
                metrics=metrics,
            )
        )
    return BenchResult(
        bench_type="instruct",
        title=f"Instruction following — {payload.get('model', '?')} "
        f"on {payload.get('engine', '?')}",
        subjects=subjects,
        winner=None,
        conditions={
            **_base_conditions(payload),
            "scenarios": ", ".join(payload.get("scenarios") or []),
            **({"runs_per_prompt": str(payload["repeats"])} if payload.get("repeats") else {}),
        },
        gates=[],
        provenance=_provenance(payload),
        headline=_headline_metric("instruct", payload),
        raw=payload,
    )


def from_thinking_ablation(payload: dict) -> BenchResult:
    subjects: list[Subject] = []
    for cell in payload.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        n_turns = int(cell.get("turns") or 0)
        hero = _pct("pct_clean", "clean", cell.get("pct_clean"), n=n_turns)
        metrics = [
            MetricValue(
                "latency_ms_mean",
                "latency/turn",
                _num(cell.get("latency_ms_mean")),
                "ms",
                direction="lower",
            ),
            MetricValue(
                "ctx_growth",
                "context growth",
                _num(cell.get("ctx_growth")),
                "tok",
                direction="lower",
            ),
            MetricValue(
                "reasoning_chars_mean",
                "think chars/turn",
                _num(cell.get("reasoning_chars_mean")),
                direction="neutral",
            ),
        ]
        subjects.append(
            Subject(
                label=_fmt(cell.get("config")) or "cell",
                engine=_fmt(payload.get("engine")),
                model=_fmt(payload.get("model")),
                hero=hero,
                metrics=[m for m in metrics if m.value is not None],
            )
        )
    return BenchResult(
        bench_type="thinking-ablation",
        title=f"Thinking ablation — {payload.get('model', '?')} on {payload.get('engine', '?')}",
        subjects=subjects,
        winner=None,
        conditions={**_base_conditions(payload), "load": _fmt(payload.get("load"))},
        gates=[],
        provenance=_provenance(payload),
        headline=_headline_metric("thinking-ablation", payload),
        raw=payload,
    )


_ADAPTERS = {
    "standard": from_standard,
    "agentic": from_agentic,
    "burst": from_burst,
    "code": from_code,
    "language": from_language,
    "instruct": from_instruct,
    "thinking-ablation": from_thinking_ablation,
}


# Every gate name build_result() can emit, by bench type. This is the list
# --fail-on-gate is checked against: a name outside it is a typo or a gate that
# does not exist, and asking to enforce it must fail loudly. On 2026-09-02 a
# campaign ran with --fail-on-gate session_replay for a gate this module never
# built — the flag filtered a name that could not match, and a control cell with
# five replayed runs passed green. A list the code owns cannot drift from the
# code; a list in a shell script can.
DOCUMENTED_GATES: dict[str, frozenset[str]] = {
    "standard": frozenset({"thermal", "memory_pressure", "energy_provenance", "energy_thermal"}),
    "agentic": frozenset(
        {
            "early_stop",
            "memory_pressure",
            "duplicate_processes",
            "output_validity",
            "session_replay",
            "bank_preload",
            "thermal",
            "thinking",
            "other_engines_resident",
        }
    ),
}


def build_result(bench_type: str, payload: dict) -> BenchResult:
    """Build the unified result view for any bench type's payload."""
    adapter = _ADAPTERS.get(bench_type)
    if adapter is None:
        raise ValueError(f"unknown bench type: {bench_type!r}")
    return adapter(payload)
