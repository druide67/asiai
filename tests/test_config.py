"""Tests for persistent engine configuration."""

from __future__ import annotations

import json
import os
import time

import pytest

from asiai.engines.config import (
    STALE_THRESHOLD_SECONDS,
    get_known_urls,
    load_config,
    prune_stale,
    remove_engine,
    reset_config,
    save_config,
    upsert_engine,
)


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    """Redirect config to a temp directory for every test."""
    config_dir = str(tmp_path / "asiai")
    config_path = os.path.join(config_dir, "engines.json")
    monkeypatch.setattr("asiai.engines.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("asiai.engines.config.CONFIG_PATH", config_path)


class TestLoadConfig:
    def test_returns_empty_when_no_file(self):
        config = load_config()
        assert config == {"version": 1, "engines": []}

    def test_loads_valid_config(self, tmp_path, monkeypatch):
        config_dir = str(tmp_path / "asiai")
        os.makedirs(config_dir, exist_ok=True)
        path = os.path.join(config_dir, "engines.json")
        monkeypatch.setattr("asiai.engines.config.CONFIG_PATH", path)

        data = {
            "version": 1,
            "engines": [
                {
                    "url": "http://localhost:11434",
                    "engine": "ollama",
                    "version": "0.17.7",
                    "last_seen": 1000,
                    "source": "auto",
                    "label": "",
                }
            ],
        }
        with open(path, "w") as f:
            json.dump(data, f)

        config = load_config()
        assert len(config["engines"]) == 1
        assert config["engines"][0]["engine"] == "ollama"

    def test_returns_empty_on_corrupt_json(self, tmp_path, monkeypatch):
        config_dir = str(tmp_path / "asiai")
        os.makedirs(config_dir, exist_ok=True)
        path = os.path.join(config_dir, "engines.json")
        monkeypatch.setattr("asiai.engines.config.CONFIG_PATH", path)

        with open(path, "w") as f:
            f.write("{not valid json")

        config = load_config()
        assert config == {"version": 1, "engines": []}

    def test_returns_empty_on_missing_engines_key(self, tmp_path, monkeypatch):
        config_dir = str(tmp_path / "asiai")
        os.makedirs(config_dir, exist_ok=True)
        path = os.path.join(config_dir, "engines.json")
        monkeypatch.setattr("asiai.engines.config.CONFIG_PATH", path)

        with open(path, "w") as f:
            json.dump({"version": 1}, f)

        config = load_config()
        assert config == {"version": 1, "engines": []}


class TestSaveConfig:
    def test_creates_directory_and_file(self):
        config = {"version": 1, "engines": []}
        assert save_config(config) is True
        loaded = load_config()
        assert loaded == config

    def test_atomic_write(self):
        """Config file should be valid even if read during write."""
        config = {
            "version": 1,
            "engines": [
                {
                    "url": "http://localhost:11434",
                    "engine": "ollama",
                    "version": "0.17",
                    "last_seen": 1000,
                    "source": "auto",
                    "label": "",
                }
            ],
        }
        save_config(config)
        loaded = load_config()
        assert loaded["engines"][0]["engine"] == "ollama"


class TestUpsertEngine:
    def test_adds_new_engine(self):
        upsert_engine("http://localhost:11434", "ollama", "0.17.7")
        config = load_config()
        assert len(config["engines"]) == 1
        assert config["engines"][0]["url"] == "http://localhost:11434"
        assert config["engines"][0]["engine"] == "ollama"
        assert config["engines"][0]["source"] == "auto"

    def test_updates_existing_engine(self):
        upsert_engine("http://localhost:11434", "ollama", "0.17.7")
        upsert_engine("http://localhost:11434", "ollama", "0.18.0")
        config = load_config()
        assert len(config["engines"]) == 1
        assert config["engines"][0]["version"] == "0.18.0"

    def test_does_not_downgrade_manual_to_auto(self):
        upsert_engine("http://localhost:11434", "ollama", "0.17.7", source="manual")
        upsert_engine("http://localhost:11434", "ollama", "0.18.0", source="auto")
        config = load_config()
        assert config["engines"][0]["source"] == "manual"

    def test_upgrades_auto_to_manual(self):
        upsert_engine("http://localhost:11434", "ollama", "0.17.7", source="auto")
        upsert_engine("http://localhost:11434", "ollama", "0.18.0", source="manual")
        config = load_config()
        assert config["engines"][0]["source"] == "manual"

    def test_updates_label_when_provided(self):
        upsert_engine("http://localhost:8800", "omlx", "0.9", label="mac-mini")
        config = load_config()
        assert config["engines"][0]["label"] == "mac-mini"

    def test_multiple_engines(self):
        upsert_engine("http://localhost:11434", "ollama", "0.17")
        upsert_engine("http://localhost:1234", "lmstudio", "0.3")
        upsert_engine("http://localhost:8800", "omlx", "0.9")
        config = load_config()
        assert len(config["engines"]) == 3


class TestRemoveEngine:
    def test_removes_existing(self):
        upsert_engine("http://localhost:11434", "ollama", "0.17")
        assert remove_engine("http://localhost:11434") is True
        config = load_config()
        assert len(config["engines"]) == 0

    def test_returns_false_for_missing(self):
        assert remove_engine("http://localhost:99999") is False


class TestGetKnownUrls:
    def test_sorted_by_last_seen(self):
        upsert_engine("http://localhost:11434", "ollama", "0.17")
        # Force an older timestamp
        config = load_config()
        config["engines"][0]["last_seen"] = 1000
        save_config(config)

        upsert_engine("http://localhost:1234", "lmstudio", "0.3")

        urls = get_known_urls()
        assert urls[0] == "http://localhost:1234"  # most recent
        assert urls[1] == "http://localhost:11434"

    def test_empty_when_no_config(self):
        assert get_known_urls() == []


class TestPruneStale:
    def test_prunes_old_auto_entries(self):
        upsert_engine("http://localhost:11434", "ollama", "0.17")
        config = load_config()
        config["engines"][0]["last_seen"] = int(time.time()) - STALE_THRESHOLD_SECONDS - 100
        save_config(config)

        pruned = prune_stale()
        assert pruned == 1
        assert len(load_config()["engines"]) == 0

    def test_keeps_manual_entries(self):
        upsert_engine("http://localhost:11434", "ollama", "0.17", source="manual")
        config = load_config()
        config["engines"][0]["last_seen"] = int(time.time()) - STALE_THRESHOLD_SECONDS - 100
        save_config(config)

        pruned = prune_stale()
        assert pruned == 0
        assert len(load_config()["engines"]) == 1

    def test_keeps_recent_auto_entries(self):
        upsert_engine("http://localhost:11434", "ollama", "0.17")
        pruned = prune_stale()
        assert pruned == 0
        assert len(load_config()["engines"]) == 1


class TestResetConfig:
    def test_deletes_config_file(self):
        upsert_engine("http://localhost:11434", "ollama", "0.17")
        assert reset_config() is True
        assert load_config() == {"version": 1, "engines": []}

    def test_returns_false_when_no_file(self):
        assert reset_config() is False
