"""MCP resources for asiai -- read-only data endpoints."""

from __future__ import annotations

import json
import time

from asiai.mcp.server import mcp


@mcp.resource("asiai://status")
def resource_status() -> str:
    """Current inference health status.

    Returns a JSON string with memory pressure, thermal state,
    and GPU utilization.
    """
    from asiai.collectors.gpu import collect_gpu
    from asiai.collectors.system import collect_memory, collect_thermal

    mem = collect_memory()
    thermal = collect_thermal()
    gpu = collect_gpu()

    result = {
        "ts": int(time.time()),
        "memory_pressure": mem.pressure,
        "memory_used_pct": round(mem.used / mem.total * 100, 1) if mem.total > 0 else 0,
        "thermal_level": thermal.level,
        "thermal_speed_limit": thermal.speed_limit,
        "gpu_utilization_pct": gpu.utilization_pct,
        "gpu_renderer_pct": gpu.renderer_pct,
        "gpu_tiler_pct": gpu.tiler_pct,
    }
    return json.dumps(result, indent=2)


@mcp.resource("asiai://models")
def resource_models() -> str:
    """List of all currently loaded models across engines.

    Returns a JSON string with engine name, model name, VRAM,
    quantization, and context length for each loaded model.
    """
    from asiai.cli import _discover_engines

    engines = _discover_engines()
    models = []
    for engine in engines:
        try:
            if not engine.is_reachable():
                continue
            for m in engine.list_running():
                models.append(
                    {
                        "engine": engine.name,
                        "name": m.name,
                        "size_vram": m.size_vram,
                        "format": m.format,
                        "quantization": m.quantization,
                        "context_length": m.context_length,
                    }
                )
        except Exception:
            pass
    return json.dumps({"models": models, "total": len(models)}, indent=2)


@mcp.resource("asiai://system")
def resource_system() -> str:
    """System hardware information: chip, RAM, OS, cores, uptime.

    Returns a JSON string with hardware details relevant for
    LLM inference capacity assessment.
    """
    from asiai.collectors.system import (
        collect_cpu_cores,
        collect_hw_chip,
        collect_memory,
        collect_os_version,
        collect_uptime,
    )

    chip = collect_hw_chip()
    mem = collect_memory()
    cores = collect_cpu_cores()
    os_ver = collect_os_version()
    uptime = collect_uptime()

    result = {
        "chip": chip,
        "ram_total_gb": round(mem.total / (1024**3), 1),
        "ram_used_gb": round(mem.used / (1024**3), 1),
        "ram_pressure": mem.pressure,
        "cpu_cores": cores,
        "os_version": os_ver,
        "uptime_seconds": uptime,
    }
    return json.dumps(result, indent=2)
