"""``asiai bench --instruct`` — instruction-following eval (deterministic).

The 4th quality pillar, distinct from ``--agentic`` (throughput/cache) and
``--code`` (dev quality). Two families, both judge-free:

* **verifiable** — IFEval-style single-turn prompts with programmatically-checkable
  instructions; reports strict/loose × prompt-level/instruction-level accuracy
  (the public-leaderboard format). See :mod:`asiai.benchmark.instruct_verifiers`.
* **research-brief** / **order-control** — a multi-step agentic task (research via
  tools → synthesise a multi-section deliverable → a secondary tool action).
  ``research-brief`` puts the deliverable first and the secondary last, surfacing a
  failure mode where a model does the tool work but returns only the secondary-step
  confirmation, skipping the primary deliverable.

JSON-only (schema ``instruct-v1``); compares across models by diffing the output.
"""

from __future__ import annotations

import re
import statistics
import time
from typing import Any

from asiai.benchmark.code_eval import ChatResult, chat
from asiai.benchmark.code_fidelity import score_constraint, score_honesty, score_scope
from asiai.benchmark.code_fidelity_scenarios import CODE_FIDELITY_SCENARIOS
from asiai.benchmark.instruct_eval_scenarios import (
    AGENTIC_SCENARIOS,
    DATASET_VERSION,
    INSTRUCT_AGENTIC_SYSTEM,
    INSTRUCT_TOOLS,
    VERIFIABLE_PROMPTS,
)
from asiai.benchmark.instruct_verifiers import evaluate_prompt
from asiai.collectors.system import collect_run_metadata

SCHEMA_VERSION = "instruct-v1"
_AGENTIC_NAMES = ("research-brief", "research-brief-deep", "order-control")
_FIDELITY_SCORERS = {
    "honesty-audit": score_honesty,
    "multi-file-scope": score_scope,
    "constraint-preservation": score_constraint,
}
_FIDELITY_NAMES = tuple(_FIDELITY_SCORERS)
ALL_SCENARIOS = ("verifiable", *_AGENTIC_NAMES, *_FIDELITY_NAMES)
DEFAULT_SCENARIOS = ("verifiable", "research-brief")


def _pct(flags: list[bool]) -> float | None:
    return round(100.0 * sum(1 for f in flags if f) / len(flags), 1) if flags else None


# --- family: verifiable (IFEval-style) ----------------------------------------


def _run_verifiable(
    base_url: str, model: str, *, repeats: int, extra_body: dict[str, Any] | None,
    timeout: int, on_progress: Any,
) -> dict[str, Any]:
    per_prompt: list[dict[str, Any]] = []
    for rep in range(repeats):
        for spec in VERIFIABLE_PROMPTS:
            res = chat(
                base_url, model, [{"role": "user", "content": spec["prompt"]}],
                max_tokens=1024, extra_body=extra_body, timeout=timeout,
            )
            scored = evaluate_prompt(res.text or "", spec["instructions"])
            per_prompt.append({
                "id": spec["id"], "repeat": rep, "error": res.error,
                "prompt_strict": scored["prompt_strict"] and res.error is None,
                "prompt_loose": scored["prompt_loose"] and res.error is None,
                "instructions": scored["instructions"],
            })
            if on_progress:
                on_progress(f"  [verifiable r{rep + 1}] {spec['id']}: "
                            f"strict={per_prompt[-1]['prompt_strict']} "
                            f"loose={per_prompt[-1]['prompt_loose']}")
    all_ins = [i for p in per_prompt for i in p["instructions"]]
    return {
        "prompts_scored": len(per_prompt),
        "instructions_scored": len(all_ins),
        "prompt_level_strict": _pct([p["prompt_strict"] for p in per_prompt]),
        "prompt_level_loose": _pct([p["prompt_loose"] for p in per_prompt]),
        "instruction_level_strict": _pct([i["strict"] for i in all_ins]),
        "instruction_level_loose": _pct([i["loose"] for i in all_ins]),
        "per_prompt": per_prompt,
    }


# --- family: agentic (research-brief / order-control) -------------------------


def _canned_search(query: str, topics: list[tuple[str, str, str]]) -> str:
    """Best-effort canned web_search result: the fact of the closest topic."""
    q = query.lower()
    best, best_score = None, 0
    for header, topic_query, fact in topics:
        words = set(re.findall(r"\w+", (header + " " + topic_query).lower()))
        score = sum(1 for w in words if len(w) > 3 and w in q)
        if score > best_score:
            best, best_score = fact, score
    if best:
        return f"Top result: {best}"
    return "Top result: (no specific finding; summarise generally)."


def _count_named_sections(text: str, headers: list[str]) -> int:
    found = 0
    for h in headers:
        name = re.escape(h.lstrip("# ").strip())
        if re.search(rf"(?im)^\s*#{{1,6}}\s*{name}\b", text):
            found += 1
    return found


