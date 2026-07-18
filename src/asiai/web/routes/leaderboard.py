"""Community leaderboard page (read-only).

- ``GET /api/v1/leaderboard`` — community entries from api.asiai.dev,
  cached 300s per (chip, model, days) filter so page polling never
  hammers the public API.
- ``GET /api/v1/leaderboard/submissions`` — per-submission drill-down
  behind one leaderboard group (proxy to the community ``/benchmarks``
  endpoint). Not cached: it only fires on an explicit row expand, and
  the upstream endpoint may not be deployed yet — a miss maps to 404 so
  the client can degrade.
- ``GET /leaderboard`` — HTML shell; the table is client-rendered from
  the JSON routes.

``fetch_leaderboard``/``fetch_benchmarks`` are synchronous urllib calls,
so the handlers wrap them in ``asyncio.to_thread`` — same discipline as
the fleet routes. The community API being unreachable is a NORMAL state
(offline lab, no submissions yet): the leaderboard surfaces it as an
empty list, never an error page.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from asiai.auth.ratelimit import TokenRateLimiter
from asiai.community import fetch_benchmarks, fetch_leaderboard, normalize_model_name
from asiai.storage.db import query_benchmarks

router = APIRouter(tags=["leaderboard"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# One fetch per filter combination per TTL — the community feed moves
# slowly and the page has no reason to hit the public API on every load.
_CACHE_TTL = 300.0
_cache: dict[tuple[str, str, int], tuple[float, list]] = {}
_cache_lock = threading.Lock()

# Query-parameter charsets, mirrored from the community API contract so
# invalid input is rejected locally (422) instead of burning an outbound
# call that the upstream would 400 anyway.
_CHIP_PATTERN = r"^[a-zA-Z0-9_.+ -]+$"
_MODEL_PATTERN = r"^[a-zA-Z0-9_.+: -]+$"
_ENGINE_PATTERN = r"^[a-zA-Z0-9_.+ -]*$"

# Same posture as the fleet read proxy: every cache miss is an outbound
# call on the process-wide thread pool, and empty results are (rightly)
# not cached — so an unauthenticated client cycling distinct filters
# while the public API is down would otherwise turn every request into
# a 10s outbound fetch and starve snapshot/doctor/history reads.
_MAX_CONCURRENT_FETCHES = 4
_fetch_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_FETCHES)
_rate_limiter = TokenRateLimiter(limit=60, window_seconds=60.0)


def _cached_leaderboard(chip: str, model: str, days: int) -> list[dict]:
    key = (chip, model, days)
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < _CACHE_TTL:
            return hit[1]
    entries = fetch_leaderboard(chip=chip, model=model, days=days)
    with _cache_lock:
        # Bound the key space: filters are free-text, so an unbounded dict
        # would grow with every distinct (chip, model, days) a client tries.
        if len(_cache) >= 128:
            _cache.clear()
        # Don't cache failures long: an unreachable API answering [] would
        # otherwise stick for 5 minutes after connectivity returns.
        if entries:
            _cache[key] = (now, entries)
    return entries


def _client_ip(request: Request) -> str:
    """Peer IP for rate limiting (socket peer, no forwarded headers)."""
    return request.client.host if request.client else "unknown"


def _reject_early(request: Request) -> JSONResponse | None:
    """Shared rate-limit + concurrency guard for the community proxies."""
    allowed, _remaining, retry_after = _rate_limiter.check(_client_ip(request))
    if not allowed:
        return JSONResponse(
            {"error": "rate_limited"},
            status_code=429,
            headers={"Retry-After": str(int(retry_after) + 1)},
        )
    if _fetch_semaphore.locked():
        return JSONResponse(
            {
                "error": "busy",
                "detail": f"{_MAX_CONCURRENT_FETCHES} leaderboard fetches already in flight",
            },
            status_code=503,
            headers={"Retry-After": "2"},
        )
    return None


@router.get("/api/v1/leaderboard")
async def api_leaderboard(
    request: Request,
    chip: str = Query(default="", max_length=64),
    model: str = Query(default="", max_length=128),
    days: int = Query(default=90, ge=1, le=365),
) -> JSONResponse:
    """Community leaderboard entries, filtered by chip/model over a window."""
    early = _reject_early(request)
    if early is not None:
        return early
    async with _fetch_semaphore:
        entries = await asyncio.to_thread(_cached_leaderboard, chip.strip(), model.strip(), days)
    return JSONResponse({"entries": entries, "count": len(entries)})


def _build_compare(db_path: str, chip: str, model_filter: str, days: int) -> dict:
    """Local medians vs community medians per engine, strict-matched.

    Matching rule (ADR 0002): (chip, model, engine) compared strictly,
    case-insensitive. The local model name goes through
    ``normalize_model_name()`` — the submission-time normalizer — so a
    machine matches exactly what it would submit. Quantization is part
    of the name, hence part of the identity. Conditions are pooled, not
    matched (the v2 aggregates carry one median per group).
    """
    from statistics import median

    since = int(time.time()) - days * 86400
    rows = query_benchmarks(db_path, since=since)

    # Group local runs by normalized model name (display name kept).
    by_model: dict[str, list[tuple[str, dict]]] = {}
    for r in rows:
        name = normalize_model_name(str(r.get("model") or ""))
        if not name:
            continue
        by_model.setdefault(name.lower(), []).append((name, r))

    meta: dict = {"chip": chip, "window_days": days, "community_matched": False}
    if not by_model:
        meta["model"] = ""
        return {"rows": [], "meta": meta}

    # No explicit model: pick the local model with the most runs in the
    # window (deterministic; ties broken alphabetically).
    if model_filter:
        key = normalize_model_name(model_filter).lower()
    else:
        key = max(sorted(by_model), key=lambda k: len(by_model[k]))
    picked = by_model.get(key, [])
    display_model = picked[0][0] if picked else model_filter
    meta["model"] = display_model

    by_engine: dict[str, list[float]] = {}
    for _name, r in picked:
        eng = str(r.get("engine") or "").strip()
        tok = r.get("tok_per_sec")
        if eng and isinstance(tok, (int, float)) and tok > 0:
            by_engine.setdefault(eng, []).append(float(tok))
    if not by_engine:
        return {"rows": [], "meta": meta}

    # Community side: server filters by substring; the strict equality
    # re-check below is what actually decides a match.
    community: dict[str, dict] = {}
    if chip:
        for e in _cached_leaderboard(chip, display_model, days):
            if str(e.get("hw_chip") or "").strip().lower() != chip.strip().lower():
                continue
            if str(e.get("model") or "").strip().lower() != display_model.strip().lower():
                continue
            eng = str(e.get("engine") or "").strip()
            med = e.get("median_tok_s")
            if eng and isinstance(med, (int, float)) and med > 0:
                community[eng.lower()] = {
                    "median": float(med),
                    "n": e.get("samples") if isinstance(e.get("samples"), int) else 0,
                }

    out = []
    for eng in sorted(by_engine, key=str.lower):
        vals = by_engine[eng]
        local_med = float(median(vals))
        comm = community.get(eng.lower())
        delta = None
        if comm:
            delta = round((local_med - comm["median"]) / comm["median"] * 100, 1)
        out.append(
            {
                "engine": eng,
                "local_median_tok_s": round(local_med, 1),
                "local_n": len(vals),
                "community_median_tok_s": round(comm["median"], 1) if comm else None,
                "community_n": comm["n"] if comm else None,
                "delta_pct": delta,
            }
        )
    meta["community_matched"] = bool(community)
    return {"rows": out, "meta": meta}


@router.get("/api/v1/leaderboard/compare")
async def api_leaderboard_compare(
    request: Request,
    model: str = Query(default="", max_length=128),
    days: int = Query(default=30, ge=1, le=365),
) -> JSONResponse:
    """\"This machine vs community\" panel data (ADR 0002).

    Compares local medians (benchmarks DB) against the community group
    for the same (chip, model, engine), per engine, over the same
    window. Without ``model``, the server picks the local model with
    the most runs in the window.
    """
    early = _reject_early(request)
    if early is not None:
        return early
    from asiai.collectors.system import collect_hw_chip

    state = request.app.state.app_state
    async with _fetch_semaphore:
        chip = await asyncio.to_thread(collect_hw_chip)
        data = await asyncio.to_thread(
            _build_compare, state.db_path, (chip or "").strip(), model.strip(), days
        )
    return JSONResponse(data)


@router.get("/api/v1/leaderboard/submissions")
async def api_leaderboard_submissions(
    request: Request,
    chip: str = Query(min_length=1, max_length=64, pattern=_CHIP_PATTERN),
    model: str = Query(min_length=1, max_length=128, pattern=_MODEL_PATTERN),
    engine: str = Query(default="", max_length=32, pattern=_ENGINE_PATTERN),
    days: int = Query(default=90, ge=1, le=365),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> JSONResponse:
    """Per-submission drill-down behind one leaderboard group.

    Proxies the community ``GET /api/v1/benchmarks`` endpoint. That
    endpoint may not be deployed yet: any upstream failure (404 included)
    maps to a local 404 the client renders as "detail unavailable".
    """
    early = _reject_early(request)
    if early is not None:
        return early
    async with _fetch_semaphore:
        data = await asyncio.to_thread(
            fetch_benchmarks,
            chip=chip.strip(),
            model=model.strip(),
            engine=engine.strip(),
            days=days,
            limit=limit,
            offset=offset,
        )
    if data is None:
        return JSONResponse({"error": "detail_unavailable"}, status_code=404)
    return JSONResponse({"results": data["results"], "meta": data.get("meta", {})})


@router.get("/leaderboard")
async def page_leaderboard(request: Request):
    """Render the leaderboard shell; data arrives via /api/v1/leaderboard."""
    from asiai.collectors.system import collect_hw_chip

    local_chip = await asyncio.to_thread(collect_hw_chip)
    return templates.TemplateResponse(
        request,
        "leaderboard.html",
        {"nav_active": "leaderboard", "local_chip": local_chip or ""},
    )
