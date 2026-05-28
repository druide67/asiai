"""Tests for the version collectors (installed + brew outdated)."""

from __future__ import annotations

import json
import subprocess
from unittest import mock

from asiai.versions import collectors
from asiai.versions.models import EngineVersionSpec


def _completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# --- installed_version: brew formula ---------------------------------------


def test_installed_brew_formula():
    spec = EngineVersionSpec("llamacpp", brew_formula="llama.cpp")
    with (
        mock.patch.object(collectors, "_brew_bin", return_value="/opt/homebrew/bin/brew"),
        mock.patch.object(collectors.subprocess, "run", return_value=_completed("llama.cpp 8180")),
    ):
        assert collectors.installed_version(spec) == "8180"


def test_installed_brew_formula_not_installed():
    spec = EngineVersionSpec("llamacpp", brew_formula="llama.cpp")
    with (
        mock.patch.object(collectors, "_brew_bin", return_value="/opt/homebrew/bin/brew"),
        mock.patch.object(collectors.subprocess, "run", return_value=_completed("")),
    ):
        assert collectors.installed_version(spec) is None


def test_installed_no_brew_binary_returns_none():
    spec = EngineVersionSpec("llamacpp", brew_formula="llama.cpp")
    with mock.patch.object(collectors, "_brew_bin", return_value=None):
        assert collectors.installed_version(spec) is None


# --- installed_version: pip ------------------------------------------------


def test_installed_pip_package():
    spec = EngineVersionSpec("vmlx", pip_package="vmlx")
    pip_out = "Name: vmlx\nVersion: 0.3.1\nSummary: ...\n"
    with mock.patch.object(collectors.subprocess, "run", return_value=_completed(pip_out)):
        assert collectors.installed_version(spec) == "0.3.1"


def test_installed_pip_missing_version_line():
    spec = EngineVersionSpec("vmlx", pip_package="vmlx")
    with mock.patch.object(collectors.subprocess, "run", return_value=_completed("Name: vmlx\n")):
        assert collectors.installed_version(spec) is None


# --- installed_version: version_cmd ----------------------------------------


def test_installed_version_cmd_regex():
    spec = EngineVersionSpec("rapidmlx", version_cmd=("rapid-mlx", "--version"))
    with (
        mock.patch.object(collectors.shutil, "which", return_value="/opt/homebrew/bin/rapid-mlx"),
        mock.patch.object(
            collectors.subprocess, "run", return_value=_completed("rapid-mlx 0.6.66")
        ),
    ):
        assert collectors.installed_version(spec) == "0.6.66"


def test_installed_version_cmd_from_stderr():
    spec = EngineVersionSpec("rapidmlx", version_cmd=("rapid-mlx", "--version"))
    with (
        mock.patch.object(collectors.shutil, "which", return_value="/opt/homebrew/bin/rapid-mlx"),
        mock.patch.object(
            collectors.subprocess, "run", return_value=_completed("", stderr="rapid-mlx 0.6.70")
        ),
    ):
        assert collectors.installed_version(spec) == "0.6.70"


def test_installed_version_cmd_binary_missing():
    spec = EngineVersionSpec("rapidmlx", version_cmd=("rapid-mlx", "--version"))
    with (
        mock.patch.object(collectors.shutil, "which", return_value=None),
        mock.patch.object(collectors.os.path, "isfile", return_value=False),
    ):
        assert collectors.installed_version(spec) is None


# --- installed_version: app bundle -----------------------------------------


def test_installed_app_bundle():
    spec = EngineVersionSpec("lmstudio", app_bundle_path="/Applications/LM Studio.app")
    with (
        mock.patch.object(collectors.os.path, "exists", return_value=True),
        mock.patch.object(collectors.subprocess, "run", return_value=_completed("0.4.14")),
    ):
        assert collectors.installed_version(spec) == "0.4.14"


