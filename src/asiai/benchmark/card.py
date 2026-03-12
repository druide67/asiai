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
) -> str:
    """Generate an SVG benchmark card (1200x630) from aggregated results.

    Design: dark theme, terminal-inspired, asiai branding.
    """
    model = _format_model_name(report.get("model", "Unknown"))
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
        runs = data.get("runs_count", 0)
        bars.append({
            "name": eng_name,
            "tok_s": tok_s,
            "ttft_ms": ttft,
            "stability": stability,
            "vram_bytes": vram,
            "runs_count": runs,
        })
        if tok_s > max_tok:
            max_tok = tok_s

    # Sort by tok/s descending
    bars.sort(key=lambda b: b["tok_s"], reverse=True)

    # --- Layout constants ---
    bar_x = 480
    bar_max_width = 520
    bar_height = 38
    bar_gap = 14
    bar_start_y = 225
    num_bars = min(len(bars), 4)

    # --- Bar chart ---
    bar_elements = []
    for i, bar in enumerate(bars[:4]):
        y = bar_start_y + i * (bar_height + bar_gap)
        ratio = (bar["tok_s"] / max_tok) if max_tok > 0 else 0
        width = max(int(ratio * bar_max_width), 60)

        fill = "#00d4aa" if i == 0 else "#4a5568"

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
        label_text = f'{bar["tok_s"]:.1f} tok/s'
        label_width = len(label_text) * 8.5
        label_outside_x = bar_x + width + 10
        if label_outside_x + label_width > _FRAME_RIGHT:
            # Inside bar (right-aligned, dark text)
            bar_elements.append(
                f'  <text x="{bar_x + width - 10}" y="{y + 26}" '
                f'text-anchor="end" fill="#0f1117" font-size="14" '
                f'font-weight="600" font-family="{_MONO}">{label_text}</text>'
            )
        else:
            # Outside bar
            bar_elements.append(
                f'  <text x="{label_outside_x}" y="{y + 26}" '
                f'fill="#e2e8f0" font-size="14" '
                f'font-family="{_MONO}">{label_text}</text>'
            )

    bars_svg = "\n".join(bar_elements)

    # --- Dynamic positions based on bar count ---
    bars_end_y = bar_start_y + num_bars * (bar_height + bar_gap)

    # --- Hero number (the "2.4x" wow factor) ---
    hero_svg = ""
    if winner:
        delta_raw = winner.get("tok_s_delta", "")
        # Extract multiplier: "2.4x faster" → "2.4×"
        delta_num = delta_raw.split()[0] if delta_raw else ""
        if delta_num:
            delta_display = delta_num.replace("x", "×")
            hero_y = bars_end_y + 50
            hero_svg = (
                f'  <text x="330" y="{hero_y}" text-anchor="middle" '
                f'fill="#00d4aa" font-size="52" '
                f'font-family="{_SANS}" font-weight="800">{_escape(delta_display)}</text>\n'
                f'  <text x="330" y="{hero_y + 28}" text-anchor="middle" '
                f'fill="#718096" font-size="15" '
                f'font-family="{_SANS}">{_escape(winner["name"])} wins</text>'
            )
    elif bars:
        # Single engine, no comparison
        hero_y = bars_end_y + 50
        hero_svg = (
            f'  <text x="330" y="{hero_y}" text-anchor="middle" '
            f'fill="#00d4aa" font-size="42" '
            f'font-family="{_SANS}" font-weight="800">'
            f'{bars[0]["tok_s"]:.1f} tok/s</text>'
        )

    # --- Metric chips (bigger, with runs info) ---
    chips = []
    if bars:
        best = bars[0]
        chips.append(f'{best["tok_s"]:.1f} tok/s')
        if best["ttft_ms"] > 0:
            chips.append(f'{best["ttft_ms"]:.0f}ms TTFT')
        if best["stability"]:
            chips.append(best["stability"])
        if best["vram_bytes"] > 0:
            chips.append(_format_vram(best["vram_bytes"]))
        if best.get("runs_count", 0) > 1:
            chips.append(f'{best["runs_count"]} runs \u00b7 median')

    chip_y = (bars_end_y + 110) if winner else (bars_end_y + 80)
    chip_elements = []
    chip_x = 60
    for chip_text in chips[:5]:
        text_width = int(len(chip_text) * 7.2) + 22
        chip_elements.append(
            f'  <rect x="{chip_x}" y="{chip_y}" width="{text_width}" '
            f'height="30" rx="15" fill="#2d3748"/>'
        )
        chip_elements.append(
            f'  <text x="{chip_x + text_width // 2}" y="{chip_y + 20}" '
            f'text-anchor="middle" fill="#a0aec0" font-size="13" '
            f'font-family="{_SANS}">{_escape(chip_text)}</text>'
        )
        chip_x += text_width + 10

    chips_svg = "\n".join(chip_elements)

    # --- Terminal frame height (dynamic) ---
    frame_bottom = max(chip_y + 50, 520)
    frame_height = frame_bottom - 170

    # --- Hardware chip badge (top-right, prominent) ---
    hw_badge = ""
    if hw_chip:
        badge_text = _escape(hw_chip)
        badge_w = int(len(hw_chip) * 8) + 28
        badge_x = 1140 - badge_w
        hw_badge = (
            f'  <rect x="{badge_x}" y="46" width="{badge_w}" height="32" '
            f'rx="16" fill="#2d3748" stroke="#4a5568" stroke-width="1"/>\n'
            f'  <text x="{badge_x + badge_w // 2}" y="67" text-anchor="middle" '
            f'fill="#e2e8f0" font-size="14" '
            f'font-family="{_SANS}" font-weight="500">{badge_text}</text>'
        )

    # --- Logo + tagline ---
    # Real speedometer logo (from assets/logo.svg, scaled to 40px)
    logo = (
        '  <g transform="translate(38, 32) scale(0.22)">\n'
        '    <circle cx="100" cy="100" r="90" fill="#0f0f23"/>\n'
        '    <circle cx="100" cy="100" r="86" fill="none" stroke="#00d4aa" stroke-width="0.5" opacity="0.15"/>\n'
        '    <line x1="30.4" y1="148.8" x2="43.5" y2="139.6" stroke="#00d4aa" stroke-width="3.2" stroke-linecap="round" opacity="0.3"/>\n'
        '    <line x1="15.5" y1="109.1" x2="31.4" y2="107.4" stroke="#00d4aa" stroke-width="3.2" stroke-linecap="round" opacity="0.37"/>\n'
        '    <line x1="21.6" y1="67.2" x2="36.3" y2="73.4" stroke="#00d4aa" stroke-width="3.2" stroke-linecap="round" opacity="0.44"/>\n'
        '    <line x1="47.1" y1="33.4" x2="57.1" y2="46.0" stroke="#00d4aa" stroke-width="3.2" stroke-linecap="round" opacity="0.51"/>\n'
        '    <line x1="85.8" y1="16.2" x2="88.5" y2="32.0" stroke="#00d4aa" stroke-width="3.2" stroke-linecap="round" opacity="0.58"/>\n'
        '    <line x1="128.0" y1="19.7" x2="122.7" y2="34.9" stroke="#00d4aa" stroke-width="3.2" stroke-linecap="round" opacity="0.65"/>\n'
        '    <line x1="163.2" y1="43.2" x2="151.3" y2="53.9" stroke="#00d4aa" stroke-width="3.2" stroke-linecap="round" opacity="0.72"/>\n'
        '    <line x1="182.8" y1="80.8" x2="167.2" y2="84.4" stroke="#00d4aa" stroke-width="3.2" stroke-linecap="round" opacity="0.78"/>\n'
        '    <line x1="181.8" y1="123.1" x2="166.4" y2="118.8" stroke="#00d4aa" stroke-width="3.2" stroke-linecap="round" opacity="0.85"/>\n'
        '    <path d="M136.8,63.2 L101.98,101.98 L98.02,98.02 Z" fill="#00d4aa"/>\n'
        '    <circle cx="100" cy="100" r="3.5" fill="#00d4aa"/>\n'
        '  </g>\n'
        f'  <text x="86" y="70" fill="#e2e8f0" font-size="28" '
        f'font-family="{_SANS}" font-weight="700">'
        f'asi<tspan fill="#00d4aa">ai</tspan></text>\n'
        f'  <text x="194" y="70" fill="#718096" font-size="14" '
        f'font-family="{_SANS}">The Speedtest for local LLMs</text>'
    )

    # --- Footer URL (prominent pill) ---
    url_text = "asiai.dev"
    url_w = int(len(url_text) * 8) + 28
    url_x = 1140 - url_w
    footer_y = frame_bottom + 10
    footer = (
        f'  <rect x="{url_x}" y="{footer_y}" width="{url_w}" height="28" '
        f'rx="14" fill="#1a202c" stroke="#00d4aa" stroke-width="1" opacity="0.8"/>\n'
        f'  <text x="{url_x + url_w // 2}" y="{footer_y + 19}" text-anchor="middle" '
        f'fill="#00d4aa" font-size="13" '
        f'font-family="{_SANS}" font-weight="500">{url_text}</text>'
    )

    esc_model = _escape(model)

    svg_lines = [
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
        "  <!-- Top accent bar -->",
        '  <rect x="0" y="0" width="1200" height="4" fill="#00d4aa"/>',
        "",
        "  <!-- Logo + tagline -->",
        logo,
        "",
        "  <!-- Hardware badge -->",
        hw_badge,
        "",
        "  <!-- Model name -->",
        f'  <text x="60" y="140" fill="#e2e8f0" font-size="26"'
        f' font-family="{_SANS}" font-weight="700">'
        f"{esc_model}</text>",
        "",
        f"  <!-- Terminal frame (dynamic height: {frame_height}px) -->",
        f'  <rect x="{_FRAME_LEFT}" y="170" width="1120" height="{frame_height}"'
        ' rx="8" fill="#1a202c" stroke="#2d3748" stroke-width="1"/>',
        '  <circle cx="65" cy="190" r="5" fill="#fc5c65"/>',
        '  <circle cx="85" cy="190" r="5" fill="#fed330"/>',
        '  <circle cx="105" cy="190" r="5" fill="#26de81"/>',
        f'  <text x="130" y="195" fill="#718096" font-size="12"'
        f' font-family="{_MONO}">asiai bench</text>',
        "",
        "  <!-- Bars -->",
        bars_svg,
        "",
        "  <!-- Hero number -->",
        hero_svg,
        "",
        "  <!-- Metric chips -->",
        chips_svg,
        "",
        "  <!-- Footer -->",
        footer,
        "</svg>",
    ]
    return "\n".join(svg_lines)


def save_card(svg: str, fmt: str = "svg", output_dir: str = "") -> str:
    """Save card to file. Returns the file path."""
    if fmt not in _VALID_FORMATS:
        fmt = "svg"

    if not output_dir:
        output_dir = os.path.join(
            os.path.expanduser("~"), ".local", "share", "asiai", "cards"
        )

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
        api_url = os.environ.get(
            "ASIAI_COMMUNITY_URL", "https://api.asiai.dev/api/v1"
        ).rstrip("/")

    url = f"{api_url}/bench/card/{submission_id}.png"

    if not output_dir:
        output_dir = os.path.join(
            os.path.expanduser("~"), ".local", "share", "asiai", "cards"
        )

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = os.path.join(output_dir, f"bench-card-{submission_id[:8]}.png")

    try:
        req = Request(url)
        with urlopen(req, timeout=10) as resp:
            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > _MAX_DOWNLOAD_BYTES:
                logger.warning(
                    "PNG too large (%s bytes), skipping download", content_length
                )
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
        site = base.replace("api.", "", 1).split("/api")[0]
    else:
        site = "https://asiai.dev"
    return f"{site}/card/{submission_id}"


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
