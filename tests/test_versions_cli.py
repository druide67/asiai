"""Tests for the ``asiai versions`` CLI command + collect_reports orchestrator."""

from __future__ import annotations

import argparse
import json
from unittest import mock

from asiai.versions import cli as versions_cli
from asiai.versions.models import EngineVersionReport, VersionStatus

# --- collect_reports orchestrator ------------------------------------------


def test_collect_reports_offline_brew_upgrade():
    specs = {
        "llamacpp": mock.Mock(
            engine_name="llamacpp",
            display="llama.cpp",
            brew_formula="llama.cpp",
            brew_cask=None,
            pip_package=None,
            github_repo="ggml-org/llama.cpp",
            no_upstream=False,
            version_scheme="llamacpp_build",
            changelog_url=lambda: "https://github.com/ggml-org/llama.cpp/releases",
        )
    }
    with (
        mock.patch.object(versions_cli, "load_specs", return_value=specs),
        mock.patch.object(versions_cli, "provider_keys", return_value=set()),
        mock.patch.object(versions_cli, "running_versions", return_value={"llamacpp": "8180"}),
        mock.patch.object(versions_cli, "brew_outdated", return_value={"llama.cpp": "8200"}),
    ):
        reports = versions_cli.collect_reports()

    assert len(reports) == 1
    r = reports[0]
    assert r.running == "8180"
    assert r.available == "8200"
    # running 8180 != installed... installed comes from installed_version (real
    # subprocess); here it's the build the brew lookup says is current only if
    # outdated. installed is resolved separately — check status logic instead.


def test_collect_reports_running_stale(monkeypatch):
    spec = mock.Mock(
        engine_name="llamacpp",
        display="llama.cpp",
        brew_formula="llama.cpp",
        brew_cask=None,
        pip_package=None,
        github_repo=None,
        no_upstream=False,
        version_scheme="llamacpp_build",
        changelog_url=lambda: None,
    )
    with (
        mock.patch.object(versions_cli, "load_specs", return_value={"llamacpp": spec}),
        mock.patch.object(versions_cli, "provider_keys", return_value=set()),
        mock.patch.object(versions_cli, "running_versions", return_value={"llamacpp": "8180"}),
        mock.patch.object(versions_cli, "installed_version", return_value="8200"),
        mock.patch.object(versions_cli, "brew_outdated", return_value={}),
    ):
        reports = versions_cli.collect_reports()

    r = reports[0]
    assert r.installed == "8200"
    assert r.running == "8180"
    # installed (8200) not in outdated -> available = installed = 8200
    assert r.available == "8200"
    assert r.status == VersionStatus.RUNNING_STALE


def test_collect_reports_engine_filter():
    specs = {
        "ollama": mock.Mock(
            engine_name="ollama",
            display="Ollama",
            brew_formula="ollama",
            brew_cask=None,
            pip_package=None,
            github_repo="ollama/ollama",
            no_upstream=False,
            version_scheme="git_tag",
            changelog_url=lambda: None,
        ),
        "llamacpp": mock.Mock(
            engine_name="llamacpp",
            display="llama.cpp",
            brew_formula="llama.cpp",
            brew_cask=None,
            pip_package=None,
            github_repo=None,
            no_upstream=False,
            version_scheme="llamacpp_build",
            changelog_url=lambda: None,
        ),
    }
    with (
        mock.patch.object(versions_cli, "load_specs", return_value=specs),
        mock.patch.object(versions_cli, "provider_keys", return_value=set()),
        mock.patch.object(versions_cli, "running_versions", return_value={}),
        mock.patch.object(versions_cli, "installed_version", return_value=None),
        mock.patch.object(versions_cli, "brew_outdated", return_value={}),
    ):
        reports = versions_cli.collect_reports(engine="ollama")
    assert [r.engine_name for r in reports] == ["ollama"]


