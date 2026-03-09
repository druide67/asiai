"""Model and engine recommendation engine.

Recommends the best engine+model combination based on:
1. Local benchmark history (SQLite)
2. Community benchmark data (optional)
3. Hardware heuristics (fallback)
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from itertools import groupby
from operator import itemgetter

logger = logging.getLogger("asiai.advisor.recommender")

# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------


@dataclass
class Recommendation:
    """A single engine recommendation."""

    engine: str
    model: str
    score: float  # 0-100
    median_tok_s: float = 0.0
    median_ttft_ms: float = 0.0
    vram_bytes: int = 0
    source: str = ""  # "local", "community", "heuristic"
    confidence: str = ""  # "high", "medium", "low"
    reason: str = ""
    caveats: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def recommend(
    chip: str,
    ram_gb: int,
    use_case: str = "throughput",
    model_filter: str = "",
    db_path: str = "",
    community_url: str = "",
) -> list[Recommendation]:
    """Generate engine recommendations.

    Args:
        chip: Hardware chip (e.g. "Apple M4 Pro").
        ram_gb: Total RAM in GB.
        use_case: "throughput" | "latency" | "efficiency".
        model_filter: If set, only recommend for this model.
        db_path: Path to local SQLite database.
        community_url: If set, also query community data.

    Returns:
        List of Recommendation sorted by score (best first).
    """
    recommendations: list[Recommendation] = []

    # 1. Local data
    if db_path:
        local_recs = _from_local(db_path, use_case, model_filter, chip)
        recommendations.extend(local_recs)

    # 2. Community data
    if community_url:
        community_recs = _from_community(
            chip,
            ram_gb,
            use_case,
            model_filter,
            community_url,
        )
        # Merge: don't duplicate engine+model combos already in local
        local_keys = {(r.engine, r.model) for r in recommendations}
        for cr in community_recs:
            if (cr.engine, cr.model) not in local_keys:
                recommendations.append(cr)

    # 3. Heuristic fallback (if no data at all)
    if not recommendations:
        heuristic_recs = _from_heuristics(chip, ram_gb, use_case, model_filter)
        recommendations.extend(heuristic_recs)

    # Sort by score descending
    recommendations.sort(key=lambda r: r.score, reverse=True)
    return recommendations


# ---------------------------------------------------------------------------
# Private: local benchmarks
# ---------------------------------------------------------------------------


def _from_local(
    db_path: str,
    use_case: str,
    model_filter: str,
    chip: str,
) -> list[Recommendation]:
    """Build recommendations from local SQLite benchmark history."""
    try:
        from asiai.storage.db import query_benchmarks
    except ImportError:
        logger.warning("asiai.storage.db not available — skipping local data")
        return []

    rows = query_benchmarks(db_path, model=model_filter)
    if not rows:
        return []

    # Group by (engine, model)
    keyfn = itemgetter("engine", "model")
    sorted_rows = sorted(rows, key=keyfn)
    groups: dict[tuple[str, str], list[dict]] = {}
    for key, grp in groupby(sorted_rows, key=keyfn):
        groups[key] = list(grp)

    # Collect per-group metrics
    all_medians: list[float] = []
    group_stats: list[tuple[tuple[str, str], dict]] = []

    for (engine, model), entries in groups.items():
        tok_values = [e["tok_per_sec"] for e in entries if e.get("tok_per_sec")]
        ttft_values = [e["ttft_ms"] for e in entries if e.get("ttft_ms")]
        if not tok_values:
            continue
        med_tok = _median(tok_values)
        med_ttft = _median(ttft_values) if ttft_values else 0.0
        p99_ttft = _percentile(ttft_values, 99) if ttft_values else 0.0
        vram = max((e.get("vram_bytes") or 0) for e in entries)
        stability = _compute_stability_score(tok_values)
        all_medians.append(med_tok)
        group_stats.append(
            (
                (engine, model),
                {
                    "med_tok": med_tok,
                    "med_ttft": med_ttft,
                    "p99_ttft": p99_ttft,
                    "vram": vram,
                    "stability": stability,
                    "runs": len(tok_values),
                },
            ),
        )

    if not group_stats:
        return []

    # Normalize across all groups
    tok_norms = _normalize([s["med_tok"] for _, s in group_stats])

    results: list[Recommendation] = []
    for idx, ((engine, model), stats) in enumerate(group_stats):
        score = _score_use_case(
            use_case,
            tok_norm=tok_norms[idx],
            stability=stats["stability"],
            med_ttft=stats["med_ttft"],
            p99_ttft=stats["p99_ttft"],
            med_tok=stats["med_tok"],
            all_group_stats=group_stats,
            group_idx=idx,
        )
        runs = stats["runs"]
        confidence = "high" if runs >= 5 else ("medium" if runs >= 1 else "low")
        results.append(
            Recommendation(
                engine=engine,
                model=model,
                score=round(score, 1),
                median_tok_s=round(stats["med_tok"], 2),
                median_ttft_ms=round(stats["med_ttft"], 2),
                vram_bytes=stats["vram"],
                source="local",
                confidence=confidence,
                reason=(
                    f"Best {use_case} on your {chip} "
                    f"({stats['med_tok']:.1f} tok/s median, {runs} runs)"
                ),
            ),
        )
    return results


# ---------------------------------------------------------------------------
# Private: community data
# ---------------------------------------------------------------------------


def _from_community(
    chip: str,
    ram_gb: int,
    use_case: str,
    model_filter: str,
    community_url: str,
) -> list[Recommendation]:
    """Build recommendations from the community leaderboard."""
    try:
        from asiai.community import fetch_leaderboard
    except ImportError:
        logger.warning("asiai.community not available — skipping community data")
        return []

    try:
        entries = fetch_leaderboard(chip=chip, model=model_filter, api_url=community_url)
    except Exception:
        logger.warning("Failed to fetch community leaderboard", exc_info=True)
        return []

    if not entries:
        return []

    # Normalize tok/s across community entries
    tok_values = [e.get("median_tok_s", 0.0) for e in entries]
    tok_norms = _normalize(tok_values)

    results: list[Recommendation] = []
    for idx, entry in enumerate(entries):
        submissions = entry.get("submissions", 0)
        confidence = "high" if submissions >= 10 else ("medium" if submissions >= 3 else "low")
        med_tok = entry.get("median_tok_s", 0.0)
        med_ttft = entry.get("median_ttft_ms", 0.0)

        # Simple scoring: community has no per-run stability data
        score = tok_norms[idx] if use_case == "throughput" else tok_norms[idx] * 0.7

        results.append(
            Recommendation(
                engine=entry.get("engine", "unknown"),
                model=entry.get("model", "unknown"),
                score=round(score, 1),
                median_tok_s=round(med_tok, 2),
                median_ttft_ms=round(med_ttft, 2),
                source="community",
                confidence=confidence,
                reason=(f"Community data: {med_tok:.1f} tok/s median ({submissions} submissions)"),
            ),
        )
    return results


# ---------------------------------------------------------------------------
# Private: heuristic fallback
# ---------------------------------------------------------------------------

# Model families with approximate parameter counts (billions).
_HEURISTIC_MODELS: list[tuple[str, float]] = [
    ("qwen3.5:7b", 7),
    ("llama3.1:8b", 8),
    ("gemma-2:9b", 9),
    ("qwen3.5:14b", 14),
    ("deepseek-r1:14b", 14),
    ("gemma-3:27b", 27),
    ("qwen3.5:35b-a3b", 35),
    ("llama3.1:70b", 70),
]

_ENGINE_ORDER = ["ollama", "mlxlm", "lmstudio", "llamacpp", "vllm_mlx", "exo"]


def _from_heuristics(
    chip: str,
    ram_gb: int,
    use_case: str,
    model_filter: str,
) -> list[Recommendation]:
    """Produce rough recommendations when no benchmark data is available."""
    # Determine max model size that fits in RAM (rough rule of thumb).
    if ram_gb >= 128:
        max_b, base_score = 70, 50
    elif ram_gb >= 64:
        max_b, base_score = 35, 50
    elif ram_gb >= 48:
        max_b, base_score = 27, 45
    elif ram_gb >= 32:
        max_b, base_score = 14, 45
    else:
        max_b, base_score = 7, 40

    candidates = [(name, params) for name, params in _HEURISTIC_MODELS if params <= max_b]

    if model_filter:
        filtered = [(n, p) for n, p in candidates if model_filter.lower() in n.lower()]
        if filtered:
            candidates = filtered

    results: list[Recommendation] = []
    for engine_rank, engine in enumerate(_ENGINE_ORDER):
        for model_name, _params in candidates:
            # Small penalty for lower-priority engines
            score = max(0, base_score - engine_rank * 3)
            results.append(
                Recommendation(
                    engine=engine,
                    model=model_name,
                    score=float(score),
                    source="heuristic",
                    confidence="low",
                    reason=f"Estimated based on {chip} with {ram_gb}GB RAM",
                    caveats=["No benchmark data — run `asiai bench` first"],
                ),
            )
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _score_use_case(
    use_case: str,
    *,
    tok_norm: float,
    stability: float,
    med_ttft: float,
    p99_ttft: float,
    med_tok: float,
    all_group_stats: list[tuple[tuple[str, str], dict]],
    group_idx: int,
) -> float:
    """Compute a 0-100 score according to the requested use case."""
    if use_case == "latency":
        ttft_values = [s["med_ttft"] for _, s in all_group_stats if s["med_ttft"] > 0]
        p99_values = [s["p99_ttft"] for _, s in all_group_stats if s["p99_ttft"] > 0]
        inv_ttft = _normalize([1.0 / v if v > 0 else 0 for v in ttft_values])
        inv_p99 = _normalize([1.0 / v if v > 0 else 0 for v in p99_values])
        # Map group_idx to the filtered index
        ttft_idx = _filtered_index(all_group_stats, group_idx, "med_ttft")
        p99_idx = _filtered_index(all_group_stats, group_idx, "p99_ttft")
        if ttft_idx is not None and p99_idx is not None:
            return inv_ttft[ttft_idx] * 0.7 + inv_p99[p99_idx] * 0.3
        return tok_norm * 0.5  # fallback if no ttft data

    if use_case == "efficiency":
        # Approximate: tok/s per watt — without real power data, use tok/s as proxy
        return tok_norm

    # Default: throughput
    return tok_norm * 0.7 + stability * 0.3


def _filtered_index(
    all_group_stats: list[tuple[tuple[str, str], dict]],
    group_idx: int,
    field: str,
) -> int | None:
    """Return the index in the filtered (non-zero) list for *group_idx*."""
    counter = 0
    for idx, (_, s) in enumerate(all_group_stats):
        if s[field] > 0:
            if idx == group_idx:
                return counter
            counter += 1
    return None


def _normalize(values: list[float]) -> list[float]:
    """Min-max normalize *values* to [0, 100]."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    span = hi - lo
    if span == 0:
        return [50.0] * len(values)
    return [(v - lo) / span * 100 for v in values]


def _compute_stability_score(tok_values: list[float]) -> float:
    """Score stability based on coefficient of variation (CV).

    CV < 5%  -> 100
    CV < 10% -> 70
    CV >= 10% -> 40
    """
    if len(tok_values) < 2:
        return 70.0  # single run — neutral
    mean = statistics.mean(tok_values)
    if mean == 0:
        return 40.0
    cv = statistics.stdev(tok_values) / mean
    if cv < 0.05:
        return 100.0
    if cv < 0.10:
        return 70.0
    return 40.0


def _median(values: list[float]) -> float:
    """Return the median of *values*."""
    return statistics.median(values)


def _percentile(values: list[float], pct: int) -> float:
    """Return the *pct*-th percentile of *values* (nearest-rank method)."""
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = max(0, min(len(sorted_v) - 1, int(len(sorted_v) * pct / 100)))
    return sorted_v[k]
