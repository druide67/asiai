"""Tests for inference activity detection (TCP connections + metrics scraping)."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from asiai.collectors.inference import (
    count_tcp_connections,
    parse_prometheus_text,
    scrape_prometheus_metrics,
    scrape_slots_kv,
)


class TestCountTcpConnections:
    """Tests for count_tcp_connections() via mocked lsof."""

    @patch("asiai.collectors.inference.subprocess.run")
    def test_no_connections(self, mock_run):
        """Empty output (header only) returns 0."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="COMMAND  PID USER  FD  TYPE DEVICE SIZE/OFF NODE NAME\n",
        )
        assert count_tcp_connections(11434) == 0

    @patch("asiai.collectors.inference.subprocess.run")
    def test_two_connections(self, mock_run):
        """Header + 2 lines = 2 connections."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "COMMAND  PID USER  FD  TYPE DEVICE SIZE/OFF NODE NAME\n"
                "ollama  1234 user  10u IPv4 0x1234 0t0 TCP "
                "127.0.0.1:11434->127.0.0.1:50000 (ESTABLISHED)\n"
                "ollama  1234 user  11u IPv4 0x1235 0t0 TCP "
                "127.0.0.1:11434->127.0.0.1:50001 (ESTABLISHED)\n"
            ),
        )
        assert count_tcp_connections(11434) == 2

    @patch("asiai.collectors.inference.subprocess.run")
    def test_lsof_failure(self, mock_run):
        """Non-zero return code gives 0."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert count_tcp_connections(11434) == 0

    @patch("asiai.collectors.inference.subprocess.run")
    def test_lsof_timeout(self, mock_run):
        """Timeout gives 0."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="lsof", timeout=5)
        assert count_tcp_connections(11434) == 0

    def test_invalid_port(self):
        """Port <= 0 returns 0 without calling lsof."""
        assert count_tcp_connections(0) == 0
        assert count_tcp_connections(-1) == 0


class TestParsePrometheusText:
    """Tests for parse_prometheus_text() with sample Prometheus output."""

    def test_llamacpp_metrics(self):
        text = """\
# HELP llamacpp_requests_processing Number of requests processing
# TYPE llamacpp_requests_processing gauge
llamacpp_requests_processing 3
# HELP llamacpp_tokens_predicted_total Total predicted tokens
# TYPE llamacpp_tokens_predicted_total counter
llamacpp_tokens_predicted_total 12345
# HELP llamacpp_kv_cache_usage_ratio KV cache usage
# TYPE llamacpp_kv_cache_usage_ratio gauge
llamacpp_kv_cache_usage_ratio 0.42
"""
        result = parse_prometheus_text(text)
        assert result["requests_processing"] == 3
        assert result["tokens_predicted_total"] == 12345
        assert result["kv_cache_usage_ratio"] == pytest.approx(0.42)

    def test_vllm_metrics(self):
        text = """\
# HELP vllm_num_requests_running Running requests
# TYPE vllm_num_requests_running gauge
vllm_num_requests_running 1
# HELP vllm_generation_tokens_total Total generated tokens
# TYPE vllm_generation_tokens_total counter
vllm_generation_tokens_total 9876
"""
        result = parse_prometheus_text(text)
        assert result["requests_processing"] == 1
        assert result["tokens_predicted_total"] == 9876

    def test_empty_text(self):
        assert parse_prometheus_text("") == {}

    def test_comments_only(self):
        text = "# HELP foo bar\n# TYPE foo gauge\n"
        assert parse_prometheus_text(text) == {}

    def test_metric_with_labels(self):
        """Metrics with labels should be parsed correctly."""
        text = 'llamacpp_requests_processing{model="llama"} 5\n'
        result = parse_prometheus_text(text)
        assert result["requests_processing"] == 5

    def test_llamacpp_colon_namespace(self):
        """Current llama-server exposes ``llamacpp:metric`` (Prometheus
        namespace colon). The old ``\\w+`` pattern truncated the name at
        the colon and every activity metric silently read as zero —
        reproduced live on the fleet (deploy 1.19.1 finding)."""
        text = """\
