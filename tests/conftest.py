"""Shared pytest configuration and fixtures."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from asiai.engines.base import InferenceEngine, ModelInfo
from asiai.storage.db import init_db


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
