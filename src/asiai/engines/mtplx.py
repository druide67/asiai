"""MTPLX inference engine adapter.

MTPLX is a third-party MLX-based inference server for Apple Silicon
(github.com/youssofal/MTPLX) with native MTP speculative decoding.  It
exposes an OpenAI-compatible API and is installable via
``brew tap youssofal/mtplx && brew install mtplx``.
"""

from __future__ import annotations

import logging
import subprocess

from asiai.engines.openai_compat import OpenAICompatEngine

logger = logging.getLogger("asiai.engines.mtplx")


class MtplxEngine(OpenAICompatEngine):
    """Adapter for MTPLX inference server (OpenAI-compatible API, quickstart port varies)."""

    _generate_endpoint = "/v1/chat/completions"
    _generate_mode = "chat"
    _model_format = "MLX"

    @property
    def name(self) -> str:
        return "mtplx"

    def version(self) -> str:
        """Return the version of the MTPLX process actually serving requests.

        Read from the server's ``/health`` payload: ``mlx_runtime.path``
        points inside the serving venv (``.../var/mtplx/venv-X.Y.Z/...``),
        which identifies the process. ``brew list`` only reports the keg —
        on 2026-08-29 a benchmark campaign exported the keg version for a
        cell that served a different venv, making the archived results
        misidentify what was measured. The keg fallback is kept, returns the
        bare version (the field is parsed as a version by the DB, the
        leaderboard grouping and the cards — prose there split one version
        into two groups, 2026-09-05 review) and logs that it is unverified;
        proving identity stays with the bench protocol, not with this string.
        """
        import re

        from asiai.engines.detect import http_get_json

        try:
            data, _ = http_get_json(f"{self.base_url}/health", **self._http_kwargs())
            path = ((data or {}).get("mlx_runtime") or {}).get("path") or ""
            m = re.search(r"/venv-(\d+(?:\.\d+)+)/", path)
            if m:
                return m.group(1)
        except Exception:
            pass
        try:
            out = subprocess.run(
                ["brew", "list", "--versions", "mtplx"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
            # Output: "mtplx 2.0.2" or empty if not installed
            if out:
                parts = out.split()
                if len(parts) >= 2:
                    logger.warning(
                        "MTPLX version %s read from the Homebrew keg, not from the "
                        "serving process (/health has no mlx_runtime.path)",
                        parts[-1],
                    )
                    return parts[-1]
        except Exception:
            pass
        return ""
