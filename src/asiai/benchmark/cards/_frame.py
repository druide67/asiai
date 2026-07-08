"""Shared chrome + primitives for the bench card family.

Implements the design handoff "asiai bench cards — SVG transcription
spec" (claude.ai/design, 2026-07-09): a 1200×630 OG card whose every
element is a rect, rounded rect, line or ``<text>`` — no filters, no
clips, no custom fonts. All geometry constants below are the measured
values from that spec; change them there first, here second.

The product's honesty rules are enforced by the layouts, but the
building blocks live here: gate badges always render (pass AND fail),
missing values are dashes or dashed placeholders (never zeroed bars),
and the conditions strip + provenance footer are part of the chrome —
a card without them cannot be assembled.
"""

from __future__ import annotations

import importlib.resources
import re
import time
from typing import Any
from xml.sax.saxutils import escape

from asiai.benchmark.result_model import BenchResult, MetricValue, Subject

# ── tokens (spec §1) ─────────────────────────────────────────────────
BG = "#0f1117"
PANEL = "#141824"
PANEL_BORDER = "rgba(255,255,255,0.05)"
CHIP = "#1c2130"
CHIP_BORDER = "rgba(255,255,255,0.07)"
BAR_NEUTRAL = "#39415a"
TRACK = "rgba(255,255,255,0.04)"
TEXT = "#eef1f7"
TEXT2 = "#8b93a7"
TEXT3 = "#5b6272"
CHIP_TEXT = "#aeb6c8"
CHIP_TEXT_HEADER = "#cdd3e0"
ACCENT = "#06b6d4"
ACCENT_DIM = "rgba(6,182,212,0.12)"
GREEN = "#10b981"
GREEN_FILL = "rgba(16,185,129,0.08)"
GREEN_STROKE = "rgba(16,185,129,0.35)"
AMBER = "#f59e0b"
AMBER_FILL = "rgba(245,158,11,0.08)"
AMBER_STROKE = "rgba(245,158,11,0.4)"
AMBER_DIM_TEXT = "#c9964a"
RED = "#ef4444"
RED_FILL = "rgba(239,68,68,0.1)"
RED_STROKE = "rgba(239,68,68,0.45)"
TRAFFIC = ("#ff5f57", "#febc2e", "#28c840")

MONO = "Menlo, Monaco, monospace"
SANS = "Helvetica, Arial, sans-serif"

# Approximate glyph advance per px of font-size (spec §6).
MONO_K = 0.602
SANS_K = 0.52

# Bar geometry (spec §2)
BAR_X = 482
BAR_MAX_W = 522
VALUE_X = 1016
LABEL_RIGHT = 470

# Panel body band (card coords)
BODY_Y = 166
BODY_H = 244


def esc(value: Any) -> str:
    return escape(str(value))


def mono_w(text: str, size: float) -> float:
    return len(str(text)) * MONO_K * size


def sans_w(text: str, size: float) -> float:
    return len(str(text)) * SANS_K * size


def text(
    x: float,
    y: float,
    content: str,
    *,
    size: float = 13,
    fill: str = TEXT,
    family: str = MONO,
    weight: int | None = None,
    anchor: str = "start",
    spacing: float | None = None,
) -> str:
    attrs = [
        f'x="{x:g}" y="{y:g}"',
        f'font-family="{family}" font-size="{size:g}" fill="{fill}"',
        f'text-anchor="{anchor}"' if anchor != "start" else "",
        f'font-weight="{weight}"' if weight else "",
        f'letter-spacing="{spacing:g}"' if spacing else "",
    ]
    return f"<text {' '.join(a for a in attrs if a)}>{esc(content)}</text>"


def rrect(
    x: float,
    y: float,
    w: float,
    h: float,
    rx: float,
    *,
    fill: str = "none",
    stroke: str = "",
    stroke_width: float = 1,
    dash: str = "",
) -> str:
    attrs = [
        f'x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="{rx:g}"',
        f'fill="{fill}"',
        f'stroke="{stroke}" stroke-width="{stroke_width:g}"' if stroke else "",
        f'stroke-dasharray="{dash}"' if dash else "",
    ]
    return f"<rect {' '.join(a for a in attrs if a)}/>"


