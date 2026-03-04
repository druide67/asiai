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


def render_doctor(checks: list) -> None:
    """Render doctor diagnostic results as a checklist."""
    # Group by category
    categories: dict[str, list] = {}
    for check in checks:
        cat = check.category
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(check)

    status_icons = {"ok": green("✓"), "warn": yellow("⚠"), "fail": red("✗")}
    category_order = ["system", "engine", "database"]

    print(bold("Doctor"))
    print()

    for cat in category_order:
        cat_checks = categories.get(cat, [])
        if not cat_checks:
            continue
        print(f"  {bold(cat.capitalize())}")
        for check in cat_checks:
            icon = status_icons.get(check.status, "?")
            print(f"    {icon} {check.name:<20} {check.message}")
            if check.fix and check.status != "ok":
                print(f"      {dim(f'Fix: {check.fix}')}")
        print()

    # Summary
    ok_count = sum(1 for c in checks if c.status == "ok")
    warn_count = sum(1 for c in checks if c.status == "warn")
    fail_count = sum(1 for c in checks if c.status == "fail")
    parts = []
    if ok_count:
        parts.append(green(f"{ok_count} ok"))
    if warn_count:
        parts.append(yellow(f"{warn_count} warning(s)"))
    if fail_count:
        parts.append(red(f"{fail_count} failed"))
    print(f"  {', '.join(parts)}")
    print()


def render_detect(engines: list[dict]) -> None:
    """Render engine detection results."""
    if not engines:
        print(dim("No inference engines detected."))
        print(dim("Checked: localhost:11434 (Ollama), :1234 (LM Studio), :8080 (mlx-lm)"))
        return

    print(bold("Detected engines:"))
    print()
    for e in engines:
        print(f"  {green('●')} {bold(e['name'])} {dim(e['version'])}")
        print(f"    URL: {e['url']}")
        if e.get("models"):
            print(f"    Running: {len(e['models'])} model(s)")
            for m in e["models"]:
                vram = format_bytes(m["size_vram"]) if m["size_vram"] else "—"
                print(f"      - {m['name']}  {dim(vram)}")
        print()


