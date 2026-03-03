"""Tests for OpenAI-compatible base class."""

from __future__ import annotations

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
        gen_response = {
            "choices": [{"message": {"role": "assistant", "content": "hello world"}}],
            "usage": {"completion_tokens": 50},
        }

        def mock_post(url, data, timeout=300):
            if "/v1/chat/completions" in url:
                return gen_response, {}
            return None, {}

        with (
            patch("asiai.engines.openai_compat.http_post_json", side_effect=mock_post),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 1.0]
            engine = _ChatEngine("http://localhost:8080")
            result = engine.generate("model-a", "say hi", 256)

        assert result.text == "hello world"
        assert result.tokens_generated == 50
        assert result.tok_per_sec == 50.0
        assert result.engine == "test_chat"
        assert result.error == ""

    def test_generate_chat_error(self):
        gen_response = {"error": {"message": "model not found"}}

        with (
            patch("asiai.engines.openai_compat.http_post_json", return_value=(gen_response, {})),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 0.1]
            engine = _ChatEngine("http://localhost:8080")
            result = engine.generate("bad", "hi", 256)

        assert "model not found" in result.error

    def test_generate_connection_failed(self):
        with (
            patch("asiai.engines.openai_compat.http_post_json", return_value=(None, {})),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 0.1]
            engine = _ChatEngine("http://localhost:8080")
            result = engine.generate("m", "hi", 256)

        assert result.error == "request failed"


class TestOpenAICompatGenerateCompletions:
    def test_generate_completions_success(self):
        gen_response = {
            "choices": [{"text": "def foo(): pass"}],
            "usage": {"completion_tokens": 80},
        }

        def mock_post(url, data, timeout=300):
            if "/v1/completions" in url:
                return gen_response, {}
            return None, {}

        with (
            patch("asiai.engines.openai_compat.http_post_json", side_effect=mock_post),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 2.0]
            engine = _CompletionsEngine("http://localhost:8080")
            result = engine.generate("model-b", "Write code", 512)

        assert result.text == "def foo(): pass"
        assert result.tokens_generated == 80
        assert result.tok_per_sec == 40.0
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
