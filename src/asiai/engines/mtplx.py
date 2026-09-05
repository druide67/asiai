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
        """Version of the MTPLX process serving requests, from
        ``/health.mlx_runtime.path``; falls back to the keg version with a warning.
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
