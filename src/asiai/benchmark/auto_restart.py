"""Optional integration with ``aisctl`` (asiai-inference-server) to cold-restart
the target engine before an agentic-mode bench.

When the user passes ``--agentic-auto-restart`` and ``aisctl`` is available
on PATH, the engine is restarted via ``aisctl restart <engine>`` and we
poll its health endpoint until it answers. This produces a reproducible
cold-start baseline — useful for engines that don't expose a model-unload
API (llama.cpp, oMLX, TurboQuant) where the only reliable way to wipe the
KV cache and freshly time a cold load is a daemon restart.

If ``aisctl`` is missing or the engine isn't managed by aisrv, the function
emits a warning and the bench proceeds against whatever state is already
running. The aisrv integration is strictly opt-in — asiai never reaches
out to aisctl unless the user asked for it.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
import urllib.error
import urllib.request

logger = logging.getLogger("asiai.benchmark.auto_restart")


# Engines whose daemon is managed by aisrv (`aisctl` ships drivers for these).
# Engines outside this set are left to the user to lifecycle manually.
AISCTL_MANAGED_ENGINES = frozenset(
    {
        "ollama",
        "llamacpp",
        "llamacpp-aux",
        "lmstudio",
        "omlx",
        "turboquant",
        "vmlx",
        "mlx-lm",
    }
)


def is_aisctl_available() -> bool:
    """Return True when ``aisctl`` is on PATH."""
    return shutil.which("aisctl") is not None


def _wait_healthy(base_url: str, timeout: int = 120) -> bool:
    """Poll ``base_url/health`` until it returns 'ok' or timeout elapses.

    Falls back to ``base_url/v1/models`` for engines that don't expose
    ``/health`` (mlx-lm, vmlx). Returns True on success, False on timeout.
    """
    deadline = time.monotonic() + timeout
    health_url = base_url.rstrip("/") + "/health"
    models_url = base_url.rstrip("/") + "/v1/models"
    while time.monotonic() < deadline:
        for url in (health_url, models_url):
            try:
                with urllib.request.urlopen(url, timeout=2) as resp:
                    if 200 <= resp.status < 300:
                        return True
            except (urllib.error.URLError, urllib.error.HTTPError, OSError):
                pass
        time.sleep(1)
    return False


def auto_restart_engine(
    engine_name: str,
    base_url: str,
    healthcheck_timeout: int = 120,
) -> tuple[bool, str]:
    """Restart ``engine_name`` via ``aisctl restart`` and wait until healthy.

    Returns a (success, message) tuple. ``success`` is True only when the
    restart command exits 0 AND the engine answers healthy within
    ``healthcheck_timeout``. Otherwise the caller decides whether to abort
    the bench or proceed against the (possibly degraded) engine.
    """
    if engine_name not in AISCTL_MANAGED_ENGINES:
        return False, f"{engine_name} is not managed by aisrv — skipping auto-restart"
    aisctl = shutil.which("aisctl")
    if not aisctl:
        return False, "aisctl not found on PATH — skipping auto-restart"

    try:
        proc = subprocess.run(
            [aisctl, "restart", engine_name],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"aisctl restart failed to launch: {e}"

    if proc.returncode != 0:
        # aisctl prints structured Python-dict output to stdout, errors to stderr.
        err = (proc.stderr or proc.stdout or "").strip()[:300]
        return False, f"aisctl restart returncode={proc.returncode}: {err}"

    if not _wait_healthy(base_url, timeout=healthcheck_timeout):
        return False, f"engine did not become healthy within {healthcheck_timeout}s"

    return True, f"{engine_name} restarted and healthy"


__all__ = [
    "AISCTL_MANAGED_ENGINES",
    "auto_restart_engine",
    "is_aisctl_available",
]
