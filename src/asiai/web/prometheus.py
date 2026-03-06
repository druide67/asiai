"""Prometheus exposition format formatter (zero dependencies)."""

from __future__ import annotations

_PRESSURE_MAP = {"normal": 0, "warn": 1, "critical": 2}


def _escape_label(value: str) -> str:
    """Escape label value for Prometheus format."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _gauge(name: str, help_text: str, value: float | int, labels: dict | None = None) -> str:
    """Format a single gauge metric with optional labels."""
    lines = [f"# HELP {name} {help_text}", f"# TYPE {name} gauge"]
    if labels:
        label_str = ",".join(f'{k}="{_escape_label(str(v))}"' for k, v in labels.items())
        lines.append(f"{name}{{{label_str}}} {value}")
    else:
        lines.append(f"{name} {value}")
    return "\n".join(lines)


def format_prometheus(snapshot: dict, benchmarks: list[dict] | None = None) -> str:
    """Convert a full snapshot dict to Prometheus exposition text format.

    Args:
        snapshot: Output from collect_full_snapshot().
        benchmarks: Optional latest benchmark results per engine+model.

    Returns:
        Prometheus text format string.
    """
    sections: list[str] = []

    # System metrics
    sections.append(
        _gauge("asiai_cpu_load_1m", "CPU load average 1 minute", snapshot.get("cpu_load_1", 0))
    )
    sections.append(
        _gauge("asiai_cpu_load_5m", "CPU load average 5 minutes", snapshot.get("cpu_load_5", 0))
    )
    sections.append(
        _gauge("asiai_cpu_load_15m", "CPU load average 15 minutes", snapshot.get("cpu_load_15", 0))
    )
    sections.append(
        _gauge("asiai_memory_used_bytes", "Memory used in bytes", snapshot.get("mem_used", 0))
    )
    sections.append(
        _gauge("asiai_memory_total_bytes", "Total memory in bytes", snapshot.get("mem_total", 0))
    )

    pressure = _PRESSURE_MAP.get(snapshot.get("mem_pressure", "normal"), 0)
    sections.append(
        _gauge(
            "asiai_memory_pressure_level",
            "Memory pressure level (0=normal 1=warn 2=critical)",
            pressure,
        )
    )

    speed_limit = snapshot.get("thermal_speed_limit", 100)
    sections.append(
        _gauge("asiai_thermal_speed_limit_pct", "CPU speed limit percentage", speed_limit)
    )

    # Per-engine metrics
    engines_status = snapshot.get("engines_status", [])
    if engines_status:
        engine_lines: list[str] = [
            "# HELP asiai_engine_reachable Whether the engine is reachable (0 or 1)",
            "# TYPE asiai_engine_reachable gauge",
        ]
        models_loaded_lines: list[str] = [
            "# HELP asiai_engine_models_loaded Number of models loaded",
            "# TYPE asiai_engine_models_loaded gauge",
        ]
        vram_lines: list[str] = [
            "# HELP asiai_engine_vram_bytes Total VRAM used by engine",
            "# TYPE asiai_engine_vram_bytes gauge",
        ]
        info_lines: list[str] = [
            "# HELP asiai_engine_version_info Engine version information",
            "# TYPE asiai_engine_version_info gauge",
        ]

        for es in engines_status:
            name = _escape_label(es["name"])
            reachable = 1 if es.get("reachable") else 0
            engine_lines.append(f'asiai_engine_reachable{{engine="{name}"}} {reachable}')
            models_loaded_lines.append(
                f'asiai_engine_models_loaded{{engine="{name}"}} {len(es.get("models", []))}'
            )
            vram_lines.append(
                f'asiai_engine_vram_bytes{{engine="{name}"}} {es.get("vram_total", 0)}'
            )
            version = _escape_label(es.get("version", ""))
            info_lines.append(f'asiai_engine_version_info{{engine="{name}",version="{version}"}} 1')

        sections.append("\n".join(engine_lines))
        sections.append("\n".join(models_loaded_lines))
        sections.append("\n".join(vram_lines))
        sections.append("\n".join(info_lines))

        # Per-model metrics
        model_vram: list[str] = [
            "# HELP asiai_model_vram_bytes VRAM used by model",
            "# TYPE asiai_model_vram_bytes gauge",
        ]
        model_ctx: list[str] = [
            "# HELP asiai_model_context_length Model context window size",
            "# TYPE asiai_model_context_length gauge",
        ]
        model_loaded: list[str] = [
            "# HELP asiai_model_loaded Whether the model is loaded (1=yes)",
            "# TYPE asiai_model_loaded gauge",
        ]

        for es in engines_status:
            ename = _escape_label(es["name"])
            for m in es.get("models", []):
                mname = _escape_label(m["name"])
                lbl = f'engine="{ename}",model="{mname}"'
                vram = m.get("size_vram", 0)
                model_vram.append(f"asiai_model_vram_bytes{{{lbl}}} {vram}")
                ctx = m.get("context_length", 0)
                model_ctx.append(f"asiai_model_context_length{{{lbl}}} {ctx}")
                model_loaded.append(f'asiai_model_loaded{{engine="{ename}",model="{mname}"}} 1')

        if any(len(lines) > 2 for lines in [model_vram, model_ctx, model_loaded]):
            sections.append("\n".join(model_vram))
            sections.append("\n".join(model_ctx))
            sections.append("\n".join(model_loaded))

    # Benchmark metrics (optional)
    if benchmarks:
        tok_lines = [
            "# HELP asiai_bench_tok_per_sec Last benchmark tokens per second",
            "# TYPE asiai_bench_tok_per_sec gauge",
        ]
        ttft_lines = [
            "# HELP asiai_bench_ttft_seconds Last benchmark time to first token",
            "# TYPE asiai_bench_ttft_seconds gauge",
        ]
        power_lines = [
            "# HELP asiai_bench_power_watts Last benchmark power consumption",
            "# TYPE asiai_bench_power_watts gauge",
        ]

        for b in benchmarks:
            ename = _escape_label(b.get("engine", ""))
            mname = _escape_label(b.get("model", ""))
            labels = f'engine="{ename}",model="{mname}"'
            tok_per_sec = b.get("tok_per_sec", 0)
            if tok_per_sec:
                tok_lines.append(f"asiai_bench_tok_per_sec{{{labels}}} {tok_per_sec}")
            ttft = b.get("ttft_ms", 0)
            if ttft:
                ttft_lines.append(f"asiai_bench_ttft_seconds{{{labels}}} {ttft / 1000.0}")
            power = b.get("power_watts", 0)
            if power:
                power_lines.append(f"asiai_bench_power_watts{{{labels}}} {power}")

        if len(tok_lines) > 2:
            sections.append("\n".join(tok_lines))
        if len(ttft_lines) > 2:
            sections.append("\n".join(ttft_lines))
        if len(power_lines) > 2:
            sections.append("\n".join(power_lines))

    return "\n\n".join(sections) + "\n"
