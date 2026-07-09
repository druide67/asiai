"""MkDocs hook: expose the package version and build date to templates.

The SoftwareApplication JSON-LD in overrides/main.html used to hardcode
softwareVersion and dateModified, which drifted from the released package.
This hook reads the version from pyproject.toml (single source of truth)
and sets:

- config.extra.asiai_version  -> [project] version from pyproject.toml
- config.extra.build_date     -> build date (UTC, ISO 8601)
"""

from __future__ import annotations

import datetime
import tomllib
from pathlib import Path


def on_config(config, **kwargs):
    pyproject = Path(config["config_file_path"]).parent / "pyproject.toml"
    with pyproject.open("rb") as f:
        version = tomllib.load(f)["project"]["version"]

    config["extra"]["asiai_version"] = version
    config["extra"]["build_date"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    print(f"[inject_version] asiai_version={version} build_date={config['extra']['build_date']}")
    return config
