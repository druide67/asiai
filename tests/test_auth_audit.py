"""Unit tests for asiai.auth.audit."""

from __future__ import annotations

import json
import os

import pytest

from asiai.auth import audit


@pytest.fixture
def tmp_audit(tmp_path, monkeypatch):
    """Redirect the audit log to a tmp dir."""
    audit_dir = tmp_path / "audit"
    audit_path = audit_dir / "fleet-audit.jsonl"
    monkeypatch.setattr(audit, "AUDIT_DIR", str(audit_dir))
    monkeypatch.setattr(audit, "AUDIT_PATH", str(audit_path))
    yield audit_path


def _read_lines(path) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


class TestAuditWrite:
    def test_appends_jsonl(self, tmp_audit):
        audit.log_event(command="purge", status="ok")
        audit.log_event(command="stop", status="error", error="something")
        lines = _read_lines(tmp_audit)
        assert len(lines) == 2
        assert lines[0]["command"] == "purge"
        assert lines[1]["error"] == "something"

    def test_records_timestamp(self, tmp_audit):
        audit.log_event(command="purge", status="ok")
        line = _read_lines(tmp_audit)[0]
        assert "ts" in line
        assert isinstance(line["ts"], int)

    def test_perms_0600_on_first_create(self, tmp_audit):
        audit.log_event(command="purge", status="ok")
        mode = os.stat(tmp_audit).st_mode & 0o777
        assert mode == 0o600

    def test_never_raises_on_oserror(self, tmp_audit, monkeypatch):
        # Force open() to fail and ensure no exception bubbles up.
        def boom(*_args, **_kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("builtins.open", boom)
        # Should NOT raise.
        audit.log_event(command="purge", status="ok")

    def test_handles_non_serializable_values(self, tmp_audit):
        class Weird:
            def __str__(self):
                return "weird"

        audit.log_event(command="purge", status="ok", obj=Weird())
        line = _read_lines(tmp_audit)[0]
        assert line["obj"] == "weird"


class TestRotation:
    def test_rotates_when_over_threshold(self, tmp_audit, monkeypatch):
        # Shrink threshold to make this fast.
        monkeypatch.setattr(audit, "ROTATE_BYTES", 200)
        for _ in range(50):
            audit.log_event(command="purge", status="ok", payload="x" * 30)
        backup = str(tmp_audit) + ".1"
        # At least one rotation must have produced a .1 backup.
        assert os.path.exists(backup)
        # Current file is below threshold (recently rotated).
        assert os.path.getsize(tmp_audit) <= os.path.getsize(backup) + 200

    def test_old_backup_overwritten(self, tmp_audit, monkeypatch):
        monkeypatch.setattr(audit, "ROTATE_BYTES", 200)
        # Create an existing backup with sentinel content.
        os.makedirs(audit.AUDIT_DIR, exist_ok=True)
        backup = str(tmp_audit) + ".1"
        with open(backup, "w") as f:
            f.write("OLD_BACKUP\n")
        # Flood the live file beyond threshold.
        for _ in range(50):
            audit.log_event(command="purge", status="ok", payload="x" * 30)
        # The backup was overwritten by the rotation.
        with open(backup) as f:
            content = f.read()
        assert "OLD_BACKUP" not in content
