"""Persistent engine configuration for 3-layer auto-detection.

Stores discovered engines in ~/.config/asiai/engines.json so that
non-standard ports (e.g. oMLX on 8800) are remembered across runs.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time

logger = logging.getLogger("asiai.engines.config")

CONFIG_DIR = os.path.expanduser("~/.config/asiai")
CONFIG_PATH = os.path.join(CONFIG_DIR, "engines.json")

# Stale auto-discovered engines are pruned after 7 days.
STALE_THRESHOLD_SECONDS = 7 * 24 * 3600

_EMPTY_CONFIG: dict = {"version": 1, "engines": []}


def load_config() -> dict:
    """Load engine config from disk. Returns empty config on any failure."""
    try:
        with open(CONFIG_PATH) as f:
            data = json.load(f)
        if not isinstance(data, dict) or "engines" not in data:
            logger.warning("Invalid config format in %s", CONFIG_PATH)
            return {"version": 1, "engines": []}
        return data
    except FileNotFoundError:
        return {"version": 1, "engines": []}
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load config %s: %s", CONFIG_PATH, e)
        return {"version": 1, "engines": []}


def save_config(config: dict) -> bool:
    """Atomic write config to disk. Returns True on success."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=CONFIG_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(config, f, indent=2)
                f.write("\n")
            os.replace(tmp_path, CONFIG_PATH)
            return True
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except OSError as e:
        logger.error("Failed to save config: %s", e)
        return False


def get_known_urls() -> list[str]:
    """Return known engine URLs sorted by most recently seen first."""
    config = load_config()
    entries = sorted(config["engines"], key=lambda e: e.get("last_seen", 0), reverse=True)
    return [e["url"] for e in entries]


def upsert_engine(
    url: str,
    engine: str,
    version: str = "",
    source: str = "auto",
    label: str = "",
) -> None:
    """Add or update an engine entry. Updates last_seen timestamp."""
    config = load_config()
    now = int(time.time())

    for entry in config["engines"]:
        if entry["url"] == url:
            entry["engine"] = engine
            entry["version"] = version
            entry["last_seen"] = now
            # Don't downgrade manual to auto
            if source == "manual" or entry.get("source") != "manual":
                entry["source"] = source
            if label:
                entry["label"] = label
            save_config(config)
            return

    config["engines"].append(
        {
            "url": url,
            "engine": engine,
            "version": version,
            "last_seen": now,
            "source": source,
            "label": label,
        }
    )
    save_config(config)


def remove_engine(url: str) -> bool:
    """Remove an engine by URL. Returns True if found and removed."""
    config = load_config()
    before = len(config["engines"])
    config["engines"] = [e for e in config["engines"] if e["url"] != url]
    if len(config["engines"]) < before:
        save_config(config)
        return True
    return False


def prune_stale(threshold: int = STALE_THRESHOLD_SECONDS) -> int:
    """Remove auto-discovered engines not seen within threshold seconds.

    Returns number of entries pruned. Manual entries are never pruned.
    """
    config = load_config()
    now = int(time.time())
    cutoff = now - threshold

    before = len(config["engines"])
    config["engines"] = [
        e
        for e in config["engines"]
        if e.get("source") == "manual" or e.get("last_seen", 0) >= cutoff
    ]
    pruned = before - len(config["engines"])
    if pruned > 0:
        save_config(config)
        logger.info("Pruned %d stale engine(s)", pruned)
    return pruned


def reset_config() -> bool:
    """Delete the config file entirely. Returns True if removed."""
    try:
        os.unlink(CONFIG_PATH)
        return True
    except FileNotFoundError:
        return False
    except OSError as e:
        logger.error("Failed to reset config: %s", e)
        return False