# ── chips & badges ───────────────────────────────────────────────────

_CHIP_STYLES = {
    "neutral": (CHIP, CHIP_BORDER, CHIP_TEXT),
    "accent": (ACCENT_DIM, ACCENT, ACCENT),
    "green": (GREEN_FILL, GREEN_STROKE, GREEN),
    "amber": (AMBER_FILL, AMBER_STROKE, AMBER),
    "red": (RED_FILL, RED_STROKE, RED),
}


def chip(
    x: float,
    y: float,
    label: str,
    *,
    style: str = "neutral",
    size: float = 11.5,
    pad_x: float = 9,
    height: float = 20,
) -> tuple[str, float]:
    """One chip; returns (svg, total width) so rows can flow left→right."""
    fill, stroke, color = _CHIP_STYLES[style]
    w = mono_w(label, size) + 2 * pad_x
    svg = rrect(x, y, w, height, 6, fill=fill, stroke=stroke) + text(
        x + pad_x, y + height / 2 + size * 0.36, label, size=size, fill=color
    )
    return svg, w


def gate_badge(
    x: float, y: float, name: str, passed: bool, *, offline: bool = False
) -> tuple[str, float]:
    """Gate chip with its prefix glyph — gates are never hidden (spec §2)."""
    if offline:
        return chip(x, y, f"◌ {name}", style="amber")
    glyph = "✓" if passed else "✗"
    return chip(x, y, f"{glyph} {name}", style="green" if passed else "red")


# ── bar rows (spec §2 anatomy) ───────────────────────────────────────


def bar_row(
    y: float,
    label: str,
    frac: float,
    value_text: str,
    *,
    bar_color: str = ACCENT,
    label_color: str = TEXT,
    value_color: str = TEXT,
    height: float = 22,
    track: bool = False,
    label_size: float = 13,
    value_size: float = 13,
) -> str:
    parts = [
        text(
            LABEL_RIGHT,
            y + height / 2 + label_size * 0.36,
            label,
            size=label_size,
            fill=label_color,
            anchor="end",
        )
    ]
    if track:
        parts.append(rrect(BAR_X, y, BAR_MAX_W, height, 4, fill=TRACK))
    w = max(0.0, min(1.0, frac)) * BAR_MAX_W
    if w > 0:
        parts.append(rrect(BAR_X, y, w, height, 4, fill=bar_color))
    parts.append(
        text(
            VALUE_X,
            y + height / 2 + value_size * 0.36,
            value_text,
            size=value_size,
            fill=value_color,
        )
    )
    return "".join(parts)


def ci_whisker(y_bar: float, value: float, ci_half: float, vmax: float, *, on_accent: bool) -> str:
    """CI95 whisker centered on the bar's value point (spec §4, tie card)."""
    if vmax <= 0 or ci_half <= 0:
        return ""
    x = (value - ci_half) / vmax * BAR_MAX_W + BAR_X
    w = 2 * ci_half / vmax * BAR_MAX_W
    fill = "rgba(255,255,255,0.6)" if on_accent else "rgba(255,255,255,0.35)"
    return rrect(x, y_bar + 8, max(w, 2), 6, 3, fill=fill)


# ── metric helpers ───────────────────────────────────────────────────


def metric_map(subject: Subject) -> dict[str, MetricValue]:
    return {m.key: m for m in subject.metrics}


def fmt_num(v: Any, digits: int = 1) -> str:
    if not isinstance(v, (int, float)):
        return "—"
    return f"{v:,.{digits}f}".rstrip("0").rstrip(".") if digits else f"{v:,.0f}"


def _power_mode_label(pm: str) -> str:
    return {"0": "standard", "1": "low", "2": "high"}.get(pm, pm)


