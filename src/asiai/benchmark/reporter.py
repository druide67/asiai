"""Benchmark result aggregation and winner determination."""

from __future__ import annotations


def aggregate_results(results: list[dict]) -> dict:
    """Aggregate per-prompt results into per-engine summaries.

    Returns:
        {
            "model": str,
            "engines": {
                "engine_name": {
                    "avg_tok_s": float,
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

    # Compute averages
    for data in engines.values():
        pr = data["prompt_results"]
        tok_values = [p["tok_per_sec"] for p in pr if p["tok_per_sec"] > 0]
        ttft_values = [p["ttft_ms"] for p in pr if p["ttft_ms"] > 0]
        cpu_values = [p["proc_cpu_pct"] for p in pr if p.get("proc_cpu_pct", 0) > 0]
        rss_values = [p["proc_rss_bytes"] for p in pr if p.get("proc_rss_bytes", 0) > 0]
        data["avg_tok_s"] = (
            round(sum(tok_values) / len(tok_values), 1) if tok_values else 0.0
        )
        data["avg_ttft_ms"] = (
            round(sum(ttft_values) / len(ttft_values), 1) if ttft_values else 0.0
        )
        data["avg_proc_cpu"] = (
            round(sum(cpu_values) / len(cpu_values), 1) if cpu_values else 0.0
        )
        data["proc_rss_bytes"] = max(rss_values) if rss_values else 0

    # Determine winner by avg tok/s
    winner = _determine_winner(engines)

    return {"model": model, "engines": engines, "winner": winner}


def _determine_winner(engines: dict[str, dict]) -> dict | None:
    """Pick winner by highest avg_tok_s and compute deltas."""
    if len(engines) < 2:
        return None

    ranked = sorted(engines.items(), key=lambda x: x[1]["avg_tok_s"], reverse=True)
    best_name, best = ranked[0]
    second_name, second = ranked[1]

    if best["avg_tok_s"] <= 0 or second["avg_tok_s"] <= 0:
        return None

    tok_pct = ((best["avg_tok_s"] - second["avg_tok_s"]) / second["avg_tok_s"]) * 100
    tok_s_delta = f"+{tok_pct:.0f}% tok/s"

    vram_delta = ""
    if best["vram_bytes"] > 0 and second["vram_bytes"] > 0:
        vram_pct = (
            (best["vram_bytes"] - second["vram_bytes"]) / second["vram_bytes"]
        ) * 100
        sign = "+" if vram_pct >= 0 else ""
        vram_delta = f"{sign}{vram_pct:.0f}% VRAM"

    return {"name": best_name, "tok_s_delta": tok_s_delta, "vram_delta": vram_delta}
