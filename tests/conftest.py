"""Shared pytest configuration and fixtures."""

from __future__ import annotations


def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests (requires real inference engines)",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--integration"):
        import pytest

        skip_integration = pytest.mark.skip(reason="needs --integration option to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)
