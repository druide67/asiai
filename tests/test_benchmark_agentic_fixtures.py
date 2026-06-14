"""Integration tests — replay anonymized bench MTP fixtures through quality gates.

Each fixture is a result JSON captured from a real bench run on Apple Silicon
hardware (M4 Pro, M5 Max) against Qwen3.6 MTP variants on llama.cpp and mlx-lm.
The fixtures use ``schema_version: agentic-v1`` (legacy: no ``quality_gates``
block written by the engine) so the tests reconstruct ``AgenticRun`` instances
from ``runs`` and feed them through the gate detectors. This validates that
the detectors give the expected verdict on real data captured in the wild.
"""

from __future__ import annotations

import getpass
import json
import re
import subprocess
from pathlib import Path

import pytest

from asiai.benchmark.agentic import AgenticRun
from asiai.benchmark.quality_gates import detect_early_stop

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "agentic"


def _load(name: str) -> dict:
    with open(FIXTURE_DIR / name) as f:
        return json.load(f)


def _runs_from_fixture(data: dict) -> list[AgenticRun]:
    return [AgenticRun(**r) for r in data["runs"]]


def test_fixture_files_exist():
    # Guards against an accidental delete of a fixture.
    expected = {
        "m4-llamacpp-27b-mtp.json",
        "m4-llamacpp-35b-mtp.json",
        "m4-mlxlm-27b-mtp.json",
        "m4-mlxlm-35b-mtp.json",
        "m5-llamacpp-27b-mtp.json",
        "m5-llamacpp-35b-mtp.json",
        "m5-mlxlm-27b-mtp.json",
        "m5-mlxlm-35b-mtp.json",
    }
    present = {p.name for p in FIXTURE_DIR.glob("*.json")}
    assert expected.issubset(present), f"missing fixtures: {expected - present}"


# Substrings that must never appear in a *published* (git-tracked) fixture:
# absolute home paths, RFC-1918 LAN IPs, hostname suffixes, Claude Code internals.
_FORBIDDEN_SUBSTRINGS = (
    "/Users/",
    "/home/",
    ".local",
    "192.168.",
    "10.0.",
    "172.16.",
    "/.claude/",
)


def _tracked_fixture_files() -> list[Path]:
    """Every git-tracked file under the fixture dir, recursive, any extension.

    Session-captured fixtures that carry local paths live in gitignored
    sub-dirs (see .gitignore ``sprint-bench-*``) and are intentionally
    excluded — they are never published, so scanning them would only
    produce false failures. Falls back to a non-recursive json+log glob
    when git is unavailable (e.g. running from an unpacked sdist)."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"],
            capture_output=True,
            text=True,
            cwd=FIXTURE_DIR,
            check=True,
        ).stdout
        files = [FIXTURE_DIR / p for p in out.split("\0") if p]
        if files:
            return files
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass
    return sorted(FIXTURE_DIR.glob("*.json")) + sorted(FIXTURE_DIR.glob("*.log"))


def test_fixtures_no_personal_data():
    """Anonymization gate — no home paths, LAN IPs, Claude Code internals, or
    the capturing user's login name leak through any *published* fixture.

    Scans every git-tracked file under the fixture tree (json, log, nested),
    not just top-level ``*.json``: the previous gate silently missed both the
    ``sprint-bench-*`` sub-dirs and the ``*.log`` captures."""
    user = getpass.getuser()
    scanned = 0
    for fp in _tracked_fixture_files():
        if not fp.is_file():
            continue
        scanned += 1
        text = fp.read_text(errors="ignore")
        for marker in _FORBIDDEN_SUBSTRINGS:
            assert marker not in text, f"{fp}: leaked {marker!r}"
        # The capturing username, as a whole word. Guarded on length to
        # avoid false positives on very short/generic CI logins.
        if len(user) >= 3:
            assert not re.search(rf"\b{re.escape(user)}\b", text), (
                f"{fp}: leaked capturing username {user!r}"
            )
    assert scanned > 0, "anonymization gate scanned no fixtures — glob/git path broken"


@pytest.mark.parametrize(
    "fixture",
    [
        "m4-llamacpp-27b-mtp.json",
        "m4-llamacpp-35b-mtp.json",
        "m5-llamacpp-27b-mtp.json",
        "m5-llamacpp-35b-mtp.json",
    ],
)
def test_llamacpp_mtp_completes_full_tokens(fixture: str):
    """llama.cpp + MTP returns the full requested token count. Early-stop is
    purely an mlx-lm-side bug — the gate must not false-positive on llamacpp."""
    data = _load(fixture)
    runs = _runs_from_fixture(data)
    es = detect_early_stop(runs)
    assert es["detected"] is False, (
        f"{fixture}: unexpected early-stop ({len(es['truncated_runs'])} truncated runs)"
    )


@pytest.mark.parametrize(
    "fixture",
    [
        "m4-mlxlm-27b-mtp.json",
        "m4-mlxlm-35b-mtp.json",
        "m5-mlxlm-27b-mtp.json",
        "m5-mlxlm-35b-mtp.json",
    ],
)
def test_mlxlm_mtp_triggers_early_stop(fixture: str):
    """mlx-lm + Qwen3.6 MTP variants exhibit the early-stop bug on prefix-test
    runs (sys identical, user different). The gate must fire on every M4 +
    M5 fixture; otherwise the gate is too lax to be useful."""
    data = _load(fixture)
    runs = _runs_from_fixture(data)
    es = detect_early_stop(runs)
    assert es["detected"] is True, f"{fixture}: early-stop missed on a known-bad fixture"
    truncated_phases = {t["phase"] for t in es["truncated_runs"]}
    # At minimum the two prefix-test runs that pair sys=A with a fresh user
    # exhibit the truncation pattern.
    assert "prefix-test-1" in truncated_phases or "prefix-test-3" in truncated_phases


def test_llamacpp_27b_mtp_verdict_no_prefix_reuse():
    """llama.cpp checkpoint-based caching does not reuse prefix when only the
    sys is identical and user differs. Fixture records 'no'."""
    data = _load("m5-llamacpp-27b-mtp.json")
    assert data["prefix_cache_reuse_verdict"] == "no"


def test_mlxlm_35b_mtp_verdict_yes_prefix_reuse():
    """mlx-lm structured prompt cache does reuse the system prefix on M5.
    Fixture records 'yes'."""
    data = _load("m5-mlxlm-35b-mtp.json")
    assert data["prefix_cache_reuse_verdict"] == "yes"


def test_fixture_hardware_tagged():
    """Fixtures should expose the hardware label so downstream consumers know
    which M-series chip captured the run."""
    valid_hw = {"m4-pro-64gb", "m5-max-128gb"}
    for fp in FIXTURE_DIR.glob("*.json"):
        data = json.loads(fp.read_text())
        assert data.get("hardware") in valid_hw, f"{fp.name}: bad hardware tag"
