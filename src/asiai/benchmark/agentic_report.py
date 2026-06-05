"""Summarize agentic-mode bench JSON into ranked, gated leaderboard rows.

Ports the decision logic validated in the 2026-06 campaign — deterministic gates
on validity / TTFT / prefix-cache reuse, then tiers (★ winner · ✓ viable ·
⚠ reserve · ✗ eliminated) grouped per machine — into asiai itself, replacing the
external ``aggregate.py`` hack. With schema ``agentic-v4`` every column is read
from the JSON's own self-describing fields (``hw_chip``, ``machine_model``,
``ram_gb``, ``powermode``, ``engine_version``); for legacy ``agentic-v3`` JSON it
falls back to parsing the file stem.

MTP is a serving-side flag (``--spec-type draft-mtp``) invisible to asiai, so it
is still read from the file stem (``…-MTP…``) — the operator names it there.

Validity gate threshold is aligned with ``reporter.DEFAULT_MIN_VALID_PCT`` (80):
``< 80`` eliminates, ``80–95`` is a reserve, ``≥ 95`` passes clean. ``★`` ranks by
validated *throughput* only — the final pick also weighs output quality (the
dev/code evaluation), which throughput does not capture.
"""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from typing import Any

from asiai.benchmark.output_gates import DEFAULT_MIN_VALID_PCT

# Gate thresholds.
VALID_CLEAN = 95.0
VALID_MIN = DEFAULT_MIN_VALID_PCT  # 80.0
TTFT_OK_MS = 500.0
TTFT_FAIL_MS = 3000.0
REUSE_OK = 0.5
_RANK = {"✓": 0, "⚠": 1, "✗": 2}

_RSS_FLOOR_MB = 500.0  # below this a match is a spurious sub-engine process

_QUANT_PATTERNS = [
    (r"Q4_K_XL", "Q4_K_XL"),
    (r"Q5_K_XL", "Q5_K_XL"),
    (r"Q4_K_S", "Q4_K_S"),
    (r"Q5_K_S", "Q5_K_S"),
    (r"Q4_K_M", "Q4_K_M"),
    (r"Q5_K_M", "Q5_K_M"),
    (r"Q6_K", "Q6_K"),
    (r"(?:MLX[-_]?4bit|[-_]4bit)", "MLX4"),
    (r"5bit", "MLX5"),
]


def parse_quant(model_id: str | None) -> str | None:
    m = model_id or ""
    for pat, lab in _QUANT_PATTERNS:
        if re.search(pat, m, re.I):
            return lab
    return None


def _parse_model(stem: str, model_id: str | None) -> str:
    s = (stem + " " + (model_id or "")).lower()
    fam = "Qwopus" if "qwopus" in s else "Qwen"
    arch = "35B" if ("35b" in s or "a3b" in s) else "27B"
    return f"{fam}-{arch}"


def _parse_mtp(stem: str) -> bool:
    s = stem.lower()
    return "mtp" in s and "-off" not in s


def _machine_label(hw_chip: str | None, ram_gb: int | None, stem: str) -> str:
    """Machine block label (e.g. ``M5``) from the recorded chip, stem fallback."""
    if hw_chip:
        m = re.search(r"\bM(\d+)\b", hw_chip)
        if m:
            return f"M{m.group(1)}"
    s = stem.lower()
    for tag in ("m5", "m4", "m3", "m2", "m1"):
        if s.startswith(tag):
            return tag.upper()
    return "?"


def _med_pos(xs: list) -> float | None:
    xs = [x for x in xs if isinstance(x, (int, float)) and x > 0]
    return statistics.median(xs) if xs else None


def _phase_vals(runs: list[dict], phase: str, key: str) -> list:
    return [r.get(key) for r in runs if r.get("phase") == phase and r.get(key) is not None]