def render_snapshot(snap: dict) -> None:
    """Render a system + inference snapshot."""
    print(bold("System"))
    print(f"  Uptime:    {format_uptime(snap.get('uptime', -1))}")
    print(
        f"  CPU Load:  {snap.get('cpu_load_1', -1):.2f} / "
        f"{snap.get('cpu_load_5', -1):.2f} / "
        f"{snap.get('cpu_load_15', -1):.2f}  "
        f"{dim('(1m / 5m / 15m)')}"
    )

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

    print(f"  Memory:    {format_bytes(mem_used)} / {format_bytes(mem_total)}  {pct_str}")
    print(f"  Pressure:  {format_pressure(snap.get('mem_pressure', 'unknown'))}")
    speed = snap.get("thermal_speed_limit", -1)
    print(
        f"  Thermal:   {format_thermal(snap.get('thermal_level', 'unknown'))}  {dim(f'({speed}%)')}"
    )
    print()

    # Engines
    engine_str = snap.get("inference_engine", "none")
    version_str = snap.get("engine_version", "")

    print(bold("Inference"))
    if engine_str == "none":
        print(dim("  No engine detected."))
    else:
        # Parse comma-separated engine names and versions
        versions = {}
        for v in version_str.split(","):
            v = v.strip()
            if "/" in v:
                ename, ever = v.split("/", 1)
                versions[ename] = ever
        for ename in engine_str.split(","):
            ename = ename.strip()
            ver = versions.get(ename, "")
            ver_display = dim(f"v{ver}") if ver else ""
            print(f"  {green('●')} {ename} {ver_display}")

    # Models
    models = snap.get("models", [])
    if models:
        total_vram = sum(m.get("size_vram", 0) for m in models)
        print()
        print(f"  Models loaded: {len(models)}  VRAM total: {bold(format_bytes(total_vram))}")
        print()
        # Table header
        print(f"  {'Model':<40} {'Engine':<12} {'VRAM':>10} {'Format':>8} {'Quant':>6}")
        print(f"  {'─' * 40} {'─' * 12} {'─' * 10} {'─' * 8} {'─' * 6}")
        for m in models:
            name = m.get("name", "unknown")
            if len(name) > 40:
                name = name[:37] + "..."
            eng = m.get("engine", "")
            vram = format_bytes(m.get("size_vram", 0))
            fmt = m.get("format", "") or ""
            quant = m.get("quantization", "") or ""
            eng_pad = dim(f"{eng:<12}")
            print(f"  {name:<40} {eng_pad} {vram:>10} {fmt:>8} {quant:>6}")
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
    print(
        f"  {'Timestamp':<20} {'CPU 1m':>7} {'CPU 5m':>7} "
        f"{'Mem Used':>10} {'Pressure':>10} {'Thermal':>10} {'Models':>7}"
    )
    print(f"  {'─' * 20} {'─' * 7} {'─' * 7} {'─' * 10} {'─' * 10} {'─' * 10} {'─' * 7}")

    for entry in data:
        ts_str = _ts_to_str(entry["ts"])
        cpu1 = f"{entry.get('cpu_load_1', -1):.2f}"
        cpu5 = f"{entry.get('cpu_load_5', -1):.2f}"
        mem = format_bytes(entry.get("mem_used", 0))
        pressure = format_pressure(entry.get("mem_pressure", "unknown"))
        thermal = format_thermal(entry.get("thermal_level", "unknown"))
        n_models = len(entry.get("models", []))
        print(
            f"  {ts_str:<20} {cpu1:>7} {cpu5:>7} "
            f"{mem:>10} {pressure:>10} {thermal:>10} {n_models:>7}"
        )
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
    print(
        f"  Memory:        {format_bytes(mem_before)} → {format_bytes(mem_after)}  {delta_mem_str}"
    )

    # Pressure & Thermal
    print(
        f"  Pressure:      {format_pressure(before.get('mem_pressure', '?'))} → "
        f"{format_pressure(after.get('mem_pressure', '?'))}"
    )
    print(
        f"  Thermal:       {format_thermal(before.get('thermal_level', '?'))} → "
        f"{format_thermal(after.get('thermal_level', '?'))}"
    )
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
    print(
        f"  {'Engine':<12} {'tok/s':>24} {'Tokens':>8} {'Duration':>8} "
        f"{'TTFT':>8} {'VRAM':>10} {'Thermal':>10}"
    )
    print(f"  {'─' * 12} {'─' * 24} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 10} {'─' * 10}")

    for engine_name, data in sorted(engines.items()):
        avg_tok = data["avg_tok_s"]
        median_tok = data.get("median_tok_s", 0.0)
        stddev = data.get("std_dev_tok_s", 0.0)
        runs_count = data.get("runs_count", 1)
        stability = data.get("stability", "")

        if avg_tok > 0:
            if runs_count > 1 and stddev > 0:
                # Show median as primary (SPEC standard), ± stddev
                primary = median_tok if median_tok > 0 else avg_tok
                tok_s = f"{primary:.1f} \u00b1 {stddev:.1f}"
                if stability:
                    tok_s += f" ({stability})"
            else:
                tok_s = f"{avg_tok:.1f}"
        else:
            tok_s = "N/A"

        tokens = (
            str(data.get("avg_tokens_generated", 0))
            if data.get("avg_tokens_generated", 0) > 0
            else "N/A"
        )
        dur_ms = data.get("avg_total_duration_ms", 0.0)
        duration = f"{dur_ms / 1000:.2f}s" if dur_ms > 0 else "N/A"
        ttft = f"{data['avg_ttft_ms'] / 1000:.2f}s" if data["avg_ttft_ms"] > 0 else "N/A"

        # VRAM only (no RSS fallback — misleading on unified memory)
        vram_bytes = data.get("vram_bytes", 0)
        vram = format_bytes(vram_bytes) if vram_bytes > 0 else "—"

        # Pad before coloring to preserve alignment (ANSI codes are invisible)
        name_pad = f"{engine_name:<12}"
        tok_s_pad = f"{tok_s:>24}"
        tokens_pad = f"{tokens:>8}"
        dur_pad = f"{duration:>8}"
        ttft_pad = f"{ttft:>8}"
        vram_pad = f"{vram:>10}"

        thermal_raw = data["thermal_level"] if data["thermal_level"] else "N/A"
        thermal_pad = f"{thermal_raw:>10}"
        if thermal_raw == "nominal":
            thermal_pad = green(thermal_pad)
        elif thermal_raw == "fair":
            thermal_pad = yellow(thermal_pad)
        elif thermal_raw in ("serious", "critical"):
            thermal_pad = red(thermal_pad)

        if winner and winner["name"] == engine_name:
            name_pad = green(name_pad)
            tok_s_pad = green(tok_s_pad)

        print(
            f"  {name_pad} {tok_s_pad} {tokens_pad} {dur_pad} {ttft_pad} {vram_pad} {thermal_pad}"
        )

    print()

    if winner:
        parts = [winner["tok_s_delta"], winner["vram_delta"]]
        parts = [p for p in parts if p]
        detail = f" ({', '.join(parts)})" if parts else ""
        print(f"  {bold('Winner:')} {green(winner['name'])}{detail}")
    elif len(engines) == 1:
        print(dim("  Single engine — no comparison available."))

    # Load time (if available)
    has_load_time = any(
        any(p.get("load_time_ms", 0) > 0 for p in d["prompt_results"]) for d in engines.values()
    )
    if has_load_time:
        print()
        print(bold("  Model Load Time"))
        for engine_name, data in sorted(engines.items()):
            pr = data["prompt_results"]
            load_vals = [p["load_time_ms"] for p in pr if p.get("load_time_ms", 0) > 0]
            if load_vals:
                load_ms = load_vals[0]  # Same for all prompts in one engine
                if load_ms >= 1000:
                    print(f"    {engine_name:<12} {load_ms / 1000:.1f}s")
                else:
                    print(f"    {engine_name:<12} {load_ms:.0f}ms")

    # Statistical details (CI, percentiles, outliers)
    has_stats = any(d.get("runs_count", 1) >= 2 for d in engines.values())
    if has_stats:
        print()
        print(bold("  Statistics"))
        for engine_name, data in sorted(engines.items()):
            if data.get("runs_count", 1) < 2:
                continue
            ci_lo = data.get("ci95_lower", 0)
            ci_hi = data.get("ci95_upper", 0)
            p90 = data.get("p90_tok_s", 0)
            p90_ttft = data.get("p90_ttft_ms", 0)
            parts = [f"95% CI: [{ci_lo:.1f}, {ci_hi:.1f}] tok/s"]
            if p90 > 0:
                parts.append(f"P90: {p90:.1f} tok/s")
            if p90_ttft > 0:
                parts.append(f"P90 TTFT: {p90_ttft / 1000:.2f}s")
            outliers = data.get("outliers", [])
            if outliers:
                parts.append(yellow(f"{len(outliers)} outlier(s)"))
            print(f"    {engine_name:<12} {', '.join(parts)}")

    # Power tip (when no power data)
    has_power = any(
        any(p.get("power_watts", 0) > 0 for p in d["prompt_results"]) for d in engines.values()
    )
    if not has_power:
        print(dim("  Tip: run with --power for tok/s per watt (requires sudo)"))

    # Power efficiency table (if power data available)
    if has_power:
        print()
        print(bold("  Power Efficiency"))
        for engine_name, data in sorted(engines.items()):
            pr = data["prompt_results"]
            power_vals = [p["power_watts"] for p in pr if p.get("power_watts", 0) > 0]
            eff_vals = [
                p["tok_per_sec_per_watt"] for p in pr if p.get("tok_per_sec_per_watt", 0) > 0
            ]
            if power_vals:
                avg_w = sum(power_vals) / len(power_vals)
                avg_eff = sum(eff_vals) / len(eff_vals) if eff_vals else 0.0
                tok_s = data["avg_tok_s"]
                print(
                    f"    {engine_name:<12} {tok_s:.1f} tok/s @ {avg_w:.1f}W"
                    f" = {avg_eff:.2f} tok/s/W (tok/J)"
                )
    print()


