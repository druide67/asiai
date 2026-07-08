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
    rrect,
    text,
    wrap_text,
)
from asiai.benchmark.result_model import BenchResult

_PHASE_ORDER = ("cold", "prefix_warm", "warm")


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

    p = [
        chrome_open(
            result,
            suite_label="agentic",
            section_tag="AGENTIC",
            model_chips=model_chips,
        )
    ]

    # ── hero column (330 wide — word hero) ───────────────────────────
    p.append(text(54, 226, verdict, size=52, weight=700, fill=ACCENT))
    if fraction is not None:
        p.append(text(54, 268, f"{fraction:.2f}", size=34, weight=700, fill=TEXT))
        p.append(
            text(
                54 + len(f"{fraction:.2f}") * 0.602 * 34 + 10,
                268,
                "prefix-cache reuse fraction",
                size=12,
                family=SANS,
                fill=TEXT2,
            )
        )
        p.append(rrect(54, 284, 280, 10, 5, fill=ACCENT_DIM))
        p.append(rrect(54, 284, max(2, min(1.0, fraction) * 280), 10, 5, fill=ACCENT))
    caveat = "engine-family-specific — compare the raw signal, not across families"
    p.append(wrap_text(54, 322, caveat, 300, size=12))

    # ── phase bars ───────────────────────────────────────────────────
    phases = [(k.removeprefix("ttft_"), m[k]) for k in m if k.startswith("ttft_")]
    phases.sort(key=lambda kv: _PHASE_ORDER.index(kv[0]) if kv[0] in _PHASE_ORDER else 9)
    ttft_max = max(
        (float(mv.value) for _, mv in phases if isinstance(mv.value, (int, float))), default=0.0
    )
    pitch = 31
    y0 = body_y0(len(phases) * pitch - 9 + 60)
    for i, (phase, mv) in enumerate(phases[:4]):
        v = float(mv.value) if isinstance(mv.value, (int, float)) else 0.0
        decode = m.get(f"decode_{phase}")
        value = f"TTFT {v:.0f}ms"
        if mv.caveat.startswith("CV="):
            try:
                value += f" CV{float(mv.caveat.removeprefix('CV=')) * 100:.0f}%"
            except ValueError:
                pass
        if decode and isinstance(decode.value, (int, float)):
            value += f" · {fmt_num(decode.value)} tok/s"
        p.append(
            bar_row(
                y0 + i * pitch,
                phase,
                (v / ttft_max) if ttft_max else 0,
                value,
                bar_color=BAR_NEUTRAL if phase == "cold" else ACCENT,
                label_color=TEXT if phase != "cold" else TEXT2,
                value_size=11.5,
            )
        )

    # chips under the bars
    cy = y0 + len(phases[:4]) * pitch + 8
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
