"""Ollama inference engine adapter."""

from __future__ import annotations

import json
import logging
import time
from urllib.request import Request, urlopen

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
            ctx_len = self._get_context_length(m.get("name", ""))
            models.append(
                ModelInfo(
                    name=m.get("name", "unknown"),
                    size_vram=m.get("size_vram", 0),
                    size_total=m.get("size", 0),
                    format=m.get("details", {}).get("format", ""),
                    quantization=m.get("details", {}).get("quantization_level", ""),
                    context_length=ctx_len,
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

    def _get_context_length(self, model_name: str) -> int:
        """Fetch context window size from /api/show for a model."""
        if not model_name:
            return 0
        data, _ = http_post_json(
            f"{self.base_url}/api/show",
            {"model": model_name},
            timeout=10,
        )
        if data is None:
            return 0
        # model_info contains <arch>.context_length
        model_info = data.get("model_info", {})
        if isinstance(model_info, dict):
            for key, value in model_info.items():
                if key.endswith(".context_length") and isinstance(value, int):
                    return value
        return 0

    def unload_model(self, model: str) -> bool:
        """Unload model from Ollama by setting keep_alive to 0."""
        try:
            http_post_json(
                f"{self.base_url}/api/generate",
                {"model": model, "keep_alive": 0},
                timeout=10,
            )
            logger.info("Unloaded %s from Ollama", model)
            return True
        except Exception as e:
            logger.debug("Ollama unload failed for %s: %s", model, e)
            return False

    def generate(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 512,
        extra_body: dict | None = None,
    ) -> GenerateResult:
        """Generate text using Ollama /api/generate with streaming.

        Streams to measure client-side TTFT (comparable across engines) while
        capturing server-side token counts from the final chunk. tok/s uses the
        unified client-side decode formula so it lines up with the OpenAI-compat
        engines on the same GGUF. ``extra_body`` is merged top-level into the
        payload (e.g. ``{"think": False}`` to disable thinking on Ollama).
        """
        body: dict = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {"num_predict": max_tokens, "temperature": 0},
        }
        if extra_body:
            body.update(extra_body)
        payload = json.dumps(body).encode()

        t0 = time.monotonic()
        ttft_client_ms = 0.0
        first_token_t = 0.0
        last_token_t = 0.0
        text_parts: list[str] = []
        final_data: dict = {}

        try:
            req = Request(
                f"{self.base_url}/api/generate",
                data=payload,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")

            with urlopen(req, timeout=300) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    token = chunk.get("response", "")
                    if token:
                        now = time.monotonic()
                        if not text_parts:
                            first_token_t = now
                            ttft_client_ms = round((now - t0) * 1000, 1)
                        last_token_t = now
                        text_parts.append(token)

                    if chunk.get("done"):
                        final_data = chunk
                        break

        except (TimeoutError, ConnectionRefusedError, OSError, ValueError) as e:
            logger.debug("Ollama streaming generate failed: %s", e)
            return GenerateResult(engine=self.name, model=model, error=str(e))

        if not final_data:
            return GenerateResult(engine=self.name, model=model, error="no final chunk received")

        eval_count = final_data.get("eval_count", 0)
        eval_duration_ns = final_data.get("eval_duration", 0)
        prompt_eval_ns = final_data.get("prompt_eval_duration", 0)
        prompt_eval_count = final_data.get("prompt_eval_count", 0)
        total_ns = final_data.get("total_duration", 0)

        # Unified client-side decode rate (same formula as the OpenAI-compat
        # engines) so Ollama lines up with llama.cpp on the same GGUF. The native
        # server eval rate stays recoverable from generation_duration_ms.
        decode_span_s = max(0.0, last_token_t - first_token_t)
        if eval_count > 1 and decode_span_s >= 0.01:
            tok_s = (eval_count - 1) / decode_span_s
        else:
            tok_s = 0.0

        ttft_client_s = ttft_client_ms / 1000.0
        prefill_tok_s = (
            round(prompt_eval_count / ttft_client_s, 2)
            if prompt_eval_count and ttft_client_s >= 0.01
            else 0.0
        )

        return GenerateResult(
            text="".join(text_parts),
            tokens_generated=eval_count,
            tok_per_sec=round(tok_s, 2),
            ttft_ms=round(prompt_eval_ns / 1e6, 1),
            ttft_client_ms=ttft_client_ms,
            total_duration_ms=round(total_ns / 1e6, 1),
            prompt_eval_duration_ms=round(prompt_eval_ns / 1e6, 1),
            generation_duration_ms=round(eval_duration_ns / 1e6, 1),
            prompt_tokens=prompt_eval_count,
            prefill_tok_s=prefill_tok_s,
            tokens_source="usage",
            model=model,
            engine=self.name,
        )
