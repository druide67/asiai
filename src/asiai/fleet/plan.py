"""Advisory UMA cohabitation planner — the VERDICT side of `aisctl plan`.

Ownership split (É3-S10): asiai-inference-server owns the COST of a
preset (weights + KV + overhead, with confidence bands), asiai owns the
VERDICT of whether that cost cohabits with what the node is already
running. aisrv depends on asiai, never the reverse, so the cost arrives
here as plain data (the JSON of ``GET /internal/v1/plan``) and this
module stays pure: no subprocess, no network, no clock.

Everything here is ADVISORY. A verdict informs the operator; it never
gates a command. Unknown inputs degrade to the ``unknown`` verdict
(fail-closed: absence of data is never reported as room to spare).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Verdict ladder, worst first. ``unknown`` outranks everything because a
# verdict built on missing data must not look safer than a bad one.
VERDICT_UNKNOWN = "unknown"
VERDICT_JETSAM_RISK = "jetsam-risk"
VERDICT_THERMAL_RISK = "thermal-risk"
VERDICT_TIGHT = "tight"
VERDICT_FITS = "fits"

# Headroom thresholds as a fraction of total unified RAM, computed on the
# PESSIMISTIC bound of the cost estimate. 15 % of a 64 GB node is ~9.6 GB
# — enough for page cache + burst allocations; below 5 % macOS jetsam
# starts killing under load (observed on the M4 aux stack, 2026-06-10).
FITS_HEADROOM_FRACTION = 0.15
TIGHT_HEADROOM_FRACTION = 0.05

_KNOWN_CONFIDENCES = frozenset({"measured", "declared", "computed"})


@dataclass(frozen=True)
class PresetCost:
    """Projected memory cost of one preset, as estimated by aisrv.

    ``total_mb_low`` / ``total_mb_high`` are the uncertainty band around
    the estimate (already widened by aisrv according to its source:
    measured, declared or computed). ``confidence`` is that source label;
    anything outside the known set is treated as unknown.
    """

    total_mb_low: float
    total_mb_high: float
    confidence: str
    components: dict = field(default_factory=dict)


@dataclass(frozen=True)
class NodeState:
    """Memory-relevant snapshot of the target node at verdict time."""

    mem_total_mb: float
    mem_used_mb: float
    pressure: str = "unknown"
    thermal_level: str = "unknown"
    # sysctl iogpu.wired_limit_mb — explicit ceiling on GPU-wired memory.
    # 0 means "no custom ceiling" (macOS default budget applies).
    gpu_wired_limit_mb: float = 0.0
    # Resident set per engine currently running, used to credit back the
    # memory an install/reinstall would evict.
    engine_rss_mb: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class PlanVerdict:
    """Advisory cohabitation verdict for installing a preset on a node."""

    verdict: str
    projected_free_mb: float | None
    projected_free_band: tuple[float, float] | None
    eviction_set: tuple[str, ...]
    headroom_pct: float | None
    reasons: tuple[str, ...]
    advisory: bool = True

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "projected_free_mb": self.projected_free_mb,
            "projected_free_band": list(self.projected_free_band)
            if self.projected_free_band is not None
            else None,
            "eviction_set": list(self.eviction_set),
            "headroom_pct": self.headroom_pct,
            "reasons": list(self.reasons),
            "advisory": True,
        }


def _unknown(reasons: tuple[str, ...], eviction_set: tuple[str, ...] = ()) -> PlanVerdict:
    return PlanVerdict(
        verdict=VERDICT_UNKNOWN,
        projected_free_mb=None,
        projected_free_band=None,
        eviction_set=eviction_set,
        headroom_pct=None,
        reasons=reasons,
    )


def cohabitation_verdict(
    cost: PresetCost,
    node: NodeState,
    replaces_engine: str | None = None,
) -> PlanVerdict:
    """Judge whether ``cost`` cohabits with what ``node`` is running.

    ``replaces_engine`` names an engine whose current RSS the operation
    frees first (install-over / reinstall) — its measured RSS is credited
    back before projecting. The credit only applies when that RSS is
    actually known; a missing measurement credits nothing rather than
    guessing.

    The verdict is computed on the PESSIMISTIC cost bound. Precedence:
    unknown > jetsam-risk > thermal-risk > tight > fits.
    """
    reasons: list[str] = []

    if cost.confidence not in _KNOWN_CONFIDENCES:
        return _unknown((f"cost-confidence-{cost.confidence or 'missing'}",))
    if cost.total_mb_high <= 0 or cost.total_mb_low <= 0:
        return _unknown(("cost-bounds-missing",))
    if cost.total_mb_low > cost.total_mb_high:
        return _unknown(("cost-bounds-inverted",))
    if node.mem_total_mb <= 0:
        return _unknown(("node-memory-unknown",))
    if node.mem_used_mb < 0:
        return _unknown(("node-memory-unknown",))

    eviction_set: tuple[str, ...] = ()
    freed_mb = 0.0
    if replaces_engine:
        rss = node.engine_rss_mb.get(replaces_engine, 0.0)
        if rss > 0:
            freed_mb = rss
            eviction_set = (replaces_engine,)
        else:
            reasons.append(f"eviction-credit-unknown:{replaces_engine}")

    free_now_mb = max(0.0, node.mem_total_mb - node.mem_used_mb)
    projected_low = free_now_mb + freed_mb - cost.total_mb_high  # pessimistic
    projected_high = free_now_mb + freed_mb - cost.total_mb_low
    headroom_pct = (projected_low / node.mem_total_mb) * 100.0

    if node.pressure in ("warn", "critical"):
        reasons.append(f"memory-pressure-{node.pressure}")
        verdict = VERDICT_JETSAM_RISK
    elif headroom_pct < TIGHT_HEADROOM_FRACTION * 100.0:
        reasons.append("headroom-below-5pct")
        verdict = VERDICT_JETSAM_RISK
    elif headroom_pct < FITS_HEADROOM_FRACTION * 100.0:
        reasons.append("headroom-5-15pct")
        verdict = VERDICT_TIGHT
    else:
        verdict = VERDICT_FITS

    # Explicit GPU-wired ceiling: a preset whose pessimistic cost exceeds
    # it can stall Metal allocations even with free RAM left, so a "fits"
    # is capped at "tight". It never upgrades a worse verdict.
    if 0 < node.gpu_wired_limit_mb < cost.total_mb_high:
        reasons.append("gpu-wired-ceiling")
        if verdict == VERDICT_FITS:
            verdict = VERDICT_TIGHT

    # Thermal pressure is advisory: it flags a bad moment to load a big
    # model, but memory risk always outranks it.
    if node.thermal_level in ("serious", "critical"):
        reasons.append(f"thermal-{node.thermal_level}")
        if verdict in (VERDICT_FITS, VERDICT_TIGHT):
            verdict = VERDICT_THERMAL_RISK

    return PlanVerdict(
        verdict=verdict,
        projected_free_mb=round(projected_low, 1),
        projected_free_band=(round(projected_low, 1), round(projected_high, 1)),
        eviction_set=eviction_set,
        headroom_pct=round(headroom_pct, 1),
        reasons=tuple(reasons),
    )
