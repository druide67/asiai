"""Rapid-MLX inference engine adapter.

Rapid-MLX is a third-party MLX-based inference server for Apple Silicon
(github.com/raullenchai/Rapid-MLX). OpenAI-compatible API, hybrid
prefix-cache support via "snapshots RNN" technique. Installable via
``brew install raullenchai/rapid-mlx/rapid-mlx`` or ``pip install rapid-mlx``.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess

from asiai.engines.openai_compat import OpenAICompatEngine

logger = logging.getLogger("asiai.engines.rapidmlx")

# Matches semver-like patterns (e.g. "0.6.66", "1.2.3-beta", "0.6.66+abc")
_VERSION_RE = re.compile(r"\b(\d+\.\d+\.\d+\S*)")


class RapidMlxEngine(OpenAICompatEngine):
    """Adapter for Rapid-MLX inference server (OpenAI-compatible API on port 8004 by default).

    Rapid-MLX is a Homebrew packaging of the vllm-mlx engine (raullenchai upstream).
    The wrapper script /opt/homebrew/bin/rapid-mlx delegates to the embedded
    vllm-mlx Python module in the brew Cellar's libexec venv.
    """

    _generate_endpoint = "/v1/chat/completions"
    _generate_mode = "chat"
    _model_format = "MLX"

    @property
    def name(self) -> str:
        return "rapidmlx"

    def version(self) -> str:
        """Return Rapid-MLX version via ``rapid-mlx --version``."""
        bin_path = shutil.which("rapid-mlx")
        if not bin_path:
            # Fall back to common brew install paths (shutil.which returns
            # None for absolute paths not in $PATH, so check the filesystem
            # directly with executable-permission test).
            for candidate in (
                "/opt/homebrew/bin/rapid-mlx",
                "/usr/local/bin/rapid-mlx",
            ):
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    bin_path = candidate
                    break
        if not bin_path:
            return ""
        try:
            out = subprocess.run(
                [bin_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
        # Output forms: "rapid-mlx 0.6.66", "0.6.66", "rapid-mlx 0.6.66 (build abc)".
        m = _VERSION_RE.search(out)
        return m.group(1) if m else ""
