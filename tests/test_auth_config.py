"""Unit tests for asiai.auth.config."""

from __future__ import annotations

import os

import pytest

from asiai.auth import config as auth_config


@pytest.fixture
def tmp_auth(tmp_path, monkeypatch):
    """Isolate auth.json + auth.lock to a tmp dir."""
    cfg_dir = tmp_path / "asiai"
    cfg_path = cfg_dir / "auth.json"
    lock_path = cfg_dir / "auth.lock"
    monkeypatch.setattr(auth_config, "CONFIG_DIR", str(cfg_dir))
    monkeypatch.setattr(auth_config, "CONFIG_PATH", str(cfg_path))
    monkeypatch.setattr(auth_config, "LOCK_PATH", str(lock_path))
    yield cfg_path


class TestInit:
    def test_init_creates_file_and_returns_token(self, tmp_auth):
        created, token_id, secret = auth_config.init_auth()
        assert created is True
        assert token_id is not None and token_id.startswith("tok_")
        assert secret is not None and secret.startswith(auth_config.TOKEN_PREFIX)
        assert tmp_auth.exists()

    def test_init_file_perms_0600(self, tmp_auth):
        auth_config.init_auth()
        mode = os.stat(tmp_auth).st_mode & 0o777
        assert mode == 0o600

    def test_init_idempotent_returns_false(self, tmp_auth):
        auth_config.init_auth()
        created, token_id, secret = auth_config.init_auth()
        assert created is False
        assert token_id is None
        assert secret is None

    def test_init_force_creates_additional_token(self, tmp_auth):
        c1, t1, _ = auth_config.init_auth()
        c2, t2, _ = auth_config.init_auth(force=True)
        assert c1 and c2
        assert t1 != t2
        assert len(auth_config.list_tokens()) == 2


class TestCreateToken:
    def test_each_secret_is_unique(self, tmp_auth):
        auth_config.init_auth()
        _, s1 = auth_config.create_token(label="A")
        _, s2 = auth_config.create_token(label="B")
        assert s1 != s2

    def test_label_validation(self, tmp_auth):
        auth_config.init_auth()
        with pytest.raises(ValueError):
            auth_config.create_token(label="bad/label\nwith newline")

    def test_label_empty_allowed(self, tmp_auth):
        auth_config.init_auth()
        tid, _ = auth_config.create_token(label="")
        assert tid.startswith("tok_")

    def test_max_tokens_cap(self, tmp_auth, monkeypatch):
        monkeypatch.setattr(auth_config, "MAX_TOKENS", 3)
        auth_config.create_token(label="a")
        auth_config.create_token(label="b")
        auth_config.create_token(label="c")
        with pytest.raises(ValueError, match="cap"):
            auth_config.create_token(label="d")


class TestVerifyToken:
    def test_valid_secret_returns_token_id(self, tmp_auth):
        _, tid, secret = auth_config.init_auth()
        assert auth_config.verify_token(secret) == tid

    def test_invalid_secret_returns_none(self, tmp_auth):
        auth_config.init_auth()
        assert auth_config.verify_token("asai_invalid_garbage") is None

    def test_wrong_prefix_returns_none(self, tmp_auth):
        auth_config.init_auth()
        assert auth_config.verify_token("bearer_xxx") is None

    def test_empty_secret_returns_none(self, tmp_auth):
        auth_config.init_auth()
        assert auth_config.verify_token("") is None

    def test_non_string_returns_none(self, tmp_auth):
        auth_config.init_auth()
        assert auth_config.verify_token(None) is None  # type: ignore[arg-type]
        assert auth_config.verify_token(123) is None  # type: ignore[arg-type]

    def test_revoked_token_returns_none(self, tmp_auth):
        _, tid, secret = auth_config.init_auth()
        auth_config.revoke_token(tid)
        assert auth_config.verify_token(secret) is None

    def test_verify_updates_last_used(self, tmp_auth):
        _, tid, secret = auth_config.init_auth()
        auth_config.verify_token(secret)
        tokens = auth_config.list_tokens()
        match = [t for t in tokens if t["id"] == tid][0]
        assert match["last_used_at"] is not None