def test_installed_app_bundle_absent():
    spec = EngineVersionSpec("lmstudio", app_bundle_path="/Applications/LM Studio.app")
    with mock.patch.object(collectors.os.path, "exists", return_value=False):
        assert collectors.installed_version(spec) is None


def test_installed_precedence_brew_over_pip():
    # mlx-lm is both a brew formula and a pip package: brew wins.
    spec = EngineVersionSpec("mlxlm", brew_formula="mlx-lm", pip_package="mlx-lm")
    with (
        mock.patch.object(collectors, "_brew_bin", return_value="/opt/homebrew/bin/brew"),
        mock.patch.object(
            collectors.subprocess, "run", return_value=_completed("mlx-lm 0.30.7")
        ) as run,
    ):
        assert collectors.installed_version(spec) == "0.30.7"
        # pip show must not have been consulted.
        assert run.call_count == 1


# --- brew_outdated ---------------------------------------------------------


def test_brew_outdated_parses_formulae_and_casks():
    payload = {
        "formulae": [
            {"name": "llama.cpp", "installed_versions": ["8180"], "current_version": "8200"},
            {"name": "ollama", "installed_versions": ["0.30.0"], "current_version": "0.31.0"},
        ],
        "casks": [
            {"name": "lm-studio", "installed_versions": ["0.4.13"], "current_version": "0.4.14"},
        ],
    }
    with (
        mock.patch.object(collectors, "_brew_bin", return_value="/opt/homebrew/bin/brew"),
        mock.patch.object(
            collectors.subprocess, "run", return_value=_completed(json.dumps(payload))
        ),
    ):
        out = collectors.brew_outdated()
    assert out == {"llama.cpp": "8200", "ollama": "0.31.0", "lm-studio": "0.4.14"}


def test_brew_outdated_empty_means_all_up_to_date():
    with (
        mock.patch.object(collectors, "_brew_bin", return_value="/opt/homebrew/bin/brew"),
        mock.patch.object(collectors.subprocess, "run", return_value=_completed("")),
    ):
        assert collectors.brew_outdated() == {}


def test_brew_outdated_malformed_json():
    with (
        mock.patch.object(collectors, "_brew_bin", return_value="/opt/homebrew/bin/brew"),
        mock.patch.object(collectors.subprocess, "run", return_value=_completed("not json{")),
    ):
        assert collectors.brew_outdated() == {}


def test_brew_outdated_no_brew():
    with mock.patch.object(collectors, "_brew_bin", return_value=None):
        assert collectors.brew_outdated() == {}


def test_brew_outdated_subprocess_error():
    with (
        mock.patch.object(collectors, "_brew_bin", return_value="/opt/homebrew/bin/brew"),
        mock.patch.object(collectors.subprocess, "run", side_effect=OSError("boom")),
    ):
        assert collectors.brew_outdated() == {}


# --- running_versions ------------------------------------------------------


def test_running_versions_collects_adapter_versions():
    fake_a = mock.Mock()
    fake_a.name = "llamacpp"
    fake_a.version.return_value = "8180"
    fake_b = mock.Mock()
    fake_b.name = "ollama"
    fake_b.version.return_value = "0.30.0"
    with mock.patch("asiai.cli._discover_engines", return_value=[fake_a, fake_b]):
        out = collectors.running_versions()
    assert out == {"llamacpp": "8180", "ollama": "0.30.0"}


def test_running_versions_skips_empty_and_errors():
    fake_a = mock.Mock()
    fake_a.name = "llamacpp"
    fake_a.version.return_value = ""  # unreachable -> skipped
    fake_b = mock.Mock()
    fake_b.name = "ollama"
    fake_b.version.side_effect = RuntimeError("boom")  # error -> skipped
    with mock.patch("asiai.cli._discover_engines", return_value=[fake_a, fake_b]):
        assert collectors.running_versions() == {}


def test_running_versions_discovery_failure_is_safe():
    with mock.patch("asiai.cli._discover_engines", side_effect=RuntimeError("no net")):
        assert collectors.running_versions() == {}
