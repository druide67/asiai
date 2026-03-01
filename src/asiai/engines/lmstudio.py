"""LM Studio inference engine adapter."""

from __future__ import annotations

import logging
import subprocess
import time

from asiai.engines.base import GenerateResult, InferenceEngine, ModelInfo
from asiai.engines.detect import http_get_json, http_post_json

_APP_PLIST = "/Applications/LM Studio.app/Contents/Info.plist"

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
        if data and isinstance(data, dict) and "version" in data:
            return data["version"]
        # Fallback: read version from app bundle plist
        try:
            out = subprocess.run(
                ["/usr/libexec/PlistBuddy", "-c",
                 "Print :CFBundleShortVersionString", _APP_PLIST],
                capture_output=True, text=True, timeout=5,
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip().split("+")[0]
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
        # LM Studio API does not expose available (downloaded) models
        return []

    def generate(self, model: str, prompt: str, max_tokens: int = 512) -> GenerateResult:
        """Generate text using LM Studio /v1/completions endpoint."""
        t0 = time.monotonic()
        data, _ = http_post_json(
            f"{self.base_url}/v1/completions",
            {
                "model": model,
                "prompt": prompt,
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
        text = choices[0].get("text", "") if choices else ""
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
