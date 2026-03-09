"""Community benchmark database client.

Handles submission, leaderboard retrieval, and comparison with community data.
All network operations are optional and fail gracefully — a network failure
never interrupts the local benchmark workflow.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger("asiai.community")

DEFAULT_API_URL = "https://api.asiai.dev/api/v1"
_MAX_RESPONSE_BYTES = 1 * 1024 * 1024  # 1 MB safety cap
_POST_TIMEOUT = 30  # seconds
_GET_TIMEOUT = 10  # seconds


@dataclass
class SubmitResult:
    """Result of a community submission attempt."""

    success: bool
    submission_id: str = ""
    http_status: int = 0
    error: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_api_url() -> str:
    """Return community API URL from env or default."""
    return os.environ.get("ASIAI_COMMUNITY_URL", DEFAULT_API_URL).rstrip("/")


def _safe_get(url: str, timeout: int = _GET_TIMEOUT) -> Any:
    """Issue a GET request and return parsed JSON, or *None* on any error."""
    try:
        req = Request(url)
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_RESPONSE_BYTES:
                logger.warning(
                    "Response from %s exceeded %d bytes — dropped",
                    url,
                    _MAX_RESPONSE_BYTES,
                )
                return None
            return json.loads(raw.decode("utf-8"))
    except HTTPError as exc:
        logger.warning("Community API HTTP %d: %s", exc.code, url)
    except (URLError, OSError) as exc:
        logger.warning("Community API unreachable: %s (%s)", exc, url)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Community API bad JSON: %s (%s)", exc, url)
    return None


# ---------------------------------------------------------------------------
# Build submission payload
# ---------------------------------------------------------------------------


def build_submission(
    raw_results: list[dict],
    report: dict,
) -> dict:
    """Build an anonymized submission payload from benchmark results.

    Uses the same export format as *reporter.export_benchmark()* but adds
    community-specific fields (``id``, ``hw_ram_gb``, ``_hash``).

    Args:
        raw_results: Raw per-run result dicts from ``BenchmarkRun.results``.
        report: Aggregated report from ``aggregate_results()``.

    Returns:
        Dict ready to be JSON-serialized and POSTed.
    """
    from asiai import __version__
    from asiai.collectors.system import collect_memory

    mem = collect_memory()
    hw_ram_gb = round(mem.total / (1024**3)) if mem.total > 0 else 0

    first: dict = raw_results[0] if raw_results else {}
    submission_id = str(uuid.uuid4())

    # Build per-engine summaries from the aggregated report.
    engines_data: dict[str, dict] = {}
    for engine_name, data in report.get("engines", {}).items():
        # Pick the first raw result for this engine (for metadata fields).
        engine_results = [r for r in raw_results if r.get("engine") == engine_name]
        er: dict = engine_results[0] if engine_results else {}
        engines_data[engine_name] = {
            "median_tok_s": data.get("median_tok_s", 0.0),
            "avg_tok_s": data.get("avg_tok_s", 0.0),
            "ci95": [data.get("ci95_lower", 0.0), data.get("ci95_upper", 0.0)],
            "median_ttft_ms": data.get("median_ttft_ms", 0.0),
            "vram_bytes": data.get("vram_bytes", 0),
            "engine_version": er.get("engine_version", ""),
            "model_format": er.get("model_format", ""),
            "model_quantization": er.get("model_quantization", ""),
            "stability": data.get("stability", ""),
            "runs_count": data.get("runs_count", 1),
        }

    prompts = sorted({r.get("prompt_type", "") for r in raw_results if r.get("prompt_type")})
    run_indices = {r.get("run_index", 0) for r in raw_results}

    payload: dict[str, Any] = {
        "id": submission_id,
        "schema_version": 1,
        "ts": first.get("ts", int(time.time())),
        "hw_chip": first.get("hw_chip", ""),
        "hw_ram_gb": hw_ram_gb,
        "os_version": first.get("os_version", ""),
        "asiai_version": __version__,
        "benchmark": {
            "model": report.get("model", ""),
            "runs_per_prompt": len(run_indices),
            "prompts": prompts,
            "engines": engines_data,
        },
    }

    # Deterministic hash for server-side dedup.
    payload_json = json.dumps(payload, sort_keys=True)
    payload["_hash"] = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    return payload


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------


def submit_benchmark(
    payload: dict,
    api_url: str = "",
    db_path: str = "",
) -> SubmitResult:
    """Submit a benchmark to the community database.

    Args:
        payload: Dict from :func:`build_submission`.
        api_url: API base URL (default from env/config).
        db_path: If provided, record submission in local SQLite.

    Returns:
        :class:`SubmitResult` with success status.
    """
    url = f"{api_url or get_api_url()}/benchmarks"
    submission_id = payload.get("id", "")
    model = payload.get("benchmark", {}).get("model", "")

    result = SubmitResult(success=False, submission_id=submission_id)

    try:
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=_POST_TIMEOUT) as resp:
            result.http_status = resp.status
            result.success = 200 <= resp.status < 300
            if result.success:
                logger.info(
                    "Community submission %s accepted (HTTP %d)",
                    submission_id,
                    resp.status,
                )
            else:
                result.error = f"HTTP {resp.status}"
                logger.warning(
                    "Community submission %s rejected (HTTP %d)",
                    submission_id,
                    resp.status,
                )
    except HTTPError as exc:
        result.http_status = exc.code
        result.error = f"HTTP {exc.code}"
        logger.warning("Community submission HTTP error %d: %s", exc.code, url)
    except (URLError, OSError) as exc:
        result.error = str(exc)
        logger.warning("Community submission failed: %s (%s)", exc, url)

    # Persist locally for audit / retry.
    if db_path:
        try:
            from asiai.storage.db import store_community_submission

            store_community_submission(
                db_path,
                {
                    "id": submission_id,
                    "ts": int(time.time()),
                    "model": model,
                    "status": "accepted" if result.success else "failed",
                    "response_status": result.http_status or None,
                    "error": result.error,
                    "payload_hash": payload.get("_hash", ""),
                },
            )
        except Exception:
            logger.debug("Could not record submission in local DB", exc_info=True)

    return result


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------


def fetch_leaderboard(
    chip: str = "",
    model: str = "",
    api_url: str = "",
) -> list[dict]:
    """Fetch leaderboard data from community API.

    Args:
        chip: Filter by chip (e.g. ``"Apple M4 Pro"``).
        model: Filter by model name.
        api_url: API base URL.

    Returns:
        List of leaderboard entries (dicts) or empty list on failure.
    """
    params: dict[str, str] = {}
    if chip:
        params["chip"] = chip
    if model:
        params["model"] = model

    base = f"{api_url or get_api_url()}/leaderboard"
    url = f"{base}?{urlencode(params)}" if params else base

    data = _safe_get(url)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "results" in data:
        return data["results"]  # type: ignore[return-value]
    return []


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def fetch_comparison(
    chip: str,
    model: str,
    local_results: dict,
    api_url: str = "",
) -> dict:
    """Compare local results against community data.

    Args:
        chip: Hardware chip identifier (e.g. ``"Apple M1 Max"``).
        model: Model name.
        local_results: Local benchmark report (from ``aggregate_results()``).
        api_url: API base URL.

    Returns:
        Comparison dict with community stats and deltas, or empty dict on
        failure.
    """
    params = urlencode({"chip": chip, "model": model})
    url = f"{api_url or get_api_url()}/compare?{params}"

    community = _safe_get(url)
    if not isinstance(community, dict):
        return {}

    # Compute deltas between local and community medians.
    comparison: dict[str, Any] = {
        "chip": chip,
        "model": model,
        "community": community,
        "engines": {},
    }

    community_engines = community.get("engines", {})
    local_engines = local_results.get("engines", {})

    for engine_name, local_data in local_engines.items():
        local_median = local_data.get("median_tok_s", 0.0)
        comm_entry = community_engines.get(engine_name, {})
        comm_median = comm_entry.get("median_tok_s", 0.0)

        if local_median > 0 and comm_median > 0:
            delta = local_median - comm_median
            delta_pct = round((delta / comm_median) * 100, 1)
        else:
            delta = 0.0
            delta_pct = 0.0

        comparison["engines"][engine_name] = {
            "local_median_tok_s": local_median,
            "community_median_tok_s": comm_median,
            "delta_tok_s": round(delta, 1),
            "delta_pct": delta_pct,
            "community_samples": comm_entry.get("samples", 0),
        }

    return comparison
