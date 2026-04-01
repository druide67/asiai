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
    category_order = ["system", "engine", "database", "daemon", "alerting"]

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
        print(dim("Try: brew install ollama && ollama serve"))
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

    # GPU (conditional — only if ioreg data available)
    gpu_util = snap.get("gpu_utilization_pct", -1)
    if gpu_util >= 0:
        print(bold("GPU"))
        renderer = snap.get("gpu_renderer_pct", -1)
        tiler = snap.get("gpu_tiler_pct", -1)

        # Color utilization: >90% red, >60% yellow, else green
        if gpu_util > 90:
            util_str = red(f"{gpu_util:.0f}%")
        elif gpu_util > 60:
            util_str = yellow(f"{gpu_util:.0f}%")
        else:
            util_str = green(f"{gpu_util:.0f}%")

        detail_parts = []
        if renderer >= 0:
            detail_parts.append(f"renderer {renderer:.0f}%")
        if tiler >= 0:
            detail_parts.append(f"tiler {tiler:.0f}%")
        detail_str = ", ".join(detail_parts)
        detail = f"  {dim('(' + detail_str + ')')}" if detail_parts else ""

        print(f"  Utilization: {util_str}{detail}")

        mem_in_use = snap.get("gpu_mem_in_use", 0)
        mem_allocated = snap.get("gpu_mem_allocated", 0)
        if mem_in_use > 0 or mem_allocated > 0:
            print(
                f"  Memory:      {format_bytes(mem_in_use)} in use"
                f" / {format_bytes(mem_allocated)} allocated"
            )
        print()

    # Power (conditional — only if IOReport data available)
    power_gpu = snap.get("power_gpu_watts", -1)
    if power_gpu >= 0:
        print(bold("Power"))
        power_cpu = snap.get("power_cpu_watts", 0)
        power_ane = snap.get("power_ane_watts", 0)
        power_dram = snap.get("power_dram_watts", 0)
        power_total = snap.get("power_total_watts", 0)

        # Color GPU power: >30W red, >15W yellow, else green
        if power_gpu > 30:
            gpu_str = red(f"{power_gpu:.1f}W")
        elif power_gpu > 15:
            gpu_str = yellow(f"{power_gpu:.1f}W")
        else:
            gpu_str = green(f"{power_gpu:.1f}W")

        print(
            f"  GPU: {gpu_str}  CPU: {power_cpu:.1f}W"
            f"  ANE: {power_ane:.1f}W  DRAM: {power_dram:.1f}W"
        )
        print(f"  Total: {power_total:.1f}W  {dim('(IOReport, no sudo)')}")
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
        # Inference activity keyed by engine name
        activity: dict[str, dict] = {}
        for es in snap.get("engines_status", []):
            activity[es.get("name", "")] = es

        for ename in engine_str.split(","):
            ename = ename.strip()
            ver = versions.get(ename, "")
            ver_display = dim(f"v{ver}") if ver else ""
            print(f"  {green('●')} {ename} {ver_display}")

            # Show inference activity metrics if available
            act = activity.get(ename, {})
            parts: list[str] = []
            tcp = act.get("tcp_connections", 0)
            req = act.get("requests_processing", 0)
            kv = act.get("kv_cache_usage_ratio", -1)
            tok_total = act.get("tokens_predicted_total", 0)
            if tcp > 0:
                parts.append(f"{tcp} conn")
            if req > 0:
                parts.append(yellow(f"{req} processing"))
            if kv >= 0:
                kv_pct = round(kv * 100)
                kv_str = f"{kv_pct}% KV"
                if kv_pct > 95:
                    kv_str = red(kv_str)
                elif kv_pct > 80:
                    kv_str = yellow(kv_str)
                parts.append(kv_str)
            # TurboQuant KV compression info
            kv_comp = act.get("kv_cache_compressed_bytes", 0)
            kv_orig = act.get("kv_cache_original_bytes", 0)
            if kv_comp > 0 and kv_orig > 0:
                ratio = kv_orig / kv_comp
                comp_mb = kv_comp / (1024 * 1024)
                parts.append(
                    green(f"TQ {comp_mb:.0f}MB ({ratio:.1f}x)")
                )
            if tok_total > 0:
                if tok_total >= 1_000_000:
                    parts.append(f"{tok_total / 1_000_000:.1f}M tokens")
                elif tok_total >= 1_000:
                    parts.append(f"{tok_total / 1_000:.1f}K tokens")
                else:
                    parts.append(f"{tok_total} tokens")
            if parts:
                print(f"    {dim(' · '.join(parts))}")

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


