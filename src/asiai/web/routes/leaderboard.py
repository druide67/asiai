"""Community leaderboard page (read-only).

- ``GET /api/v1/leaderboard`` — community entries from api.asiai.dev,
  cached 300s per (chip, model) filter so page polling never hammers the
  public API.
- ``GET /leaderboard`` — HTML shell; the table is client-rendered from
  the JSON route.

``fetch_leaderboard`` is a synchronous urllib call, so the handler wraps
it in ``asyncio.to_thread`` — same discipline as the fleet routes. The
community API being unreachable is a NORMAL state (offline lab, no
submissions yet): it surfaces as an empty list, never an error page.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from asiai.community import fetch_leaderboard

router = APIRouter(tags=["leaderboard"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# One fetch per filter combination per TTL — the community feed moves
# slowly and the page has no reason to hit the public API on every load.
_CACHE_TTL = 300.0
_cache: dict[tuple[str, str], tuple[float, list]] = {}
_cache_lock = threading.Lock()


def _cached_leaderboard(chip: str, model: str) -> list[dict]:
    key = (chip, model)
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < _CACHE_TTL:
            return hit[1]
    entries = fetch_leaderboard(chip=chip, model=model)
    with _cache_lock:
        # Bound the key space: filters are free-text, so an unbounded dict
        # would grow with every distinct (chip, model) a client tries.
        if len(_cache) >= 128:
            _cache.clear()
        # Don't cache failures long: an unreachable API answering [] would
        # otherwise stick for 5 minutes after connectivity returns.
        if entries:
            _cache[key] = (now, entries)
    return entries


@router.get("/api/v1/leaderboard")
async def api_leaderboard(
    chip: str = Query(default="", max_length=64),
    model: str = Query(default="", max_length=128),
) -> JSONResponse:
    """Community leaderboard entries, optionally filtered by chip/model."""
    entries = await asyncio.to_thread(_cached_leaderboard, chip.strip(), model.strip())
    return JSONResponse({"entries": entries, "count": len(entries)})


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
