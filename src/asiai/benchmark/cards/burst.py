"""Burst concurrency card (spec §3 BURST)."""

from __future__ import annotations

from asiai.benchmark.cards._frame import (
    ACCENT,
    BAR_MAX_W,
    BAR_NEUTRAL,
    BAR_X,
    SANS,
    TEXT,
    TEXT2,
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
)
from asiai.benchmark.result_model import BenchResult, Subject


def _metric(s: Subject, key: str) -> float | None:
    m = metric_map(s).get(key)
    if key == "p95_ms":
        m = s.hero
    return float(m.value) if m and isinstance(m.value, (int, float)) else None


def render(result: BenchResult) -> str:
    subjects = result.subjects  # one per burst size, ordered
    quant = result.conditions.get("quantizations", "")
    model_chips = [(quant, "neutral")] if quant else []
    if subjects:
        model_chips.append((subjects[0].engine, "neutral"))

    p = [
        chrome_open(
            result,
            suite_label="burst",
            section_tag="BURST",
            model_chips=model_chips,
        )
    ]

    # Shared scale: max p99 (fall back to p95) across groups (spec §3).
    vmax = max(
        (v for s in subjects for v in (_metric(s, "p99_ms") or _metric(s, "p95_ms"),) if v),
        default=0.0,
    )

    # ── hero: p95 @ max size ─────────────────────────────────────────
    last = subjects[-1] if subjects else None
    if last:
        p95 = _metric(last, "p95_ms")
        hero = fmt_num(p95, 0) if p95 is not None else "—"
        p.append(text(54, 234, hero, size=64, weight=700, fill=ACCENT))
        p.append(text(54 + mono_w(hero, 64) + 8, 234, "ms", size=22, fill=ACCENT))
        size_label = last.label.removeprefix("burst-")
        p.append(
            text(
                54,
                264,
                f"p95 latency @ {size_label} concurrent calls",
                size=13,
                family=SANS,
                fill=TEXT2,
            )
        )
        cy, cx = 288.0, 54.0
        agg = _metric(last, "agg_tok_s")
        if agg is not None:
            svg, w = chip(cx, cy, f"{fmt_num(agg, 0)} tok/s aggregate", style="accent")
            p.append(svg)
            cx += w + 8
        calls = _metric(last, "calls_per_s")
        if calls is not None:
            svg, w = chip(cx, cy, f"{fmt_num(calls)} calls/s")
            p.append(svg)
            cx += w + 8
        wall = _metric(last, "wall_s")
        if wall is not None:
            svg, w = chip(54, cy + 28, f"wall {fmt_num(wall)}s")
            p.append(svg)

    # ── groups: slim p50/p95/p99 bars per size ───────────────────────
    group_h = 3 * 17 + 22  # 3 slim bars + header
    y0 = body_y0(len(subjects) * group_h - 6)
    for s in subjects[:4]:
        size_label = s.label.removeprefix("burst-")
        p.append(text(BAR_X - 100, y0 + 10, f"{size_label} calls", size=12, fill=TEXT))
        row_y = y0 + 18
        for pct in ("p50", "p95", "p99"):
            key = f"{pct}_ms"
            v = _metric(s, key)
            if v is None:
                continue
            w = min(1.0, v / vmax) * BAR_MAX_W if vmax else 0
            color = ACCENT if pct == "p95" else BAR_NEUTRAL
            p.append(text(BAR_X - 12, row_y + 10, pct, size=11, fill=TEXT2, anchor="end"))
            p.append(rrect(BAR_X, row_y, max(w, 2), 12, 3, fill=color))
            value = f"{fmt_num(v, 0)}ms"
            if pct == "p99":
                vm = _metric(s, "max_ms")
                if vm is not None:
                    value += f" · max {fmt_num(vm, 0)}"
            p.append(text(BAR_X + BAR_MAX_W + 12, row_y + 10, value, size=11, fill=TEXT2))
            row_y += 17
        y0 += group_h

    p.append(gates_row(result, 424))
    p.append(chrome_close(result))
    return "".join(p)
