"""Tests for the daemon module."""

from __future__ import annotations

from unittest.mock import MagicMock, mock_open, patch

import pytest

from asiai.daemon import (
    LABEL,
    PLIST_PATH,
    SERVICES,
    _find_asiai_command,
    _read_plist_config,
    daemon_logs,
    daemon_start,
    daemon_status,
    daemon_status_all,
    daemon_stop,
    daemon_stop_all,
    generate_plist,
)

# ── ServiceProfile ──────────────────────────────────────────────────


class TestServiceProfile:
    def test_all_services_have_required_fields(self):
        for name, profile in SERVICES.items():
            assert profile.name == name
            assert profile.label.startswith("com.druide67.asiai.")
            assert profile.plist_path.endswith(".plist")
            assert profile.log_path
            assert profile.err_log_path

    def test_separate_log_paths(self):
        paths = set()
        for profile in SERVICES.values():
            assert profile.log_path not in paths
            assert profile.err_log_path not in paths
            paths.add(profile.log_path)
            paths.add(profile.err_log_path)

    def test_separate_labels(self):
        labels = [p.label for p in SERVICES.values()]
        assert len(labels) == len(set(labels))

    def test_backward_compat_aliases(self):
        assert LABEL == SERVICES["monitor"].label
        assert PLIST_PATH == SERVICES["monitor"].plist_path


# ── _find_asiai_command ─────────────────────────────────────────────


class TestFindAsiaiCommand:
    def test_found_in_path(self):
        with patch("asiai.daemon.shutil.which", return_value="/usr/local/bin/asiai"):
            cmd = _find_asiai_command()
        assert cmd == ["/usr/local/bin/asiai"]

    def test_fallback_python_m(self):
        with (
            patch("asiai.daemon.shutil.which", return_value=None),
            patch("asiai.daemon.sys") as mock_sys,
        ):
            mock_sys.executable = "/usr/bin/python3"
            cmd = _find_asiai_command()
        assert cmd == ["/usr/bin/python3", "-m", "asiai"]


# ── generate_plist ──────────────────────────────────────────────────


class TestGeneratePlist:
    def test_default_monitor(self):
        with patch("asiai.daemon.shutil.which", return_value="/usr/local/bin/asiai"):
            plist = generate_plist()
        assert plist["Label"] == LABEL
        assert plist["StartInterval"] == 60
        assert plist["RunAtLoad"] is True
        assert plist["KeepAlive"] is False
        assert "/usr/local/bin/asiai" in plist["ProgramArguments"]
        assert "monitor" in plist["ProgramArguments"]
        assert "--quiet" in plist["ProgramArguments"]

    def test_custom_interval(self):
        with patch("asiai.daemon.shutil.which", return_value="/usr/local/bin/asiai"):
            plist = generate_plist(interval=120)
        assert plist["StartInterval"] == 120


class TestGeneratePlistWeb:
    def test_web_defaults(self):
        with patch("asiai.daemon.shutil.which", return_value="/usr/local/bin/asiai"):
            plist = generate_plist("web")
        assert plist["Label"] == SERVICES["web"].label
        assert plist["KeepAlive"] is True
        assert plist["ThrottleInterval"] == 10
        assert "StartInterval" not in plist
        assert "--no-open" in plist["ProgramArguments"]
        assert "--port" in plist["ProgramArguments"]
        assert "8899" in plist["ProgramArguments"]
        assert "--host" in plist["ProgramArguments"]
        assert "127.0.0.1" in plist["ProgramArguments"]

    def test_web_custom_port(self):
        with patch("asiai.daemon.shutil.which", return_value="/usr/local/bin/asiai"):
            plist = generate_plist("web", port=9000)
        assert "9000" in plist["ProgramArguments"]

    def test_web_custom_host(self):
        with patch("asiai.daemon.shutil.which", return_value="/usr/local/bin/asiai"):
            plist = generate_plist("web", host="0.0.0.0")
        assert "0.0.0.0" in plist["ProgramArguments"]

    def test_unknown_service_raises(self):
        with pytest.raises(ValueError, match="Unknown service"):
            generate_plist("unknown")


