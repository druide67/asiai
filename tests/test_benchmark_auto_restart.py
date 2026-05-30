"""Tests for opt-in aisctl-based engine restart before the agentic bench."""

from __future__ import annotations

from unittest.mock import patch

from asiai.benchmark.auto_restart import (
    AISCTL_MANAGED_ENGINES,
    auto_restart_engine,
    is_aisctl_available,
)


def test_managed_engines_set_is_non_empty():
    # Guards against an accidental clear that would make auto-restart
    # silently no-op for every engine.
    assert "llamacpp" in AISCTL_MANAGED_ENGINES
    assert "ollama" in AISCTL_MANAGED_ENGINES
    assert "mlx-lm" in AISCTL_MANAGED_ENGINES
    assert "rapidmlx" in AISCTL_MANAGED_ENGINES


def test_is_aisctl_available_true_when_on_path():
    with patch("asiai.benchmark.auto_restart.shutil.which", return_value="/usr/local/bin/aisctl"):
        assert is_aisctl_available() is True


def test_is_aisctl_available_false_when_missing():
    with patch("asiai.benchmark.auto_restart.shutil.which", return_value=None):
        assert is_aisctl_available() is False


def test_auto_restart_skipped_when_engine_not_managed():
    ok, msg = auto_restart_engine("custom-engine", "http://localhost:8080")
    assert ok is False
    assert "not managed by aisrv" in msg


def test_auto_restart_skipped_when_aisctl_missing():
    with patch("asiai.benchmark.auto_restart.shutil.which", return_value=None):
        ok, msg = auto_restart_engine("llamacpp", "http://localhost:8080")
    assert ok is False
    assert "aisctl not found" in msg


def test_auto_restart_fails_on_subprocess_error():
    with (
        patch("asiai.benchmark.auto_restart.shutil.which", return_value="/usr/local/bin/aisctl"),
        patch("asiai.benchmark.auto_restart.subprocess.run", side_effect=OSError("boom")),
    ):
        ok, msg = auto_restart_engine("llamacpp", "http://localhost:8080")
    assert ok is False
    assert "failed to launch" in msg


def test_auto_restart_fails_on_nonzero_returncode():
    class _FakeProc:
        returncode = 1
        stdout = ""
        stderr = "permission denied"

    with (
        patch("asiai.benchmark.auto_restart.shutil.which", return_value="/usr/local/bin/aisctl"),
        patch("asiai.benchmark.auto_restart.subprocess.run", return_value=_FakeProc()),
    ):
        ok, msg = auto_restart_engine("llamacpp", "http://localhost:8080")
    assert ok is False
    assert "returncode=1" in msg
    assert "permission denied" in msg


def test_auto_restart_success_path():
    class _FakeProc:
        returncode = 0
        stdout = "{'engine': 'llamacpp', 'restarted': True}"
        stderr = ""

    with (
        patch("asiai.benchmark.auto_restart.shutil.which", return_value="/usr/local/bin/aisctl"),
        patch("asiai.benchmark.auto_restart.subprocess.run", return_value=_FakeProc()),
        patch("asiai.benchmark.auto_restart._wait_healthy", return_value=True),
    ):
        ok, msg = auto_restart_engine("llamacpp", "http://localhost:8080")
    assert ok is True
    assert "healthy" in msg


def test_auto_restart_fails_when_health_never_returns():
    class _FakeProc:
        returncode = 0
        stdout = ""
        stderr = ""

    with (
        patch("asiai.benchmark.auto_restart.shutil.which", return_value="/usr/local/bin/aisctl"),
        patch("asiai.benchmark.auto_restart.subprocess.run", return_value=_FakeProc()),
        patch("asiai.benchmark.auto_restart._wait_healthy", return_value=False),
    ):
        ok, msg = auto_restart_engine("llamacpp", "http://localhost:8080", healthcheck_timeout=5)
    assert ok is False
    assert "did not become healthy" in msg
    assert "5s" in msg
