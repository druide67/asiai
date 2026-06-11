"""Shared dataclasses and the status enum for the versions feature."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class VersionStatus(StrEnum):
    """Per-engine version comparison verdict.

    ``StrEnum`` so the value serializes cleanly to JSON and compares as a
    plain string. Callers still use ``.value`` explicitly where a bare
    string is wanted.
    """

    UP_TO_DATE = "up-to-date"
    UPGRADE_AVAILABLE = "upgrade-available"
    RUNNING_STALE = "running-stale"  # running != installed (process predates upgrade)
    NOT_INSTALLED = "not-installed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EngineVersionSpec:
    """How to read & compare versions for one engine.

    Source of truth for the formula/package mapping. Built either from
    asiai's internal fallback table or from aisrv's richer table delivered
    via the ``asiai.version_sources`` entry point. Frozen so a spec can be
    shared/cached without risk of mutation.
    """

    engine_name: str  # canonical asiai key: "mlxlm", "llamacpp", ...
    display: str = ""
    brew_formula: str | None = None
    brew_cask: str | None = None  # "lm-studio" (casks are listed separately)
    pip_package: str | None = None
    github_repo: str | None = None  # "ggml-org/llama.cpp" (owner/repo)
    app_bundle_path: str | None = None
    version_cmd: tuple[str, ...] | None = None  # ("rapid-mlx", "--version")
    version_scheme: str = "semver"  # "semver" | "llamacpp_build" | "git_tag"
    no_upstream: bool = False  # app-bundle / closed-source: skip "available"

    def changelog_url(self) -> str | None:
        """Best-effort upstream changelog/release URL for this engine.

        Preference order: GitHub releases page (richest), then the brew
        formula/cask page, then the PyPI project page. Returns ``None``
        when no public source is known (e.g. closed-source app bundles).
        """
        if self.github_repo:
            return f"https://github.com/{self.github_repo}/releases"
        if self.brew_formula:
            return f"https://formulae.brew.sh/formula/{self.brew_formula}"
        if self.brew_cask:
            return f"https://formulae.brew.sh/cask/{self.brew_cask}"
        if self.pip_package:
            return f"https://pypi.org/project/{self.pip_package}/"
        return None


@dataclass
class EngineVersionReport:
    """The three version coordinates for one engine plus the derived status."""

    engine_name: str
    display: str = ""
    running: str | None = None
    installed: str | None = None
    available: str | None = None
    status: VersionStatus = VersionStatus.UNKNOWN
    changelog_url: str | None = None
    source: str = "internal"  # "internal" | "aisrv" — provenance of the spec
    notes: str = ""
    # Carried through so the renderer / web can pick the right compare
    # semantics without re-loading the spec.
    version_scheme: str = "semver"

    def to_dict(self) -> dict:
        return {
            "engine_name": self.engine_name,
            "display": self.display,
            "running": self.running,
            "installed": self.installed,
            "available": self.available,
            "status": self.status.value,
            "changelog_url": self.changelog_url,
            "source": self.source,
            "notes": self.notes,
            "version_scheme": self.version_scheme,
        }