def render_bench(report: dict, context_size: int = 0) -> None:
    """Render benchmark comparison table with machine context."""
    from asiai.benchmark.reporter import report_to_slots
    from asiai.collectors.system import collect_machine_info, collect_memory

    session_type = report.get("session_type", "engine")
    slots = report_to_slots(report)
    winner = report.get("winner")

    if not slots:
        print(dim("No benchmark results to display."))
        return

    # Build display items: (display_name, data_dict) pairs
    items: list[tuple[str, dict]] = []
    for s in slots:
        if session_type == "model":
            display_name = s.get("model", "")
        elif session_type == "matrix":
            display_name = f"{s.get('model', '')} / {s.get('engine', '')}"
        else:
            display_name = s.get("engine", "")
        items.append((display_name, s))

    # Column label and width
    if session_type == "model":
        col_label = "Model"
    elif session_type == "matrix":
        col_label = "Model/Engine"
    else:
        col_label = "Engine"
    col_w = max(max(len(name) for name, _ in items), len(col_label), 12)

    # Title
    if session_type == "model" and slots:
        title = slots[0].get("engine", "unknown")
    elif session_type == "matrix":
        title = "Cross-model comparison"
    else:
        title = report.get("model", "unknown")

    print()
    # Machine context header
    machine = collect_machine_info()
    mem = collect_memory()
    ram_str = format_bytes(mem.total) if mem.total > 0 else "N/A"
    mem_pct = f"{mem.used / mem.total * 100:.0f}%" if mem.total > 0 else "N/A"
    print(dim(f"  {machine}  RAM: {ram_str} ({mem_pct} used)  Pressure: {mem.pressure}"))
    print()
    ctx_str = ""
    if context_size > 0:
        if context_size >= 1024:
            ctx_str = f" [{context_size // 1024}K context fill]"
        else:
            ctx_str = f" [{context_size} context fill]"
    print(bold(f"Benchmark: {title}{ctx_str}"))
    print()

    # Table header
    print(
        f"  {col_label:<{col_w}} {'tok/s':>24} {'Tokens':>8} {'Duration':>8} "
        f"{'TTFT':>8} {'VRAM':>10} {'Thermal':>10}"
    )
    print(f"  {'─' * col_w} {'─' * 24} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 10} {'─' * 10}")

    for display_name, data in items:
        avg_tok = data.get("avg_tok_s", 0.0)
        median_tok = data.get("median_tok_s", 0.0)
        stddev = data.get("std_dev_tok_s", 0.0)
        runs_count = data.get("runs_count", 1)
        stability = data.get("stability", "")

        if avg_tok > 0:
            if runs_count > 1 and stddev > 0:
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
        ttft = (
            f"{data.get('avg_ttft_ms', 0) / 1000:.2f}s" if data.get("avg_ttft_ms", 0) > 0 else "N/A"
        )

        vram_bytes = data.get("vram_bytes", 0)
        vram = format_bytes(vram_bytes) if vram_bytes > 0 else "—"

        name_pad = f"{display_name:<{col_w}}"
        tok_s_pad = f"{tok_s:>24}"
        tokens_pad = f"{tokens:>8}"
        dur_pad = f"{duration:>8}"
        ttft_pad = f"{ttft:>8}"
        vram_pad = f"{vram:>10}"

        thermal_raw = data.get("thermal_level", "") or "N/A"
        thermal_pad = f"{thermal_raw:>10}"
        if thermal_raw == "nominal":
            thermal_pad = green(thermal_pad)
        elif thermal_raw == "fair":
            thermal_pad = yellow(thermal_pad)
        elif thermal_raw in ("serious", "critical"):
            thermal_pad = red(thermal_pad)

        if winner and winner.get("name") == display_name:
            name_pad = green(name_pad)
            tok_s_pad = green(tok_s_pad)

        print(
            f"  {name_pad} {tok_s_pad} {tokens_pad} {dur_pad} {ttft_pad} {vram_pad} {thermal_pad}"
        )

    print()

    if winner:
        parts = [winner.get("tok_s_delta", ""), winner.get("vram_delta", "")]
        parts = [p for p in parts if p]
        detail = f" ({', '.join(parts)})" if parts else ""
        print(f"  {bold('Winner:')} {green(winner['name'])}{detail}")
    elif len(slots) == 1:
        if session_type == "engine":
            print(dim("  Single engine — no comparison available."))
        else:
            print(dim("  Single result — no comparison available."))

    # Load time (if available)
    has_load_time = any(
        any(p.get("load_time_ms", 0) > 0 for p in d.get("prompt_results", [])) for _, d in items
    )
    if has_load_time:
        print()
        print(bold("  Model Load Time"))
        for display_name, data in items:
            pr = data.get("prompt_results", [])
            load_vals = [p["load_time_ms"] for p in pr if p.get("load_time_ms", 0) > 0]
            if load_vals:
                load_ms = load_vals[0]
                if load_ms >= 1000:
                    print(f"    {display_name:<{col_w}} {load_ms / 1000:.1f}s")
                else:
                    print(f"    {display_name:<{col_w}} {load_ms:.0f}ms")

    # Statistical details (CI, percentiles, outliers)
    has_stats = any(d.get("runs_count", 1) >= 2 for _, d in items)
    if has_stats:
        print()
        print(bold("  Statistics"))
        for display_name, data in items:
            if data.get("runs_count", 1) < 2:
                continue
            ci_lo = data.get("ci95_lower", 0)
            ci_hi = data.get("ci95_upper", 0)
            p90 = data.get("p90_tok_s", 0)
            p90_ttft = data.get("p90_ttft_ms", 0)
            stat_parts = [f"95% CI: [{ci_lo:.1f}, {ci_hi:.1f}] tok/s"]
            if p90 > 0:
                stat_parts.append(f"P90: {p90:.1f} tok/s")
            if p90_ttft > 0:
                stat_parts.append(f"P90 TTFT: {p90_ttft / 1000:.2f}s")
            outliers = data.get("outliers", [])
            if outliers:
                stat_parts.append(yellow(f"{len(outliers)} outlier(s)"))
            print(f"    {display_name:<{col_w}} {', '.join(stat_parts)}")

    # Power efficiency table (if power data available)
    has_power = any(
        any(p.get("power_watts", 0) > 0 for p in d.get("prompt_results", [])) for _, d in items
    )
    if has_power:
        print()
        print(bold("  Power Efficiency"))
        for display_name, data in items:
            pr = data.get("prompt_results", [])
            power_vals = [p["power_watts"] for p in pr if p.get("power_watts", 0) > 0]
            eff_vals = [
                p["tok_per_sec_per_watt"] for p in pr if p.get("tok_per_sec_per_watt", 0) > 0
            ]
            if power_vals:
                avg_w = sum(power_vals) / len(power_vals)
                avg_eff = sum(eff_vals) / len(eff_vals) if eff_vals else 0.0
                tok_s_val = data.get("avg_tok_s", 0.0)
                print(
                    f"    {display_name:<{col_w}} {tok_s_val:.1f} tok/s @ {avg_w:.1f}W"
                    f" = {avg_eff:.2f} tok/s/W (tok/J)"
                )

    # Process metrics (if available)
    has_proc = any(d.get("avg_proc_cpu", 0) > 0 or d.get("proc_rss_bytes", 0) > 0 for _, d in items)
    if has_proc:
        print()
        print(bold("  Process"))
        for display_name, data in items:
            cpu = data.get("avg_proc_cpu", 0)
            rss = data.get("proc_rss_bytes", 0)
            if cpu > 0 or rss > 0:
                parts_proc = []
                if cpu > 0:
                    parts_proc.append(f"{cpu:.0f}% CPU")
                if rss > 0:
                    parts_proc.append(f"{format_bytes(rss)} RSS (peak)")
                print(f"    {display_name:<{col_w}} {' · '.join(parts_proc)}")
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
