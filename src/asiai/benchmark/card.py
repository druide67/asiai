"""Benchmark card generator — shareable SVG/PNG cards."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def generate_card_svg(
    report: dict[str, Any],
    hw_chip: str = "",
) -> str:
    """Generate an SVG benchmark card (1200x630) from aggregated results.

    Design: dark theme, terminal-inspired, asiai branding.
    """
    model = report.get("model", "Unknown")
    engines = report.get("engines", {})
    winner = report.get("winner")

    # Collect engine data for bars
    bars: list[dict] = []
    max_tok = 0.0
    for eng_name, data in engines.items():
        tok_s = data.get("median_tok_s", 0.0) or data.get("avg_tok_s", 0.0)
        ttft = data.get("median_ttft_ms", 0.0)
        stability = data.get("stability", "")
        vram = data.get("vram_bytes", 0)
        bars.append({
            "name": eng_name,
            "tok_s": tok_s,
            "ttft_ms": ttft,
            "stability": stability,
            "vram_bytes": vram,
        })
        if tok_s > max_tok:
            max_tok = tok_s

    # Sort by tok/s descending
    bars.sort(key=lambda b: b["tok_s"], reverse=True)

    # Build bar chart SVG elements
    bar_x = 520
    bar_max_width = 580
    bar_height = 36
    bar_gap = 14
    bar_start_y = 240

    bar_elements = []
    for i, bar in enumerate(bars[:4]):  # Max 4 engines
        y = bar_start_y + i * (bar_height + bar_gap)
        width = int((bar["tok_s"] / max_tok) * bar_max_width) if max_tok > 0 else 0
        width = max(width, 40)  # Minimum visible bar

        # Bar color: winner gets accent, others get muted
        fill = "#00d4aa" if i == 0 else "#4a5568"

        bar_elements.append(
            f'  <text x="{bar_x - 10}" y="{y + 24}" '
            f'text-anchor="end" fill="#e2e8f0" font-size="15" '
            f'font-family="Menlo,Monaco,monospace">{_escape(bar["name"])}</text>'
        )
        bar_elements.append(
            f'  <rect x="{bar_x}" y="{y}" width="{width}" height="{bar_height}" '
            f'rx="4" fill="{fill}" opacity="0.9"/>'
        )
        bar_elements.append(
            f'  <text x="{bar_x + width + 8}" y="{y + 24}" '
            f'fill="#e2e8f0" font-size="14" '
            f'font-family="Menlo,Monaco,monospace">{bar["tok_s"]:.1f} tok/s</text>'
        )

    bars_svg = "\n".join(bar_elements)

    # Metric chips
    chips = []
    if bars:
        best = bars[0]
        chips.append(f'{best["tok_s"]:.1f} tok/s')
        if best["ttft_ms"] > 0:
            chips.append(f'{best["ttft_ms"]:.0f}ms TTFT')
        if best["stability"]:
            chips.append(best["stability"])
        if best["vram_bytes"] > 0:
            vram_gb = best["vram_bytes"] / (1024**3)
            chips.append(f'{vram_gb:.1f} GB VRAM')

    chip_elements = []
    chip_x = 60
    chip_y = 540
    for chip_text in chips[:4]:
        text_width = len(chip_text) * 8 + 16
        chip_elements.append(
            f'  <rect x="{chip_x}" y="{chip_y}" width="{text_width}" '
            f'height="28" rx="14" fill="#2d3748"/>'
        )
        chip_elements.append(
            f'  <text x="{chip_x + text_width // 2}" y="{chip_y + 19}" '
            f'text-anchor="middle" fill="#a0aec0" font-size="12" '
            f'font-family="Inter,system-ui,sans-serif">{_escape(chip_text)}</text>'
        )
        chip_x += text_width + 10

    chips_svg = "\n".join(chip_elements)

    # Winner line
    winner_text = ""
    if winner:
        winner_text = (
            f'  <text x="60" y="500" fill="#00d4aa" font-size="16" '
            f'font-family="Inter,system-ui,sans-serif" font-weight="600">'
            f'Winner: {_escape(winner["name"])} ({_escape(winner["tok_s_delta"])})'
            f'</text>'
        )

    # Subtitle: model + chip
    subtitle = model
    if hw_chip:
        subtitle = f"{model} on {hw_chip}"

    sans = "Inter,system-ui,sans-serif"
    mono = "Menlo,Monaco,monospace"
    esc_sub = _escape(subtitle)

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg"'
        ' width="1200" height="630"'
        ' viewBox="0 0 1200 630">',
        "  <!-- Background -->",
        "  <defs>",
        '    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">',
        '      <stop offset="0%" stop-color="#0f1117"/>',
        '      <stop offset="100%" stop-color="#1a1d2e"/>',
        "    </linearGradient>",
        "  </defs>",
        '  <rect width="1200" height="630" fill="url(#bg)"/>',
        "",
        "  <!-- Border accent -->",
        '  <rect x="0" y="0" width="1200" height="4" fill="#00d4aa"/>',
        "",
        "  <!-- Logo + brand -->",
        f'  <text x="60" y="70" fill="#e2e8f0" font-size="28"'
        f' font-family="{sans}" font-weight="700">'
        f'asi<tspan fill="#00d4aa">ai</tspan></text>',
        f'  <text x="160" y="70" fill="#718096" font-size="14"'
        f' font-family="{sans}">'
        f"Built for humans. Ready for AI agents.</text>",
        "",
        "  <!-- Model + chip -->",
        f'  <text x="60" y="140" fill="#e2e8f0" font-size="22"'
        f' font-family="{sans}" font-weight="600">'
        f"{esc_sub}</text>",
        "",
        "  <!-- Terminal mockup frame -->",
        '  <rect x="40" y="170" width="1120" height="380"'
        ' rx="8" fill="#1a202c" stroke="#2d3748" stroke-width="1"/>',
        '  <circle cx="65" cy="190" r="5" fill="#fc5c65"/>',
        '  <circle cx="85" cy="190" r="5" fill="#fed330"/>',
        '  <circle cx="105" cy="190" r="5" fill="#26de81"/>',
        f'  <text x="130" y="195" fill="#718096" font-size="12"'
        f' font-family="{mono}">asiai bench</text>',
        "",
        "  <!-- Header line -->",
        f'  <text x="60" y="240" fill="#a0aec0" font-size="13"'
        f' font-family="{mono}">Engine          tok/s</text>',
        "",
        "  <!-- Bars -->",
        bars_svg,
        "",
        "  <!-- Winner -->",
        winner_text,
        "",
        "  <!-- Metric chips -->",
        chips_svg,
        "",
        "  <!-- Footer -->",
        f'  <text x="1140" y="600" text-anchor="end"'
        f' fill="#4a5568" font-size="12"'
        f' font-family="{sans}">asiai.dev</text>',
        "</svg>",
    ]
    svg = "\n".join(lines)

    return svg


def save_card(svg: str, fmt: str = "svg", output_dir: str = "") -> str:
    """Save SVG card to file. Returns the file path."""
    if not output_dir:
        output_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "asiai", "cards")

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time())
    filename = f"bench-card-{timestamp}.{fmt}"
    path = os.path.join(output_dir, filename)

    with open(path, "w") as f:
        f.write(svg)

    return path


def download_card_png(
    submission_id: str,
    api_url: str = "",
    output_dir: str = "",
) -> str:
    """Download PNG card from API. Returns file path or empty string on failure."""
    if not api_url:
        api_url = os.environ.get("ASIAI_COMMUNITY_URL", "https://api.asiai.dev/api/v1").rstrip("/")

    url = f"{api_url}/bench/card/{submission_id}.png"

    if not output_dir:
        output_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "asiai", "cards")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = os.path.join(output_dir, f"bench-card-{submission_id[:8]}.png")

    try:
        req = Request(url)
        with urlopen(req, timeout=30) as resp:
            data = resp.read(5 * 1024 * 1024)  # 5 MB cap
            with open(path, "wb") as f:
                f.write(data)
            return path
    except (HTTPError, URLError, OSError):
        return ""


def _escape(text: str) -> str:
    """Escape text for SVG XML."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
