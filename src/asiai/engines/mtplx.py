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
        """Return MTPLX version via ``brew list --versions mtplx``."""
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
                    return parts[-1]
        except Exception:
            pass
        return ""
