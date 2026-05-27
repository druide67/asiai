"""Unit tests for asiai.web.fleet_metrics."""

from __future__ import annotations

import pytest

from asiai.web import fleet_metrics


@pytest.fixture(autouse=True)
def reset_metrics():
    fleet_metrics.reset_for_tests()
    yield
    fleet_metrics.reset_for_tests()


class TestRecord:
    def test_ok_increments_command_counter(self):
        fleet_metrics.record(command="purge", status="ok", duration_ms=42)
        out = fleet_metrics.format_fleet_metrics()
        assert 'asiai_fleet_command_total{command="purge",status="ok"} 1' in out
        assert 'asiai_fleet_latency_ms_total{command="purge"} 42' in out

    def test_denied_records_token_and_error(self):
        fleet_metrics.record(
            command=None, status="denied", error="rate_limited", token_id="tok_abc"
        )
        out = fleet_metrics.format_fleet_metrics()
        assert 'asiai_fleet_denied_total{token_id="tok_abc",error="rate_limited"} 1' in out

    def test_anonymous_denials_grouped(self):
        # No token_id (missing bearer) → bucket under "<anon>".
        fleet_metrics.record(command=None, status="denied", error="missing_bearer")
        out = fleet_metrics.format_fleet_metrics()
        assert 'asiai_fleet_denied_total{token_id="<anon>",error="missing_bearer"} 1' in out

    def test_increments_aggregate_across_calls(self):
        for _ in range(5):
            fleet_metrics.record(command="restart", status="ok", duration_ms=100)
        out = fleet_metrics.format_fleet_metrics()
        assert 'asiai_fleet_command_total{command="restart",status="ok"} 5' in out
        assert 'asiai_fleet_latency_ms_total{command="restart"} 500' in out

    def test_label_injection_escaped(self):
        # A nasty command with embedded quote and newline must not split
        # the line or break the Prometheus label syntax.
        fleet_metrics.record(command='evil"\ncmd', status="error", error="bad")
        out = fleet_metrics.format_fleet_metrics()
        sample_line = next(
            line for line in out.splitlines() if line.startswith("asiai_fleet_command_total{")
        )
        # No raw newline mid-line (would otherwise emit a second metric).
        assert "\n" not in sample_line
        # Embedded quote must be backslash-escaped, not bare.
        assert '\\"' in sample_line
        # The line still ends with the counter integer.
        assert sample_line.rsplit(" ", 1)[1].isdigit()


class TestInflightGauge:
    def test_inc_dec_pair(self):
        fleet_metrics.aisctl_inflight_inc()
        fleet_metrics.aisctl_inflight_inc()
        out = fleet_metrics.format_fleet_metrics()
        assert "asiai_aisctl_inflight 2" in out
        fleet_metrics.aisctl_inflight_dec()
        out = fleet_metrics.format_fleet_metrics()
        assert "asiai_aisctl_inflight 1" in out

    def test_dec_never_goes_negative(self):
        fleet_metrics.aisctl_inflight_dec()
        fleet_metrics.aisctl_inflight_dec()
        out = fleet_metrics.format_fleet_metrics()
        assert "asiai_aisctl_inflight 0" in out


class TestFormat:
    def test_empty_state_renders(self):
        out = fleet_metrics.format_fleet_metrics()
        # Header lines must be present even when no events were recorded.
        assert "# TYPE asiai_fleet_command_total counter" in out
        assert "asiai_aisctl_inflight 0" in out

    def test_help_lines_first(self):
        fleet_metrics.record(command="purge", status="ok", duration_ms=10)
        out = fleet_metrics.format_fleet_metrics()
        # Every metric must have its HELP/TYPE preamble before any sample.
        lines = out.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("asiai_fleet_command_total"):
                assert any("# TYPE asiai_fleet_command_total counter" == p for p in lines[:i])
                break
