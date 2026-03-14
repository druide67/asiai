"""Engine auto-detection from a URL."""

from __future__ import annotations

import json
import logging
import subprocess
from urllib.error import URLError
from urllib.request import Request, urlopen

_LMSTUDIO_APP_PLIST = "/Applications/LM Studio.app/Contents/Info.plist"

logger = logging.getLogger("asiai.engines.detect")

# Map process command names to engine identifiers.
# Max response body size (10 MB) to prevent memory exhaustion from rogue servers.
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024

# Map process command names to engine identifiers.
_PORT_PROCESS_MAP: dict[str, str] = {
    "mlx_lm": "mlxlm",
    "llama-server": "llamacpp",
    "llama_server": "llamacpp",
    "omlx": "omlx",
    "vllm": "vllm_mlx",
    "exo": "exo",
}

# Default ports to scan when no explicit URL is given.
DEFAULT_URLS = [
    "http://localhost:11434",  # Ollama default
    "http://localhost:1234",  # LM Studio default
    "http://localhost:8080",  # mlx-lm / llama.cpp default
    "http://localhost:8000",  # oMLX / vllm-mlx default
    "http://localhost:52415",  # Exo default
]


def http_get_json(url: str, timeout: int = 5) -> tuple[dict | None, dict[str, str]]:
    """Generic HTTP GET returning parsed JSON and lowercase headers.

    Returns (None, {}) on any failure.
    """
    try:
        req = Request(url)
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_RESPONSE_BYTES:
                logger.warning("Response from %s exceeded %d bytes", url, _MAX_RESPONSE_BYTES)
                return None, {}
            data = json.loads(raw.decode())
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return data, headers
    except (URLError, OSError, ValueError, json.JSONDecodeError) as e:
        logger.debug("http_get_json %s failed: %s", url, e)
        return None, {}


def http_post_json(
    url: str,
    data: dict,
    timeout: int = 300,
) -> tuple[dict | None, dict[str, str]]:
    """HTTP POST with JSON body, returning parsed JSON and lowercase headers.

    Returns (None, {}) on any failure. On error, returns a dict with an
    "error" key describing the failure if possible.
    """
    try:
        body = json.dumps(data).encode()
        req = Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_RESPONSE_BYTES:
                logger.warning("Response from %s exceeded %d bytes", url, _MAX_RESPONSE_BYTES)
                return None, {}
            parsed = json.loads(raw.decode())
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return parsed, headers
    except TimeoutError:
        return {"error": "request timed out"}, {}
    except ConnectionRefusedError:
        return {"error": "connection refused"}, {}
    except URLError as e:
        reason = str(e.reason) if hasattr(e, "reason") else str(e)
        return {"error": f"connection error: {reason}"}, {}
    except (OSError, ValueError, json.JSONDecodeError) as e:
        logger.debug("http_post_json %s failed: %s", url, e)
        return None, {}


