"""macOS system metrics collection (Apple Silicon).

Uses native commands (sysctl, vm_stat, pmset) — no external dependencies.
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
from dataclasses import dataclass

logger = logging.getLogger("asiai.collectors.system")


@dataclass
class CpuLoad:
    """CPU load averages."""

    load_1: float = -1.0
    load_5: float = -1.0
    load_15: float = -1.0


@dataclass
class MemoryInfo:
    """RAM usage information."""

    total: int = 0
    used: int = 0
    pressure: str = "unknown"


@dataclass
class ThermalInfo:
    """Thermal throttling state."""

    level: str = "unknown"
    speed_limit: int = -1


def collect_cpu_load() -> CpuLoad:
    """Load average 1/5/15 min via sysctl."""
    try:
        out = subprocess.run(
            ["sysctl", "-n", "vm.loadavg"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
        # Format: "{ 0.45 0.62 0.58 }"
        parts = out.strip("{ }").split()
        return CpuLoad(
            load_1=float(parts[0]),
            load_5=float(parts[1]),
            load_15=float(parts[2]),
        )
    except Exception as e:
        logger.warning("cpu_load: %s", e)
        return CpuLoad()


def collect_cpu_cores() -> int:
    """Number of logical CPU cores."""
    try:
        out = subprocess.run(
            ["sysctl", "-n", "hw.logicalcpu"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
        return int(out)
    except Exception:
        return -1


def collect_memory() -> MemoryInfo:
    """RAM total/used via vm_stat + sysctl, pressure via sysctl."""
    result = MemoryInfo()

    # Total RAM
    try:
        total_bytes = int(subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip())
        result.total = total_bytes

        vm_out = subprocess.run(
            ["vm_stat"], capture_output=True, text=True, timeout=5, check=True,
        ).stdout

        page_size = 16384  # Apple Silicon default
        m = re.search(r"page size of (\d+) bytes", vm_out)
        if m:
            page_size = int(m.group(1))

        def extract(label: str) -> int:
            match = re.search(rf"{label}:\s+(\d+)", vm_out)
            return int(match.group(1)) * page_size if match else 0

        free = extract("Pages free")
        inactive = extract("Pages inactive")
        speculative = extract("Pages speculative")
        available = free + inactive + speculative
        result.used = total_bytes - available
    except Exception as e:
        logger.warning("memory: %s", e)

    # Memory pressure via sysctl
    try:
        level = int(subprocess.run(
            ["sysctl", "-n", "kern.memorystatus_vm_pressure_level"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip())
        # 1=normal, 2=warn, 4=critical
        if level <= 1:
            result.pressure = "normal"
        elif level == 2:
            result.pressure = "warn"
        else:
            result.pressure = "critical"
    except Exception:
        # Fallback: memory_pressure command (slow)
        try:
            mp_out = subprocess.run(
                ["memory_pressure"],
                capture_output=True, text=True, timeout=10,
            ).stdout.lower()
            if "normal" in mp_out:
                result.pressure = "normal"
            elif "warn" in mp_out:
                result.pressure = "warn"
            elif "critical" in mp_out:
                result.pressure = "critical"
        except Exception:
            pass

    return result


def collect_thermal() -> ThermalInfo:
    """Thermal pressure via sysctl and pmset."""
    result = ThermalInfo()

    # Method 1: sysctl (available on recent macOS)
    try:
        out = subprocess.run(
            ["sysctl", "-n", "machdep.xcpm.cpu_thermal_level"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
        level = int(out)
        if level == 0:
            result.level = "nominal"
            result.speed_limit = 100
        elif level <= 33:
            result.level = "fair"
            result.speed_limit = 100 - level
        elif level <= 70:
            result.level = "serious"
            result.speed_limit = 100 - level
        else:
            result.level = "critical"
            result.speed_limit = 100 - level
    except Exception:
        pass

    # Method 2: pmset -g therm (varies by macOS version)
    if result.level == "unknown":
        try:
            out = subprocess.run(
                ["pmset", "-g", "therm"],
                capture_output=True, text=True, timeout=5,
            ).stdout
            if "no thermal warning" in out.lower():
                result.level = "nominal"
                result.speed_limit = 100
            else:
                for pattern in [
                    r"CPU_Speed_Limit\s*=\s*(\d+)",
                    r"CPU_Scheduler_Limit\s*=\s*(\d+)",
                ]:
                    m = re.search(pattern, out)
                    if m:
                        result.speed_limit = int(m.group(1))
                        break

                m = re.search(r"[Tt]hermal\s+[Ss]tate\s*:\s*(\w+)", out)
                if m:
                    state = m.group(1).lower()
                    if state in ("nominal", "normal"):
                        result.level = "nominal"
                    elif state == "fair":
                        result.level = "fair"
                    elif state == "serious":
                        result.level = "serious"
                    elif state == "critical":
                        result.level = "critical"
                elif result.speed_limit == 100:
                    result.level = "nominal"
                elif result.speed_limit > 0:
                    if result.speed_limit >= 80:
                        result.level = "fair"
                    elif result.speed_limit >= 50:
                        result.level = "serious"
                    else:
                        result.level = "critical"
        except Exception as e:
            logger.warning("thermal pmset: %s", e)

    return result


def collect_uptime() -> int:
    """System uptime in seconds via sysctl kern.boottime."""
    try:
        out = subprocess.run(
            ["sysctl", "-n", "kern.boottime"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout
        # Format: "{ sec = 1234567890, usec = 0 }"
        m = re.search(r"sec\s*=\s*(\d+)", out)
        if m:
            boot_ts = int(m.group(1))
            return int(time.time()) - boot_ts
    except Exception as e:
        logger.warning("uptime: %s", e)
    return -1
