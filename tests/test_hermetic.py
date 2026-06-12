"""Guard test: the suite must never touch the developer's real files.

Every user-facing path is a module constant frozen at import with
``expanduser("~/…")``. The autouse ``_isolate_home`` fixture in conftest.py
re-points them at a throwaway home. This test proves that isolation is real
(not a silent no-op) by checking the live constants against the *system* home
resolved via ``pwd`` — which ignores the patched ``$HOME`` — so a regression
that breaks the fixture fails here instead of silently writing to ~/.config
and ~/.local again.
"""

from __future__ import annotations

import importlib
import os
import pwd

import pytest

# Real home of the running user, independent of the patched $HOME.
_REAL_HOME = pwd.getpwuid(os.getuid()).pw_dir

# (module, attribute) pairs that must resolve OUTSIDE the real ~/.config and
# ~/.local trees while the suite runs.
_SENSITIVE = [
    ("asiai.storage.db", "DEFAULT_DB_PATH"),
    ("asiai.daemon", "DATA_DIR"),
    ("asiai.daemon", "PLIST_DIR"),
    ("asiai.auth.config", "CONFIG_PATH"),
    ("asiai.auth.config", "LOCK_PATH"),
    ("asiai.auth.audit", "AUDIT_PATH"),
    ("asiai.auth.loopback", "TOKEN_PATH"),
    ("asiai.engines.config", "CONFIG_PATH"),
    ("asiai.fleet.config", "CONFIG_PATH"),
    ("asiai.fleet.config", "LOCK_PATH"),
    ("asiai.community", "_AGENT_JSON"),
]

_FORBIDDEN_PREFIXES = (
    os.path.join(_REAL_HOME, ".config", "asiai"),
    os.path.join(_REAL_HOME, ".local", "share", "asiai"),
    os.path.join(_REAL_HOME, ".local", "state", "asiai"),
    os.path.join(_REAL_HOME, "Library", "LaunchAgents"),
)


@pytest.mark.parametrize("mod_name,attr", _SENSITIVE)
def test_path_constants_isolated_from_real_home(mod_name, attr):
    mod = importlib.import_module(mod_name)
    value = os.path.realpath(getattr(mod, attr))
    for forbidden in _FORBIDDEN_PREFIXES:
        assert not value.startswith(os.path.realpath(forbidden)), (
            f"{mod_name}.{attr} resolves to {value}, inside the real home "
            f"({forbidden}) — the _isolate_home fixture is not covering it"
        )


def test_bench_without_db_does_not_touch_real_metrics_db():
    """The headline finding: `asiai bench` with no --db migrated the real DB."""
    import asiai.storage.db as db
    from asiai.cli import main  # noqa: F401  (import resolves DEFAULT_DB_PATH at runtime)

    real_metrics = os.path.join(_REAL_HOME, ".local", "share", "asiai", "metrics.db")
    assert os.path.realpath(db.DEFAULT_DB_PATH) != os.path.realpath(real_metrics)
