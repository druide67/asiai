"""Unit tests for the ``asiai fleet`` CLI handlers."""

from __future__ import annotations

import argparse
import json as _json
from unittest.mock import patch

import pytest

from asiai.fleet import cli as fleet_cli
from asiai.fleet import config as fleet_config
from asiai.fleet.poll import NodePoll


@pytest.fixture
def tmp_fleet(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "asiai"
    cfg_path = cfg_dir / "fleet.json"
    monkeypatch.setattr(fleet_config, "CONFIG_DIR", str(cfg_dir))
    monkeypatch.setattr(fleet_config, "CONFIG_PATH", str(cfg_path))
    yield cfg_path


def _args(**kwargs) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


class TestCmdAdd:
    def test_add_success(self, tmp_fleet, capsys):
        rc = fleet_cli.cmd_fleet(
            _args(action="add", nickname="alpha", url="http://192.0.2.1:8899", role="lab")
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "added" in out.lower()
        node = fleet_config.find_node("alpha")
        assert node is not None
        assert node["asiai_url"] == "http://192.0.2.1:8899"

    def test_add_empty_nickname_returns_1(self, tmp_fleet, capsys):
        rc = fleet_cli.cmd_fleet(
            _args(action="add", nickname="", url="http://192.0.2.1:8899", role="")
        )
        assert rc == 1


class TestCmdRemove:
    def test_remove_existing(self, tmp_fleet, capsys):
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899")
        rc = fleet_cli.cmd_fleet(_args(action="remove", nickname="alpha"))
        assert rc == 0
        assert fleet_config.find_node("alpha") is None

    def test_remove_missing_returns_1(self, tmp_fleet, capsys):
        rc = fleet_cli.cmd_fleet(_args(action="remove", nickname="ghost"))
        assert rc == 1


class TestCmdList:
    def test_list_empty(self, tmp_fleet, capsys):
        rc = fleet_cli.cmd_fleet(_args(action="list", json=False))
        assert rc == 0
        assert "No nodes" in capsys.readouterr().out

    def test_list_json_with_entries(self, tmp_fleet, capsys):
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899", role="lab")
        rc = fleet_cli.cmd_fleet(_args(action="list", json=True))
        assert rc == 0
        out = capsys.readouterr().out
        payload = _json.loads(out)
        assert payload["nodes"][0]["nickname"] == "alpha"

    def test_list_table_shows_nickname(self, tmp_fleet, capsys):
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899", role="lab")
        rc = fleet_cli.cmd_fleet(_args(action="list", json=False))
        assert rc == 0
        out = capsys.readouterr().out
        assert "alpha" in out
        assert "192.0.2.1" in out

    def test_list_json_does_not_leak_auth_token(self, tmp_fleet, capsys):
        # Phase 1 leaves auth_token at None, but a future Phase 2 token must
        # never surface in the CLI JSON output (terminals, CI logs, shell hist).
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899", auth_token="SHOULD_NOT_LEAK")
        rc = fleet_cli.cmd_fleet(_args(action="list", json=True))
        assert rc == 0
        out = capsys.readouterr().out
        assert "SHOULD_NOT_LEAK" not in out
        assert "auth_token" not in out


class TestCmdStatus:
    def test_status_no_nodes(self, tmp_fleet, capsys):
        rc = fleet_cli.cmd_fleet(_args(action="status", json=False, timeout=5.0))
        assert rc == 0

    def test_status_all_ok(self, tmp_fleet, capsys):
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899")

        def fake_poll_all(nodes, timeout=5.0, max_workers=16):
            return [
                NodePoll(
                    nickname="alpha",
                    url="http://192.0.2.1:8899",
                    ok=True,
                    latency_ms=42.0,
                    snapshot={
                        "engines_status": [
                            {"name": "ollama", "reachable": True, "models": [{"name": "llama3.2"}]}
                        ]
                    },
                    error=None,
                    reached_at=1700000000,
                )
            ]

        with patch.object(fleet_cli, "poll_all", side_effect=fake_poll_all):
            rc = fleet_cli.cmd_fleet(_args(action="status", json=False, timeout=5.0))
        assert rc == 0
        out = capsys.readouterr().out
        assert "alpha" in out
        assert "ok" in out

    def test_status_partial_failure_returns_1(self, tmp_fleet, capsys):
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899")
        fleet_config.upsert_node("beta", "http://192.0.2.2:8899")

        def fake_poll_all(nodes, timeout=5.0, max_workers=16):
            return [
                NodePoll(
                    nickname="alpha",
                    url="http://192.0.2.1:8899",
                    ok=True,
                    latency_ms=42.0,
                    snapshot={"engines_status": []},
                    error=None,
                    reached_at=1700000000,
                ),
                NodePoll(
                    nickname="beta",
                    url="http://192.0.2.2:8899",
                    ok=False,
                    latency_ms=0.0,
                    snapshot=None,
                    error="TimeoutError",
                    reached_at=1700000000,
                ),
            ]

        with patch.object(fleet_cli, "poll_all", side_effect=fake_poll_all):
            rc = fleet_cli.cmd_fleet(_args(action="status", json=False, timeout=5.0))
        # When at least one node is down, exit code is 1 to ease scripting.
        assert rc == 1
        out = capsys.readouterr().out
        assert "DOWN" in out

    def test_status_json_emits_polled_at_and_nodes(self, tmp_fleet, capsys):
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899")

        def fake_poll_all(nodes, timeout=5.0, max_workers=16):
            return [
                NodePoll(
                    nickname="alpha",
                    url="http://192.0.2.1:8899",
                    ok=True,
                    latency_ms=10.0,
                    snapshot={"engines_status": []},
                    error=None,
                    reached_at=1700000000,
                )
            ]

        with patch.object(fleet_cli, "poll_all", side_effect=fake_poll_all):
            rc = fleet_cli.cmd_fleet(_args(action="status", json=True, timeout=5.0))
        assert rc == 0
        payload = _json.loads(capsys.readouterr().out)
        assert "polled_at" in payload
        assert payload["nodes"][0]["nickname"] == "alpha"


class TestCmdPing:
    def test_ping_unknown_node(self, tmp_fleet, capsys):
        rc = fleet_cli.cmd_fleet(_args(action="ping", nickname="ghost", timeout=5.0))
        assert rc == 1

    def test_ping_ok(self, tmp_fleet, capsys):
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899")

        def fake_poll_one(nickname, url, timeout=5.0):
            return NodePoll(
                nickname=nickname,
                url=url,
                ok=True,
                latency_ms=15.0,
                snapshot={"engines_status": []},
                error=None,
                reached_at=1700000000,
            )

        with patch.object(fleet_cli, "poll_one", side_effect=fake_poll_one):
            rc = fleet_cli.cmd_fleet(_args(action="ping", nickname="alpha", timeout=5.0))
        assert rc == 0
        out = capsys.readouterr().out
        assert "reachable" in out


class TestDispatcher:
    def test_unknown_action_returns_1(self, tmp_fleet, capsys):
        rc = fleet_cli.cmd_fleet(_args(action="not-a-real-action"))
        assert rc == 1

    def test_no_action_prints_usage(self, tmp_fleet, capsys):
        rc = fleet_cli.cmd_fleet(_args(action=None))
        assert rc == 1
        err = capsys.readouterr().err
        assert "Usage" in err
