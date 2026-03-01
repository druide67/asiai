"""Tests for the daemon module."""

from __future__ import annotations

from unittest.mock import MagicMock, mock_open, patch

from asiai.daemon import (
    LABEL,
    PLIST_PATH,
    _find_asiai_command,
    daemon_logs,
    daemon_start,
    daemon_status,
    daemon_stop,
    generate_plist,
)


class TestFindAsiaiCommand:
    def test_found_in_path(self):
        with patch("asiai.daemon.shutil.which", return_value="/usr/local/bin/asiai"):
            cmd = _find_asiai_command()
        assert cmd == ["/usr/local/bin/asiai"]

    def test_fallback_python_m(self):
        with patch("asiai.daemon.shutil.which", return_value=None), \
             patch("asiai.daemon.sys") as mock_sys:
            mock_sys.executable = "/usr/bin/python3"
            cmd = _find_asiai_command()
        assert cmd == ["/usr/bin/python3", "-m", "asiai"]


class TestGeneratePlist:
    def test_default_interval(self):
        with patch("asiai.daemon.shutil.which", return_value="/usr/local/bin/asiai"):
            plist = generate_plist()
        assert plist["Label"] == LABEL
        assert plist["StartInterval"] == 60
        assert plist["RunAtLoad"] is True
        assert "/usr/local/bin/asiai" in plist["ProgramArguments"]
        assert "monitor" in plist["ProgramArguments"]
        assert "--quiet" in plist["ProgramArguments"]

    def test_custom_interval(self):
        with patch("asiai.daemon.shutil.which", return_value="/usr/local/bin/asiai"):
            plist = generate_plist(interval=120)
        assert plist["StartInterval"] == 120


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

        with patch("asiai.daemon.subprocess.run", side_effect=mock_run), \
             patch("asiai.daemon.os.makedirs"), \
             patch("asiai.daemon.shutil.which", return_value="/usr/local/bin/asiai"), \
             patch("builtins.open", mock_open()), \
             patch("asiai.daemon.plistlib.dump"), \
             patch("asiai.daemon.os.path.exists", return_value=False):
            result = daemon_start(60)

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

        with patch("asiai.daemon.subprocess.run", side_effect=mock_run), \
             patch("asiai.daemon.os.makedirs"), \
             patch("asiai.daemon.shutil.which", return_value="/usr/local/bin/asiai"), \
             patch("builtins.open", mock_open()), \
             patch("asiai.daemon.plistlib.dump"), \
             patch("asiai.daemon.os.path.exists", return_value=False):
            result = daemon_start()

        assert result["status"] == "error"
        assert "Permission denied" in result["message"]


class TestDaemonStop:
    def test_stop_with_plist(self):
        with patch("asiai.daemon.os.path.exists", return_value=True), \
             patch("asiai.daemon.subprocess.run") as mock_run, \
             patch("asiai.daemon.os.remove") as mock_remove:
            mock_run.return_value = MagicMock(returncode=0)
            result = daemon_stop()

        assert result["status"] == "stopped"
        mock_remove.assert_called_once_with(PLIST_PATH)

    def test_stop_without_plist(self):
        with patch("asiai.daemon.os.path.exists", return_value=False):
            result = daemon_stop()
        assert result["status"] == "stopped"


class TestDaemonStatus:
    def test_running(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{\n\t"PID" = 12345;\n}'

        with patch("asiai.daemon.subprocess.run", return_value=mock_result), \
             patch("asiai.daemon.os.path.exists", return_value=True):
            status = daemon_status()

        assert status["running"] is True
        assert status["pid"] == 12345
        assert status["plist_exists"] is True

    def test_not_running(self):
        mock_result = MagicMock()
        mock_result.returncode = 113  # Not found

        with patch("asiai.daemon.subprocess.run", return_value=mock_result), \
             patch("asiai.daemon.os.path.exists", return_value=False):
            status = daemon_status()

        assert status["running"] is False
        assert status["pid"] is None
        assert status["plist_exists"] is False


class TestDaemonLogs:
    def test_logs_exist(self):
        mock_result = MagicMock()
        mock_result.stdout = "line1\nline2\nline3\n"

        with patch("asiai.daemon.os.path.exists", return_value=True), \
             patch("asiai.daemon.subprocess.run", return_value=mock_result):
            output = daemon_logs(3)

        assert "line1" in output

    def test_no_log_file(self):
        with patch("asiai.daemon.os.path.exists", return_value=False):
            output = daemon_logs()
        assert "No log file" in output
