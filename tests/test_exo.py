"""Tests for Exo distributed inference engine adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from asiai.engines.exo import ExoEngine


class TestExoEngine:
    def test_name(self):
        engine = ExoEngine("http://localhost:52415")
        assert engine.name == "exo"

    def test_model_format(self):
        engine = ExoEngine("http://localhost:52415")
        assert engine._model_format == "MLX"

    def test_generate_endpoint(self):
        engine = ExoEngine("http://localhost:52415")
        assert engine._generate_endpoint == "/v1/chat/completions"

    def test_version_from_api(self):
        with patch(
            "asiai.engines.exo.http_get_json",
            return_value=({"version": "0.1.0"}, {}),
        ):
            engine = ExoEngine("http://localhost:52415")
            assert engine.version() == "0.1.0"

    def test_version_from_cli(self):
        with patch(
            "asiai.engines.exo.http_get_json",
            return_value=(None, {}),
        ):
            mock_result = MagicMock()
            mock_result.stdout = "exo 0.1.0\n"
            mock_result.stderr = ""
            with patch("asiai.engines.exo.subprocess.run", return_value=mock_result):
                engine = ExoEngine("http://localhost:52415")
                assert engine.version() == "0.1.0"

    def test_version_fallback(self):
        with (
            patch(
                "asiai.engines.exo.http_get_json",
                return_value=(None, {}),
            ),
            patch(
                "asiai.engines.exo.subprocess.run",
                side_effect=Exception("not found"),
            ),
        ):
            engine = ExoEngine("http://localhost:52415")
            assert engine.version() == ""

    def test_is_reachable_inherited(self):
        """Exo inherits OpenAI-compatible is_reachable via /v1/models."""
        with patch(
            "asiai.engines.openai_compat.http_get_json",
            return_value=({"data": [{"id": "llama3"}]}, {}),
        ):
            engine = ExoEngine("http://localhost:52415")
            assert engine.is_reachable()

    def test_is_not_reachable(self):
        with patch(
            "asiai.engines.openai_compat.http_get_json",
            return_value=(None, {}),
        ):
            engine = ExoEngine("http://localhost:52415")
            assert not engine.is_reachable()

    def test_list_running_with_topology(self):
        """list_running enriches models with cluster topology info."""
        models_data = {"data": [{"id": "llama3-70b"}]}
        topology_data = {
            "nodes": [
                {"id": "node1", "device": "M1 Max"},
                {"id": "node2", "device": "M4 Pro"},
            ]
        }

        def mock_get_openai(url, timeout=5):
            if "/v1/models" in url:
                return models_data, {}
            return None, {}

        def mock_get_exo(url, timeout=5):
            if "/api/topology" in url:
                return topology_data, {}
            return None, {}

        with (
            patch("asiai.engines.openai_compat.http_get_json", side_effect=mock_get_openai),
            patch("asiai.engines.exo.http_get_json", side_effect=mock_get_exo),
        ):
            engine = ExoEngine("http://localhost:52415")
            models = engine.list_running()

        assert len(models) == 1
        assert models[0].name == "llama3-70b"
        assert models[0].format == "MLX"

    def test_list_running_without_topology(self):
        """list_running works when topology endpoint returns None."""
        models_data = {"data": [{"id": "qwen3-30b"}]}

        def mock_get_openai(url, timeout=5):
            if "/v1/models" in url:
                return models_data, {}
            return None, {}

        with (
            patch("asiai.engines.openai_compat.http_get_json", side_effect=mock_get_openai),
            patch("asiai.engines.exo.http_get_json", return_value=(None, {})),
        ):
            engine = ExoEngine("http://localhost:52415")
            models = engine.list_running()

        assert len(models) == 1
        assert models[0].name == "qwen3-30b"
        assert models[0].format == "MLX"

    def test_list_running_empty(self):
        """list_running returns [] when super() returns no models."""
        with (
            patch(
                "asiai.engines.openai_compat.http_get_json",
                return_value=({"data": []}, {}),
            ),
            patch("asiai.engines.exo.http_get_json", return_value=(None, {})),
        ):
            engine = ExoEngine("http://localhost:52415")
            models = engine.list_running()

        assert models == []
