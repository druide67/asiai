"""Tests for agent registration (community.py)."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

from asiai.community import (
    _load_agent_json,
    _save_agent_json,
    get_agent_info,
    register_agent,
    unregister_agent,
)


class TestAgentJsonStorage:
    def test_save_and_load(self, tmp_path):
        agent_json = str(tmp_path / "agent.json")
        data = {"agent_id": "abc123456789", "agent_token": "secret_tok"}

        with patch("asiai.community._AGENT_JSON", agent_json):
            _save_agent_json(data)
            loaded = _load_agent_json()
            assert loaded["agent_id"] == "abc123456789"
            assert loaded["agent_token"] == "secret_tok"

            # Verify permissions (chmod 600)
            mode = oct(os.stat(agent_json).st_mode)[-3:]
            assert mode == "600"

    def test_load_missing_file(self, tmp_path):
        agent_json = str(tmp_path / "nonexistent.json")
        with patch("asiai.community._AGENT_JSON", agent_json):
            assert _load_agent_json() == {}

    def test_load_corrupt_file(self, tmp_path):
        agent_json = str(tmp_path / "agent.json")
        with open(agent_json, "w") as f:
            f.write("not valid json{{{")
        with patch("asiai.community._AGENT_JSON", agent_json):
            assert _load_agent_json() == {}


class TestRegisterAgent:
    @patch("asiai.community.urlopen")
    def test_first_registration(self, mock_urlopen, tmp_path):
        agent_json = str(tmp_path / "agent.json")
        resp = MagicMock()
        resp.read.return_value = json.dumps(
            {
                "status": "registered",
                "agent_id": "a1b2c3d4e5f6",
                "agent_token": "secret_token_123",
                "total_agents": 42,
            }
        ).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        with patch("asiai.community._AGENT_JSON", agent_json):
            result = register_agent(
                chip="Apple M4 Pro",
                ram_gb=64,
                engines=["ollama", "lmstudio"],
            )
            assert result.success is True
            assert result.agent_id == "a1b2c3d4e5f6"
            assert result.total_agents == 42

            # Verify agent.json was created
            with open(agent_json) as f:
                saved = json.load(f)
            assert saved["agent_id"] == "a1b2c3d4e5f6"
            assert saved["agent_token"] == "secret_token_123"

    @patch("asiai.community.urlopen")
    def test_existing_registration_sends_heartbeat(self, mock_urlopen, tmp_path):
        """If agent.json exists, send heartbeat instead of re-registering."""
        agent_json = str(tmp_path / "agent.json")
        with open(agent_json, "w") as f:
            json.dump(
                {
                    "agent_id": "existing_id",
                    "agent_token": "existing_token",
                    "total_agents": 10,
                },
                f,
            )

        resp = MagicMock()
        resp.read.return_value = json.dumps({"status": "ok"}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        with patch("asiai.community._AGENT_JSON", agent_json):
            result = register_agent(chip="Apple M4 Pro", ram_gb=64)
            assert result.success is True
            assert result.agent_id == "existing_id"

            # Verify it called heartbeat endpoint (X-Agent-Id header)
            call_args = mock_urlopen.call_args[0][0]
            assert call_args.get_header("X-agent-id") == "existing_id"

    @patch("asiai.community.urlopen")
    def test_network_failure_returns_error(self, mock_urlopen, tmp_path):
        from urllib.error import URLError

        agent_json = str(tmp_path / "nonexistent.json")
        mock_urlopen.side_effect = URLError("connection refused")

        with patch("asiai.community._AGENT_JSON", agent_json):
            result = register_agent(chip="Apple M4 Pro", ram_gb=64)
            assert result.success is False
            assert "connection refused" in result.error

    @patch("asiai.community.urlopen")
    def test_heartbeat_403_removes_agent_json(self, mock_urlopen, tmp_path):
        """Invalid token should trigger removal of agent.json."""
        from urllib.error import HTTPError

        agent_json = str(tmp_path / "agent.json")
        with open(agent_json, "w") as f:
            json.dump({"agent_id": "old_id", "agent_token": "bad_token"}, f)

        mock_urlopen.side_effect = HTTPError(url="", code=403, msg="Forbidden", hdrs=None, fp=None)

        with patch("asiai.community._AGENT_JSON", agent_json):
            result = register_agent(chip="Apple M4 Pro", ram_gb=64)
            assert result.success is False
            assert not os.path.exists(agent_json)

    @patch("asiai.community.urlopen")
    def test_heartbeat_429_still_success(self, mock_urlopen, tmp_path):
        """Rate-limited heartbeat should still count as success."""
        from urllib.error import HTTPError

        agent_json = str(tmp_path / "agent.json")
        with open(agent_json, "w") as f:
            json.dump(
                {
                    "agent_id": "my_id",
                    "agent_token": "my_token",
                    "total_agents": 55,
                },
                f,
            )

        mock_urlopen.side_effect = HTTPError(
            url="", code=429, msg="Too Many Requests", hdrs=None, fp=None
        )

        with patch("asiai.community._AGENT_JSON", agent_json):
            result = register_agent(chip="Apple M4 Pro", ram_gb=64)
            assert result.success is True
            assert result.total_agents == 55


class TestUnregisterAgent:
    def test_unregister_removes_file(self, tmp_path):
        agent_json = str(tmp_path / "agent.json")
        with open(agent_json, "w") as f:
            json.dump({"agent_id": "test"}, f)

        with patch("asiai.community._AGENT_JSON", agent_json):
            assert unregister_agent() is True
            assert not os.path.exists(agent_json)

    def test_unregister_no_file(self, tmp_path):
        agent_json = str(tmp_path / "nonexistent.json")
        with patch("asiai.community._AGENT_JSON", agent_json):
            assert unregister_agent() is False


class TestGetAgentInfo:
    def test_returns_data(self, tmp_path):
        agent_json = str(tmp_path / "agent.json")
        with open(agent_json, "w") as f:
            json.dump({"agent_id": "test123", "total_agents": 7}, f)

        with patch("asiai.community._AGENT_JSON", agent_json):
            info = get_agent_info()
            assert info["agent_id"] == "test123"
            assert info["total_agents"] == 7

    def test_returns_empty_if_not_registered(self, tmp_path):
        agent_json = str(tmp_path / "nonexistent.json")
        with patch("asiai.community._AGENT_JSON", agent_json):
            assert get_agent_info() == {}
