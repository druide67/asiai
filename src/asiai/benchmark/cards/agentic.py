"""Agentic prefix-cache card (spec §3 AGENTIC)."""

from __future__ import annotations

from asiai.benchmark.cards._frame import (
    ACCENT,
    ACCENT_DIM,
    BAR_NEUTRAL,
    SANS,
    TEXT,
    TEXT2,
    bar_row,
    body_y0,
    chip,
    chrome_close,
    chrome_open,
    fmt_num,
    gates_row,
    metric_map,
    mono_w,
    rrect,
    text,
    wrap_text,
)
from asiai.benchmark.result_model import BenchResult

# Reading order, not measurement order: the phases someone actually decides on
# come first. "cold" is the number you pay once, "warm" the one you live with,
# "long-context" the one that says whether the model still works at depth.
_PHASE_ORDER = ("cold", "warm", "cold-prefix", "prefix_warm", "long-context", "long-prefix")

# Phase labels are internal names; these are what they mean to a reader.
_PHASE_LABEL = {
    "cold": "first call",
    "warm": "warm",
    "cold-prefix": "cold + prefix",
    "long-context": "long context",
    "long-prefix": "long + prefix",
}


def _thousands(n: float) -> str:
    """5839 -> '5.8k'. Context depths are read as magnitudes, not as exact counts."""
    return f"{n / 1000:.0f}k" if n >= 9500 else f"{n / 1000:.1f}k"


