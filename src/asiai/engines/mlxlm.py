"""mlx-lm inference engine adapter.

mlx-lm is Apple's native MLX-based inference server, installable via
``brew install mlx-lm``.  It exposes an OpenAI-compatible API on port 8080.
"""

from __future__ import annotations

import logging
import subprocess
import time

from asiai.engines.base import GenerateResult, InferenceEngine, ModelInfo
from asiai.engines.detect import http_get_json, http_post_json

logger = logging.getLogger("asiai.engines.mlxlm")


class MlxLmEngine(InferenceEngine):
    """Adapter for mlx-lm inference server (OpenAI-compatible API on port 8080)."""

    @property
    def name(self) -> str:
        return "mlxlm"

    def version(self) -> str:
        """Return mlx-lm version via ``brew list --versions mlx-lm``."""
        try:
            out = subprocess.run(
                ["brew", "list", "--versions", "mlx-lm"],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip()
            # Output: "mlx-lm 0.30.7" or empty if not installed
            if out:
                parts = out.split()
                if len(parts) >= 2:
                    return parts[-1]
        except Exception:
            pass
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
        return []

    def generate(self, model: str, prompt: str, max_tokens: int = 512) -> GenerateResult:
        """Generate text using mlx-lm /v1/chat/completions endpoint."""
        t0 = time.monotonic()
        data, _ = http_post_json(
            f"{self.base_url}/v1/chat/completions",
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "stream": False,
                "temperature": 0.0,
            },
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
            message = choices[0].get("message", {})
            text = message.get("content", "")

        usage = data.get("usage", {})
        completion_tokens = usage.get("completion_tokens", 0)

        tok_s = (completion_tokens / elapsed_s) if elapsed_s > 0 else 0.0

        return GenerateResult(
            text=text,
            tokens_generated=completion_tokens,
            tok_per_sec=round(tok_s, 2),
            ttft_ms=0.0,  # Not available in non-streaming mode
            total_duration_ms=round(elapsed_s * 1000, 1),
            prompt_eval_duration_ms=0.0,
            model=model,
            engine=self.name,
        )
