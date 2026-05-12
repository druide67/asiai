"""Tests for asiai sub-CLI plugin discovery (asiai.subcommands entry-point group)."""

from __future__ import annotations

import argparse
from importlib.metadata import EntryPoint
from unittest.mock import MagicMock, patch

from asiai.cli import PLUGIN_API_VERSION, _load_subcommand_plugins, main

# ---------------------------------------------------------------------------
# Module-level constant
# ---------------------------------------------------------------------------


def test_plugin_api_version_is_int() -> None:
    assert isinstance(PLUGIN_API_VERSION, int)
    assert PLUGIN_API_VERSION >= 1


# ---------------------------------------------------------------------------
# _load_subcommand_plugins — unit-level
# ---------------------------------------------------------------------------


def _make_subparsers() -> tuple[argparse.ArgumentParser, argparse._SubParsersAction]:
    parser = argparse.ArgumentParser(prog="asiai-test")
    sub = parser.add_subparsers(dest="command")
    return parser, sub


def test_load_plugins_calls_register_with_subparsers_and_commands() -> None:
    """A discovered plugin's register() receives (subparsers, commands)."""
    parser, subparsers = _make_subparsers()
    commands: dict = {}

    captured: list = []

    def fake_register(subs, cmds):
        captured.append((subs, cmds))
        cmds["fake"] = lambda args: 0

    fake_ep = MagicMock(spec=EntryPoint)
    fake_ep.name = "fake-plugin"
    fake_ep.load.return_value = fake_register

    with patch("asiai.cli.entry_points", return_value=[fake_ep]):
        _load_subcommand_plugins(subparsers, commands)

    assert len(captured) == 1
    assert captured[0][0] is subparsers
    assert "fake" in commands


def test_load_plugins_is_fault_tolerant(capsys) -> None:
    """A plugin that raises must not crash asiai; error goes to stderr."""
    parser, subparsers = _make_subparsers()
    commands: dict = {}

    def broken_register(subs, cmds):
        raise RuntimeError("plugin kaputt")

    fake_ep = MagicMock(spec=EntryPoint)
    fake_ep.name = "broken-plugin"
    fake_ep.load.return_value = broken_register

    with patch("asiai.cli.entry_points", return_value=[fake_ep]):
        _load_subcommand_plugins(subparsers, commands)  # must not raise

    err = capsys.readouterr().err
    assert "broken-plugin" in err
    assert "kaputt" in err


def test_load_plugins_with_no_registered_plugins() -> None:
    """No entry points → commands dict stays empty, no error."""
    parser, subparsers = _make_subparsers()
    commands: dict = {}
    with patch("asiai.cli.entry_points", return_value=[]):
        _load_subcommand_plugins(subparsers, commands)
    assert commands == {}


# ---------------------------------------------------------------------------
# main() — plugin dispatch integration
# ---------------------------------------------------------------------------


def test_main_dispatches_to_plugin_command() -> None:
    """When a plugin registers 'myplug', `asiai myplug` dispatches to it."""
    handler_called: list = []

    def fake_register(subs, cmds):
        subs.add_parser("myplug", help="test plugin")
        cmds["myplug"] = lambda args: handler_called.append(True) or 0

    fake_ep = MagicMock(spec=EntryPoint)
    fake_ep.name = "my-plugin"
    fake_ep.load.return_value = fake_register

    with patch("asiai.cli.entry_points", return_value=[fake_ep]):
        rc = main(["myplug"])

    assert rc == 0
    assert handler_called


def test_main_skips_plugin_discovery_for_version_flag() -> None:
    """--version must never trigger plugin discovery (cold-start budget)."""
    discovery_called: list = []

    def fake_register(subs, cmds):
        discovery_called.append(True)

    fake_ep = MagicMock(spec=EntryPoint)
    fake_ep.name = "slow-plugin"
    fake_ep.load.return_value = fake_register

    with patch("asiai.cli.entry_points", return_value=[fake_ep]):
        try:
            main(["--version"])
        except SystemExit:
            pass

    assert not discovery_called, "plugin discovery must be skipped for --version"


def test_main_skips_plugin_discovery_for_help_flag() -> None:
    """--help must never trigger plugin discovery."""
    discovery_called: list = []

    def fake_register(subs, cmds):
        discovery_called.append(True)

    fake_ep = MagicMock(spec=EntryPoint)
    fake_ep.name = "slow-plugin"
    fake_ep.load.return_value = fake_register

    with patch("asiai.cli.entry_points", return_value=[fake_ep]):
        try:
            main(["--help"])
        except SystemExit:
            pass

    assert not discovery_called, "plugin discovery must be skipped for --help"