def _lmstudio_version_from_app() -> str:
    """Read LM Studio version from the macOS app bundle plist."""
    try:
        out = subprocess.run(
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleShortVersionString",
                _LMSTUDIO_APP_PLIST,
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip().split("+")[0]
    except Exception as e:
        logger.debug("Failed to read LM Studio plist: %s", e)
    return ""


def detect_port_process(port: int) -> str:
    """Identify engine process listening on port via lsof.

    Returns engine name string (e.g. "mlxlm", "llamacpp") or empty string.
    """
    try:
        out = subprocess.run(
            ["lsof", "-i", f":{port}", "-sTCP:LISTEN", "-Fn"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except Exception as e:
        logger.debug("lsof port %d failed: %s", port, e)
        return ""

    for line in out.splitlines():
        if line.startswith("c"):
            cmd = line[1:]  # strip "c" prefix
            for pattern, engine_name in _PORT_PROCESS_MAP.items():
                if pattern in cmd:
                    return engine_name
    return ""


def extract_port(base_url: str) -> int:
    """Extract port number from a base URL."""
    try:
        # "http://localhost:8080" -> "8080"
        host_port = base_url.split("//", 1)[-1].rstrip("/")
        if ":" in host_port:
            return int(host_port.rsplit(":", 1)[-1])
    except (ValueError, IndexError):
        pass
    return 0


def detect_engine_type(base_url: str) -> tuple[str, str]:
    """Detect which engine is running at the given URL.

    Detection cascade:
      1. GET /api/version          -> Ollama (unique endpoint)
      2. GET /v1/models responds?
         2a. x-lm-studio-version header or /lms/version -> LM Studio
         2b. GET /health {"status":"ok"} + /props       -> llama.cpp
         2c. GET /admin/info or /admin page              -> oMLX
         2d. GET /version or owned_by:"vllm-mlx"       -> vllm-mlx
         2e. detect_port_process(port)                  -> lsof result
         2f. fallback                                   -> mlx-lm
      3. Otherwise -> "unknown"
    """
    base_url = base_url.rstrip("/")

    # 1. Ollama: unique /api/version endpoint
    data, _ = http_get_json(f"{base_url}/api/version")
    if data and "version" in data:
        return "ollama", data["version"]

    # 2. OpenAI-compatible: /v1/models
    data, headers = http_get_json(f"{base_url}/v1/models")
    if data is not None:
        # 2a. LM Studio signatures
        version = headers.get("x-lm-studio-version", "")
        if version:
            return "lmstudio", version
        ver_data, _ = http_get_json(f"{base_url}/lms/version")
        if ver_data and isinstance(ver_data, dict):
            if "version" in ver_data:
                return "lmstudio", ver_data["version"]
            if "error" in ver_data:
                return "lmstudio", _lmstudio_version_from_app()

        # 2b. llama.cpp: /health {"status":"ok"} AND /props must respond
        health_data, _ = http_get_json(f"{base_url}/health")
        if health_data and isinstance(health_data, dict):
            if health_data.get("status") == "ok":
                props_data, _ = http_get_json(f"{base_url}/props")
                if props_data and isinstance(props_data, dict):
                    ver = ""
                    build_info = props_data.get("build_info", "")
                    if isinstance(build_info, str) and build_info:
                        # "b8180-d979f2b17" -> "8180"
                        ver = build_info.lstrip("b").split("-")[0]
                    elif isinstance(build_info, dict):
                        ver = build_info.get("version", "")
                    return "llamacpp", ver

        # 2c. oMLX: /admin endpoint (unique to oMLX)
        admin_data, _ = http_get_json(f"{base_url}/admin/info")
        if admin_data and isinstance(admin_data, dict):
            ver = admin_data.get("version", "")
            return "omlx", ver
        # Also detect via oMLX admin HTML page (returns non-JSON)
        try:
            from urllib.request import urlopen as _urlopen

            with _urlopen(f"{base_url}/admin", timeout=3) as resp:
                body = resp.read(1024).decode(errors="ignore")
                if "omlx" in body.lower() or "oMLX" in body:
                    return "omlx", ""
        except Exception:
            pass

        # 2d. vllm-mlx: /version endpoint OR "owned_by":"vllm-mlx" in /v1/models
        ver_resp, _ = http_get_json(f"{base_url}/version")
        if ver_resp and isinstance(ver_resp, dict) and "version" in ver_resp:
            return "vllm_mlx", ver_resp["version"]
        # Check owned_by field in /v1/models response
        if isinstance(data, dict):
            for model_entry in data.get("data", []):
                if isinstance(model_entry, dict) and model_entry.get("owned_by") == "vllm-mlx":
                    return "vllm_mlx", ""

        # 2d. Process detection via lsof
        port = extract_port(base_url)
        if port:
            process_engine = detect_port_process(port)
            if process_engine:
                return process_engine, ""

        # 2e. Fallback: mlx-lm
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