# TYPE llamacpp:tokens_predicted_total counter
llamacpp:tokens_predicted_total 7892
llamacpp:requests_processing 2
llamacpp:kv_cache_usage_ratio 0.17
"""
        result = parse_prometheus_text(text)
        assert result["tokens_predicted_total"] == 7892
        assert result["requests_processing"] == 2
        assert result["kv_cache_usage_ratio"] == pytest.approx(0.17)

    def test_unknown_metrics_ignored(self):
        text = "some_random_metric 42\n"
        result = parse_prometheus_text(text)
        assert result == {}

    def test_first_match_wins(self):
        """When same output key appears twice, first value wins."""
        text = "llamacpp_requests_processing 3\nvllm_num_requests_running 7\n"
        result = parse_prometheus_text(text)
        # llamacpp_requests_processing maps to requests_processing first
        assert result["requests_processing"] == 3


def _slots_response(payload):
    """Build a mocked urlopen context manager returning ``payload`` as JSON."""
    import json as _json

    mock_resp = MagicMock()
    mock_resp.read.return_value = _json.dumps(payload).encode()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestScrapeSlotsKv:
    """Tests for scrape_slots_kv() — the /slots KV occupancy source."""

    @patch("urllib.request.urlopen")
    def test_occupancy_summed_over_all_slots(self, mock_urlopen):
        """Real-world shape (llama-server b9580): idle slots keep their hot
        cache, so occupancy sums over ALL slots, not just processing ones."""
        mock_urlopen.return_value = _slots_response(
            [
                {"id": 0, "n_ctx": 40960, "is_processing": True, "n_prompt_tokens": 1219},
                {"id": 1, "n_ctx": 40960, "is_processing": False, "n_prompt_tokens": 2048},
            ]
        )
        result = scrape_slots_kv("http://localhost:8092")
        assert result["kv_cache_tokens"] == 3267
        assert result["kv_cache_usage_ratio"] == pytest.approx(3267 / 81920)

    @patch("urllib.request.urlopen")
    def test_numbers_only_no_prompt_text_leaks(self, mock_urlopen):
        """/slots carries prompt fragments — nothing textual may leave."""
        mock_urlopen.return_value = _slots_response(
            [
                {
                    "id": 0,
                    "n_ctx": 4096,
                    "is_processing": True,
                    "n_prompt_tokens": 100,
                    "prompt": "TOP-SECRET user prompt content",
                    "params": {"grammar": "sensitive grammar text"},
                }
            ]
        )
        result = scrape_slots_kv("http://localhost:8092")
        assert "TOP-SECRET" not in repr(result)
        assert all(isinstance(v, (int, float)) for v in result.values())

    @patch("urllib.request.urlopen")
    def test_ratio_capped_at_one(self, mock_urlopen):
        """Context-shift can hold more than n_ctx transiently — cap the bar."""
        mock_urlopen.return_value = _slots_response(
            [{"id": 0, "n_ctx": 1000, "n_prompt_tokens": 1500}]
        )
        result = scrape_slots_kv("http://localhost:8092")
        assert result["kv_cache_usage_ratio"] == 1.0

    @patch("urllib.request.urlopen")
    def test_unreachable_returns_empty(self, mock_urlopen):
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("Connection refused")
        assert scrape_slots_kv("http://localhost:8092") == {}

    @patch("urllib.request.urlopen")
    def test_non_list_body_returns_empty(self, mock_urlopen):
        """Engines without the endpoint often answer a JSON error object."""
        mock_urlopen.return_value = _slots_response({"error": "not supported"})
        assert scrape_slots_kv("http://localhost:8092") == {}

    @patch("urllib.request.urlopen")
    def test_zero_capacity_returns_empty(self, mock_urlopen):
        mock_urlopen.return_value = _slots_response([])
        assert scrape_slots_kv("http://localhost:8092") == {}

    def test_bad_base_url_returns_empty(self):
        assert scrape_slots_kv("") == {}
        assert scrape_slots_kv("not-a-url") == {}


class TestScrapePrometheusMetrics:
    """Tests for scrape_prometheus_metrics() with mocked urlopen."""

    @patch("urllib.request.urlopen")
    def test_scrape_success(self, mock_urlopen):
        body = b"llamacpp_requests_processing 2\n"
        mock_resp = MagicMock()
        mock_resp.read.return_value = body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = scrape_prometheus_metrics("http://localhost:8080/metrics")
        assert result["requests_processing"] == 2

    @patch("urllib.request.urlopen")
    def test_scrape_unreachable(self, mock_urlopen):
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("Connection refused")
        result = scrape_prometheus_metrics("http://localhost:8080/metrics")
        assert result == {}
