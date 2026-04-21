"""MkDocs hook: copy docs/.well-known/ to site/.well-known/ after build.

MkDocs excludes dotfiles/dotdirs by default. This hook re-adds the
.well-known directory, which is required for agent-readiness manifests
(see isitagentready.com scan results).
"""

from __future__ import annotations

import shutil
from pathlib import Path


def on_post_build(config, **kwargs) -> None:
    docs_dir = Path(config["docs_dir"])
    site_dir = Path(config["site_dir"])

    src = docs_dir / ".well-known"
    dst = site_dir / ".well-known"

    if not src.is_dir():
        return

    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"[copy_well_known] copied {src} -> {dst}")
