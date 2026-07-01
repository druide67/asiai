"""Fleet write-command timeout spec — the drift + ordering invariants (SB).

This is the safety net that prevents the briefing retex from recurring: the
three write layers used to hand-maintain their own timeout maps, drift apart,
and invert the nesting (edge/client tighter than the loopback work budget) so an
outer layer killed a command the inner layer was still running.
"""

from __future__ import annotations

import pytest

from asiai.fleet import command_spec as cs


def test_allowed_commands_is_the_budget_keys() -> None:
    """The whitelist and the timeout map are the SAME source — cannot disagree."""
    assert cs.ALLOWED_COMMANDS == frozenset(cs.WORK_BUDGET)
    assert "upgrade" in cs.ALLOWED_COMMANDS


@pytest.mark.parametrize("command", sorted(cs.WORK_BUDGET))
def test_outer_layers_wait_strictly_longer_than_inner(command: str) -> None:
    """THE invariant: client > edge > loopback for every command.

    Each HTTP hop outward must outlast the layer it calls, or it abandons a
    command still legitimately running inside. Strictly greater (by HOP_MARGIN),
    not merely >=, so there is always slack for the network + handler overhead.
    """
    loop = cs.loopback_timeout(command)
    edge = cs.edge_timeout(command)
    client = cs.client_timeout(command)
    assert client > edge > loop, f"{command}: client={client} edge={edge} loop={loop}"
    assert edge - loop == cs.HOP_MARGIN
    assert client - edge == cs.HOP_MARGIN


def test_upgrade_regression_client_outlasts_loopback() -> None:
    """The exact briefing retex: the outermost hop must NOT time out before the
    loopback finishes a long upgrade (was client 420 < loopback 600 → killed)."""
    assert cs.client_timeout("upgrade") > cs.loopback_timeout("upgrade")
    assert cs.loopback_timeout("upgrade") == 600.0


def test_inner_tool_timeout_reports_before_subprocess_kill() -> None:
    """A wrapped tool (aisctl upgrade --timeout N) must finish BEFORE the loopback
    subprocess-kill, so the operator sees the tool's real error, not a SIGKILL."""
    assert cs.inner_tool_timeout("upgrade") < cs.loopback_timeout("upgrade")
    assert cs.inner_tool_timeout("upgrade") == 540.0  # 600 budget - 60 headroom


def test_inner_tool_timeout_never_nonpositive_for_small_budgets() -> None:
    """Budgets below the headroom (purge 30, headroom 60) floor at 1s, never <= 0."""
    assert cs.inner_tool_timeout("purge") >= 1.0


@pytest.mark.parametrize("fn", [cs.loopback_timeout, cs.edge_timeout, cs.client_timeout])
def test_unknown_command_raises(fn) -> None:
    with pytest.raises(KeyError, match="unknown fleet write command"):
        fn("rm-rf-slash")
