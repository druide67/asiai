"""Tests for engine detection and adapters."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from asiai.engines.detect import (
    detect_engine_type,
    detect_engines,
    detect_port_process,
    discover_via_processes,
    http_get_json,
    http_post_json,
)
from asiai.engines.llamacpp import LlamaCppEngine
from asiai.engines.lmstudio import LMStudioEngine
from asiai.engines.mlxlm import MlxLmEngine
from asiai.engines.ollama import OllamaEngine
from asiai.engines.vllm_mlx import VllmMlxEngine


class TestHttpGetJson:
    def test_success(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"version": "0.17.4"}'
        mock_resp.headers = MagicMock()
        mock_resp.headers.items.return_value = [("Content-Type", "application/json")]
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("asiai.engines.detect.urlopen", return_value=mock_resp):
            data, headers = http_get_json("http://localhost:11434/api/version")

        assert data == {"version": "0.17.4"}
        assert headers["content-type"] == "application/json"

    def test_connection_error(self):
        with patch("asiai.engines.detect.urlopen", side_effect=OSError("refused")):
            data, headers = http_get_json("http://localhost:11434/api/version")

        assert data is None
        assert headers == {}


class TestDetectEngineType:
    def test_ollama(self):
        def mock_get(url, timeout=5):
            if "/api/version" in url:
                return {"version": "0.17.4"}, {}
            return None, {}

        with patch("asiai.engines.detect.http_get_json", side_effect=mock_get):
            engine, version = detect_engine_type("http://localhost:11434")

        assert engine == "ollama"
        assert version == "0.17.4"

    def test_lmstudio(self):
        def mock_get(url, timeout=5):
            if "/api/version" in url:
                return None, {}
            if "/v1/models" in url:
                return {"data": []}, {"x-lm-studio-version": "0.3.5"}
            return None, {}

        with patch("asiai.engines.detect.http_get_json", side_effect=mock_get):
            engine, version = detect_engine_type("http://localhost:1234")

        assert engine == "lmstudio"
        assert version == "0.3.5"

    def test_unknown(self):
        with patch("asiai.engines.detect.http_get_json", return_value=(None, {})):
            engine, version = detect_engine_type("http://localhost:9999")

        assert engine == "unknown"
        assert version == ""


class TestOllamaEngine:
    def _mock_get(self, responses: dict):
        def mock(url, timeout=5):
            for path, resp in responses.items():
                if path in url:
                    return resp, {}
            return None, {}

        return mock

    def test_is_reachable(self):
        with patch(
            "asiai.engines.ollama.http_get_json",
            return_value=({"version": "0.17.4"}, {}),
        ):
            engine = OllamaEngine("http://localhost:11434")
            assert engine.is_reachable()

    def test_list_running(self):
        ps_response = {
            "models": [
                {
                    "name": "qwen3-coder:30b",
                    "size_vram": 20_000_000_000,
                    "size": 16_000_000_000,
                    "details": {"format": "gguf", "quantization_level": "Q4_K_M"},
                }
            ]
        }
        show_response = {"model_info": {"llama.context_length": 32768}}
        mock = self._mock_get({"/api/ps": ps_response})
        with (
            patch("asiai.engines.ollama.http_get_json", side_effect=mock),
            patch("asiai.engines.ollama.http_post_json", return_value=(show_response, {})),
        ):
            engine = OllamaEngine("http://localhost:11434")
            models = engine.list_running()

        assert len(models) == 1
        assert models[0].name == "qwen3-coder:30b"
        assert models[0].size_vram == 20_000_000_000
        assert models[0].quantization == "Q4_K_M"
        assert models[0].context_length == 32768

    def test_list_running_no_context_length(self):
        ps_response = {"models": [{"name": "test:latest", "details": {}}]}
        mock = self._mock_get({"/api/ps": ps_response})
        with (
            patch("asiai.engines.ollama.http_get_json", side_effect=mock),
            patch("asiai.engines.ollama.http_post_json", return_value=(None, {})),
        ):
            engine = OllamaEngine("http://localhost:11434")
            models = engine.list_running()

        assert len(models) == 1
        assert models[0].context_length == 0

    def test_list_available(self):
        tags_response = {
            "models": [
                {"name": "llama3:8b", "size": 4_000_000_000},
                {"name": "qwen3-coder:30b", "size": 16_000_000_000},
            ]
        }
        mock = self._mock_get({"/api/tags": tags_response})
        with patch("asiai.engines.ollama.http_get_json", side_effect=mock):
            engine = OllamaEngine("http://localhost:11434")
            models = engine.list_available()

        assert len(models) == 2


class TestOllamaMeasureLoadTime:
    def test_load_time_from_api(self):
        def mock_post(url, data, timeout=300):
            if "/api/generate" in url:
                return {"load_duration": 2_000_000_000}, {}  # 2s in ns
            return None, {}

        with patch("asiai.engines.ollama.http_post_json", side_effect=mock_post):
            engine = OllamaEngine("http://localhost:11434")
            result = engine.measure_load_time("test-model")

        assert result == 2000.0  # 2000 ms

    def test_load_time_no_data(self):
        with patch("asiai.engines.ollama.http_post_json", return_value=(None, {})):
            engine = OllamaEngine("http://localhost:11434")
            result = engine.measure_load_time("test-model")

        assert result == 0.0


class TestHttpPostJson:
    def test_success(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"response": "hello"}'
        mock_resp.headers = MagicMock()
        mock_resp.headers.items.return_value = [("Content-Type", "application/json")]
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("asiai.engines.detect.urlopen", return_value=mock_resp):
            data, headers = http_post_json("http://localhost/api", {"prompt": "hi"})

        assert data == {"response": "hello"}

    def test_error(self):
        with patch("asiai.engines.detect.urlopen", side_effect=OSError("refused")):
            data, headers = http_post_json("http://localhost/api", {"prompt": "hi"})

        assert data is None
        assert headers == {}


def _ollama_stream_response(chunks: list[dict]):
    """Build a mock urlopen response yielding NDJSON lines (Ollama /api/generate stream)."""
    lines = [json.dumps(c).encode() + b"\n" for c in chunks]

    class MockResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def __iter__(self):
            return iter(lines)

    return MockResp()


class TestOllamaGenerate:
    def test_generate_success(self):
        chunks = [
            {"response": "class BST:"},
            {"response": "\n    pass"},
            {
                "done": True,
                "eval_count": 150,
                "eval_duration": 3_000_000_000,
                "prompt_eval_duration": 800_000_000,
                "total_duration": 4_000_000_000,
            },
        ]

        with patch(
            "asiai.engines.ollama.urlopen",
            return_value=_ollama_stream_response(chunks),
        ):
            engine = OllamaEngine("http://localhost:11434")
            result = engine.generate("test-model", "Write a BST", 512)

        assert result.tokens_generated == 150
        assert result.tok_per_sec == 50.0
        assert result.ttft_ms == 800.0
        assert result.text == "class BST:\n    pass"
        assert result.error == ""

    def test_generate_error(self):
        # Streaming server returns an error chunk without `done=True` —
        # the engine never sees a final chunk and reports the truncation.
        chunks = [{"error": "model not found"}]

        with patch(
            "asiai.engines.ollama.urlopen",
            return_value=_ollama_stream_response(chunks),
        ):
            engine = OllamaEngine("http://localhost:11434")
            result = engine.generate("bad-model", "hello", 512)

        assert "no final chunk" in result.error

    def test_generate_connection_failed(self):
        with patch(
            "asiai.engines.ollama.urlopen",
            side_effect=ConnectionRefusedError("Connection refused"),
        ):
            engine = OllamaEngine("http://localhost:11434")
            result = engine.generate("model", "hello", 512)

        assert "Connection refused" in result.error


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


class TestLMStudioGenerate:
    def test_generate_success(self):
        chunks = [
            {"choices": [{"text": "def hello(): pass"}], "usage": {"completion_tokens": 80}},
        ]

        with (
            patch("asiai.engines.openai_compat.urlopen", return_value=_sse_response(chunks)),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 0.1, 2.0]
            engine = LMStudioEngine("http://localhost:1234")
            result = engine.generate("test-model", "Write code", 512)

        assert result.tokens_generated == 80
        assert result.tok_per_sec == 42.11  # 80 / (2.0 - 0.1) generation only
        assert result.ttft_ms == 100.0
        assert result.error == ""

    def test_generate_error(self):
        from urllib.error import URLError

        with (
            patch(
                "asiai.engines.openai_compat.urlopen",
                side_effect=URLError("model not loaded"),
            ),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0]
            engine = LMStudioEngine("http://localhost:1234")
            result = engine.generate("bad-model", "hello", 512)

        assert "model not loaded" in result.error


class TestLMStudioEngine:
    def test_list_running(self):
        def mock_get(url, timeout=5):
            if "/v1/models" in url:
                return {
                    "data": [
                        {"id": "qwen-2.5-32b-instruct"},
                        {"id": "phi-3-mini"},
                    ]
                }, {}
            return None, {}

        with patch("asiai.engines.openai_compat.http_get_json", side_effect=mock_get):
            engine = LMStudioEngine("http://localhost:1234")
            models = engine.list_running()

        assert len(models) == 2
        assert models[0].name == "qwen-2.5-32b-instruct"
        assert models[0].format == "MLX"


class TestMlxLmEngine:
    def test_is_reachable(self):
        with patch(
            "asiai.engines.openai_compat.http_get_json",
            return_value=({"data": []}, {}),
        ):
            engine = MlxLmEngine("http://localhost:8080")
            assert engine.is_reachable()

    def test_is_not_reachable(self):
        with patch(
            "asiai.engines.openai_compat.http_get_json",
            return_value=(None, {}),
        ):
            engine = MlxLmEngine("http://localhost:8080")
            assert not engine.is_reachable()

    def test_list_running(self):
        def mock_get(url, timeout=5):
            if "/v1/models" in url:
                return {
                    "data": [
                        {"id": "mlx-community/gemma-2-9b-4bit"},
                    ]
                }, {}
            return None, {}

        with patch("asiai.engines.openai_compat.http_get_json", side_effect=mock_get):
            engine = MlxLmEngine("http://localhost:8080")
            models = engine.list_running()

        assert len(models) == 1
        assert models[0].name == "mlx-community/gemma-2-9b-4bit"
        assert models[0].format == "MLX"

    def test_list_available(self):
        engine = MlxLmEngine("http://localhost:8080")
        assert engine.list_available() == []

    def test_version_via_brew(self):
        with patch("asiai.engines.mlxlm.subprocess") as mock_sub:
            mock_result = MagicMock()
            mock_result.stdout = "mlx-lm 0.30.7\n"
            mock_sub.run.return_value = mock_result
            engine = MlxLmEngine("http://localhost:8080")
            assert engine.version() == "0.30.7"

    def test_version_not_installed(self):
        with patch("asiai.engines.mlxlm.subprocess") as mock_sub:
            mock_result = MagicMock()
            mock_result.stdout = ""
            mock_sub.run.return_value = mock_result
            engine = MlxLmEngine("http://localhost:8080")
            assert engine.version() == ""


class TestMlxLmGenerate:
    def test_generate_success(self):
        chunks = [
            {"choices": [{"delta": {"role": "assistant"}}]},
            {
                "choices": [{"delta": {"content": "def hello(): pass"}}],
                "usage": {"completion_tokens": 80},
            },
        ]

        with (
            patch("asiai.engines.openai_compat.urlopen", return_value=_sse_response(chunks)),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 0.1, 2.0]
            engine = MlxLmEngine("http://localhost:8080")
            result = engine.generate("test-model", "Write code", 512)

        assert result.tokens_generated == 80
        assert result.tok_per_sec == 42.11  # 80 / (2.0 - 0.1) generation only
        assert result.text == "def hello(): pass"
        assert result.error == ""

    def test_generate_error(self):
        from urllib.error import URLError

        with (
            patch(
                "asiai.engines.openai_compat.urlopen",
                side_effect=URLError("model not loaded"),
            ),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0]
            engine = MlxLmEngine("http://localhost:8080")
            result = engine.generate("bad-model", "hello", 512)

        assert "model not loaded" in result.error

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
            engine = MlxLmEngine("http://localhost:8080")
            result = engine.generate("model", "hello", 512)

        assert result.error != ""


class TestDetectMlxLm:
    def test_detect_mlxlm_no_lmstudio_headers(self):
        """mlx-lm responds to /v1/models but has no LM Studio markers."""

        def mock_get(url, timeout=5):
            if "/api/version" in url:
                return None, {}
            if "/v1/models" in url:
                return {"data": [{"id": "gemma-2-9b"}]}, {}
            if "/lms/version" in url:
                return None, {}
            return None, {}

        with patch("asiai.engines.detect.http_get_json", side_effect=mock_get):
            engine, version = detect_engine_type("http://localhost:8080")

        assert engine == "mlxlm"

    def test_detect_lmstudio_with_header(self):
        """LM Studio with header should NOT be detected as mlx-lm."""

        def mock_get(url, timeout=5):
            if "/api/version" in url:
                return None, {}
            if "/v1/models" in url:
                return {"data": []}, {"x-lm-studio-version": "0.4.6"}
            return None, {}

        with patch("asiai.engines.detect.http_get_json", side_effect=mock_get):
            engine, version = detect_engine_type("http://localhost:1234")

        assert engine == "lmstudio"
        assert version == "0.4.6"


class TestDetectPortProcess:
    def test_detect_mlxlm(self):
        mock_result = MagicMock()
        mock_result.stdout = "p1234\ncmlx_lm.server\n"
        with patch("asiai.engines.detect.subprocess") as mock_sub:
            mock_sub.run.return_value = mock_result
            assert detect_port_process(8080) == "mlxlm"

    def test_detect_llamacpp(self):
        mock_result = MagicMock()
        mock_result.stdout = "p5678\ncllama-server\n"
        with patch("asiai.engines.detect.subprocess") as mock_sub:
            mock_sub.run.return_value = mock_result
            assert detect_port_process(8080) == "llamacpp"

    def test_detect_vllm(self):
        mock_result = MagicMock()
        mock_result.stdout = "p9999\ncvllm\n"
        with patch("asiai.engines.detect.subprocess") as mock_sub:
            mock_sub.run.return_value = mock_result
            assert detect_port_process(8000) == "vllm_mlx"

    def test_detect_unknown_process(self):
        mock_result = MagicMock()
        mock_result.stdout = "p1111\ncpython3\n"
        with patch("asiai.engines.detect.subprocess") as mock_sub:
            mock_sub.run.return_value = mock_result
            assert detect_port_process(8080) == ""

    def test_detect_no_listener(self):
        mock_result = MagicMock()
        mock_result.stdout = ""
        with patch("asiai.engines.detect.subprocess") as mock_sub:
            mock_sub.run.return_value = mock_result
            assert detect_port_process(8080) == ""

    def test_detect_lsof_error(self):
        with patch("asiai.engines.detect.subprocess") as mock_sub:
            mock_sub.run.side_effect = Exception("command failed")
            assert detect_port_process(8080) == ""


class TestLlamaCppEngine:
    def test_name(self):
        engine = LlamaCppEngine("http://localhost:8080")
        assert engine.name == "llamacpp"

    def test_is_reachable_ok(self):
        with patch(
            "asiai.engines.llamacpp.http_get_json",
            return_value=({"status": "ok"}, {}),
        ):
            engine = LlamaCppEngine("http://localhost:8080")
            assert engine.is_reachable()

    def test_is_reachable_down(self):
        with patch(
            "asiai.engines.llamacpp.http_get_json",
            return_value=(None, {}),
        ):
            engine = LlamaCppEngine("http://localhost:8080")
            assert not engine.is_reachable()

    def test_version_via_props(self):
        def mock_get(url, timeout=5):
            if "/props" in url:
                return {"build_info": {"version": "b4567"}}, {}
            return None, {}

        with patch("asiai.engines.llamacpp.http_get_json", side_effect=mock_get):
            engine = LlamaCppEngine("http://localhost:8080")
            assert engine.version() == "b4567"

    def test_version_via_brew(self):
        with (
            patch("asiai.engines.llamacpp.http_get_json", return_value=(None, {})),
            patch("asiai.engines.llamacpp.subprocess") as mock_sub,
        ):
            mock_result = MagicMock()
            mock_result.stdout = "llama.cpp 0.0.4567\n"
            mock_sub.run.return_value = mock_result
            engine = LlamaCppEngine("http://localhost:8080")
            assert engine.version() == "0.0.4567"

    def test_generate_uses_chat_mode(self):
        chunks = [
            {"choices": [{"delta": {"content": "hello"}}], "usage": {"completion_tokens": 10}},
        ]

        with (
            patch("asiai.engines.openai_compat.urlopen", return_value=_sse_response(chunks)),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 0.1, 1.0]
            engine = LlamaCppEngine("http://localhost:8080")
            result = engine.generate("model", "hi", 256)

        assert result.text == "hello"
        assert result.engine == "llamacpp"

    def test_generate_reasoning_content_counted_in_throughput(self):
        # Qwen3/3.5/3.6 with --jinja or preserve_thinking emits reasoning tokens
        # in delta.reasoning_content. TTFT must fire on first reasoning chunk;
        # text returned to user excludes reasoning; throughput counts both.
        chunks = [
            {"choices": [{"delta": {"reasoning_content": "Let me think..."}}]},
            {"choices": [{"delta": {"reasoning_content": " more thinking."}}]},
            {
                "choices": [{"delta": {"content": "Final answer"}}],
                "usage": {"completion_tokens": 50},
            },
        ]
        with (
            patch("asiai.engines.openai_compat.urlopen", return_value=_sse_response(chunks)),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 0.1, 0.2, 0.3, 1.1]
            engine = LlamaCppEngine("http://localhost:8080")
            result = engine.generate("qwen3.6", "hi", 512)

        assert result.text == "Final answer"
        assert result.ttft_ms == 100.0
        assert result.tokens_generated == 50
        assert result.tok_per_sec > 0

    def test_generate_reasoning_only_no_usage_estimates_throughput(self):
        # Edge case: model stops in thinking mode (no content), no usage block.
        # Fallback estimate must include reasoning chars to produce non-zero tok/s.
        chunks = [
            {"choices": [{"delta": {"reasoning_content": "x" * 200}}]},
        ]
        with (
            patch("asiai.engines.openai_compat.urlopen", return_value=_sse_response(chunks)),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 0.1, 1.1]
            engine = LlamaCppEngine("http://localhost:8080")
            result = engine.generate("qwen3.6", "hi", 512)

        assert result.text == ""
        assert result.tokens_generated >= 1
        assert result.tok_per_sec > 0

    def test_list_running(self):
        data = {"data": [{"id": "my-gguf-model"}]}
        props = {"default_generation_settings": {"n_ctx": 8192}}

        def mock_get(url, timeout=5):
            if "/v1/models" in url:
                return data, {}
            if "/props" in url:
                return props, {}
            return None, {}

        with (
            patch("asiai.engines.openai_compat.http_get_json", side_effect=mock_get),
            patch("asiai.engines.llamacpp.http_get_json", side_effect=mock_get),
        ):
            engine = LlamaCppEngine("http://localhost:8080")
            models = engine.list_running()
        assert len(models) == 1
        assert models[0].format == "GGUF"
        assert models[0].context_length == 8192

    def test_list_running_no_props(self):
        data = {"data": [{"id": "my-gguf-model"}]}

        def mock_get(url, timeout=5):
            if "/v1/models" in url:
                return data, {}
            return None, {}

        with (
            patch("asiai.engines.openai_compat.http_get_json", side_effect=mock_get),
            patch("asiai.engines.llamacpp.http_get_json", side_effect=mock_get),
        ):
            engine = LlamaCppEngine("http://localhost:8080")
            models = engine.list_running()
        assert len(models) == 1
        assert models[0].context_length == 0


class TestVllmMlxEngine:
    def test_name(self):
        engine = VllmMlxEngine("http://localhost:8000")
        assert engine.name == "vllm_mlx"

    def test_version(self):
        with patch(
            "asiai.engines.vllm_mlx.http_get_json",
            return_value=({"version": "0.1.2"}, {}),
        ):
            engine = VllmMlxEngine("http://localhost:8000")
            assert engine.version() == "0.1.2"

    def test_version_unreachable(self):
        with patch(
            "asiai.engines.vllm_mlx.http_get_json",
            return_value=(None, {}),
        ):
            engine = VllmMlxEngine("http://localhost:8000")
            assert engine.version() == ""

    def test_generate_uses_chat_mode(self):
        chunks = [
            {"choices": [{"delta": {"content": "fast"}}], "usage": {"completion_tokens": 200}},
        ]

        with (
            patch("asiai.engines.openai_compat.urlopen", return_value=_sse_response(chunks)),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 0.1, 0.5]
            engine = VllmMlxEngine("http://localhost:8000")
            result = engine.generate("model", "hi", 256)

        assert result.text == "fast"
        assert result.tok_per_sec == 500.0  # 200 / (0.5 - 0.1) generation only
        assert result.engine == "vllm_mlx"

    def test_list_running(self):
        data = {"data": [{"id": "mlx-model"}]}
        with patch("asiai.engines.openai_compat.http_get_json", return_value=(data, {})):
            engine = VllmMlxEngine("http://localhost:8000")
            models = engine.list_running()
        assert len(models) == 1
        assert models[0].format == "MLX"


class TestDetectCascade:
    """Full cascade detection tests for all 5 engines."""

    def test_detect_llamacpp(self):
        """llama.cpp: /v1/models OK, no LM Studio, /health OK."""

        def mock_get(url, timeout=5):
            if "/api/version" in url:
                return None, {}
            if "/v1/models" in url:
                return {"data": [{"id": "model"}]}, {}
            if "/lms/version" in url:
                return None, {}
            if "/health" in url:
                return {"status": "ok"}, {}
            if "/props" in url:
                return {"build_info": {"version": "b9999"}}, {}
            return None, {}

        with patch("asiai.engines.detect.http_get_json", side_effect=mock_get):
            engine, version = detect_engine_type("http://localhost:8080")

        assert engine == "llamacpp"
        assert version == "b9999"

    def test_detect_llamacpp_build_info_string(self):
        """llama.cpp: build_info as string 'b8180-d979f2b17' -> version '8180'."""

        def mock_get(url, timeout=5):
            if "/api/version" in url:
                return None, {}
            if "/v1/models" in url:
                return {"data": [{"id": "model"}]}, {}
            if "/lms/version" in url:
                return None, {}
            if "/health" in url:
                return {"status": "ok"}, {}
            if "/props" in url:
                return {"build_info": "b8180-d979f2b17"}, {}
            return None, {}

        with patch("asiai.engines.detect.http_get_json", side_effect=mock_get):
            engine, version = detect_engine_type("http://localhost:8080")

        assert engine == "llamacpp"
        assert version == "8180"

    def test_detect_omlx_via_owned_by(self):
        """oMLX: /v1/models with owned_by:'omlx' -> detected as omlx."""

        def mock_get(url, timeout=5):
            if "/api/version" in url:
                return None, {}
            if "/v1/models" in url:
                return {"data": [{"id": "Qwen3-Coder-30B", "owned_by": "omlx"}]}, {}
            if "/lms/version" in url:
                return None, {}
            if "/health" in url:
                return None, {}
            if "/admin/info" in url:
                return {"detail": "Not Found"}, {}
            return None, {}

        with patch("asiai.engines.detect.http_get_json", side_effect=mock_get):
            engine, version = detect_engine_type("http://localhost:8800")

        assert engine == "omlx"

    def test_detect_omlx_via_owned_by_with_version(self):
        """oMLX: owned_by:'omlx' + /admin/info version."""

        def mock_get(url, timeout=5):
            if "/api/version" in url:
                return None, {}
            if "/v1/models" in url:
                return {"data": [{"id": "model", "owned_by": "omlx"}]}, {}
            if "/lms/version" in url:
                return None, {}
            if "/health" in url:
                return None, {}
            if "/admin/info" in url:
                return {"version": "0.9.2"}, {}
            return None, {}

        with patch("asiai.engines.detect.http_get_json", side_effect=mock_get):
            engine, version = detect_engine_type("http://localhost:8800")

        assert engine == "omlx"
        assert version == "0.9.2"

    def test_detect_vllm_mlx(self):
        """vllm-mlx: /v1/models OK, no LM Studio, no /health, /version OK."""

        def mock_get(url, timeout=5):
            if "/api/version" in url:
                return None, {}
            if "/v1/models" in url:
                return {"data": [{"id": "model"}]}, {}
            if "/lms/version" in url:
                return None, {}
            if "/health" in url:
                return None, {}
            if "/version" in url:
                return {"version": "0.2.0"}, {}
            return None, {}

        with patch("asiai.engines.detect.http_get_json", side_effect=mock_get):
            engine, version = detect_engine_type("http://localhost:8000")

        assert engine == "vllm_mlx"
        assert version == "0.2.0"

    def test_detect_vllm_mlx_via_owned_by(self):
        """vllm-mlx: /v1/models with owned_by:'vllm-mlx', no /version endpoint."""

        def mock_get(url, timeout=5):
            if "/api/version" in url:
                return None, {}
            if "/v1/models" in url:
                return {"data": [{"id": "model", "owned_by": "vllm-mlx"}]}, {}
            if "/lms/version" in url:
                return None, {}
            if "/health" in url:
                return {"status": "healthy"}, {}
            if "/version" in url:
                return None, {}
            return None, {}

        with patch("asiai.engines.detect.http_get_json", side_effect=mock_get):
            engine, version = detect_engine_type("http://localhost:8000")

        assert engine == "vllm_mlx"
        assert version == ""

    def test_detect_mlxlm_fallback(self):
        """mlx-lm: /v1/models OK, no other markers -> fallback."""

        def mock_get(url, timeout=5):
            if "/api/version" in url:
                return None, {}
            if "/v1/models" in url:
                return {"data": [{"id": "model"}]}, {}
            if "/lms/version" in url:
                return None, {}
            if "/health" in url:
                return None, {}
            if "/version" in url:
                return None, {}
            return None, {}

        with (
            patch("asiai.engines.detect.http_get_json", side_effect=mock_get),
            patch("asiai.engines.detect.detect_port_process", return_value=""),
        ):
            engine, version = detect_engine_type("http://localhost:8080")

        assert engine == "mlxlm"

    def test_detect_via_lsof_fallback(self):
        """Process detection via lsof when no API markers match."""

        def mock_get(url, timeout=5):
            if "/api/version" in url:
                return None, {}
            if "/v1/models" in url:
                return {"data": []}, {}
            if "/lms/version" in url:
                return None, {}
            if "/health" in url:
                return None, {}
            if "/version" in url:
                return None, {}
            return None, {}

        with (
            patch("asiai.engines.detect.http_get_json", side_effect=mock_get),
            patch("asiai.engines.detect.detect_port_process", return_value="llamacpp"),
        ):
            engine, version = detect_engine_type("http://localhost:8080")

        assert engine == "llamacpp"

    def test_llamacpp_health_not_ok(self):
        """llama.cpp /health exists but status != ok -> not llamacpp."""

        def mock_get(url, timeout=5):
            if "/api/version" in url:
                return None, {}
            if "/v1/models" in url:
                return {"data": []}, {}
            if "/lms/version" in url:
                return None, {}
            if "/health" in url:
                return {"status": "loading"}, {}
            if "/version" in url:
                return None, {}
            return None, {}

        with (
            patch("asiai.engines.detect.http_get_json", side_effect=mock_get),
            patch("asiai.engines.detect.detect_port_process", return_value=""),
        ):
            engine, _ = detect_engine_type("http://localhost:8080")

        # Should fall through to mlxlm fallback
        assert engine == "mlxlm"


class TestDetectEnginesCascade:
    """Tests for the 3-layer detection cascade in detect_engines()."""

    def test_explicit_urls_bypass_config(self):
        """When urls are provided, config is not consulted."""

        def mock_detect(url):
            if url == "http://localhost:9999":
                return "ollama", "0.17"
            return "unknown", ""

        with (
            patch("asiai.engines.detect.detect_engine_type", side_effect=mock_detect),
        ):
            result = detect_engines(urls=["http://localhost:9999"])

        assert len(result) == 1
        assert result[0] == ("http://localhost:9999", "ollama", "0.17")

    def test_config_layer_returns_known_engines(self, tmp_path, monkeypatch):
        """L1: engines from config are probed first."""
        config_dir = str(tmp_path / "asiai")
        config_path = str(tmp_path / "asiai" / "engines.json")
        monkeypatch.setattr("asiai.engines.config.CONFIG_DIR", config_dir)
        monkeypatch.setattr("asiai.engines.config.CONFIG_PATH", config_path)

        # Pre-populate config with a non-standard port
        import json
        import os
        import time

        os.makedirs(config_dir, exist_ok=True)
        config = {
            "version": 1,
            "engines": [
                {
                    "url": "http://localhost:8800",
                    "engine": "omlx",
                    "version": "0.9",
                    "last_seen": int(time.time()),
                    "source": "auto",
                    "label": "",
                }
            ],
        }
        with open(config_path, "w") as f:
            json.dump(config, f)

        def mock_detect(url):
            if url == "http://localhost:8800":
                return "omlx", "0.9.2"
            return "unknown", ""

        with (
            patch("asiai.engines.detect.detect_engine_type", side_effect=mock_detect),
            patch("asiai.engines.detect.discover_via_processes", return_value=[]),
        ):
            result = detect_engines()

        urls = [r[0] for r in result]
        assert "http://localhost:8800" in urls

    def test_dedup_across_layers(self, tmp_path, monkeypatch):
        """An engine found in L1 should not be duplicated in L2."""
        config_dir = str(tmp_path / "asiai")
        config_path = str(tmp_path / "asiai" / "engines.json")
        monkeypatch.setattr("asiai.engines.config.CONFIG_DIR", config_dir)
        monkeypatch.setattr("asiai.engines.config.CONFIG_PATH", config_path)

        import json
        import os
        import time

        os.makedirs(config_dir, exist_ok=True)
        config = {
            "version": 1,
            "engines": [
                {
                    "url": "http://localhost:11434",
                    "engine": "ollama",
                    "version": "0.17",
                    "last_seen": int(time.time()),
                    "source": "auto",
                    "label": "",
                }
            ],
        }
        with open(config_path, "w") as f:
            json.dump(config, f)

        def mock_detect(url):
            if url == "http://localhost:11434":
                return "ollama", "0.17"
            return "unknown", ""

        with (
            patch("asiai.engines.detect.detect_engine_type", side_effect=mock_detect),
            patch("asiai.engines.detect.discover_via_processes", return_value=[]),
        ):
            result = detect_engines()

        ollama_entries = [r for r in result if r[1] == "ollama"]
        assert len(ollama_entries) == 1

    def test_process_detection_finds_odd_port(self, tmp_path, monkeypatch):
        """L3: process detection discovers an engine on a non-default port."""
        config_dir = str(tmp_path / "asiai")
        config_path = str(tmp_path / "asiai" / "engines.json")
        monkeypatch.setattr("asiai.engines.config.CONFIG_DIR", config_dir)
        monkeypatch.setattr("asiai.engines.config.CONFIG_PATH", config_path)

        def mock_detect(url):
            if url == "http://localhost:8800":
                return "omlx", "0.9"
            return "unknown", ""

        with (
            patch("asiai.engines.detect.detect_engine_type", side_effect=mock_detect),
            patch(
                "asiai.engines.detect.discover_via_processes",
                return_value=[("omlx", 8800)],
            ),
        ):
            result = detect_engines()

        urls = [r[0] for r in result]
        assert "http://localhost:8800" in urls

    def test_explicit_urls_no_persist(self, tmp_path, monkeypatch):
        """Explicit --url should not write to config."""
        config_dir = str(tmp_path / "asiai")
        config_path = str(tmp_path / "asiai" / "engines.json")
        monkeypatch.setattr("asiai.engines.config.CONFIG_DIR", config_dir)
        monkeypatch.setattr("asiai.engines.config.CONFIG_PATH", config_path)

        def mock_detect(url):
            return "ollama", "0.17"

        with patch("asiai.engines.detect.detect_engine_type", side_effect=mock_detect):
            detect_engines(urls=["http://localhost:11434"])

        from asiai.engines.config import load_config

        config = load_config()
        assert len(config["engines"]) == 0


class TestDiscoverViaProcesses:
    def test_returns_empty_on_ps_failure(self):
        with patch(
            "asiai.engines.detect.subprocess.run",
            side_effect=OSError("no ps"),
        ):
            result = discover_via_processes()
        assert result == []

    def test_finds_process_with_port(self):
        ps_output = "  PID COMMAND\n  123 /opt/homebrew/opt/omlx/bin/omlx serve --port 8800\n"
        lsof_output = (
            "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
            "omlx    123 user 5u  IPv4 0x1234 0t0  TCP *:8800 (LISTEN)\n"
        )

        mock_ps = MagicMock()
        mock_ps.stdout = ps_output
        mock_lsof = MagicMock()
        mock_lsof.stdout = lsof_output

        def mock_run(cmd, **kwargs):
            if cmd[0] == "ps":
                return mock_ps
            if cmd[0] == "lsof":
                return mock_lsof
            return MagicMock(stdout="")

        with patch("asiai.engines.detect.subprocess.run", side_effect=mock_run):
            result = discover_via_processes()

        assert ("omlx", 8800) in result

    def test_finds_python_wrapped_engine(self):
        """Python process running omlx via full command line."""
        ps_output = (
            "  PID COMMAND\n"
            "  83180 /opt/homebrew/.../Python /opt/homebrew/opt/omlx/bin/omlx serve --port 8800\n"
        )
        lsof_output = (
            "COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
            "Python  83180 user 8u  IPv4 0x1234 0t0  TCP *:8800 (LISTEN)\n"
        )

        mock_ps = MagicMock()
        mock_ps.stdout = ps_output
        mock_lsof = MagicMock()
        mock_lsof.stdout = lsof_output

        def mock_run(cmd, **kwargs):
            if cmd[0] == "ps":
                return mock_ps
            if cmd[0] == "lsof":
                return mock_lsof
            return MagicMock(stdout="")

        with patch("asiai.engines.detect.subprocess.run", side_effect=mock_run):
            result = discover_via_processes()

        assert ("omlx", 8800) in result
