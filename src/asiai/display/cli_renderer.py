"""CLI output renderers for monitor commands."""

from __future__ import annotations

import time
from datetime import datetime

from asiai.display.formatters import (
    bold,
    dim,
    format_bytes,
    format_pressure,
    format_thermal,
    format_uptime,
    green,
    red,
    yellow,
)


def _ts_to_str(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _time_ago(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s ago"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m ago"
    return f"{seconds // 86400}d ago"


def render_detect(engines: list[dict]) -> None:
    """Render engine detection results."""
    if not engines:
        print(dim("No inference engines detected."))
        print(dim("Checked default ports: localhost:11434 (Ollama), localhost:1234 (LM Studio)"))
        return

    print(bold("Detected engines:"))
    print()
    for e in engines:
        print(f"  {green('●')} {bold(e['name'])} {dim(e['version'])}")
        print(f"    URL: {e['url']}")
        if e.get("models"):
            print(f"    Running: {len(e['models'])} model(s)")
            for m in e["models"]:
                vram = format_bytes(m["size_vram"]) if m["size_vram"] else "N/A"
                print(f"      - {m['name']}  {dim(vram)}")
        print()


def render_snapshot(snap: dict) -> None:
    """Render a system + inference snapshot."""
    print(bold("System"))
    print(f"  Uptime:    {format_uptime(snap.get('uptime', -1))}")
    print(f"  CPU Load:  {snap.get('cpu_load_1', -1):.2f} / "
          f"{snap.get('cpu_load_5', -1):.2f} / "
          f"{snap.get('cpu_load_15', -1):.2f}  "
          f"{dim('(1m / 5m / 15m)')}")

    mem_total = snap.get("mem_total", 0)
    mem_used = snap.get("mem_used", 0)
    if mem_total > 0:
        pct = mem_used / mem_total * 100
        pct_str = f"{pct:.0f}%"
        if pct > 90:
            pct_str = red(pct_str)
        elif pct > 75:
            pct_str = yellow(pct_str)
    else:
        pct_str = "N/A"

    print(f"  Memory:    {format_bytes(mem_used)} / {format_bytes(mem_total)}  "
          f"{pct_str}")
    print(f"  Pressure:  {format_pressure(snap.get('mem_pressure', 'unknown'))}")
    speed = snap.get("thermal_speed_limit", -1)
    print(f"  Thermal:   {format_thermal(snap.get('thermal_level', 'unknown'))}  "
          f"{dim(f'({speed}%)')}")
    print()

    # Models
    models = snap.get("models", [])
    engine = snap.get("inference_engine", "none")
    version = snap.get("engine_version", "")

    if engine != "none":
        print(bold("Inference") + f"  {dim(f'{engine} {version}')}")
    else:
        print(bold("Inference") + f"  {dim('no engine detected')}")

    if models:
        total_vram = sum(m.get("size_vram", 0) for m in models)
        print(f"  Models loaded: {len(models)}  "
              f"VRAM total: {bold(format_bytes(total_vram))}")
        print()
        # Table header
        print(f"  {'Model':<40} {'VRAM':>10} {'Format':>8} {'Quant':>6}")
        print(f"  {'─' * 40} {'─' * 10} {'─' * 8} {'─' * 6}")
        for m in models:
            name = m.get("name", "unknown")
            if len(name) > 40:
                name = name[:37] + "..."
            vram = format_bytes(m.get("size_vram", 0))
            fmt = m.get("format", "") or ""
            quant = m.get("quantization", "") or ""
            print(f"  {name:<40} {vram:>10} {fmt:>8} {quant:>6}")
    else:
        print(dim("  No models loaded."))
    print()


def render_history(data: list[dict], hours: int) -> None:
    """Render a history table."""
    if not data:
        print(dim(f"No data for the last {hours}h."))
        return

    print(bold(f"History ({hours}h) — {len(data)} entries"))
    print()
    print(f"  {'Timestamp':<20} {'CPU 1m':>7} {'CPU 5m':>7} "
          f"{'Mem Used':>10} {'Pressure':>10} {'Thermal':>10} {'Models':>7}")
    print(f"  {'─' * 20} {'─' * 7} {'─' * 7} "
          f"{'─' * 10} {'─' * 10} {'─' * 10} {'─' * 7}")

    for entry in data:
        ts_str = _ts_to_str(entry["ts"])
        cpu1 = f"{entry.get('cpu_load_1', -1):.2f}"
        cpu5 = f"{entry.get('cpu_load_5', -1):.2f}"
        mem = format_bytes(entry.get("mem_used", 0))
        pressure = format_pressure(entry.get("mem_pressure", "unknown"))
        thermal = format_thermal(entry.get("thermal_level", "unknown"))
        n_models = len(entry.get("models", []))
        print(f"  {ts_str:<20} {cpu1:>7} {cpu5:>7} "
              f"{mem:>10} {pressure:>10} {thermal:>10} {n_models:>7}")
    print()


def render_compare(data: dict) -> None:
    """Render a before/after comparison."""
    before = data.get("before")
    after = data.get("after")

    if not before or not after:
        print(dim("Insufficient data for comparison."))
        return

    print(bold("Comparison"))
    print(f"  Before: {_ts_to_str(before['ts'])}")
    print(f"  After:  {_ts_to_str(after['ts'])}")
    print()

    # CPU
    cpu_before = before.get("cpu_load_1", 0)
    cpu_after = after.get("cpu_load_1", 0)
    delta_cpu = cpu_after - cpu_before
    delta_str = f"{delta_cpu:+.2f}"
    if delta_cpu > 0:
        delta_str = red(delta_str)
    elif delta_cpu < 0:
        delta_str = green(delta_str)
    print(f"  CPU Load (1m): {cpu_before:.2f} → {cpu_after:.2f}  {delta_str}")

    # Memory
    mem_before = before.get("mem_used", 0)
    mem_after = after.get("mem_used", 0)
    delta_mem = mem_after - mem_before
    delta_mem_str = f"{'+' if delta_mem > 0 else ''}{format_bytes(abs(delta_mem))}"
    if delta_mem > 0:
        delta_mem_str = red(delta_mem_str)
    elif delta_mem < 0:
        delta_mem_str = green(f"-{format_bytes(abs(delta_mem))}")
    print(f"  Memory:        {format_bytes(mem_before)} → {format_bytes(mem_after)}  "
          f"{delta_mem_str}")

    # Pressure & Thermal
    print(f"  Pressure:      {format_pressure(before.get('mem_pressure', '?'))} → "
          f"{format_pressure(after.get('mem_pressure', '?'))}")
    print(f"  Thermal:       {format_thermal(before.get('thermal_level', '?'))} → "
          f"{format_thermal(after.get('thermal_level', '?'))}")
    print()

    # Model changes
    before_names = {m["name"] for m in before.get("models", [])}
    after_names = {m["name"] for m in after.get("models", [])}
    added = after_names - before_names
    removed = before_names - after_names

    if added or removed:
        print(bold("  Model changes:"))
        for name in sorted(added):
            print(f"    {green('+')} {name}")
        for name in sorted(removed):
            print(f"    {red('-')} {name}")
    else:
        print(dim("  No model changes."))
    print()


def render_bench(report: dict) -> None:
    """Render benchmark comparison table with machine context."""
    from asiai.collectors.system import collect_machine_info, collect_memory

    model = report.get("model", "unknown")
    engines = report.get("engines", {})
    winner = report.get("winner")

    if not engines:
        print(dim("No benchmark results to display."))
        return

    print()
    # Machine context header
    machine = collect_machine_info()
    mem = collect_memory()
    ram_str = format_bytes(mem.total) if mem.total > 0 else "N/A"
    mem_pct = f"{mem.used / mem.total * 100:.0f}%" if mem.total > 0 else "N/A"
    print(dim(f"  {machine}  RAM: {ram_str} ({mem_pct} used)  Pressure: {mem.pressure}"))
    print()
    print(bold(f"Benchmark: {model}"))
    print()

    # Table header
    print(f"  {'Engine':<12} {'tok/s':>8} {'TTFT':>8} {'VRAM':>10} "
          f"{'CPU%':>6} {'RSS':>10} {'Thermal':>10}")
    print(f"  {'─' * 12} {'─' * 8} {'─' * 8} {'─' * 10} "
          f"{'─' * 6} {'─' * 10} {'─' * 10}")

    for engine_name, data in sorted(engines.items()):
        tok_s = f"{data['avg_tok_s']:.1f}" if data["avg_tok_s"] > 0 else "N/A"
        ttft = f"{data['avg_ttft_ms'] / 1000:.2f}s" if data["avg_ttft_ms"] > 0 else "N/A"
        vram = format_bytes(data["vram_bytes"]) if data["vram_bytes"] > 0 else "N/A"
        cpu = f"{data.get('avg_proc_cpu', 0):.0f}%" if data.get("avg_proc_cpu", 0) > 0 else "N/A"
        rss_val = data.get("proc_rss_bytes", 0)
        rss = format_bytes(rss_val) if rss_val > 0 else "N/A"
        thermal = format_thermal(data["thermal_level"]) if data["thermal_level"] else "N/A"

        name_str = engine_name
        tok_s_str = tok_s
        if winner and winner["name"] == engine_name:
            name_str = green(engine_name)
            tok_s_str = green(tok_s)

        print(f"  {name_str:<12} {tok_s_str:>8} {ttft:>8} {vram:>10} "
              f"{cpu:>6} {rss:>10} {thermal:>10}")

    print()

    if winner:
        parts = [winner["tok_s_delta"], winner["vram_delta"]]
        parts = [p for p in parts if p]
        detail = f" ({', '.join(parts)})" if parts else ""
        print(f"  {bold('Winner:')} {green(winner['name'])}{detail}")
    elif len(engines) == 1:
        print(dim("  Single engine — no comparison available."))
    print()


def render_bench_history(rows: list[dict]) -> None:
    """Render past benchmark results."""
    if not rows:
        print(dim("No benchmark history found."))
        return

    print(bold(f"Benchmark History — {len(rows)} entries"))
    print()
    print(f"  {'Timestamp':<20} {'Engine':<12} {'Model':<30} "
          f"{'Prompt':>10} {'tok/s':>8} {'TTFT':>8}")
    print(f"  {'─' * 20} {'─' * 12} {'─' * 30} "
          f"{'─' * 10} {'─' * 8} {'─' * 8}")

    for row in rows:
        ts_str = _ts_to_str(row["ts"])
        engine = row.get("engine", "")
        model = row.get("model", "")
        if len(model) > 30:
            model = model[:27] + "..."
        prompt = row.get("prompt_type", "")
        tok_s = f"{row.get('tok_per_sec', 0):.1f}"
        ttft = row.get("ttft_ms", 0)
        ttft_str = f"{ttft / 1000:.2f}s" if ttft > 0 else "N/A"

        print(f"  {ts_str:<20} {engine:<12} {model:<30} "
              f"{prompt:>10} {tok_s:>8} {ttft_str:>8}")
    print()


def render_analyze(data: list[dict], hours: int) -> None:
    """Render a comprehensive analysis of historical data."""
    if not data:
        print(dim(f"No data for the last {hours}h."))
        return

    now = int(time.time())
    span = now - data[0]["ts"]

    print(bold(f"Analysis ({hours}h) — {len(data)} data points"))
    print()

    # Model presence
    print(bold("  Model presence"))
    all_models: dict[str, dict] = {}
    for entry in data:
        for m in entry.get("models", []):
            name = m["name"]
            if name not in all_models:
                all_models[name] = {"count": 0, "max_vram": 0}
            all_models[name]["count"] += 1
            vram = m.get("size_vram", 0)
            if vram > all_models[name]["max_vram"]:
                all_models[name]["max_vram"] = vram

    if all_models:
        total_entries = len(data)
        for name, info in sorted(all_models.items(), key=lambda x: -x[1]["count"]):
            pct = info["count"] / total_entries * 100
            bar = green(f"{pct:.0f}%") if pct > 90 else (
                yellow(f"{pct:.0f}%") if pct > 50 else dim(f"{pct:.0f}%")
            )
            print(f"    {name:<40} {bar:>8}  "
                  f"{format_bytes(info['max_vram']):>10}")
    else:
        print(dim("    No models found."))
    print()

    # Swap events
    print(bold("  Swap events"))
    swaps: list[dict] = []
    prev_names: set[str] | None = None
    for entry in data:
        current_names = {m["name"] for m in entry.get("models", [])}
        if prev_names is not None and current_names != prev_names:
            added = current_names - prev_names
            removed = prev_names - current_names
            swaps.append({
                "ts": entry["ts"],
                "added": added,
                "removed": removed,
                "count": len(current_names),
            })
        prev_names = current_names

    if swaps:
        print(f"    {len(swaps)} swap(s) detected")
        for s in swaps[-5:]:  # Show last 5
            ts_str = _ts_to_str(s["ts"])
            parts = []
            for name in sorted(s["added"]):
                parts.append(green(f"+{name}"))
            for name in sorted(s["removed"]):
                parts.append(red(f"-{name}"))
            print(f"    {ts_str}  {', '.join(parts)}  ({s['count']} models)")
    else:
        print(f"    {green('Stable')} — no swaps detected")
    print()

    # VRAM stats
    vram_values = []
    for entry in data:
        total_vram = sum(m.get("size_vram", 0) for m in entry.get("models", []))
        if total_vram > 0:
            vram_values.append(total_vram)

    if vram_values:
        print(bold("  VRAM"))
        print(f"    Min: {format_bytes(min(vram_values))}  "
              f"Max: {format_bytes(max(vram_values))}  "
              f"Avg: {format_bytes(int(sum(vram_values) / len(vram_values)))}")
        print()

    # System stats
    print(bold("  System stats"))
    cpu1_values = [e.get("cpu_load_1", 0) for e in data if e.get("cpu_load_1", -1) >= 0]
    if cpu1_values:
        print(f"    CPU 1m:  min {min(cpu1_values):.2f}  "
              f"max {max(cpu1_values):.2f}  "
              f"avg {sum(cpu1_values) / len(cpu1_values):.2f}")

    # Pressure distribution
    pressure_counts: dict[str, int] = {}
    for entry in data:
        p = entry.get("mem_pressure", "unknown")
        pressure_counts[p] = pressure_counts.get(p, 0) + 1

    if pressure_counts:
        total = sum(pressure_counts.values())
        parts = []
        for level in ["normal", "warn", "critical"]:
            count = pressure_counts.get(level, 0)
            if count:
                pct = count / total * 100
                parts.append(f"{format_pressure(level)} {pct:.0f}%")
        if parts:
            print(f"    Pressure: {', '.join(parts)}")

    # Thermal distribution
    thermal_counts: dict[str, int] = {}
    for entry in data:
        t = entry.get("thermal_level", "unknown")
        thermal_counts[t] = thermal_counts.get(t, 0) + 1

    if thermal_counts:
        total = sum(thermal_counts.values())
        parts = []
        for level in ["nominal", "fair", "serious", "critical"]:
            count = thermal_counts.get(level, 0)
            if count:
                pct = count / total * 100
                parts.append(f"{format_thermal(level)} {pct:.0f}%")
        if parts:
            print(f"    Thermal:  {', '.join(parts)}")
    print()

    # Current lineup
    if data:
        last = data[-1]
        models = last.get("models", [])
        if models:
            print(bold("  Current lineup"))
            # Time since last swap
            if swaps:
                since = now - swaps[-1]["ts"]
                stable_str = _time_ago(since)
            else:
                stable_str = _time_ago(span)
            print(f"    Stable since: {green(stable_str)}")

            sorted_models = sorted(
                models, key=lambda m: m.get("size_vram", 0), reverse=True
            )
            for m in sorted_models:
                vram = format_bytes(m.get("size_vram", 0))
                print(f"    {m['name']:<40} {vram:>10}")
            print()
