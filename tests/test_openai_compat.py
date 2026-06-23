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

    def test_list_running_resolves_local_symlink(self, tmp_path):
        """llama.cpp reports the --model path; a LOCAL symlinked active model must surface as
        the real GGUF filename, not the useless 'active.gguf'."""
        real = tmp_path / "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf"
        real.write_bytes(b"gguf")
        link = tmp_path / "active.gguf"
        link.symlink_to(real)
        data = {"data": [{"id": str(link)}]}
        with patch(
            "asiai.engines.openai_compat.http_get_json",
            return_value=(data, {}),
        ):
            models = _ChatEngine("http://127.0.0.1:8080").list_running()
        assert models[0].name == "Qwen3.6-35B-A3B-UD-Q4_K_S.gguf"

    def test_list_running_remote_path_basename_not_resolved(self, tmp_path):
        """A REMOTE engine's path must NOT be realpath'd against THIS filesystem (could resolve
        to a wrong local file) — only its basename is taken."""
        real = tmp_path / "local-decoy.gguf"
        real.write_bytes(b"gguf")
        link = tmp_path / "active.gguf"
        link.symlink_to(real)
        data = {"data": [{"id": str(link)}]}
        with patch(
            "asiai.engines.openai_compat.http_get_json",
            return_value=(data, {}),
        ):
            models = _ChatEngine("http://192.0.2.1:8080").list_running()
        assert models[0].name == "active.gguf"  # basename only, not the resolved decoy

    def test_list_running_prefers_meta_size(self):
        """meta.size (real model size) wins over the per-process footprint estimate."""
        data = {"data": [{"id": "model-a", "meta": {"size": 21_377_327_616}}]}
        with patch(
            "asiai.engines.openai_compat.http_get_json",
            return_value=(data, {}),
        ):
            models = _ChatEngine("http://localhost:8080").list_running()
        assert models[0].size_vram == 21_377_327_616

    def test_is_local_exact_hostname_not_substring(self):
        """A remote host merely CONTAINING a loopback token is not local (no realpath leak)."""
        assert _ChatEngine("http://127.0.0.1:8080")._is_local()
        assert _ChatEngine("http://localhost:8080")._is_local()
        assert _ChatEngine("http://[::1]:8080")._is_local()
        assert not _ChatEngine("http://localhost.example.com:8080")._is_local()
        assert not _ChatEngine("http://127.0.0.1.evil.com:8080")._is_local()
        assert not _ChatEngine("http://192.0.2.1:8080")._is_local()

    def test_list_running_dangling_local_symlink_falls_back_to_basename(self, tmp_path):
        """A local symlink whose target is missing degrades to the basename, never crashes."""
        link = tmp_path / "active.gguf"
        link.symlink_to(tmp_path / "missing-target.gguf")  # dangling
        data = {"data": [{"id": str(link)}]}
        with patch(
            "asiai.engines.openai_compat.http_get_json",
            return_value=(data, {}),
        ):
            models = _ChatEngine("http://127.0.0.1:8080").list_running()
        assert models[0].name == "active.gguf"

    def test_list_running_tolerates_non_numeric_meta_size(self):
        """A non-numeric meta.size must not abort the listing (size falls back to 0)."""
        data = {"data": [{"id": "model-a", "meta": {"size": "21G"}}]}
        with patch(
            "asiai.engines.openai_compat.http_get_json",
            return_value=(data, {}),
        ):
            models = _ChatEngine("http://localhost:8080").list_running()
        assert models[0].name == "model-a"
        assert models[0].size_vram == 0

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
            # t0, "hello" (first token), " world" (last token), elapsed-at-end.
            mock_time.monotonic.side_effect = [0.0, 0.15, 0.95, 1.0]
            engine = _ChatEngine("http://localhost:8080")
            result = engine.generate("model-a", "say hi", 256)

        assert result.text == "hello world"
        assert result.tokens_generated == 50
        assert result.tokens_source == "usage"
        # Unified decode rate: (50-1) tokens over the [first, last] span (0.95-0.15).
        assert result.tok_per_sec == 61.25
        assert result.ttft_ms == 150.0
        assert result.prompt_eval_duration_ms == 0.0  # no server-native prefill
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

    def test_generate_no_usage_counts_chunks(self):
        # No usage block: completion_tokens falls back to the streamed content
        # chunk count (labeled tokens_source='chunks'), never the old chars//4.
        chunks = [
            {"choices": [{"delta": {"content": "a"}}]},
            {"choices": [{"delta": {"content": "b"}}]},
            {"choices": [{"delta": {"content": "c"}}]},
        ]
        with (
            patch("asiai.engines.openai_compat.urlopen", return_value=_sse_response(chunks)),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 0.1, 0.2, 0.3, 0.4]
            engine = _ChatEngine("http://localhost:8080")
            result = engine.generate("m", "go", 64)

        assert result.tokens_generated == 3
        assert result.tokens_source == "chunks"
        assert result.error == ""

    def test_generate_empty_response_errors(self):
        # No content and no usage: refuse to fabricate a tok/s — error out
        # (the old chars//4 estimate is gone).
        chunks = [{"choices": [{"delta": {"role": "assistant"}}]}]
        with (
            patch("asiai.engines.openai_compat.urlopen", return_value=_sse_response(chunks)),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 0.1]
            engine = _ChatEngine("http://localhost:8080")
            result = engine.generate("m", "go", 64)

        assert result.error != ""
        assert result.tokens_generated == 0


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
            # t0, "def " (first), "foo():", " pass" (last), elapsed-at-end.
            mock_time.monotonic.side_effect = [0.0, 0.1, 0.5, 1.9, 2.0]
            engine = _CompletionsEngine("http://localhost:8080")
            result = engine.generate("model-b", "Write code", 512)

        assert result.text == "def foo(): pass"
        assert result.tokens_generated == 80
        # Unified decode rate: (80-1) tokens over the [first, last] span (1.9-0.1).
        assert result.tok_per_sec == 43.89
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
