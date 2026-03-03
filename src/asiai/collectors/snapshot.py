"""Full system + inference snapshot collection."""

from __future__ import annotations

import logging
import threading
import time

from asiai.collectors.system import (
    collect_cpu_cores,
    collect_cpu_load,
    collect_memory,
    collect_thermal,
    collect_uptime,
)
from asiai.engines.base import InferenceEngine
from asiai.storage.db import purge_old, store_snapshot
from asiai.storage.schema import RETENTION_DAYS

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


class CollectorThread(threading.Thread):
    """Background thread that periodically collects and stores snapshots."""

    def __init__(
        self,
        db_path: str,
        interval: int,
        engines: list[InferenceEngine],
    ) -> None:
        super().__init__(daemon=True)
        self.db_path = db_path
        self.interval = interval
        self.engines = engines
        self._stop_event = threading.Event()
        self.last_snapshot: dict | None = None

    def run(self) -> None:
        logger.info("Collector started (interval=%ds)", self.interval)
        while not self._stop_event.is_set():
            try:
                snap = collect_snapshot(self.engines)
                self.last_snapshot = snap
                store_snapshot(self.db_path, snap)
                # Purge approximately every 24h
                if snap["ts"] % 86400 < self.interval:
                    deleted = purge_old(self.db_path)
                    if deleted:
                        logger.info(
                            "Purged %d entries older than %d days",
                            deleted,
                            RETENTION_DAYS,
                        )
            except Exception as e:
                logger.error("Collector error: %s", e)
            self._stop_event.wait(self.interval)

    def stop(self) -> None:
        """Signal the collector to stop."""
        self._stop_event.set()
