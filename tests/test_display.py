"""Tests for display formatters."""

from __future__ import annotations

import os
from unittest.mock import patch

from asiai.display.formatters import (
    format_bytes,
    format_pressure,
    format_thermal,
    format_uptime,
)


class TestFormatBytes:
    def test_gb(self):
        assert format_bytes(68719476736) == "64.0 GB"

    def test_mb(self):
        assert format_bytes(104857600) == "100.0 MB"

    def test_kb(self):
        assert format_bytes(2048) == "2.0 KB"

    def test_bytes(self):
        assert format_bytes(512) == "512 B"

    def test_negative(self):
        assert format_bytes(-1) == "N/A"

    def test_zero(self):
        assert format_bytes(0) == "0 B"


class TestFormatUptime:
    def test_days_hours_minutes(self):
        assert format_uptime(90061) == "1d 1h 1m"

    def test_hours_minutes(self):
        assert format_uptime(3660) == "1h 1m"

    def test_minutes_only(self):
        assert format_uptime(300) == "5m"

    def test_zero(self):
        assert format_uptime(0) == "0m"

    def test_negative(self):
        assert format_uptime(-1) == "N/A"


class TestFormatPressure:
    def test_normal_has_text(self):
        # Without color (force NO_COLOR)
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            from asiai.display import formatters
            old = formatters._COLOR
            formatters._COLOR = False
            try:
                assert format_pressure("normal") == "normal"
                assert format_pressure("warn") == "warn"
                assert format_pressure("critical") == "critical"
                assert format_pressure("unknown") == "unknown"
            finally:
                formatters._COLOR = old


class TestFormatThermal:
    def test_levels(self):
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            from asiai.display import formatters
            old = formatters._COLOR
            formatters._COLOR = False
            try:
                assert format_thermal("nominal") == "nominal"
                assert format_thermal("fair") == "fair"
                assert format_thermal("serious") == "serious"
                assert format_thermal("critical") == "critical"
            finally:
                formatters._COLOR = old
