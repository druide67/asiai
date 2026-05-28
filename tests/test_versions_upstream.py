"""Tests for opt-in upstream version fetches (PyPI + GitHub)."""

from __future__ import annotations

import io
import json
import urllib.error
from unittest import mock

from asiai.versions import upstream


class _FakeResp:
    """Minimal context-manager stand-in for urlopen's return value."""

    def __init__(self, body: bytes):
        self._buf = io.BytesIO(body)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=-1):
        return self._buf.read(n)


def _json_resp(obj) -> _FakeResp:
    return _FakeResp(json.dumps(obj).encode("utf-8"))


# --- pypi_latest -----------------------------------------------------------


def test_pypi_latest_ok():
    with mock.patch.object(
        upstream.urllib.request, "urlopen", return_value=_json_resp({"info": {"version": "0.31.0"}})
    ):
        assert upstream.pypi_latest("mlx-lm") == "0.31.0"


def test_pypi_latest_empty_package():
    assert upstream.pypi_latest("") is None


def test_pypi_latest_http_error():
    err = urllib.error.HTTPError("u", 404, "nf", {}, None)
    with mock.patch.object(upstream.urllib.request, "urlopen", side_effect=err):
        assert upstream.pypi_latest("nope") is None


def test_pypi_latest_timeout():
    with mock.patch.object(upstream.urllib.request, "urlopen", side_effect=TimeoutError):
        assert upstream.pypi_latest("mlx-lm") is None


# --- github_latest_release -------------------------------------------------


def test_github_latest_release_ok():
    with mock.patch.object(
        upstream.urllib.request, "urlopen", return_value=_json_resp({"tag_name": "b8200"})
    ):
        assert upstream.github_latest_release("ggml-org/llama.cpp") == "b8200"


def test_github_token_header_set(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "secret-tok")
    captured = {}

    def _fake_urlopen(req, timeout=None):
        captured["auth"] = req.headers.get("Authorization")
        return _json_resp({"tag_name": "b8200"})

    with mock.patch.object(upstream.urllib.request, "urlopen", side_effect=_fake_urlopen):
        upstream.github_latest_release("ggml-org/llama.cpp")
    assert captured["auth"] == "Bearer secret-tok"


def test_github_no_token_no_auth_header(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    captured = {}

    def _fake_urlopen(req, timeout=None):
        captured["auth"] = req.headers.get("Authorization")
        return _json_resp({"tag_name": "b8200"})

    with mock.patch.object(upstream.urllib.request, "urlopen", side_effect=_fake_urlopen):
        upstream.github_latest_release("ggml-org/llama.cpp")
    assert captured["auth"] is None


# --- defensive shell -------------------------------------------------------


def test_get_json_rejects_non_http_scheme():
    # file:// must never reach urlopen.
    with mock.patch.object(upstream.urllib.request, "urlopen") as urlopen:
        assert upstream._get_json("file:///etc/passwd", 5.0) is None
        urlopen.assert_not_called()


def test_get_json_oversized_response():
    big = b"x" * (upstream._MAX_RESPONSE_BYTES + 10)
    with mock.patch.object(upstream.urllib.request, "urlopen", return_value=_FakeResp(big)):
        assert upstream._get_json("https://pypi.org/pypi/x/json", 5.0) is None


def test_get_json_non_object_body():
    with mock.patch.object(
        upstream.urllib.request, "urlopen", return_value=_FakeResp(b'["a","b"]')
    ):
        assert upstream._get_json("https://example.com/x", 5.0) is None


# --- fetch_all -------------------------------------------------------------


def test_fetch_all_mixed_sources():
    def _fake(source, target):
        return {"pypi": "0.31.0", "github": "b8200"}[source]

    jobs = [
        ("mlxlm", "pypi", "mlx-lm"),
        ("llamacpp", "github", "ggml-org/llama.cpp"),
    ]
    with (
        mock.patch.object(upstream, "pypi_latest", side_effect=lambda t, to=5.0: "0.31.0"),
        mock.patch.object(upstream, "github_latest_release", side_effect=lambda t, to=5.0: "b8200"),
    ):
        out = upstream.fetch_all(jobs)
    assert out == {"mlxlm": "0.31.0", "llamacpp": "b8200"}


def test_fetch_all_empty():
    assert upstream.fetch_all([]) == {}
