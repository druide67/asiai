"""Tests for `asiai bench --instruct` (instruction-following eval, 1.12.0)."""

from __future__ import annotations

import json
from unittest.mock import patch

from asiai.benchmark.code_eval import ChatResult
from asiai.benchmark.instruct_eval import _count_named_sections, run_instruct_eval
from asiai.benchmark.instruct_eval_scenarios import (
    RESEARCH_SECTIONS,
    RESEARCH_SECTIONS_DEEP,
    VERIFIABLE_PROMPTS,
)


def _tc(name, args):
    return {
        "id": "c1",
        "name": name,
        "arguments_raw": json.dumps(args),
        "arguments_parsed": args,
        "parse_error": None,
    }


def _has_tool(messages):
    return any(m.get("role") == "tool" for m in messages)


# --- verifiable family --------------------------------------------------------


class TestVerifiableFamily:
    def test_runs_all_prompts_and_reports_metrics(self):
        # A model that answers everything in lowercase with no commas: some
        # prompts pass, others fail — we assert the run covers all prompts and
        # produces the four leaderboard metrics.
        def chat(base_url, model, messages, **kw):
            return ChatResult(
                text="here is a short lowercase answer without punctuation", finish_reason="stop"
            )

        with (
            patch("asiai.benchmark.instruct_eval.chat", side_effect=chat),
            patch("asiai.benchmark.instruct_eval.collect_run_metadata", return_value={}),
        ):
            out = run_instruct_eval("u", "e", "m", scenarios=["verifiable"])
        vf = out["instruct_results"]["verifiable"]
        assert vf["prompts_scored"] == len(VERIFIABLE_PROMPTS)
        for k in (
            "prompt_level_strict",
            "prompt_level_loose",
            "instruction_level_strict",
            "instruction_level_loose",
        ):
            assert k in vf and vf[k] is not None
        # the all_lowercase prompt should pass strict for this response
        low = next(p for p in vf["per_prompt"] if p["id"] == "lowercase")
        assert low["prompt_strict"] is True

    def test_perfect_model_scores_100(self):
        # A model that returns a response satisfying ANY instruction set is not
        # realistic; instead verify a single targeted prompt via the engine path.
        def chat(base_url, model, messages, **kw):
            return ChatResult(text="Yes", finish_reason="stop")

        with (
            patch("asiai.benchmark.instruct_eval.chat", side_effect=chat),
            patch("asiai.benchmark.instruct_eval.collect_run_metadata", return_value={}),
        ):
            out = run_instruct_eval("u", "e", "m", scenarios=["verifiable"])
        choose = next(
            p for p in out["instruct_results"]["verifiable"]["per_prompt"] if p["id"] == "choose"
        )
        assert choose["prompt_strict"] is True  # "Yes" ∈ {Yes, No}


# --- agentic family (research-brief) ------------------------------------------


def _good_chat(base_url, model, messages, **kw):
    """Researches, writes the full multi-section briefing, then saves (delivers)."""
    if not _has_tool(messages):
        briefing = "\n".join(f"{h}\nA synthesised finding." for h in RESEARCH_SECTIONS)
        return ChatResult(text=briefing, tool_calls=[_tc("save_note", {"title": "x"})])
    return ChatResult(text="Saved.", finish_reason="stop")


def _good_chat_deep(base_url, model, messages, **kw):
    """Delivers the full DEEP briefing (all topics) then saves."""
    if not _has_tool(messages):
        briefing = "\n".join(f"{h}\nA synthesised finding." for h in RESEARCH_SECTIONS_DEEP)
        return ChatResult(text=briefing, tool_calls=[_tc("save_note", {"title": "x"})])
    return ChatResult(text="Saved.", finish_reason="stop")


