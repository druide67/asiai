"""Ollama inference engine adapter."""

from __future__ import annotations

import logging

from asiai.engines.base import EngineStatus, InferenceEngine, ModelInfo
from asiai.engines.detect import http_get_json

logger = logging.getLogger("asiai.engines.ollama")


class OllamaEngine(InferenceEngine):
    """Adapter for Ollama inference server.

    API docs: https://github.com/ollama/ollama/blob/main/docs/api.md
    """

    @property
    def name(self) -> str:
        return "ollama"

    def version(self) -> str:
        data, _ = http_get_json(f"{self.base_url}/api/version")
        if data and "version" in data:
            return data["version"]
        return ""

    def is_reachable(self) -> bool:
        data, _ = http_get_json(f"{self.base_url}/api/version")
        return data is not None

    def list_running(self) -> list[ModelInfo]:
        data, _ = http_get_json(f"{self.base_url}/api/ps")
        if data is None:
            return []
        models = []
        for m in data.get("models", []):
            models.append(ModelInfo(
                name=m.get("name", "unknown"),
                size_vram=m.get("size_vram", 0),
                size_total=m.get("size", 0),
                format=m.get("details", {}).get("format", ""),
                quantization=m.get("details", {}).get("quantization_level", ""),
            ))
        return models

    def list_available(self) -> list[ModelInfo]:
        data, _ = http_get_json(f"{self.base_url}/api/tags")
        if data is None:
            return []
        models = []
        for m in data.get("models", []):
            models.append(ModelInfo(
                name=m.get("name", "unknown"),
                size_total=m.get("size", 0),
            ))
        return models
