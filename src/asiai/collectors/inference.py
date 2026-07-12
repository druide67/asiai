"""Inference activity detection via TCP connections and metrics scraping.

Passive detection — no requests sent to the inference engine.
Uses ``lsof`` to count established TCP connections on engine ports.
"""

from __future__ import annotations

import logging
import re
import subprocess

logger = logging.getLogger("asiai.collectors.inference")


def count_tcp_connections(port: int) -> int:
    """Count established TCP connections on a given port via lsof.

    Args:
        port: TCP port number to inspect.

    Returns:
        Number of ESTABLISHED connections, or 0 on failure.
    """
    if port <= 0:
        return 0
    try:
        out = subprocess.run(
            ["lsof", "-i", f":{port}", "-sTCP:ESTABLISHED", "-nP"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode != 0 or not out.stdout:
            return 0
        # lsof lists BOTH endpoints of a loopback connection (client and
        # server socket), so counting raw lines double-counts local clients.
        # Keep only the server side: lines whose LOCAL address is :PORT
        # (i.e. ":PORT->" before the arrow).
        lines = out.stdout.strip().splitlines()[1:]  # drop header
        server_side = [ln for ln in lines if f":{port}->" in ln]
        # Remote (non-loopback) connections only ever show the server side,
        # so this filter is exact for them too.
        return len(server_side)
    except Exception as e:
        logger.debug("lsof TCP count on port %d failed: %s", port, e)
        return 0


def scrape_slots_kv(base_url: str, headers: dict[str, str] | None = None) -> dict:
    """KV-cache occupancy via ``GET /slots`` (llama.cpp).

    Modern llama.cpp removed the KV gauges from ``/metrics`` (KV-cache
    refactor); ``/slots`` is the only live source. Each slot reports
    ``n_ctx`` (its capacity) and ``n_prompt_tokens`` — the tokens held in
    the slot's KV (prompt + decoded, validated on b9430 by the bench
    KVCacheSampler). Idle slots keep their hot cache for prefix reuse, so
    summing over ALL slots reads the real occupancy, not just in-flight work.

    Privacy guard: the ``/slots`` body can carry prompt fragments. Only
    numbers leave this function — the response text is never stored,
    logged, or returned.

    Best-effort: any failure (endpoint absent — MLX/ollama —, disabled
    build, network, malformed JSON) returns ``{}``.

    Returns:
        ``{kv_cache_usage_ratio: float 0..1, kv_cache_tokens: int}`` or ``{}``.
    """
    import json
    from urllib.error import URLError
    from urllib.request import Request, urlopen

    if not base_url or not base_url.startswith(("http://", "https://")):
        return {}
    url = base_url.rstrip("/") + "/slots"
    try:
        with urlopen(Request(url, headers=headers or {}), timeout=2) as resp:
            # Large cap: a 256K-context slot's JSON (prompt text included)
            # runs to megabytes; truncated JSON would parse-fail to {}.
            slots = json.loads(resp.read(8 * 1024 * 1024).decode("utf-8", errors="replace"))
    except (URLError, OSError, ValueError) as e:
        logger.debug("Failed to scrape %s: %s", url, e)
        return {}
    if not isinstance(slots, list):
        return {}
    used = 0
    capacity = 0
    for s in slots:
        if not isinstance(s, dict):
            continue
        n_ctx = s.get("n_ctx")
        if isinstance(n_ctx, int) and n_ctx > 0:
            capacity += n_ctx
        n = s.get("n_prompt_tokens")
        if isinstance(n, int) and n > 0:
            used += n
    if capacity <= 0:
        return {}
    return {
        "kv_cache_usage_ratio": min(1.0, used / capacity),
        "kv_cache_tokens": used,
    }


def scrape_prometheus_metrics(url: str, headers: dict[str, str] | None = None) -> dict:
    """Scrape a Prometheus /metrics endpoint and extract key gauges.

    Parses simple Prometheus text format with regex. Returns a dict with
    recognized metrics, or {} on failure.

    Recognized metrics (llama.cpp):
        - llamacpp_requests_processing -> requests_processing
        - llamacpp_tokens_predicted_total -> tokens_predicted_total
        - llamacpp_kv_cache_usage_ratio -> kv_cache_usage_ratio

    Recognized metrics (vllm-mlx):
        - vllm_num_requests_running -> requests_processing
        - vllm_generation_tokens_total -> tokens_predicted_total

    Args:
        url: Full URL to the /metrics endpoint.

    Returns:
        Dict of extracted metric values, or {} on failure.
    """
    from urllib.error import URLError
    from urllib.request import Request, urlopen

    try:
        with urlopen(Request(url, headers=headers or {}), timeout=3) as resp:
            text = resp.read(512 * 1024).decode("utf-8", errors="replace")
    except (URLError, OSError, ValueError) as e:
        logger.debug("Failed to scrape %s: %s", url, e)
        return {}

    return parse_prometheus_text(text)


def parse_prometheus_text(text: str) -> dict:
    """Parse Prometheus exposition text and extract known inference metrics.

    Args:
        text: Raw Prometheus text format content.

    Returns:
        Dict with normalized metric names.
    """
    result: dict = {}

    # Mapping: prometheus_metric_name -> (output_key, type)
    mappings = {
        "llamacpp_requests_processing": ("requests_processing", int),
        "llamacpp_tokens_predicted_total": ("tokens_predicted_total", int),
        "llamacpp_kv_cache_usage_ratio": ("kv_cache_usage_ratio", float),
        "vllm_num_requests_running": ("requests_processing", int),
        "vllm_generation_tokens_total": ("tokens_predicted_total", int),
        # TurboQuant KV cache metrics (llama.cpp fork)
        "llamacpp_kv_cache_tokens_count": ("kv_cache_tokens", int),
        "llamacpp_kv_cache_compressed_bytes": ("kv_cache_compressed_bytes", int),
        "llamacpp_kv_cache_original_bytes": ("kv_cache_original_bytes", int),
    }

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Match: metric_name{labels} value  or  metric_name value.
        # Prometheus metric names may carry a namespace COLON —
        # llama.cpp exposes ``llamacpp:tokens_predicted_total`` — which
        # ``\w`` does not match: the old pattern silently truncated the
        # name to "llamacpp" and every activity metric read as zero.
        m = re.match(r"^([\w:]+)(?:\{[^}]*\})?\s+([\d.eE+-]+)", line)
        if not m:
            continue

        # Normalize the namespace separator so both exposition styles
        # (``llamacpp:foo`` current, ``llamacpp_foo`` legacy) hit the map.
        metric_name = m.group(1).replace(":", "_")
        if metric_name in mappings:
            key, typ = mappings[metric_name]
            try:
                value = typ(float(m.group(2)))
                # Don't overwrite if already set (first match wins)
                if key not in result:
                    result[key] = value
            except (ValueError, OverflowError):
                pass

    return result
