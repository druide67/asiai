"""Full system + inference snapshot collection."""

from __future__ import annotations

import logging
import time

from asiai.collectors.system import (
    collect_cpu_cores,
    collect_cpu_load,
    collect_memory,
    collect_thermal,
    collect_uptime,
)
from asiai.engines.base import InferenceEngine

logger = logging.getLogger("asiai.collectors.snapshot")


def collect_snapshot(engines: list[InferenceEngine]) -> dict:
    """Collect a full snapshot: system metrics + inference models.

    Args:
        engines: List of detected inference engines to query.

    Returns:
        Dict with all metrics, suitable for store_snapshot().
    """
    cpu = collect_cpu_load()
    mem = collect_memory()
    thermal = collect_thermal()

    # Collect models from all engines
    models: list[dict] = []
    engine_names: list[str] = []
    engine_versions: list[str] = []

    for engine in engines:
        try:
            running = engine.list_running()
            for m in running:
                models.append(
                    {
                        "engine": engine.name,
                        "name": m.name,
                        "size_vram": m.size_vram,
                        "size_total": m.size_total,
                        "format": m.format,
                        "quantization": m.quantization,
                    }
                )
            engine_names.append(engine.name)
            version = engine.version()
            if version:
                engine_versions.append(f"{engine.name}/{version}")
        except Exception as e:
            logger.warning("Engine %s error: %s", engine.name, e)

    return {
        "ts": int(time.time()),
        "cpu_load_1": cpu.load_1,
        "cpu_load_5": cpu.load_5,
        "cpu_load_15": cpu.load_15,
        "cpu_cores": collect_cpu_cores(),
        "mem_total": mem.total,
        "mem_used": mem.used,
        "mem_pressure": mem.pressure,
        "thermal_level": thermal.level,
        "thermal_speed_limit": thermal.speed_limit,
        "uptime": collect_uptime(),
        "inference_engine": ",".join(engine_names) if engine_names else "none",
        "engine_version": ",".join(engine_versions) if engine_versions else "",
        "models": models,
    }


def collect_engines_status(engines: list[InferenceEngine]) -> list[dict]:
    """Collect status for each engine without failing on unreachable ones.

    Returns:
        List of dicts: {name, url, reachable, version, models, vram_total}
    """
    statuses = []
    for engine in engines:
        entry: dict = {
            "name": engine.name,
            "url": engine.base_url,
            "reachable": False,
            "version": "",
            "models": [],
            "vram_total": 0,
        }
        try:
            entry["reachable"] = engine.is_reachable()
            if entry["reachable"]:
                entry["version"] = engine.version() or ""
                running = engine.list_running()
                vram_total = 0
                for m in running:
                    entry["models"].append(
                        {
                            "name": m.name,
                            "size_vram": m.size_vram,
                            "format": m.format,
                            "quantization": m.quantization,
                            "context_length": m.context_length,
                        }
                    )
                    vram_total += m.size_vram
                entry["vram_total"] = vram_total
        except Exception as e:
            logger.warning("Engine %s status error: %s", engine.name, e)
        statuses.append(entry)
    return statuses


def collect_full_snapshot(engines: list[InferenceEngine]) -> dict:
    """Extended snapshot: system metrics + per-engine status.

    Combines collect_snapshot() data with detailed per-engine status.
    """
    base = collect_snapshot(engines)
    base["engines_status"] = collect_engines_status(engines)
    return base


