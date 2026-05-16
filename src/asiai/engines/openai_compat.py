"""Base class for OpenAI-compatible inference engine adapters.

Shared by LM Studio, mlx-lm, llama.cpp, and vllm-mlx.
"""

from __future__ import annotations

import json
import logging
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from asiai.engines.base import GenerateResult, InferenceEngine, ModelInfo
from asiai.engines.detect import http_get_json

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
        # Enrich with process footprint when engine doesn't report VRAM
        if models and all(m.size_vram == 0 for m in models):
            try:
                from asiai.collectors.system import collect_engine_processes

                procs = collect_engine_processes()
                engine_proc = next((p for p in procs if p.name == self.name), None)
                if engine_proc and engine_proc.rss_bytes > 0:
                    # Divide evenly if multiple models (rough estimate)
                    per_model = engine_proc.rss_bytes // len(models)
                    for m in models:
                        m.size_vram = per_model
            except Exception:
                pass
        return models

    def list_available(self) -> list[ModelInfo]:
        return []

    def generate(self, model: str, prompt: str, max_tokens: int = 512) -> GenerateResult:
        """Generate text via streaming OpenAI-compatible API (measures TTFT)."""
        t0 = time.monotonic()

        if self._generate_mode == "chat":
            payload: dict = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "stream": True,
                "temperature": 0.0,
            }
        else:
            payload = {
                "model": model,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "stream": True,
                "temperature": 0.0,
            }

        url = f"{self.base_url}{self._generate_endpoint}"
        ttft_ms = 0.0
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        completion_tokens = 0

        try:
            body = json.dumps(payload).encode()
            req = Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")

            with urlopen(req, timeout=300) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    if self._generate_mode == "chat":
                        delta = choices[0].get("delta", {}) or {}
                        content = delta.get("content") or ""
                        # Qwen3/3.5/3.6 thinking mode (Jinja chat template) emits
                        # reasoning tokens in delta.reasoning_content. Counted in
                        # throughput, excluded from `text` (clean user output).
                        reasoning = delta.get("reasoning_content") or ""
                    else:
                        content = choices[0].get("text", "") or ""
                        reasoning = ""

                    if (content or reasoning) and not (text_parts or reasoning_parts):
                        ttft_ms = round((time.monotonic() - t0) * 1000, 1)
                    if content:
                        text_parts.append(content)
                    if reasoning:
                        reasoning_parts.append(reasoning)

                    usage = chunk.get("usage")
                    if usage and "completion_tokens" in usage:
                        completion_tokens = usage["completion_tokens"]

        except (TimeoutError, ConnectionRefusedError, URLError, OSError, ValueError) as e:
            logger.debug("streaming generate %s failed: %s", url, e)
            return GenerateResult(engine=self.name, model=model, error=str(e))

        elapsed_s = time.monotonic() - t0
        text = "".join(text_parts)
        reasoning_text = "".join(reasoning_parts)
        if completion_tokens == 0:
            total_chars = len(text) + len(reasoning_text)
            completion_tokens = max(1, total_chars // 4)
            logger.warning(
                "Engine did not report completion_tokens — using estimate "
                "(content+reasoning chars)//4 = %d (may be ~25%% off). Model: %s",
                completion_tokens,
                model,
            )

        ttft_s = ttft_ms / 1000.0
        generation_s = max(0.0, elapsed_s - ttft_s)
        tok_s = (completion_tokens / generation_s) if generation_s >= 0.01 else 0.0

        return GenerateResult(
            text=text,
            tokens_generated=completion_tokens,
            tok_per_sec=round(tok_s, 2),
            ttft_ms=ttft_ms,
            ttft_client_ms=ttft_ms,  # Already client-side
            total_duration_ms=round(elapsed_s * 1000, 1),
            prompt_eval_duration_ms=ttft_ms,
            generation_duration_ms=round(generation_s * 1000, 1),
            model=model,
            engine=self.name,
        )
