"""Alerting — transition-based webhook notifications."""

from __future__ import annotations

import json
import logging
import platform
import time
import urllib.error
import urllib.request

from asiai.storage.db import query_recent_alerts, store_alert

logger = logging.getLogger("asiai.alerting")

# Default cooldown: 5 minutes between same alert type.
DEFAULT_COOLDOWN = 300


def check_and_alert(
    snapshot: dict,
    prev_snapshot: dict | None,
    webhook_url: str,
    db_path: str,
    cooldown: int = DEFAULT_COOLDOWN,
) -> list[dict]:
    """Evaluate alert conditions and fire webhooks for state transitions.

    Args:
        snapshot: Current system snapshot dict.
        prev_snapshot: Previous snapshot (None on first tick — no alerts fired).
        webhook_url: URL to POST alerts to.
        db_path: SQLite database path for cooldown tracking.
        cooldown: Seconds between re-alerts of the same type.

    Returns:
        List of alerts that were fired.
    """
    if prev_snapshot is None:
        return []

    alerts = _evaluate_conditions(snapshot, prev_snapshot)
    fired = []

    for alert in alerts:
        if not _should_fire(alert["alert_type"], db_path, cooldown):
            logger.debug("Alert %s suppressed (cooldown)", alert["alert_type"])
            continue

        ts = int(time.time())
        payload = {
            "alert": alert["alert_type"],
            "severity": alert["severity"],
            "ts": ts,
            "host": platform.node(),
            "message": alert["message"],
            "details": alert["details"],
            "source": _get_source_version(),
        }

        sent = _send_webhook(webhook_url, payload)

        record = {
            "ts": ts,
            "alert_type": alert["alert_type"],
            "severity": alert["severity"],
            "message": alert["message"],
            "details": json.dumps(alert["details"]),
            "webhook_sent": sent,
            "webhook_status": alert.get("_http_status"),
        }
        store_alert(db_path, record)
        fired.append(payload)

    return fired


def _evaluate_conditions(snap: dict, prev: dict) -> list[dict]:
    """Detect state transitions and return triggered alerts."""
    alerts: list[dict] = []

    # 1. Memory pressure: normal → warn or critical
    mem_cur = snap.get("mem_pressure", "normal")
    mem_prev = prev.get("mem_pressure", "normal")
    if mem_cur != mem_prev and mem_cur in ("warn", "critical"):
        severity = "critical" if mem_cur == "critical" else "warning"
        alerts.append(
            {
                "alert_type": f"mem_pressure_{mem_cur}",
                "severity": severity,
                "message": f"Memory pressure changed: {mem_prev} \u2192 {mem_cur}",
                "details": {
                    "mem_pressure": mem_cur,
                    "mem_used": snap.get("mem_used", 0),
                    "mem_total": snap.get("mem_total", 0),
                },
            }
        )

    # 2. Thermal level: nominal → degraded
    therm_cur = snap.get("thermal_level", "nominal")
    therm_prev = prev.get("thermal_level", "nominal")
    if therm_cur != therm_prev and therm_cur in ("fair", "serious", "critical"):
        severity = "critical" if therm_cur == "critical" else "warning"
        alerts.append(
            {
                "alert_type": "thermal_degraded",
                "severity": severity,
                "message": f"Thermal level changed: {therm_prev} \u2192 {therm_cur}",
                "details": {
                    "thermal_level": therm_cur,
                    "thermal_speed_limit": snap.get("thermal_speed_limit", -1),
                },
            }
        )

    # 3. Engine down: was listed in inference_engine, now missing
    prev_engines = set(_parse_engines(prev.get("inference_engine", "none")))
    cur_engines = set(_parse_engines(snap.get("inference_engine", "none")))
    gone = prev_engines - cur_engines
    for engine_name in sorted(gone):
        alerts.append(
            {
                "alert_type": "engine_down",
                "severity": "critical",
                "message": f"Engine down: {engine_name}",
                "details": {"engine": engine_name},
            }
        )

    return alerts


def _parse_engines(engine_str: str) -> list[str]:
    """Parse comma-separated engine string, filtering out 'none'."""
    if not engine_str or engine_str == "none":
        return []
    return [e.strip() for e in engine_str.split(",") if e.strip()]


def _should_fire(alert_type: str, db_path: str, cooldown: int = DEFAULT_COOLDOWN) -> bool:
    """Check if alert should fire (no recent alert of same type within cooldown)."""
    recent = query_recent_alerts(db_path, alert_type, seconds=cooldown)
    return len(recent) == 0


def _send_webhook(url: str, payload: dict, timeout: int = 10) -> bool:
    """POST JSON payload to webhook URL. Fire-and-forget.

    Returns True if HTTP 2xx, False otherwise.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        logger.warning("Webhook URL must use http(s), ignoring: %s", url)
        return False

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        logger.warning("Webhook HTTP error %d: %s", e.code, url)
        return False
    except (urllib.error.URLError, OSError, ValueError) as e:
        logger.warning("Webhook error: %s (%s)", e, url)
        return False


def _get_source_version() -> str:
    """Return source identifier for webhook payloads."""
    try:
        from asiai import __version__

        return f"asiai/{__version__}"
    except ImportError:
        return "asiai"
