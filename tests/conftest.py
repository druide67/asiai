"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import importlib
import os
import sys
from unittest.mock import MagicMock

import pytest

from asiai.engines.base import InferenceEngine, ModelInfo
from asiai.storage.db import init_db

# ---------------------------------------------------------------------------
# Hermetic isolation (audit 2026-06-12)
# ---------------------------------------------------------------------------
# Every user-facing path (DB, configs, fleet/auth state, daemon plists, cards,
# audit log) is a module constant computed AT IMPORT with expanduser("~/…") or
# Path.home(). Running the suite therefore touched the developer's real files —
# `main(["bench"])` without --db even migrated the real metrics.db. Setting
# $HOME in a fixture is not enough: those constants were already frozen against
# the real home before any test ran. So we BOTH point $HOME/XDG at a tmp dir
# (covers runtime resolutions — card.py, web/app.py — and any module imported
# after the fixture runs) AND re-point the already-frozen constants below.

# (module, attribute, path relative to the fake home)
_FROZEN_PATHS = [
    ("asiai.storage.db", "DEFAULT_DB_PATH", ".local/share/asiai/metrics.db"),
    ("asiai.daemon", "DATA_DIR", ".local/share/asiai"),
    ("asiai.daemon", "PLIST_DIR", "Library/LaunchAgents"),
    ("asiai.auth.audit", "AUDIT_DIR", ".local/share/asiai"),
    ("asiai.auth.audit", "AUDIT_PATH", ".local/share/asiai/fleet-audit.jsonl"),
    ("asiai.auth.config", "CONFIG_DIR", ".config/asiai"),
    ("asiai.auth.config", "CONFIG_PATH", ".config/asiai/auth.json"),
    ("asiai.auth.config", "LOCK_PATH", ".config/asiai/auth.lock"),
    ("asiai.auth.loopback", "STATE_DIR", ".local/state/asiai"),
    ("asiai.auth.loopback", "TOKEN_PATH", ".local/state/asiai/aisctl-serve-token"),
    ("asiai.engines.config", "CONFIG_DIR", ".config/asiai"),
    ("asiai.engines.config", "CONFIG_PATH", ".config/asiai/engines.json"),
    ("asiai.fleet.config", "CONFIG_DIR", ".config/asiai"),
    ("asiai.fleet.config", "CONFIG_PATH", ".config/asiai/fleet.json"),
    ("asiai.fleet.config", "LOCK_PATH", ".config/asiai/fleet.lock"),
    ("asiai.community", "_AGENT_JSON", ".local/share/asiai/agent.json"),
]
# DEFAULT_DB_PATH is ALSO imported as a module-level copy in these modules, so
# patching only asiai.storage.db would miss them once they are loaded.
_DB_COPIES = ["asiai.doctor", "asiai.benchmark.regression", "asiai.mcp.server"]

# Real paths captured before any fixture patches $HOME — the guard test asserts
# the isolated paths differ from these.
REAL_DB_PATH = os.path.expanduser("~/.local/share/asiai/metrics.db")
REAL_FLEET_CONFIG = os.path.expanduser("~/.config/asiai/fleet.json")


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path, monkeypatch):
    """Redirect every user-facing path to a throwaway home for each test."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / ".local" / "state"))

    for mod_name, attr, rel in _FROZEN_PATHS:
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue  # optional dependency (e.g. mcp) not installed
        if hasattr(mod, attr):
            monkeypatch.setattr(mod, attr, str(home / rel))

    db_path = str(home / ".local" / "share" / "asiai" / "metrics.db")
    for mod_name in _DB_COPIES:
        mod = sys.modules.get(mod_name)
        if mod is not None and hasattr(mod, "DEFAULT_DB_PATH"):
            monkeypatch.setattr(mod, "DEFAULT_DB_PATH", db_path)


def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests (requires real inference engines)",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--integration"):
        skip_integration = pytest.mark.skip(reason="needs --integration option to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite database, initialized with the asiai schema."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path


@pytest.fixture
def mock_engine():
    """Create a mock InferenceEngine (ollama, reachable, no models)."""
    engine = MagicMock(spec=InferenceEngine)
    engine.name = "ollama"
    engine.url = "http://localhost:11434"
    engine.base_url = "http://localhost:11434"
    engine.is_reachable.return_value = True
    engine.list_running.return_value = []
    engine.list_available.return_value = []
    engine.version.return_value = "0.17.4"
    return engine


@pytest.fixture
def mock_engine_with_model():
    """Create a mock engine with a loaded model (42 tok/s test model)."""
    engine = MagicMock(spec=InferenceEngine)
    engine.name = "ollama"
    engine.url = "http://localhost:11434"
    engine.base_url = "http://localhost:11434"
    engine.is_reachable.return_value = True
    model = ModelInfo(
        name="test-model:7b",
        size_vram=4_000_000_000,
        format="gguf",
        quantization="Q4_K_M",
    )
    engine.list_running.return_value = [model]
    engine.list_available.return_value = []
    engine.version.return_value = "0.17.4"
    return engine
