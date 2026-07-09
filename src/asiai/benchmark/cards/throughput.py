"""Throughput card — normal, single-engine, no-winner and tie states.

Spec §3 THROUGHPUT + §4 (no-winner, tie). The honesty rules drive the
branching: when a ranking is withheld (validity gate, tie, single
engine) nothing may read as a crown — neutral bars, alphabetical order,
an explicit "not a ranking" legend.
"""

from __future__ import annotations

from asiai.benchmark.cards._frame import (
    ACCENT,
    AMBER,
    BAR_NEUTRAL,
    RED,
    SANS,
    TEXT,
    TEXT2,
    bar_row,
    body_y0,
    chip,
    chrome_close,
    chrome_open,
    ci_whisker,
    fmt_num,
    metric_map,
    mono_w,
    text,
    wrap_text,
)
from asiai.benchmark.result_model import BenchResult, Subject


def _hero_value(s: Subject) -> float:
    return float(s.hero.value) if s.hero and isinstance(s.hero.value, (int, float)) else 0.0


def _engine_label(s: Subject) -> str:
    ver = metric_map(s).get("engine_version")
    return f"{s.label} {ver.value}" if ver and ver.value else s.label


def render(result: BenchResult) -> str:
    subjects = sorted(result.subjects, key=lambda s: _hero_value(s), reverse=True)
    is_tie = bool(result.co_leaders)
    no_winner = result.winner is None and not is_tie and len(subjects) >= 2
    single = len(subjects) == 1
    if no_winner or is_tie:
        subjects = sorted(result.subjects, key=lambda s: s.label)  # alphabetical — no crown

    quant = result.conditions.get("quantizations", "")
    model_chips = [(quant, "neutral")] if quant else []
    if single and subjects:
        model_chips.append((_engine_label(subjects[0]), "neutral"))

    rail = AMBER if no_winner else ACCENT
    p = [
        chrome_open(
            result,
            rail=rail,
            suite_label="throughput",
            section_tag="THROUGHPUT",
            legend=(
                "tok/s shown for transparency · not a ranking"
                if no_winner
                else "bar shows measured tok/s at 100% of its own scale · not a ranking"
                if single
                else "▬ whisker = ±CI95 · co-leader whiskers overlap → tie"
                if is_tie
                else ""
            ),
            model_chips=model_chips,
        )
    ]

    vmax = max((_hero_value(s) for s in subjects), default=0.0)
    winner = next((s for s in result.subjects if s.label == result.winner), None)

    # ── hero column ──────────────────────────────────────────────────
    if is_tie:
        p.append(text(54, 232, "TIE", size=52, weight=700, fill=ACCENT))
        y = 262
        for name in result.co_leaders:
            s = next((x for x in result.subjects if x.label == name), None)
            if s:
                p.append(
                    text(54, y, f"{name}  {fmt_num(_hero_value(s))} tok/s", size=15, fill=TEXT)
                )
                y += 22
        p.append(
            wrap_text(
                54,
                y + 8,
                result.winner_note or "ranking withheld — Δ inside the combined CI95",
                300,
            )
        )
        # §5.1: the headline never goes naked — carry the sample count.
        ns = sorted(
            {
                x.hero.n
                for x in result.subjects
                if x.label in result.co_leaders and x.hero and x.hero.n
            }
        )
        if ns:
            n_label = (
                f"n={ns[0]} runs each" if len(ns) == 1 else "n=" + "/".join(map(str, ns)) + " runs"
            )
            p.append(text(54, y + 66, f"{n_label} · same prompt set", size=12, fill=TEXT2))
        if len(result.co_leaders) >= 2:
            a, b = (next(x for x in result.subjects if x.label == n) for n in result.co_leaders[:2])
            svg, _w = chip(
                54,
                y + 84,
                f"tie: Δ {fmt_num(abs(_hero_value(a) - _hero_value(b)))} < CI95 overlap",
                style="accent",
            )
            p.append(svg)
    elif no_winner:
        invalid = [s.label for s in subjects if _subject_invalid(s)]
        if invalid:
            # Only claim the validity gate when it actually fired — a
            # fabricated gate on an old/zero-tok payload would be the
            # exact dishonesty this card exists to prevent.
            svg, _ = chip(54, 176, "✗ output_validity", style="red", size=12, height=24)
            p.append(svg)
        p.append(text(54, 240, "no winner declared", size=34, family=SANS, weight=700, fill=TEXT))
        note = result.winner_note or (
            "the output validity gate refused the ranking"
            if invalid
            else "no comparable measurements — ranking unavailable"
        )
        if not invalid and "validity" in note:
            note = "no comparable measurements — ranking unavailable"
        p.append(wrap_text(54, 268, note, 300))
        if invalid:
            p.append(
                text(
                    54,
                    340,
                    f"{len(invalid)} of {len(subjects)} engines produced invalid output",
                    size=13,
                    fill=AMBER,
                )
            )
    elif subjects:
        top = winner or subjects[0]
        hero_v = fmt_num(_hero_value(top))
        p.append(text(54, 240, hero_v, size=74, weight=700, fill=ACCENT))
        p.append(text(54 + mono_w(hero_v, 74) + 8, 240, "tok/s", size=23, fill=ACCENT))
        sub = []
        if top.hero and top.hero.ci95:
            sub.append(f"±{fmt_num(top.hero.ci95[1] - _hero_value(top))} CI95")
        if top.hero and top.hero.n:
            sub.append(f"n={top.hero.n} runs")
        if sub:
            p.append(text(54, 270, " · ".join(sub), size=14, fill=TEXT2))
        if single:
            p.append(
                text(54, 322, "single engine — no comparison", size=14, family=SANS, fill=TEXT2)
            )
        elif len(subjects) >= 2:
            runner = subjects[1] if subjects[0] is top else subjects[0]
            rv = _hero_value(runner)
            if rv > 0:
                p.append(
                    text(54, 330, f"{_hero_value(top) / rv:.1f}×", size=30, weight=700, fill=TEXT)
                )
                p.append(
                    text(
                        54 + mono_w(f"{_hero_value(top) / rv:.1f}×", 30) + 8,
                        330,
                        f"vs {runner.label}",
                        size=14,
                        family=SANS,
                        fill=TEXT2,
                    )
                )
            p.append(text(54, 366, f"{_engine_label(top)} wins", size=14, fill=ACCENT))

    # ── bars ─────────────────────────────────────────────────────────
    pitch = 31
    y0 = body_y0(len(subjects) * pitch - 9)
    for i, s in enumerate(subjects):
        v = _hero_value(s)
        invalid = no_winner and _subject_invalid(s)
        is_leader = (
            (result.winner == s.label)
            or (is_tie and s.label in result.co_leaders)
            or (single and not no_winner)
        )
        color = ACCENT if is_leader and not no_winner else BAR_NEUTRAL
        value = f"{fmt_num(v)}"
        if s.hero and s.hero.ci95:
            value += f" ±{fmt_num(s.hero.ci95[1] - v)}"
        if invalid:
            value += " · invalid ✗"
        y = y0 + i * pitch
        p.append(
            bar_row(
                y,
                s.label,
                (v / vmax) if vmax else 0,
                value,
                bar_color=color,
                label_color=ACCENT
                if is_tie and s.label in result.co_leaders
                else (TEXT if is_leader else TEXT2),
                value_color=RED if invalid else (TEXT if is_leader else TEXT2),
            )
        )
        if is_tie and s.hero and s.hero.ci95:
            p.append(
                ci_whisker(y, v, s.hero.ci95[1] - v, vmax, on_accent=s.label in result.co_leaders)
            )

    # ── bottom block: per-engine chip rows (spec: rows OR gates, not both) ──
    p.append(_engine_chip_rows(result, subjects, winner))
    p.append(chrome_close(result))
    return "".join(p)


