"""Unit tests for the fleet configuration module."""

from __future__ import annotations

import json
import stat

import pytest

from asiai.fleet import config as fleet_config


@pytest.fixture
def tmp_fleet(tmp_path, monkeypatch):
    """Isolate fleet.json to a temp directory for each test."""
    cfg_dir = tmp_path / "asiai"
    cfg_path = cfg_dir / "fleet.json"
    monkeypatch.setattr(fleet_config, "CONFIG_DIR", str(cfg_dir))
    monkeypatch.setattr(fleet_config, "CONFIG_PATH", str(cfg_path))
    yield cfg_path


class TestLoadFleet:
    def test_missing_file_returns_empty(self, tmp_fleet):
        cfg = fleet_config.load_fleet()
        assert cfg == {"version": 1, "nodes": []}

    def test_valid_file_returns_data(self, tmp_fleet):
        tmp_fleet.parent.mkdir(parents=True, exist_ok=True)
        tmp_fleet.write_text(json.dumps({"version": 1, "nodes": [{"nickname": "a"}]}))
        cfg = fleet_config.load_fleet()
        assert cfg["nodes"] == [{"nickname": "a"}]

    def test_malformed_json_returns_empty(self, tmp_fleet):
        tmp_fleet.parent.mkdir(parents=True, exist_ok=True)
        tmp_fleet.write_text("{not valid json")
        cfg = fleet_config.load_fleet()
        assert cfg == {"version": 1, "nodes": []}

    def test_missing_nodes_key_returns_empty(self, tmp_fleet):
        tmp_fleet.parent.mkdir(parents=True, exist_ok=True)
        tmp_fleet.write_text(json.dumps({"version": 1}))
        cfg = fleet_config.load_fleet()
        assert cfg == {"version": 1, "nodes": []}

    def test_nodes_not_a_list_returns_empty(self, tmp_fleet):
        tmp_fleet.parent.mkdir(parents=True, exist_ok=True)
        tmp_fleet.write_text(json.dumps({"version": 1, "nodes": "oops"}))
        cfg = fleet_config.load_fleet()
        assert cfg == {"version": 1, "nodes": []}


class TestSaveFleet:
    def test_creates_dir_and_file(self, tmp_fleet):
        ok = fleet_config.save_fleet({"version": 1, "nodes": []})
        assert ok is True
        assert tmp_fleet.exists()

    def test_file_perms_are_0o600(self, tmp_fleet):
        fleet_config.save_fleet({"version": 1, "nodes": []})
        mode = stat.S_IMODE(tmp_fleet.stat().st_mode)
        assert mode == 0o600, f"expected 0o600 perms, got {oct(mode)}"

    def test_atomic_write_no_tmp_leftover(self, tmp_fleet):
        fleet_config.save_fleet({"version": 1, "nodes": [{"nickname": "x"}]})
        leftovers = list(tmp_fleet.parent.glob("*.tmp"))
        assert leftovers == []


