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
                from asiai.collectors.system import find_engine_process

                engine_proc = find_engine_process(self.name)
                if engine_proc and engine_proc.phys_footprint_bytes > 0:
                    # Divide evenly if multiple models (rough estimate)
                    per_model = engine_proc.phys_footprint_bytes // len(models)
                    for m in models:
                        m.size_vram = per_model
            except Exception:
                pass
        return models

    def list_available(self) -> list[ModelInfo]:
        return []

    def generate(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 512,
        extra_body: dict | None = None,
    ) -> GenerateResult:
        """Generate text via streaming OpenAI-compatible API (measures TTFT).

        Token counts come from the streamed ``usage`` block (requested via
        ``stream_options.include_usage``) when the engine reports it
        (``tokens_source='usage'``); otherwise the streamed content chunks are
        counted (``tokens_source='chunks'``). The old chars//4 estimate is gone:
        if neither is available the run errors out rather than fabricate a tok/s.
        ``extra_body`` is merged into the payload (caller keys win) — used to
        pass ``chat_template_kwargs={"enable_thinking": False}`` uniformly.
        """
        t0 = time.monotonic()

        if self._generate_mode == "chat":
            payload: dict = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "stream": True,
                "stream_options": {"include_usage": True},
                "temperature": 0.0,
            }
        else:
            payload = {
                "model": model,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "stream": True,
                "stream_options": {"include_usage": True},
                "temperature": 0.0,
            }
        if extra_body:
            payload.update(extra_body)

        url = f"{self.base_url}{self._generate_endpoint}"
        ttft_ms = 0.0
        first_token_t = 0.0
        last_token_t = 0.0
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        content_chunks = 0
        completion_tokens = 0
        prompt_tokens = 0

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

                    usage = chunk.get("usage")
                    if usage:
                        if "completion_tokens" in usage:
                            completion_tokens = usage["completion_tokens"]
                        if "prompt_tokens" in usage:
                            prompt_tokens = usage["prompt_tokens"]

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    if self._generate_mode == "chat":
                        delta = choices[0].get("delta", {}) or {}
                        content = delta.get("content") or ""
                        # Qwen3/3.5/3.6 thinking mode emits reasoning tokens in
                        # delta.reasoning_content (llama.cpp) or delta.reasoning
                        # (mlx-lm). Counted in throughput (they are real decode
                        # work), excluded from `text` (clean output).
                        reasoning = (delta.get("reasoning_content") or "") + (
                            delta.get("reasoning") or ""
                        )
                    else:
                        content = choices[0].get("text", "") or ""
                        reasoning = ""

                    if content or reasoning:
                        now = time.monotonic()
                        if not (text_parts or reasoning_parts):
                            first_token_t = now
                            ttft_ms = round((now - t0) * 1000, 1)
                        last_token_t = now
                        content_chunks += 1
                    if content:
                        text_parts.append(content)
                    if reasoning:
                        reasoning_parts.append(reasoning)

        except (TimeoutError, ConnectionRefusedError, URLError, OSError, ValueError) as e:
            logger.debug("streaming generate %s failed: %s", url, e)
            return GenerateResult(engine=self.name, model=model, error=str(e))

        elapsed_s = time.monotonic() - t0
        text = "".join(text_parts)

        if completion_tokens > 0:
            tokens_source = "usage"
        elif content_chunks > 0:
            completion_tokens = content_chunks
            tokens_source = "chunks"
        else:
            return GenerateResult(
                engine=self.name,
                model=model,
                error="no usage reported and no content chunks streamed",
            )

        # Unified client-side decode rate: (n-1) tokens over the inter-token span
        # [first_token, last_token]. Same formula for every engine so tok/s is
        # comparable; server-native rates are never mixed in.
        decode_span_s = max(0.0, last_token_t - first_token_t)
        if completion_tokens > 1 and decode_span_s >= 0.01:
            tok_s = (completion_tokens - 1) / decode_span_s
        else:
            tok_s = 0.0

        ttft_s = ttft_ms / 1000.0
        prefill_tok_s = (
            round(prompt_tokens / ttft_s, 2) if prompt_tokens and ttft_s >= 0.01 else 0.0
        )
        generation_s = max(0.0, elapsed_s - ttft_s)

        return GenerateResult(
            text=text,
            tokens_generated=completion_tokens,
            tok_per_sec=round(tok_s, 2),
            ttft_ms=ttft_ms,
            ttft_client_ms=ttft_ms,  # No server-native prefill on this path
            total_duration_ms=round(elapsed_s * 1000, 1),
            prompt_eval_duration_ms=0.0,  # client-only: no server prefill timing
            generation_duration_ms=round(generation_s * 1000, 1),
            prompt_tokens=prompt_tokens,
            prefill_tok_s=prefill_tok_s,
            tokens_source=tokens_source,
            model=model,
            engine=self.name,
        )
