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
        # lsof output has a header line; each subsequent line is a connection
        lines = out.stdout.strip().splitlines()
        return max(0, len(lines) - 1)
    except Exception as e:
        logger.debug("lsof TCP count on port %d failed: %s", port, e)
        return 0


def scrape_prometheus_metrics(url: str) -> dict:
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
    from urllib.request import urlopen

    try:
        with urlopen(url, timeout=3) as resp:
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
    }

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Match: metric_name{labels} value  or  metric_name value
        m = re.match(r"^(\w+)(?:\{[^}]*\})?\s+([\d.eE+-]+)", line)
        if not m:
            continue

        metric_name = m.group(1)
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
