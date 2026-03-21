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


def normalize_model_name(raw: str) -> str:
    """Normalize a model name before community submission.

    Strips filesystem paths (vllm-mlx local dirs) and SHA256 blob names
    (llamacpp blobs) to produce a clean, human-readable model name.
    """
    name = raw

    # Strip filesystem paths
    if "/" in name or "\\" in name:
        name = os.path.basename(name)

    # Drop SHA256 blob names entirely
    if name.startswith("sha256-") and len(name) > 20:
        return ""

    return name.strip()


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


def _build_slot_entry(
    slot_data: dict,
    raw_results: list[dict],
) -> dict[str, Any]:
    """Build a single slot entry for community submission payload.

    Extracts stats from aggregated slot data and metadata from raw results.
    Shared between v2 (engine-keyed) and v3 (slots array) payloads.
    """
    engine_name = slot_data.get("engine", "")
    model_name = slot_data.get("model", "")

    # Pick raw results for this slot.
    # Filter by (engine, model) when model is present in raw data,
    # otherwise filter by engine only (legacy single-model benchmarks).
    slot_results = [
        r
        for r in raw_results
        if r.get("engine") == engine_name
        and (not r.get("model") or r.get("model") == model_name)
    ]
    er: dict = slot_results[0] if slot_results else {}

    # Power/efficiency/load from raw results
    power_vals = [r.get("power_watts", 0) for r in slot_results if r.get("power_watts", 0) > 0]
    eff_vals = [
        r.get("tok_per_sec_per_watt", 0)
        for r in slot_results
        if r.get("tok_per_sec_per_watt", 0) > 0
    ]
    load_vals = [
        r.get("load_time_ms", 0) for r in slot_results if r.get("load_time_ms", 0) > 0
    ]

    entry: dict[str, Any] = {
        "median_tok_s": slot_data.get("median_tok_s", 0.0),
        "avg_tok_s": slot_data.get("avg_tok_s", 0.0),
        "ci95": [slot_data.get("ci95_lower", 0.0), slot_data.get("ci95_upper", 0.0)],
        "median_ttft_ms": slot_data.get("median_ttft_ms", 0.0),
        "vram_bytes": slot_data.get("vram_bytes", 0),
        "engine_version": er.get("engine_version", ""),
        "model_format": er.get("model_format", ""),
        "model_quantization": er.get("model_quantization", ""),
        "stability": slot_data.get("stability", ""),
        "runs_count": slot_data.get("runs_count", 1),
        "p90_tok_s": slot_data.get("p90_tok_s", 0.0),
        "p99_tok_s": slot_data.get("p99_tok_s", 0.0),
        "p90_ttft_ms": slot_data.get("p90_ttft_ms", 0.0),
    }
    if power_vals:
        entry["avg_power_watts"] = round(sum(power_vals) / len(power_vals), 1)
    if eff_vals:
        entry["avg_tok_per_sec_per_watt"] = round(sum(eff_vals) / len(eff_vals), 2)
    if load_vals:
        entry["load_time_ms"] = round(sum(load_vals) / len(load_vals), 1)

    return entry


