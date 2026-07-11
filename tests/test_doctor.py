"""Tests for the doctor diagnostic module."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from asiai.doctor import (
    CheckResult,
    _check_apple_silicon,
    _check_db,
    _check_exo,
    _check_llamacpp,
    _check_lmstudio,
    _check_memory_pressure,
    _check_mlxlm,
    _check_ollama,
    _check_ollama_config,
    _check_omlx,
    _check_ram,
    _check_thermal,
    _check_vllm_mlx,
    run_checks,
)


@pytest.fixture(autouse=True)
def _mock_engine_config():
    """Ensure doctor tests don't read real engine config from disk."""
    with patch(
        "asiai.doctor.load_config",
        return_value={"version": 1, "engines": []},
    ):
        yield


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
        with (
            patch("asiai.doctor._which", return_value=None),
            patch("asiai.doctor.http_get_json", return_value=(None, {})),
        ):
            result = _check_ollama()
        assert result.status == "fail"
        assert "not installed" in result.message

    def test_installed_not_running(self):
        with (
            patch("asiai.doctor._which", return_value="/opt/homebrew/bin/ollama"),
            patch("asiai.doctor.http_get_json", return_value=(None, {})),
        ):
            result = _check_ollama()
        assert result.status == "warn"
        assert "not running" in result.message

    def test_running_with_models(self):
        def mock_get(url, timeout=5):
            if "/api/version" in url:
                return {"version": "0.17.4"}, {}
            if "/api/ps" in url:
                return {"models": [{"name": "gemma2:9b"}]}, {}
            return None, {}

        with (
            patch("asiai.doctor._which", return_value="/opt/homebrew/bin/ollama"),
            patch("asiai.doctor.http_get_json", side_effect=mock_get),
        ):
            result = _check_ollama()
        assert result.status == "ok"
        assert "gemma2:9b" in result.message


class TestCheckLMStudio:
    def test_not_installed(self):
        with (
            patch("asiai.doctor.os.path.exists", return_value=False),
            patch("asiai.doctor.http_get_json", return_value=(None, {})),
        ):
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
        with (
            patch("asiai.doctor._brew_formula_version", return_value=None),
            patch("asiai.doctor.http_get_json", return_value=(None, {})),
        ):
            result = _check_mlxlm()
        assert result.status == "fail"
        assert "not installed" in result.message

    def test_installed_not_running(self):
        with (
            patch("asiai.doctor._brew_formula_version", return_value="0.30.7"),
            patch("asiai.doctor.http_get_json", return_value=(None, {})),
        ):
            result = _check_mlxlm()
        assert result.status == "warn"
        assert "not running" in result.message

    def test_running_with_models(self):
        def mock_get(url, timeout=5):
            if "/v1/models" in url:
                return {"data": [{"id": "mlx-community/gemma-2-9b-4bit"}]}, {}
            return None, {}

        with (
            patch("asiai.doctor._brew_formula_version", return_value="0.30.7"),
            patch("asiai.doctor.http_get_json", side_effect=mock_get),
        ):
            result = _check_mlxlm()
        assert result.status == "ok"
        assert "gemma-2-9b" in result.message


class TestCheckLlamaCpp:
    def test_not_installed(self):
        with (
            patch("asiai.doctor._brew_formula_version", return_value=None),
            patch("asiai.doctor.http_get_json", return_value=(None, {})),
        ):
            result = _check_llamacpp()
        assert result.status == "fail"
        assert "not installed" in result.message

    def test_installed_not_running(self):
        with (
            patch("asiai.doctor._brew_formula_version", return_value="0.0.4567"),
            patch("asiai.doctor.http_get_json", return_value=(None, {})),
        ):
            result = _check_llamacpp()
        assert result.status == "warn"
        assert "not running" in result.message

    def test_running(self):
        def mock_get(url, timeout=5):
            if "/health" in url:
                return {"status": "ok"}, {}
            if "/v1/models" in url:
                return {"data": [{"id": "my-model.gguf"}]}, {}
            return None, {}

        with (
            patch("asiai.doctor._brew_formula_version", return_value="0.0.4567"),
            patch("asiai.doctor.http_get_json", side_effect=mock_get),
        ):
            result = _check_llamacpp()
        assert result.status == "ok"
        assert "my-model" in result.message


