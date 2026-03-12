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

    # --- Bar chart ---
    bar_x = 520
    bar_max_width = 580
    bar_height = 36
    bar_gap = 14
    bar_start_y = 245

    bar_elements = []
    for i, bar in enumerate(bars[:4]):  # Max 4 engines
        y = bar_start_y + i * (bar_height + bar_gap)
        ratio = (bar["tok_s"] / max_tok) if max_tok > 0 else 0
        width = max(int(ratio * bar_max_width), 60)  # Min 60px for readability

        # Winner gets accent color, others get muted
        fill = "#00d4aa" if i == 0 else "#4a5568"

        bar_elements.append(
            f'  <text x="{bar_x - 10}" y="{y + 24}" '
            f'text-anchor="end" fill="#e2e8f0" font-size="15" '
            f'font-family="{_MONO}">{_escape(bar["name"])}</text>'
        )
        bar_elements.append(
            f'  <rect x="{bar_x}" y="{y}" width="{width}" height="{bar_height}" '
            f'rx="4" fill="{fill}" opacity="0.9"/>'
        )
        bar_elements.append(
            f'  <text x="{bar_x + width + 8}" y="{y + 24}" '
            f'fill="#e2e8f0" font-size="14" '
            f'font-family="{_MONO}">{bar["tok_s"]:.1f} tok/s</text>'
        )

    bars_svg = "\n".join(bar_elements)

    # --- Metric chips ---
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

    chip_elements = []
    chip_x = 60
    chip_y = 540
    for chip_text in chips[:4]:
        text_width = int(len(chip_text) * 6.5) + 20  # G6: proportional font factor
        chip_elements.append(
            f'  <rect x="{chip_x}" y="{chip_y}" width="{text_width}" '
            f'height="28" rx="14" fill="#2d3748"/>'
        )
        chip_elements.append(
            f'  <text x="{chip_x + text_width // 2}" y="{chip_y + 19}" '
            f'text-anchor="middle" fill="#a0aec0" font-size="12" '
            f'font-family="{_SANS}">{_escape(chip_text)}</text>'
        )
        chip_x += text_width + 10

    chips_svg = "\n".join(chip_elements)

    # --- Winner line ---
    winner_text = ""
    if winner:
        delta = winner.get("tok_s_delta", "")
        winner_text = (
            f'  <text x="60" y="500" fill="#00d4aa" font-size="16" '
            f'font-family="{_SANS}" font-weight="600">'
            f'Winner: {_escape(winner["name"])}'
            + (f" ({_escape(delta)})" if delta else "")
            + "</text>"
        )

    # --- Hardware chip badge (top-right, prominent) --- M3
    hw_badge = ""
    if hw_chip:
        badge_text = _escape(hw_chip)
        badge_w = int(len(hw_chip) * 7.5) + 24
        badge_x = 1140 - badge_w
        hw_badge = (
            f'  <rect x="{badge_x}" y="48" width="{badge_w}" height="30" '
            f'rx="15" fill="#2d3748" stroke="#4a5568" stroke-width="1"/>\n'
            f'  <text x="{badge_x + badge_w // 2}" y="68" text-anchor="middle" '
            f'fill="#e2e8f0" font-size="13" '
            f'font-family="{_SANS}" font-weight="500">{badge_text}</text>'
        )

    # --- Column headers (aligned with bars) --- G1
    header_line = (
        f'  <text x="{bar_x - 10}" y="230" text-anchor="end" fill="#a0aec0" '
        f'font-size="12" font-family="{_MONO}">Engine</text>\n'
        f'  <text x="{bar_x}" y="230" fill="#a0aec0" '
        f'font-size="12" font-family="{_MONO}">tok/s</text>'
    )

    # --- Logo mark + tagline --- G3, M1
    logo = (
        f'  <rect x="50" y="42" width="30" height="30" rx="7" '
        f'fill="#00d4aa" opacity="0.2"/>\n'
        f'  <text x="65" y="64" text-anchor="middle" fill="#00d4aa" '
        f'font-size="16" font-family="{_SANS}" font-weight="800">ai</text>\n'
        f'  <text x="90" y="70" fill="#e2e8f0" font-size="28" '
        f'font-family="{_SANS}" font-weight="700">'
        f'asi<tspan fill="#00d4aa">ai</tspan></text>\n'
        f'  <text x="200" y="70" fill="#718096" font-size="14" '
        f'font-family="{_SANS}">The Speedtest for local LLMs</text>'
    )

    # --- Footer URL (prominent pill badge) --- M2
    url_text = "asiai.dev"
    url_w = int(len(url_text) * 8) + 28
    url_x = 1140 - url_w
    footer = (
        f'  <rect x="{url_x}" y="585" width="{url_w}" height="28" '
        f'rx="14" fill="#1a202c" stroke="#00d4aa" stroke-width="1" opacity="0.8"/>\n'
        f'  <text x="{url_x + url_w // 2}" y="604" text-anchor="middle" '
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
        f'  <text x="60" y="140" fill="#e2e8f0" font-size="24"'
        f' font-family="{_SANS}" font-weight="600">'
        f"{esc_model}</text>",
        "",
        "  <!-- Terminal frame -->",
        '  <rect x="40" y="170" width="1120" height="380"'
        ' rx="8" fill="#1a202c" stroke="#2d3748" stroke-width="1"/>',
        '  <circle cx="65" cy="190" r="5" fill="#fc5c65"/>',
        '  <circle cx="85" cy="190" r="5" fill="#fed330"/>',
        '  <circle cx="105" cy="190" r="5" fill="#26de81"/>',
        f'  <text x="130" y="195" fill="#718096" font-size="12"'
        f' font-family="{_MONO}">asiai bench</text>',
        "",
        "  <!-- Column headers -->",
        header_line,
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
        footer,
        "</svg>",
    ]
    return "\n".join(svg_lines)


