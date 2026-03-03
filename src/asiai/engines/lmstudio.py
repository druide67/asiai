"""LM Studio inference engine adapter."""

from __future__ import annotations

import logging
import subprocess

from asiai.engines.detect import http_get_json
from asiai.engines.openai_compat import OpenAICompatEngine

_APP_PLIST = "/Applications/LM Studio.app/Contents/Info.plist"

logger = logging.getLogger("asiai.engines.lmstudio")


class LMStudioEngine(OpenAICompatEngine):
    """Adapter for LM Studio inference server (OpenAI-compatible API).

    LM Studio uses /v1/completions (text mode) instead of chat completions.
    """

    _generate_endpoint = "/v1/completions"
    _generate_mode = "completions"
    _model_format = "MLX"

    @property
    def name(self) -> str:
        return "lmstudio"

    def version(self) -> str:
        # Check header first
        _, headers = http_get_json(f"{self.base_url}/v1/models")
        version = headers.get("x-lm-studio-version", "")
        if version:
            return version
        # Fallback: /lms/version endpoint
        data, _ = http_get_json(f"{self.base_url}/lms/version")
        if data and isinstance(data, dict) and "version" in data:
            return data["version"]
        # Fallback: read version from app bundle plist
        try:
            out = subprocess.run(
                ["/usr/libexec/PlistBuddy", "-c", "Print :CFBundleShortVersionString", _APP_PLIST],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip().split("+")[0]
        except Exception:
            pass
        return ""
