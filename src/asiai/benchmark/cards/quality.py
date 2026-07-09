"""Quality card — code / language / instruct / thinking-ablation
(spec §3 QUALITY + §4 judge-offline).

One layout for the four quality bench types: full-width threshold-
colored suite bars with sub-metric lines. The judge-offline state is a
first-class design, not an error: ungraded suites render as dashed
placeholders — never a zeroed bar on a scored track (spec §5 rule 4).
"""

from __future__ import annotations

from asiai.benchmark.cards._frame import (
    ACCENT,
    AMBER,
    AMBER_DIM_TEXT,
    AMBER_FILL,
    AMBER_STROKE,
    BAR_MAX_W,
    BAR_X,
    GREEN,
    RED,
    TEXT,
    TEXT2,
    TEXT3,
    TRACK,
    body_y0,
    chrome_close,
    chrome_open,
    fmt_num,
    gates_row,
    metric_map,
    rrect,
    text,
)
from asiai.benchmark.result_model import BenchResult, Subject

_SECTION_TAGS = {
    "code": "CODE",
    "language": "LANGUAGE",
    "instruct": "INSTRUCT",
    "thinking-ablation": "THINKING",
}


def _threshold_color(score: float) -> str:
    if score >= 85:
        return GREEN
    if score >= 60:
        return AMBER
    return RED


def _score(s: Subject) -> float | None:
    if s.hero and isinstance(s.hero.value, (int, float)):
        return float(s.hero.value)
    return None


def _subline(s: Subject, judge_offline: bool) -> str:
    m = metric_map(s)
    parts = [
        f"{mv.label} {fmt_num(mv.value, 2 if isinstance(mv.value, float) and mv.value < 2 else 0)}"
        for key, mv in m.items()
        if mv is not s.hero and isinstance(mv.value, (int, float))
    ]
    line = " · ".join(parts[:6])
    if judge_offline:
        line += " · mechanical, no judge" if line else "mechanical, no judge"
    return line


def render(result: BenchResult) -> str:
    judge_offline = any("judge offline" in g.detail.lower() for g in result.gates)
    subjects = result.subjects
    dense = len(subjects) >= 6
    pitch = 44 if dense else 51

    quant = result.conditions.get("quantizations", "")
    model_chips = [(quant, "neutral")] if quant else []
    if subjects and subjects[0].engine:
        m = metric_map(subjects[0])
        ver = m.get("engine_version")
        model_chips.append(
            (
                f"{subjects[0].engine} {ver.value}" if ver and ver.value else subjects[0].engine,
                "neutral",
            )
        )

    p = [
        chrome_open(
            result,
            rail=AMBER if judge_offline else ACCENT,
            suite_label=result.bench_type
            if result.bench_type != "thinking-ablation"
            else "thinking",
            section_tag=_SECTION_TAGS.get(result.bench_type, "QUALITY"),
            legend="■ ≥85 ■ ≥60 ■ <60",
            model_chips=model_chips,
        )
    ]

    shown = subjects[:6]
    y = body_y0(len(shown) * pitch - 13)
    if judge_offline:
        # Notice strip above the bars (spec §4).
        p.append(rrect(54, 166, 1092, 30, 8, fill=AMBER_FILL, stroke=AMBER_STROKE))
        p.append(text(66, 186, "judge: offline", size=13, weight=700, fill=AMBER))
        p.append(
            text(
                66 + 13 * 0.602 * len("judge: offline") + 14,
                186,
                "transcripts captured, not graded · mechanical checks below are unaffected"
                " · re-run with --judge to grade",
                size=12,
                fill=AMBER_DIM_TEXT,
            )
        )
        y = max(y, 206.0)
    # The stack must never cross the GATES divider at 424: compress the
    # pitch when the notice strip + a dense suite set squeeze the band.
    if shown:
        pitch = min(pitch, (414 - y) / len(shown))

    label_x = BAR_X - 12
    draw_subline = pitch >= 40  # below that the subline would overlap the next bar
    for s in shown:
        score = _score(s)
        graded = score is not None
        p.append(
            text(
                label_x, y + 13, s.label[:18], size=13, fill=TEXT if graded else TEXT2, anchor="end"
            )
        )
        if graded:
            p.append(rrect(BAR_X, y, BAR_MAX_W + 100, 18, 4, fill=TRACK))
            w = max(2.0, min(1.0, score / 100) * (BAR_MAX_W + 100))
            p.append(rrect(BAR_X, y, w, 18, 4, fill=_threshold_color(score)))
            p.append(
                text(BAR_X + BAR_MAX_W + 112, y + 14, f"{fmt_num(score, 0)}%", size=14, fill=TEXT)
            )
        else:
            # Ungraded ≠ zero: dashed empty placeholder (spec §4/§5).
            p.append(
                rrect(
                    BAR_X,
                    y,
                    BAR_MAX_W + 100,
                    18,
                    4,
                    stroke="rgba(245,158,11,0.5)",
                    dash="4 3",
                )
            )
            placeholder = "not graded — judge offline" if judge_offline else "not graded"
            p.append(text(BAR_X + 10, y + 13, placeholder, size=11, fill=AMBER))
            p.append(text(BAR_X + BAR_MAX_W + 112, y + 14, "—", size=14, fill=TEXT2))
        subline = _subline(s, judge_offline)
        if subline and draw_subline:
            p.append(text(BAR_X + 12, y + (30 if dense else 32), subline[:95], size=11, fill=TEXT3))
        y += pitch

    extra = []
    n_runs = result.conditions.get("runs_per_prompt") or ""
    if n_runs:
        extra.append((f"n={n_runs} runs", "neutral"))
    if len(subjects) > 6:
        # Truncation is never silent (spec §5 spirit).
        extra.append((f"+{len(subjects) - 6} more suites — see report", "amber"))
    p.append(gates_row(result, 424, extra_chips=extra))
    p.append(chrome_close(result))
    return "".join(p)
