"""Benchmark result aggregation and winner determination."""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict


def aggregate_results(results: list[dict]) -> dict:
    """Aggregate per-prompt results into per-engine summaries.

    Returns:
        {
            "model": str,
            "engines": {
                "engine_name": {
                    "avg_tok_s": float,
                    "std_dev_tok_s": float,
                    "runs_count": int,
                    "stability": str,          # "stable", "variable", "unstable"
                    "avg_ttft_ms": float,
                    "vram_bytes": int,
                    "thermal_level": str,
                    "prompt_results": [...]
                },
                ...
            },
            "winner": {"name": str, "tok_s_delta": str, "vram_delta": str} | None
        }
    """
    if not results:
        return {"model": "", "engines": {}, "winner": None}

    model = results[0]["model"]
    engines: dict[str, dict] = {}

    for r in results:
        name = r["engine"]
        if name not in engines:
            engines[name] = {
                "prompt_results": [],
                "vram_bytes": r.get("vram_bytes", 0),
                "thermal_level": r.get("thermal_level", ""),
            }
        engines[name]["prompt_results"].append(r)

    # Compute aggregated stats per engine
    for data in engines.values():
        _compute_stats(data["prompt_results"], data)

    # Determine winner by median tok/s (falls back to avg if single run)
    winner = _determine_winner(engines)

    return {"model": model, "engines": engines, "winner": winner}