def summarize_agentic(data: dict, stem: str = "") -> dict[str, Any]:
    """One leaderboard row from one agentic-bench result dict.

    Reads self-describing v4 fields (``hw_chip``/``engine_version``/``footprint``)
    and falls back to stem parsing + per-run recomputation for legacy v3 JSON.
    """
    runs = data.get("runs", [])
    warm = "warm" if any(r.get("phase") == "warm" for r in runs) else "cold"
    model_id = data.get("model")
    stem_l = stem.lower()
    engine = "mlx_vlm" if "mlxvlm" in stem_l else (data.get("engine") or "?")

    fp = data.get("footprint") or {}
    ram_peak = fp.get("engine_rss_peak_mb")
    ram_warm = fp.get("engine_rss_warm_mb")
    if ram_peak is None:  # legacy v3 — recompute from per-run RSS
        rss_all = [
            r.get("engine_rss_mb") for r in runs if (r.get("engine_rss_mb") or 0) > _RSS_FLOOR_MB
        ]
        ram_peak = max(rss_all) if rss_all else None
        rss_warm = [
            r.get("engine_rss_mb")
            for r in runs
            if r.get("phase") == warm and (r.get("engine_rss_mb") or 0) > _RSS_FLOOR_MB
        ]
        ram_warm = statistics.median(rss_warm) if rss_warm else None

    qg = data.get("quality_gates", {}) or {}
    reuse = data.get("prefix_cache_reuse", {}) or {}
    decs = [r.get("decode_tok_s") for r in runs if (r.get("decode_tok_s") or 0) > 0]

    return {
        "machine": _machine_label(data.get("hw_chip"), data.get("ram_gb"), stem),
        "hw_chip": data.get("hw_chip"),
        "model": _parse_model(stem, model_id),
        "quant": parse_quant(model_id),
        "model_id": model_id,
        "engine": engine,
        "engine_version": data.get("engine_version"),
        "mtp": _parse_mtp(stem),
        "powermode": data.get("powermode"),
        "ram_gb": data.get("ram_gb"),
        "bench_mode": data.get("bench_mode"),
        "dec": _med_pos(_phase_vals(runs, warm, "decode_tok_s")),
        "peak": max(decs) if decs else None,
        "long_ctx": _med_pos(_phase_vals(runs, "long-context", "decode_tok_s")),
        "ttft": _med_pos(_phase_vals(runs, warm, "ttft_ms")),
        "socw": _med_pos(_phase_vals(runs, warm, "soc_watts")),
        "tsw": _med_pos(_phase_vals(runs, warm, "tok_s_per_soc_watt")),
        "jtok": _med_pos(_phase_vals(runs, warm, "energy_per_token_j")),
        "ram_peak_mb": ram_peak,
        "ram_warm_mb": ram_warm,
        "valid": qg.get("output_validity", {}).get("output_valid_pct"),
        "reuse": reuse.get("reuse_fraction"),
        "reuse_ttft": reuse.get("reuse_corroborated_by_ttft"),
        "reuse_source": reuse.get("cache_source"),
    }


def gate(row: dict) -> tuple[str, list[str]]:
    """Deterministic verdict (``✓``/``⚠``/``✗``) + the causes that capped it.

    The verdict is the worst of the validity, TTFT and reuse gates. A
    non-measured signal (``None``) is neutral, never a failure.
    """
    worst, causes = "✓", []

    def bump(level: str, why: str) -> None:
        nonlocal worst
        if _RANK[level] > _RANK[worst]:
            worst = level
        if level != "✓":
            causes.append(why)

    v = row.get("valid")
    if v is not None:
        bump("✗" if v < VALID_MIN else "⚠" if v < VALID_CLEAN else "✓", f"val{v:.0f}%")
    t = row.get("ttft")
    if t is not None:
        bump("✗" if t > TTFT_FAIL_MS else "⚠" if t > TTFT_OK_MS else "✓", f"ttft{t:.0f}ms")
    r = row.get("reuse")
    if r is not None:
        bump("✗" if r == 0 else "⚠" if r < REUSE_OK else "✓", "reuse0" if r == 0 else f"reuse{r}")
    return worst, causes


def load_agentic_dir(path: str | Path) -> list[dict]:
    """Summarize every agentic-bench JSON under ``path`` into leaderboard rows.

    A file qualifies when it carries ``runs`` and either ``bench_mode ==
    'agentic'`` or a ``prefix_cache_reuse`` block (the agentic signature) — burst
    and standard JSON are skipped. Unreadable files are ignored.
    """
    p = Path(path)
    files = sorted(p.glob("*.json")) if p.is_dir() else [p]
    rows: list[dict] = []
    for f in files:
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        if not isinstance(data, dict) or not data.get("runs"):
            continue
        is_agentic = data.get("bench_mode") == "agentic" or "prefix_cache_reuse" in data
        if not is_agentic:
            continue
        rows.append(summarize_agentic(data, f.stem))
    return rows