# ── daemon_start ────────────────────────────────────────────────────


class TestDaemonStart:
    def test_start_success(self):
        mock_launchctl = MagicMock()
        mock_launchctl.returncode = 0

        mock_status_result = MagicMock()
        mock_status_result.returncode = 113  # Not running

        def mock_run(cmd, **kwargs):
            if cmd[0] == "launchctl" and cmd[1] == "load":
                return mock_launchctl
            if cmd[0] == "launchctl" and cmd[1] == "list":
                return mock_status_result
            return MagicMock(returncode=0)

        with (
            patch("asiai.daemon.subprocess.run", side_effect=mock_run),
            patch("asiai.daemon.os.makedirs"),
            patch("asiai.daemon.shutil.which", return_value="/usr/local/bin/asiai"),
            patch("builtins.open", mock_open()),
            patch("asiai.daemon.plistlib.dump"),
            patch("asiai.daemon.os.path.exists", return_value=False),
        ):
            result = daemon_start("monitor", interval=60)

        assert result["status"] == "started"
        assert result["interval"] == 60

    def test_start_launchctl_error(self):
        mock_launchctl = MagicMock()
        mock_launchctl.returncode = 1
        mock_launchctl.stderr = "Permission denied"

        mock_status_result = MagicMock()
        mock_status_result.returncode = 113

        def mock_run(cmd, **kwargs):
            if cmd[0] == "launchctl" and cmd[1] == "load":
                return mock_launchctl
            if cmd[0] == "launchctl" and cmd[1] == "list":
                return mock_status_result
            return MagicMock(returncode=0)

        with (
            patch("asiai.daemon.subprocess.run", side_effect=mock_run),
            patch("asiai.daemon.os.makedirs"),
            patch("asiai.daemon.shutil.which", return_value="/usr/local/bin/asiai"),
            patch("builtins.open", mock_open()),
            patch("asiai.daemon.plistlib.dump"),
            patch("asiai.daemon.os.path.exists", return_value=False),
        ):
            result = daemon_start()

        assert result["status"] == "error"
        assert "Permission denied" in result["message"]

    def test_start_unknown_service(self):
        result = daemon_start("bogus")
        assert result["status"] == "error"
        assert "Unknown service" in result["message"]


class TestDaemonStartWeb:
    def test_start_web_success(self):
        mock_launchctl = MagicMock()
        mock_launchctl.returncode = 0

        mock_status_result = MagicMock()
        mock_status_result.returncode = 113

        def mock_run(cmd, **kwargs):
            if cmd[0] == "launchctl" and cmd[1] == "load":
                return mock_launchctl
            if cmd[0] == "launchctl" and cmd[1] == "list":
                return mock_status_result
            return MagicMock(returncode=0)

        with (
            patch("asiai.daemon.subprocess.run", side_effect=mock_run),
            patch("asiai.daemon.os.makedirs"),
            patch("asiai.daemon.shutil.which", return_value="/usr/local/bin/asiai"),
            patch("builtins.open", mock_open()),
            patch("asiai.daemon.plistlib.dump"),
            patch("asiai.daemon.os.path.exists", return_value=False),
        ):
            result = daemon_start("web", port=9000, host="0.0.0.0")

        assert result["status"] == "started"
        assert result["port"] == 9000
        assert result["host"] == "0.0.0.0"


# ── daemon_stop ─────────────────────────────────────────────────────


