"""Collect the three version coordinates: running, installed, available.

- ``running_versions`` reuses the engine adapters' ``version()`` methods.
- ``installed_version`` consolidates the brew/pip/version-cmd/app-bundle
  logic that ``doctor.py`` previously duplicated per engine (DRY).
- ``brew_outdated`` runs a single ``brew outdated --json=v2`` against the
  local brew cache (no network) and powers the offline "available" column.

Network fetches (PyPI / GitHub) live in ``asiai.versions.upstream`` and are
opt-in.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess

from asiai.versions.models import EngineVersionSpec

logger = logging.getLogger("asiai.versions.collectors")

# Matches a semver-ish token anywhere in a string (mirrors rapidmlx adapter).
_VERSION_RE = re.compile(r"\b(\d+(?:\.\d+){1,}\S*)")

# Common Homebrew prefixes to probe when ``brew`` is not on PATH.
_BREW_CANDIDATES = ("/opt/homebrew/bin/brew", "/usr/local/bin/brew")


def _brew_bin() -> str | None:
    """Locate the brew executable (PATH first, then standard prefixes)."""
    found = shutil.which("brew")
    if found:
        return found
    for candidate in _BREW_CANDIDATES:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


# ---------------------------------------------------------------------------
# running
# ---------------------------------------------------------------------------


def running_versions(urls: list[str] | None = None) -> dict[str, str]:
    """Map ``engine_name -> running version`` for every detected engine.

    Reuses ``cli._discover_engines`` (imported locally to avoid a
    ``cli -> versions -> cli`` import cycle) and each adapter's
    ``version()``. Empty dict if nothing is reachable. Never raises.
    """
    from asiai.cli import _discover_engines

    out: dict[str, str] = {}
    try:
        engines = _discover_engines(urls)
    except Exception as e:  # noqa: BLE001 — detection must never crash the report
        logger.debug("engine discovery failed: %s", e)
        return out

    for engine in engines:
        try:
            ver = engine.version()
        except Exception as e:  # noqa: BLE001
            logger.debug("version() failed for %s: %s", getattr(engine, "name", "?"), e)
            continue
        if ver:
            # If the same engine type is detected on multiple ports, keep the
            # first non-empty version (they should agree for one binary).
            out.setdefault(engine.name, ver)
    return out


# ---------------------------------------------------------------------------
# installed
# ---------------------------------------------------------------------------


def installed_version(spec: EngineVersionSpec) -> str | None:
    """Resolve the installed version for *spec*, or None if not installed.

    Resolution order: brew formula, brew cask, pip package, ``version_cmd``,
    app-bundle plist. The first source that yields a version wins. For
    engines that are both a brew formula and a pip package (e.g. mlx-lm),
    brew takes precedence — that matches what ``doctor`` reports and what
    aisrv's ``UPGRADE_FORMULAS`` targets.
    """
    if spec.brew_formula:
        v = _brew_formula_version(spec.brew_formula)
        if v:
            return v
    if spec.brew_cask:
        v = _brew_cask_version(spec.brew_cask)
        if v:
            return v
    if spec.pip_package:
        v = _pip_version(spec.pip_package)
        if v:
            return v
    if spec.version_cmd:
        v = _version_cmd_output(spec.version_cmd)
        if v:
            return v
    if spec.app_bundle_path:
        v = _app_bundle_version(spec.app_bundle_path)
        if v:
            return v
    return None


def _brew_formula_version(formula: str) -> str | None:
    """``brew list --versions <formula>`` -> last token, or None."""
    brew = _brew_bin()
    if not brew:
        return None
    try:
        out = subprocess.run(
            [brew, "list", "--versions", formula],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("brew list %s failed: %s", formula, e)
        return None
    # "llama.cpp 8180" -> "8180"; empty if not installed.
    parts = out.split()
    return parts[-1] if len(parts) >= 2 else None


def _brew_cask_version(cask: str) -> str | None:
    """``brew list --cask --versions <cask>`` -> last token, or None."""
    brew = _brew_bin()
    if not brew:
        return None
    try:
        out = subprocess.run(
            [brew, "list", "--cask", "--versions", cask],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("brew list --cask %s failed: %s", cask, e)
        return None
    parts = out.split()
    return parts[-1] if len(parts) >= 2 else None


def _pip_version(package: str) -> str | None:
    """``<python> -m pip show <package>`` -> Version field, or None.

    Uses ``sys.executable`` so the lookup hits the environment asiai runs
    under — which can legitimately differ from the venv running the engine.
    """
    import sys

    try:
        out = subprocess.run(
            [sys.executable, "-m", "pip", "show", package],
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("pip show %s failed: %s", package, e)
        return None
    for line in out.splitlines():
        if line.lower().startswith("version:"):
            return line.split(":", 1)[1].strip() or None
    return None


def _version_cmd_output(cmd: tuple[str, ...]) -> str | None:
    """Run a ``--version`` style command and regex-extract the version."""
    argv = list(cmd)
    # Resolve the binary; tolerate absolute paths not on PATH.
    bin_path = shutil.which(argv[0])
    if not bin_path:
        for candidate in (f"/opt/homebrew/bin/{argv[0]}", f"/usr/local/bin/{argv[0]}"):
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                bin_path = candidate
                break
    if not bin_path:
        return None
    try:
        result = subprocess.run(
            [bin_path, *argv[1:]],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("%s failed: %s", argv, e)
        return None
    # Some tools print the version to stderr.
    text = (result.stdout or "") + "\n" + (result.stderr or "")
    m = _VERSION_RE.search(text)
    return m.group(1) if m else None


def _app_bundle_version(plist_path: str) -> str | None:
    """Read ``CFBundleShortVersionString`` from an app bundle's Info.plist.

    *plist_path* may be the .app path or the Info.plist path; PlistBuddy is
    pointed at ``<app>/Contents/Info.plist`` when given a .app directory.
    """
    target = plist_path
    if plist_path.endswith(".app"):
        target = os.path.join(plist_path, "Contents", "Info.plist")
    if not os.path.exists(target):
        return None
    try:
        out = subprocess.run(
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleShortVersionString",
                target,
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("PlistBuddy %s failed: %s", target, e)
        return None
    if out.returncode == 0 and out.stdout.strip():
        return out.stdout.strip().split("+")[0]
    return None


# ---------------------------------------------------------------------------
# available (offline: brew outdated)
# ---------------------------------------------------------------------------


def brew_outdated() -> dict[str, str]:
    """Return ``{formula_or_cask_name: latest_version}`` for outdated items.

    Runs one ``brew outdated --json=v2``. The reported "current" version is
    what brew knows about from its *local* cache (no network) — so this can
    lag reality without a prior ``brew update``. A name absent from the
    output is already up-to-date. Never raises; returns ``{}`` on any
    failure or malformed output.
    """
    brew = _brew_bin()
    if not brew:
        return {}
    try:
        result = subprocess.run(
            # No --greedy: it probes auto-updating casks (slow, sometimes
            # network-bound) and we only care about the formulas/casks we map
            # engines to. Keeps the call fast enough for the doctor recap.
            [brew, "outdated", "--json=v2"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("brew outdated failed: %s", e)
        return {}
    raw = result.stdout.strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as e:
        logger.debug("brew outdated JSON parse failed: %s", e)
        return {}
    if not isinstance(data, dict):
        return {}

    out: dict[str, str] = {}
    for key in ("formulae", "casks"):
        for item in data.get(key, []) or []:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            current = item.get("current_version")
            if isinstance(name, str) and isinstance(current, str) and current:
                out[name] = current
    return out