class TestRevokeAndRotate:
    def test_revoke_marks_token(self, tmp_auth):
        _, tid, _ = auth_config.init_auth()
        assert auth_config.revoke_token(tid) is True
        tokens = auth_config.list_tokens()
        assert tokens[0]["revoked_at"] is not None

    def test_revoke_unknown_returns_false(self, tmp_auth):
        auth_config.init_auth()
        assert auth_config.revoke_token("tok_doesnotexist") is False

    def test_revoke_already_revoked_returns_false(self, tmp_auth):
        _, tid, _ = auth_config.init_auth()
        auth_config.revoke_token(tid)
        assert auth_config.revoke_token(tid) is False

    def test_rotate_returns_new_secret(self, tmp_auth):
        _, tid, old_secret = auth_config.init_auth()
        result = auth_config.rotate_token(tid)
        assert result is not None
        new_id, new_secret = result
        assert new_id != tid
        assert new_secret != old_secret
        # Old secret no longer verifies.
        assert auth_config.verify_token(old_secret) is None
        # New secret verifies to the new id.
        assert auth_config.verify_token(new_secret) == new_id

    def test_rotate_unknown_returns_none(self, tmp_auth):
        auth_config.init_auth()
        assert auth_config.rotate_token("tok_unknown") is None

    def test_rotate_preserves_label_by_default(self, tmp_auth):
        _, tid, _ = auth_config.init_auth()
        # Patch existing label to a known value.
        cfg = auth_config.load_auth()
        cfg["tokens"][0]["label"] = "studio"
        auth_config.save_auth(cfg)
        result = auth_config.rotate_token(tid)
        assert result is not None
        new_id, _ = result
        tokens = auth_config.list_tokens()
        new = [t for t in tokens if t["id"] == new_id][0]
        assert new["label"] == "studio"

    def test_rotate_with_explicit_label(self, tmp_auth):
        _, tid, _ = auth_config.init_auth()
        new_id, _ = auth_config.rotate_token(tid, label="new-label")  # type: ignore[misc]
        new = [t for t in auth_config.list_tokens() if t["id"] == new_id][0]
        assert new["label"] == "new-label"


class TestListTokens:
    def test_list_does_not_leak_hash(self, tmp_auth):
        auth_config.init_auth()
        tokens = auth_config.list_tokens()
        assert all("secret_hash" not in t for t in tokens)
        assert all("secret" not in t for t in tokens)

    def test_list_includes_metadata(self, tmp_auth):
        auth_config.init_auth()
        t = auth_config.list_tokens()[0]
        assert "id" in t
        assert "label" in t
        assert "created_at" in t
        assert "last_used_at" in t
        assert "revoked_at" in t


class TestSymlinkResistance:
    def test_refuses_to_write_through_symlink(self, tmp_auth, tmp_path):
        target = tmp_path / "elsewhere.json"
        target.write_text("{}")
        tmp_auth.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(str(target), str(tmp_auth))
        ok = auth_config.save_auth({"version": 1, "tokens": []})
        assert ok is False
        # Target file content untouched.
        assert target.read_text() == "{}"


class TestHashRoundtrip:
    def test_hash_then_verify_succeeds(self, tmp_auth):
        secret = "asai_test_secret_123"
        stored = auth_config._hash_secret(secret)
        assert stored.startswith("sha256$")
        assert auth_config._verify_hash(secret, stored) is True

    def test_verify_constant_time_against_different_secret(self, tmp_auth):
        stored = auth_config._hash_secret("asai_correct")
        assert auth_config._verify_hash("asai_wrong", stored) is False

    def test_verify_rejects_malformed_hash(self, tmp_auth):
        assert auth_config._verify_hash("anything", "not-a-valid-hash") is False
        assert auth_config._verify_hash("anything", "md5$abc$def") is False
