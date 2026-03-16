"""Tests for community benchmark database client."""

from __future__ import annotations

import hashlib
import json
import re
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from asiai.community import (
    DEFAULT_API_URL,
    SubmitResult,
    build_submission,
    fetch_comparison,
    fetch_leaderboard,
    get_api_url,
    submit_benchmark,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_response(data: dict | list, status: int = 200) -> MagicMock:
    """Create a mock urllib response (context-manager compatible)."""
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.read.return_value = json.dumps(data).encode()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _sample_raw_results(engine: str = "ollama") -> list[dict]:
    """Return minimal raw results for build_submission tests."""
    return [
        {
            "engine": engine,
            "hw_chip": "Apple M1 Max",
            "os_version": "Darwin 25.3.0",
            "ts": 1709900000,
            "prompt_type": "code",
            "run_index": 0,
            "engine_version": "0.6.5",
            "model_format": "gguf",
            "model_quantization": "Q4_K_M",
        },
        {
            "engine": engine,
            "hw_chip": "Apple M1 Max",
            "os_version": "Darwin 25.3.0",
            "ts": 1709900001,
            "prompt_type": "reasoning",
            "run_index": 1,
            "engine_version": "0.6.5",
            "model_format": "gguf",
            "model_quantization": "Q4_K_M",
        },
    ]


def _sample_report(engine: str = "ollama") -> dict:
    """Return a minimal aggregated report for build_submission tests."""
    return {
        "model": "qwen3.5:35b",
        "engines": {
            engine: {
                "median_tok_s": 42.5,
                "avg_tok_s": 41.8,
                "ci95_lower": 39.0,
                "ci95_upper": 45.0,
                "median_ttft_ms": 120.0,
                "vram_bytes": 24_000_000_000,
                "stability": "stable",
                "runs_count": 5,
            },
        },
    }


# ---------------------------------------------------------------------------
# SubmitResult
# ---------------------------------------------------------------------------


class TestSubmitResult:
    def test_submit_result_defaults(self):
        r = SubmitResult(success=True)
        assert r.success is True
        assert r.submission_id == ""
        assert r.http_status == 0
        assert r.error == ""


# ---------------------------------------------------------------------------
# get_api_url
# ---------------------------------------------------------------------------


class TestGetApiUrl:
    def test_get_api_url_default(self):
        with patch.dict("os.environ", {}, clear=False):
            # Remove the override key if present.
            import os

            os.environ.pop("ASIAI_COMMUNITY_URL", None)
            assert get_api_url() == DEFAULT_API_URL

    def test_get_api_url_env_override(self):
        custom = "https://custom.example.com/v2/"
        with patch.dict("os.environ", {"ASIAI_COMMUNITY_URL": custom}):
            # Trailing slash must be stripped.
            assert get_api_url() == custom.rstrip("/")


# ---------------------------------------------------------------------------
# build_submission
# ---------------------------------------------------------------------------


class TestBuildSubmission:
    def _build(
        self,
        raw_results: list[dict] | None = None,
        report: dict | None = None,
    ) -> dict:
        """Call build_submission with mocked dependencies."""
        if raw_results is None:
            raw_results = _sample_raw_results()
        if report is None:
            report = _sample_report()

        with (
            patch("asiai.collectors.system.collect_memory") as mock_mem,
            patch("asiai.__version__", "0.7.0"),
        ):
            mock_mem.return_value = MagicMock(total=68_719_476_736)  # 64 GB
            return build_submission(raw_results, report)

    def test_build_submission_structure(self):
        payload = self._build()

        required_keys = {
            "id",
            "schema_version",
            "ts",
            "hw_chip",
            "hw_ram_gb",
            "os_version",
            "asiai_version",
            "benchmark",
            "_hash",
        }
        assert required_keys.issubset(payload.keys())

        bench = payload["benchmark"]
        assert "model" in bench
        assert "runs_per_prompt" in bench
        assert "prompts" in bench
        assert "engines" in bench

        assert payload["schema_version"] == 2
        assert payload["hw_ram_gb"] == 64
        assert payload["hw_gpu_cores"] == 0
        assert payload["asiai_version"] == "0.7.0"
        assert payload["hw_chip"] == "Apple M1 Max"
        assert payload["benchmark"]["context_size"] == 0

    def test_build_submission_hash(self):
        payload = self._build()

        # _hash must be a 64-char lowercase hex string (SHA-256).
        assert "_hash" in payload
        assert re.fullmatch(r"[0-9a-f]{64}", payload["_hash"])

        # Verify the hash was computed on the payload *before* _hash was added.
        payload_copy = dict(payload)
        del payload_copy["_hash"]
        expected = hashlib.sha256(json.dumps(payload_copy, sort_keys=True).encode()).hexdigest()
        assert payload["_hash"] == expected

    def test_build_submission_empty_results(self):
        payload = self._build(raw_results=[], report={"model": "", "engines": {}})

        assert payload["benchmark"]["model"] == ""
        assert payload["benchmark"]["engines"] == {}
        assert payload["benchmark"]["prompts"] == []
        assert payload["benchmark"]["runs_per_prompt"] == 0

    def test_build_submission_multiple_engines(self):
        raw = _sample_raw_results("ollama") + [
            {
                "engine": "lmstudio",
                "hw_chip": "Apple M1 Max",
                "os_version": "Darwin 25.3.0",
                "ts": 1709900010,
                "prompt_type": "code",
                "run_index": 0,
                "engine_version": "0.4.6",
                "model_format": "gguf",
                "model_quantization": "Q8_0",
            },
        ]
        report = _sample_report("ollama")
        report["engines"]["lmstudio"] = {
            "median_tok_s": 38.0,
            "avg_tok_s": 37.5,
            "ci95_lower": 35.0,
            "ci95_upper": 40.0,
            "median_ttft_ms": 150.0,
            "vram_bytes": 20_000_000_000,
            "stability": "stable",
            "runs_count": 3,
        }
        payload = self._build(raw_results=raw, report=report)

        engines = payload["benchmark"]["engines"]
        assert "ollama" in engines
        assert "lmstudio" in engines
        assert engines["ollama"]["median_tok_s"] == 42.5
        assert engines["lmstudio"]["median_tok_s"] == 38.0
        assert engines["lmstudio"]["engine_version"] == "0.4.6"
        assert engines["lmstudio"]["model_quantization"] == "Q8_0"


# ---------------------------------------------------------------------------
# submit_benchmark
# ---------------------------------------------------------------------------


class TestSubmitBenchmark:
    def _payload(self) -> dict:
        return {
            "id": "test-uuid-1234",
            "benchmark": {"model": "qwen3.5:35b"},
            "_hash": "abc123",
        }

    def test_submit_success(self):
        mock_resp = _make_mock_response({"status": "accepted"}, status=200)
        with patch("asiai.community.urlopen", return_value=mock_resp):
            result = submit_benchmark(
                self._payload(),
                api_url="https://test.example.com",
            )
        assert result.success is True
        assert result.http_status == 200
        assert result.submission_id == "test-uuid-1234"
        assert result.error == ""

    def test_submit_http_error(self):
        exc = HTTPError(
            url="https://test.example.com/api/v1/benchmarks",
            code=429,
            msg="Too Many Requests",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )
        with patch("asiai.community.urlopen", side_effect=exc):
            result = submit_benchmark(
                self._payload(),
                api_url="https://test.example.com",
            )
        assert result.success is False
        assert result.http_status == 429
        assert "Rate limited" in result.error

    def test_submit_network_error(self):
        exc = URLError("Connection refused")
        with patch("asiai.community.urlopen", side_effect=exc):
            result = submit_benchmark(
                self._payload(),
                api_url="https://test.example.com",
            )
        assert result.success is False
        assert result.http_status == 0
        assert "Connection refused" in result.error

    def test_submit_records_to_db(self, tmp_path):
        mock_resp = _make_mock_response({"status": "accepted"}, status=200)
        db_path = str(tmp_path / "test.db")

        with (
            patch("asiai.community.urlopen", return_value=mock_resp),
            patch("asiai.storage.db.store_community_submission") as mock_store,
        ):
            result = submit_benchmark(
                self._payload(),
                api_url="https://test.example.com",
                db_path=db_path,
            )

        assert result.success is True
        mock_store.assert_called_once()
        call_args = mock_store.call_args
        assert call_args[0][0] == db_path
        submission = call_args[0][1]
        assert submission["id"] == "test-uuid-1234"
        assert submission["status"] == "accepted"
        assert submission["model"] == "qwen3.5:35b"
        assert submission["payload_hash"] == "abc123"


# ---------------------------------------------------------------------------
# fetch_leaderboard
# ---------------------------------------------------------------------------


class TestFetchLeaderboard:
    def test_fetch_leaderboard_list_response(self):
        entries = [
            {"chip": "Apple M4 Pro", "median_tok_s": 55.0},
            {"chip": "Apple M1 Max", "median_tok_s": 42.5},
        ]
        mock_resp = _make_mock_response(entries)
        with patch("asiai.community.urlopen", return_value=mock_resp):
            result = fetch_leaderboard(api_url="https://test.example.com")
        assert len(result) == 2
        assert result[0]["chip"] == "Apple M4 Pro"

    def test_fetch_leaderboard_dict_response(self):
        data = {
            "results": [
                {"chip": "Apple M4 Pro", "median_tok_s": 55.0},
            ],
            "total": 1,
        }
        mock_resp = _make_mock_response(data)
        with patch("asiai.community.urlopen", return_value=mock_resp):
            result = fetch_leaderboard(api_url="https://test.example.com")
        assert len(result) == 1
        assert result[0]["median_tok_s"] == 55.0

    def test_fetch_leaderboard_unreachable(self):
        exc = URLError("Network is unreachable")
        with patch("asiai.community.urlopen", side_effect=exc):
            result = fetch_leaderboard(api_url="https://test.example.com")
        assert result == []


# ---------------------------------------------------------------------------
# fetch_comparison
# ---------------------------------------------------------------------------


class TestFetchComparison:
    def test_fetch_comparison_with_deltas(self):
        community_data = {
            "engines": {
                "ollama": {
                    "median_tok_s": 40.0,
                    "samples": 25,
                },
            },
        }
        mock_resp = _make_mock_response(community_data)

        local_results = {
            "engines": {
                "ollama": {
                    "median_tok_s": 44.0,
                },
            },
        }

        with patch("asiai.community.urlopen", return_value=mock_resp):
            result = fetch_comparison(
                chip="Apple M1 Max",
                model="qwen3.5:35b",
                local_results=local_results,
                api_url="https://test.example.com",
            )

        assert result["chip"] == "Apple M1 Max"
        assert result["model"] == "qwen3.5:35b"
        assert "community" in result

        ollama = result["engines"]["ollama"]
        assert ollama["local_median_tok_s"] == 44.0
        assert ollama["community_median_tok_s"] == 40.0
        assert ollama["delta_tok_s"] == 4.0
        assert ollama["delta_pct"] == 10.0  # (44-40)/40 * 100
        assert ollama["community_samples"] == 25

    def test_fetch_comparison_unreachable(self):
        exc = URLError("Network is unreachable")
        with patch("asiai.community.urlopen", side_effect=exc):
            result = fetch_comparison(
                chip="Apple M1 Max",
                model="qwen3.5:35b",
                local_results={"engines": {}},
                api_url="https://test.example.com",
            )
        assert result == {}
