"""Tests for the ``_check_versions`` doctor recap (offline-only)."""

from __future__ import annotations

from unittest import mock

from asiai import doctor
from asiai.versions.models import EngineVersionReport, VersionStatus


def _report(name, status):
    return EngineVersionReport(engine_name=name, display=name, status=status)


def test_check_versions_ok_when_all_up_to_date():
    reports = [
        _report("ollama", VersionStatus.UP_TO_DATE),
        _report("llamacpp", VersionStatus.UP_TO_DATE),
    ]
    with mock.patch("asiai.versions.cli.collect_reports", return_value=reports) as cr:
        result = doctor._check_versions()
    assert result.status == "ok"
    assert result.category == "engine"
    # Recap must be offline — no network fetch.
    cr.assert_called_once_with(check_upstream=False)


def test_check_versions_warn_on_upgrades_and_stale():
    reports = [
        _report("ollama", VersionStatus.UPGRADE_AVAILABLE),
        _report("mlxlm", VersionStatus.UPGRADE_AVAILABLE),
        _report("llamacpp", VersionStatus.RUNNING_STALE),
    ]
    with mock.patch("asiai.versions.cli.collect_reports", return_value=reports):
        result = doctor._check_versions()
    assert result.status == "warn"
    assert "2 upgrade(s)" in result.message
    assert "1 stale process(es)" in result.message
    assert result.fix == "asiai versions"


def test_check_versions_survives_collect_failure():
    with mock.patch("asiai.versions.cli.collect_reports", side_effect=RuntimeError("boom")):
        result = doctor._check_versions()
    assert result.status == "warn"
    assert "failed" in result.message.lower()


def test_check_versions_included_in_run_checks():
    # The recap must be wired into run_checks under the engine category.
    reports = [_report("ollama", VersionStatus.UP_TO_DATE)]
    with (
        mock.patch("asiai.versions.cli.collect_reports", return_value=reports),
        mock.patch("asiai.doctor.http_get_json", return_value=(None, {})),
        mock.patch("asiai.doctor.subprocess"),
        mock.patch(
            "asiai.doctor._check_db", return_value=doctor.CheckResult("database", "DB", "ok", "")
        ),
        mock.patch("asiai.doctor._check_daemon", return_value=[]),
        mock.patch("asiai.doctor._check_alerting", return_value=[]),
        mock.patch("asiai.doctor._check_ollama_config", return_value=[]),
    ):
        checks = doctor.run_checks()
    version_checks = [c for c in checks if c.name == "Versions"]
    assert len(version_checks) == 1
    assert version_checks[0].category == "engine"