def conditions_string(result: BenchResult) -> str:
    """quant · ctx N · KV type · power: mode · versions [· note] (spec §2).

    Only measured/known items appear — omission, never invention."""
    c = result.conditions
    parts: list[str] = []
    if c.get("quantizations"):
        parts.append(c["quantizations"])
    if c.get("context_size"):
        parts.append(f"ctx {c['context_size']}")
    if c.get("kv_cache_type"):
        parts.append(f"KV {c['kv_cache_type']}")
    if c.get("powermode"):
        parts.append(f"power: {_power_mode_label(c['powermode'])}")
    versions = [
        f"{s.label} {m['engine_version'].value}"
        for s in result.subjects
        if (m := metric_map(s)).get("engine_version")
    ]
    seen: set[str] = set()
    for v in versions:
        if v not in seen:
            seen.add(v)
            parts.append(v)
    if not versions and result.provenance.get("engine_version"):
        eng = result.subjects[0].engine if result.subjects else ""
        parts.append(f"{eng} {result.provenance['engine_version']}".strip())
    for key in (
        "suites",
        "scenarios",
        "burst_sizes",
        "load",
        "streaming",
        "max_tokens_per_call",
        "runs",
        "runs_per_prompt",
        "cold_warm_repeats",
    ):
        if c.get(key):
            parts.append(f"{key}: {c[key]}")
    if c.get("extra_body"):
        parts.append("custom sampling params")
    return " · ".join(parts) if parts else "conditions not recorded"


# ── chrome assembly (spec §0 + §2) ───────────────────────────────────


def _logo_group() -> str:
    """Inline the speedometer logo primitives at [37,24] scaled to 46px."""
    raw = importlib.resources.files("asiai.benchmark.cards").joinpath("logo_mark.svg").read_text()
    inner = re.sub(r"^.*?<svg[^>]*>", "", raw, flags=re.S)
    inner = inner.replace("</svg>", "")
    return f'<g transform="translate(37,24) scale(0.23)">{inner}</g>'


def chrome_open(
    result: BenchResult,
    *,
    rail: str = ACCENT,
    suite_label: str,
    section_tag: str,
    legend: str = "",
    model_chips: list[tuple[str, str]] | None = None,
) -> str:
    """Everything from the canvas down to the open terminal panel.

    ``model_chips`` = [(label, style)] rendered after the model name.
    Amber rail = something was refused, offline or throttled; a tie is a
    legitimate result and keeps the cyan rail (spec §0).
    """
    p: list[str] = []
    p.append(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630" width="1200" height="630">'
    )
    p.append(rrect(0, 0, 1200, 630, 24, fill=BG))
    p.append(rrect(0.5, 0.5, 1199, 629, 24, stroke="rgba(255,255,255,0.07)"))
    p.append(rrect(8, 1, 1184, 5, 0, fill=rail))

    # Header row
    p.append(_logo_group())
    wordmark_x = 37 + 46 + 14
    p.append(text(wordmark_x, 56, "asiai", size=28, family=SANS, weight=700, fill=TEXT))
    tagline_x = wordmark_x + sans_w("asiai", 28) + 14
    p.append(text(tagline_x, 53, "The Speedtest for local LLMs", size=15, family=SANS, fill=TEXT2))

    # Hardware badges, right-aligned at x=1164
    badges: list[str] = []
    prov = result.provenance
    if prov.get("hw_chip"):
        badges.append(prov["hw_chip"])
    gpu = (result.raw.get("machine") or {}).get("gpu_cores")
    if gpu:
        badges.append(f"{gpu}c GPU")
    if prov.get("ram_gb"):
        badges.append(f"{prov['ram_gb']} GB")
    bx = 1164
    for label in reversed(badges):
        w = sans_w(label, 13) + 24
        bx -= w
        p.append(rrect(bx, 30, w, 26, 8, fill=CHIP, stroke=CHIP_BORDER))
        p.append(text(bx + 12, 47, label, size=13, family=SANS, fill=CHIP_TEXT_HEADER))
        bx -= 8

    # Model row
    model = next((s.model for s in result.subjects if s.model), "") or "unknown model"
    p.append(text(36, 104, model, size=25, family=SANS, weight=600, fill=TEXT))
    cx = 36 + sans_w(model, 25) + 16
    for label, style in model_chips or []:
        svg, w = chip(cx, 86, label, size=12, height=24)
        if style != "neutral":
            svg, w = chip(cx, 86, label, style=style, size=12, height=24)
        p.append(svg)
        cx += w + 12

    # Terminal panel + header
    p.append(rrect(29, 125, 1142, 430, 12, fill=PANEL, stroke=PANEL_BORDER))
    for i, color in enumerate(TRAFFIC):
        p.append(f'<circle cx="{58 + i * 16}" cy="147" r="5" fill="{color}"/>')
    p.append(text(108, 151, f"asiai bench {suite_label}", size=12, fill=TEXT3))
    p.append(text(1146, 151, section_tag, size=12, fill=ACCENT, anchor="end", spacing=2))
    if legend:
        p.append(
            text(
                1146 - mono_w(section_tag, 12) - 2 * len(section_tag) - 14,
                151,
                legend,
                size=11,
                fill=TEXT3,
                anchor="end",
            )
        )
    return "".join(p)