def _regressed_chat(base_url, model, messages, **kw):
    """Reproduces the briefing regression: searches, saves, then only confirms —
    never produces the multi-section briefing."""
    tools_done = [m for m in messages if m.get("role") == "tool"]
    if not tools_done:
        return ChatResult(text="", tool_calls=[_tc("web_search", {"query": "energy storage"})])
    if not any("Note saved" in m.get("content", "") for m in tools_done):
        return ChatResult(text="", tool_calls=[_tc("save_note", {"title": "idea"})])
    return ChatResult(
        text="Saved the most interesting item to the notes file.", finish_reason="stop"
    )


def _tool_names(kw):
    return {(t.get("function") or {}).get("name") for t in (kw.get("tools") or [])}


def _search_loop_then_save_chat(base_url, model, messages, **kw):
    """Loops on web_search while it's offered, then — once the harness caps the
    tool — jumps straight to save_note without writing the briefing (the faithful
    skip-to-secondary failure the cap is meant to surface)."""
    if "web_search" in _tool_names(kw):
        return ChatResult(text="", tool_calls=[_tc("web_search", {"query": "x"})])
    tools_done = [m for m in messages if m.get("role") == "tool"]
    if not any("Note saved" in m.get("content", "") for m in tools_done):
        return ChatResult(text="", tool_calls=[_tc("save_note", {"title": "idea"})])
    return ChatResult(text="Saved the highlight.", finish_reason="stop")


class TestAgenticScenario:
    def test_good_model_delivers(self):
        with (
            patch("asiai.benchmark.instruct_eval.chat", side_effect=_good_chat),
            patch("asiai.benchmark.instruct_eval.collect_run_metadata", return_value={}),
        ):
            out = run_instruct_eval("u", "e", "m", scenarios=["research-brief"])
        rb = out["instruct_results"]["research_brief"]
        assert rb["pct_primary_delivered"] == 100.0
        assert rb["pct_only_secondary"] == 0.0
        assert rb["pct_did_secondary"] == 100.0

    def test_regressed_model_only_secondary(self):
        with (
            patch("asiai.benchmark.instruct_eval.chat", side_effect=_regressed_chat),
            patch("asiai.benchmark.instruct_eval.collect_run_metadata", return_value={}),
        ):
            out = run_instruct_eval("u", "e", "m", scenarios=["research-brief"])
        rb = out["instruct_results"]["research_brief"]
        assert rb["pct_primary_delivered"] == 0.0
        assert rb["pct_only_secondary"] == 100.0  # did the save, skipped the briefing
        assert rb["pct_did_secondary"] == 100.0

    def test_deep_scenario_scores_all_topics(self):
        with (
            patch("asiai.benchmark.instruct_eval.chat", side_effect=_good_chat_deep),
            patch("asiai.benchmark.instruct_eval.collect_run_metadata", return_value={}),
        ):
            out = run_instruct_eval("u", "e", "m", scenarios=["research-brief-deep"])
        rb = out["instruct_results"]["research_brief_deep"]
        assert rb["sections_total"] == len(RESEARCH_SECTIONS_DEEP) == 10
        assert rb["pct_primary_delivered"] == 100.0

    def test_search_loop_is_capped_then_skips(self):
        with (
            patch("asiai.benchmark.instruct_eval.chat", side_effect=_search_loop_then_save_chat),
            patch("asiai.benchmark.instruct_eval.collect_run_metadata", return_value={}),
        ):
            out = run_instruct_eval("u", "e", "m", scenarios=["research-brief"])
        rb = out["instruct_results"]["research_brief"]
        assert rb["pct_search_capped"] == 100.0
        ep = rb["per_episode"][0]
        assert ep["searches"] == len(RESEARCH_SECTIONS)  # capped, not an unbounded loop
        assert rb["pct_primary_delivered"] == 0.0
        assert rb["pct_only_secondary"] == 100.0  # forced off search → skipped to save


class TestCountSections:
    def test_counts_named_headers(self):
        text = "## Energy\nx\n## Space\ny"
        assert _count_named_sections(text, RESEARCH_SECTIONS) == 2
        assert _count_named_sections("no headers", RESEARCH_SECTIONS) == 0


