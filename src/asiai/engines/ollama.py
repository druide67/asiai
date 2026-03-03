"""Ollama inference engine adapter."""

from __future__ import annotations

import logging

from asiai.engines.base import GenerateResult, InferenceEngine, ModelInfo
from asiai.engines.detect import http_get_json, http_post_json

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
            models.append(
                ModelInfo(
                    name=m.get("name", "unknown"),
                    size_vram=m.get("size_vram", 0),
                    size_total=m.get("size", 0),
                    format=m.get("details", {}).get("format", ""),
                    quantization=m.get("details", {}).get("quantization_level", ""),
                )
            )
        return models

    def list_available(self) -> list[ModelInfo]:
        data, _ = http_get_json(f"{self.base_url}/api/tags")
        if data is None:
            return []
        models = []
        for m in data.get("models", []):
            models.append(
                ModelInfo(
                    name=m.get("name", "unknown"),
                    size_total=m.get("size", 0),
                )
            )
        return models

    def measure_load_time(self, model: str) -> float:
        """Measure model load time via a minimal /api/generate call.

        Returns load_duration in milliseconds from Ollama's response.
        """
        data, _ = http_post_json(
            f"{self.base_url}/api/generate",
            {
                "model": model,
                "prompt": "",
                "stream": False,
                "options": {"num_predict": 1},
            },
            timeout=120,
        )
        if data and "load_duration" in data:
            return round(data["load_duration"] / 1e6, 1)  # ns -> ms
        return 0.0

    def generate(self, model: str, prompt: str, max_tokens: int = 512) -> GenerateResult:
        """Generate text using Ollama /api/generate endpoint."""
        data, _ = http_post_json(
            f"{self.base_url}/api/generate",
            {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
            timeout=300,
        )
        if data is None:
            return GenerateResult(engine=self.name, model=model, error="request failed")

        if "error" in data:
            return GenerateResult(engine=self.name, model=model, error=data["error"])

        eval_count = data.get("eval_count", 0)
        eval_duration_ns = data.get("eval_duration", 0)
        prompt_eval_ns = data.get("prompt_eval_duration", 0)
        total_ns = data.get("total_duration", 0)

        tok_s = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns > 0 else 0.0

        return GenerateResult(
            text=data.get("response", ""),
            tokens_generated=eval_count,
            tok_per_sec=round(tok_s, 2),
            ttft_ms=round(prompt_eval_ns / 1e6, 1),
            total_duration_ms=round(total_ns / 1e6, 1),
            prompt_eval_duration_ms=round(prompt_eval_ns / 1e6, 1),
            model=model,
            engine=self.name,
        )
