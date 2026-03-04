"""Benchmark result aggregation and winner determination."""

from __future__ import annotations

import math


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

    # Compute averages and variance
    for data in engines.values():
        pr = data["prompt_results"]
        tok_values = [p["tok_per_sec"] for p in pr if p["tok_per_sec"] > 0]
        ttft_values = [p["ttft_ms"] for p in pr if p["ttft_ms"] > 0]
        cpu_values = [p["proc_cpu_pct"] for p in pr if p.get("proc_cpu_pct", 0) > 0]
        rss_values = [p["proc_rss_bytes"] for p in pr if p.get("proc_rss_bytes", 0) > 0]
        data["avg_tok_s"] = round(sum(tok_values) / len(tok_values), 1) if tok_values else 0.0
        data["avg_ttft_ms"] = round(sum(ttft_values) / len(ttft_values), 1) if ttft_values else 0.0
        data["avg_proc_cpu"] = round(sum(cpu_values) / len(cpu_values), 1) if cpu_values else 0.0
        data["proc_rss_bytes"] = max(rss_values) if rss_values else 0

        # Tokens generated and total duration (for display)
        tok_gen_values = [p["tokens_generated"] for p in pr if p.get("tokens_generated", 0) > 0]
        duration_values = [
            p["total_duration_ms"] for p in pr if p.get("total_duration_ms", 0) > 0
        ]
        data["avg_tokens_generated"] = (
            round(sum(tok_gen_values) / len(tok_gen_values)) if tok_gen_values else 0
        )
        data["avg_total_duration_ms"] = (
            round(sum(duration_values) / len(duration_values), 1) if duration_values else 0.0
        )

        # Variance: pooled intra-prompt stddev (excludes inter-prompt variance)
        data["std_dev_tok_s"] = _pooled_stddev(pr)
        data["runs_count"] = _count_runs(pr)
        data["stability"] = _classify_stability(data["avg_tok_s"], data["std_dev_tok_s"])

    # Determine winner by avg tok/s
    winner = _determine_winner(engines)

    return {"model": model, "engines": engines, "winner": winner}


def _stddev(values: list[float]) -> float:
    """Compute population standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
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
        var = sum((v - mean) ** 2 for v in values) / len(values)
        variances.append(var)

    if not variances:
        return 0.0

    pooled_var = sum(variances) / len(variances)
    return round(math.sqrt(pooled_var), 2)


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


def _determine_winner(engines: dict[str, dict]) -> dict | None:
    """Pick winner by highest avg_tok_s and compute deltas."""
    if len(engines) < 2:
        return None

    ranked = sorted(engines.items(), key=lambda x: x[1]["avg_tok_s"], reverse=True)
    best_name, best = ranked[0]
    second_name, second = ranked[1]

    if best["avg_tok_s"] <= 0 or second["avg_tok_s"] <= 0:
        return None

    tok_ratio = best["avg_tok_s"] / second["avg_tok_s"]
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
