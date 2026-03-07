"""Tests for the doctor diagnostic module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from asiai.doctor import (
    CheckResult,
    _check_apple_silicon,
    _check_db,
    _check_llamacpp,
    _check_lmstudio,
    _check_memory_pressure,
    _check_mlxlm,
    _check_ollama,
    _check_ram,
    _check_thermal,
    _check_vllm_mlx,
    run_checks,
)


class TestCheckAppleSilicon:
    def test_arm64(self):
        with (
            patch("asiai.doctor.platform") as mock_platform,
            patch("asiai.doctor.collect_machine_info", return_value="Mac14,2 — Apple M2"),
        ):
            mock_platform.machine.return_value = "arm64"
            result = _check_apple_silicon()
        assert result.status == "ok"
        assert "M2" in result.message

    def test_x86(self):
        with patch("asiai.doctor.platform") as mock_platform:
            mock_platform.machine.return_value = "x86_64"
            result = _check_apple_silicon()
        assert result.status == "fail"
        assert "x86_64" in result.message


class TestCheckRam:
    def test_sufficient_ram(self):
        mock_mem = MagicMock()
        mock_mem.total = 64 * 1024**3  # 64 GB
        mock_mem.used = 32 * 1024**3
        with patch("asiai.doctor.collect_memory", return_value=mock_mem):
            result = _check_ram()
        assert result.status == "ok"
        assert "64 GB" in result.message

    def test_low_ram(self):
        mock_mem = MagicMock()
        mock_mem.total = 8 * 1024**3  # 8 GB
        mock_mem.used = 4 * 1024**3
        with patch("asiai.doctor.collect_memory", return_value=mock_mem):
            result = _check_ram()
        assert result.status == "warn"


class TestCheckMemoryPressure:
    def test_normal(self):
        mock_mem = MagicMock()
        mock_mem.pressure = "normal"
        with patch("asiai.doctor.collect_memory", return_value=mock_mem):
            result = _check_memory_pressure()
        assert result.status == "ok"

    def test_warn(self):
        mock_mem = MagicMock()
        mock_mem.pressure = "warn"
        with patch("asiai.doctor.collect_memory", return_value=mock_mem):
            result = _check_memory_pressure()
        assert result.status == "warn"

    def test_critical(self):
        mock_mem = MagicMock()
        mock_mem.pressure = "critical"
        with patch("asiai.doctor.collect_memory", return_value=mock_mem):
            result = _check_memory_pressure()
        assert result.status == "fail"


class TestCheckThermal:
    def test_nominal(self):
        mock_thermal = MagicMock()
        mock_thermal.level = "nominal"
        mock_thermal.speed_limit = 100
        with patch("asiai.doctor.collect_thermal", return_value=mock_thermal):
            result = _check_thermal()
        assert result.status == "ok"

    def test_fair(self):
        mock_thermal = MagicMock()
        mock_thermal.level = "fair"
        mock_thermal.speed_limit = 85
        with patch("asiai.doctor.collect_thermal", return_value=mock_thermal):
            result = _check_thermal()
        assert result.status == "warn"

    def test_critical(self):
        mock_thermal = MagicMock()
        mock_thermal.level = "critical"
        mock_thermal.speed_limit = 30
        with patch("asiai.doctor.collect_thermal", return_value=mock_thermal):
            result = _check_thermal()
        assert result.status == "fail"


class TestCheckOllama:
    def test_not_installed(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("asiai.doctor.subprocess") as mock_sub:
            mock_sub.run.return_value = mock_result
            result = _check_ollama()
        assert result.status == "fail"
        assert "not installed" in result.message

    def test_installed_not_running(self):
        mock_which = MagicMock()
        mock_which.returncode = 0

        def mock_subprocess_run(cmd, **kwargs):
            if cmd[0] == "which":
                return mock_which
            return MagicMock(returncode=0)

        with (
            patch("asiai.doctor.subprocess") as mock_sub,
            patch("asiai.doctor.http_get_json", return_value=(None, {})),
        ):
            mock_sub.run.side_effect = mock_subprocess_run
            result = _check_ollama()
        assert result.status == "warn"
        assert "not running" in result.message

    def test_running_with_models(self):
        mock_which = MagicMock()
        mock_which.returncode = 0

        def mock_get(url, timeout=5):
            if "/api/version" in url:
                return {"version": "0.17.4"}, {}
            if "/api/ps" in url:
                return {"models": [{"name": "gemma2:9b"}]}, {}
            return None, {}

        with (
            patch("asiai.doctor.subprocess") as mock_sub,
            patch("asiai.doctor.http_get_json", side_effect=mock_get),
        ):
            mock_sub.run.return_value = mock_which
            result = _check_ollama()
        assert result.status == "ok"
        assert "gemma2:9b" in result.message


class TestCheckLMStudio:
    def test_not_installed(self):
        with patch("asiai.doctor.os.path.exists", return_value=False):
            result = _check_lmstudio()
        assert result.status == "fail"
        assert "not installed" in result.message

    def test_installed_not_running(self):
        with (
            patch("asiai.doctor.os.path.exists", return_value=True),
            patch("asiai.doctor.http_get_json", return_value=(None, {})),
        ):
            result = _check_lmstudio()
        assert result.status == "warn"
        assert "not running" in result.message

    def test_running_with_models(self):
        def mock_get(url, timeout=5):
            if "/v1/models" in url:
                return {"data": [{"id": "gemma-2-9b"}]}, {"x-lm-studio-version": "0.4.6"}
            return None, {}

        with (
            patch("asiai.doctor.os.path.exists", return_value=True),
            patch("asiai.doctor.http_get_json", side_effect=mock_get),
        ):
            result = _check_lmstudio()
        assert result.status == "ok"
        assert "gemma-2-9b" in result.message


class TestCheckMlxLm:
    def test_not_installed(self):
        mock_result = MagicMock()
        mock_result.stdout = ""
        with patch("asiai.doctor.subprocess") as mock_sub:
            mock_sub.run.return_value = mock_result
            result = _check_mlxlm()
        assert result.status == "fail"
        assert "not installed" in result.message

    def test_installed_not_running(self):
        mock_result = MagicMock()
        mock_result.stdout = "mlx-lm 0.30.7"
        with (
            patch("asiai.doctor.subprocess") as mock_sub,
            patch("asiai.doctor.http_get_json", return_value=(None, {})),
        ):
            mock_sub.run.return_value = mock_result
            result = _check_mlxlm()
        assert result.status == "warn"
        assert "not running" in result.message

    def test_running_with_models(self):
        mock_result = MagicMock()
        mock_result.stdout = "mlx-lm 0.30.7"

        def mock_get(url, timeout=5):
            if "/v1/models" in url:
                return {"data": [{"id": "mlx-community/gemma-2-9b-4bit"}]}, {}
            return None, {}

        with (
            patch("asiai.doctor.subprocess") as mock_sub,
            patch("asiai.doctor.http_get_json", side_effect=mock_get),
        ):
            mock_sub.run.return_value = mock_result
            result = _check_mlxlm()
        assert result.status == "ok"
        assert "gemma-2-9b" in result.message


class TestCheckLlamaCpp:
    def test_not_installed(self):
        mock_result = MagicMock()
        mock_result.stdout = ""
        with patch("asiai.doctor.subprocess") as mock_sub:
            mock_sub.run.return_value = mock_result
            result = _check_llamacpp()
        assert result.status == "fail"
        assert "not installed" in result.message

    def test_installed_not_running(self):
        mock_result = MagicMock()
        mock_result.stdout = "llama.cpp 0.0.4567"
        with (
            patch("asiai.doctor.subprocess") as mock_sub,
            patch("asiai.doctor.http_get_json", return_value=(None, {})),
        ):
            mock_sub.run.return_value = mock_result
            result = _check_llamacpp()
        assert result.status == "warn"
        assert "not running" in result.message

    def test_running(self):
        mock_result = MagicMock()
        mock_result.stdout = "llama.cpp 0.0.4567"

        def mock_get(url, timeout=5):
            if "/health" in url:
                return {"status": "ok"}, {}
            if "/v1/models" in url:
                return {"data": [{"id": "my-model.gguf"}]}, {}
            return None, {}

        with (
            patch("asiai.doctor.subprocess") as mock_sub,
            patch("asiai.doctor.http_get_json", side_effect=mock_get),
        ):
            mock_sub.run.return_value = mock_result
            result = _check_llamacpp()
        assert result.status == "ok"
        assert "my-model" in result.message


class TestCheckVllmMlx:
    def test_not_installed(self):
        mock_result = MagicMock()
        mock_result.stdout = ""
        with patch("asiai.doctor.subprocess") as mock_sub:
            mock_sub.run.return_value = mock_result
            result = _check_vllm_mlx()
        assert result.status == "fail"
        assert "not installed" in result.message

    def test_installed_not_running(self):
        mock_result = MagicMock()
        mock_result.stdout = "Name: vllm-mlx\nVersion: 0.1.2\n"
        with (
            patch("asiai.doctor.subprocess") as mock_sub,
            patch("asiai.doctor.http_get_json", return_value=(None, {})),
        ):
            mock_sub.run.return_value = mock_result
            result = _check_vllm_mlx()
        assert result.status == "warn"
        assert "not running" in result.message

    def test_running_with_models(self):
        mock_result = MagicMock()
        mock_result.stdout = "Name: vllm-mlx\nVersion: 0.1.2\n"

        def mock_get(url, timeout=5):
            if "/version" in url and "/v1" not in url:
                return {"version": "0.1.2"}, {}
            if "/v1/models" in url:
                return {"data": [{"id": "mlx-model"}]}, {}
            return None, {}

        with (
            patch("asiai.doctor.subprocess") as mock_sub,
            patch("asiai.doctor.http_get_json", side_effect=mock_get),
        ):
            mock_sub.run.return_value = mock_result
            result = _check_vllm_mlx()
        assert result.status == "ok"
        assert "mlx-model" in result.message


class TestCheckDb:
    def test_db_not_exists(self):
        result = _check_db("/nonexistent/path/metrics.db")
        assert result.status == "warn"
        assert "does not exist" in result.message

    def test_db_exists_with_data(self, tmp_path):
        import sqlite3
        import time

        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE metrics (ts INTEGER PRIMARY KEY, cpu_load_1 REAL)")
        conn.execute(
            "INSERT INTO metrics (ts, cpu_load_1) VALUES (?, ?)",
            (int(time.time()) - 60, 1.5),
        )
        conn.commit()
        conn.close()

        result = _check_db(db_path)
        assert result.status == "ok"

    def test_db_exists_empty(self, tmp_path):
        import sqlite3

        db_path = str(tmp_path / "empty.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE metrics (ts INTEGER PRIMARY KEY, cpu_load_1 REAL)")
        conn.commit()
        conn.close()

        result = _check_db(db_path)
        assert result.status == "warn"
        assert "no data" in result.message


class TestRunChecks:
    def test_returns_all_categories(self):
        with (
            patch("asiai.doctor._check_apple_silicon") as m1,
            patch("asiai.doctor._check_ram") as m2,
            patch("asiai.doctor._check_memory_pressure") as m3,
            patch("asiai.doctor._check_thermal") as m4,
            patch("asiai.doctor._check_ollama") as m5,
            patch("asiai.doctor._check_lmstudio") as m6,
            patch("asiai.doctor._check_mlxlm") as m7,
            patch("asiai.doctor._check_llamacpp") as m8a,
            patch("asiai.doctor._check_vllm_mlx") as m8b,
            patch("asiai.doctor._check_db") as m9,
            patch("asiai.doctor._check_daemon") as m10,
        ):
            for m in [m1, m2, m3, m4, m5, m6, m7, m8a, m8b, m9]:
                m.return_value = CheckResult("test", "test", "ok", "ok")
            m10.return_value = [CheckResult("daemon", "test", "ok", "ok")]
            checks = run_checks()
        assert len(checks) == 11