class TestUpsertNode:
    def test_add_new_node(self, tmp_fleet):
        entry = fleet_config.upsert_node("alpha", "http://192.0.2.1:8899", role="lab")
        assert entry["nickname"] == "alpha"
        assert entry["asiai_url"] == "http://192.0.2.1:8899"
        assert entry["role"] == "lab"
        assert entry["auth_token"] is None
        assert entry["last_seen"] is None

    def test_update_existing_node(self, tmp_fleet):
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899", role="lab")
        fleet_config.upsert_node("alpha", "http://192.0.2.99:8899", role="prod")
        nodes = fleet_config.get_nodes()
        assert len(nodes) == 1
        assert nodes[0]["asiai_url"] == "http://192.0.2.99:8899"
        assert nodes[0]["role"] == "prod"

    def test_strips_trailing_slash(self, tmp_fleet):
        entry = fleet_config.upsert_node("alpha", "http://192.0.2.1:8899/")
        assert entry["asiai_url"] == "http://192.0.2.1:8899"

    def test_empty_nickname_raises(self, tmp_fleet):
        with pytest.raises(ValueError, match="nickname"):
            fleet_config.upsert_node("", "http://192.0.2.1:8899")

    def test_empty_url_raises(self, tmp_fleet):
        with pytest.raises(ValueError, match="asiai_url"):
            fleet_config.upsert_node("alpha", "")

    def test_nickname_with_newline_rejected(self, tmp_fleet):
        with pytest.raises(ValueError, match="nickname"):
            fleet_config.upsert_node("evil\nname", "http://192.0.2.1:8899")

    def test_nickname_with_null_byte_rejected(self, tmp_fleet):
        with pytest.raises(ValueError, match="nickname"):
            fleet_config.upsert_node("evil\x00name", "http://192.0.2.1:8899")

    def test_nickname_with_slash_rejected(self, tmp_fleet):
        with pytest.raises(ValueError, match="nickname"):
            fleet_config.upsert_node("../etc/passwd", "http://192.0.2.1:8899")

    def test_nickname_too_long_rejected(self, tmp_fleet):
        with pytest.raises(ValueError, match="nickname"):
            fleet_config.upsert_node("a" * 65, "http://192.0.2.1:8899")

    def test_nickname_at_max_length_accepted(self, tmp_fleet):
        entry = fleet_config.upsert_node("a" * 64, "http://192.0.2.1:8899")
        assert entry["nickname"] == "a" * 64

    def test_file_scheme_url_rejected(self, tmp_fleet):
        with pytest.raises(ValueError, match="scheme"):
            fleet_config.upsert_node("alpha", "file:///etc/passwd")

    def test_ftp_scheme_url_rejected(self, tmp_fleet):
        with pytest.raises(ValueError, match="scheme"):
            fleet_config.upsert_node("alpha", "ftp://ftp.example.com/")

    def test_javascript_scheme_url_rejected(self, tmp_fleet):
        with pytest.raises(ValueError, match="scheme"):
            fleet_config.upsert_node("alpha", "javascript:alert(1)")

    def test_url_without_hostname_rejected(self, tmp_fleet):
        with pytest.raises(ValueError, match="hostname"):
            fleet_config.upsert_node("alpha", "http://")

    def test_https_url_accepted(self, tmp_fleet):
        entry = fleet_config.upsert_node("alpha", "https://node.example.com:8899")
        assert entry["asiai_url"].startswith("https://")

    def test_max_nodes_cap_enforced(self, tmp_fleet, monkeypatch):
        monkeypatch.setattr(fleet_config, "MAX_NODES", 3)
        for i in range(3):
            fleet_config.upsert_node(f"node{i}", f"http://192.0.2.{i + 1}:8899")
        with pytest.raises(ValueError, match="cap"):
            fleet_config.upsert_node("node3", "http://192.0.2.4:8899")

    def test_max_nodes_does_not_block_update(self, tmp_fleet, monkeypatch):
        monkeypatch.setattr(fleet_config, "MAX_NODES", 2)
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899")
        fleet_config.upsert_node("beta", "http://192.0.2.2:8899")
        # Updating an existing node must work even at the cap.
        fleet_config.upsert_node("alpha", "http://192.0.2.99:8899")
        assert fleet_config.find_node("alpha")["asiai_url"] == "http://192.0.2.99:8899"


class TestRemoveNode:
    def test_remove_existing_returns_true(self, tmp_fleet):
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899")
        assert fleet_config.remove_node("alpha") is True
        assert fleet_config.get_nodes() == []

    def test_remove_missing_returns_false(self, tmp_fleet):
        assert fleet_config.remove_node("nope") is False


class TestFindNode:
    def test_returns_entry_when_present(self, tmp_fleet):
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899")
        entry = fleet_config.find_node("alpha")
        assert entry is not None
        assert entry["nickname"] == "alpha"

    def test_returns_none_when_missing(self, tmp_fleet):
        assert fleet_config.find_node("nope") is None


class TestRedactNode:
    def test_non_dict_input_returns_empty(self):
        # A hand-edited fleet.json could contain non-dict entries.
        assert fleet_config.redact_node("string") == {}
        assert fleet_config.redact_node(42) == {}
        assert fleet_config.redact_node(None) == {}

    def test_removes_auth_token(self):
        node = {"nickname": "a", "asiai_url": "http://x", "auth_token": "SECRET"}
        out = fleet_config.redact_node(node)
        assert "auth_token" not in out
        assert out["nickname"] == "a"
        assert out["asiai_url"] == "http://x"

    def test_preserves_other_fields(self):
        node = {
            "nickname": "a",
            "asiai_url": "http://x",
            "role": "lab",
            "added_at": 123,
            "last_seen": 456,
            "last_status": "ok",
            "auth_token": "X",
        }
        out = fleet_config.redact_node(node)
        for k in ("nickname", "asiai_url", "role", "added_at", "last_seen", "last_status"):
            assert k in out
        assert "auth_token" not in out

    def test_does_not_mutate_input(self):
        node = {"nickname": "a", "auth_token": "S"}
        fleet_config.redact_node(node)
        assert node["auth_token"] == "S"


class TestTouchNodeStatus:
    def test_updates_last_seen_and_status_ok(self, tmp_fleet):
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899")
        fleet_config.touch_node_status("alpha", ok=True)
        node = fleet_config.find_node("alpha")
        assert node["last_status"] == "ok"
        assert node["last_seen"] is not None
        assert isinstance(node["last_seen"], int)

    def test_updates_last_status_error_with_reason(self, tmp_fleet):
        fleet_config.upsert_node("alpha", "http://192.0.2.1:8899")
        fleet_config.touch_node_status("alpha", ok=False, error="TimeoutError")
        node = fleet_config.find_node("alpha")
        assert node["last_status"] == "TimeoutError"

    def test_unknown_nickname_is_noop(self, tmp_fleet):
        fleet_config.touch_node_status("ghost", ok=True)
        assert fleet_config.find_node("ghost") is None
