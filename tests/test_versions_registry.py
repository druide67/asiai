"""Tests for the version-source registry and entry-point merge."""

from __future__ import annotations

from unittest import mock

from asiai.versions import registry
from asiai.versions.models import EngineVersionSpec


class _FakeEP:
    """Minimal importlib.metadata EntryPoint stand-in."""

    def __init__(self, name, fn):
        self.name = name
        self._fn = fn

    def load(self):
        return self._fn


def test_internal_table_when_no_provider():
    with mock.patch.object(registry, "entry_points", return_value=[]):
        specs = registry.load_specs()
    assert "llamacpp" in specs
    assert specs["llamacpp"].brew_formula == "llama.cpp"
    assert specs["llamacpp"].version_scheme == "llamacpp_build"
    assert registry.provider_keys() == set()


def test_provider_overrides_and_adds():
    def provide(api_version):
        assert api_version == registry.VERSION_SOURCE_API_VERSION
        return [
            # Override an internal engine
            {
                "engine_name": "llamacpp",
                "brew_formula": "llama.cpp",
                "display": "llama.cpp (aisrv)",
            },
            # Add a new engine aisrv manages
            {"engine_name": "turboquant", "brew_formula": "turboquant", "display": "TurboQuant"},
            {
                "engine_name": "llamacpp-aux-1",
                "brew_formula": "llama.cpp",
                "version_scheme": "llamacpp_build",
            },
        ]

    ep = _FakeEP("engines", provide)
    with mock.patch.object(registry, "entry_points", return_value=[ep]):
        specs = registry.load_specs()

    assert specs["llamacpp"].display == "llama.cpp (aisrv)"
    assert "turboquant" in specs
    assert "llamacpp-aux-1" in specs
    assert specs["llamacpp-aux-1"].version_scheme == "llamacpp_build"
    assert {"llamacpp", "turboquant", "llamacpp-aux-1"} <= registry.provider_keys()


def test_provider_that_raises_is_skipped(capsys):
    def boom(api_version):
        raise RuntimeError("plugin exploded")

    ep = _FakeEP("broken", boom)
    with mock.patch.object(registry, "entry_points", return_value=[ep]):
        specs = registry.load_specs()
    # Internal table still intact.
    assert "llamacpp" in specs
    err = capsys.readouterr().err
    assert "version source 'broken' failed" in err


def test_unknown_keys_ignored_forward_compat():
    def provide(api_version):
        return [
            {
                "engine_name": "ollama",
                "brew_formula": "ollama",
                "future_field_we_dont_know": "ignored",
            }
        ]

    ep = _FakeEP("engines", provide)
    with mock.patch.object(registry, "entry_points", return_value=[ep]):
        specs = registry.load_specs()
    assert isinstance(specs["ollama"], EngineVersionSpec)
    assert specs["ollama"].brew_formula == "ollama"


def test_version_cmd_list_coerced_to_tuple():
    def provide(api_version):
        return [{"engine_name": "rapidmlx", "version_cmd": ["rapid-mlx", "--version"]}]

    ep = _FakeEP("engines", provide)
    with mock.patch.object(registry, "entry_points", return_value=[ep]):
        specs = registry.load_specs()
    assert specs["rapidmlx"].version_cmd == ("rapid-mlx", "--version")


def test_wrapper_payload_shape():
    def provide(api_version):
        return {"specs": [{"engine_name": "vmlx", "pip_package": "vmlx"}]}

    ep = _FakeEP("engines", provide)
    with mock.patch.object(registry, "entry_points", return_value=[ep]):
        specs = registry.load_specs()
    assert specs["vmlx"].pip_package == "vmlx"


def test_provider_enriches_without_erasing_internal_fields():
    # aisrv's lmstudio entry carries brew_cask but omits app_bundle_path.
    # The internal lmstudio spec HAS app_bundle_path — it must survive the merge.
    def provide(api_version):
        return [
            {
                "engine_name": "lmstudio",
                "display": "LM Studio",
                "brew_cask": "lm-studio",
                "no_upstream": True,
                "version_scheme": "semver",
            }
        ]

    ep = _FakeEP("engines", provide)
    with mock.patch.object(registry, "entry_points", return_value=[ep]):
        specs = registry.load_specs()
    lms = specs["lmstudio"]
    # Provider override applied...
    assert lms.brew_cask == "lm-studio"
    # ...but the internal app-bundle fallback is preserved.
    assert lms.app_bundle_path == "/Applications/LM Studio.app"


def test_invalid_dict_without_engine_name_skipped():
    def provide(api_version):
        return [{"brew_formula": "orphan"}, {"engine_name": "ollama", "brew_formula": "ollama"}]

    ep = _FakeEP("engines", provide)
    with mock.patch.object(registry, "entry_points", return_value=[ep]):
        specs = registry.load_specs()
    assert specs["ollama"].brew_formula == "ollama"
    # The orphan dict produced no new key.
    assert "orphan" not in specs