def render_regressions(regressions: list) -> None:
    """Render regression warnings after a benchmark run."""
    if not regressions:
        return

    print(bold("  Regression Warnings"))
    severity_icons = {"major": red("!!!"), "significant": yellow("!!"), "minor": yellow("!")}
    for r in regressions:
        icon = severity_icons.get(r.severity, "?")
        if r.metric == "tok_per_sec":
            print(
                f"    {icon} {r.engine}: tok/s dropped {abs(r.pct_change):.0f}%"
                f" ({r.baseline:.1f} -> {r.current:.1f}) -- {r.severity}"
            )
        elif r.metric == "ttft_ms":
            print(
                f"    {icon} {r.engine}: TTFT increased {r.pct_change:.0f}%"
                f" ({r.baseline:.0f}ms -> {r.current:.0f}ms) -- {r.severity}"
            )
    print()


def render_bench_history(rows: list[dict]) -> None:
    """Render past benchmark results."""
    if not rows:
        print(dim("No benchmark history found."))
        return

    print(bold(f"Benchmark History — {len(rows)} entries"))
    print()
    print(
        f"  {'Timestamp':<20} {'Engine':<12} {'Model':<30} {'Prompt':>10} {'tok/s':>8} {'TTFT':>8}"
    )
    print(f"  {'─' * 20} {'─' * 12} {'─' * 30} {'─' * 10} {'─' * 8} {'─' * 8}")

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

        print(f"  {ts_str:<20} {engine:<12} {model:<30} {prompt:>10} {tok_s:>8} {ttft_str:>8}")
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
            bar = (
                green(f"{pct:.0f}%")
                if pct > 90
                else (yellow(f"{pct:.0f}%") if pct > 50 else dim(f"{pct:.0f}%"))
            )
            print(f"    {name:<40} {bar:>8}  {format_bytes(info['max_vram']):>10}")
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
            swaps.append(
                {
                    "ts": entry["ts"],
                    "added": added,
                    "removed": removed,
                    "count": len(current_names),
                }
            )
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
        print(
            f"    Min: {format_bytes(min(vram_values))}  "
            f"Max: {format_bytes(max(vram_values))}  "
            f"Avg: {format_bytes(int(sum(vram_values) / len(vram_values)))}"
        )
        print()

    # System stats
    print(bold("  System stats"))
    cpu1_values = [e.get("cpu_load_1", 0) for e in data if e.get("cpu_load_1", -1) >= 0]
    if cpu1_values:
        print(
            f"    CPU 1m:  min {min(cpu1_values):.2f}  "
            f"max {max(cpu1_values):.2f}  "
            f"avg {sum(cpu1_values) / len(cpu1_values):.2f}"
        )

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

            sorted_models = sorted(models, key=lambda m: m.get("size_vram", 0), reverse=True)
            for m in sorted_models:
                vram = format_bytes(m.get("size_vram", 0))
                print(f"    {m['name']:<40} {vram:>10}")
            print()
