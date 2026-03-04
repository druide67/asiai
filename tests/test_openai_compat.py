"""Tests for OpenAI-compatible base class."""

from __future__ import annotations

import json
from unittest.mock import patch

from asiai.engines.openai_compat import OpenAICompatEngine


class _ChatEngine(OpenAICompatEngine):
    """Test engine using chat mode."""

    _generate_endpoint = "/v1/chat/completions"
    _generate_mode = "chat"
    _model_format = "MLX"

    @property
    def name(self) -> str:
        return "test_chat"

    def version(self) -> str:
        return "1.0"


class _CompletionsEngine(OpenAICompatEngine):
    """Test engine using completions mode."""

    _generate_endpoint = "/v1/completions"
    _generate_mode = "completions"
    _model_format = "GGUF"

    @property
    def name(self) -> str:
        return "test_completions"

    def version(self) -> str:
        return "2.0"


def _sse_response(chunks: list[dict]):
    """Build a mock HTTP response that yields SSE lines."""
    lines: list[bytes] = []
    for chunk in chunks:
        lines.append(f"data: {json.dumps(chunk)}\n".encode())
        lines.append(b"\n")
    lines.append(b"data: [DONE]\n")
    lines.append(b"\n")

    class MockSSEResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def __iter__(self):
            return iter(lines)

    return MockSSEResponse()


class TestOpenAICompatIsReachable:
    def test_reachable(self):
        with patch(
            "asiai.engines.openai_compat.http_get_json",
            return_value=({"data": []}, {}),
        ):
            engine = _ChatEngine("http://localhost:8080")
            assert engine.is_reachable()

    def test_not_reachable(self):
        with patch(
            "asiai.engines.openai_compat.http_get_json",
            return_value=(None, {}),
        ):
            engine = _ChatEngine("http://localhost:8080")
            assert not engine.is_reachable()


class TestOpenAICompatListRunning:
    def test_list_running(self):
        data = {"data": [{"id": "model-a"}, {"id": "model-b"}]}
        with patch(
            "asiai.engines.openai_compat.http_get_json",
            return_value=(data, {}),
        ):
            engine = _ChatEngine("http://localhost:8080")
            models = engine.list_running()

        assert len(models) == 2
        assert models[0].name == "model-a"
        assert models[0].format == "MLX"

    def test_list_running_unreachable(self):
        with patch(
            "asiai.engines.openai_compat.http_get_json",
            return_value=(None, {}),
        ):
            engine = _ChatEngine("http://localhost:8080")
            assert engine.list_running() == []

    def test_list_available_always_empty(self):
        engine = _ChatEngine("http://localhost:8080")
        assert engine.list_available() == []


class TestOpenAICompatGenerateChat:
    def test_generate_chat_success(self):
        chunks = [
            {"choices": [{"delta": {"role": "assistant"}}]},
            {"choices": [{"delta": {"content": "hello"}}]},
            {"choices": [{"delta": {"content": " world"}}]},
            {"choices": [{"delta": {}}], "usage": {"completion_tokens": 50}},
        ]

        with (
            patch("asiai.engines.openai_compat.urlopen", return_value=_sse_response(chunks)),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 0.15, 1.0]
            engine = _ChatEngine("http://localhost:8080")
            result = engine.generate("model-a", "say hi", 256)

        assert result.text == "hello world"
        assert result.tokens_generated == 50
        assert result.tok_per_sec == 58.82  # 50 / (1.0 - 0.15) generation only
        assert result.ttft_ms == 150.0
        assert result.engine == "test_chat"
        assert result.error == ""

    def test_generate_chat_ttft_measured(self):
        """TTFT is measured at the first content chunk, not the role chunk."""
        chunks = [
            {"choices": [{"delta": {"role": "assistant"}}]},
            {"choices": [{"delta": {"content": "hi"}}]},
        ]

        with (
            patch("asiai.engines.openai_compat.urlopen", return_value=_sse_response(chunks)),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            # t0=0.0, first content monotonic=0.2, end=0.5
            mock_time.monotonic.side_effect = [0.0, 0.2, 0.5]
            engine = _ChatEngine("http://localhost:8080")
            result = engine.generate("m", "hi", 64)

        assert result.ttft_ms == 200.0
        assert result.tokens_generated == 1  # fallback: len(text_parts)

    def test_generate_connection_failed(self):
        from urllib.error import URLError

        with (
            patch(
                "asiai.engines.openai_compat.urlopen",
                side_effect=URLError("connection refused"),
            ),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0]
            engine = _ChatEngine("http://localhost:8080")
            result = engine.generate("m", "hi", 256)

        assert result.error != ""


class TestOpenAICompatGenerateCompletions:
    def test_generate_completions_success(self):
        chunks = [
            {"choices": [{"text": "def "}]},
            {"choices": [{"text": "foo():"}]},
            {"choices": [{"text": " pass"}], "usage": {"completion_tokens": 80}},
        ]

        with (
            patch("asiai.engines.openai_compat.urlopen", return_value=_sse_response(chunks)),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 0.1, 2.0]
            engine = _CompletionsEngine("http://localhost:8080")
            result = engine.generate("model-b", "Write code", 512)

        assert result.text == "def foo(): pass"
        assert result.tokens_generated == 80
        assert result.tok_per_sec == 42.11  # 80 / (2.0 - 0.1) generation only
        assert result.ttft_ms == 100.0
        assert result.engine == "test_completions"


class TestOpenAICompatModelFormat:
    def test_format_propagated(self):
        data = {"data": [{"id": "model-a"}]}
        with patch(
            "asiai.engines.openai_compat.http_get_json",
            return_value=(data, {}),
        ):
            engine = _CompletionsEngine("http://localhost:8080")
            models = engine.list_running()
        assert models[0].format == "GGUF"
