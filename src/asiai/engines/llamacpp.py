"""llama.cpp server inference engine adapter.

llama.cpp server (``llama-server``) is installable via ``brew install llama.cpp``.
It exposes an OpenAI-compatible API on port 8080 by default, plus /health and /props.
"""

from __future__ import annotations

import logging
import subprocess

from asiai.engines.detect import http_get_json
from asiai.engines.openai_compat import OpenAICompatEngine

logger = logging.getLogger("asiai.engines.llamacpp")


class LlamaCppEngine(OpenAICompatEngine):
    """Adapter for llama.cpp server (OpenAI-compatible + /health, /props)."""

    _generate_endpoint = "/v1/chat/completions"
    _generate_mode = "chat"
    _model_format = "GGUF"

    @property
    def name(self) -> str:
        return "llamacpp"

    def version(self) -> str:
        """Return llama.cpp version via /props or brew."""
        # Try /props endpoint first (has build_info)
        data, _ = http_get_json(f"{self.base_url}/props")
        if data and isinstance(data, dict):
            build_info = data.get("build_info", {})
            if isinstance(build_info, dict) and "version" in build_info:
                return build_info["version"]
        # Fallback: brew
        try:
            out = subprocess.run(
                ["brew", "list", "--versions", "llama.cpp"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
            if out:
                parts = out.split()
                if len(parts) >= 2:
                    return parts[-1]
        except Exception:
            pass
        return ""

    def is_reachable(self) -> bool:
        """Check /health endpoint (unique to llama.cpp)."""
        data, _ = http_get_json(f"{self.base_url}/health")
        if data and isinstance(data, dict):
            return data.get("status") == "ok"
        return False

    def list_running(self) -> list:
        """List running models, enriched with context_length from /props."""
        models = super().list_running()
        # Enrich with context length from /props
        ctx_len = 0
        data, _ = http_get_json(f"{self.base_url}/props")
        if data and isinstance(data, dict):
            gen_settings = data.get("default_generation_settings", {})
            if isinstance(gen_settings, dict):
                ctx_len = gen_settings.get("n_ctx", 0)
        if ctx_len > 0:
            for m in models:
                m.context_length = ctx_len
        return models
