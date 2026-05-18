"""vMLX inference engine adapter.

vMLX (https://vmlx.net) is a high-performance MLX-based inference server
with first-class Mamba/SSM hybrid architecture support (DeltaNet, Mamba2,
RetNet). It exposes an OpenAI-compatible API and a /version endpoint
identifying itself as "vmlx". Default port is 8000.

Install: pip install vmlx
Run:     vmlx serve --model <repo-id-or-path> [--port 8000]
"""

from __future__ import annotations

import logging
import subprocess

from asiai.engines.detect import http_get_json
from asiai.engines.openai_compat import OpenAICompatEngine

logger = logging.getLogger("asiai.engines.vmlx")


class VmlxEngine(OpenAICompatEngine):
    """Adapter for vMLX inference server (OpenAI-compatible + /version)."""

    _generate_endpoint = "/v1/chat/completions"
    _generate_mode = "chat"
    _model_format = "MLX"

    @property
    def name(self) -> str:
        return "vmlx"

    def version(self) -> str:
        """Return vMLX version via /version endpoint, fallback to `pip show vmlx`."""
        data, _ = http_get_json(f"{self.base_url}/version")
        if data and isinstance(data, dict) and "version" in data:
            return data["version"]
        try:
            out = subprocess.run(
                ["pip", "show", "vmlx"],
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout
            for line in out.splitlines():
                if line.lower().startswith("version:"):
                    return line.split(":", 1)[1].strip()
        except Exception as e:
            logger.debug("pip show vmlx failed: %s", e)
        return ""

    def scrape_metrics(self) -> dict:
        """Scrape vMLX /metrics for inference activity."""
        from asiai.collectors.inference import scrape_prometheus_metrics

        return scrape_prometheus_metrics(f"{self.base_url}/metrics")
