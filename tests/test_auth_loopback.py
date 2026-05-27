"""Unit tests for asiai.auth.loopback."""

from __future__ import annotations

import os

import pytest

from asiai.auth import loopback


@pytest.fixture
def tmp_loopback(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    token_path = state_dir / "aisctl-serve-token"
    monkeypatch.setattr(loopback, "STATE_DIR", str(state_dir))
    monkeypatch.setattr(loopback, "TOKEN_PATH", str(token_path))
    yield token_path


class TestWriteToken:
    def test_writes_and_returns_token(self, tmp_loopback):
        tok = loopback.write_token()
        assert tok.startswith(loopback.INTERNAL_TOKEN_PREFIX)
        with open(tmp_loopback) as f:
            assert f.read() == tok

    def test_perms_0600(self, tmp_loopback):
        loopback.write_token()
        mode = os.stat(tmp_loopback).st_mode & 0o777
        assert mode == 0o600

    def test_rotates_on_each_call(self, tmp_loopback):
        t1 = loopback.write_token()
        t2 = loopback.write_token()
        assert t1 != t2

    def test_refuses_symlink(self, tmp_loopback, tmp_path):
        elsewhere = tmp_path / "elsewhere.token"
        elsewhere.write_text("hijacked")
        tmp_loopback.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(str(elsewhere), str(tmp_loopback))
        with pytest.raises(OSError, match="symlink"):
            loopback.write_token()
        assert elsewhere.read_text() == "hijacked"


class TestReadToken:
    def test_returns_none_when_missing(self, tmp_loopback):
        assert loopback.read_token() is None

    def test_returns_token_when_present(self, tmp_loopback):
        tok = loopback.write_token()
        assert loopback.read_token() == tok

    def test_rejects_unexpected_prefix(self, tmp_loopback):
        tmp_loopback.parent.mkdir(parents=True, exist_ok=True)
        tmp_loopback.write_text("garbage_no_prefix")
        assert loopback.read_token() is None


class TestRemoveToken:
    def test_removes_existing(self, tmp_loopback):
        loopback.write_token()
        loopback.remove_token()
        assert not tmp_loopback.exists()

    def test_removes_silently_when_missing(self, tmp_loopback):
        # Should not raise.
        loopback.remove_token()