def gates_row(
    result: BenchResult, y: float, *, extra_chips: list[tuple[str, str]] | None = None
) -> str:
    """Divider + GATES badges + optional extra chips (spec §2 bottom block)."""
    stroke = 'stroke="rgba(255,255,255,0.05)" stroke-width="1"'
    p = [f'<line x1="54" y1="{y:g}" x2="1146" y2="{y:g}" {stroke}/>']
    cy = y + 12
    cx = 54.0
    if result.gates or extra_chips:
        p.append(text(cx, cy + 14, "GATES", size=11, fill=TEXT3, spacing=1.5))
        cx += mono_w("GATES", 11) + 1.5 * 5 + 16
    for gate in result.gates:
        offline = "offline" in gate.detail.lower() or "skipped" in gate.detail.lower()
        svg, w = gate_badge(
            cx,
            cy,
            gate.name if not gate.detail or gate.passed else f"{gate.name}",
            gate.passed,
            offline=offline and gate.passed,
        )
        p.append(svg)
        cx += w + 8
    for label, style in extra_chips or []:
        svg, w = chip(cx, cy, label, style=style)
        p.append(svg)
        cx += w + 8
    return "".join(p)


def chrome_close(result: BenchResult) -> str:
    """Conditions strip + footer + closing tag. Never omitted (spec §2)."""
    p: list[str] = []
    p.append(text(36, 572, "CONDITIONS", size=10, fill=ACCENT, spacing=2))
    cond_x = 36 + mono_w("CONDITIONS", 10) + 2 * 10 + 14
    p.append(text(cond_x, 572, conditions_string(result), size=12, fill=TEXT2))

    prov = result.provenance
    footer_bits = []
    if prov.get("asiai_version"):
        footer_bits.append(f"asiai v{prov['asiai_version']}")
    if prov.get("hw_chip"):
        footer_bits.append(prov["hw_chip"])
    if prov.get("ram_gb"):
        footer_bits.append(f"{prov['ram_gb']} GB")
    if prov.get("os_version"):
        footer_bits.append(f"macOS {prov['os_version']}")
    ts = prov.get("started_at", "")
    if ts.isdigit():
        footer_bits.append(time.strftime("%Y-%m-%d", time.localtime(int(ts))))
    p.append(
        text(36, 606, " · ".join(footer_bits) or "provenance not recorded", size=11, fill=TEXT3)
    )

    pill_label = "asiai.dev"
    pill_w = mono_w(pill_label, 12) + 32
    p.append(rrect(1164 - pill_w, 588, pill_w, 28, 14, stroke=ACCENT))
    p.append(text(1164 - pill_w + 16, 606, pill_label, size=12, fill=ACCENT))
    p.append("</svg>")
    return "".join(p)


def wrap_text(x: float, y: float, content: str, width: float, *, size: float = 13) -> str:
    """Greedy word wrap (sans, TEXT2) — SVG text cannot flow by itself."""
    words = content.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if sans_w(trial, size) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return "".join(
        text(x, y + i * (size + 5), line, size=size, family=SANS, fill=TEXT2)
        for i, line in enumerate(lines[:4])
    )


def body_y0(stack_h: float) -> float:
    """Vertically center a stack in the body band (spec §6)."""
    return BODY_Y + max(0.0, (BODY_H - stack_h) / 2)
