"""Tests for engine detection and adapters."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from asiai.engines.detect import (
    detect_engine_type,
    detect_port_process,
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
        mock = self._mock_get({"/api/ps": ps_response})
        with patch("asiai.engines.ollama.http_get_json", side_effect=mock):
            engine = OllamaEngine("http://localhost:11434")
            models = engine.list_running()

        assert len(models) == 1
        assert models[0].name == "qwen3-coder:30b"
        assert models[0].size_vram == 20_000_000_000
        assert models[0].quantization == "Q4_K_M"

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


class TestOllamaGenerate:
    def test_generate_success(self):
        gen_response = {
            "response": "class BST:\n    pass",
            "eval_count": 150,
            "eval_duration": 3_000_000_000,
            "prompt_eval_duration": 800_000_000,
            "total_duration": 4_000_000_000,
        }

        def mock_post(url, data, timeout=300):
            if "/api/generate" in url:
                return gen_response, {}
            return None, {}

        with patch("asiai.engines.ollama.http_post_json", side_effect=mock_post):
            engine = OllamaEngine("http://localhost:11434")
            result = engine.generate("test-model", "Write a BST", 512)

        assert result.tokens_generated == 150
        assert result.tok_per_sec == 50.0
        assert result.ttft_ms == 800.0
        assert result.error == ""

    def test_generate_error(self):
        def mock_post(url, data, timeout=300):
            return {"error": "model not found"}, {}

        with patch("asiai.engines.ollama.http_post_json", side_effect=mock_post):
            engine = OllamaEngine("http://localhost:11434")
            result = engine.generate("bad-model", "hello", 512)

        assert result.error == "model not found"

    def test_generate_connection_failed(self):
        with patch("asiai.engines.ollama.http_post_json", return_value=(None, {})):
            engine = OllamaEngine("http://localhost:11434")
            result = engine.generate("model", "hello", 512)

        assert result.error == "request failed"


class TestLMStudioGenerate:
    def test_generate_success(self):
        gen_response = {
            "choices": [{"text": "def hello(): pass"}],
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
            mock_time.monotonic.side_effect = [0.0, 2.0]  # 2 seconds elapsed
            engine = LMStudioEngine("http://localhost:1234")
            result = engine.generate("test-model", "Write code", 512)

        assert result.tokens_generated == 80
        assert result.tok_per_sec == 40.0
        assert result.ttft_ms == 0.0  # N/A for LM Studio
        assert result.error == ""

    def test_generate_error(self):
        gen_response = {"error": {"message": "model not loaded"}}

        with (
            patch("asiai.engines.openai_compat.http_post_json", return_value=(gen_response, {})),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 0.1]
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
        gen_response = {
            "choices": [{"message": {"role": "assistant", "content": "def hello(): pass"}}],
            "usage": {"completion_tokens": 80},
        }

        def mock_post(url, data, timeout=300):
            if "/v1/chat/completions" in url:
                return gen_response, {}
            return None, {}

        with (
            patch("asiai.engines.openai_compat.http_post_json", side_effect=mock_post),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 2.0]
            engine = MlxLmEngine("http://localhost:8080")
            result = engine.generate("test-model", "Write code", 512)

        assert result.tokens_generated == 80
        assert result.tok_per_sec == 40.0
        assert result.text == "def hello(): pass"
        assert result.error == ""

    def test_generate_error(self):
        gen_response = {"error": {"message": "model not loaded"}}

        with (
            patch("asiai.engines.openai_compat.http_post_json", return_value=(gen_response, {})),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 0.1]
            engine = MlxLmEngine("http://localhost:8080")
            result = engine.generate("bad-model", "hello", 512)

        assert "model not loaded" in result.error

    def test_generate_connection_failed(self):
        with (
            patch("asiai.engines.openai_compat.http_post_json", return_value=(None, {})),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 0.1]
            engine = MlxLmEngine("http://localhost:8080")
            result = engine.generate("model", "hello", 512)

        assert result.error == "request failed"


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
        gen_response = {
            "choices": [{"message": {"role": "assistant", "content": "hello"}}],
            "usage": {"completion_tokens": 10},
        }

        with (
            patch("asiai.engines.openai_compat.http_post_json", return_value=(gen_response, {})),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 1.0]
            engine = LlamaCppEngine("http://localhost:8080")
            result = engine.generate("model", "hi", 256)

        assert result.text == "hello"
        assert result.engine == "llamacpp"

    def test_list_running(self):
        data = {"data": [{"id": "my-gguf-model"}]}
        with patch("asiai.engines.openai_compat.http_get_json", return_value=(data, {})):
            engine = LlamaCppEngine("http://localhost:8080")
            models = engine.list_running()
        assert len(models) == 1
        assert models[0].format == "GGUF"


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
        gen_response = {
            "choices": [{"message": {"role": "assistant", "content": "fast"}}],
            "usage": {"completion_tokens": 200},
        }

        with (
            patch("asiai.engines.openai_compat.http_post_json", return_value=(gen_response, {})),
            patch("asiai.engines.openai_compat.time") as mock_time,
        ):
            mock_time.monotonic.side_effect = [0.0, 0.5]
            engine = VllmMlxEngine("http://localhost:8000")
            result = engine.generate("model", "hi", 256)

        assert result.text == "fast"
        assert result.tok_per_sec == 400.0
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
