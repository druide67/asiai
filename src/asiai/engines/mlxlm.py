"""mlx-lm inference engine adapter.

mlx-lm is Apple's native MLX-based inference server, installable via
``brew install mlx-lm``.  It exposes an OpenAI-compatible API on port 8080.
"""

from __future__ import annotations

import logging
import subprocess

from asiai.engines.openai_compat import OpenAICompatEngine

logger = logging.getLogger("asiai.engines.mlxlm")


class MlxLmEngine(OpenAICompatEngine):
    """Adapter for mlx-lm inference server (OpenAI-compatible API on port 8080)."""

    _generate_endpoint = "/v1/chat/completions"
    _generate_mode = "chat"
    _model_format = "MLX"

    @property
    def name(self) -> str:
        return "mlxlm"

    def version(self) -> str:
        """Return mlx-lm version via ``brew list --versions mlx-lm``."""
        try:
            out = subprocess.run(
                ["brew", "list", "--versions", "mlx-lm"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
            # Output: "mlx-lm 0.30.7" or empty if not installed
            if out:
                parts = out.split()
                if len(parts) >= 2:
                    return parts[-1]
        except Exception:
            pass
        return ""
