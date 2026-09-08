"""mlx-vlm adapter (github.com/Blaizzy/mlx-vlm): ``mlx_vlm.server`` exposes an
OpenAI-compatible API. Distinct project from mlx-lm."""

from __future__ import annotations

import logging
import subprocess

from asiai.engines.openai_compat import OpenAICompatEngine

logger = logging.getLogger("asiai.engines.mlxvlm")


class MlxVlmEngine(OpenAICompatEngine):
    """Adapter for the mlx-vlm server (OpenAI-compatible API)."""

    _generate_endpoint = "/v1/chat/completions"
    _generate_mode = "chat"
    _model_format = "MLX"

    @property
    def name(self) -> str:
        return "mlxvlm"

    def version(self) -> str:
        """Return the mlx-vlm version from package metadata, or ``""`` (the server
        has no ``--version`` and often runs in another virtualenv)."""
        try:
            from importlib.metadata import PackageNotFoundError, version

            try:
                return version("mlx-vlm")
            except PackageNotFoundError:
                pass
        except Exception:
            pass
        try:
            out = subprocess.run(
                ["pip", "show", "mlx-vlm"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout
            for line in out.splitlines():
                if line.lower().startswith("version:"):
                    return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return ""
