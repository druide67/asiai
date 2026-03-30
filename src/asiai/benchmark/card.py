"""Benchmark card generator — shareable SVG/PNG cards."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# --- Constants ---
_SANS = "Inter,system-ui,sans-serif"  # Falls back to SF Pro on macOS
_MONO = "Menlo,Monaco,monospace"
_VALID_FORMATS = frozenset({"svg", "png"})
_SUBMISSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{8,}$")
_PNG_MAGIC = b"\x89PNG"
_MAX_DOWNLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
_FRAME_LEFT = 40
_FRAME_RIGHT = 1140  # 40 + 1100


def generate_card_svg(
    report: dict[str, Any],
    hw_chip: str = "",
    model_quantization: str = "",
    ram_gb: int = 0,
    gpu_cores: int = 0,
    context_size: int = 0,
    engine_versions: dict[str, str] | None = None,
    power_data: dict[str, dict] | None = None,
    engine_quants: dict[str, str] | None = None,
) -> str:
    """Generate an SVG benchmark card (1200x630) from aggregated results.

    Design: dark theme, terminal-inspired, asiai branding.
    v2: per-engine chips, insight line, left-aligned hero, bigger logo.
    v3: cross-model/matrix comparison support via session_type.
    """
    from asiai.benchmark.reporter import report_to_slots

    session_type = report.get("session_type", "engine")
    slots = report_to_slots(report)
    winner = report.get("winner")

    # Title depends on session type
    if session_type == "model" and slots:
        model = _format_model_name(slots[0].get("engine", "Unknown"))
    elif session_type == "matrix":
        model = "Cross-model benchmark"
    else:
        model = _format_model_name(report.get("model", "Unknown"))

    # Collect data for bars from slots
    bars: list[dict] = []
    max_tok = 0.0
    for s in slots:
        tok_s = s.get("median_tok_s", 0.0) or s.get("avg_tok_s", 0.0)
        ttft = s.get("median_ttft_ms", 0.0)
        stability = s.get("stability", "")
        vram = s.get("vram_bytes", 0)
        runs = s.get("runs_count", 0)
        eng_name = s.get("engine", "")

        # Bar label depends on session type
        if session_type == "model":
            label = _format_model_name(s.get("model", ""))
        elif session_type == "matrix":
            label = f"{_format_model_name(s.get('model', ''))} / {eng_name}"
        else:
            label = eng_name

        quant = ""
        if engine_quants and eng_name in engine_quants:
            quant = engine_quants[eng_name]
        bars.append(
            {
                "name": label,
                "engine": eng_name,  # Keep for engine_versions/power_data lookup
                "tok_s": tok_s,
                "ttft_ms": ttft,
                "stability": stability,
                "vram_bytes": vram,
                "runs_count": runs,
                "quant": quant,
            }
        )
        if tok_s > max_tok:
            max_tok = tok_s

    # Sort by tok/s descending
    bars.sort(key=lambda b: b["tok_s"], reverse=True)

    # --- Hardware badges (top-right, 3 separate pills) --- [Change #1]
    hw_badge = ""
    if hw_chip:
        hw_pills: list[str] = [_escape(hw_chip)]
        if gpu_cores > 0:
            hw_pills.append(f"{gpu_cores}c GPU")
        if ram_gb > 0:
            hw_pills.append(f"{ram_gb} GB")
        badge_elements = []
        bx = 1140
        for pill_text in reversed(hw_pills):
            pw = int(len(pill_text) * 7.5) + 24
            bx -= pw
            badge_elements.append(
                f'  <rect x="{bx}" y="40" width="{pw}" height="30" '
                f'rx="6" fill="#2d3748" stroke="#4a5568" stroke-width="1"/>\n'
                f'  <text x="{bx + pw // 2}" y="60" text-anchor="middle" '
                f'fill="#e2e8f0" font-size="13" '
                f'font-family="{_SANS}" font-weight="500">{pill_text}</text>'
            )
            bx -= 8
        hw_badge = "\n".join(reversed(badge_elements))

    # --- Specs banner ---
    # Quant: global only if ALL engines report the same value.
    # If only some report it, show per-engine (only on those that have it).
    specs_parts: list[str] = []
    quant_values = set(v for v in (engine_quants or {}).values() if v)
    num_slots = len(slots)
    num_with_quant = len([v for v in (engine_quants or {}).values() if v])
    if len(quant_values) == 1 and num_with_quant == num_slots and num_slots > 0:
        # All engines report same quant → global
        specs_parts.append(quant_values.pop())
        engine_quants = None
    elif not engine_quants and model_quantization:
        # No per-engine data at all → fallback to global
        specs_parts.append(model_quantization)
    # else: per-engine in chips (engine_quants stays as-is)
    if context_size > 0:
        if context_size >= 1024:
            specs_parts.append(f"{context_size // 1024}K ctx")
        else:
            specs_parts.append(f"{context_size} ctx")

    # Specs chips inline with model name (right of it) — no separate banner line
    specs_svg = ""
    if specs_parts:
        # Estimate model name width (26px bold Inter ≈ 15px per char)
        model_text_w = int(len(model) * 15) + 60  # x=60 start + text width
        spec_elements = []
        spec_x = model_text_w + 16
        for spec_text in specs_parts:
            text_w = int(len(spec_text) * 7) + 18
            spec_elements.append(
                f'  <rect x="{spec_x}" y="120" width="{text_w}" height="22" rx="6" fill="#2d3748"/>'
            )
            spec_elements.append(
                f'  <text x="{spec_x + text_w // 2}" '
                f'y="135" text-anchor="middle" '
                f'fill="#a0aec0" font-size="12" '
                f'font-family="{_SANS}">'
                f"{_escape(spec_text)}</text>"
            )
            spec_x += text_w + 8
        specs_svg = "\n".join(spec_elements)
    frame_top = 170  # No more vertical shift for specs

    # --- Layout constants ---
    bar_x = 480
    bar_max_width = 520
    bar_height = 38
    bar_gap = 14
    bar_start_y = frame_top + 55
    num_bars = min(len(bars), 4)

    # --- Bar chart ---
    bar_elements = []
    for i, bar in enumerate(bars[:4]):
        y = bar_start_y + i * (bar_height + bar_gap)
        ratio = (bar["tok_s"] / max_tok) if max_tok > 0 else 0
        width = max(int(ratio * bar_max_width), 60)

        fill = "#06b6d4" if i == 0 else "#4a5568"

        # Engine name (left of bar)
        bar_elements.append(
            f'  <text x="{bar_x - 14}" y="{y + 26}" '
            f'text-anchor="end" fill="#e2e8f0" font-size="15" '
            f'font-family="{_MONO}">{_escape(bar["name"])}</text>'
        )
        # Bar
        bar_elements.append(
            f'  <rect x="{bar_x}" y="{y}" width="{width}" height="{bar_height}" '
            f'rx="4" fill="{fill}" opacity="0.9"/>'
        )
        # tok/s label — inside bar if it would overflow, outside otherwise
        label_text = f"{bar['tok_s']:.1f} tok/s"
        label_width = len(label_text) * 8.5
        label_outside_x = bar_x + width + 10
        if label_outside_x + label_width > _FRAME_RIGHT:
            bar_elements.append(
                f'  <text x="{bar_x + width - 10}" y="{y + 26}" '
                f'text-anchor="end" fill="#0f1117" font-size="14" '
                f'font-weight="600" font-family="{_MONO}">{label_text}</text>'
            )
        else:
            bar_elements.append(
                f'  <text x="{label_outside_x}" y="{y + 26}" '
                f'fill="#e2e8f0" font-size="14" '
                f'font-family="{_MONO}">{label_text}</text>'
            )

    bars_svg = "\n".join(bar_elements)

    # --- Dynamic positions based on bar count ---
    bars_end_y = bar_start_y + num_bars * (bar_height + bar_gap)

    # --- Hero number (left-aligned, tight to bars) --- [Change #5 v3: 60px, +32]
    hero_svg = ""
    hero_end_y = bars_end_y
    if winner:
        delta_raw = winner.get("tok_s_delta", "")
        delta_num = delta_raw.split()[0] if delta_raw else ""
        if delta_num:
            delta_display = delta_num.replace("x", "\u00d7")
            hero_y = bars_end_y + 32
            hero_svg = (
                f'  <text x="80" y="{hero_y}" '
                f'fill="#06b6d4" font-size="72" '
                f'font-family="{_SANS}" font-weight="800">{_escape(delta_display)}</text>\n'
                f'  <text x="80" y="{hero_y + 28}" '
                f'fill="#718096" font-size="15" '
                f'font-family="{_SANS}">{_escape(winner["name"])} wins</text>'
            )
            hero_end_y = hero_y + 32
    elif bars:
        hero_y = bars_end_y + 32
        hero_svg = (
            f'  <text x="80" y="{hero_y}" '
            f'fill="#06b6d4" font-size="60" '
            f'font-family="{_SANS}" font-weight="800">'
            f"{bars[0]['tok_s']:.1f} tok/s</text>"
        )
        hero_end_y = hero_y + 20

    # --- Insight line (auto-generated) --- [Change #4]
    insight_svg = ""
    if len(bars) >= 2:
        insights = []
        best, second = bars[0], bars[1]
        # TTFT comparison
        if best["ttft_ms"] > 0 and second["ttft_ms"] > 0:
            if second["ttft_ms"] < best["ttft_ms"]:
                pct = int((best["ttft_ms"] - second["ttft_ms"]) / best["ttft_ms"] * 100)
                if pct >= 10:
                    insights.append(f"{second['name']} {pct}% faster TTFT")
            elif best["ttft_ms"] < second["ttft_ms"]:
                pct = int((second["ttft_ms"] - best["ttft_ms"]) / second["ttft_ms"] * 100)
                if pct >= 10:
                    insights.append(f"{best['name']} {pct}% faster TTFT")
        # VRAM comparison
        if best["vram_bytes"] > 0 and second["vram_bytes"] > 0:
            if best["vram_bytes"] < second["vram_bytes"]:
                pct = int((second["vram_bytes"] - best["vram_bytes"]) / second["vram_bytes"] * 100)
                if pct >= 10:
                    insights.append(f"{best['name']} {pct}% less VRAM")
            elif second["vram_bytes"] < best["vram_bytes"]:
                pct = int((best["vram_bytes"] - second["vram_bytes"]) / best["vram_bytes"] * 100)
                if pct >= 10:
                    insights.append(f"{second['name']} {pct}% less VRAM")
        # Stability warning
        for b in bars[:2]:
            if b["stability"] and b["stability"] != "stable":
                insights.append(f"{b['name']}: {b['stability']}")

        if insights:
            insight_text = _escape(" \u00b7 ".join(insights[:3]))
            insight_y = hero_end_y + 12 if winner else bars_end_y + 30
            insight_x = 80
            insight_svg = (
                f'  <text x="{insight_x}" y="{insight_y}" '
                f'fill="#a0aec0" font-size="13" font-style="italic" '
                f'font-family="{_SANS}">{insight_text}</text>'
            )

    # --- Per-engine metric chips (top 2 engines) --- [Changes #2, #5, #8]
    # Pre-compute per-metric winners for green highlight
    metric_winners: dict[str, str] = {}  # metric_key → engine_name
    if len(bars) >= 2:
        b0, b1 = bars[0], bars[1]
        # TTFT: lower is better
        if b0["ttft_ms"] > 0 and b1["ttft_ms"] > 0:
            metric_winners["ttft"] = b0["name"] if b0["ttft_ms"] <= b1["ttft_ms"] else b1["name"]
        # VRAM: lower is better
        if b0["vram_bytes"] > 0 and b1["vram_bytes"] > 0:
            metric_winners["vram"] = (
                b0["name"] if b0["vram_bytes"] <= b1["vram_bytes"] else b1["name"]
            )
        # Power efficiency: higher is better
        if power_data:
            eff0 = power_data.get(b0.get("engine", b0["name"]), {}).get("avg_eff", 0)
            eff1 = power_data.get(b1.get("engine", b1["name"]), {}).get("avg_eff", 0)
            if eff0 > 0 and eff1 > 0:
                metric_winners["power"] = b0["name"] if eff0 >= eff1 else b1["name"]

    # Tighter spacing: hero→insight 12px (done above), insight→chips 16px [Change #4]
    chip_y_start = (hero_end_y + 16) if hero_svg else (bars_end_y + 24)
    if insight_svg:
        chip_y_start += 20
    all_chip_elements = []

    for eng_idx, bar in enumerate(bars[:2]):
        chip_y = chip_y_start + eng_idx * 36
        # Build chips as (text, metric_key) tuples for highlight logic
        chips: list[tuple[str, str]] = []
        # Per-engine quant [Change #2]
        if bar["quant"]:
            chips.append((bar["quant"], ""))
        if bar["ttft_ms"] > 0:
            chips.append((f"{bar['ttft_ms']:.0f}ms TTFT", "ttft"))
        if bar["stability"]:
            chips.append((bar["stability"], "stability"))
        if bar["vram_bytes"] > 0:
            native_vram_engines = {"ollama", "lmstudio"}
            vram_label = _format_vram(bar["vram_bytes"])
            if bar.get("engine", "") not in native_vram_engines:
                vram_label += " (est.)"
            chips.append((vram_label, "vram"))
        # Power per engine [Change #8]
        eng_key = bar.get("engine", bar["name"])
        if power_data and eng_key in power_data:
            pw = power_data[eng_key]
            watts = pw.get("avg_watts", 0)
            eff = pw.get("avg_eff", 0)
            if watts > 0 and eff > 0:
                chips.append((f"{watts:.0f}W \u00b7 {eff:.1f} tok/s/W", "power"))
            elif watts > 0:
                chips.append((f"{watts:.0f}W", ""))
        # Engine version now in label, not as chip [Change #3]
        if bar.get("runs_count", 0) > 1:
            chips.append((f"{bar['runs_count']} runs", ""))

        # Engine name label with version (colored for winner) [Change #3]
        name_color = "#06b6d4" if eng_idx == 0 else "#718096"
        chip_x = 60
        name_raw = bar["name"]
        eng_key = bar.get("engine", name_raw)
        if engine_versions and eng_key in engine_versions and engine_versions[eng_key]:
            name_raw = f"{name_raw} v{engine_versions[eng_key]}"
        name_text = _escape(name_raw)
        name_w = int(len(name_text) * 7.5) + 16
        all_chip_elements.append(
            f'  <text x="{chip_x}" y="{chip_y + 19}" '
            f'fill="{name_color}" font-size="13" font-weight="600" '
            f'font-family="{_MONO}">{name_text}</text>'
        )
        chip_x += name_w + 4

        for chip_text, metric_key in chips[:6]:
            text_width = int(len(chip_text) * 7.2) + 22
            # Style: red for unstable, green stroke for winner, default gray
            is_unstable = metric_key == "stability" and chip_text.lower() != "stable"
            is_winner = (
                metric_key
                and metric_key in metric_winners
                and metric_winners[metric_key] == bar["name"]
            )
            if is_unstable:
                chip_fill = "#2d1b1b"
                stroke = ' stroke="#ef4444" stroke-width="1"'
                text_color = "#fca5a5"
            elif is_winner:
                chip_fill = "#2d3748"
                stroke = ' stroke="#06b6d4" stroke-width="1"'
                text_color = "#e2e8f0"
            else:
                chip_fill = "#2d3748"
                stroke = ""
                text_color = "#a0aec0"
            all_chip_elements.append(
                f'  <rect x="{chip_x}" y="{chip_y}" width="{text_width}" '
                f'height="28" rx="6" fill="{chip_fill}"{stroke}/>'
            )
            all_chip_elements.append(
                f'  <text x="{chip_x + text_width // 2}" y="{chip_y + 19}" '
                f'text-anchor="middle" fill="{text_color}" font-size="12" '
                f'font-family="{_SANS}">{_escape(chip_text)}</text>'
            )
            chip_x += text_width + 6

    chips_svg = "\n".join(all_chip_elements)

    # --- Terminal frame height (dynamic, 20px padding bottom) --- [Change #1]
    last_chip_y = chip_y_start + min(len(bars), 2) * 36
    min_frame_bottom = 440 if num_bars <= 1 else 520
    max_frame_bottom = 592  # 630 - 10 (gap) - 28 (footer pill) = footer fits in canvas
    frame_bottom = min(max(last_chip_y + 20, min_frame_bottom), max_frame_bottom)
    frame_height = frame_bottom - frame_top

    # --- Logo + tagline (bigger) --- [Change #7]
    logo = (
        '  <g transform="translate(32, 24) scale(0.30)">\n'
        '    <circle cx="100" cy="100" r="90" fill="#0f0f23"/>\n'
        '    <circle cx="100" cy="100" r="86" fill="none" stroke="#06b6d4" stroke-width="0.5" opacity="0.15"/>\n'
        '    <line x1="30.4" y1="148.8" x2="43.5" y2="139.6" stroke="#06b6d4" stroke-width="3.2" stroke-linecap="round" opacity="0.3"/>\n'
        '    <line x1="15.5" y1="109.1" x2="31.4" y2="107.4" stroke="#06b6d4" stroke-width="3.2" stroke-linecap="round" opacity="0.37"/>\n'
        '    <line x1="21.6" y1="67.2" x2="36.3" y2="73.4" stroke="#06b6d4" stroke-width="3.2" stroke-linecap="round" opacity="0.44"/>\n'
        '    <line x1="47.1" y1="33.4" x2="57.1" y2="46.0" stroke="#06b6d4" stroke-width="3.2" stroke-linecap="round" opacity="0.51"/>\n'
        '    <line x1="85.8" y1="16.2" x2="88.5" y2="32.0" stroke="#06b6d4" stroke-width="3.2" stroke-linecap="round" opacity="0.58"/>\n'
        '    <line x1="128.0" y1="19.7" x2="122.7" y2="34.9" stroke="#06b6d4" stroke-width="3.2" stroke-linecap="round" opacity="0.65"/>\n'
        '    <line x1="163.2" y1="43.2" x2="151.3" y2="53.9" stroke="#06b6d4" stroke-width="3.2" stroke-linecap="round" opacity="0.72"/>\n'
        '    <line x1="182.8" y1="80.8" x2="167.2" y2="84.4" stroke="#06b6d4" stroke-width="3.2" stroke-linecap="round" opacity="0.78"/>\n'
        '    <line x1="181.8" y1="123.1" x2="166.4" y2="118.8" stroke="#06b6d4" stroke-width="3.2" stroke-linecap="round" opacity="0.85"/>\n'
        '    <path d="M136.8,63.2 L101.98,101.98 L98.02,98.02 Z" fill="#06b6d4"/>\n'
        '    <circle cx="100" cy="100" r="3.5" fill="#06b6d4"/>\n'
        "  </g>\n"
        f'  <text x="100" y="72" fill="#e2e8f0" font-size="36" '
        f'font-family="{_SANS}" font-weight="700">'
        f'asi<tspan fill="#06b6d4">ai</tspan></text>\n'
        f'  <text x="230" y="72" fill="#718096" font-size="16" '
        f'font-family="{_SANS}">The Speedtest for local LLMs</text>'
    )

    # --- Footer URL (prominent pill) ---
    url_text = "asiai.dev"
    url_w = int(len(url_text) * 8) + 28
    url_x = 1140 - url_w
    footer_y = frame_bottom + 10
    footer = (
        f'  <rect x="{url_x}" y="{footer_y}" width="{url_w}" height="28" '
        f'rx="14" fill="#1a202c" stroke="#06b6d4" stroke-width="1" opacity="0.8"/>\n'
        f'  <text x="{url_x + url_w // 2}" y="{footer_y + 19}" text-anchor="middle" '
        f'fill="#06b6d4" font-size="13" '
        f'font-family="{_SANS}" font-weight="500">{url_text}</text>'
    )

    esc_model = _escape(model)

    svg_lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">',
        "  <!-- Background -->",
        "  <defs>",
        '    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">',
        '      <stop offset="0%" stop-color="#0f1117"/>',
        '      <stop offset="100%" stop-color="#1a1d2e"/>',
        "    </linearGradient>",
        '    <clipPath id="card-clip">',
        '      <rect width="1200" height="630" rx="12"/>',
        "    </clipPath>",
        "  </defs>",
        '  <g clip-path="url(#card-clip)">',
        '  <rect width="1200" height="630" rx="12" fill="url(#bg)"/>',
        "",
        "  <!-- Top accent bar -->",
        '  <rect x="0" y="0" width="1200" height="4" fill="#06b6d4"/>',
        "",
        "  <!-- Logo + tagline -->",
        logo,
        "",
        "  <!-- Hardware badge -->",
        hw_badge,
        "",
        "  <!-- Model name + specs -->",
        f'  <text x="60" y="140" fill="#e2e8f0" font-size="26"'
        f' font-family="{_SANS}" font-weight="700">'
        f"{esc_model}</text>",
        specs_svg,
        "",
        f"  <!-- Terminal frame (dynamic height: {frame_height}px) -->",
        f'  <rect x="{_FRAME_LEFT}" y="{frame_top}" '
        f'width="1120" height="{frame_height}"'
        ' rx="8" fill="#1a202c" stroke="#2d3748" stroke-width="1"/>',
        f'  <circle cx="65" cy="{frame_top + 20}" r="5" fill="#fc5c65"/>',
        f'  <circle cx="85" cy="{frame_top + 20}" r="5" fill="#fed330"/>',
        f'  <circle cx="105" cy="{frame_top + 20}" r="5" fill="#26de81"/>',
        f'  <text x="130" y="{frame_top + 25}" fill="#718096" font-size="12"'
        f' font-family="{_MONO}">asiai bench</text>',
        "",
        "  <!-- Bars -->",
        bars_svg,
        "",
        "  <!-- Hero number -->",
        hero_svg,
        "",
        "  <!-- Insight -->",
        insight_svg,
        "",
        "  <!-- Per-engine metric chips -->",
        chips_svg,
        "",
        "  <!-- Footer -->",
        footer,
        "  </g>",
        "</svg>",
    ]
    return "\n".join(svg_lines)


def save_card(svg: str, fmt: str = "svg", output_dir: str = "") -> str:
    """Save card to file. Returns the file path."""
    if fmt not in _VALID_FORMATS:
        fmt = "svg"

    if not output_dir:
        output_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "asiai", "cards")

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    ts = f"{int(time.time())}_{os.getpid()}"
    filename = f"bench-card-{ts}.{fmt}"
    path = os.path.join(output_dir, filename)

    with open(path, "w") as f:
        f.write(svg)

    return path


def convert_svg_to_png(svg_path: str, png_path: str = "") -> str:
    """Convert SVG to PNG using macOS native sips. Returns path or empty string."""
    if not png_path:
        png_path = svg_path.rsplit(".", 1)[0] + ".png"
    try:
        result = subprocess.run(
            ["sips", "-s", "format", "png", svg_path, "--out", png_path],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0 and os.path.exists(png_path):
            return png_path
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    logger.debug("sips SVG to PNG conversion failed, SVG-only available")
    return ""


def download_card_png(
    submission_id: str,
    api_url: str = "",
    output_dir: str = "",
) -> str:
    """Download PNG card from API. Returns file path or empty string on failure."""
    if not _validate_submission_id(submission_id):
        logger.warning("Invalid submission_id format: %s", submission_id[:20])
        return ""

    if not api_url:
        api_url = os.environ.get("ASIAI_COMMUNITY_URL", "https://api.asiai.dev/api/v1").rstrip("/")

    url = f"{api_url}/bench/card/{submission_id}.png"

    if not output_dir:
        output_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "asiai", "cards")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = os.path.join(output_dir, f"bench-card-{submission_id[:8]}.png")

    try:
        req = Request(url)
        with urlopen(req, timeout=10) as resp:
            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > _MAX_DOWNLOAD_BYTES:
                logger.warning("PNG too large (%s bytes), skipping download", content_length)
                return ""

            data = resp.read(_MAX_DOWNLOAD_BYTES)

            if not data.startswith(_PNG_MAGIC):
                logger.warning("Downloaded file is not a valid PNG")
                return ""

            with open(path, "wb") as f:
                f.write(data)
            return path
    except (HTTPError, URLError, OSError) as exc:
        logger.warning("PNG card download failed: %s", exc)
        return ""


def get_share_url(submission_id: str) -> str:
    """Get shareable card URL, respecting ASIAI_COMMUNITY_URL env var."""
    base = os.environ.get("ASIAI_COMMUNITY_URL", "").rstrip("/")
    if base:
        # Strip path suffix (/api/v1) keeping scheme + host
        site = re.sub(r"/api(/v\d+)?$", "", base)
    else:
        site = "https://api.asiai.dev"
    return f"{site}/card/{submission_id}"


def extract_card_metadata(
    raw_results: list[dict],
) -> tuple[dict[str, str], dict[str, dict], dict[str, str]]:
    """Extract engine versions, power data, and per-engine quants.

    Returns:
        (engine_versions, power_data, engine_quants) dicts keyed by engine name.
    """
    engine_versions: dict[str, str] = {}
    engine_quants: dict[str, str] = {}
    power_by_engine: dict[str, list[dict]] = {}

    for r in raw_results:
        eng = r.get("engine", "")
        if not eng:
            continue
        if eng not in engine_versions:
            engine_versions[eng] = r.get("engine_version", "")
        if eng not in engine_quants:
            quant = r.get("model_quantization", "")
            if quant:
                engine_quants[eng] = quant
        watts = r.get("power_watts", 0)
        eff = r.get("tok_per_sec_per_watt", 0)
        if watts > 0:
            power_by_engine.setdefault(eng, []).append({"watts": watts, "eff": eff})

    power_data: dict[str, dict] = {}
    for eng, vals in power_by_engine.items():
        avg_w = sum(v["watts"] for v in vals) / len(vals)
        eff_vals = [v["eff"] for v in vals if v["eff"] > 0]
        avg_eff = sum(eff_vals) / len(eff_vals) if eff_vals else 0.0
        power_data[eng] = {
            "avg_watts": round(avg_w, 1),
            "avg_eff": round(avg_eff, 2),
        }

    return engine_versions, power_data, engine_quants


def _escape(text: str) -> str:
    """Escape text for SVG XML content and attributes."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _format_vram(vram_bytes: int) -> str:
    """Format VRAM to human-readable. Round when .0."""
    vram_gb = vram_bytes / (1024**3)
    if vram_gb == int(vram_gb):
        return f"{int(vram_gb)} GB VRAM"
    return f"{vram_gb:.1f} GB VRAM"


def _format_model_name(name: str) -> str:
    """Format Ollama-style tag name for human display.

    'qwen3.5:35b-a3b' → 'Qwen 3.5 35B-A3B'
    'gemma2:9b'        → 'Gemma 2 9B'
    'llama3.1:latest'  → 'Llama 3.1'
    """
    parts = name.split(":")
    model = parts[0]
    tag = parts[1] if len(parts) > 1 else ""

    # Insert space before first digit group: "qwen3.5" → "qwen 3.5"
    model = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", model, count=1)
    # Capitalize first letter
    model = model[0].upper() + model[1:] if model else model

    # Clean tag: "latest" → skip, otherwise uppercase
    if tag and tag != "latest":
        tag = tag.upper()
        return f"{model} {tag}"
    return model


def _validate_submission_id(submission_id: str) -> bool:
    """Validate submission ID: alphanumeric + hyphens/underscores, min 8 chars."""
    return bool(_SUBMISSION_ID_RE.match(submission_id))
