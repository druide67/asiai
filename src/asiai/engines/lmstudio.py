"""LM Studio inference engine adapter."""

from __future__ import annotations

import logging

from asiai.engines.base import InferenceEngine, ModelInfo
from asiai.engines.detect import http_get_json

logger = logging.getLogger("asiai.engines.lmstudio")


class LMStudioEngine(InferenceEngine):
    """Adapter for LM Studio inference server (OpenAI-compatible API).

    LM Studio exposes /v1/models and optionally /lms/version.
    """

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
        if data and "version" in data:
            return data["version"]
        return ""

    def is_reachable(self) -> bool:
        data, _ = http_get_json(f"{self.base_url}/v1/models")
        return data is not None

    def list_running(self) -> list[ModelInfo]:
        data, _ = http_get_json(f"{self.base_url}/v1/models")
        if data is None:
            return []
        models = []
        for m in data.get("data", []):
            models.append(ModelInfo(
                name=m.get("id", "unknown"),
                format="MLX",
            ))
        return models

    def list_available(self) -> list[ModelInfo]:
        # LM Studio API does not expose available (downloaded) models
        return []
