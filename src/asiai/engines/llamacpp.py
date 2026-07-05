"""llama.cpp server inference engine adapter.

llama.cpp server (``llama-server``) is installable via ``brew install llama.cpp``.
It exposes an OpenAI-compatible API on port 8080 by default, plus /health and /props.
"""

from __future__ import annotations

import logging
import os
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
        """List running models, enriched with context_length from /props.

        Preset-managed instances load a stable symlink (``active.gguf``)
        and the API reports that alias, which tells an operator nothing —
        resolve it to the real model filename when possible.
        """
        models = super().list_running()
        ctx_len = 0
        alias = ""
        resolved = ""
        data, _ = http_get_json(f"{self.base_url}/props")
        if data and isinstance(data, dict):
            gen_settings = data.get("default_generation_settings", {})
            if isinstance(gen_settings, dict):
                ctx_len = gen_settings.get("n_ctx", 0)
            alias, resolved = self._resolve_model_symlink(data.get("model_path"))
        for m in models:
            if ctx_len > 0:
                m.context_length = ctx_len
            # Only rewrite the DEFAULT alias (the file's own basename): a
            # custom --alias is an operator choice and must stay untouched.
            if resolved and m.name == alias:
                m.name = resolved
        return models

    @staticmethod
    def _resolve_model_symlink(model_path: object) -> tuple[str, str]:
        """``(default_alias, real_filename)`` behind a model-path symlink.

        The collector runs on the same host as a locally-detected engine,
        so resolving the path is legitimate; for a remote ``--url`` engine
        the path does not exist locally and both values stay empty (the
        reported name is kept). Never raises.
        """
        if not isinstance(model_path, str) or not model_path:
            return ("", "")
        try:
            if not os.path.islink(model_path):
                return ("", "")
            real_base = os.path.basename(os.path.realpath(model_path))
        except OSError:
            return ("", "")
        alias = os.path.basename(model_path)
        if not real_base or real_base == alias:
            return ("", "")
        return (alias, real_base)

    def scrape_metrics(self) -> dict:
        """Scrape llama.cpp /metrics for inference activity."""
        from asiai.collectors.inference import scrape_prometheus_metrics

        return scrape_prometheus_metrics(f"{self.base_url}/metrics")
