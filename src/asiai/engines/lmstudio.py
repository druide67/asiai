"""LM Studio inference engine adapter."""

from __future__ import annotations

import json
import logging
import os
import subprocess

from asiai.engines.base import ModelInfo
from asiai.engines.detect import http_get_json
from asiai.engines.openai_compat import OpenAICompatEngine

_APP_PLIST = "/Applications/LM Studio.app/Contents/Info.plist"
_LMS_PATH = os.path.expanduser("~/.lmstudio/bin/lms")

logger = logging.getLogger("asiai.engines.lmstudio")


class LMStudioEngine(OpenAICompatEngine):
    """Adapter for LM Studio inference server (OpenAI-compatible API).

    LM Studio uses /v1/completions (text mode) instead of chat completions.
    """

    _generate_endpoint = "/v1/completions"
    _generate_mode = "completions"
    _model_format = "MLX"

    @property
    def name(self) -> str:
        return "lmstudio"

    def list_running(self) -> list[ModelInfo]:
        """List loaded models, enriching with VRAM from lms CLI when available."""
        models = super().list_running()
        if not models:
            return models

        vram_map = self._get_vram_from_lms()
        if vram_map:
            for m in models:
                if m.name in vram_map:
                    m.size_vram = vram_map[m.name]

        return models

    def _get_vram_from_lms(self) -> dict[str, int]:
        """Call lms ps --json to get VRAM usage per loaded model.

        Falls back to ``lms ls --json`` when ``lms ps`` returns an empty list
        (lazy-loading: models appear in /v1/models but aren't actively loaded
        until the first request).

        Returns:
            Mapping of model identifier → size in bytes, or empty dict on failure.
        """
        if not os.path.isfile(_LMS_PATH):
            return {}
        try:
            result = subprocess.run(
                [_LMS_PATH, "ps", "--json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return {}
            data = json.loads(result.stdout)
            vram_map = self._parse_lms_ps(data)
            if vram_map:
                return vram_map
            # Fallback: lms ls --json (downloaded models with sizeBytes)
            return self._get_size_from_lms_ls()
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
            logger.debug("lms ps --json failed: %s", e)
            return {}

    def _get_size_from_lms_ls(self) -> dict[str, int]:
        """Fallback: call lms ls --json for downloaded model sizes.

        Used when lms ps returns empty (lazy loading scenario).
        """
        try:
            result = subprocess.run(
                [_LMS_PATH, "ls", "--json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return {}
            data = json.loads(result.stdout)
            return self._parse_lms_ps(data)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
            logger.debug("lms ls --json failed: %s", e)
            return {}

    @staticmethod
    def _parse_lms_ps(data: list) -> dict[str, int]:
        """Parse lms ps --json output into {model_id: vram_bytes}.

        The lms CLI returns a JSON array of loaded model objects.
        Each has at minimum: modelKey (or path) and sizeBytes.
        The /v1/models API uses path as the model id.
        """
        vram_map: dict[str, int] = {}
        if not isinstance(data, list):
            return vram_map
        for entry in data:
            if not isinstance(entry, dict):
                continue
            size = entry.get("sizeBytes", 0)
            # The API model id can match modelKey, path, or indexedModelIdentifier
            for key in ("path", "indexedModelIdentifier", "modelKey"):
                val = entry.get(key)
                if val and isinstance(val, str):
                    vram_map[val] = size
        return vram_map

    def version(self) -> str:
        # Check header first
        _, headers = http_get_json(f"{self.base_url}/v1/models")
        version = headers.get("x-lm-studio-version", "")
        if version:
            return version
        # Fallback: /lms/version endpoint
        data, _ = http_get_json(f"{self.base_url}/lms/version")
        if data and isinstance(data, dict) and "version" in data:
            return data["version"]
        # Fallback: read version from app bundle plist
        try:
            out = subprocess.run(
                ["/usr/libexec/PlistBuddy", "-c", "Print :CFBundleShortVersionString", _APP_PLIST],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip().split("+")[0]
        except Exception:
            pass
        return ""
