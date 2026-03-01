"""Engine auto-detection from a URL."""

from __future__ import annotations

import json
import logging
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger("asiai.engines.detect")

# Default ports to scan when no explicit URL is given.
DEFAULT_URLS = [
    "http://localhost:11434",  # Ollama default
    "http://localhost:1234",   # LM Studio default
    "http://localhost:8080",   # mlx-lm default
]


def http_get_json(url: str, timeout: int = 5) -> tuple[dict | None, dict[str, str]]:
    """Generic HTTP GET returning parsed JSON and lowercase headers.

    Returns (None, {}) on any failure.
    """
    try:
        req = Request(url)
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return data, headers
    except (URLError, OSError, ValueError, json.JSONDecodeError):
        return None, {}


def http_post_json(
    url: str,
    data: dict,
    timeout: int = 300,
) -> tuple[dict | None, dict[str, str]]:
    """HTTP POST with JSON body, returning parsed JSON and lowercase headers.

    Returns (None, {}) on any failure.
    """
    try:
        body = json.dumps(data).encode()
        req = Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            parsed = json.loads(raw)
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return parsed, headers
    except (URLError, OSError, ValueError, json.JSONDecodeError):
        return None, {}


def detect_engine_type(base_url: str) -> tuple[str, str]:
    """Detect which engine is running at the given URL.

    Returns (engine_name, version) where engine_name is
    'ollama', 'lmstudio', or 'unknown'.
    """
    base_url = base_url.rstrip("/")

    # Try Ollama: GET /api/version -> {"version": "0.17.4"}
    data, _ = http_get_json(f"{base_url}/api/version")
    if data and "version" in data:
        return "ollama", data["version"]

    # Try OpenAI-compatible: GET /v1/models (LM Studio or mlx-lm)
    data, headers = http_get_json(f"{base_url}/v1/models")
    if data is not None:
        # Check for LM Studio signatures first
        version = headers.get("x-lm-studio-version", "")
        if version:
            return "lmstudio", version
        ver_data, _ = http_get_json(f"{base_url}/lms/version")
        if ver_data and "version" in ver_data:
            return "lmstudio", ver_data["version"]
        # No LM Studio markers → mlx-lm (or other OpenAI-compatible server)
        return "mlxlm", ""

    return "unknown", ""


def detect_engines(
    urls: list[str] | None = None,
) -> list[tuple[str, str, str]]:
    """Scan URLs and return detected engines.

    Args:
        urls: URLs to scan. Defaults to DEFAULT_URLS.

    Returns:
        List of (base_url, engine_name, version) for each reachable engine.
    """
    if urls is None:
        urls = DEFAULT_URLS

    found: list[tuple[str, str, str]] = []
    for url in urls:
        engine, version = detect_engine_type(url)
        if engine != "unknown":
            found.append((url, engine, version))
            logger.info("Detected %s %s at %s", engine, version, url)
    return found
