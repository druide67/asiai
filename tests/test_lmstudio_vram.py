"""Tests for LM Studio VRAM enrichment via lms CLI."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from asiai.engines.lmstudio import LMStudioEngine


class TestParseLmsPs:
    """Tests for _parse_lms_ps static method."""

    def test_empty_list(self):
        assert LMStudioEngine._parse_lms_ps([]) == {}

    def test_not_a_list(self):
        assert LMStudioEngine._parse_lms_ps({}) == {}

    def test_single_model(self):
        data = [
            {
                "type": "llm",
                "modelKey": "gemma-2-9b",
                "path": "mlx-community/gemma-2-9b-8bit",
                "sizeBytes": 9837652042,
                "indexedModelIdentifier": "mlx-community/gemma-2-9b-8bit",
            }
        ]
        result = LMStudioEngine._parse_lms_ps(data)
        assert result["mlx-community/gemma-2-9b-8bit"] == 9837652042
        assert result["gemma-2-9b"] == 9837652042

    def test_multiple_models(self):
        data = [
            {"modelKey": "model-a", "path": "org/model-a", "sizeBytes": 1000},
            {"modelKey": "model-b", "path": "org/model-b", "sizeBytes": 2000},
        ]
        result = LMStudioEngine._parse_lms_ps(data)
        assert result["org/model-a"] == 1000
        assert result["org/model-b"] == 2000

    def test_missing_size_bytes(self):
        data = [{"modelKey": "model-a", "path": "org/model-a"}]
        result = LMStudioEngine._parse_lms_ps(data)
        assert result["org/model-a"] == 0

    def test_invalid_entries_skipped(self):
        data = [None, "string", {"modelKey": "ok", "sizeBytes": 100}]
        result = LMStudioEngine._parse_lms_ps(data)
        assert result["ok"] == 100


class TestGetVramFromLms:
    """Tests for _get_vram_from_lms method."""

    def test_lms_not_found(self):
        engine = LMStudioEngine("http://localhost:1234")
        with patch("asiai.engines.lmstudio.os.path.isfile", return_value=False):
            assert engine._get_vram_from_lms() == {}

    def test_lms_success(self):
        engine = LMStudioEngine("http://localhost:1234")
        lms_output = json.dumps([
            {"modelKey": "gemma-2-9b", "path": "mlx-community/gemma-2-9b-8bit",
             "sizeBytes": 9837652042}
        ])
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = lms_output

        with (
            patch("asiai.engines.lmstudio.os.path.isfile", return_value=True),
            patch("asiai.engines.lmstudio.subprocess.run", return_value=mock_result),
        ):
            result = engine._get_vram_from_lms()

        assert result["mlx-community/gemma-2-9b-8bit"] == 9837652042

    def test_lms_returncode_error(self):
        engine = LMStudioEngine("http://localhost:1234")
        mock_result = MagicMock()
        mock_result.returncode = 1

        with (
            patch("asiai.engines.lmstudio.os.path.isfile", return_value=True),
            patch("asiai.engines.lmstudio.subprocess.run", return_value=mock_result),
        ):
            assert engine._get_vram_from_lms() == {}

    def test_lms_timeout(self):
        import subprocess

        engine = LMStudioEngine("http://localhost:1234")

        with (
            patch("asiai.engines.lmstudio.os.path.isfile", return_value=True),
            patch(
                "asiai.engines.lmstudio.subprocess.run",
                side_effect=subprocess.TimeoutExpired("lms", 10),
            ),
        ):
            assert engine._get_vram_from_lms() == {}

    def test_lms_invalid_json(self):
        engine = LMStudioEngine("http://localhost:1234")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json"

        with (
            patch("asiai.engines.lmstudio.os.path.isfile", return_value=True),
            patch("asiai.engines.lmstudio.subprocess.run", return_value=mock_result),
        ):
            assert engine._get_vram_from_lms() == {}

    def test_lms_ps_empty_falls_back_to_ls(self):
        """When lms ps returns [] (lazy loading), fallback to lms ls."""
        engine = LMStudioEngine("http://localhost:1234")
        ps_result = MagicMock()
        ps_result.returncode = 0
        ps_result.stdout = "[]"

        ls_output = json.dumps([
            {"modelKey": "gemma-2-9b", "path": "mlx-community/gemma-2-9b-8bit",
             "sizeBytes": 9837652042}
        ])
        ls_result = MagicMock()
        ls_result.returncode = 0
        ls_result.stdout = ls_output

        def mock_run(cmd, **_kw):
            if "ps" in cmd:
                return ps_result
            return ls_result

        with (
            patch("asiai.engines.lmstudio.os.path.isfile", return_value=True),
            patch("asiai.engines.lmstudio.subprocess.run", side_effect=mock_run),
        ):
            result = engine._get_vram_from_lms()

        assert result["mlx-community/gemma-2-9b-8bit"] == 9837652042

    def test_lms_ps_has_data_skips_ls(self):
        """When lms ps returns data, don't call lms ls."""
        engine = LMStudioEngine("http://localhost:1234")
        ps_output = json.dumps([
            {"modelKey": "gemma-2-9b", "path": "mlx-community/gemma-2-9b-8bit",
             "sizeBytes": 9837652042}
        ])
        ps_result = MagicMock()
        ps_result.returncode = 0
        ps_result.stdout = ps_output

        call_args = []

        def mock_run(cmd, **_kw):
            call_args.append(cmd)
            return ps_result

        with (
            patch("asiai.engines.lmstudio.os.path.isfile", return_value=True),
            patch("asiai.engines.lmstudio.subprocess.run", side_effect=mock_run),
        ):
            result = engine._get_vram_from_lms()

        assert result["mlx-community/gemma-2-9b-8bit"] == 9837652042
        # Only lms ps should have been called
        assert len(call_args) == 1
        assert "ps" in call_args[0]

    def test_lms_ls_fallback_error(self):
        """When both lms ps returns [] and lms ls fails, return empty."""
        engine = LMStudioEngine("http://localhost:1234")
        ps_result = MagicMock()
        ps_result.returncode = 0
        ps_result.stdout = "[]"

        ls_result = MagicMock()
        ls_result.returncode = 1

        def mock_run(cmd, **_kw):
            if "ps" in cmd:
                return ps_result
            return ls_result

        with (
            patch("asiai.engines.lmstudio.os.path.isfile", return_value=True),
            patch("asiai.engines.lmstudio.subprocess.run", side_effect=mock_run),
        ):
            assert engine._get_vram_from_lms() == {}