def _stddev(values: list[float]) -> float:
    """Compute sample standard deviation (Bessel's correction, N-1)."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return round(math.sqrt(variance), 2)


def _pooled_stddev(results: list[dict]) -> float:
    """Compute pooled intra-prompt standard deviation.

    Groups results by prompt_type, computes variance within each group,
    then returns sqrt(mean(variances)). This captures run-to-run noise
    without mixing in inter-prompt variance.
    """
    by_prompt: dict[str, list[float]] = {}
    for r in results:
        pt = r.get("prompt_type", "unknown")
        tok_s = r.get("tok_per_sec", 0.0)
        if tok_s > 0:
            by_prompt.setdefault(pt, []).append(tok_s)

    variances: list[float] = []
    for values in by_prompt.values():
        if len(values) < 2:
            continue
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        variances.append(var)

    if not variances:
        return 0.0

    pooled_var = sum(variances) / len(variances)
    return round(math.sqrt(pooled_var), 2)


def _percentile(values: list[float], p: int) -> float:
    """Compute the p-th percentile using linear interpolation."""
    if not values:
        return 0.0
    sorted_v = sorted(values)
    n = len(sorted_v)
    if n == 1:
        return sorted_v[0]
    k = (p / 100) * (n - 1)
    lo = int(k)
    hi = min(lo + 1, n - 1)
    frac = k - lo
    return sorted_v[lo] + frac * (sorted_v[hi] - sorted_v[lo])


def _detect_outliers(values: list[float]) -> list[dict]:
    """Detect outliers using the IQR method.

    Returns list of {"index": int, "value": float} for values outside
    [Q1 - 1.5*IQR, Q3 + 1.5*IQR].
    """
    if len(values) < 4:
        return []
    q1 = _percentile(values, 25)
    q3 = _percentile(values, 75)
    iqr = q3 - q1
    if iqr <= 0:
        return []
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return [
        {"index": i, "value": round(v, 1)} for i, v in enumerate(values) if v < lower or v > upper
    ]


def _count_runs(results: list[dict]) -> int:
    """Count distinct run indices."""
    indices = {r.get("run_index", 0) for r in results}
    return len(indices)


def _classify_stability(avg: float, stddev: float) -> str:
    """Classify tok/s stability based on coefficient of variation."""
    if avg <= 0 or stddev <= 0:
        return "stable"
    cv = (stddev / avg) * 100
    if cv < 5:
        return "stable"
    if cv < 10:
        return "variable"
    return "unstable"


def _compute_stats(prompt_results: list[dict], data: dict) -> dict:
    """Compute aggregated statistics from raw per-run results into data dict.

    Shared between aggregate_results() (groups by engine) and
    aggregate_slots() (groups by engine+model).
    """
    pr = prompt_results
    tok_values = [p["tok_per_sec"] for p in pr if p["tok_per_sec"] > 0]
    ttft_values = [p["ttft_ms"] for p in pr if p["ttft_ms"] > 0]
    ttft_client_values = [p["ttft_client_ms"] for p in pr if p.get("ttft_client_ms", 0) > 0]
    cpu_values = [p["proc_cpu_pct"] for p in pr if p.get("proc_cpu_pct", 0) > 0]
    rss_values = [p["proc_rss_bytes"] for p in pr if p.get("proc_rss_bytes", 0) > 0]

    data["avg_tok_s"] = round(sum(tok_values) / len(tok_values), 1) if tok_values else 0.0
    data["median_tok_s"] = round(statistics.median(tok_values), 1) if tok_values else 0.0
    data["avg_ttft_ms"] = round(sum(ttft_values) / len(ttft_values), 1) if ttft_values else 0.0
    data["median_ttft_ms"] = round(statistics.median(ttft_values), 1) if ttft_values else 0.0
    data["avg_ttft_client_ms"] = round(sum(ttft_client_values) / len(ttft_client_values), 1) if ttft_client_values else 0.0
    data["median_ttft_client_ms"] = round(statistics.median(ttft_client_values), 1) if ttft_client_values else 0.0
    data["avg_proc_cpu"] = round(sum(cpu_values) / len(cpu_values), 1) if cpu_values else 0.0
    data["proc_rss_bytes"] = max(rss_values) if rss_values else 0

    tok_gen_values = [p["tokens_generated"] for p in pr if p.get("tokens_generated", 0) > 0]
    duration_values = [p["total_duration_ms"] for p in pr if p.get("total_duration_ms", 0) > 0]
    data["avg_tokens_generated"] = (
        round(sum(tok_gen_values) / len(tok_gen_values)) if tok_gen_values else 0
    )
    data["avg_total_duration_ms"] = (
        round(sum(duration_values) / len(duration_values), 1) if duration_values else 0.0
    )

    data["std_dev_tok_s"] = _pooled_stddev(pr)
    data["runs_count"] = _count_runs(pr)
    data["stability"] = _classify_stability(data["avg_tok_s"], data["std_dev_tok_s"])

    if tok_values and len(tok_values) >= 2:
        n = len(tok_values)
        se = data["std_dev_tok_s"] / math.sqrt(n) if n > 0 else 0.0
        data["ci95_lower"] = round(data["avg_tok_s"] - 2 * se, 1)
        data["ci95_upper"] = round(data["avg_tok_s"] + 2 * se, 1)
    else:
        data["ci95_lower"] = data["avg_tok_s"]
        data["ci95_upper"] = data["avg_tok_s"]

    data["p50_tok_s"] = data["median_tok_s"]
    data["p90_tok_s"] = round(_percentile(tok_values, 90), 1) if tok_values else 0.0
    data["p99_tok_s"] = round(_percentile(tok_values, 99), 1) if tok_values else 0.0
    data["p50_ttft_ms"] = data["median_ttft_ms"]
    data["p90_ttft_ms"] = round(_percentile(ttft_values, 90), 1) if ttft_values else 0.0
    data["p99_ttft_ms"] = round(_percentile(ttft_values, 99), 1) if ttft_values else 0.0
    data["p90_ttft_client_ms"] = round(_percentile(ttft_client_values, 90), 1) if ttft_client_values else 0.0
    data["outliers"] = _detect_outliers(tok_values) if tok_values else []

    return data


def _determine_winner(engines: dict[str, dict]) -> dict | None:
    """Pick winner by median tok/s (more robust than mean) and compute deltas."""
    if len(engines) < 2:
        return None

    def _primary_tok_s(data: dict) -> float:
        """Use median when available (multi-run), fallback to avg."""
        return data.get("median_tok_s", 0.0) or data.get("avg_tok_s", 0.0)

    ranked = sorted(engines.items(), key=lambda x: _primary_tok_s(x[1]), reverse=True)
    best_name, best = ranked[0]
    second_name, second = ranked[1]

    best_tok = _primary_tok_s(best)
    second_tok = _primary_tok_s(second)
    if best_tok <= 0 or second_tok <= 0:
        return None

    tok_ratio = best_tok / second_tok
    if tok_ratio >= 1.5:
        tok_s_delta = f"{tok_ratio:.1f}x faster"
    else:
        tok_pct = (tok_ratio - 1) * 100
        tok_s_delta = f"+{tok_pct:.0f}% tok/s"

    vram_delta = ""
    if best["vram_bytes"] > 0 and second["vram_bytes"] > 0:
        vram_pct = ((best["vram_bytes"] - second["vram_bytes"]) / second["vram_bytes"]) * 100
        sign = "+" if vram_pct >= 0 else ""
        vram_delta = f"{sign}{vram_pct:.0f}% VRAM"

    return {"name": best_name, "tok_s_delta": tok_s_delta, "vram_delta": vram_delta}


def export_benchmark(
    raw_results: list[dict],
    report: dict,
    output_path: str,
) -> str:
    """Export benchmark results to a standardized JSON file.

    Args:
        raw_results: Raw per-run result dicts from BenchmarkRun.results.
        report: Aggregated report from aggregate_results().
        output_path: File path to write the JSON.

    Returns:
        The path written to.
    """
    from asiai import __version__

    # Extract machine info from first result
    first = raw_results[0] if raw_results else {}
    hw_chip = first.get("hw_chip", "")
    os_version = first.get("os_version", "")

    # Distinct prompt types
    prompts = sorted({r.get("prompt_type", "") for r in raw_results if r.get("prompt_type")})

    # Runs per prompt
    run_indices = {r.get("run_index", 0) for r in raw_results}
    runs_per_prompt = len(run_indices)

    # Build per-engine export
    engines_export: dict[str, dict] = {}
    for engine_name, data in report.get("engines", {}).items():
        engine_data: dict = {
            "median_tok_s": data.get("median_tok_s", 0.0),
            "avg_tok_s": data.get("avg_tok_s", 0.0),
            "std_dev_tok_s": data.get("std_dev_tok_s", 0.0),
            "stability": data.get("stability", ""),
            "runs_count": data.get("runs_count", 1),
            "ci95": [data.get("ci95_lower", 0.0), data.get("ci95_upper", 0.0)],
            "percentiles_tok_s": {
                "p50": data.get("p50_tok_s", 0.0),
                "p90": data.get("p90_tok_s", 0.0),
                "p99": data.get("p99_tok_s", 0.0),
            },
            "median_ttft_ms": data.get("median_ttft_ms", 0.0),
            "median_ttft_client_ms": data.get("median_ttft_client_ms", 0.0),
            "percentiles_ttft_ms": {
                "p50": data.get("p50_ttft_ms", 0.0),
                "p90": data.get("p90_ttft_ms", 0.0),
                "p99": data.get("p99_ttft_ms", 0.0),
            },
            "percentiles_ttft_client_ms": {
                "p90": data.get("p90_ttft_client_ms", 0.0),
            },
            "vram_bytes": data.get("vram_bytes", 0),
        }

        # Engine version and model metadata from raw results
        engine_results = [r for r in raw_results if r.get("engine") == engine_name]
        if engine_results:
            er = engine_results[0]
            engine_data["engine_version"] = er.get("engine_version", "")
            engine_data["model_format"] = er.get("model_format", "")
            engine_data["model_quantization"] = er.get("model_quantization", "")

        # Power data (if available)
        power_vals = [
            r.get("power_watts", 0) for r in engine_results if r.get("power_watts", 0) > 0
        ]
        if power_vals:
            engine_data["avg_power_watts"] = round(sum(power_vals) / len(power_vals), 1)
            eff_vals = [
                r["tok_per_sec_per_watt"]
                for r in engine_results
                if r.get("tok_per_sec_per_watt", 0) > 0
            ]
            if eff_vals:
                engine_data["avg_tok_per_sec_per_watt"] = round(sum(eff_vals) / len(eff_vals), 2)

        # Outliers
        outliers = data.get("outliers", [])
        if outliers:
            engine_data["outliers"] = outliers

        # Raw per-run data (stripped to essential fields)
        engine_data["raw_runs"] = [
            {
                "run_index": r.get("run_index", 0),
                "prompt_type": r.get("prompt_type", ""),
                "tok_per_sec": r.get("tok_per_sec", 0.0),
                "ttft_ms": r.get("ttft_ms", 0.0),
                "tokens_generated": r.get("tokens_generated", 0),
                "total_duration_ms": r.get("total_duration_ms", 0.0),
            }
            for r in engine_results
        ]

        engines_export[engine_name] = engine_data

    export = {
        "schema_version": 2,
        "asiai_version": __version__,
        "timestamp": first.get("ts", 0),
        "machine": {
            "chip": hw_chip,
            "os_version": os_version,
            "ram_gb": first.get("ram_gb", 0),
            "gpu_cores": first.get("gpu_cores", 0),
        },
        "benchmark": {
            "model": report.get("model", ""),
            "runs_per_prompt": runs_per_prompt,
            "prompts": prompts,
            "context_size": first.get("context_size", 0),
            "engines": engines_export,
            "winner": report.get("winner"),
        },
    }

    with open(output_path, "w") as f:
        json.dump(export, f, indent=2)

    return output_path


# ---------------------------------------------------------------------------
# Cross-model / matrix comparison support
# ---------------------------------------------------------------------------


def aggregate_slots(results: list[dict]) -> list[dict]:
    """Group results by (engine, model) and compute stats per slot.

    Returns a list of slot dicts ordered by median tok/s descending.
    Each slot contains engine, model, and all aggregated stats.
    """
    if not results:
        return []

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in results:
        key = (r.get("engine", ""), r.get("model", ""))
        groups[key].append(r)

    slots = []
    for (engine, model), runs in groups.items():
        data: dict = {
            "engine": engine,
            "model": model,
            "prompt_results": runs,
            "vram_bytes": runs[0].get("vram_bytes", 0),
            "thermal_level": runs[0].get("thermal_level", ""),
        }
        _compute_stats(runs, data)
        slots.append(data)

    return sorted(slots, key=lambda s: s.get("median_tok_s", 0), reverse=True)


def detect_session_type(slots: list[dict]) -> str:
    """Derive session type from slot data.

    Returns:
        "engine" — all slots share the same model (current behavior)
        "model"  — all slots share the same engine
        "matrix" — mixed models and engines
    """
    if not slots:
        return "engine"
    models = {s["model"] for s in slots}
    engines = {s["engine"] for s in slots}
    if len(models) == 1:
        return "engine"
    if len(engines) == 1:
        return "model"
    return "matrix"


def _determine_winner_slots(slots: list[dict]) -> dict | None:
    """Pick winner by median tok/s from a list of slots."""
    if len(slots) < 2:
        return None

    def _primary_tok_s(data: dict) -> float:
        return data.get("median_tok_s", 0.0) or data.get("avg_tok_s", 0.0)

    # slots already sorted by median_tok_s desc from aggregate_slots()
    best = slots[0]
    second = slots[1]

    best_tok = _primary_tok_s(best)
    second_tok = _primary_tok_s(second)
    if best_tok <= 0 or second_tok <= 0:
        return None

    tok_ratio = best_tok / second_tok
    if tok_ratio >= 1.5:
        tok_s_delta = f"{tok_ratio:.1f}x faster"
    else:
        tok_pct = (tok_ratio - 1) * 100
        tok_s_delta = f"+{tok_pct:.0f}% tok/s"

    vram_delta = ""
    if best.get("vram_bytes", 0) > 0 and second.get("vram_bytes", 0) > 0:
        vram_pct = ((best["vram_bytes"] - second["vram_bytes"]) / second["vram_bytes"]) * 100
        sign = "+" if vram_pct >= 0 else ""
        vram_delta = f"{sign}{vram_pct:.0f}% VRAM"

    # Build winner label based on what differs between best and second
    if best["model"] != second["model"] and best["engine"] != second["engine"]:
        winner_name = f"{best['model']} / {best['engine']}"
    elif best["model"] != second["model"]:
        winner_name = best["model"]
    else:
        winner_name = best["engine"]

    return {"name": winner_name, "tok_s_delta": tok_s_delta, "vram_delta": vram_delta}


def build_report(results: list[dict]) -> dict:
    """Unified report builder for all session types.

    Detects session_type from the data and returns a report with
    a "slots" list. For session_type == "engine", also populates
    legacy "model" and "engines" fields for backward compatibility.
    """
    if not results:
        return {
            "session_type": "engine",
            "slots": [],
            "winner": None,
            "model": "",
            "engines": {},
        }

    slots = aggregate_slots(results)
    session_type = detect_session_type(slots)
    winner = _determine_winner_slots(slots)

    report: dict = {
        "session_type": session_type,
        "slots": slots,
        "winner": winner,
    }

    # Backward compat: populate legacy fields for engine comparison
    if session_type == "engine":
        report["model"] = slots[0]["model"] if slots else ""
        report["engines"] = {s["engine"]: s for s in slots}

    return report


def report_to_slots(report: dict) -> list[dict]:
    """Convert any report format to a list of slot dicts.

    Works with both legacy reports (from aggregate_results) and
    new reports (from build_report). Code downstream can always
    call this to get a uniform list.
    """
    if "slots" in report:
        return report["slots"]
    # Legacy engine report: convert engines dict to slots list
    model = report.get("model", "")
    engines = report.get("engines", {})
    slots = [{"engine": name, "model": model, **stats} for name, stats in engines.items()]
    return sorted(slots, key=lambda s: s.get("median_tok_s", 0), reverse=True)
