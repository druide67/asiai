"""Tests for the 'asiai config' CLI subcommand."""

from __future__ import annotations

import os

from asiai.cli import main
from asiai.engines.config import load_config, upsert_engine


class TestCliConfigShow:
    def test_show_empty(self, capsys, tmp_path, monkeypatch):
        config_dir = str(tmp_path / "asiai")
        monkeypatch.setattr("asiai.engines.config.CONFIG_DIR", config_dir)
        config_path = os.path.join(config_dir, "engines.json")
        monkeypatch.setattr("asiai.engines.config.CONFIG_PATH", config_path)

        ret = main(["config", "show"])
        assert ret == 0
        assert "No engines" in capsys.readouterr().out

    def test_show_with_engines(self, capsys, tmp_path, monkeypatch):
        config_dir = str(tmp_path / "asiai")
        config_path = os.path.join(config_dir, "engines.json")
        monkeypatch.setattr("asiai.engines.config.CONFIG_DIR", config_dir)
        monkeypatch.setattr("asiai.engines.config.CONFIG_PATH", config_path)

        upsert_engine("http://localhost:11434", "ollama", "0.17")
        ret = main(["config", "show"])
        assert ret == 0
        out = capsys.readouterr().out
        assert "ollama" in out
        assert "11434" in out


class TestCliConfigAdd:
    def test_add_engine(self, capsys, tmp_path, monkeypatch):
        config_dir = str(tmp_path / "asiai")
        config_path = os.path.join(config_dir, "engines.json")
        monkeypatch.setattr("asiai.engines.config.CONFIG_DIR", config_dir)
        monkeypatch.setattr("asiai.engines.config.CONFIG_PATH", config_path)

        ret = main(["config", "add", "omlx", "http://localhost:8800", "--label", "mac-mini"])
        assert ret == 0
        assert "Added" in capsys.readouterr().out

        config = load_config()
        assert len(config["engines"]) == 1
        assert config["engines"][0]["source"] == "manual"
        assert config["engines"][0]["label"] == "mac-mini"


class TestCliConfigRemove:
    def test_remove_existing(self, capsys, tmp_path, monkeypatch):
        config_dir = str(tmp_path / "asiai")
        config_path = os.path.join(config_dir, "engines.json")
        monkeypatch.setattr("asiai.engines.config.CONFIG_DIR", config_dir)
        monkeypatch.setattr("asiai.engines.config.CONFIG_PATH", config_path)

        upsert_engine("http://localhost:11434", "ollama", "0.17")
        ret = main(["config", "remove", "http://localhost:11434"])
        assert ret == 0
        assert "Removed" in capsys.readouterr().out
        assert len(load_config()["engines"]) == 0

    def test_remove_nonexistent(self, capsys, tmp_path, monkeypatch):
        config_dir = str(tmp_path / "asiai")
        config_path = os.path.join(config_dir, "engines.json")
        monkeypatch.setattr("asiai.engines.config.CONFIG_DIR", config_dir)
        monkeypatch.setattr("asiai.engines.config.CONFIG_PATH", config_path)

        ret = main(["config", "remove", "http://localhost:99999"])
        assert ret == 0
        assert "No engine" in capsys.readouterr().out


class TestCliConfigReset:
    def test_reset(self, capsys, tmp_path, monkeypatch):
        config_dir = str(tmp_path / "asiai")
        config_path = os.path.join(config_dir, "engines.json")
        monkeypatch.setattr("asiai.engines.config.CONFIG_DIR", config_dir)
        monkeypatch.setattr("asiai.engines.config.CONFIG_PATH", config_path)

        upsert_engine("http://localhost:11434", "ollama", "0.17")
        ret = main(["config", "reset"])
        assert ret == 0
        assert "reset" in capsys.readouterr().out.lower()
        assert len(load_config()["engines"]) == 0
