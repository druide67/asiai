"""Tests for power-supply detection."""

from __future__ import annotations

# ── collect_power_supply ──────────────────────────────────────────────


class TestCollectPowerSupply:
    def _with(self, stdout: str):
        from unittest.mock import patch

        import asiai.collectors.system as sysmod

        fake = type("R", (), {"stdout": stdout})()
        return patch.object(sysmod.subprocess, "run", return_value=fake), sysmod

    def test_ac(self):
        ctx, sysmod = self._with(
            "Now drawing from 'AC Power'\n -InternalBattery-0 80%; AC attached"
        )
        with ctx:
            assert sysmod.collect_power_supply() == "ac"

    def test_battery(self):
        ctx, sysmod = self._with(
            "Now drawing from 'Battery Power'\n -InternalBattery-0 64%; discharging"
        )
        with ctx:
            assert sysmod.collect_power_supply() == "battery"

    def test_unknown_is_none_not_a_guess(self):
        ctx, sysmod = self._with("")
        with ctx:
            assert sysmod.collect_power_supply() is None

    def test_pmset_failure_is_none(self):
        from unittest.mock import patch

        import asiai.collectors.system as sysmod

        with patch.object(sysmod.subprocess, "run", side_effect=OSError("no pmset")):
            assert sysmod.collect_power_supply() is None
