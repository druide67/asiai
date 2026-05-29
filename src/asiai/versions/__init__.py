"""Engine version observability: running / installed / available.

Compares, per inference engine, three version coordinates:

- **running**: the version of the currently-started engine process
  (reuses the HTTP/shell detection in ``asiai.engines.detect``).
- **installed**: what is installed on this machine (brew / pip / app bundle).
- **available**: the latest upstream version (``brew outdated`` against the
  local brew cache by default; PyPI / GitHub releases when explicitly
  requested with ``--check-upstream``).

The package is a leaf: it imports ``asiai.cli`` only locally (inside
functions) to avoid an import cycle. The formula/package mapping table is
seeded from an internal fallback and enriched by ``asiai-inference-server``
through the ``asiai.version_sources`` entry-point group when installed.
"""

from __future__ import annotations

from asiai.versions.models import (
    EngineVersionReport,
    EngineVersionSpec,
    VersionStatus,
)

__all__ = [
    "EngineVersionReport",
    "EngineVersionSpec",
    "VersionStatus",
]
