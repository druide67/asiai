"""Integration tests for the code-fidelity family wired into run_instruct_eval."""

from __future__ import annotations

from unittest.mock import patch

from asiai.benchmark.code_eval import ChatResult
from asiai.benchmark.instruct_eval import ALL_SCENARIOS, run_instruct_eval


def _run(scenario, responder):
    with (
        patch("asiai.benchmark.instruct_eval.chat", side_effect=responder),
        patch("asiai.benchmark.instruct_eval.collect_run_metadata", return_value={}),
    ):
        out = run_instruct_eval("u", "e", "m", scenarios=[scenario])
    return out["instruct_results"][scenario.replace("-", "_")]


def test_scenarios_registered():
    for s in ("honesty-audit", "multi-file-scope", "constraint-preservation"):
        assert s in ALL_SCENARIOS


class TestHonestyWired:
    def test_diligent_model_applies_edits(self):
        # answers each honesty prompt with the required tokens present
        def chat(base_url, model, messages, **kw):
            return ChatResult(text=(
                "```python\n"
                "def fetchUserProfile(uid): return db.get(uid)\n"
                "fetchUserProfile(1); fetchUserProfile(2)\n"
                "x = {'ltt_access_token': t, 'ltt_access_token': t}\n"
                "def handle(payload):\n    return process(payload)\n"
                "```"), finish_reason="stop")
        block = _run("honesty-audit", chat)
        assert "pct_applied" in block and "pct_honest" in block and "pct_false_claim" in block
        assert block["prompts_scored"] == 3

    def test_false_claimer_is_caught(self):
        # claims completion but never changes anything (F3)
        def chat(base_url, model, messages, **kw):
            return ChatResult(text="Done, I renamed everything.\n```python\n"
                              "def getUserData(uid): return db.get(uid)\n```",
                              finish_reason="stop")
        block = _run("honesty-audit", chat)
        assert block["pct_applied"] == 0.0
        assert block["pct_false_claim"] == 100.0   # claimed but not applied
        assert block["pct_honest"] == 0.0


class TestScopeWired:
    def test_partial_scope_lowers_coverage(self):
        # only ever emits one converted site → incomplete on the 3-site prompt
        def chat(base_url, model, messages, **kw):
            return ChatResult(text="```python\ncontains([ulid])\n```", finish_reason="stop")
        block = _run("multi-file-scope", chat)
        assert "mean_coverage" in block and "pct_complete" in block
        assert block["pct_complete"] == 0.0  # never covers all sites


class TestConstraintWired:
    def test_metrics_present(self):
        def chat(base_url, model, messages, **kw):
            return ChatResult(text="```jsx\nconst v = props.value;\n"
                              "const [p] = useState(v);\nreturn 0.0;\n```",
                              finish_reason="stop")
        block = _run("constraint-preservation", chat)
        for k in ("pct_bug_fixed", "pct_constraint_preserved", "pct_both",
                  "pct_broke_constraint"):
            assert k in block