def test_collect_reports_check_upstream_routes_pip(monkeypatch):
    spec = mock.Mock(
        engine_name="vmlx",
        display="vMLX",
        brew_formula=None,
        brew_cask=None,
        pip_package="vmlx",
        github_repo=None,
        no_upstream=False,
        version_scheme="semver",
        changelog_url=lambda: None,
    )
    with (
        mock.patch.object(versions_cli, "load_specs", return_value={"vmlx": spec}),
        mock.patch.object(versions_cli, "provider_keys", return_value=set()),
        mock.patch.object(versions_cli, "running_versions", return_value={}),
        mock.patch.object(versions_cli, "installed_version", return_value="0.3.0"),
        mock.patch.object(versions_cli, "brew_outdated", return_value={}),
        mock.patch.object(versions_cli, "fetch_all", return_value={"vmlx": "0.4.0"}) as fetch,
    ):
        reports = versions_cli.collect_reports(check_upstream=True)

    fetch.assert_called_once()
    jobs = fetch.call_args[0][0]
    assert jobs == [("vmlx", "pypi", "vmlx")]
    assert reports[0].available == "0.4.0"
    assert reports[0].status == VersionStatus.UPGRADE_AVAILABLE


def test_collect_reports_no_upstream_skips_network():
    spec = mock.Mock(
        engine_name="lmstudio",
        display="LM Studio",
        brew_formula=None,
        brew_cask="lm-studio",
        pip_package=None,
        github_repo=None,
        no_upstream=True,
        version_scheme="semver",
        changelog_url=lambda: None,
    )
    with (
        mock.patch.object(versions_cli, "load_specs", return_value={"lmstudio": spec}),
        mock.patch.object(versions_cli, "provider_keys", return_value=set()),
        mock.patch.object(versions_cli, "running_versions", return_value={"lmstudio": "0.4.14"}),
        mock.patch.object(versions_cli, "installed_version", return_value="0.4.14"),
        mock.patch.object(versions_cli, "brew_outdated", return_value={}),
        mock.patch.object(versions_cli, "fetch_all") as fetch,
    ):
        reports = versions_cli.collect_reports(check_upstream=True)
    fetch.assert_not_called()
    assert reports[0].status == VersionStatus.UP_TO_DATE


# --- cmd_versions ----------------------------------------------------------


def _args(**kw):
    base = {
        "check_upstream": False,
        "json_output": False,
        "engine": None,
        "timeout": 5.0,
        "url": None,
    }
    base.update(kw)
    return argparse.Namespace(**base)


def test_cmd_versions_json(capsys):
    report = EngineVersionReport(
        engine_name="ollama",
        display="Ollama",
        running="0.30.0",
        installed="0.30.0",
        available="0.31.0",
        status=VersionStatus.UPGRADE_AVAILABLE,
    )
    with mock.patch.object(versions_cli, "collect_reports", return_value=[report]):
        rc = versions_cli.cmd_versions(_args(json_output=True))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["engines"][0]["engine_name"] == "ollama"
    assert out["engines"][0]["status"] == "upgrade-available"


def test_cmd_versions_table(capsys):
    report = EngineVersionReport(
        engine_name="ollama",
        display="Ollama",
        running="0.30.0",
        installed="0.30.0",
        available="0.31.0",
        status=VersionStatus.UPGRADE_AVAILABLE,
        changelog_url="https://github.com/ollama/ollama/releases",
    )
    with mock.patch.object(versions_cli, "collect_reports", return_value=[report]):
        rc = versions_cli.cmd_versions(_args())
    assert rc == 0
    out = capsys.readouterr().out
    assert "Ollama" in out
    assert "0.31.0" in out
    assert "upgrade-available" in out
    assert "github.com/ollama/ollama/releases" in out


def test_versions_command_registered_in_dispatch():
    # The command must be wired into cli.main's dispatch table.
    import asiai.cli as cli

    with (
        mock.patch.object(cli, "_discover_engines", return_value=[]),
        mock.patch("asiai.versions.cli.collect_reports", return_value=[]),
    ):
        rc = cli.main(["versions"])
    assert rc == 0
