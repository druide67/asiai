"""mlx-vlm inference engine adapter.

mlx-vlm (github.com/Blaizzy/mlx-vlm) serves MLX vision-language models and
exposes an OpenAI-compatible API through ``mlx_vlm.server``.  It is a distinct
project from mlx-lm: it carries the multimodal architectures, its own tool
parsers, and speculative decoding through DFlash, EAGLE3 or native MTP drafters.

Install with ``pip install mlx-vlm``; start with
``mlx_vlm.server --model <hf_repo_or_path> --port <port>``.
"""

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
        """Return the mlx-vlm version from installed package metadata.

        mlx_vlm.server has no ``--version`` flag, and the server is commonly run
        from a dedicated virtualenv that is not the one asiai runs in.  When the
        package is not importable here, the version is reported as unknown rather
        than guessed: a bench declares the version it can prove.
        """
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
