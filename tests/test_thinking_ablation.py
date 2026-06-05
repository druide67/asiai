"""Tests for `asiai bench --thinking-ablation` (enable/preserve trade-off)."""

from __future__ import annotations

from unittest.mock import patch

from asiai.benchmark.code_eval import ChatResult
from asiai.benchmark.code_eval_scenarios import STRESS_TOOLCALL_TURNS
from asiai.benchmark.thinking_ablation import (
    _ablation_extra,
    _continue_with_reasoning,
    run_thinking_ablation,
)


def _tc(name="search_code"):
    return {"id": "c1", "name": name, "arguments_raw": '{"pattern":"x"}',
            "arguments_parsed": {"pattern": "x"}, "parse_error": None}


def test_ablation_extra_sets_flags():
    eb = _ablation_extra(None, True, False)
    assert eb["chat_template_kwargs"]["enable_thinking"] is True
    assert eb["chat_template_kwargs"]["preserve_thinking"] is False
    # preserve None → flag not sent (moot when no reasoning generated)
    eb2 = _ablation_extra(None, False, None)
    assert eb2["chat_template_kwargs"]["enable_thinking"] is False
    assert "preserve_thinking" not in eb2["chat_template_kwargs"]


def test_continue_carries_reasoning_into_history():
    res = ChatResult(text="ok", reasoning_text="because reasons", tool_calls=[])
    assert _continue_with_reasoning(res, "tool ok")[0]["reasoning_content"] == "because reasons"
    res2 = ChatResult(text="ok", reasoning_text="", tool_calls=[])
    assert "reasoning_content" not in _continue_with_reasoning(res2, "x")[0]


def _responder(base_url, model, messages, **kw):
    # reasoning only when enable_thinking is on (mirrors a real engine)
    eb = kw.get("extra_body") or {}
    enable = (eb.get("chat_template_kwargs") or {}).get("enable_thinking")
    return ChatResult(
        text="", reasoning_text=("thinking..." if enable else ""),
        tool_calls=[_tc()], finish_reason="tool_calls",
        prompt_tokens=100, completion_tokens=20, latency_ms=50,
    )


class TestRun:
    def _run(self):
        with (
            patch("asiai.benchmark.thinking_ablation.chat", side_effect=_responder),
            patch("asiai.benchmark.thinking_ablation.collect_run_metadata", return_value={}),
        ):
            return run_thinking_ablation("u", "e", "m")

    def test_three_cells_with_metrics(self):
        out = self._run()
        assert out["schema_version"] == "thinking-ablation-v1"
        cells = {c["config"]: c for c in out["cells"]}
        assert set(cells) == {"enable-off", "enable-on-preserve-on", "enable-on-preserve-off"}
        for c in cells.values():
            assert c["turns"] == len(STRESS_TOOLCALL_TURNS)
            for k in ("pct_clean", "latency_ms_mean", "ctx_tokens_first_turn",
                      "ctx_tokens_last_turn", "reasoning_chars_mean"):
                assert k in c

    def test_reasoning_only_when_enabled(self):
        cells = {c["config"]: c for c in self._run()["cells"]}
        assert cells["enable-off"]["reasoning_chars_mean"] == 0
        assert cells["enable-on-preserve-on"]["reasoning_chars_mean"] > 0
        assert cells["enable-on-preserve-off"]["reasoning_chars_mean"] > 0

    def test_writes_output(self, tmp_path):
        import json

        with (
            patch("asiai.benchmark.thinking_ablation.chat", side_effect=_responder),
            patch("asiai.benchmark.thinking_ablation.collect_run_metadata", return_value={}),
        ):
            run_thinking_ablation("u", "e", "m", out_path=str(tmp_path / "a.json"))
        saved = json.loads((tmp_path / "a.json").read_text())
        assert saved["schema_version"] == "thinking-ablation-v1"
        assert len(saved["cells"]) == 3
