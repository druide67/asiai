"""Exo distributed inference engine adapter.

Exo (exo-explore/exo) enables distributed inference across Apple Silicon
devices using MLX. It exposes an OpenAI-compatible API on port 52415 by default.
"""

from __future__ import annotations

import logging
import subprocess

from asiai.engines.detect import http_get_json
from asiai.engines.openai_compat import OpenAICompatEngine

logger = logging.getLogger("asiai.engines.exo")


class ExoEngine(OpenAICompatEngine):
    """Adapter for Exo distributed inference (OpenAI-compatible)."""

    _generate_endpoint = "/v1/chat/completions"
    _generate_mode = "chat"
    _model_format = "MLX"

    @property
    def name(self) -> str:
        return "exo"

    def version(self) -> str:
        """Return Exo version via API or CLI fallback."""
        # Try API endpoint first
        data, _ = http_get_json(f"{self.base_url}/api/version")
        if data and isinstance(data, dict) and "version" in data:
            return data["version"]
        # Fallback: exo --version
        try:
            out = subprocess.run(
                ["exo", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            text = (out.stdout or out.stderr).strip()
            if text:
                # Handle "exo 0.1.0" or plain "0.1.0"
                parts = text.split()
                return parts[-1] if parts else text
        except Exception:
            pass
        return ""

    def list_running(self) -> list:
        """List running models, enriched with cluster topology if available."""
        models = super().list_running()
        # Try to get cluster/topology info from Exo API
        data, _ = http_get_json(f"{self.base_url}/api/topology")
        if data and isinstance(data, dict):
            nodes = data.get("nodes", [])
            if isinstance(nodes, list) and len(nodes) > 1:
                logger.info("Exo cluster: %d nodes", len(nodes))
        return models
