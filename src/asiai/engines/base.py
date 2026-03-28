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
    tokens_generated: int = 0
    tok_per_sec: float = 0.0
    ttft_ms: float = 0.0
    total_duration_ms: float = 0.0
    prompt_eval_duration_ms: float = 0.0
    generation_duration_ms: float = 0.0
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

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

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
    def generate(self, model: str, prompt: str, max_tokens: int = 512) -> GenerateResult:
        """Send a generation request and return timing metrics."""

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
