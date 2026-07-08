"""Tests for the /api/bench-runs endpoints (History multi-type view)."""

from __future__ import annotations

import json
import time

import pytest

pytest.importorskip("fastapi", reason="web routes require FastAPI optional dep")
pytest.importorskip("httpx", reason="TestClient requires httpx")

from fastapi.testclient import TestClient  # noqa: E402

from asiai.storage.db import init_db, store_bench_run  # noqa: E402
from asiai.web.app import create_app  # noqa: E402
from asiai.web.state import AppState  # noqa: E402

NOW = int(time.time())


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "bench.db")
    init_db(db_path)
    store_bench_run(
        db_path,
        {
            "ts": NOW,
            "finished_ts": NOW + 60,
            "bench_type": "code",
            "engine": "llamacpp",
            "engine_version": "b9580",
            "model": "qwen3.5:4b",
            "asiai_version": "1.24.0",
            "score_primary": 90.0,
            "score_label": "mean_pct_clean_deterministic",
            "gates_failed": 0,
            "payload": json.dumps({"code_results": {"tool_call": {"pct_clean": 90.0}}}),
        },
    )
    store_bench_run(
        db_path,
        {
            "ts": NOW - 100,
            "bench_type": "agentic",
            "engine": "llamacpp",
            "model": "qwen3.5:4b",
            "score_primary": 0.93,
            "score_label": "reuse_fraction",
            "gates_failed": 1,
            "payload": "{}",
        },
    )
    state = AppState(engines=[], db_path=db_path)
    return TestClient(create_app(state))


class TestBenchRunsList:
    def test_list_without_payload(self, client):
        resp = client.get("/api/bench-runs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert all("payload" not in r for r in body["runs"])
        # Newest first
        assert body["runs"][0]["bench_type"] == "code"

    def test_type_filter(self, client):
        body = client.get("/api/bench-runs?type=agentic").json()
        assert body["count"] == 1
        assert body["runs"][0]["score_label"] == "reuse_fraction"
        assert body["runs"][0]["gates_failed"] == 1

    def test_unknown_type_rejected(self, client):
        assert client.get("/api/bench-runs?type=evil").status_code == 422

    def test_model_and_engine_filters(self, client):
        assert client.get("/api/bench-runs?model=qwen3.5:4b").json()["count"] == 2
        assert client.get("/api/bench-runs?engine=nope").json()["count"] == 0

    def test_hours_window(self, client):
        # Both rows are recent; a 1-hour window keeps them.
        assert client.get("/api/bench-runs?hours=1").json()["count"] == 2


class TestBenchRunDetail:
    def test_detail_includes_parsed_payload(self, client):
        run_id = client.get("/api/bench-runs?type=code").json()["runs"][0]["id"]
        resp = client.get(f"/api/bench-runs/{run_id}")
        assert resp.status_code == 200
        run = resp.json()
        assert run["payload"]["code_results"]["tool_call"]["pct_clean"] == 90.0

    def test_missing_run_404(self, client):
        assert client.get("/api/bench-runs/424242").status_code == 404

    def test_non_numeric_id_422(self, client):
        assert client.get("/api/bench-runs/abc").status_code == 422
