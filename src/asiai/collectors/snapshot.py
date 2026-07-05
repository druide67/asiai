"""Full system + inference snapshot collection."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request

from asiai.collectors.gpu import collect_gpu
from asiai.collectors.inference import count_tcp_connections
from asiai.collectors.system import (
    collect_cpu_cores,
    collect_cpu_load,
    collect_memory,
    collect_thermal,
    collect_uptime,
)
from asiai.engines.base import InferenceEngine
from asiai.engines.detect import extract_port

logger = logging.getLogger("asiai.collectors.snapshot")

# Loopback companion (aisctl serve). Same env knob as the fleet write proxy.
AISCTL_SERVE_URL = os.environ.get("ASIAI_AISCTL_SERVE_URL", "http://127.0.0.1:8898")

# Rich lifecycle states an aisctl-serve-equipped node can report. Mirrors
# ais_core.lifecycle.EngineState by VALUE (no import: asiai must not depend
# on asiai-inference-server) — unknown values are passed through untouched
# so a newer aisrv can add states without breaking older dashboards.
_LIFECYCLE_TIMEOUT = 3.0
_LIFECYCLE_MAX_BODY = 256 * 1024


def collect_snapshot(
    engines: list[InferenceEngine],
    ioreport_sampler: object | None = None,
) -> dict:
    """Collect a full snapshot: system metrics + inference models.

    Args:
        engines: List of detected inference engines to query.
        ioreport_sampler: Optional IOReportSampler for power metrics (no sudo).

    Returns:
        Dict with all metrics, suitable for store_snapshot().
    """
    cpu = collect_cpu_load()
    mem = collect_memory()
    thermal = collect_thermal()
    gpu = collect_gpu()

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

    result = {
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
        "gpu_utilization_pct": gpu.utilization_pct,
        "gpu_renderer_pct": gpu.renderer_pct,
        "gpu_tiler_pct": gpu.tiler_pct,
        "gpu_mem_in_use": gpu.mem_in_use,
        "gpu_mem_allocated": gpu.mem_allocated,
    }

    # Power via IOReport (no sudo) — if sampler available
    if ioreport_sampler is not None:
        try:
            reading = ioreport_sampler.sample()
            result["power_gpu_watts"] = reading.gpu_watts
            result["power_cpu_watts"] = reading.cpu_watts
            result["power_ane_watts"] = reading.ane_watts
            result["power_dram_watts"] = reading.dram_watts
            result["power_total_watts"] = reading.total_watts
            result["power_source"] = "ioreport"
        except Exception as e:
            logger.debug("IOReport power collection failed: %s", e)

    return result


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
            "tcp_connections": 0,
            "requests_processing": 0,
            "tokens_predicted_total": 0,
            "kv_cache_usage_ratio": -1.0,
            "kv_cache_compressed_bytes": 0,
            "kv_cache_original_bytes": 0,
            "kv_cache_tokens": 0,
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

                # Inference activity: TCP connections + scraped metrics
                port = extract_port(engine.base_url)
                entry["tcp_connections"] = count_tcp_connections(port)
                scraped = engine.scrape_metrics()
                entry["requests_processing"] = scraped.get("requests_processing", 0)
                entry["tokens_predicted_total"] = scraped.get("tokens_predicted_total", 0)
                entry["kv_cache_usage_ratio"] = scraped.get("kv_cache_usage_ratio", -1.0)
                # TurboQuant KV cache compression metrics
                entry["kv_cache_compressed_bytes"] = scraped.get("kv_cache_compressed_bytes", 0)
                entry["kv_cache_original_bytes"] = scraped.get("kv_cache_original_bytes", 0)
                entry["kv_cache_tokens"] = scraped.get("kv_cache_tokens", 0)
        except Exception as e:
            logger.warning("Engine %s status error: %s", engine.name, e)
        statuses.append(entry)
    return statuses


def _fetch_lifecycle_states() -> list[dict] | None:
    """Rich EngineStates from the co-located ``aisctl serve``, or None.

    Optional by design: a node without asiai-inference-server (or with
    ``aisctl serve`` down) simply keeps the HTTP-detection-only snapshot.
    """
    try:
        from asiai.auth import loopback
    except ImportError:  # pragma: no cover - auth is part of this package
        return None
    token = loopback.read_token()
    if not token:
        return None
    req = urllib.request.Request(
        f"{AISCTL_SERVE_URL}/internal/v1/engines-state",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        # nosec B310 — fixed loopback URL from a trusted env knob.
        with urllib.request.urlopen(req, timeout=_LIFECYCLE_TIMEOUT) as resp:  # noqa: S310
            raw = resp.read(_LIFECYCLE_MAX_BODY)
        data = json.loads(raw.decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    engines = data.get("engines") if isinstance(data, dict) else None
    return engines if isinstance(engines, list) else None


def _merge_lifecycle_states(statuses: list[dict]) -> list[dict]:
    """Join rich lifecycle states onto HTTP-detected statuses, by PORT.

    Detection names every llama.cpp instance "llamacpp"; the manifest side
    knows one engine per port. The port is therefore the join key:

    - a detected engine whose port matches a manifest gains ``state`` and
      ``display_name`` (e.g. ``llamacpp-aux-1`` instead of a third
      homonymous ``llamacpp``);
    - a manifest with NO detected engine (stopped, disabled, loaded,
      not_installed — nothing answers HTTP) is APPENDED as a minimal
      entry, so the fleet cockpit can finally show non-running engines.

    If two manifests declare the same port (misconfiguration), the last
    one wins in the index — harmless for display purposes.
    """
    entries = _fetch_lifecycle_states()
    if not entries:
        return statuses

    by_port: dict[int, dict] = {}
    for e in entries:
        port = e.get("port")
        if isinstance(port, int) and port > 0:
            by_port[port] = e

    matched_ports: set[int] = set()
    for s in statuses:
        port = extract_port(str(s.get("url", "")))
        m = by_port.get(port)
        if m is None:
            continue
        s["state"] = m.get("state")
        # The manifest name is BOTH the compact display ("llamacpp-aux-1"
        # instead of a third homonymous "llamacpp") and the identifier the
        # write funnel expects — action buttons must target it, or a click
        # on an aux card would command the base-manifest engine instead.
        s["engine_id"] = m.get("name")
        s["display_hint"] = m.get("display") or ""
        s["model"] = m.get("model")
        matched_ports.add(port)

    for port, m in sorted(by_port.items()):
        if port in matched_ports:
            continue
        statuses.append(
            {
                "name": m.get("name") or "engine",
                "engine_id": m.get("name"),
                "display_hint": m.get("display") or "",
                "model": m.get("model"),
                "url": f"http://127.0.0.1:{port}",
                "reachable": False,
                "state": m.get("state"),
                "version": "",
                "models": [],
                "vram_total": 0,
                "tcp_connections": 0,
                "requests_processing": 0,
                "tokens_predicted_total": 0,
                "kv_cache_usage_ratio": -1.0,
                "kv_cache_compressed_bytes": 0,
                "kv_cache_original_bytes": 0,
                "kv_cache_tokens": 0,
            }
        )
    return statuses


def collect_full_snapshot(
    engines: list[InferenceEngine],
    ioreport_sampler: object | None = None,
) -> dict:
    """Extended snapshot: system metrics + per-engine status.

    Combines collect_snapshot() data with detailed per-engine status,
    enriched with rich lifecycle states when ``aisctl serve`` runs on
    this node (see :func:`_merge_lifecycle_states`).
    """
    base = collect_snapshot(engines, ioreport_sampler=ioreport_sampler)
    base["engines_status"] = _merge_lifecycle_states(collect_engines_status(engines))
    return base
