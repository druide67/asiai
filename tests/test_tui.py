"""Tests for the TUI module."""

from __future__ import annotations

import pytest

try:
    from asiai.display.tui import AsiaiApp, SystemPanel, run_tui

    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

pytestmark = pytest.mark.skipif(not HAS_TEXTUAL, reason="textual not installed")


class TestSystemPanel:
    def test_update_data(self):
        panel = SystemPanel()
        snap = {
            "cpu_load_1": 2.5,
            "cpu_load_5": 3.0,
            "cpu_load_15": 2.8,
            "mem_total": 64 * 1024**3,
            "mem_used": 32 * 1024**3,
            "mem_pressure": "normal",
            "thermal_level": "nominal",
            "thermal_speed_limit": 100,
        }
        # Should not raise
        panel.update_data(snap)


class TestAsiaiApp:
    @pytest.mark.asyncio
    async def test_app_creates(self):
        app = AsiaiApp(engines=[], db_path="")
        assert app.TITLE == "asiai"

    @pytest.mark.asyncio
    async def test_app_compose(self):
        """Verify the app can compose its widgets."""
        app = AsiaiApp(engines=[], db_path="")
        async with app.run_test(size=(120, 40)):
            # Check that the app started and has expected widgets
            assert app.query_one("#system") is not None
            assert app.query_one("#models") is not None
            assert app.query_one("#bench") is not None


class TestRunTui:
    def test_import_error_without_textual(self):
        """run_tui should raise ImportError when textual is not available."""
        import asiai.display.tui as tui_module

        original = tui_module.HAS_TEXTUAL
        try:
            tui_module.HAS_TEXTUAL = False
            with pytest.raises(ImportError, match="Textual"):
                run_tui()
        finally:
            tui_module.HAS_TEXTUAL = original
