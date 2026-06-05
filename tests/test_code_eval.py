"""Tests for the `asiai bench --code` dev-quality eval (1.12.0).

Covers the deterministic scorers (output_gates), the chat primitive's tool-call
accumulator, the four suites (with mocked chat), the LLM-judge parsing, and the
run_code_eval orchestrator.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from asiai.benchmark import code_eval
from asiai.benchmark.code_eval import (
    ChatResult,
    _continue_messages,
    _finalize_tool_calls,
    _merge_streamed_tool_call,
    _parse_judge_json,
    _score_recovery,
    chat,
    run_code_eval,
)
from asiai.benchmark.code_eval_scenarios import TOOLCALL_TURNS, TOOLS_BY_NAME
from asiai.benchmark.output_gates import (
    first_corrective_index,
    has_think_tag_leak,
    is_empty_object_bug,
    repeats_same_call,
    schema_conform,
    score_toolcall_turn,
)

EDIT_SCHEMA = TOOLS_BY_NAME["edit_file"]
_VALID_EDIT = {"path": "a.py", "edits": [{"search": "a", "replace": "b"}]}


def _tc(name, args, *, raw=None, parse_error=None):
    """Build a tool-call dict like the client produces."""
    return {
        "id": "c1",
        "name": name,
        "arguments_raw": raw if raw is not None else json.dumps(args),
        "arguments_parsed": args if isinstance(args, dict) else None,
        "parse_error": parse_error,
    }


# --- output_gates scorers -----------------------------------------------------


class TestSchemaConform:
    def test_valid_edit_call(self):
        args = {"path": "a.py", "edits": [{"search": "x", "replace": "y"}]}
        assert schema_conform(_tc("edit_file", args), EDIT_SCHEMA) is True

    def test_wrong_inner_type(self):
        # edits items must be objects; a list of strings violates the schema.
        args = {"path": "a.py", "edits": ["not-an-object"]}
        assert schema_conform(_tc("edit_file", args), EDIT_SCHEMA) is False

    def test_missing_required(self):
        assert schema_conform(_tc("edit_file", {"path": "a.py"}), EDIT_SCHEMA) is False

    def test_parse_error_fails(self):
        tc = _tc("edit_file", None, raw="{bad", parse_error="JSONDecodeError")
        assert schema_conform(tc, EDIT_SCHEMA) is False

    def test_bool_not_integer(self):
        # run_tests.verbose is boolean; an integer-typed field must reject bool.
        sc = TOOLS_BY_NAME["search_code"]
        bad = _tc("search_code", {"pattern": "x", "max_results": True})
        assert schema_conform(bad, sc) is False


class TestEmptyObjectBug:
    def test_empty_dict_with_required(self):
        assert is_empty_object_bug(_tc("edit_file", {}), EDIT_SCHEMA) is True

    def test_empty_array_required(self):
        args = {"path": "a.py", "edits": []}
        assert is_empty_object_bug(_tc("edit_file", args), EDIT_SCHEMA) is True

    def test_stringified_empty_array(self):
        tc = _tc("edit_file", {"path": "a.py", "edits": "[]"})
        assert is_empty_object_bug(tc, EDIT_SCHEMA) is True

    def test_valid_call_no_bug(self):
        args = {"path": "a.py", "edits": [{"search": "x", "replace": "y"}]}
        assert is_empty_object_bug(_tc("edit_file", args), EDIT_SCHEMA) is False

    def test_parse_error_not_counted(self):
        # A JSON parse failure is a different category (json_valid catches it) —
        # it must NOT inflate the empty-object-bug count.
        tc = _tc("edit_file", None, raw='{"path":"a","edi', parse_error="JSONDecodeError")
        assert is_empty_object_bug(tc, EDIT_SCHEMA) is False


class TestSchemaConformEmptyArray:
    def test_empty_required_array_rejected(self):
        # edits:[] is the |items collapse — schema_conform must agree with
        # is_empty_object_bug and reject it (all([]) would otherwise pass it).
        tc = _tc("edit_file", {"path": "a.py", "edits": []})
        assert schema_conform(tc, EDIT_SCHEMA) is False
        assert is_empty_object_bug(tc, EDIT_SCHEMA) is True


class TestScoreToolcallTurn:
    def test_clean_turn(self):
        args = {"path": "a.py", "edits": [{"search": "x", "replace": "y"}]}
        res = ChatResult(tool_calls=[_tc("edit_file", args)], finish_reason="stop")
        s = score_toolcall_turn(res, "edit_file", EDIT_SCHEMA)
        assert s["emitted_tool_call"] and s["json_valid"] and s["non_truncated"]
        assert s["correct_tool"] and s["schema_conform"] and not s["empty_object_bug"]

    def test_truncated_turn(self):
        res = ChatResult(tool_calls=[_tc("edit_file", {})], finish_reason="length")
        s = score_toolcall_turn(res, "edit_file", EDIT_SCHEMA)
        assert s["non_truncated"] is False
        assert s["empty_object_bug"] is True

    def test_no_tool_call(self):
        res = ChatResult(text="sorry", tool_calls=[], finish_reason="stop")
        s = score_toolcall_turn(res, "edit_file", EDIT_SCHEMA)
        assert s["emitted_tool_call"] is False
        assert s["correct_tool"] is False


class TestThinkAndRecoveryScorers:
    def test_think_leak(self):
        assert has_think_tag_leak("<think>reasoning</think> answer") is True
        assert has_think_tag_leak("clean answer") is False

    def test_repeats_same_call(self):
        a = ChatResult(tool_calls=[_tc("run_tests", {"filter": "x"})])
        b = ChatResult(tool_calls=[_tc("run_tests", {"filter": "x"})])
        assert repeats_same_call([a, b]) is True
        c = ChatResult(tool_calls=[_tc("edit_file", {"path": "a", "edits": []})])
        assert repeats_same_call([a, c]) is False

    def test_first_corrective_index(self):
        loop = ChatResult(tool_calls=[_tc("run_tests", {"filter": "x"})])
        fix = ChatResult(tool_calls=[_tc("edit_file", _VALID_EDIT)])
        assert first_corrective_index([loop, fix]) == 2
        assert first_corrective_index([loop, loop]) is None


# --- chat primitive: streaming tool-call accumulator --------------------------


class TestContinueMessages:
    def test_single_tool_call(self):
        res = ChatResult(tool_calls=[_tc("run_tests", {"filter": "x"})])
        msgs = _continue_messages(res, "ok")
        assert msgs[0]["role"] == "assistant" and len(msgs[0]["tool_calls"]) == 1
        assert msgs[1]["role"] == "tool"
        assert msgs[1]["tool_call_id"] == msgs[0]["tool_calls"][0]["id"]

    def test_multiple_tool_calls_all_kept(self):
        # A model emitting several calls in one turn: all must be carried + each
        # gets a matching tool reply (else the next turn sees a falsified history).
        res = ChatResult(tool_calls=[
            _tc("search_code", {"pattern": "a"}),
            {"id": "c2", "name": "run_tests", "arguments_raw": "{}", "parse_error": None},
        ])
        msgs = _continue_messages(res, "ok")
        assert len(msgs[0]["tool_calls"]) == 2
        tool_msgs = [m for m in msgs if m["role"] == "tool"]
        assert len(tool_msgs) == 2
        assert {m["tool_call_id"] for m in tool_msgs} == {"c1", "c2"}

    def test_no_tool_call_is_plain_assistant(self):
        msgs = _continue_messages(ChatResult(text="hi", tool_calls=[]), "ok")
        assert msgs == [{"role": "assistant", "content": "hi"}]


class TestToolCallAccumulator:
    def test_concatenates_fragments_then_parses(self):
        acc: dict = {}
        _merge_streamed_tool_call(acc, {"index": 0, "id": "c1", "function": {"name": "edit_file"}})
        _merge_streamed_tool_call(acc, {"index": 0, "function": {"arguments": '{"path":"a",'}})
        _merge_streamed_tool_call(acc, {"index": 0, "function": {"arguments": '"edits":[]}'}})
        out = _finalize_tool_calls(acc)
        assert len(out) == 1
        assert out[0]["name"] == "edit_file"
        assert out[0]["arguments_parsed"] == {"path": "a", "edits": []}
        assert out[0]["parse_error"] is None

    def test_truncated_args_keep_raw_and_flag(self):
        acc: dict = {}
        _merge_streamed_tool_call(acc, {"index": 0, "function": {"name": "edit_file"}})
        _merge_streamed_tool_call(acc, {"index": 0, "function": {"arguments": '{"path":"a","edi'}})
        out = _finalize_tool_calls(acc)
        assert out[0]["arguments_parsed"] is None
        assert "JSONDecodeError" in out[0]["parse_error"]
        assert out[0]["arguments_raw"] == '{"path":"a","edi'  # raw kept for diagnosis

    def test_non_object_args_flagged(self):
        acc: dict = {}
        piece = {"index": 0, "function": {"name": "x", "arguments": "[1,2]"}}
        _merge_streamed_tool_call(acc, piece)
        out = _finalize_tool_calls(acc)
        assert out[0]["parse_error"] == "non_object_args:list"


class _FakeStream:
    """Minimal urlopen() context manager yielding SSE byte lines."""

    def __init__(self, chunks):
        lines = [f"data: {json.dumps(c)}".encode() for c in chunks] + [b"data: [DONE]"]
        self._buf = lines

    def __enter__(self):
        return iter(self._buf)

    def __exit__(self, *a):
        return False


def test_chat_stream_parses_tool_call():
    frag1 = {"index": 0, "id": "c1", "function": {"name": "search_code", "arguments": '{"pattern"'}}
    frag2 = {"index": 0, "function": {"arguments": ':"x"}'}}
    chunks = [
        {"choices": [{"delta": {"tool_calls": [frag1]}}]},
        {
            "choices": [{"delta": {"tool_calls": [frag2]}, "finish_reason": "tool_calls"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    ]
    target = "asiai.benchmark.code_eval.urllib.request.urlopen"
    with patch(target, return_value=_FakeStream(chunks)):
        res = chat("http://localhost:8080", "m", [{"role": "user", "content": "hi"}])
    assert res.finish_reason == "tool_calls"
    assert res.tool_calls[0]["name"] == "search_code"
    assert res.tool_calls[0]["arguments_parsed"] == {"pattern": "x"}
    assert res.completion_tokens == 5


# --- suites with mocked chat --------------------------------------------------

_VALID_ARGS = {
    "search_code": {"pattern": "parse_config"},
    "write_file": {"path": "config.py", "content": "x = 1"},
    "edit_file": {"path": "config.py", "edits": [{"search": "a", "replace": "b"}]},
    "run_tests": {"filter": "config", "verbose": True},
}
_USER_TO_TOOL = {t["user"]: t["expected_tool"] for t in TOOLCALL_TURNS}


def _clean_chat(base_url, model, messages, **kw):
    """Mock: emit a valid call for whatever tool the last user turn expects."""
    user = messages[-1]["content"]
    tool = _USER_TO_TOOL.get(user, "search_code")
    return ChatResult(tool_calls=[_tc(tool, _VALID_ARGS[tool])], finish_reason="tool_calls")


def _buggy_edit_chat(base_url, model, messages, **kw):
    """Mock: correct tool, but edit_file collapses to the empty-object bug."""
    user = messages[-1]["content"]
    tool = _USER_TO_TOOL.get(user, "search_code")
    if tool == "edit_file":
        return ChatResult(tool_calls=[_tc("edit_file", {})], finish_reason="length")
    return ChatResult(tool_calls=[_tc(tool, _VALID_ARGS[tool])], finish_reason="tool_calls")


class TestToolcallSuite:
    def test_clean_run_is_100(self):
        with patch("asiai.benchmark.code_eval.chat", side_effect=_clean_chat):
            out = code_eval._run_toolcall_suite(
                "u", "m", repeats=1, extra_body=None, timeout=1, on_progress=None
            )
        assert out["pct_clean"] == 100.0
        assert out["count_empty_object_bug"] == 0
        assert out["pct_correct_tool"] == 100.0
        assert out["turns_scored"] == len(TOOLCALL_TURNS)

    def test_empty_object_bug_counted_on_edit_turns(self):
        with patch("asiai.benchmark.code_eval.chat", side_effect=_buggy_edit_chat):
            out = code_eval._run_toolcall_suite(
                "u", "m", repeats=1, extra_body=None, timeout=1, on_progress=None
            )
        # 3 edit_file turns in the sequence, all buggy.
        assert out["count_empty_object_bug"] == 3
        assert out["edit_turns_empty_object_bug"] == 3
        assert out["edit_turns_pct_clean"] == 0.0
        assert out["pct_clean"] < 100.0


class TestRecoveryScorer:
    def test_recovered(self):
        loop = ChatResult(tool_calls=[_tc("run_tests", {"filter": "x"})])
        fix = ChatResult(tool_calls=[_tc("edit_file", _VALID_EDIT)])
        s = _score_recovery([loop, fix])
        assert s["recovered"] is True
        assert s["turns_to_recover"] == 2

    def test_looped(self):
        same = ChatResult(tool_calls=[_tc("run_tests", {"filter": "x"})])
        s = _score_recovery([same, same, same])
        assert s["recovered"] is False
        assert s["repeated_failing_call"] is True


class TestThinkingSuite:
    def test_all_pass(self):
        def good(base_url, model, messages, **kw):
            # no reasoning, clean content, not truncated
            return ChatResult(text="def f(): return 1", reasoning_text="", finish_reason="stop")

        with patch("asiai.benchmark.code_eval.chat", side_effect=good):
            out = code_eval._run_thinking_suite(
                "u", "m", repeats=1, extra_body=None, timeout=1, on_progress=None
            )
        assert out["pct_no_think_leak"] == 100.0
        assert out["pct_nonempty_short_budget"] == 100.0
        assert out["pct_thinking_off_honoured"] == 100.0

    def test_leak_and_empty_fail(self):
        def bad(base_url, model, messages, **kw):
            # leaks a think tag, empty at short budget, reasoning streamed when off
            return ChatResult(text="<think>hmm</think>", reasoning_text="r", finish_reason="length")

        with patch("asiai.benchmark.code_eval.chat", side_effect=bad):
            out = code_eval._run_thinking_suite(
                "u", "m", repeats=1, extra_body=None, timeout=1, on_progress=None
            )
        assert out["pct_no_think_leak"] == 0.0
        assert out["pct_thinking_off_honoured"] == 0.0


# --- judge --------------------------------------------------------------------


class TestJudgeParse:
    def test_parses_fenced_json(self):
        raw = '```json\n{"correctness": 4, "overall": 4, "reason": "ok"}\n```'
        parsed = _parse_judge_json(raw)
        assert parsed["correctness"] == 4
        assert parsed["overall"] == 4

    def test_returns_none_on_garbage(self):
        assert _parse_judge_json("no json here") is None


def test_coding_suite_judged():
    """coding suite generates a transcript per task then grades it via the judge."""
    from asiai.benchmark.code_eval_scenarios import CODING_TASKS

    judge_json = '{"correctness": 4, "coherence": 4, "quality": 5, "overall": 4}'

    def fake_chat(base_url, model, messages, **kw):
        if base_url == "http://judge":
            return ChatResult(text=judge_json, finish_reason="stop")
        return ChatResult(text="def code(): ...", finish_reason="stop")

    with patch("asiai.benchmark.code_eval.chat", side_effect=fake_chat):
        out = code_eval._run_coding_judged(
            "http://target", "m", tasks=CODING_TASKS, extra_body=None, timeout=1,
            judge_url="http://judge", judge_model="judge-m", judge_api_key=None,
            on_progress=None,
        )
    assert len(out["tasks"]) == len(CODING_TASKS)
    entry = out["tasks"][0]
    assert "transcript" in entry
    assert entry["judge"]["scores"]["overall"] == 4
    assert entry["judge"]["parse_ok"] is True


def test_toolcall_stress_suite_runs():
    """The stress tool-call suite runs its deeper turn-set with the same scorers."""
    from asiai.benchmark.code_eval_scenarios import STRESS_EDIT_TURNS, STRESS_TOOLCALL_TURNS

    def stress_chat(base_url, model, messages, **kw):
        user = messages[-1]["content"]
        # map the stress turn's user text to its expected tool
        tool = next((t["expected_tool"] for t in STRESS_TOOLCALL_TURNS if t["user"] == user),
                    "search_code")
        return ChatResult(tool_calls=[_tc(tool, _VALID_ARGS[tool])], finish_reason="tool_calls")

    with patch("asiai.benchmark.code_eval.chat", side_effect=stress_chat):
        out = code_eval._run_toolcall_suite(
            "u", "m", repeats=1, extra_body=None, timeout=1, on_progress=None,
            turns=STRESS_TOOLCALL_TURNS, edit_indices=STRESS_EDIT_TURNS, label="tc-stress",
        )
    assert out["turns_scored"] == len(STRESS_TOOLCALL_TURNS)
    assert out["pct_clean"] == 100.0  # valid args for every expected tool


# --- orchestrator -------------------------------------------------------------


def test_run_code_eval_schema_and_metadata():
    fake_md = {"hw_chip": "Apple M5 Max", "powermode": 2, "bench_mode": "code"}
    with (
        patch("asiai.benchmark.code_eval.chat", side_effect=_clean_chat),
        patch("asiai.benchmark.code_eval.collect_run_metadata", return_value=fake_md) as md,
    ):
        out = run_code_eval(
            "http://localhost:8080", "llamacpp", "m.gguf",
            suites=["tool-call"], engine_version="b9430",
        )
    assert out["schema_version"] == "code-v1"
    assert out["dataset_version"] == "code-v1"
    assert out["suites"] == ["tool-call"]
    assert out["hw_chip"] == "Apple M5 Max"
    assert "tool_call" in out["code_results"]
    assert "recovery" not in out["code_results"]  # not requested
    md.assert_called_once()
    assert md.call_args.kwargs["bench_mode"] == "code"


def test_run_code_eval_writes_output(tmp_path):
    with (
        patch("asiai.benchmark.code_eval.chat", side_effect=_clean_chat),
        patch("asiai.benchmark.code_eval.collect_run_metadata", return_value={}),
    ):
        out = run_code_eval(
            "u", "e", "m", suites=["tool-call"], out_path=str(tmp_path / "code.json")
        )
    saved = json.loads((tmp_path / "code.json").read_text())
    assert saved["schema_version"] == "code-v1"
    saved_clean = saved["code_results"]["tool_call"]["pct_clean"]
    out_clean = out["code_results"]["tool_call"]["pct_clean"]
    assert saved_clean == out_clean
