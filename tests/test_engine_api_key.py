"""Tests for per-engine API key support (api_key_file config field).

Engines whose server requires ``Authorization: Bearer <key>`` on all routes
(e.g. MTPLX with an API key, llama.cpp with ``--api-key``) are configured
with an ``api_key_file`` entry in engines.json. The key lives in that file,
never in the config itself, and is only ever sent to the engine's own URL.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import MagicMock, patch

import pytest

from asiai.engines.config import (
    get_api_key_file,
    load_config,
    read_api_key_file,
    resolve_api_key,
    upsert_engine,
)
from asiai.engines.detect import detect_engine_type, detect_engines
from asiai.engines.mtplx import MtplxEngine

API_KEY = "sk-test-key-do-not-log"


class _BearerHandler(BaseHTTPRequestHandler):
    """OpenAI-compatible test server that 401s every route without the key."""

    require_auth = True
    seen_headers: list[dict]  # class attribute, fresh per fixture

    def _send_json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {API_KEY}"

    def do_GET(self):  # noqa: N802 (http.server API)
        type(self).seen_headers.append(dict(self.headers))
        if self.require_auth and not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return
        if self.path == "/v1/models":
            self._send_json(200, {"data": [{"id": "test-model", "owned_by": "mtplx"}]})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802 (http.server API)
        type(self).seen_headers.append(dict(self.headers))
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if self.require_auth and not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return
        if self.path == "/v1/chat/completions":
            chunks = [
                {"choices": [{"delta": {"content": "Hello"}}]},
                {"choices": [{"delta": {"content": " world"}}]},
                {"choices": [], "usage": {"completion_tokens": 2, "prompt_tokens": 3}},
            ]
            body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
            data = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self._send_json(404, {"error": "not found"})

    def log_message(self, *args):  # silence test output
        pass


def _start_server(require_auth: bool):
    handler = type(
        "Handler",
        (_BearerHandler,),
        {"seen_headers": [], "require_auth": require_auth},
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    return server, url, handler


@pytest.fixture
def bearer_server():
    """Server requiring Bearer auth on every route. Yields (url, handler)."""
    server, url, handler = _start_server(require_auth=True)
    yield url, handler
    server.shutdown()
    server.server_close()


@pytest.fixture
def open_server():
    """Server accepting anything, recording request headers."""
    server, url, handler = _start_server(require_auth=False)
    yield url, handler
    server.shutdown()
    server.server_close()


@pytest.fixture
def key_file(tmp_path):
    path = tmp_path / "engine.key"
    path.write_text(API_KEY + "\n")
    return str(path)


class TestReadApiKeyFile:
    def test_reads_and_strips(self, key_file):
        assert read_api_key_file(key_file) == API_KEY

    def test_empty_path(self):
        assert read_api_key_file("") == ""

    def test_missing_file(self, tmp_path):
        assert read_api_key_file(str(tmp_path / "nope.key")) == ""

    def test_empty_file(self, tmp_path):
        path = tmp_path / "empty.key"
        path.write_text("   \n\n")
        assert read_api_key_file(str(path)) == ""

    @pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
    def test_unreadable_file(self, tmp_path):
        path = tmp_path / "locked.key"
        path.write_text(API_KEY)
        path.chmod(0o000)
        try:
            assert read_api_key_file(str(path)) == ""
        finally:
            path.chmod(0o600)

    def test_expands_user_home(self, tmp_path, monkeypatch):
        # conftest already points $HOME at a tmp dir
        home = os.path.expanduser("~")
        path = os.path.join(home, "engine.key")
        with open(path, "w") as f:
            f.write(API_KEY)
        assert read_api_key_file("~/engine.key") == API_KEY

    def test_failure_never_logs_key_material(self, tmp_path, caplog):
        path = tmp_path / "gone.key"
        with caplog.at_level(logging.DEBUG):
            read_api_key_file(str(path))
        assert API_KEY not in caplog.text


class TestConfigApiKeyFile:
    URL = "http://localhost:9999"

    def test_upsert_and_lookup(self, key_file):
        upsert_engine(self.URL, "mtplx", source="manual", api_key_file=key_file)
        assert get_api_key_file(self.URL) == key_file
        assert resolve_api_key(self.URL) == API_KEY

    def test_lookup_tolerates_trailing_slash(self, key_file):
        upsert_engine(self.URL, "mtplx", api_key_file=key_file)
        assert get_api_key_file(self.URL + "/") == key_file

    def test_unknown_url(self):
        assert get_api_key_file("http://localhost:1") == ""
        assert resolve_api_key("http://localhost:1") == ""

    def test_update_preserves_api_key_file(self, key_file):
        upsert_engine(self.URL, "mtplx", source="manual", api_key_file=key_file)
        # Re-detection updates the entry without touching the key file.
        upsert_engine(self.URL, "mtplx", version="2.0.2")
        assert get_api_key_file(self.URL) == key_file

    def test_empty_string_clears(self, key_file):
        upsert_engine(self.URL, "mtplx", api_key_file=key_file)
        upsert_engine(self.URL, "mtplx", api_key_file="")
        assert get_api_key_file(self.URL) == ""

    def test_key_itself_never_in_config(self, key_file):
        upsert_engine(self.URL, "mtplx", api_key_file=key_file)
        assert API_KEY not in json.dumps(load_config())


class TestEngineWithApiKey:
    def test_is_reachable_and_list_running(self, bearer_server):
        url, _ = bearer_server
        engine = MtplxEngine(url, api_key=API_KEY)
        assert engine.is_reachable()
        models = engine.list_running()
        assert [m.name for m in models] == ["test-model"]

    def test_generate_sends_bearer(self, bearer_server):
        url, handler = bearer_server
        engine = MtplxEngine(url, api_key=API_KEY)
        result = engine.generate("test-model", "hi", max_tokens=8)
        assert result.error == ""
        assert result.text == "Hello world"
        assert result.tokens_generated == 2
        assert any(h.get("Authorization") == f"Bearer {API_KEY}" for h in handler.seen_headers)

    def test_without_key_fails_soft(self, bearer_server):
        url, _ = bearer_server
        engine = MtplxEngine(url)
        assert not engine.is_reachable()
        assert engine.list_running() == []

    def test_wrong_key_error_never_contains_key(self, bearer_server, caplog):
        url, _ = bearer_server
        engine = MtplxEngine(url, api_key="wrong-key")
        with caplog.at_level(logging.DEBUG):
            result = engine.generate("test-model", "hi")
        assert result.error != ""
        assert "wrong-key" not in result.error
        assert "wrong-key" not in caplog.text

    def test_key_never_logged_on_success(self, bearer_server, caplog):
        url, _ = bearer_server
        engine = MtplxEngine(url, api_key=API_KEY)
        with caplog.at_level(logging.DEBUG):
            engine.is_reachable()
            engine.generate("test-model", "hi")
        assert API_KEY not in caplog.text

    def test_no_key_sends_no_auth_header(self, open_server):
        url, handler = open_server
        engine = MtplxEngine(url)
        assert engine.is_reachable()
        assert all("Authorization" not in h for h in handler.seen_headers)

    def test_no_key_calls_http_helper_without_headers_kwarg(self):
        # Keyless engines must issue requests identical to before this
        # feature existed (no headers kwarg at all).
        mock = MagicMock(return_value=({"data": []}, {}))
        with patch("asiai.engines.openai_compat.http_get_json", mock):
            MtplxEngine("http://localhost:1234").is_reachable()
        assert mock.call_args.kwargs == {}


class TestAuthenticatedDetection:
    def test_detect_engine_type_with_headers(self, bearer_server):
        url, _ = bearer_server
        engine, _version = detect_engine_type(url, headers={"Authorization": f"Bearer {API_KEY}"})
        assert engine == "mtplx"

    def test_detect_engine_type_without_headers_is_blind(self, bearer_server):
        url, _ = bearer_server
        assert detect_engine_type(url) == ("unknown", "")

    def test_detect_engines_uses_configured_key(self, bearer_server, key_file):
        url, handler = bearer_server
        upsert_engine(url, "mtplx", source="manual", api_key_file=key_file)
        found = detect_engines([url])
        assert [(u, name) for u, name, _v in found] == [(url, "mtplx")]
        assert any(h.get("Authorization") == f"Bearer {API_KEY}" for h in handler.seen_headers)

    def test_detect_engines_without_key_stays_blind(self, bearer_server):
        url, _ = bearer_server
        assert detect_engines([url]) == []

    def test_detection_never_logs_key(self, bearer_server, key_file, caplog):
        url, _ = bearer_server
        upsert_engine(url, "mtplx", source="manual", api_key_file=key_file)
        with caplog.at_level(logging.DEBUG):
            detect_engines([url])
        assert API_KEY not in caplog.text


class TestDiscoverEnginesInjectsKey:
    def test_engine_instance_gets_key_for_its_url(self, key_file):
        from asiai.cli import _discover_engines

        url = "http://localhost:9999"
        upsert_engine(url, "mtplx", source="manual", api_key_file=key_file)
        with patch(
            "asiai.engines.detect.detect_engines",
            return_value=[(url, "mtplx", ""), ("http://localhost:9998", "mtplx", "")],
        ):
            engines = _discover_engines()
        by_url = {e.base_url: e for e in engines}
        assert by_url[url].api_key == API_KEY
        # The key is bound to its URL: the other engine gets none.
        assert by_url["http://localhost:9998"].api_key == ""
