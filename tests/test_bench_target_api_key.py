"""Target api_key threading through the raw-HTTP bench paths.

The engine adapters have carried per-engine Bearer auth since the
``api_key_file`` config field landed, but the bench suites talk to the target
with raw ``urllib``/``chat()`` calls that bypassed the adapters. These tests
pin the contract: every suite forwards the resolved target key to every
request it makes, the judge keeps its own separate key, and a keyless engine
produces byte-identical unauthenticated requests.
"""

from __future__ import annotations

import io
import json
import urllib.request
from unittest.mock import patch

from asiai.benchmark import agentic, auto_restart, burst, quality_gates
from asiai.benchmark.code_eval import ChatResult, run_code_eval
from asiai.benchmark.instruct_eval import run_instruct_eval
from asiai.benchmark.language_eval import run_language_eval
from asiai.benchmark.thinking_ablation import run_thinking_ablation

TARGET_KEY = "sk-target-key-do-not-log"
JUDGE_KEY = "sk-judge-key-do-not-log"


def _plain_chat(base_url, model, messages, **kw):
    return ChatResult(text="ok", finish_reason="stop")


def _target_keys(mock) -> set:
    return {c.kwargs.get("api_key") for c in mock.call_args_list}


# --- suites built on code_eval.chat() ------------------------------------------


class TestChatSuitesForwardTargetKey:
    def test_run_code_eval_deterministic_suites(self):
        with patch("asiai.benchmark.code_eval.chat", side_effect=_plain_chat) as m:
            run_code_eval(
                "http://t:1",
                "llamacpp",
                "m",
                suites=["tool-call", "recovery", "thinking"],
                api_key=TARGET_KEY,
            )
        assert m.call_args_list, "suites made no chat calls"
        assert _target_keys(m) == {TARGET_KEY}

    def test_run_code_eval_judge_key_stays_separate(self):
        with patch("asiai.benchmark.code_eval.chat", side_effect=_plain_chat) as m:
            run_code_eval(
                "http://t:1",
                "llamacpp",
                "m",
                suites=["coding"],
                judge_url="http://j:2",
                judge_model="judge",
                judge_api_key=JUDGE_KEY,
                api_key=TARGET_KEY,
            )
        by_url = {}
        for c in m.call_args_list:
            by_url.setdefault(c.args[0], set()).add(c.kwargs.get("api_key"))
        assert by_url["http://t:1"] == {TARGET_KEY}
        assert by_url["http://j:2"] == {JUDGE_KEY}

    def test_run_instruct_eval(self):
        with patch("asiai.benchmark.instruct_eval.chat", side_effect=_plain_chat) as m:
            run_instruct_eval(
                "http://t:1", "llamacpp", "m", scenarios=["verifiable"], api_key=TARGET_KEY
            )
        assert m.call_args_list
        assert _target_keys(m) == {TARGET_KEY}

    def test_run_language_eval(self):
        with patch("asiai.benchmark.language_eval.chat", side_effect=_plain_chat) as m:
            run_language_eval(
                "http://t:1",
                "llamacpp",
                "m",
                language="fr",
                suites=["adherence", "diacritics"],
                api_key=TARGET_KEY,
            )
        assert m.call_args_list
        assert _target_keys(m) == {TARGET_KEY}

    def test_run_thinking_ablation(self):
        with patch("asiai.benchmark.thinking_ablation.chat", side_effect=_plain_chat) as m:
            run_thinking_ablation("http://t:1", "llamacpp", "m", api_key=TARGET_KEY)
        assert m.call_args_list
        assert _target_keys(m) == {TARGET_KEY}

    def test_no_key_means_no_key_forwarded(self):
        with patch("asiai.benchmark.code_eval.chat", side_effect=_plain_chat) as m:
            run_code_eval("http://t:1", "llamacpp", "m", suites=["thinking"])
        assert _target_keys(m) == {None}


# --- raw-urllib paths (agentic, burst, probes) ----------------------------------


class _FakeResp(io.BytesIO):
    """Minimal urlopen() stand-in: context manager + iterable + .read()."""

    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _sse_done() -> _FakeResp:
    return _FakeResp(b"data: [DONE]\n")