class TestCheckVllmMlx:
    def test_not_installed(self):
        # http_get_json must be mocked too: without it the check would probe
        # the real localhost ports and flake when anything answers on :8000.
        with (
            patch("asiai.doctor._pip_version", return_value=None),
            patch("asiai.doctor.http_get_json", return_value=(None, {})),
        ):
            result = _check_vllm_mlx()
        assert result.status == "fail"
        assert "not installed" in result.message

    def test_installed_not_running(self):
        with (
            patch("asiai.doctor._pip_version", return_value="0.1.2"),
            patch("asiai.doctor.http_get_json", return_value=(None, {})),
        ):
            result = _check_vllm_mlx()
        assert result.status == "warn"
        assert "not running" in result.message

    def test_running_with_models(self):
        def mock_get(url, timeout=5):
            if "/version" in url and "/v1" not in url:
                return {"version": "0.1.2"}, {}
            if "/v1/models" in url:
                return {"data": [{"id": "mlx-model"}]}, {}
            return None, {}

        with (
            patch("asiai.doctor._pip_version", return_value="0.1.2"),
            patch("asiai.doctor.http_get_json", side_effect=mock_get),
        ):
            result = _check_vllm_mlx()
        assert result.status == "ok"
        assert "mlx-model" in result.message

    def test_running_no_models(self):
        """A real vllm server with no model loaded is still detected."""

        def mock_get(url, timeout=5):
            if "/version" in url and "/v1" not in url:
                return {"version": "0.1.2"}, {}
            if "/v1/models" in url:
                return {"object": "list", "data": []}, {}
            return None, {}

        with (
            patch("asiai.doctor._pip_version", return_value="0.1.2"),
            patch("asiai.doctor.http_get_json", side_effect=mock_get),
        ):
            result = _check_vllm_mlx()
        assert result.status == "ok"
        assert "server running" in result.message

    def test_third_party_service_on_port_not_vllm(self):
        """A third-party service answering /version on :8000 is not vllm.

        Regression: any JSON body with a "version" field used to be taken
        as a running vllm-mlx server, so an unrelated local web service
        exposing {"service": ..., "version": ...} produced a false
        "server running" report.
        """

        def mock_get(url, timeout=5):
            if "/version" in url and "/v1" not in url:
                return {"service": "some-dashboard", "version": "0.1.0"}, {}
            return None, {}

        with (
            patch("asiai.doctor._pip_version", return_value=None),
            patch("asiai.doctor.http_get_json", side_effect=mock_get),
        ):
            result = _check_vllm_mlx()
        assert result.status == "fail"
        assert "not installed" in result.message

    def test_version_endpoint_without_openai_api_rejected(self):
        """/version alone is not enough: /v1/models must have OpenAI shape."""

        def mock_get(url, timeout=5):
            if "/version" in url and "/v1" not in url:
                return {"version": "0.1.0"}, {}
            if "/v1/models" in url:
                return {"detail": "Not Found"}, {}
            return None, {}

        with (
            patch("asiai.doctor._pip_version", return_value=None),
            patch("asiai.doctor.http_get_json", side_effect=mock_get),
        ):
            result = _check_vllm_mlx()
        assert result.status == "fail"
        assert "not installed" in result.message

    def test_installed_with_third_party_on_port(self):
        """Installed vllm-mlx + foreign service on the port = not running."""

        def mock_get(url, timeout=5):
            if "/version" in url and "/v1" not in url:
                return {"service": "some-dashboard", "version": "0.1.0"}, {}
            return None, {}

        with (
            patch("asiai.doctor._pip_version", return_value="0.1.2"),
            patch("asiai.doctor.http_get_json", side_effect=mock_get),
        ):
            result = _check_vllm_mlx()
        assert result.status == "warn"
        assert "not running" in result.message

    def test_version_payload_naming_vllm_accepted(self):
        """A /version payload whose identity fields name vllm is accepted."""

        def mock_get(url, timeout=5):
            if "/version" in url and "/v1" not in url:
                return {"name": "vllm-mlx", "version": "0.1.2"}, {}
            if "/v1/models" in url:
                return {"object": "list", "data": [{"id": "mlx-model"}]}, {}
            return None, {}

        with (
            patch("asiai.doctor._pip_version", return_value="0.1.2"),
            patch("asiai.doctor.http_get_json", side_effect=mock_get),
        ):
            result = _check_vllm_mlx()
        assert result.status == "ok"
        assert "mlx-model" in result.message


