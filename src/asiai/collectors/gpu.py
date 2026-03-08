"""GPU utilization collection via ioreg (Apple Silicon).

Uses ``ioreg -r -c AGXAccelerator`` to read GPU performance statistics
without requiring sudo privileges. Tested on M1 Max, M4 Pro.
"""

from __future__ import annotations

import logging
import plistlib
import subprocess
from dataclasses import dataclass

logger = logging.getLogger("asiai.collectors.gpu")


@dataclass
class GpuInfo:
    """GPU utilization and memory from AGXAccelerator."""

    utilization_pct: float = -1.0
    renderer_pct: float = -1.0
    tiler_pct: float = -1.0
    mem_in_use: int = 0
    mem_allocated: int = 0


def collect_gpu() -> GpuInfo:
    """Collect GPU stats via ioreg -r -c AGXAccelerator -a.

    Returns GpuInfo with defaults (-1 / 0) if ioreg is unavailable or parsing fails.
    """
    try:
        out = subprocess.run(
            ["ioreg", "-r", "-c", "AGXAccelerator", "-a"],
            capture_output=True,
            timeout=5,
        )
        if out.returncode != 0 or not out.stdout:
            logger.debug("ioreg returned no data (rc=%d)", out.returncode)
            return GpuInfo()

        entries = plistlib.loads(out.stdout)
        if not isinstance(entries, list) or not entries:
            return GpuInfo()

        # Take the first AGXAccelerator entry
        entry = entries[0]
        perf = entry.get("PerformanceStatistics", {})
        if not isinstance(perf, dict):
            return GpuInfo()

        return GpuInfo(
            utilization_pct=_pct(perf.get("Device Utilization %")),
            renderer_pct=_pct(perf.get("Renderer Utilization %")),
            tiler_pct=_pct(perf.get("Tiler Utilization %")),
            mem_in_use=_int(perf.get("In use system memory", 0)),
            mem_allocated=_int(perf.get("Allocated system memory", 0)),
        )
    except Exception as e:
        logger.debug("GPU collection failed: %s", e)
        return GpuInfo()


def _pct(value: object) -> float:
    """Convert a PerformanceStatistics percentage to float, or -1 if missing."""
    if value is None:
        return -1.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return -1.0


def _int(value: object) -> int:
    """Convert to int, or 0 if invalid."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
