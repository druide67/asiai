"""Version normalization and comparison.

The hard part is reconciling the *four* live representations of a
llama.cpp version that flow through asiai:

- ``"b8180-d979f2b17"`` — raw ``build_info`` string from ``/props``
- ``"8180"`` — bare build number returned by ``detect_engine_type``
- ``"0.0.8180"`` — the adapter's parsed ``build_info.version``
- ``"b8200"`` — a GitHub release tag

Under the ``llamacpp_build`` scheme all four must collapse to the single
build integer ``(8180,)`` / ``(8200,)`` or the status will be perpetually
wrong. The ``semver`` and ``git_tag`` schemes handle the common
``1.2.3`` / ``v1.2.3`` shapes.
"""

from __future__ import annotations

import re

from asiai.versions.models import EngineVersionReport, VersionStatus

# A leading numeric component, tolerating a ``v`` or ``b`` prefix
# (``v1.2.3``, ``b8200``). Splits on ``.``, ``-``, ``+``, ``_``.
_SPLIT_RE = re.compile(r"[.\-+_]")
_LEADING_INT_RE = re.compile(r"^(\d+)")


def normalize(raw: str | None, scheme: str = "semver") -> tuple[int, ...]:
    """Normalize a raw version string into a comparable integer tuple.

    Returns an empty tuple for unparseable / empty input, which compares
    as "lowest" and lets callers treat it as UNKNOWN.

    Examples::

        normalize("v1.2.3")                         -> (1, 2, 3)
        normalize("0.30.7")                         -> (0, 30, 7)
        normalize("b8180-d979f2b17", "llamacpp_build") -> (8180,)
        normalize("8180", "llamacpp_build")            -> (8180,)
        normalize("0.0.8180", "llamacpp_build")        -> (8180,)
        normalize("latest")                         -> ()
    """
    if not raw:
        return ()
    s = raw.strip()
    if not s:
        return ()

    if scheme == "llamacpp_build":
        return _normalize_llamacpp_build(s)

    # semver / git_tag: strip a single leading v/b, split, keep the leading
    # integer of each field until a non-numeric field is hit (drops
    # pre-release suffixes like ``-rc1`` cleanly because that field has no
    # leading digit).
    s = _strip_prefix(s)
    parts: list[int] = []
    for field_str in _SPLIT_RE.split(s):
        m = _LEADING_INT_RE.match(field_str)
        if not m:
            break
        parts.append(int(m.group(1)))
    return tuple(parts)


def _strip_prefix(s: str) -> str:
    """Strip a single leading ``v`` or ``b`` when followed by a digit."""
    if len(s) >= 2 and s[0] in ("v", "V", "b", "B") and s[1].isdigit():
        return s[1:]
    return s


def _normalize_llamacpp_build(s: str) -> tuple[int, ...]:
    """Collapse any llama.cpp version representation to ``(build,)``.

    Strategy: strip a ``b`` prefix, split into numeric fields, and take the
    *last* numeric field. ``0.0.8180`` -> 8180, ``8180`` -> 8180,
    ``b8180-d979f2b17`` -> 8180, ``b8200`` -> 8200. The trailing git short
    hash (``d979f2b17``) has no leading digit after the split on ``-`` so it
    is discarded.
    """
    s = _strip_prefix(s)
    nums: list[int] = []
    for field_str in _SPLIT_RE.split(s):
        m = _LEADING_INT_RE.match(field_str)
        if m:
            nums.append(int(m.group(1)))
    if not nums:
        return ()
    return (nums[-1],)


def compare(a: str | None, b: str | None, scheme: str = "semver") -> int:
    """Return -1 if a<b, 0 if equal, 1 if a>b, under *scheme*.

    Shorter tuples are right-padded with zeros so ``1.2`` == ``1.2.0``.
    Unparseable inputs normalize to ``()`` and therefore compare as lowest.
    """
    ta = normalize(a, scheme)
    tb = normalize(b, scheme)
    width = max(len(ta), len(tb))
    pa = ta + (0,) * (width - len(ta))
    pb = tb + (0,) * (width - len(tb))
    if pa < pb:
        return -1
    if pa > pb:
        return 1
    return 0


def derive_status(report: EngineVersionReport, scheme: str = "semver") -> VersionStatus:
    """Derive the verdict from a report's three version coordinates.

    Precedence:
      1. nothing installed -> NOT_INSTALLED
      2. running present and != installed -> RUNNING_STALE (process
         predates an upgrade; a restart would reconcile them)
      3. available present and installed < available -> UPGRADE_AVAILABLE
      4. all parseable and installed >= available -> UP_TO_DATE
      5. otherwise -> UNKNOWN
    """
    installed = report.installed
    running = report.running
    available = report.available

    if not installed:
        # If it isn't installed but something is running, that's still a
        # meaningful "running but not tracked" state — surface as UNKNOWN
        # rather than NOT_INSTALLED so the row isn't misread as "absent".
        if running:
            return VersionStatus.UNKNOWN
        return VersionStatus.NOT_INSTALLED

    # A running process on a different version than what's installed means
    # the binary was upgraded under a live process.
    if running and normalize(installed, scheme) and normalize(running, scheme):
        if compare(running, installed, scheme) != 0:
            return VersionStatus.RUNNING_STALE

    if available:
        cmp = compare(installed, available, scheme)
        if normalize(installed, scheme) == () or normalize(available, scheme) == ():
            return VersionStatus.UNKNOWN
        if cmp < 0:
            return VersionStatus.UPGRADE_AVAILABLE
        return VersionStatus.UP_TO_DATE

    # Installed but no upstream signal: only meaningful conclusion is that
    # running matches installed (checked above) — treat as up-to-date for
    # engines we can't compare upstream (no_upstream), else unknown.
    if report.notes and "no_upstream" in report.notes:
        return VersionStatus.UP_TO_DATE
    return VersionStatus.UNKNOWN
