"""Unit tests for the fleet poll module."""

from __future__ import annotations

import urllib.error
from io import BytesIO
from unittest.mock import patch

from asiai.fleet.poll import (
    DEFAULT_TIMEOUT,
    ERROR_HTTP_4XX,
    ERROR_HTTP_5XX,
    ERROR_PARSE,
    ERROR_REFUSED,
    ERROR_TIMEOUT,
    ERROR_UNSUPPORTED_SCHEME,
    NodePoll,
    classify_error,
    poll_all,
    poll_one,
)


def _fake_resp(body: bytes):
    """Return a context-manager mock yielding the given body when read()."""

    class FakeResp:
        def read(self, size: int = -1) -> bytes:
            return body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    return FakeResp()


class TestPollOne:
    def test_success_returns_snapshot(self):
        body = b'{"engines": [{"name": "ollama", "running": true}], "system": {}}'
        with patch("urllib.request.urlopen", return_value=_fake_resp(body)):
            r = poll_one("alpha", "http://192.0.2.1:8899")
        assert r.ok is True
        assert r.snapshot == {
            "engines": [{"name": "ollama", "running": True}],
            "system": {},
        }
        assert r.error is None
        assert r.nickname == "alpha"
        assert r.latency_ms >= 0
        assert r.reached_at > 0

    def test_http_error_returns_status_code(self):
        err = urllib.error.HTTPError(
            url="http://192.0.2.1:8899/api/v1/snapshot",
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=BytesIO(b"overloaded"),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            r = poll_one("alpha", "http://192.0.2.1:8899")
        assert r.ok is False
        assert r.error == "HTTP 503"
        assert r.snapshot is None

    def test_timeout_captured_as_typename(self):
        with patch("urllib.request.urlopen", side_effect=TimeoutError("read timed out")):
            r = poll_one("alpha", "http://192.0.2.1:8899")
        assert r.ok is False
        assert r.error == "TimeoutError"

    def test_malformed_json_returns_error(self):
        with patch("urllib.request.urlopen", return_value=_fake_resp(b"not json{")):
            r = poll_one("alpha", "http://192.0.2.1:8899")
        assert r.ok is False
        # json.JSONDecodeError is a subclass; type name is "JSONDecodeError"
        assert "JSONDecodeError" in r.error or "decode" in r.error.lower()

    def test_non_dict_body_returns_error(self):
        with patch("urllib.request.urlopen", return_value=_fake_resp(b"[1,2,3]")):
            r = poll_one("alpha", "http://192.0.2.1:8899")
        assert r.ok is False
        assert "JSON object" in r.error

    def test_oversize_response_rejected(self):
        from asiai.fleet.poll import _MAX_RESPONSE_BYTES

        class BigResp:
            def read(self, size: int = -1) -> bytes:
                return b"x" * (_MAX_RESPONSE_BYTES + 1)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with patch("urllib.request.urlopen", return_value=BigResp()):
            r = poll_one("alpha", "http://192.0.2.1:8899")
        assert r.ok is False
        assert "exceeded" in r.error

    def test_file_scheme_rejected_defense_in_depth(self):
        # A hand-edited fleet.json could smuggle file:// past upsert_node.
        # poll_one must refuse to resolve it.
        r = poll_one("evil", "file:///etc/passwd")
        assert r.ok is False
        assert "unsupported URL scheme" in r.error

    def test_ftp_scheme_rejected_defense_in_depth(self):
        r = poll_one("evil", "ftp://ftp.example.com/")
        assert r.ok is False
        assert "unsupported URL scheme" in r.error

    def test_trailing_slash_in_url_handled(self):
        body = b'{"engines": []}'
        captured: dict = {}

        def _capture(req, timeout=None):
            captured["url"] = req.full_url
            return _fake_resp(body)

        with patch("urllib.request.urlopen", side_effect=_capture):
            poll_one("alpha", "http://192.0.2.1:8899/")
        assert captured["url"] == "http://192.0.2.1:8899/api/v1/snapshot"


class TestPollAll:
    def test_empty_node_list_returns_empty(self):
        assert poll_all([]) == []

    def test_all_success(self):
        body = b'{"engines": []}'
        with patch("urllib.request.urlopen", return_value=_fake_resp(body)):
            results = poll_all(
                [
                    {"nickname": "a", "asiai_url": "http://192.0.2.1:8899"},
                    {"nickname": "b", "asiai_url": "http://192.0.2.2:8899"},
                ]
            )
        assert len(results) == 2
        assert all(r.ok for r in results)
        # Order preserved
        assert results[0].nickname == "a"
        assert results[1].nickname == "b"

    def test_mixed_ok_and_error(self):
        def _side_effect(req, timeout=None):
            if "192.0.2.2" in req.full_url:
                raise TimeoutError("slow")
            return _fake_resp(b'{"engines": []}')

        with patch("urllib.request.urlopen", side_effect=_side_effect):
            results = poll_all(
                [
                    {"nickname": "ok-node", "asiai_url": "http://192.0.2.1:8899"},
                    {"nickname": "down-node", "asiai_url": "http://192.0.2.2:8899"},
                ]
            )
        by_nick = {r.nickname: r for r in results}
        assert by_nick["ok-node"].ok is True
        assert by_nick["down-node"].ok is False
        assert by_nick["down-node"].error == "TimeoutError"

    def test_all_down(self):
        with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("refused")):
            results = poll_all(
                [
                    {"nickname": "a", "asiai_url": "http://192.0.2.1:8899"},
                    {"nickname": "b", "asiai_url": "http://192.0.2.2:8899"},
                ]
            )
        assert all(not r.ok for r in results)
        assert all(r.error == "ConnectionRefusedError" for r in results)

    def test_node_dict_to_dict_serializable(self):
        body = b'{"engines": []}'
        with patch("urllib.request.urlopen", return_value=_fake_resp(body)):
            r = poll_one("alpha", "http://192.0.2.1:8899")
        d = r.to_dict()
        assert d["nickname"] == "alpha"
        assert d["ok"] is True
        assert "snapshot" in d
        # Must be JSON-serializable
        import json as _json

        _json.dumps(d)

    def test_node_missing_url_returns_error_not_crash(self):
        results = poll_all([{"nickname": "broken", "asiai_url": ""}])
        # poll_one with empty URL will fail at urllib parse stage
        assert len(results) == 1
        assert results[0].ok is False