# --- loop-search (perfectionist research loop) --------------------------------


def _is_ambiguous_result(content: str) -> bool:
    c = content.lower()
    return "too short to process" in c or "no official confirmation" in c


class TestLoopSearch:
    def test_sober_model_accepts_and_delivers(self):
        # One transfer search, accepts the ambiguous result, writes the full briefing.
        full = "\n".join(f"{h}\nfinding." for h in [*RESEARCH_SECTIONS_DEEP, "## Transfer"])
        calls = {"n": 0}

        def chat(base_url, model, messages, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                return ChatResult(
                    text="",
                    tool_calls=[_tc("web_search", {"query": "Falinor transfer confirmed?"})],
                    completion_tokens=200,
                )
            return ChatResult(text=full, finish_reason="stop", completion_tokens=300)

        with (
            patch("asiai.benchmark.instruct_eval.chat", side_effect=chat),
            patch("asiai.benchmark.instruct_eval.collect_run_metadata", return_value={}),
        ):
            out = run_instruct_eval("u", "e", "m", scenarios=["loop-search-short"])
        r = out["instruct_results"]["loop_search_short"]
        assert r["pct_hit_cap"] == 0.0
        assert r["pct_accepted_ambiguous"] == 100.0
        assert r["pct_delivered"] == 100.0
        assert r["mean_loop_count"] == 1.0
        assert r["cap"] == 5

    def test_perfectionist_loops_to_cap_and_skips_deliverable(self):
        # Re-searches the transfer while web_search is offered; once the cap pulls it,
        # emits only a partial section — the faithful perfectionist failure.
        def chat(base_url, model, messages, **kw):
            names = {(t.get("function") or {}).get("name") for t in (kw.get("tools") or [])}
            if "web_search" in names:
                return ChatResult(
                    text="",
                    tool_calls=[_tc("web_search", {"query": "Falinor transfer 30 June confirmed"})],
                    completion_tokens=70,
                )
            return ChatResult(text="## Transfer\nstill checking.", finish_reason="stop")

        with (
            patch("asiai.benchmark.instruct_eval.chat", side_effect=chat),
            patch("asiai.benchmark.instruct_eval.collect_run_metadata", return_value={}),
        ):
            out = run_instruct_eval("u", "e", "m", scenarios=["loop-search-unconfirmable"])
        r = out["instruct_results"]["loop_search_unconfirmable"]
        assert r["pct_hit_cap"] == 100.0
        assert r["mean_loop_count"] == 5.0  # capped at the configured cap
        assert r["pct_accepted_ambiguous"] == 0.0
        assert r["pct_delivered"] == 0.0
        assert r["mode"] == "unconfirmable"


# --- orchestrator -------------------------------------------------------------


def test_schema_and_bench_mode():
    captured = {}

    def fake_md(**kw):
        captured.update(kw)
        return {"bench_mode": kw.get("bench_mode")}

    with (
        patch("asiai.benchmark.instruct_eval.chat", side_effect=_good_chat),
        patch("asiai.benchmark.instruct_eval.collect_run_metadata", side_effect=fake_md),
    ):
        out = run_instruct_eval("u", "e", "m", scenarios=["research-brief"], engine_version="b9430")
    assert out["schema_version"] == "instruct-v1"
    assert out["bench_mode"] == "instruct"
    assert captured["bench_mode"] == "instruct"
    assert captured["engine_version"] == "b9430"


def test_writes_output(tmp_path):
    with (
        patch("asiai.benchmark.instruct_eval.chat", side_effect=_good_chat),
        patch("asiai.benchmark.instruct_eval.collect_run_metadata", return_value={}),
    ):
        run_instruct_eval(
            "u", "e", "m", scenarios=["research-brief"], out_path=str(tmp_path / "i.json")
        )
    saved = json.loads((tmp_path / "i.json").read_text())
    assert saved["schema_version"] == "instruct-v1"
    assert "research_brief" in saved["instruct_results"]