class TestCheckOllamaConfig:
    def test_ollama_not_running_returns_empty(self):
        mock_lsof = MagicMock()
        mock_lsof.returncode = 1
        mock_lsof.stdout = ""
        with patch("asiai.doctor.subprocess.run", return_value=mock_lsof):
            results = _check_ollama_config()
        assert results == []

    def test_custom_env_vars(self):
        mock_lsof = MagicMock()
        mock_lsof.returncode = 0
        mock_lsof.stdout = "12345"

        env_line = (
            "  PID COMMAND\n"
            "12345 ollama serve OLLAMA_NUM_PARALLEL=4 OLLAMA_KEEP_ALIVE=-1 "
            "OLLAMA_FLASH_ATTENTION=1 HOME=/Users/test"
        )
        mock_ps = MagicMock()
        mock_ps.returncode = 0
        mock_ps.stdout = env_line

        def mock_run(cmd, **_kw):
            if cmd[0] == "lsof":
                return mock_lsof
            return mock_ps

        with patch("asiai.doctor.subprocess.run", side_effect=mock_run):
            results = _check_ollama_config()

        assert len(results) == 1
        msg = results[0].message
        assert "num_parallel=4" in msg
        assert "keep_alive=-1" in msg
        assert "flash_attention=1" in msg
        # defaults should still show
        assert "host=127.0.0.1:11434 (default)" in msg

    def test_all_defaults(self):
        mock_lsof = MagicMock()
        mock_lsof.returncode = 0
        mock_lsof.stdout = "12345"

        mock_ps = MagicMock()
        mock_ps.returncode = 0
        mock_ps.stdout = "  PID COMMAND\n12345 ollama serve HOME=/Users/test"

        def mock_run(cmd, **_kw):
            if cmd[0] == "lsof":
                return mock_lsof
            return mock_ps

        with patch("asiai.doctor.subprocess.run", side_effect=mock_run):
            results = _check_ollama_config()

        assert len(results) == 1
        # All should show (default)
        assert results[0].message.count("(default)") == 5


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
            patch("asiai.doctor._check_ollama_config") as m5b,
            patch("asiai.doctor._check_lmstudio") as m6,
            patch("asiai.doctor._check_mlxlm") as m7,
            patch("asiai.doctor._check_llamacpp") as m8a,
            patch("asiai.doctor._check_vllm_mlx") as m8b,
            patch("asiai.doctor._check_omlx") as m8b2,
            patch("asiai.doctor._check_exo") as m8c,
            patch("asiai.doctor._check_db") as m9,
            patch("asiai.doctor._check_daemon") as m10,
            patch("asiai.doctor._check_alerting") as m11,
            patch("asiai.doctor._check_versions") as m12,
        ):
            for m in [m1, m2, m3, m4, m5, m6, m7, m8a, m8b, m8b2, m8c, m9, m12]:
                m.return_value = CheckResult("test", "test", "ok", "ok")
            m5b.return_value = [CheckResult("engine", "Ollama config", "ok", "ok")]
            m10.return_value = [CheckResult("daemon", "test", "ok", "ok")]
            m11.return_value = [CheckResult("alerting", "test", "ok", "ok")]
            checks = run_checks()
        assert len(checks) == 16


class TestBinaryOrPort:
    """Tests for the binary-OR-port detection logic."""

    def test_ollama_no_binary_but_port_reachable(self):
        """Ollama as LaunchDaemon (binary not found) but reachable = OK."""

        def mock_get(url, timeout=5):
            if "/api/version" in url:
                return {"version": "0.17.7"}, {}
            if "/api/ps" in url:
                return {"models": []}, {}
            return None, {}

        with (
            patch("asiai.doctor._which", return_value=None),
            patch("asiai.doctor.http_get_json", side_effect=mock_get),
        ):
            result = _check_ollama()
        assert result.status == "ok"
        assert "0.17.7" in result.message

    def test_omlx_reachable_on_config_port(self):
        """oMLX reachable on non-standard port from config = OK."""
        with (
            patch("asiai.doctor.os.path.exists", return_value=False),
            patch("asiai.doctor._which", return_value=None),
            patch(
                "asiai.doctor.load_config",
                return_value={
                    "version": 1,
                    "engines": [
                        {"url": "http://localhost:8800", "engine": "omlx"},
                    ],
                },
            ),
        ):

            def mock_get(url, timeout=5):
                if "8800" in url and "/v1/models" in url:
                    return {"data": [{"id": "qwen3"}]}, {}
                return None, {}

            with patch("asiai.doctor.http_get_json", side_effect=mock_get):
                result = _check_omlx()

        assert result.status == "ok"
        assert "qwen3" in result.message
        assert "8800" in result.message

    def test_engine_neither_binary_nor_port(self):
        """Neither binary found nor port responds = fail."""
        with (
            patch("asiai.doctor._which", return_value=None),
            patch("asiai.doctor.http_get_json", return_value=(None, {})),
        ):
            result = _check_ollama()
        assert result.status == "fail"
        assert "not installed" in result.message

    def test_lmstudio_no_app_but_port_reachable(self):
        """LM Studio app not found but server responding = OK."""

        def mock_get(url, timeout=5):
            if "/v1/models" in url:
                return {"data": [{"id": "model-1"}]}, {"x-lm-studio-version": "0.5.0"}
            return None, {}

        with (
            patch("asiai.doctor.os.path.exists", return_value=False),
            patch("asiai.doctor.http_get_json", side_effect=mock_get),
        ):
            result = _check_lmstudio()
        assert result.status == "ok"
        assert "model-1" in result.message


