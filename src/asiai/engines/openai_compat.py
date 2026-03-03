"""Base class for OpenAI-compatible inference engine adapters.

Shared by LM Studio, mlx-lm, llama.cpp, and vllm-mlx.
"""

from __future__ import annotations

import logging
import time

from asiai.engines.base import GenerateResult, InferenceEngine, ModelInfo
from asiai.engines.detect import http_get_json, http_post_json

logger = logging.getLogger("asiai.engines.openai_compat")


class OpenAICompatEngine(InferenceEngine):
    """Template method base for engines exposing an OpenAI-compatible API.

    Subclasses set class-level attributes to customize behavior:
        _generate_endpoint: API path for generation (default: /v1/chat/completions)
        _generate_mode: "chat" or "completions" (default: "chat")
        _model_format: Format label for models (e.g. "MLX", "GGUF")
    """

    _generate_endpoint: str = "/v1/chat/completions"
    _generate_mode: str = "chat"
    _model_format: str = ""

    def is_reachable(self) -> bool:
        data, _ = http_get_json(f"{self.base_url}/v1/models")
        return data is not None

    def list_running(self) -> list[ModelInfo]:
        data, _ = http_get_json(f"{self.base_url}/v1/models")
        if data is None:
            return []
        models = []
        for m in data.get("data", []):
            models.append(
                ModelInfo(
                    name=m.get("id", "unknown"),
                    format=self._model_format,
                )
            )
        return models

    def list_available(self) -> list[ModelInfo]:
        return []

    def generate(self, model: str, prompt: str, max_tokens: int = 512) -> GenerateResult:
        """Generate text via OpenAI-compatible API."""
        t0 = time.monotonic()

        if self._generate_mode == "chat":
            payload: dict = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "stream": False,
                "temperature": 0.0,
            }
        else:
            payload = {
                "model": model,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "stream": False,
                "temperature": 0.0,
            }

        data, _ = http_post_json(
            f"{self.base_url}{self._generate_endpoint}",
            payload,
            timeout=300,
        )
        elapsed_s = time.monotonic() - t0

        if data is None:
            return GenerateResult(engine=self.name, model=model, error="request failed")

        if "error" in data:
            msg = data["error"]
            if isinstance(msg, dict):
                msg = msg.get("message", str(msg))
            return GenerateResult(engine=self.name, model=model, error=str(msg))

        choices = data.get("choices", [])
        text = ""
        if choices:
            if self._generate_mode == "chat":
                message = choices[0].get("message", {})
                text = message.get("content", "")
            else:
                text = choices[0].get("text", "")

        usage = data.get("usage", {})
        completion_tokens = usage.get("completion_tokens", 0)

        tok_s = (completion_tokens / elapsed_s) if elapsed_s > 0 else 0.0

        return GenerateResult(
            text=text,
            tokens_generated=completion_tokens,
            tok_per_sec=round(tok_s, 2),
            ttft_ms=0.0,
            total_duration_ms=round(elapsed_s * 1000, 1),
            prompt_eval_duration_ms=0.0,
            model=model,
            engine=self.name,
        )