def save_card(svg: str, fmt: str = "svg", output_dir: str = "") -> str:
    """Save card to file. Returns the file path."""
    if fmt not in _VALID_FORMATS:  # P6: validate format
        fmt = "svg"

    if not output_dir:
        output_dir = os.path.join(
            os.path.expanduser("~"), ".local", "share", "asiai", "cards"
        )

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # P2: pid suffix avoids collision within same second
    ts = f"{int(time.time())}_{os.getpid()}"
    filename = f"bench-card-{ts}.{fmt}"
    path = os.path.join(output_dir, filename)

    with open(path, "w") as f:
        f.write(svg)

    return path


def convert_svg_to_png(svg_path: str, png_path: str = "") -> str:
    """Convert SVG to PNG using macOS native sips. Returns path or empty string.

    O2: Enables local PNG generation without --share.
    """
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
    logger.debug("sips SVG→PNG conversion failed, SVG-only available")
    return ""


def download_card_png(
    submission_id: str,
    api_url: str = "",
    output_dir: str = "",
) -> str:
    """Download PNG card from API. Returns file path or empty string on failure."""
    # X2: validate submission_id format  /  P5: reject < 8 chars
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
        with urlopen(req, timeout=10) as resp:  # D2: 10s timeout
            # P3: check Content-Length before downloading
            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > _MAX_DOWNLOAD_BYTES:
                logger.warning(
                    "PNG too large (%s bytes), skipping download", content_length
                )
                return ""

            data = resp.read(_MAX_DOWNLOAD_BYTES)

            # X1: verify PNG magic bytes
            if not data.startswith(_PNG_MAGIC):
                logger.warning("Downloaded file is not a valid PNG")
                return ""

            with open(path, "wb") as f:
                f.write(data)
            return path
    except (HTTPError, URLError, OSError) as exc:
        # P1: log instead of silently swallowing
        logger.warning("PNG card download failed: %s", exc)
        return ""


def get_share_url(submission_id: str) -> str:
    """Get shareable card URL, respecting ASIAI_COMMUNITY_URL env var.

    A1: derives URL from same env var as download, not hardcoded.
    """
    base = os.environ.get("ASIAI_COMMUNITY_URL", "").rstrip("/")
    if base:
        # https://api.asiai.dev/api/v1 → https://asiai.dev
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
        .replace("'", "&#39;")  # P4: single quotes
    )


def _format_vram(vram_bytes: int) -> str:
    """Format VRAM to human-readable. G5: round when .0."""
    vram_gb = vram_bytes / (1024**3)
    if vram_gb == int(vram_gb):
        return f"{int(vram_gb)} GB VRAM"
    return f"{vram_gb:.1f} GB VRAM"


def _validate_submission_id(submission_id: str) -> bool:
    """Validate submission ID: alphanumeric + hyphens/underscores, min 8 chars."""
    return bool(_SUBMISSION_ID_RE.match(submission_id))
