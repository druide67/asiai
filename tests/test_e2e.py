"""End-to-end CLI tests via subprocess."""

from __future__ import annotations

import subprocess
import sys


class TestCLIEndToEnd:
    """Run the real CLI binary and validate stdout/stderr."""

    def _run(
        self, *args: str, expect_rc: int = 0, timeout: int = 10
    ) -> subprocess.CompletedProcess:
        result = subprocess.run(
            [sys.executable, "-m", "asiai", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        assert result.returncode == expect_rc, (
            f"Expected rc={expect_rc}, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        return result

    def test_version_flag(self):
        result = self._run("--version")
        assert "asiai" in result.stdout

    def test_version_subcommand(self):
        result = self._run("version")
        assert "asiai" in result.stdout

    def test_help(self):
        result = self._run("--help")
        assert "detect" in result.stdout
        assert "bench" in result.stdout
        assert "monitor" in result.stdout

    def test_detect_output(self):
        """detect produces meaningful output (engines or 'no engines' message)."""
        result = subprocess.run(
            [sys.executable, "-m", "asiai", "detect"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        combined = result.stdout + result.stderr
        assert "engine" in combined.lower() or "detect" in combined.lower()

    def test_doctor_runs(self):
        """doctor should always run (even without engines).

        doctor does heavy per-engine I/O (brew/pip/HTTP) plus the offline
        version recap, so it gets a generous timeout — the test asserts it
        runs and produces output, not that it's fast.
        """
        result = self._run("doctor", timeout=30)
        assert "Doctor" in result.stdout or "System" in result.stdout

    def test_version_enriched(self):
        """version subcommand shows chip and RAM info."""
        result = self._run("version")
        assert "asiai" in result.stdout
        assert "GB RAM" in result.stdout

    def test_setup_runs(self):
        """setup wizard should run without error."""
        result = self._run("setup")
        assert "Hardware:" in result.stdout or "setup wizard" in result.stdout

    def test_help_includes_setup(self):
        """setup should appear in help output."""
        result = self._run("--help")
        assert "setup" in result.stdout