# launchd LaunchAgents inherit a minimal PATH without Homebrew or user dirs.
_LAUNCHD_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


class TestLaunchdMinimalPath:
    """Doctor must find installed engines even under launchd's minimal PATH.

    Regression tests: when doctor runs inside a LaunchAgent (web dashboard),
    subprocess lookups like ``which ollama``, ``brew list`` and ``pip show``
    used to inherit the minimal launchd PATH and report every engine as
    "not installed" even though they were.
    """

    @staticmethod
    def _fake_bin(directory, name, body="exit 0"):
        directory.mkdir(exist_ok=True)
        path = directory / name
        path.write_text(f"#!/bin/sh\n{body}\n")
        path.chmod(0o755)
        return path

    def test_ollama_binary_found_outside_path(self, tmp_path, monkeypatch):
        """Binary lives in a standard install dir not present on PATH."""
        bin_dir = tmp_path / "brew-bin"
        self._fake_bin(bin_dir, "ollama")
        monkeypatch.setenv("PATH", _LAUNCHD_PATH)
        monkeypatch.setattr("asiai.doctor._FALLBACK_BIN_DIRS", (str(bin_dir),), raising=False)
        with patch("asiai.doctor.http_get_json", return_value=(None, {})):
            result = _check_ollama()
        assert result.status == "warn"
        assert "not running" in result.message

    def test_mlxlm_brew_resolved_from_standard_prefix(self, tmp_path, monkeypatch):
        """brew is not on PATH but exists at a standard Homebrew prefix."""
        fake_brew = self._fake_bin(tmp_path / "brew-bin", "brew", 'echo "mlx-lm 0.30.7"')
        monkeypatch.setenv("PATH", _LAUNCHD_PATH)
        monkeypatch.setattr("asiai.versions.collectors._BREW_CANDIDATES", (str(fake_brew),))
        with patch("asiai.doctor.http_get_json", return_value=(None, {})):
            result = _check_mlxlm()
        assert result.status == "warn"
        assert "0.30.7" in result.message
        assert "not running" in result.message

    def test_llamacpp_brew_resolved_from_standard_prefix(self, tmp_path, monkeypatch):
        fake_brew = self._fake_bin(tmp_path / "brew-bin", "brew", 'echo "llama.cpp 8180"')
        monkeypatch.setenv("PATH", _LAUNCHD_PATH)
        monkeypatch.setattr("asiai.versions.collectors._BREW_CANDIDATES", (str(fake_brew),))
        with patch("asiai.doctor.http_get_json", return_value=(None, {})):
            result = _check_llamacpp()
        assert result.status == "warn"
        assert "8180" in result.message
        assert "not running" in result.message

    def test_vllm_mlx_pip_uses_interpreter_not_path(self, monkeypatch):
        """pip lookup must go through sys.executable, immune to PATH."""
        monkeypatch.setenv("PATH", _LAUNCHD_PATH)
        captured: dict[str, list[str]] = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return MagicMock(returncode=0, stdout="Name: vllm-mlx\nVersion: 0.1.2\n")

        with (
            patch("asiai.versions.collectors.subprocess.run", side_effect=fake_run),
            patch("asiai.doctor.http_get_json", return_value=(None, {})),
        ):
            result = _check_vllm_mlx()
        assert result.status == "warn"
        assert "0.1.2" in result.message
        assert captured["cmd"][0] == sys.executable

    def test_exo_binary_found_outside_path(self, tmp_path, monkeypatch):
        bin_dir = tmp_path / "user-bin"
        self._fake_bin(bin_dir, "exo")
        monkeypatch.setenv("PATH", _LAUNCHD_PATH)
        monkeypatch.setattr("asiai.doctor._FALLBACK_BIN_DIRS", (str(bin_dir),), raising=False)
        with patch("asiai.doctor.http_get_json", return_value=(None, {})):
            result = _check_exo()
        assert result.status == "warn"
        assert "not running" in result.message

    def test_omlx_binary_found_outside_path(self, tmp_path, monkeypatch):
        bin_dir = tmp_path / "brew-bin"
        self._fake_bin(bin_dir, "omlx")
        monkeypatch.setenv("PATH", _LAUNCHD_PATH)
        monkeypatch.setattr("asiai.doctor._FALLBACK_BIN_DIRS", (str(bin_dir),), raising=False)
        with (
            patch("asiai.doctor.os.path.exists", return_value=False),
            patch("asiai.doctor.http_get_json", return_value=(None, {})),
        ):
            result = _check_omlx()
        assert result.status == "warn"
        assert "not running" in result.message
