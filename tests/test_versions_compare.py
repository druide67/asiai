"""Tests for version normalization, comparison, and status derivation.

The llama.cpp build-number reconciliation is the highest-bug-risk piece of
the versions feature, so it is locked down here with explicit fixtures for
all four live representations.
"""

from __future__ import annotations

import pytest

from asiai.versions.compare import compare, derive_status, normalize
from asiai.versions.models import EngineVersionReport, VersionStatus

# --- normalize -------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("v1.2.3", (1, 2, 3)),
        ("1.2.3", (1, 2, 3)),
        ("0.30.7", (0, 30, 7)),
        ("1.2", (1, 2)),
        ("2026.5.0", (2026, 5, 0)),
        ("0.6.66-beta", (0, 6, 66)),  # pre-release suffix dropped
        ("0.6.66+abc", (0, 6, 66)),
        ("", ()),
        ("   ", ()),
        ("latest", ()),
        (None, ()),
    ],
)
def test_normalize_semver(raw, expected):
    assert normalize(raw, "semver") == expected


@pytest.mark.parametrize(
    "raw",
    ["b8180-d979f2b17", "8180", "0.0.8180", "b8180"],
)
def test_normalize_llamacpp_build_all_representations_collapse(raw):
    """All four llama.cpp version shapes must collapse to the same build int."""
    assert normalize(raw, "llamacpp_build") == (8180,)


def test_normalize_llamacpp_build_distinct_builds():
    assert normalize("b8200", "llamacpp_build") == (8200,)
    assert normalize("0.0.8200", "llamacpp_build") == (8200,)


def test_normalize_llamacpp_build_unparseable():
    assert normalize("master", "llamacpp_build") == ()
    assert normalize("", "llamacpp_build") == ()


# --- compare ---------------------------------------------------------------


def test_compare_equal_with_and_without_v_prefix():
    assert compare("v1.2.3", "1.2.3") == 0


def test_compare_zero_pads_shorter():
    assert compare("1.2", "1.2.0") == 0
    assert compare("1.2.0", "1.2") == 0


def test_compare_ordering():
    assert compare("0.30.7", "0.31.0") == -1
    assert compare("0.31.0", "0.30.7") == 1


def test_compare_llamacpp_builds():
    assert compare("8180", "8200", "llamacpp_build") == -1
    assert compare("0.0.8180", "b8180-deadbeef", "llamacpp_build") == 0
    assert compare("b8200", "8180", "llamacpp_build") == 1


def test_compare_unparseable_is_lowest():
    # An unparseable version normalizes to () and compares below any real one.
    assert compare("latest", "1.0.0") == -1


# --- derive_status ---------------------------------------------------------


def _report(**kw) -> EngineVersionReport:
    base = {"engine_name": "x", "display": "X"}
    base.update(kw)
    return EngineVersionReport(**base)


def test_status_not_installed():
    r = _report(installed=None, running=None, available="1.0.0")
    assert derive_status(r) == VersionStatus.NOT_INSTALLED


def test_status_running_but_not_installed_is_unknown():
    # Running process but no installed record (e.g. detected via port only).
    r = _report(installed=None, running="1.0.0")
    assert derive_status(r) == VersionStatus.UNKNOWN


def test_status_running_stale():
    # brew upgraded llama.cpp to b8200 but the live process is still b8180.
    r = _report(installed="0.0.8200", running="8180", available="0.0.8200")
    assert derive_status(r, "llamacpp_build") == VersionStatus.RUNNING_STALE


def test_status_upgrade_available():
    r = _report(installed="0.30.7", running="0.30.7", available="0.31.0")
    assert derive_status(r) == VersionStatus.UPGRADE_AVAILABLE


def test_status_up_to_date():
    r = _report(installed="0.31.0", running="0.31.0", available="0.31.0")
    assert derive_status(r) == VersionStatus.UP_TO_DATE


def test_status_up_to_date_when_installed_ahead():
    # Local install ahead of brew cache (e.g. installed from source).
    r = _report(installed="0.32.0", running="0.32.0", available="0.31.0")
    assert derive_status(r) == VersionStatus.UP_TO_DATE


def test_status_no_upstream_engine_is_up_to_date():
    r = _report(installed="3.2.1", running="3.2.1", available=None, notes="no_upstream")
    assert derive_status(r) == VersionStatus.UP_TO_DATE


def test_status_installed_no_available_unknown():
    r = _report(installed="1.0.0", running="1.0.0", available=None)
    assert derive_status(r) == VersionStatus.UNKNOWN


def test_status_unparseable_available_is_unknown():
    r = _report(installed="1.0.0", running="1.0.0", available="rolling")
    assert derive_status(r) == VersionStatus.UNKNOWN