_SEARCH_DONE_NUDGE = (
    "You now have findings for all topics. Stop searching and write the COMPLETE "
    "multi-section briefing as your final answer, then call save_note."
)


def _agentic_tool_messages(
    res: ChatResult, searched_before: int, n_topics: int,
    topics: list[tuple[str, str, str]],
) -> tuple[list[dict[str, Any]], int]:
    """Assistant turn + one role:tool reply per call (per-tool canned results).

    The primary loop-breaker is dropping ``web_search`` from the toolset once the
    topics are covered (see ``_run_agentic_scenario``). This nudge is a defensive
    fallback for a model that fires more than ``n_topics`` searches within a single
    turn (before the toolset can be capped): those extra searches return a prompt
    to stop and write the deliverable. Returns the messages and the updated
    cumulative search count.
    """
    tcs = res.tool_calls or []
    assistant_tcs, tool_msgs = [], []
    searched = searched_before
    for i, tc in enumerate(tcs):
        tc_id = tc.get("id") or f"call_{i}"
        name = tc.get("name") or ""
        assistant_tcs.append({
            "id": tc_id, "type": "function",
            "function": {"name": name, "arguments": tc.get("arguments_raw") or "{}"},
        })
        if name == "web_search":
            searched += 1
            if searched > n_topics:
                result = _SEARCH_DONE_NUDGE
            else:
                args = tc.get("arguments_parsed") or {}
                result = _canned_search(str(args.get("query", "")), topics)
        elif name == "save_note":
            result = "Note saved to the notes file."
        else:
            result = "OK."
        tool_msgs.append({"role": "tool", "tool_call_id": tc_id, "content": result})
    assistant = {"role": "assistant", "content": res.text or "", "tool_calls": assistant_tcs}
    return [assistant, *tool_msgs], searched


def _tools_without_search(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [t for t in tools if (t.get("function") or {}).get("name") != "web_search"]


def _run_agentic_scenario(
    base_url: str, model: str, scenario: str, *, repeats: int,
    extra_body: dict[str, Any] | None, timeout: int, on_progress: Any,
) -> dict[str, Any]:
    cfg = AGENTIC_SCENARIOS[scenario]
    prompt, topics, sections = cfg["prompt"], cfg["topics"], cfg["sections"]
    max_turns = cfg["max_turns"]
    n_sections = len(sections)
    no_search_tools = _tools_without_search(INSTRUCT_TOOLS)
    results: list[dict[str, Any]] = []
    for rep in range(repeats):
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": INSTRUCT_AGENTIC_SYSTEM},
            {"role": "user", "content": prompt},
        ]
        contents: list[str] = []
        did_secondary = False
        searched = 0
        search_capped = False
        for _ in range(max_turns):
            # Once the topics are covered, drop web_search from the toolset so the
            # model cannot loop on it — it must transition to writing the briefing
            # or to save_note. That transition is the actual failure point (a
            # finetune that won't stop searching, or that jumps straight to the
            # secondary save), not the search itself.
            capped = searched >= n_sections
            search_capped = search_capped or capped
            tools = no_search_tools if capped else INSTRUCT_TOOLS
            res = chat(base_url, model, messages, tools=tools, max_tokens=2048,
                       extra_body=extra_body, timeout=timeout)
            if res.text:
                contents.append(res.text)
            tcs = res.tool_calls or []
            if not tcs:
                break
            if any(tc.get("name") == "save_note" for tc in tcs):
                did_secondary = True
            tool_msgs, searched = _agentic_tool_messages(res, searched, n_sections, topics)
            messages.extend(tool_msgs)
        joined = "\n".join(contents)
        present = _count_named_sections(joined, sections)
        results.append({
            "sections_present": present,
            "primary_delivered": present == n_sections,
            "only_secondary": present == 0 and did_secondary,
            "did_secondary": did_secondary,
            "searches": searched,
            "search_capped": search_capped,
            "final_len": len(joined),
            "repeat": rep,
        })
        if on_progress:
            on_progress(f"  [{scenario} r{rep + 1}] sections={present}/{n_sections} "
                        f"delivered={results[-1]['primary_delivered']} "
                        f"only_secondary={results[-1]['only_secondary']} searches={searched}")
    return {
        "episodes": len(results),
        "sections_total": n_sections,
        "pct_primary_delivered": _pct([r["primary_delivered"] for r in results]),
        "pct_only_secondary": _pct([r["only_secondary"] for r in results]),
        "pct_did_secondary": _pct([r["did_secondary"] for r in results]),
        "pct_search_capped": _pct([r["search_capped"] for r in results]),
        "mean_sections_present": (
            round(statistics.fmean([r["sections_present"] for r in results]), 2)
            if results else None
        ),
        "mean_final_len": (
            round(statistics.fmean([r["final_len"] for r in results])) if results else None
        ),
        "per_episode": results,
    }


