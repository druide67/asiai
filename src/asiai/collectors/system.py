"""macOS system metrics collection (Apple Silicon).

Uses native commands (sysctl, vm_stat, pmset) — no external dependencies.
"""

from __future__ import annotations

import ctypes
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
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        # Format: "{ 0.45 0.62 0.58 }" (comma decimal on FR locale)
        parts = out.strip("{ }").split()
        return CpuLoad(
            load_1=float(parts[0].replace(",", ".")),
            load_5=float(parts[1].replace(",", ".")),
            load_15=float(parts[2].replace(",", ".")),
        )
    except Exception as e:
        logger.warning("cpu_load: %s", e)
        return CpuLoad()


def collect_cpu_cores() -> int:
    """Number of logical CPU cores."""
    try:
        out = subprocess.run(
            ["sysctl", "-n", "hw.logicalcpu"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        return int(out)
    except Exception:
        return -1


def collect_memory() -> MemoryInfo:
    """RAM total/used via vm_stat + sysctl, pressure via sysctl."""
    result = MemoryInfo()

    # Total RAM
    try:
        total_bytes = int(
            subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            ).stdout.strip()
        )
        result.total = total_bytes

        vm_out = subprocess.run(
            ["vm_stat"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
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
        level = int(
            subprocess.run(
                ["sysctl", "-n", "kern.memorystatus_vm_pressure_level"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            ).stdout.strip()
        )
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
                capture_output=True,
                text=True,
                timeout=10,
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


# Apple Silicon thermal pressure via notifyd (no sudo). The Intel sysctl OID
# machdep.xcpm.cpu_thermal_level is dead on M-series, so this is the only live
# signal. OSThermalPressureLevel: 0 nominal, 1 moderate, 2 heavy, 3 trapping,
# 4 sleeping — mapped to an approximate speed_limit for the throttle gates.
_THERMAL_NOTIFY_KEY = b"com.apple.system.thermalpressurelevel"
_THERMAL_LEVEL_MAP = {
    0: ("nominal", 100),
    1: ("fair", 80),
    2: ("serious", 50),
    3: ("critical", 25),
    4: ("critical", 10),
}


def _thermal_via_notifyd() -> ThermalInfo | None:
    """Read OSThermalPressureLevel from notifyd (Apple Silicon, no sudo).

    Returns None when the channel is unavailable (non-Darwin, or the register
    call fails) so the caller can fall back to the legacy sysctl/pmset path.
    """
    try:
        libc = ctypes.CDLL(None)
        libc.notify_register_check.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
        libc.notify_register_check.restype = ctypes.c_uint32
        libc.notify_get_state.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint64)]
        libc.notify_get_state.restype = ctypes.c_uint32
        libc.notify_cancel.argtypes = [ctypes.c_int]
        libc.notify_cancel.restype = ctypes.c_uint32

        token = ctypes.c_int(0)
        if libc.notify_register_check(_THERMAL_NOTIFY_KEY, ctypes.byref(token)) != 0:
            return None
        try:
            state = ctypes.c_uint64(0)
            if libc.notify_get_state(token.value, ctypes.byref(state)) != 0:
                return None
            level, speed = _THERMAL_LEVEL_MAP.get(int(state.value), ("unknown", -1))
            return ThermalInfo(level=level, speed_limit=speed) if speed >= 0 else None
        finally:
            libc.notify_cancel(token.value)
    except Exception:
        logger.debug("notifyd thermal read failed", exc_info=True)
        return None


def collect_thermal() -> ThermalInfo:
    """Thermal pressure via notifyd (Apple Silicon) with sysctl/pmset fallback."""
    notify_result = _thermal_via_notifyd()
    if notify_result is not None:
        return notify_result

    result = ThermalInfo()

    # Method 1: sysctl (Intel / older macOS — dead OID on Apple Silicon)
    try:
        out = subprocess.run(
            ["sysctl", "-n", "machdep.xcpm.cpu_thermal_level"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
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
                capture_output=True,
                text=True,
                timeout=5,
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


def collect_machine_info() -> str:
    """Return machine model and chip (e.g. 'MacBookPro18,3 — Apple M1 Pro')."""
    parts = []
    try:
        model = subprocess.run(
            ["sysctl", "-n", "hw.model"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        parts.append(model)
    except Exception:
        pass
    try:
        chip = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        parts.append(chip)
    except Exception:
        pass
    return " — ".join(parts) if parts else "unknown"


def collect_hw_chip() -> str:
    """Return the Apple Silicon chip name (e.g. 'Apple M4 Pro')."""
    try:
        return subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
    except Exception:
        return ""


def collect_os_version() -> str:
    """Return macOS version (e.g. '15.3')."""
    try:
        return subprocess.run(
            ["sw_vers", "-productVersion"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
    except Exception:
        return ""


@dataclass
class ProcessInfo:
    """Resource usage of an inference engine process."""

    name: str = ""
    cpu_pct: float = 0.0
    mem_pct: float = 0.0
    phys_footprint_bytes: int = 0  # ri_phys_footprint (dirty+compressed+iokit/Metal,
    # EXCLUDES clean file-backed mmap); falls back to RSS when rusage fails.
    resident_bytes: int = 0  # true RSS (ps resident_size): counts resident
    # file-backed mmap pages too, so it captures GGUF weights that phys_footprint
    # excludes — the honest, cross-family RAM figure on Apple Silicon UMA.


# ---------------------------------------------------------------------------
# Physical footprint via libproc (what Activity Monitor shows)
# More accurate than RSS: includes Metal/GPU allocations that are resident.
# ---------------------------------------------------------------------------


def _get_phys_footprint(pid: int) -> int:
    """Get physical footprint (bytes) for a process via proc_pid_rusage.

    Uses RUSAGE_INFO_V6.  ri_phys_footprint is at byte offset 72.
    Returns 0 on failure (wrong PID, permission denied, non-macOS).
    """
    try:
        import ctypes
        import ctypes.util

        lib = ctypes.util.find_library("proc")
        if not lib:
            return 0
        libproc = ctypes.CDLL(lib)
        buf = (ctypes.c_uint8 * 512)()
        ret = libproc.proc_pid_rusage(pid, 6, ctypes.byref(buf))
        if ret != 0:
            return 0
        import struct

        return struct.unpack_from("<Q", buf, 72)[0]
    except Exception:
        return 0


# Process name patterns for inference engines
_ENGINE_PATTERNS = ["ollama", "LM Studio", "lmstudio", "mlx_lm", "llama-server", "omlx", "vllm"]


def collect_engine_processes() -> list[ProcessInfo]:
    """Collect CPU%, MEM%, and physical footprint for inference engine processes."""
    try:
        out = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout
    except Exception as e:
        logger.warning("engine_processes: %s", e)
        return []

    # Aggregate by engine name (sum child processes)
    totals: dict[str, ProcessInfo] = {}
    for line in out.splitlines()[1:]:  # Skip header
        cols = line.split(None, 10)
        if len(cols) < 11:
            continue
        cmd = cols[10]
        for pattern in _ENGINE_PATTERNS:
            if pattern.lower() in cmd.lower():
                pat = pattern.lower()
                if "lm studio" in pat or "lmstudio" in pat:
                    key = "lmstudio"
                elif "mlx_lm" in pat:
                    key = "mlxlm"
                elif "llama-server" in pat:
                    key = "llamacpp"
                elif pat == "vllm":
                    key = "vllm_mlx"
                else:
                    key = pat
                if key not in totals:
                    totals[key] = ProcessInfo(name=key)
                totals[key].cpu_pct += float(cols[2].replace(",", "."))
                totals[key].mem_pct += float(cols[3].replace(",", "."))
                # Capture BOTH metrics per process: phys_footprint (dirty +
                # compressed + iokit/Metal, excludes clean file-backed mmap) and
                # the true RSS (resident_size from ps, KB), which DOES count the
                # resident GGUF weight pages that phys_footprint omits.
                pid = int(cols[1])
                rss = int(cols[5]) * 1024
                phys = _get_phys_footprint(pid)
                totals[key].phys_footprint_bytes += phys if phys > 0 else rss
                totals[key].resident_bytes += rss
                break

    return list(totals.values())


def _engine_match_key(engine_name: str | None) -> str:
    """Canonical key to match an engine against ``collect_engine_processes()``.

    Aux llama.cpp instances (``llamacpp-aux``, ``llamacpp-aux-N``) alias to the
    ``llamacpp`` key the collector emits; everything else is lowercased with
    ``-``/``_`` stripped. This is the single source of truth for engine-name
    normalization (the collector produces the keys, so the matcher lives here).
    """
    if not engine_name:
        return ""
    name = "llamacpp" if engine_name.startswith("llamacpp-aux") else engine_name
    return name.lower().replace("-", "").replace("_", "")


def find_engine_process(engine_name: str | None) -> ProcessInfo | None:
    """The aggregated ProcessInfo for ``engine_name``, matched by canonical key.

    Use this instead of ``p.name == engine_name``: the collector emits canonical
    keys ('llamacpp', 'mlxlm', 'lmstudio', 'vllm_mlx') that differ from adapter
    names ('llamacpp-aux', 'mlx-lm', 'vllm-mlx'), so a direct equality misses
    MLX/aux engines. ``None`` when no name or no matching process.
    """
    target = _engine_match_key(engine_name)
    if not target:
        return None
    for p in collect_engine_processes():
        if _engine_match_key(p.name) == target:
            return p
    return None


def collect_uptime() -> int:
    """System uptime in seconds via sysctl kern.boottime."""
    try:
        out = subprocess.run(
            ["sysctl", "-n", "kern.boottime"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout
        # Format: "{ sec = 1234567890, usec = 0 }"
        m = re.search(r"sec\s*=\s*(\d+)", out)
        if m:
            boot_ts = int(m.group(1))
            return int(time.time()) - boot_ts
    except Exception as e:
        logger.warning("uptime: %s", e)
    return -1
