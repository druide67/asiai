"""Base classes for inference engine adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ModelInfo:
    """Information about a loaded or available model."""

    name: str
    size_vram: int = 0
    size_total: int = 0
    format: str = ""
    quantization: str = ""
    context_length: int = 0


@dataclass
class GenerateResult:
    """Result of a text generation request with timing metrics."""

    text: str = ""
    # Thinking/reasoning tokens streamed separately from `text` (Qwen3-family
    # thinking mode: delta.reasoning_content on llama.cpp, delta.reasoning on
    # mlx-lm). Kept out of `text` (clean output) but they ARE generated text —
    # output gates must see them.
    reasoning_text: str = ""
    tokens_generated: int = 0
    tok_per_sec: float = 0.0
    ttft_ms: float = 0.0
    ttft_client_ms: float = 0.0  # Client-side TTFT (comparable across engines)
    total_duration_ms: float = 0.0
    prompt_eval_duration_ms: float = 0.0
    generation_duration_ms: float = 0.0
    prompt_tokens: int = 0
    prefill_tok_s: float = 0.0  # prompt_tokens / time-to-first-token
    tokens_source: str = ""  # 'usage' (server-exact) | 'chunks' (streamed count)
    model: str = ""
    engine: str = ""
    error: str = ""


@dataclass
class EngineStatus:
    """Status of an inference engine."""

    running: list[ModelInfo] = field(default_factory=list)
    available: list[ModelInfo] = field(default_factory=list)
    reachable: bool = False


class InferenceEngine(ABC):
    """Abstract base class for inference engine adapters.

    Each engine (Ollama, LM Studio, mlx-lm, etc.) implements this interface.
    """

    def __init__(self, base_url: str, api_key: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        # Optional per-engine API key (resolved from the user's api_key_file
        # config). Bound to THIS engine's base_url: it must never be attached
        # to a request targeting any other host. Never log it.
        self.api_key = api_key

    def auth_headers(self) -> dict[str, str]:
        """Authorization header for this engine's API key ({} when none).

        Only ever attach these headers to requests aimed at ``self.base_url``.
        """
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    def _http_kwargs(self) -> dict:
        """Keyword arguments for ``http_get_json``/``http_post_json`` calls.

        Empty when no API key is configured, so keyless engines issue
        byte-identical requests to before this feature existed.
        """
        headers = self.auth_headers()
        return {"headers": headers} if headers else {}

    @property
    @abstractmethod
    def name(self) -> str:
        """Engine name (e.g. 'ollama', 'lmstudio')."""

    @abstractmethod
    def version(self) -> str:
        """Return the engine version string, or empty string if unreachable."""

    @abstractmethod
    def is_reachable(self) -> bool:
        """Check if the engine is responding."""

    @abstractmethod
    def list_running(self) -> list[ModelInfo]:
        """List currently loaded/running models."""

    @abstractmethod
    def list_available(self) -> list[ModelInfo]:
        """List all available (downloaded) models."""

    @abstractmethod
    def generate(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 512,
        extra_body: dict | None = None,
    ) -> GenerateResult:
        """Send a generation request and return timing metrics.

        ``extra_body`` is merged into the request payload so the caller can pass
        engine-specific kwargs uniformly — e.g.
        ``{"chat_template_kwargs": {"enable_thinking": False}}`` to keep Qwen3
        reasoning tokens out of the throughput/TTFT measurement.
        """

    def unload_model(self, model: str) -> bool:
        """Unload a model from engine memory to free resources.

        Returns True if unload was attempted, False if not supported.
        Override in engines that support model unloading (Ollama, LM Studio).
        """
        return False

    def measure_load_time(self, model: str) -> float:
        """Measure model load time in milliseconds.

        Returns 0.0 by default. Override in engines that support load timing.
        """
        return 0.0

    def scrape_metrics(self) -> dict:
        """Scrape engine-native /metrics endpoint.

        Returns a dict of normalized metrics, or {} by default.
        Override in engines that expose Prometheus metrics (llama.cpp, vllm-mlx).
        """
        return {}

    def status(self) -> EngineStatus:
        """Collect full engine status."""
        return EngineStatus(
            running=self.list_running(),
            available=self.list_available(),
            reachable=self.is_reachable(),
        )