# --- family: code-fidelity (honesty-audit / multi-file-scope / constraint) ----


def _aggregate_scores(pure_scores: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate a scorer's per-prompt dicts: ``pct_<k>`` for bool keys,
    ``mean_<k>`` for numeric keys (ignoring None)."""
    if not pure_scores:
        return {}
    agg: dict[str, Any] = {}
    for k in pure_scores[0]:
        vals = [p[k] for p in pure_scores]
        if all(isinstance(v, bool) for v in vals):
            agg[f"pct_{k}"] = _pct(vals)
        elif all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
            nums = [v for v in vals if v is not None]
            agg[f"mean_{k}"] = round(statistics.fmean(nums), 3) if nums else None
    return agg


def _run_code_fidelity_scenario(
    base_url: str, model: str, scenario: str, *, repeats: int,
    extra_body: dict[str, Any] | None, timeout: int, on_progress: Any,
) -> dict[str, Any]:
    prompts = CODE_FIDELITY_SCENARIOS[scenario]
    scorer = _FIDELITY_SCORERS[scenario]
    per_prompt: list[dict[str, Any]] = []
    pure_scores: list[dict[str, Any]] = []
    for rep in range(repeats):
        for spec in prompts:
            res = chat(
                base_url, model, [{"role": "user", "content": spec["prompt"]}],
                max_tokens=1536, extra_body=extra_body, timeout=timeout,
            )
            pure = scorer(res.text or "", spec)
            pure_scores.append(pure)
            per_prompt.append({**pure, "id": spec["id"], "repeat": rep, "error": res.error})
            if on_progress:
                flags = " ".join(f"{k}={v}" for k, v in pure.items())
                on_progress(f"  [{scenario} r{rep + 1}] {spec['id']}: {flags}")
    return {
        "prompts_scored": len(per_prompt),
        **_aggregate_scores(pure_scores),
        "per_prompt": per_prompt,
    }


# --- orchestrator -------------------------------------------------------------


def run_instruct_eval(
    base_url: str,
    engine_name: str,
    model: str,
    *,
    scenarios: tuple[str, ...] | list[str] = DEFAULT_SCENARIOS,
    repeats: int = 1,
    extra_body: dict[str, Any] | None = None,
    timeout: int = 900,
    out_path: str | None = None,
    include_host: bool = False,
    engine_version: str = "",
    on_progress: Any = None,
) -> dict[str, Any]:
    """Run the requested instruction-following scenarios → ``instruct-v1`` dict.

    ``scenarios`` ⊆ {verifiable, research-brief, research-brief-deep, order-control}.
    ``verifiable`` is IFEval-style (strict/loose × prompt/instruction-level); the
    agentic scenarios score whether the primary multi-section deliverable is produced
    after the tool sequence. ``research-brief-deep`` adds topics (deeper context) and
    an elaborate secondary step, to probe depth-dependent deliverable-dropping.
    """
    started = int(time.time())
    requested = [s for s in scenarios if s in ALL_SCENARIOS]
    results: dict[str, Any] = {}

    if "verifiable" in requested:
        results["verifiable"] = _run_verifiable(
            base_url, model, repeats=repeats, extra_body=extra_body, timeout=timeout,
            on_progress=on_progress,
        )
    for scenario in _AGENTIC_NAMES:
        if scenario in requested:
            results[scenario.replace("-", "_")] = _run_agentic_scenario(
                base_url, model, scenario, repeats=repeats, extra_body=extra_body,
                timeout=timeout, on_progress=on_progress,
            )
    for scenario in _FIDELITY_NAMES:
        if scenario in requested:
            results[scenario.replace("-", "_")] = _run_code_fidelity_scenario(
                base_url, model, scenario, repeats=repeats, extra_body=extra_body,
                timeout=timeout, on_progress=on_progress,
            )

    out = {
        "schema_version": SCHEMA_VERSION,
        "dataset_version": DATASET_VERSION,
        "engine": engine_name,
        "model": model,
        "base_url": base_url,
        "started_at": started,
        "finished_at": int(time.time()),
        "scenarios": requested,
        "repeats": max(1, repeats),
        "extra_body": extra_body or {},
        "instruct_results": results,
    }
    out.update(
        collect_run_metadata(
            engine_version=engine_version, bench_mode="instruct", include_host=include_host
        )
    )
    if out_path:
        import json

        with open(out_path, "w") as f:
            json.dump(out, f, indent=2)
    return out


__all__ = ["ALL_SCENARIOS", "DEFAULT_SCENARIOS", "SCHEMA_VERSION", "run_instruct_eval"]