def _subject_invalid(s: Subject) -> bool:
    """Invalid = below the SAME threshold the ranking gate uses — an
    engine at 95% is rankable and must not be branded invalid."""
    from asiai.benchmark.output_gates import DEFAULT_MIN_VALID_PCT

    validity = metric_map(s).get("output_valid_pct")
    return bool(
        validity
        and isinstance(validity.value, (int, float))
        and validity.value < DEFAULT_MIN_VALID_PCT
    )


def _engine_chip_rows(result: BenchResult, subjects: list[Subject], winner: Subject | None) -> str:
    """One chip row per engine under the divider (≤4 rows, pitch 27)."""
    stroke = 'stroke="rgba(255,255,255,0.05)" stroke-width="1"'
    p = [f'<line x1="54" y1="424" x2="1146" y2="424" {stroke}/>']
    y = 436
    for s in subjects[:4]:
        m = metric_map(s)
        label_color = ACCENT if winner is s else TEXT2
        p.append(text(54, y + 14, _engine_label(s)[:20], size=12, fill=label_color))
        cx = 192.0
        chips: list[str] = []
        if m.get("median_ttft_ms"):
            chips.append(f"{fmt_num(m['median_ttft_ms'].value, 0)}ms TTFT")
        if m.get("p90_tok_s"):
            chips.append(f"p90 {fmt_num(m['p90_tok_s'].value)}")
        if m.get("vram_gb"):
            chips.append(f"{fmt_num(m['vram_gb'].value)} GB VRAM")
        watts = m.get("avg_soc_watts") or m.get("avg_power_watts")
        if watts:  # only when measured — never faked (spec §5)
            power = f"{fmt_num(watts.value, 0)}W"
            if m.get("avg_tok_s_per_soc_watt"):
                power += f" · {fmt_num(m['avg_tok_s_per_soc_watt'].value)} tok/s/W"
            if m.get("avg_energy_per_token_j"):
                power += f" · {fmt_num(m['avg_energy_per_token_j'].value, 2)} J/tok"
            chips.append(power)
        for label in chips:
            svg, w = chip(cx, y, label)
            p.append(svg)
            cx += w + 8
        stability = m.get("stability")
        if stability and stability.value:
            style = "amber" if "variance" in str(stability.value) else "neutral"
            svg, w = chip(cx, y, str(stability.value), style=style)
            p.append(svg)
        y += 27
    return "".join(p)
