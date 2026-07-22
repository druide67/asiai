"""Tests for the "This machine vs community" compare endpoint (ADR 0002)."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi", reason="web routes require FastAPI optional dep")
pytest.importorskip("httpx", reason="TestClient requires httpx")

from fastapi.testclient import TestClient  # noqa: E402

from asiai.storage.db import init_db, store_benchmark  # noqa: E402
from asiai.web.app import create_app  # noqa: E402
from asiai.web.routes.leaderboard import _build_compare  # noqa: E402
from asiai.web.state import AppState  # noqa: E402

NOW = int(time.time())
# A fictional chip: the endpoint test patches collect_hw_chip, and a
# real chip name would let the test pass by accident on that hardware
# if the patch target ever silently broke.
CHIP = "Apple TestChip Z9"
MODEL = "Qwen3-4B-Q5_K_XL.gguf"


def _local_run(engine: str, tok_s: float, model: str = MODEL, ts: int = NOW) -> dict:
    return {
        "ts": ts,
        "engine": engine,
        "model": model,
        "prompt_type": "code_generation",
        "tok_per_sec": tok_s,
    }


def _group(engine: str, median: float, model: str = MODEL, chip: str = CHIP, n: int = 40) -> dict:
    return {
        "engine": engine,
        "model": model,
        "hw_chip": chip,
        "median_tok_s": median,
        "samples": n,
    }


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "bench.db")
    init_db(path)
    return path


class TestBuildCompare:
    def test_strict_match_computes_delta(self, db_path):
        store_benchmark(db_path, [_local_run("llamacpp", 120.0), _local_run("llamacpp", 130.0)])
        with patch(
            "asiai.web.routes.leaderboard._cached_leaderboard",
            return_value=[_group("llamacpp", 100.0)],
        ):
            data = _build_compare(db_path, CHIP, "", 30)
        (row,) = data["rows"]
        assert row["engine"] == "llamacpp"
        assert row["local_median_tok_s"] == 125.0
        assert row["local_n"] == 2
        assert row["community_median_tok_s"] == 100.0
        assert row["delta_pct"] == 25.0
        assert data["meta"]["community_matched"] is True
        assert data["meta"]["model"] == MODEL

    def test_chip_mismatch_is_not_a_match(self, db_path):
        """'Apple M4' community group must not match an 'Apple M4 Pro' machine
        even though the upstream substring filter would return it."""
        store_benchmark(db_path, [_local_run("llamacpp", 120.0)])
        with patch(
            "asiai.web.routes.leaderboard._cached_leaderboard",
            return_value=[_group("llamacpp", 100.0, chip="Apple M4")],
        ):
            data = _build_compare(db_path, "Apple M4 Pro", "", 30)
        (row,) = data["rows"]
        assert row["community_median_tok_s"] is None
        assert row["delta_pct"] is None
        assert data["meta"]["community_matched"] is False

    def test_disjoint_engines_do_not_count_as_matched(self, db_path):
        """Community data for this chip+model on an engine this machine never
        ran is NOT a match: community_matched must stay False so the client
        renders the share band, not a 0-matched grid."""
        store_benchmark(db_path, [_local_run("mlxlm", 120.0)])
        with patch(
            "asiai.web.routes.leaderboard._cached_leaderboard",
            return_value=[_group("llamacpp", 100.0)],
        ):
            data = _build_compare(db_path, CHIP, "", 30)
        (row,) = data["rows"]
        assert row["engine"] == "mlxlm"
        assert row["community_median_tok_s"] is None
        assert data["meta"]["community_matched"] is False

    def test_different_quant_is_not_a_match(self, db_path):
        """Quantization is part of the model name, hence of the identity."""
        store_benchmark(db_path, [_local_run("llamacpp", 120.0)])
        with patch(
            "asiai.web.routes.leaderboard._cached_leaderboard",
            return_value=[_group("llamacpp", 100.0, model="Qwen3-4B-Q4_K_M.gguf")],
        ):
            data = _build_compare(db_path, CHIP, "", 30)
        (row,) = data["rows"]
        assert row["community_median_tok_s"] is None

    def test_model_match_is_case_insensitive_and_normalized(self, db_path):
        """A local path-prefixed model matches its normalized community name."""
        store_benchmark(db_path, [_local_run("mlx", 90.0, model="/models/" + MODEL)])
        with patch(
            "asiai.web.routes.leaderboard._cached_leaderboard",
            return_value=[_group("mlx", 80.0, model=MODEL.upper())],
        ):
            data = _build_compare(db_path, CHIP, "", 30)
        (row,) = data["rows"]
        assert row["community_median_tok_s"] == 80.0

    def test_no_model_param_picks_most_benched(self, db_path):
        store_benchmark(
            db_path,
            [
                _local_run("llamacpp", 100.0, model="rare.gguf"),
                _local_run("llamacpp", 110.0),
                _local_run("mlx", 120.0),
            ],
        )
        with patch(
            "asiai.web.routes.leaderboard._cached_leaderboard",
            return_value=[],
        ):
            data = _build_compare(db_path, CHIP, "", 30)
        assert data["meta"]["model"] == MODEL
        assert [r["engine"] for r in data["rows"]] == ["llamacpp", "mlx"]

    def test_engine_match_is_case_insensitive(self, db_path):
        """ADR: engines compare case-insensitively across the two sides."""
        store_benchmark(db_path, [_local_run("llamacpp", 120.0)])
        with patch(
            "asiai.web.routes.leaderboard._cached_leaderboard",
            return_value=[_group("LlamaCpp", 100.0)],
        ):
            data = _build_compare(db_path, CHIP, "", 30)
        (row,) = data["rows"]
        assert row["community_median_tok_s"] == 100.0

    def test_nonpositive_tok_s_rows_are_ignored(self, db_path):
        store_benchmark(
            db_path,
            [
                _local_run("llamacpp", 120.0),
                _local_run("llamacpp", 0.0),
                _local_run("llamacpp", -5.0),
            ],
        )
        with patch("asiai.web.routes.leaderboard._cached_leaderboard", return_value=[]):
            data = _build_compare(db_path, CHIP, "", 30)
        (row,) = data["rows"]
        assert row["local_median_tok_s"] == 120.0
        assert row["local_n"] == 1

    def test_model_filter_is_a_substring_match(self, db_path):
        """The page's model field filters by substring (same semantics as
        the table): 'qwen' must select the Qwen model, not empty out."""
        store_benchmark(db_path, [_local_run("llamacpp", 120.0)])
        with patch("asiai.web.routes.leaderboard._cached_leaderboard", return_value=[]):
            data = _build_compare(db_path, CHIP, "qwen", 30)
        assert data["meta"]["model"] == MODEL
        assert data["rows"][0]["local_median_tok_s"] == 120.0

    def test_unmatched_filter_reports_no_local_match(self, db_path):
        """Local runs exist but none contains the filter text — the reason
        distinguishes this from an empty window."""
        store_benchmark(db_path, [_local_run("llamacpp", 120.0)])
        with patch("asiai.web.routes.leaderboard._cached_leaderboard", return_value=[]):
            data = _build_compare(db_path, CHIP, "gemma", 30)
        assert data["rows"] == []
        assert data["meta"]["reason"] == "no_local_match"

    def test_boolean_samples_from_upstream_is_not_a_count(self, db_path):
        store_benchmark(db_path, [_local_run("llamacpp", 120.0)])
        group = _group("llamacpp", 100.0)
        group["samples"] = True
        with patch(
            "asiai.web.routes.leaderboard._cached_leaderboard",
            return_value=[group],
        ):
            data = _build_compare(db_path, CHIP, "", 30)
        assert data["rows"][0]["community_n"] == 0

    def test_no_local_runs_yields_empty_rows(self, db_path):
        with patch("asiai.web.routes.leaderboard._cached_leaderboard", return_value=[]):
            data = _build_compare(db_path, CHIP, "", 30)
        assert data["rows"] == []
        assert data["meta"]["community_matched"] is False

    def test_runs_outside_window_are_excluded(self, db_path):
        store_benchmark(db_path, [_local_run("llamacpp", 100.0, ts=NOW - 40 * 86400)])
        with patch("asiai.web.routes.leaderboard._cached_leaderboard", return_value=[]):
            data = _build_compare(db_path, CHIP, "", 30)
        assert data["rows"] == []

    def test_empty_chip_skips_community_fetch(self, db_path):
        store_benchmark(db_path, [_local_run("llamacpp", 100.0)])
        with patch("asiai.web.routes.leaderboard._cached_leaderboard") as m:
            data = _build_compare(db_path, "", "", 30)
        m.assert_not_called()
        (row,) = data["rows"]
        assert row["community_median_tok_s"] is None


class TestCompareEndpoint:
    @pytest.fixture
    def client(self, db_path):
        state = AppState(engines=[], db_path=db_path)
        return TestClient(create_app(state))

    def test_endpoint_shape(self, client, db_path):
        store_benchmark(db_path, [_local_run("llamacpp", 120.0)])
        with (
            patch(
                "asiai.collectors.system.collect_hw_chip",
                return_value=CHIP,
            ),
            patch(
                "asiai.web.routes.leaderboard._cached_leaderboard",
                return_value=[_group("llamacpp", 100.0)],
            ),
        ):
            resp = client.get("/api/v1/leaderboard/compare?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["chip"] == CHIP
        assert data["meta"]["window_days"] == 30
        assert data["rows"][0]["delta_pct"] == 20.0

    def test_endpoint_validates_days(self, client):
        assert client.get("/api/v1/leaderboard/compare?days=0").status_code == 422
        assert client.get("/api/v1/leaderboard/compare?days=999").status_code == 422
