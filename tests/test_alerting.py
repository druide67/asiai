"""Tests for the alerting module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from asiai.alerting import (
    _evaluate_conditions,
    _parse_engines,
    _send_webhook,
    _should_fire,
    check_and_alert,
)
from asiai.storage.db import init_db, query_alert_history, store_alert


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def db(tmp_path):
    """Create a temporary database."""
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def _snap(
    mem_pressure="normal",
    thermal_level="nominal",
    inference_engine="ollama",
    **kw,
):
    """Build a minimal snapshot dict."""
    return {
        "ts": kw.get("ts", 1700000000),
        "cpu_load_1": 1.0,
        "cpu_load_5": 1.0,
        "cpu_load_15": 1.0,
        "mem_total": 68719476736,
        "mem_used": 40000000000,
        "mem_pressure": mem_pressure,
        "thermal_level": thermal_level,
        "thermal_speed_limit": 100,
        "uptime": 86400,
        "inference_engine": inference_engine,
        "engine_version": "",
        "models": [],
        **kw,
    }


# ---------------------------------------------------------------------------
# _parse_engines
# ---------------------------------------------------------------------------
class TestParseEngines:
    def test_none_string(self):
        assert _parse_engines("none") == []

    def test_empty_string(self):
        assert _parse_engines("") == []

    def test_single(self):
        assert _parse_engines("ollama") == ["ollama"]

    def test_multiple(self):
        assert _parse_engines("ollama,lmstudio") == ["ollama", "lmstudio"]

    def test_whitespace(self):
        assert _parse_engines("ollama , lmstudio") == ["ollama", "lmstudio"]


# ---------------------------------------------------------------------------
# _evaluate_conditions
# ---------------------------------------------------------------------------
class TestEvaluateConditions:
    def test_no_change(self):
        prev = _snap()
        cur = _snap()
        assert _evaluate_conditions(cur, prev) == []

    def test_mem_pressure_normal_to_warn(self):
        prev = _snap(mem_pressure="normal")
        cur = _snap(mem_pressure="warn")
        alerts = _evaluate_conditions(cur, prev)
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "mem_pressure_warn"
        assert alerts[0]["severity"] == "warning"
        assert "normal" in alerts[0]["message"]
        assert "warn" in alerts[0]["message"]

    def test_mem_pressure_normal_to_critical(self):
        prev = _snap(mem_pressure="normal")
        cur = _snap(mem_pressure="critical")
        alerts = _evaluate_conditions(cur, prev)
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "mem_pressure_critical"
        assert alerts[0]["severity"] == "critical"

    def test_mem_pressure_warn_to_normal_no_alert(self):
        """Recovery should not trigger an alert."""
        prev = _snap(mem_pressure="warn")
        cur = _snap(mem_pressure="normal")
        assert _evaluate_conditions(cur, prev) == []

    def test_mem_pressure_same_no_alert(self):
        prev = _snap(mem_pressure="warn")
        cur = _snap(mem_pressure="warn")
        assert _evaluate_conditions(cur, prev) == []

    def test_thermal_nominal_to_fair(self):
        prev = _snap(thermal_level="nominal")
        cur = _snap(thermal_level="fair")
        alerts = _evaluate_conditions(cur, prev)
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "thermal_degraded"
        assert alerts[0]["severity"] == "warning"

    def test_thermal_nominal_to_critical(self):
        prev = _snap(thermal_level="nominal")
        cur = _snap(thermal_level="critical")
        alerts = _evaluate_conditions(cur, prev)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "critical"

    def test_thermal_recovery_no_alert(self):
        prev = _snap(thermal_level="fair")
        cur = _snap(thermal_level="nominal")
        assert _evaluate_conditions(cur, prev) == []

    def test_engine_down(self):
        prev = _snap(inference_engine="ollama,lmstudio")
        cur = _snap(inference_engine="ollama")
        alerts = _evaluate_conditions(cur, prev)
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "engine_down"
        assert alerts[0]["severity"] == "critical"
        assert "lmstudio" in alerts[0]["message"]

    def test_engine_down_multiple(self):
        prev = _snap(inference_engine="ollama,lmstudio,mlx-lm")
        cur = _snap(inference_engine="none")
        alerts = _evaluate_conditions(cur, prev)
        engine_alerts = [a for a in alerts if a["alert_type"] == "engine_down"]
        assert len(engine_alerts) == 3

    def test_engine_up_no_alert(self):
        """New engine appearing should not alert."""
        prev = _snap(inference_engine="ollama")
        cur = _snap(inference_engine="ollama,lmstudio")
        assert _evaluate_conditions(cur, prev) == []

    def test_combined_alerts(self):
        prev = _snap(mem_pressure="normal", thermal_level="nominal", inference_engine="ollama")
        cur = _snap(mem_pressure="warn", thermal_level="fair", inference_engine="none")
        alerts = _evaluate_conditions(cur, prev)
        types = {a["alert_type"] for a in alerts}
        assert "mem_pressure_warn" in types
        assert "thermal_degraded" in types
        assert "engine_down" in types

    def test_details_contain_mem_info(self):
        prev = _snap(mem_pressure="normal")
        cur = _snap(mem_pressure="warn")
        alerts = _evaluate_conditions(cur, prev)
        details = alerts[0]["details"]
        assert "mem_used" in details
        assert "mem_total" in details

    def test_details_contain_thermal_info(self):
        prev = _snap(thermal_level="nominal")
        cur = _snap(thermal_level="serious")
        alerts = _evaluate_conditions(cur, prev)
        details = alerts[0]["details"]
        assert "thermal_level" in details
        assert "thermal_speed_limit" in details


# ---------------------------------------------------------------------------
# _should_fire (cooldown)
# ---------------------------------------------------------------------------
class TestShouldFire:
    def test_no_recent_alerts(self, db):
        assert _should_fire("mem_pressure_warn", db) is True

    def test_recent_alert_blocks(self, db):
        store_alert(db, {
            "ts": int(__import__("time").time()),
            "alert_type": "mem_pressure_warn",
            "severity": "warning",
            "message": "test",
            "details": "{}",
            "webhook_sent": True,
        })
        assert _should_fire("mem_pressure_warn", db) is False

    def test_different_type_not_blocked(self, db):
        store_alert(db, {
            "ts": int(__import__("time").time()),
            "alert_type": "thermal_degraded",
            "severity": "warning",
            "message": "test",
            "details": "{}",
            "webhook_sent": True,
        })
        assert _should_fire("mem_pressure_warn", db) is True

    def test_old_alert_allows_fire(self, db):
        store_alert(db, {
            "ts": int(__import__("time").time()) - 600,
            "alert_type": "mem_pressure_warn",
            "severity": "warning",
            "message": "test",
            "details": "{}",
            "webhook_sent": True,
        })
        assert _should_fire("mem_pressure_warn", db, cooldown=300) is True


# ---------------------------------------------------------------------------
# _send_webhook
# ---------------------------------------------------------------------------
class TestSendWebhook:
    def test_success(self):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("asiai.alerting.urllib.request.urlopen", return_value=mock_resp):
            assert _send_webhook("https://example.com/hook", {"test": 1}) is True

    def test_http_error(self):
        from urllib.error import HTTPError

        with patch(
            "asiai.alerting.urllib.request.urlopen",
            side_effect=HTTPError("url", 500, "err", {}, None),
        ):
            assert _send_webhook("https://example.com/hook", {"test": 1}) is False

    def test_connection_error(self):
        from urllib.error import URLError

        with patch(
            "asiai.alerting.urllib.request.urlopen",
            side_effect=URLError("connection refused"),
        ):
            assert _send_webhook("https://example.com/hook", {"test": 1}) is False

    def test_invalid_url(self):
        assert _send_webhook("not-a-url", {"test": 1}) is False


# ---------------------------------------------------------------------------
# check_and_alert (integration)
# ---------------------------------------------------------------------------
class TestCheckAndAlert:
    def test_no_prev_snapshot_returns_empty(self, db):
        snap = _snap(mem_pressure="critical")
        result = check_and_alert(snap, None, "https://example.com/hook", db)
        assert result == []

    def test_no_transition_returns_empty(self, db):
        prev = _snap()
        cur = _snap()
        with patch("asiai.alerting._send_webhook", return_value=True):
            result = check_and_alert(cur, prev, "https://example.com/hook", db)
        assert result == []

    def test_fires_on_transition(self, db):
        prev = _snap(mem_pressure="normal")
        cur = _snap(mem_pressure="warn")
        with patch("asiai.alerting._send_webhook", return_value=True) as mock_send:
            result = check_and_alert(cur, prev, "https://example.com/hook", db)
        assert len(result) == 1
        assert result[0]["alert"] == "mem_pressure_warn"
        mock_send.assert_called_once()
        payload = mock_send.call_args[0][1]
        assert payload["host"]
        assert payload["source"].startswith("asiai/")

    def test_stores_alert_in_db(self, db):
        prev = _snap(mem_pressure="normal")
        cur = _snap(mem_pressure="warn")
        with patch("asiai.alerting._send_webhook", return_value=True):
            check_and_alert(cur, prev, "https://example.com/hook", db)
        alerts = query_alert_history(db, hours=1)
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "mem_pressure_warn"

    def test_cooldown_prevents_second_fire(self, db):
        prev = _snap(mem_pressure="normal")
        cur = _snap(mem_pressure="warn")
        with patch("asiai.alerting._send_webhook", return_value=True):
            check_and_alert(cur, prev, "https://example.com/hook", db)
            result = check_and_alert(cur, prev, "https://example.com/hook", db)
        assert result == []

    def test_webhook_failure_still_stores(self, db):
        prev = _snap(mem_pressure="normal")
        cur = _snap(mem_pressure="warn")
        with patch("asiai.alerting._send_webhook", return_value=False):
            check_and_alert(cur, prev, "https://example.com/hook", db)
        alerts = query_alert_history(db, hours=1)
        assert len(alerts) == 1
        assert alerts[0]["webhook_sent"] == 0