def build_submission(
    raw_results: list[dict],
    report: dict,
) -> dict:
    """Build an anonymized submission payload from benchmark results.

    Produces **schema_version 2** for engine-comparison sessions (backward
    compatible) and **schema_version 3** for model/matrix sessions (slots
    array where each slot = independent leaderboard entry).

    Args:
        raw_results: Raw per-run result dicts from ``BenchmarkRun.results``.
        report: Aggregated report from ``aggregate_results()`` or ``build_report()``.

    Returns:
        Dict ready to be JSON-serialized and POSTed.
    """
    from asiai import __version__
    from asiai.benchmark.reporter import report_to_slots
    from asiai.collectors.system import collect_memory

    mem = collect_memory()
    hw_ram_gb = round(mem.total / (1024**3)) if mem.total > 0 else 0

    first: dict = raw_results[0] if raw_results else {}
    submission_id = str(uuid.uuid4())

    prompts = sorted({r.get("prompt_type", "") for r in raw_results if r.get("prompt_type")})
    run_indices = {r.get("run_index", 0) for r in raw_results}
    context_size = first.get("context_size", 0)
    gpu_cores = first.get("gpu_cores", 0)

    session_type = report.get("session_type", "engine")
    slots = report_to_slots(report)

    # Common payload fields
    payload_base: dict[str, Any] = {
        "id": submission_id,
        "ts": first.get("ts", int(time.time())),
        "hw_chip": first.get("hw_chip", ""),
        "hw_ram_gb": hw_ram_gb,
        "hw_gpu_cores": gpu_cores,
        "os_version": first.get("os_version", ""),
        "asiai_version": __version__,
    }

    if session_type == "engine":
        # Schema v2 — backward compatible engine comparison
        raw_model = report.get("model", slots[0]["model"] if slots else "")
        clean_model = normalize_model_name(raw_model)
        if not clean_model:
            logger.warning(
                "Model name '%s' could not be normalized — skipping submission",
                raw_model,
            )

        engines_data: dict[str, dict] = {}
        for slot in slots:
            entry = _build_slot_entry(slot, raw_results)
            engines_data[slot["engine"]] = entry

        payload: dict[str, Any] = {
            **payload_base,
            "schema_version": 2,
            "benchmark": {
                "model": clean_model or raw_model,
                "runs_per_prompt": len(run_indices),
                "prompts": prompts,
                "context_size": context_size,
                "engines": engines_data,
            },
        }
    else:
        # Schema v3 — model/matrix sessions with slots array
        # Each slot is an independent leaderboard entry (no data loss).
        slots_data: list[dict[str, Any]] = []
        for slot in slots:
            raw_model = slot.get("model", "")
            clean_model = normalize_model_name(raw_model)
            if not clean_model:
                logger.warning(
                    "Model name '%s' could not be normalized — slot skipped",
                    raw_model,
                )
                continue

            entry = _build_slot_entry(slot, raw_results)
            entry["engine"] = slot["engine"]
            entry["model"] = clean_model
            entry["model_raw"] = raw_model
            slots_data.append(entry)

        payload = {
            **payload_base,
            "schema_version": 3,
            "session_type": session_type,
            "benchmark": {
                "slots": slots_data,
                "runs_per_prompt": len(run_indices),
                "prompts": prompts,
                "context_size": context_size,
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
        if exc.code == 429:
            # Rate limited — tell user clearly, don't retry
            try:
                body = json.loads(exc.read().decode("utf-8", errors="replace"))
                result.error = body.get("error", "Rate limited — try again later")
            except Exception:
                result.error = "Rate limited — try again later"
            logger.info("Community submission rate-limited (429), not retrying")
        elif exc.code == 409:
            # Duplicate — already submitted, treat as success
            result.success = True
            result.error = ""
            logger.info("Community submission %s already exists (409)", submission_id)
        else:
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


# ---------------------------------------------------------------------------
# Agent registration (opt-in, ADR-001)
# ---------------------------------------------------------------------------

_AGENT_JSON = os.path.join(
    os.environ.get("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")),
    "asiai",
    "agent.json",
)
_REGISTER_TIMEOUT = 5  # seconds


@dataclass
class AgentRegistration:
    """Result of an agent registration attempt."""

    success: bool
    agent_id: str = ""
    agent_token: str = ""
    total_agents: int = 0
    error: str = ""


def _load_agent_json() -> dict:
    """Load agent credentials from disk, or return empty dict."""
    try:
        with open(_AGENT_JSON) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_agent_json(data: dict) -> None:
    """Save agent credentials to disk with restrictive permissions."""
    os.makedirs(os.path.dirname(_AGENT_JSON), exist_ok=True)
    with open(_AGENT_JSON, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(_AGENT_JSON, 0o600)


def register_agent(
    chip: str = "",
    ram_gb: int = 0,
    engines: list[str] | None = None,
    api_url: str = "",
    verbose: bool = True,
) -> AgentRegistration:
    """Register with the asiai agent network (opt-in).

    If an agent.json already exists, sends a heartbeat instead of re-registering.

    Args:
        chip: Hardware chip (e.g. "Apple M4 Pro").
        ram_gb: Total RAM in GB.
        engines: List of detected engine names.
        api_url: API base URL (default from env/config).
        verbose: Print payload and result to stdout.

    Returns:
        :class:`AgentRegistration` with success status.
    """
    from asiai import __version__

    base = api_url or get_api_url()
    result = AgentRegistration(success=False)

    # Check for existing registration → heartbeat
    existing = _load_agent_json()
    if existing.get("agent_id") and existing.get("agent_token"):
        return _agent_heartbeat(
            existing["agent_id"],
            existing["agent_token"],
            engines=engines or [],
            api_url=base,
            verbose=verbose,
        )

    # First-time registration
    payload = {
        "chip": chip,
        "ram_gb": ram_gb,
        "engines": engines or [],
        "framework": "asiai-mcp",
        "asiai_version": __version__,
    }

    if verbose:
        engine_str = ", ".join(engines or []) or "none"
        logger.info(
            "Registering with asiai network: chip=%s, ram=%dGB, engines=%s",
            chip or "unknown",
            ram_gb,
            engine_str,
        )

    try:
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            f"{base}/agent-register",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=_REGISTER_TIMEOUT) as resp:
            body = json.loads(resp.read(_MAX_RESPONSE_BYTES).decode("utf-8"))
            result.success = True
            result.agent_id = body.get("agent_id", "")
            result.agent_token = body.get("agent_token", "")
            result.total_agents = body.get("total_agents", 0)

            _save_agent_json(
                {
                    "agent_id": result.agent_id,
                    "agent_token": result.agent_token,
                    "registered_at": int(time.time()),
                    "total_agents": result.total_agents,
                }
            )

    except HTTPError as exc:
        result.error = f"HTTP {exc.code}"
        logger.warning("Agent registration HTTP error %d", exc.code)
    except (URLError, OSError) as exc:
        result.error = str(exc)
        logger.warning("Agent registration failed: %s", exc)
    except (json.JSONDecodeError, ValueError) as exc:
        result.error = str(exc)
        logger.warning("Agent registration bad response: %s", exc)

    return result


def _agent_heartbeat(
    agent_id: str,
    agent_token: str,
    engines: list[str] | None = None,
    api_url: str = "",
    verbose: bool = True,
) -> AgentRegistration:
    """Send a heartbeat for an already-registered agent."""
    from asiai import __version__

    base = api_url or get_api_url()
    result = AgentRegistration(success=False, agent_id=agent_id)

    payload = {
        "engines": engines or [],
        "version": __version__,
        "models_loaded": 0,
    }

    if verbose:
        logger.info("Sending heartbeat for agent %s", agent_id)

    try:
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            f"{base}/agent-heartbeat",
            data=data,
            headers={
                "Content-Type": "application/json",
                "X-Agent-Id": agent_id,
                "X-Agent-Token": agent_token,
            },
            method="POST",
        )
        with urlopen(req, timeout=_REGISTER_TIMEOUT) as resp:
            resp.read(_MAX_RESPONSE_BYTES)
            result.success = True

            # Reload total from agent.json
            existing = _load_agent_json()
            result.total_agents = existing.get("total_agents", 0)

    except HTTPError as exc:
        if exc.code == 403:
            # Token invalid — re-register next time
            logger.warning("Agent token invalid, removing agent.json for re-registration")
            try:
                os.remove(_AGENT_JSON)
            except OSError:
                pass
            result.error = "Token expired, will re-register next time"
        elif exc.code == 429:
            # Rate limited — still counts as OK
            result.success = True
            existing = _load_agent_json()
            result.total_agents = existing.get("total_agents", 0)
            logger.debug("Heartbeat rate-limited (OK)")
        else:
            result.error = f"HTTP {exc.code}"
            logger.warning("Agent heartbeat HTTP error %d", exc.code)
    except (URLError, OSError) as exc:
        result.error = str(exc)
        logger.warning("Agent heartbeat failed: %s", exc)

    return result


def unregister_agent() -> bool:
    """Remove local agent credentials. Returns True if file was removed."""
    try:
        os.remove(_AGENT_JSON)
        logger.info("Agent credentials removed")
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        logger.warning("Failed to remove agent.json: %s", exc)
        return False


def get_agent_info() -> dict:
    """Return current agent registration info, or empty dict if not registered."""
    return _load_agent_json()


def fetch_agent_count(api_url: str = "") -> dict:
    """Fetch agent count from community API.

    Returns:
        Dict with ``registered``, ``active_24h``, ``active_7d`` keys, or empty dict.
    """
    url = f"{api_url or get_api_url()}/agent-count"
    data = _safe_get(url)
    return data if isinstance(data, dict) else {}


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