def _auth_of(urlopen_mock, call_index: int = 0) -> str | None:
    req = urlopen_mock.call_args_list[call_index].args[0]
    assert isinstance(req, urllib.request.Request)
    return req.get_header("Authorization")


class TestRawUrllibPathsForwardTargetKey:
    def test_agentic_single_run_sets_bearer(self):
        with patch("asiai.benchmark.agentic.urllib.request.urlopen", return_value=_sse_done()) as m:
            agentic._do_single_run(
                "http://t:1", "m", "phase", "sys", "user", 16, timeout=1, api_key=TARGET_KEY
            )
        assert _auth_of(m) == f"Bearer {TARGET_KEY}"

    def test_agentic_single_run_no_key_no_header(self):
        with patch("asiai.benchmark.agentic.urllib.request.urlopen", return_value=_sse_done()) as m:
            agentic._do_single_run("http://t:1", "m", "phase", "sys", "user", 16, timeout=1)
        assert _auth_of(m) is None

    def test_burst_call_sets_bearer(self):
        body = json.dumps(
            {"usage": {"completion_tokens": 1}, "choices": [{"message": {"content": "4"}}]}
        ).encode()
        with patch(
            "asiai.benchmark.burst.urllib.request.urlopen", return_value=_FakeResp(body)
        ) as m:
            burst._do_one_call(
                "http://t:1", "m", "sys", "user", 0, 16, 1, stream=False, api_key=TARGET_KEY
            )
        assert _auth_of(m) == f"Bearer {TARGET_KEY}"

    def test_run_burst_threads_key_through_pool_submit(self):
        """End-to-end through run_burst → _run_one_burst_pass → pool.submit:
        _do_one_call takes 10 positional args there — a future param insertion
        would silently shift api_key; this pins the whole chain."""
        body = json.dumps(
            {"usage": {"completion_tokens": 1}, "choices": [{"message": {"content": "4"}}]}
        ).encode()
        with patch(
            "asiai.benchmark.burst.urllib.request.urlopen",
            side_effect=lambda *a, **kw: _FakeResp(body),
        ) as m:
            burst.run_burst(
                base_url="http://t:1",
                engine="llamacpp",
                model="m",
                burst_sizes=(1,),
                pause_between_sizes=0,
                max_tokens=16,
                timeout=5,
                stream=False,
                api_key=TARGET_KEY,
            )
        assert m.call_args_list
        for i in range(len(m.call_args_list)):
            assert _auth_of(m, i) == f"Bearer {TARGET_KEY}"

    def test_burst_call_no_key_no_header(self):
        body = json.dumps({"usage": {}, "choices": [{"message": {"content": "4"}}]}).encode()
        with patch(
            "asiai.benchmark.burst.urllib.request.urlopen", return_value=_FakeResp(body)
        ) as m:
            burst._do_one_call("http://t:1", "m", "sys", "user", 0, 16, 1, stream=False)
        assert _auth_of(m) is None

    def test_kv_metrics_probe_sends_headers(self):
        with patch(
            "asiai.benchmark.quality_gates.urllib.request.urlopen",
            return_value=_FakeResp(b"llamacpp:kv_cache_tokens 42\n"),
        ) as m:
            out = quality_gates.read_kv_cache_tokens(
                "http://t:1", headers={"Authorization": f"Bearer {TARGET_KEY}"}
            )
        assert out == 42
        assert _auth_of(m) == f"Bearer {TARGET_KEY}"

    def test_kv_slots_sampler_sends_headers(self):
        sampler = quality_gates.KVCacheSampler(
            "http://t:1", headers={"Authorization": f"Bearer {TARGET_KEY}"}
        )
        with patch(
            "asiai.benchmark.quality_gates.urllib.request.urlopen",
            return_value=_FakeResp(b"[]"),
        ) as m:
            sampler._poll_once()
        assert _auth_of(m) == f"Bearer {TARGET_KEY}"

    def test_wait_healthy_sends_headers(self):
        with patch(
            "asiai.benchmark.auto_restart.urllib.request.urlopen", return_value=_FakeResp(b"ok")
        ) as m:
            ok = auto_restart._wait_healthy(
                "http://t:1", timeout=1, headers={"Authorization": f"Bearer {TARGET_KEY}"}
            )
        assert ok is True
        assert _auth_of(m) == f"Bearer {TARGET_KEY}"
