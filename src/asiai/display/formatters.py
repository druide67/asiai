"""Output formatting helpers for CLI display."""

from __future__ import annotations

import os
import sys

# --- ANSI color helpers ---


def _supports_color() -> bool:
    """Check if the terminal supports ANSI colors."""
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty"):
        return False
    return sys.stdout.isatty()


_COLOR = _supports_color()


def _wrap(code: str, text: str) -> str:
    if not _COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def bold(text: str) -> str:
    return _wrap("1", text)


def dim(text: str) -> str:
    return _wrap("2", text)


def green(text: str) -> str:
    return _wrap("32", text)


def yellow(text: str) -> str:
    return _wrap("33", text)


def red(text: str) -> str:
    return _wrap("31", text)



# --- Value formatters ---


def format_bytes(n: int) -> str:
    """Format byte count as human-readable string (e.g. '12.3 GB')."""
    if n < 0:
        return "N/A"
    if n >= 1_073_741_824:
        return f"{n / 1_073_741_824:.1f} GB"
    if n >= 1_048_576:
        return f"{n / 1_048_576:.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n} B"


def format_uptime(seconds: int) -> str:
    """Format seconds as human-readable uptime (e.g. '3d 12h 5m')."""
    if seconds < 0:
        return "N/A"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def format_pressure(pressure: str) -> str:
    """Color-code memory pressure level."""
    if pressure == "normal":
        return green(pressure)
    if pressure == "warn":
        return yellow(pressure)
    if pressure == "critical":
        return red(pressure)
    return dim(pressure)


def format_thermal(level: str) -> str:
    """Color-code thermal level."""
    if level == "nominal":
        return green(level)
    if level == "fair":
        return yellow(level)
    if level in ("serious", "critical"):
        return red(level)
    return dim(level)