def render(result: BenchResult) -> str:
    subject = result.subjects[0] if result.subjects else None
    m = metric_map(subject) if subject else {}
    verdict = str(m["verdict"].value) if m.get("verdict") and m["verdict"].value else "?"
    fraction = (
        float(subject.hero.value)
        if subject and subject.hero and isinstance(subject.hero.value, (int, float))
        else None
    )

    quant = result.conditions.get("quantizations", "")
    model_chips = [(quant, "neutral")] if quant else []
    if subject:
        ver = m.get("engine_version")
        model_chips.append(
            (f"{subject.engine} {ver.value}" if ver and ver.value else subject.engine, "neutral")
        )
    # Speculative decoding changes the headline number by tens of percent, so a
    # card that omits it is not merely incomplete — two cards of the same model
    # on the same machine then differ by 45% with identical declared conditions,
    # and a reader comparing the images can only conclude one of them is wrong.
    # It rides next to the engine name, where the reader already looks.
    spec = (result.raw.get("engine_config") or {}).get("speculative")
    if isinstance(spec, dict) and spec.get("type"):
        cap = spec.get("draft_n_max")
        model_chips.append((f"{spec['type']}{f' cap {cap}' if cap else ''}", "neutral"))

    p = [
        chrome_open(
            result,
            suite_label="agentic",
            section_tag="AGENTIC",
            model_chips=model_chips,
        )
    ]

    # ── phases, ordered for reading ──────────────────────────────────
    phases = [(k.removeprefix("ttft_"), m[k]) for k in m if k.startswith("ttft_")]
    phases.sort(key=lambda kv: _PHASE_ORDER.index(kv[0]) if kv[0] in _PHASE_ORDER else 99)
    phases = phases[:4]

    def decode_of(phase: str) -> float | None:
        mv = m.get(f"decode_{phase}")
        return float(mv.value) if mv and isinstance(mv.value, (int, float)) else None

    # ── hero column: the number the card is FOR ──────────────────────
    # It used to be the prefix-cache verdict, a diagnostic signal that means
    # nothing outside its own engine family — while throughput, the one figure
    # every reader came for, sat in 11px type at the right edge (and was clipped
    # there). Sustained throughput leads; the cache verdict stays, demoted.
    depths = result.raw.get("context_depth") or {}
    warm_tps = decode_of("warm") or decode_of("cold")
    if warm_tps is not None:
        p.append(text(54, 240, fmt_num(warm_tps), size=64, weight=700, fill=ACCENT))
        hx = 54 + mono_w(fmt_num(warm_tps), 64) + 12
        p.append(text(hx, 240, "tok/s", size=17, family=SANS, fill=TEXT2))
        short = (depths.get("short") or {}).get("median") or depths.get("median")
        sub = "sustained, warm cache"
        if isinstance(short, (int, float)) and short:
            sub += f" · {_thousands(short)} ctx"
        p.append(text(54, 264, sub, size=13, family=SANS, fill=TEXT2))

    # Second line: does it hold at depth? A model that collapses at long context
    # is a different product from one that does not, and one number cannot say so.
    long_tps = decode_of("long-context")
    deep = (depths.get("long") or {}).get("median") or depths.get("max")
    yb = 300
    if long_tps is not None:
        label = "at depth"
        if isinstance(deep, (int, float)) and deep:
            label = f"at {_thousands(deep)} ctx"
        p.append(text(54, yb, label, size=13, family=SANS, fill=TEXT2))
        deep_tps = f"{fmt_num(long_tps)} t/s"
        p.append(text(190, yb, deep_tps, size=15, weight=700, fill=TEXT))
        if warm_tps:
            drop = (long_tps - warm_tps) / warm_tps * 100
            x_drop = 190 + mono_w(deep_tps, 15) + 10
            p.append(text(x_drop, yb, f"{drop:+.0f}%", size=13, fill=TEXT2))
        yb += 26

    if fraction is not None:
        p.append(text(54, yb, "prefix reuse", size=13, family=SANS, fill=TEXT2))
        p.append(text(190, yb, f"{verdict} {fraction:.2f}", size=15, weight=700, fill=TEXT))
        p.append(rrect(54, yb + 12, 280, 6, 3, fill=ACCENT_DIM))
        p.append(rrect(54, yb + 12, max(2, min(1.0, fraction) * 280), 6, 3, fill=ACCENT))
        yb += 32
    caveat = "prefix reuse is engine-family-specific — compare the raw signal, not across families"
    p.append(wrap_text(54, yb + 6, caveat, 300, size=11))

    # ── phase bars, scaled by THROUGHPUT ─────────────────────────────
    # They used to be scaled by TTFT, so the slowest phase drew the longest bar
    # and the card read backwards at a glance. Bars now mean what bars mean:
    # longer is faster. TTFT keeps its place in the value text, where a number
    # that is better when small belongs.
    tps_max = max((t for t in (decode_of(ph) for ph, _ in phases) if t), default=0.0)
    # Four bars used to occupy a third of the panel and leave the rest blank.
    # A card is read at thumbnail size on a timeline: the bars ARE the picture,
    # so they get the room.
    pitch, bar_h = 44, 28
    y0 = body_y0(len(phases) * pitch - (pitch - bar_h) + 60)
    for i, (phase, mv) in enumerate(phases):
        ttft = float(mv.value) if isinstance(mv.value, (int, float)) else 0.0
        tps = decode_of(phase)
        value = f"{fmt_num(tps)} t/s · {ttft:.0f}ms" if tps is not None else f"TTFT {ttft:.0f}ms"
        p.append(
            bar_row(
                y0 + i * pitch,
                _PHASE_LABEL.get(phase, phase),
                (tps / tps_max) if (tps and tps_max) else 0,
                value,
                bar_color=BAR_NEUTRAL if phase == "cold" else ACCENT,
                label_color=TEXT if phase != "cold" else TEXT2,
                height=bar_h,
                value_size=11.5,
            )
        )

    # chips under the bars
    cy = y0 + len(phases) * pitch + 6
    cx = 482.0
    chips: list[str] = []
    rss_peak, rss_warm = m.get("engine_rss_peak_mb"), m.get("engine_rss_warm_mb")
    if rss_peak and isinstance(rss_peak.value, (int, float)):
        label = f"RSS peak {fmt_num(rss_peak.value, 0)} MB"
        if rss_warm and isinstance(rss_warm.value, (int, float)):
            label += f" · warm {fmt_num(rss_warm.value, 0)} MB"
        chips.append(label)
    if subject and subject.hero and subject.hero.n:
        chips.append(f"n={subject.hero.n} runs")
    for label in chips:
        svg, w = chip(cx, cy, label)
        p.append(svg)
        cx += w + 8

    p.append(gates_row(result, 424))
    p.append(chrome_close(result))
    return "".join(p)
