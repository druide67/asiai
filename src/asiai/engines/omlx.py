"""oMLX inference engine adapter.

oMLX is a high-performance MLX-based inference server with SSD KV caching
and continuous batching. It exposes an OpenAI-compatible API on port 8000
and an admin dashboard at /admin.
"""

from __future__ import annotations

import logging

from asiai.engines.detect import http_get_json
from asiai.engines.openai_compat import OpenAICompatEngine

logger = logging.getLogger("asiai.engines.omlx")


class OmlxEngine(OpenAICompatEngine):
    """Adapter for oMLX inference server (OpenAI-compatible API on port 8000)."""

    _generate_endpoint = "/v1/chat/completions"
    _generate_mode = "chat"
    _model_format = "MLX"

    @property
    def name(self) -> str:
        return "omlx"

    def version(self) -> str:
        """Return oMLX version via /admin/info or fallback."""
        # Try /admin/info (oMLX-specific)
        data, _ = http_get_json(f"{self.base_url}/admin/info")
        if data and isinstance(data, dict) and "version" in data:
            return data["version"]
        return ""