class TestClassifyError:
    def test_timeout_variants(self):
        assert classify_error("TimeoutError") == ERROR_TIMEOUT
        assert classify_error("socket.timeout") == ERROR_TIMEOUT

    def test_refused(self):
        assert classify_error("ConnectionRefusedError") == ERROR_REFUSED

    def test_http_status_4xx(self):
        assert classify_error("", http_status=404) == ERROR_HTTP_4XX

    def test_http_status_5xx(self):
        assert classify_error("", http_status=503) == ERROR_HTTP_5XX

    def test_parse(self):
        assert classify_error("JSONDecodeError") == ERROR_PARSE


class TestErrorClassFieldPopulated:
    def test_timeout_yields_timeout_class(self):
        with patch("urllib.request.urlopen", side_effect=TimeoutError("slow")):
            r = poll_one("a", "http://192.0.2.1:8899")
        assert r.error_class == ERROR_TIMEOUT

    def test_unsupported_scheme_yields_scheme_class(self):
        r = poll_one("a", "file:///etc/passwd")
        assert r.error_class == ERROR_UNSUPPORTED_SCHEME

    def test_ok_call_has_no_error_class(self):
        body = b'{"engines_status": []}'
        with patch("urllib.request.urlopen", return_value=_fake_resp(body)):
            r = poll_one("a", "http://192.0.2.1:8899")
        assert r.error_class is None


class TestNodePollDataclass:
    def test_default_timeout_constant(self):
        assert DEFAULT_TIMEOUT == 5.0

    def test_to_dict_includes_all_fields(self):
        p = NodePoll(
            nickname="x",
            url="http://192.0.2.1:8899",
            ok=True,
            latency_ms=12.3,
            snapshot={"k": "v"},
            error=None,
            reached_at=1234567890,
        )
        d = p.to_dict()
        assert set(d.keys()) == {
            "nickname",
            "url",
            "ok",
            "latency_ms",
            "snapshot",
            "error",
            "reached_at",
            "error_class",
        }