class TestListRunningVram:
    """Tests for list_running with VRAM enrichment."""

    def test_enriches_matching_model(self):
        engine = LMStudioEngine("http://localhost:1234")
        api_response = {"data": [{"id": "mlx-community/gemma-2-9b-8bit"}]}

        with (
            patch("asiai.engines.openai_compat.http_get_json",
                   return_value=(api_response, {})),
            patch.object(engine, "_get_vram_from_lms",
                         return_value={"mlx-community/gemma-2-9b-8bit": 9837652042}),
        ):
            models = engine.list_running()

        assert len(models) == 1
        assert models[0].name == "mlx-community/gemma-2-9b-8bit"
        assert models[0].size_vram == 9837652042

    def test_no_lms_keeps_zero_vram(self):
        engine = LMStudioEngine("http://localhost:1234")
        api_response = {"data": [{"id": "mlx-community/gemma-2-9b-8bit"}]}

        with (
            patch("asiai.engines.openai_compat.http_get_json",
                   return_value=(api_response, {})),
            patch.object(engine, "_get_vram_from_lms", return_value={}),
        ):
            models = engine.list_running()

        assert len(models) == 1
        assert models[0].size_vram == 0

    def test_no_models_skips_lms(self):
        engine = LMStudioEngine("http://localhost:1234")

        with (
            patch("asiai.engines.openai_compat.http_get_json",
                   return_value=(None, {})),
            patch.object(engine, "_get_vram_from_lms") as mock_lms,
        ):
            models = engine.list_running()

        assert models == []
        mock_lms.assert_not_called()
