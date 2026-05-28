"""Engine version-source registry: internal table + entry-point merge.

asiai ships an internal fallback table covering the engines it knows about,
so the feature works standalone. ``asiai-inference-server`` (and any future
plugin) can enrich/override that table through the ``asiai.version_sources``
entry-point group — this is how aisrv contributes the formula/package
mapping for engines it manages (turboquant, llamacpp-aux-*, ...).

The contract is deliberately decoupled: a provider exposes a callable
``provide(api_version: int) -> list[dict]`` and returns *plain dicts* (not a
shared dataclass), so the two packages never import each other's types. asiai
rebuilds its own ``EngineVersionSpec`` from each dict, ignoring unknown keys
for forward compatibility. A provider that raises is logged and skipped — a
broken plugin never crashes ``asiai versions``.
"""

from __future__ import annotations

import dataclasses
import logging
import sys
from importlib.metadata import entry_points

from asiai.versions.models import EngineVersionSpec

logger = logging.getLogger("asiai.versions.registry")

# Contract version asiai offers to ``asiai.version_sources`` providers.
VERSION_SOURCE_API_VERSION = 1

ENTRY_POINT_GROUP = "asiai.version_sources"

# Internal fallback table. Mirrors ``cli._discover_engines`` engine_map keys.
# Kept conservative: only sources we are confident about. aisrv overrides
# these and adds the engines it manages.
_INTERNAL_SPECS: dict[str, EngineVersionSpec] = {
    "ollama": EngineVersionSpec(
        "ollama",
        display="Ollama",
        brew_formula="ollama",
        github_repo="ollama/ollama",
        version_scheme="git_tag",
    ),
    "lmstudio": EngineVersionSpec(
        "lmstudio",
        display="LM Studio",
        brew_cask="lm-studio",
        app_bundle_path="/Applications/LM Studio.app",
        no_upstream=True,
    ),
    "mlxlm": EngineVersionSpec(
        "mlxlm",
        display="mlx-lm",
        brew_formula="mlx-lm",
        pip_package="mlx-lm",
        github_repo="ml-explore/mlx-lm",
    ),
    "llamacpp": EngineVersionSpec(
        "llamacpp",
        display="llama.cpp",
        brew_formula="llama.cpp",
        github_repo="ggml-org/llama.cpp",
        version_scheme="llamacpp_build",
    ),
    "omlx": EngineVersionSpec(
        "omlx",
        display="oMLX",
        pip_package="omlx",
        app_bundle_path="/Applications/oMLX.app",
    ),
    "rapidmlx": EngineVersionSpec(
        "rapidmlx",
        display="Rapid-MLX",
        brew_formula="rapid-mlx",
        version_cmd=("rapid-mlx", "--version"),
    ),
    "vllm_mlx": EngineVersionSpec(
        "vllm_mlx",
        display="vllm-mlx",
        pip_package="vllm-mlx",
    ),
    "vmlx": EngineVersionSpec(
        "vmlx",
        display="vMLX",
        pip_package="vmlx",
    ),
    "exo": EngineVersionSpec(
        "exo",
        display="Exo",
        pip_package="exo-inference",
        github_repo="exo-explore/exo",
    ),
}

# Field names asiai accepts from a provider dict. Anything else is ignored
# (forward-compat: a newer provider may emit fields a newer asiai understands).
_SPEC_FIELDS = {f.name for f in dataclasses.fields(EngineVersionSpec)}


def _spec_from_dict(
    d: dict,
    source: str,
    base: EngineVersionSpec | None = None,
) -> EngineVersionSpec | None:
    """Build/merge an EngineVersionSpec from a provider dict; None if invalid.

    A provider *enriches* — it does not replace. Only the keys actually
    present in *d* are applied; any field the provider omits keeps its value
    from *base* (the internal spec). This prevents a provider that knows the
    brew formula but not, say, the app-bundle path from silently erasing
    asiai's own app-bundle fallback.
    """
    if not isinstance(d, dict):
        return None
    name = d.get("engine_name")
    if not isinstance(name, str) or not name:
        return None
    overrides: dict = {}
    for k, v in d.items():
        if k == "engine_name" or k not in _SPEC_FIELDS:
            continue  # forward-compat: ignore unknown keys
        if k == "version_cmd" and isinstance(v, list):
            v = tuple(v)  # JSON arrays -> tuple
        overrides[k] = v
    try:
        if base is not None:
            return dataclasses.replace(base, **overrides)
        return EngineVersionSpec(engine_name=name, **overrides)
    except (TypeError, ValueError) as e:
        logger.debug("invalid spec dict for %r from %s: %s", name, source, e)
        return None


def _normalize_payload(payload: object) -> list[dict]:
    """Coerce a provider return value into a list of dicts.

    Tolerates a single dict, a list of dicts, or a ``{"specs": [...]}``
    wrapper. Anything else yields an empty list.
    """
    if isinstance(payload, dict):
        if "specs" in payload and isinstance(payload["specs"], list):
            return [d for d in payload["specs"] if isinstance(d, dict)]
        return [payload]
    if isinstance(payload, list):
        return [d for d in payload if isinstance(d, dict)]
    return []


def load_specs() -> dict[str, EngineVersionSpec]:
    """Return the merged engine→spec table.

    Starts from the internal fallback, then applies provider tables from the
    ``asiai.version_sources`` group. Provider entries override internal ones
    per engine key (and carry ``source != "internal"`` semantics — the
    report layer stamps provenance). Never raises; a failing provider is
    logged to stderr and skipped.
    """
    specs = dict(_INTERNAL_SPECS)
    provider_keys: set[str] = set()

    try:
        eps = entry_points(group=ENTRY_POINT_GROUP)
    except Exception as e:  # noqa: BLE001 — importlib edge cases
        logger.debug("entry_points lookup failed: %s", e)
        return specs

    for ep in eps:
        try:
            provide = ep.load()
            payload = provide(api_version=VERSION_SOURCE_API_VERSION)
        except Exception as exc:  # noqa: BLE001 — a broken plugin must not crash us
            print(
                f"[asiai] version source {ep.name!r} failed: {exc}",
                file=sys.stderr,
            )
            continue
        for d in _normalize_payload(payload):
            name = d.get("engine_name") if isinstance(d, dict) else None
            base = specs.get(name) if isinstance(name, str) else None
            spec = _spec_from_dict(d, source=ep.name, base=base)
            if spec is not None:
                specs[spec.engine_name] = spec
                provider_keys.add(spec.engine_name)

    # Stash which keys came from a provider so the report layer can label
    # provenance without re-querying the entry points.
    load_specs._provider_keys = provider_keys  # type: ignore[attr-defined]
    return specs


def provider_keys() -> set[str]:
    """Engine keys that were last sourced from a provider (not internal)."""
    return getattr(load_specs, "_provider_keys", set())
