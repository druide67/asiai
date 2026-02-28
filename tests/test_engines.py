"""Tests for engine detection and adapters."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from asiai.engines.base import InferenceEngine, ModelInfo
from asiai.engines.detect import detect_engine_type, http_get_json
from asiai.engines.lmstudio import LMStudioEngine
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
