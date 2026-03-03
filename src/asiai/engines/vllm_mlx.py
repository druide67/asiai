"""vllm-mlx inference engine adapter.

vllm-mlx brings vLLM's continuous batching to Apple Silicon via MLX.
It exposes an OpenAI-compatible API on port 8000 by default, plus /version.
"""

from __future__ import annotations

import logging

from asiai.engines.detect import http_get_json
from asiai.engines.openai_compat import OpenAICompatEngine

logger = logging.getLogger("asiai.engines.vllm_mlx")


class VllmMlxEngine(OpenAICompatEngine):
    """Adapter for vllm-mlx (OpenAI-compatible + /version)."""

    _generate_endpoint = "/v1/chat/completions"
    _generate_mode = "chat"
    _model_format = "MLX"

    @property
    def name(self) -> str:
        return "vllm_mlx"

    def version(self) -> str:
        """Return vllm-mlx version via /version endpoint."""
        data, _ = http_get_json(f"{self.base_url}/version")
        if data and isinstance(data, dict) and "version" in data:
            return data["version"]
        return ""
