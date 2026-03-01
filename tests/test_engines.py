"""Tests for engine detection and adapters."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from asiai.engines.detect import detect_engine_type, http_get_json, http_post_json
from asiai.engines.lmstudio import LMStudioEngine
from asiai.engines.mlxlm import MlxLmEngine
from asiai.engines.ollama import OllamaEngine


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

        with patch("asiai.engines.lmstudio.http_post_json", side_effect=mock_post), \
             patch("asiai.engines.lmstudio.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 2.0]  # 2 seconds elapsed
            engine = LMStudioEngine("http://localhost:1234")
            result = engine.generate("test-model", "Write code", 512)

        assert result.tokens_generated == 80
        assert result.tok_per_sec == 40.0
        assert result.ttft_ms == 0.0  # N/A for LM Studio
        assert result.error == ""

    def test_generate_error(self):
        gen_response = {"error": {"message": "model not loaded"}}

        with patch("asiai.engines.lmstudio.http_post_json", return_value=(gen_response, {})), \
             patch("asiai.engines.lmstudio.time") as mock_time:
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

        with patch("asiai.engines.lmstudio.http_get_json", side_effect=mock_get):
            engine = LMStudioEngine("http://localhost:1234")
            models = engine.list_running()

        assert len(models) == 2
        assert models[0].name == "qwen-2.5-32b-instruct"
        assert models[0].format == "MLX"


class TestMlxLmEngine:
    def test_is_reachable(self):
        with patch(
            "asiai.engines.mlxlm.http_get_json",
            return_value=({"data": []}, {}),
        ):
            engine = MlxLmEngine("http://localhost:8080")
            assert engine.is_reachable()

    def test_is_not_reachable(self):
        with patch(
            "asiai.engines.mlxlm.http_get_json",
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

        with patch("asiai.engines.mlxlm.http_get_json", side_effect=mock_get):
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

        with patch("asiai.engines.mlxlm.http_post_json", side_effect=mock_post), \
             patch("asiai.engines.mlxlm.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 2.0]
            engine = MlxLmEngine("http://localhost:8080")
            result = engine.generate("test-model", "Write code", 512)

        assert result.tokens_generated == 80
        assert result.tok_per_sec == 40.0
        assert result.text == "def hello(): pass"
        assert result.error == ""

    def test_generate_error(self):
        gen_response = {"error": {"message": "model not loaded"}}

        with patch("asiai.engines.mlxlm.http_post_json", return_value=(gen_response, {})), \
             patch("asiai.engines.mlxlm.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.1]
            engine = MlxLmEngine("http://localhost:8080")
            result = engine.generate("bad-model", "hello", 512)

        assert "model not loaded" in result.error

    def test_generate_connection_failed(self):
        with patch("asiai.engines.mlxlm.http_post_json", return_value=(None, {})), \
             patch("asiai.engines.mlxlm.time") as mock_time:
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