class TestDaemonStop:
    def test_stop_with_plist(self):
        with (
            patch("asiai.daemon.os.path.exists", return_value=True),
            patch("asiai.daemon.subprocess.run") as mock_run,
            patch("asiai.daemon.os.remove") as mock_remove,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            result = daemon_stop()

        assert result["status"] == "stopped"
        assert result["service"] == "monitor"
        mock_remove.assert_called_once_with(PLIST_PATH)

    def test_stop_without_plist(self):
        with patch("asiai.daemon.os.path.exists", return_value=False):
            result = daemon_stop()
        assert result["status"] == "stopped"

    def test_stop_unknown_service(self):
        result = daemon_stop("bogus")
        assert result["status"] == "error"


class TestDaemonStopAll:
    def test_stop_all(self):
        with (
            patch("asiai.daemon.os.path.exists", return_value=False),
        ):
            results = daemon_stop_all()

        assert "monitor" in results
        assert "web" in results
        for r in results.values():
            assert r["status"] == "stopped"


# ── daemon_status ───────────────────────────────────────────────────


class TestDaemonStatus:
    def test_running(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{\n\t"PID" = 12345;\n}'

        with (
            patch("asiai.daemon.subprocess.run", return_value=mock_result),
            patch("asiai.daemon.os.path.exists", return_value=True),
        ):
            status = daemon_status()

        assert status["running"] is True
        assert status["pid"] == 12345
        assert status["plist_exists"] is True

    def test_not_running(self):
        mock_result = MagicMock()
        mock_result.returncode = 113  # Not found

        with (
            patch("asiai.daemon.subprocess.run", return_value=mock_result),
            patch("asiai.daemon.os.path.exists", return_value=False),
        ):
            status = daemon_status()

        assert status["running"] is False
        assert status["pid"] is None
        assert status["plist_exists"] is False

    def test_unknown_service(self):
        status = daemon_status("bogus")
        assert status["running"] is False


class TestDaemonStatusAll:
    def test_status_all(self):
        mock_result = MagicMock()
        mock_result.returncode = 113

        with (
            patch("asiai.daemon.subprocess.run", return_value=mock_result),
            patch("asiai.daemon.os.path.exists", return_value=False),
        ):
            statuses = daemon_status_all()

        assert "monitor" in statuses
        assert "web" in statuses
        for s in statuses.values():
            assert "running" in s
            assert "pid" in s


# ── daemon_logs ─────────────────────────────────────────────────────


class TestDaemonLogs:
    def test_logs_exist(self):
        mock_result = MagicMock()
        mock_result.stdout = "line1\nline2\nline3\n"

        with (
            patch("asiai.daemon.os.path.exists", return_value=True),
            patch("asiai.daemon.subprocess.run", return_value=mock_result),
        ):
            output = daemon_logs(lines=3)

        assert "line1" in output

    def test_no_log_file(self):
        with patch("asiai.daemon.os.path.exists", return_value=False):
            output = daemon_logs()
        assert "No log file" in output

    def test_unknown_service(self):
        output = daemon_logs("bogus")
        assert "Unknown service" in output


class TestDaemonLogsWeb:
    def test_web_logs(self):
        mock_result = MagicMock()
        mock_result.stdout = "web log line\n"

        with (
            patch("asiai.daemon.os.path.exists", return_value=True),
            patch("asiai.daemon.subprocess.run", return_value=mock_result),
        ):
            output = daemon_logs("web", lines=10)

        assert "web log line" in output


# ── _read_plist_config ──────────────────────────────────────────────


class TestReadPlistConfig:
    def test_read_web_config(self):
        plist_data = {
            "ProgramArguments": [
                "/usr/local/bin/asiai",
                "web",
                "--no-open",
                "--port",
                "9000",
                "--host",
                "0.0.0.0",
            ],
        }

        with (
            patch("asiai.daemon.os.path.exists", return_value=True),
            patch("asiai.daemon.plistlib.load", return_value=plist_data),
            patch("builtins.open", mock_open()),
        ):
            config = _read_plist_config("web")

        assert config["port"] == 9000
        assert config["host"] == "0.0.0.0"

    def test_read_monitor_config(self):
        plist_data = {"StartInterval": 120, "ProgramArguments": []}

        with (
            patch("asiai.daemon.os.path.exists", return_value=True),
            patch("asiai.daemon.plistlib.load", return_value=plist_data),
            patch("builtins.open", mock_open()),
        ):
            config = _read_plist_config("monitor")

        assert config["interval"] == 120

    def test_no_plist_returns_empty(self):
        with patch("asiai.daemon.os.path.exists", return_value=False):
            config = _read_plist_config("web")
        assert config == {}

    def test_unknown_service_returns_empty(self):
        config = _read_plist_config("bogus")
        assert config == {}
