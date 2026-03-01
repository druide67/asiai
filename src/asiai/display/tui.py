"""Textual TUI dashboard for asiai.

Provides a live-updating terminal UI showing system metrics,
loaded models, and benchmark history.

Requires: ``pip install asiai[tui]``
"""

from __future__ import annotations

import logging

logger = logging.getLogger("asiai.display.tui")

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.widgets import DataTable, Footer, Header, Static

    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


def _format_bytes(n: int) -> str:
    """Format bytes to human-readable string."""
    if n <= 0:
        return "N/A"
    if n >= 1024**3:
        return f"{n / 1024**3:.1f} GB"
    if n >= 1024**2:
        return f"{n / 1024**2:.0f} MB"
    return f"{n / 1024:.0f} KB"


if HAS_TEXTUAL:

    class SystemPanel(Static):
        """Displays system metrics: CPU, RAM, pressure, thermal."""

        def update_data(self, snap: dict) -> None:
            """Update panel with fresh snapshot data."""
            cpu1 = snap.get("cpu_load_1", -1)
            cpu5 = snap.get("cpu_load_5", -1)
            cpu15 = snap.get("cpu_load_15", -1)
            mem_total = snap.get("mem_total", 0)
            mem_used = snap.get("mem_used", 0)
            pct = f"{mem_used / mem_total * 100:.0f}%" if mem_total > 0 else "N/A"
            pressure = snap.get("mem_pressure", "unknown")
            thermal = snap.get("thermal_level", "unknown")
            speed = snap.get("thermal_speed_limit", -1)

            text = (
                f"[bold]System[/bold]\n"
                f"  CPU Load: {cpu1:.2f} / {cpu5:.2f} / {cpu15:.2f}\n"
                f"  Memory:   {_format_bytes(mem_used)} / {_format_bytes(mem_total)}  {pct}\n"
                f"  Pressure: {pressure}\n"
                f"  Thermal:  {thermal} ({speed}%)"
            )
            self.update(text)

    class ModelsPanel(DataTable):
        """DataTable showing loaded models across engines."""

        def on_mount(self) -> None:
            self.add_columns("Engine", "Model", "VRAM", "Format", "Quant")

        def update_data(self, snap: dict) -> None:
            """Refresh model rows from snapshot."""
            self.clear()
            for m in snap.get("models", []):
                self.add_row(
                    m.get("engine", ""),
                    m.get("name", "unknown"),
                    _format_bytes(m.get("size_vram", 0)),
                    m.get("format", ""),
                    m.get("quantization", ""),
                )

    class BenchPanel(DataTable):
        """DataTable showing benchmark history."""

        def on_mount(self) -> None:
            self.add_columns(
                "Engine", "Model", "Prompt", "tok/s", "TTFT",
            )

        def update_data(self, rows: list[dict]) -> None:
            """Refresh benchmark rows."""
            self.clear()
            for r in rows[:20]:  # Show last 20
                ttft = r.get("ttft_ms", 0)
                ttft_str = f"{ttft / 1000:.2f}s" if ttft > 0 else "N/A"
                self.add_row(
                    r.get("engine", ""),
                    r.get("model", ""),
                    r.get("prompt_type", ""),
                    f"{r.get('tok_per_sec', 0):.1f}",
                    ttft_str,
                )

    class AsiaiApp(App):
        """Main TUI application for asiai."""

        CSS = """
        Screen {
            layout: grid;
            grid-size: 2 2;
            grid-gutter: 1;
        }
        SystemPanel {
            row-span: 1;
            column-span: 1;
            border: solid $primary;
            padding: 1;
        }
        ModelsPanel {
            row-span: 1;
            column-span: 1;
            border: solid $secondary;
        }
        BenchPanel {
            row-span: 1;
            column-span: 2;
            border: solid $accent;
        }
        """

        BINDINGS = [
            Binding("q", "quit", "Quit"),
            Binding("r", "refresh", "Refresh"),
        ]

        TITLE = "asiai"
        SUB_TITLE = "LLM Benchmark & Monitoring"

        def __init__(
            self,
            engines: list | None = None,
            db_path: str = "",
        ) -> None:
            super().__init__()
            self._engines = engines or []
            self._db_path = db_path

        def compose(self) -> ComposeResult:
            yield Header()
            yield SystemPanel(id="system")
            yield ModelsPanel(id="models")
            yield BenchPanel(id="bench")
            yield Footer()

        def on_mount(self) -> None:
            """Start auto-refresh timer."""
            self.action_refresh()
            self.set_interval(5, self.action_refresh)

        def action_refresh(self) -> None:
            """Refresh all panels with fresh data."""
            try:
                from asiai.collectors.snapshot import collect_snapshot
                from asiai.storage.db import init_db, query_benchmarks, store_snapshot

                snap = collect_snapshot(self._engines)

                # Store if we have a DB path
                if self._db_path:
                    init_db(self._db_path)
                    store_snapshot(self._db_path, snap)

                # Update panels
                system_panel = self.query_one("#system", SystemPanel)
                system_panel.update_data(snap)

                models_panel = self.query_one("#models", ModelsPanel)
                models_panel.update_data(snap)

                # Benchmark history
                if self._db_path:
                    rows = query_benchmarks(self._db_path, hours=24)
                    bench_panel = self.query_one("#bench", BenchPanel)
                    bench_panel.update_data(rows)
            except Exception as e:
                logger.error("Refresh error: %s", e)


def run_tui(engines: list | None = None, db_path: str = "") -> None:
    """Launch the TUI app. Raises ImportError if textual is not installed."""
    if not HAS_TEXTUAL:
        raise ImportError(
            "Textual is required for the TUI. Install with: pip install asiai[tui]"
        )
    app = AsiaiApp(engines=engines, db_path=db_path)
    app.run()
