"""Tests for inference activity detection (TCP connections + metrics scraping)."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from asiai.collectors.inference import (
    count_tcp_connections,
    parse_prometheus_text,
    scrape_prometheus_metrics,
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

    def test_unknown_metrics_ignored(self):
        text = "some_random_metric 42\n"
        result = parse_prometheus_text(text)
        assert result == {}

    def test_first_match_wins(self):
        """When same output key appears twice, first value wins."""
        text = (
            "llamacpp_requests_processing 3\n"
            "vllm_num_requests_running 7\n"
        )
        result = parse_prometheus_text(text)
        # llamacpp_requests_processing maps to requests_processing first
        assert result["requests_processing"] == 3


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
