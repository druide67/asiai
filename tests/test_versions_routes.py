"""Integration tests for the FastAPI versions routes."""

from __future__ import annotations

from unittest import mock

import pytest

pytest.importorskip("fastapi", reason="versions routes require FastAPI optional dep")
pytest.importorskip("httpx", reason="TestClient requires httpx")

from fastapi.testclient import TestClient  # noqa: E402

from asiai.versions.models import EngineVersionReport, VersionStatus  # noqa: E402
from asiai.web.app import create_app  # noqa: E402
from asiai.web.state import AppState  # noqa: E402


def _reports():
    return [
        EngineVersionReport(
            engine_name="llamacpp",
            display="llama.cpp",
            running="8180",
            installed="8200",
            available="8200",
            status=VersionStatus.RUNNING_STALE,
            changelog_url="https://github.com/ggml-org/llama.cpp/releases",
            version_scheme="llamacpp_build",
        ),
        EngineVersionReport(
            engine_name="ollama",
            display="Ollama",
            running="0.30.0",
            installed="0.30.0",
            available="0.31.0",
            status=VersionStatus.UPGRADE_AVAILABLE,
            changelog_url="https://github.com/ollama/ollama/releases",
        ),
    ]


@pytest.fixture
def client(tmp_path):
    state = AppState(engines=[], db_path=str(tmp_path / "bench.db"))
    app = create_app(state)
    return TestClient(app)


def test_api_versions_shape(client):
    with mock.patch("asiai.web.routes.versions.collect_reports", return_value=_reports()) as cr:
        resp = client.get("/api/v1/versions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["check_upstream"] is False
    names = {e["engine_name"] for e in body["engines"]}
    assert names == {"llamacpp", "ollama"}
    # Default endpoint must be offline.
    cr.assert_called_once_with(check_upstream=False)


def test_api_versions_cache_hit_second_call(client):
    with mock.patch("asiai.web.routes.versions.collect_reports", return_value=_reports()) as cr:
        client.get("/api/v1/versions")
        client.get("/api/v1/versions")
    # Second call served from the 60s cache.
    assert cr.call_count == 1


def test_api_versions_upstream_flag(client):
    with mock.patch("asiai.web.routes.versions.collect_reports", return_value=_reports()) as cr:
        resp = client.get("/api/v1/versions?upstream=1")
    assert resp.status_code == 200
    assert resp.json()["check_upstream"] is True
    cr.assert_called_once_with(check_upstream=True)


def test_offline_and_upstream_caches_are_separate(client):
    with mock.patch("asiai.web.routes.versions.collect_reports", return_value=_reports()) as cr:
        client.get("/api/v1/versions")
        client.get("/api/v1/versions?upstream=1")
    # Distinct keys -> two computations, not one.
    assert cr.call_count == 2


def test_versions_page_renders(client):
    with mock.patch("asiai.web.routes.versions.collect_reports", return_value=_reports()):
        resp = client.get("/versions")
    assert resp.status_code == 200
    assert "llama.cpp" in resp.text
    assert "Ollama" in resp.text
    assert "running stale" in resp.text
    assert "upgrade available" in resp.text
    assert "github.com/ollama/ollama/releases" in resp.text


def test_versions_grid_fragment(client):
    with mock.patch("asiai.web.routes.versions.collect_reports", return_value=_reports()):
        resp = client.get("/versions/grid-fragment")
    assert resp.status_code == 200
    # Fragment only — no full-page chrome.
    assert "<table" in resp.text
    assert "<!DOCTYPE html>" not in resp.text


def test_versions_page_shows_not_installed_engines(client):
    # The page must list ALL engines, including not-installed ones (with a
    # "not installed" marker) — a fleet-style at-a-glance view.
    reports = [
        EngineVersionReport(
            engine_name="llamacpp", display="llama.cpp", status=VersionStatus.UP_TO_DATE
        ),
        EngineVersionReport(engine_name="exo", display="Exo", status=VersionStatus.NOT_INSTALLED),
    ]
    with mock.patch("asiai.web.routes.versions.collect_reports", return_value=reports):
        resp = client.get("/versions")
    assert resp.status_code == 200
    assert "Exo" in resp.text
    assert "not installed" in resp.text


def test_versions_page_has_copypaste_actions_not_post_buttons(client):
    with mock.patch("asiai.web.routes.versions.collect_reports", return_value=_reports()):
        resp = client.get("/versions")
    text = resp.text
    # running-stale llamacpp -> restart snippet; upgrade-available ollama -> upgrade snippet.
    assert "aisctl restart llamacpp" in text
    assert "aisctl upgrade ollama --restart" in text
    # Security: copy-paste only, no live POST that would need a token in the page.
    assert "hx-post" not in text
    assert "/api/v1/fleet/" not in text
