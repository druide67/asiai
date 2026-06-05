"""``asiai bench --code`` — deterministic dev-quality eval + optional LLM judge.

Measures what throughput cannot: whether a model is actually usable for agentic
coding. Four suites, three deterministic (no judge, no extra dep) and one
optional judge:

* **tool-call** (headline, deterministic) — an 8-turn agentic file-editing
  session under accumulating context. Scores tool-call emission, JSON validity,
  non-truncation, correct tool, schema conformance, and the **empty-object bug**
  (the ``|items`` template truncation that collapses ``edit_file.edits`` to
  ``{}`` / ``[]``) — the known Qwen3.6 weakness.
* **recovery** (deterministic) — inject a synthetic tool error mid-session and
  score corrective action vs. a stuck loop (re-emitting the failing call).
* **thinking** (deterministic) — thinking-mode discipline: no ``<think>`` leak
  into content, non-empty output at a short budget, and ``enable_thinking=false``
  actually honoured.
* **coding** (optional judge) — a 7-turn incremental RateLimiter task graded
  1-5 per criterion by an LLM judge at ``--judge-url`` (any OpenAI-compatible
  endpoint — a local small model or a frontier model behind a proxy; **no SDK is
  bundled**, the API key is read from the environment, never an argument).

The chat primitive mirrors ``agentic.py:_do_single_run`` (same SSE parser, same
structured-error contract) but generalises it to a full ``messages`` list and
``tools``/``tool_choice`` with a streaming ``tool_calls`` accumulator. JSON-only
output (schema ``code-v1``); no DB write. asiai benches one target at a time, so
comparing two models (e.g. *does Qwopus-35B match the 27B dense's dev quality?*)
is done by running ``--code`` on each and diffing the JSON.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from asiai.benchmark.code_eval_scenarios import (
    CODING_JUDGE_RUBRIC,
    CODING_JUDGE_SYSTEM,
    CODING_TASKS,
    DATASET_VERSION,
    HARD_CODING_TASKS,
    RECOVERY_CONTEXT_TURNS,
    RECOVERY_FIX_PROMPT,
    RECOVERY_OBSERVE_TURNS,
    RECOVERY_SYSTEM,
    RECOVERY_TOOL_ERROR,
    RECOVERY_TRIGGER_TURN,
    STRESS_EDIT_TURNS,
    STRESS_TOOLCALL_SYSTEM,
    STRESS_TOOLCALL_TURNS,
    THINKING_PROBES,
    THINKING_SYSTEM,
    TOOLCALL_EDIT_TURNS,
    TOOLCALL_SYSTEM,
    TOOLCALL_TURNS,
    TOOLS,
    TOOLS_BY_NAME,
)
from asiai.benchmark.output_gates import (
    check_degenerate,
    first_corrective_index,
    has_think_tag_leak,
    repeats_same_call,
    score_toolcall_turn,
    truncate_text,
)
from asiai.collectors.system import collect_run_metadata

SCHEMA_VERSION = "code-v1"

ALL_SUITES = ("tool-call", "tool-call-stress", "recovery", "thinking", "coding", "coding-hard")
DEFAULT_SUITES = ("tool-call", "recovery", "thinking")  # deterministic, no judge

_CORRECTIVE_TOOLS = {"edit_file", "write_file", "search_code"}
_JUDGE_CRITERIA = ("correctness", "coherence", "quality", "following", "overall")


# --- Chat primitive (messages + tools, streaming tool_calls accumulator) -----


@dataclass
class ToolCall:
    """One tool call recovered from a response.

    ``arguments_raw`` is the concatenated streaming fragments verbatim, kept even
    when ``json.loads`` fails so a truncated (``finish_reason == "length"`` mid-
    arguments) or malformed payload stays diagnosable — the whole point of the
    ``|items`` truncation hunt.
    """

    id: str | None = None
    name: str | None = None
    arguments_raw: str = ""
    arguments_parsed: dict[str, Any] | None = None
    parse_error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "arguments_raw": self.arguments_raw,
            "arguments_parsed": self.arguments_parsed,
            "parse_error": self.parse_error,
        }


@dataclass
class ChatResult:
    """Superset of what the suites need from one chat completion."""

    text: str = ""
    reasoning_text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: int | None = None
    error: str | None = None
    error_body: str | None = None


def _finalize_tool_calls(acc: dict[int, ToolCall]) -> list[dict[str, Any]]:
    """Concatenate-then-parse each accumulated tool call (keyed by index)."""
    out: list[dict[str, Any]] = []
    for idx in sorted(acc):
        tc = acc[idx]
        raw = tc.arguments_raw
        if raw.strip():
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    tc.arguments_parsed = parsed
                else:
                    tc.parse_error = f"non_object_args:{type(parsed).__name__}"
            except json.JSONDecodeError as e:
                tc.parse_error = f"JSONDecodeError: {e}"
        else:
            tc.parse_error = "empty_arguments"
        out.append(tc.as_dict())
    return out


def _merge_streamed_tool_call(acc: dict[int, ToolCall], piece: dict[str, Any]) -> None:
    """Fold one ``delta.tool_calls[]`` fragment into the accumulator.

    OpenAI-compat streaming sends ``id``/``name`` on the first fragment and the
    ``function.arguments`` in later fragments; ``index`` keys them together.
    """
    idx = piece.get("index", 0)
    tc = acc.setdefault(idx, ToolCall())
    if piece.get("id"):
        tc.id = piece["id"]
    fn = piece.get("function") or {}
    if fn.get("name"):
        tc.name = fn["name"]
    if fn.get("arguments"):
        tc.arguments_raw += fn["arguments"]


def _parse_nonstream_choice(choice: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]]]:
    msg = choice.get("message", {}) or {}
    text = msg.get("content") or ""
    reasoning = (msg.get("reasoning_content") or "") + (msg.get("reasoning") or "")
    acc: dict[int, ToolCall] = {}
    for i, raw_tc in enumerate(msg.get("tool_calls") or []):
        fn = raw_tc.get("function") or {}
        acc[i] = ToolCall(
            id=raw_tc.get("id"), name=fn.get("name"), arguments_raw=fn.get("arguments") or ""
        )
    return text, reasoning, _finalize_tool_calls(acc)


def chat(
    base_url: str,
    model: str,
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any = None,
    max_tokens: int = 1024,
    temperature: float = 0.0,
    extra_body: dict[str, Any] | None = None,
    api_key: str | None = None,
    timeout: int = 900,
    stream: bool = True,
) -> ChatResult:
    """One chat completion to an OpenAI-compat endpoint.

    ``extra_body`` is merged into the payload (caller keys win), e.g.
    ``chat_template_kwargs={"enable_thinking": False}``. ``api_key`` (judge
    endpoints only) sets a Bearer header; read it from the environment, never an
    argument. Network/HTTP/JSON failures land in ``error``/``error_body`` rather
    than raising, matching agentic.py's contract.
    """
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": stream,
    }
    if stream:
        payload["stream_options"] = {"include_usage": True}
    if tools is not None:
        payload["tools"] = tools
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice
    if extra_body:
        payload.update(extra_body)

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers=headers,
    )
    result = ChatResult()
    t0 = time.time()
    out = _chat_stream(req, timeout, result) if stream else _chat_nonstream(req, timeout, result)
    out.latency_ms = round((time.time() - t0) * 1000)
    return out


def _chat_nonstream(req: urllib.request.Request, timeout: int, result: ChatResult) -> ChatResult:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        result.error = f"HTTP {e.code}"
        result.error_body = e.read().decode("utf-8", errors="replace")[:500]
        return result
    except Exception as e:  # noqa: BLE001 — network/json/timeout grab bag
        result.error = type(e).__name__
        result.error_body = str(e)[:300]
        return result
    usage = data.get("usage") or {}
    result.prompt_tokens = usage.get("prompt_tokens")
    result.completion_tokens = usage.get("completion_tokens")
    choices = data.get("choices") or []
    if not choices:
        result.error = "no_choices"
        return result
    choice = choices[0]
    result.finish_reason = choice.get("finish_reason")
    result.text, result.reasoning_text, result.tool_calls = _parse_nonstream_choice(choice)
    return result


def _chat_stream(req: urllib.request.Request, timeout: int, result: ChatResult) -> ChatResult:
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_acc: dict[int, ToolCall] = {}
    last_usage: dict[str, Any] | None = None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                payload_str = line[len("data:") :].strip()
                if payload_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload_str)
                except json.JSONDecodeError:
                    continue
                if chunk.get("usage"):
                    last_usage = chunk["usage"]
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                choice = choices[0]
                if choice.get("finish_reason"):
                    result.finish_reason = choice["finish_reason"]
                delta = choice.get("delta", {}) or {}
                text_content = delta.get("content") or ""
                reasoning_chunk = (delta.get("reasoning_content") or "") + (
                    delta.get("reasoning") or ""
                )
                if text_content:
                    content_parts.append(text_content)
                if reasoning_chunk:
                    reasoning_parts.append(reasoning_chunk)
                for piece in delta.get("tool_calls") or []:
                    _merge_streamed_tool_call(tool_acc, piece)
    except urllib.error.HTTPError as e:
        result.error = f"HTTP {e.code}"
        result.error_body = e.read().decode("utf-8", errors="replace")[:500]
        return result
    except Exception as e:  # noqa: BLE001 — network/json/timeout grab bag
        result.error = type(e).__name__
        result.error_body = str(e)[:300]
        return result
    result.text = "".join(content_parts)
    result.reasoning_text = "".join(reasoning_parts)
    result.tool_calls = _finalize_tool_calls(tool_acc)
    if last_usage:
        result.prompt_tokens = last_usage.get("prompt_tokens")
        result.completion_tokens = last_usage.get("completion_tokens")
    return result


# --- Conversation helpers -----------------------------------------------------


def _continue_messages(res: ChatResult, tool_result: str) -> list[dict[str, Any]]:
    """Append the assistant turn + a canned tool result so the chat can go on.

    When the model emitted a tool call, the assistant message must carry
    ``tool_calls`` and be followed by a matching ``role:tool`` message (the
    OpenAI-compat tool protocol); otherwise just the assistant text.
    """
    tcs = res.tool_calls or []
    if not tcs:
        return [{"role": "assistant", "content": res.text or ""}]
    # Carry EVERY tool call (a model may emit several in one turn) so the
    # reconstructed history matches what the model actually said — dropping the
    # extras would feed it a falsified transcript on the next turn. Each call gets
    # a matching role:tool reply (the OpenAI-compat pairing requirement).
    assistant_tcs = [
        {
            "id": tc.get("id") or f"call_{i}",
            "type": "function",
            "function": {
                "name": tc.get("name") or "",
                "arguments": tc.get("arguments_raw") or "{}",
            },
        }
        for i, tc in enumerate(tcs)
    ]
    msgs: list[dict[str, Any]] = [
        {"role": "assistant", "content": res.text or "", "tool_calls": assistant_tcs}
    ]
    msgs.extend(
        {"role": "tool", "tool_call_id": atc["id"], "content": tool_result} for atc in assistant_tcs
    )
    return msgs


def _thinking_extra(base: dict[str, Any] | None, enable: bool) -> dict[str, Any]:
    """Merge ``chat_template_kwargs.enable_thinking`` into the user extra_body."""
    eb = dict(base or {})
    ctk = dict(eb.get("chat_template_kwargs") or {})
    ctk["enable_thinking"] = enable
    eb["chat_template_kwargs"] = ctk
    return eb


def _pct(flags: list[bool]) -> float | None:
    return round(100.0 * sum(1 for f in flags if f) / len(flags), 1) if flags else None


# --- Suite: tool-call (deterministic, headline) -------------------------------


def _run_toolcall_suite(
    base_url: str,
    model: str,
    *,
    repeats: int,
    extra_body: dict[str, Any] | None,
    timeout: int,
    on_progress: Any,
    turns: list[dict[str, Any]] = TOOLCALL_TURNS,
    edit_indices: list[int] = TOOLCALL_EDIT_TURNS,
    system: str = TOOLCALL_SYSTEM,
    label: str = "tool-call",
) -> dict[str, Any]:
    per_turn: list[dict[str, Any]] = []
    for rep in range(repeats):
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for idx, turn in enumerate(turns):
            messages.append({"role": "user", "content": turn["user"]})
            res = chat(
                base_url,
                model,
                messages,
                tools=TOOLS,
                max_tokens=1024,
                extra_body=extra_body,
                timeout=timeout,
            )
            schema = TOOLS_BY_NAME[turn["expected_tool"]]
            score = score_toolcall_turn(res, turn["expected_tool"], schema)
            score.update(
                {
                    "turn": idx,
                    "expected_tool": turn["expected_tool"],
                    "repeat": rep,
                    "error": res.error,
                }
            )
            per_turn.append(score)
            messages.extend(_continue_messages(res, turn["tool_result"]))
            if on_progress:
                on_progress(
                    f"  [{label} r{rep + 1} t{idx + 1}/{len(turns)}] "
                    f"{turn['expected_tool']} clean={_turn_clean(score)}"
                )
    return _summarize_toolcall(per_turn, edit_indices)


def _turn_clean(s: dict[str, Any]) -> bool:
    return bool(
        s["json_valid"]
        and s["non_truncated"]
        and s["correct_tool"]
        and s["schema_conform"]
        and not s["empty_object_bug"]
    )


def _summarize_toolcall(
    per_turn: list[dict[str, Any]], edit_indices: list[int] = TOOLCALL_EDIT_TURNS
) -> dict[str, Any]:
    n = len(per_turn)
    edits = [s for s in per_turn if s["turn"] in edit_indices]
    return {
        "turns_scored": n,
        "pct_emitted": _pct([s["emitted_tool_call"] for s in per_turn]),
        "pct_json_valid": _pct([s["json_valid"] for s in per_turn]),
        "pct_non_truncated": _pct([s["non_truncated"] for s in per_turn]),
        "pct_correct_tool": _pct([s["correct_tool"] for s in per_turn]),
        "pct_schema_conform": _pct([s["schema_conform"] for s in per_turn]),
        "count_empty_object_bug": sum(1 for s in per_turn if s["empty_object_bug"]),
        "pct_clean": _pct([_turn_clean(s) for s in per_turn]),
        # The edit_file turns are the array-of-objects truncation probe.
        "edit_turns_pct_clean": _pct([_turn_clean(s) for s in edits]),
        "edit_turns_empty_object_bug": sum(1 for s in edits if s["empty_object_bug"]),
        "per_turn": per_turn,
    }


# --- Suite: recovery (deterministic) ------------------------------------------


def _run_recovery_suite(
    base_url: str,
    model: str,
    *,
    repeats: int,
    extra_body: dict[str, Any] | None,
    timeout: int,
    on_progress: Any,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for rep in range(repeats):
        messages: list[dict[str, Any]] = [{"role": "system", "content": RECOVERY_SYSTEM}]
        for turn in RECOVERY_CONTEXT_TURNS:
            messages.append({"role": "user", "content": turn["user"]})
            res = chat(
                base_url,
                model,
                messages,
                tools=TOOLS,
                max_tokens=1024,
                extra_body=extra_body,
                timeout=timeout,
            )
            messages.extend(_continue_messages(res, turn["tool_result"]))
        # Trigger turn → run_tests, then return a synthetic tool ERROR.
        messages.append({"role": "user", "content": RECOVERY_TRIGGER_TURN["user"]})
        trig = chat(
            base_url,
            model,
            messages,
            tools=TOOLS,
            max_tokens=1024,
            extra_body=extra_body,
            timeout=timeout,
        )
        messages.extend(_continue_messages(trig, RECOVERY_TOOL_ERROR))
        messages.append({"role": "user", "content": RECOVERY_FIX_PROMPT})
        observed: list[ChatResult] = []
        for _ in range(RECOVERY_OBSERVE_TURNS):
            r = chat(
                base_url,
                model,
                messages,
                tools=TOOLS,
                max_tokens=1024,
                extra_body=extra_body,
                timeout=timeout,
            )
            observed.append(r)
            messages.extend(_continue_messages(r, "OK: applied."))
            tcs = r.tool_calls or []
            if tcs and tcs[0].get("name") in _CORRECTIVE_TOOLS and not tcs[0].get("parse_error"):
                break
        results.append(_score_recovery(observed))
        if on_progress:
            on_progress(
                f"  [recovery r{rep + 1}] recovered={results[-1]['recovered']} "
                f"looped={results[-1]['looped']}"
            )
    return _summarize_recovery(results)


def _score_recovery(observed: list[ChatResult]) -> dict[str, Any]:
    joined = "\n".join((t.text or "") + json.dumps(t.tool_calls or []) for t in observed)
    degen = check_degenerate(joined)
    corrective_idx = first_corrective_index(observed)
    return {
        "recovered": corrective_idx is not None,
        "looped": bool(degen["degenerate"]),
        "loop_reason": degen["reason"],
        "repeated_failing_call": repeats_same_call(observed),
        "turns_to_recover": corrective_idx,
        "finish_reason_seq": [t.finish_reason for t in observed],
    }


def _summarize_recovery(results: list[dict[str, Any]]) -> dict[str, Any]:
    recovered_turns = [r["turns_to_recover"] for r in results if r["turns_to_recover"]]
    return {
        "episodes": len(results),
        "pct_recovered": _pct([r["recovered"] for r in results]),
        "pct_looped": _pct([r["looped"] for r in results]),
        "pct_repeated_failing_call": _pct([r["repeated_failing_call"] for r in results]),
        "mean_turns_to_recover": (
            round(sum(recovered_turns) / len(recovered_turns), 2) if recovered_turns else None
        ),
        "per_episode": results,
    }


# --- Suite: thinking discipline (deterministic) -------------------------------


def _check_thinking(check: str, res: ChatResult) -> bool:
    if res.error is not None:
        return False
    if check == "no_think_leak":
        return not has_think_tag_leak(res.text)
    if check == "nonempty_short_budget":
        return not check_degenerate(res.text)["degenerate"]
    if check == "thinking_off_honoured":
        return res.reasoning_text == "" and res.finish_reason != "length"
    return False


def _run_thinking_suite(
    base_url: str,
    model: str,
    *,
    repeats: int,
    extra_body: dict[str, Any] | None,
    timeout: int,
    on_progress: Any,
) -> dict[str, Any]:
    probe_results: list[dict[str, Any]] = []
    for rep in range(repeats):
        for probe in THINKING_PROBES:
            eb = _thinking_extra(extra_body, probe["enable_thinking"])
            res = chat(
                base_url,
                model,
                [
                    {"role": "system", "content": THINKING_SYSTEM},
                    {"role": "user", "content": probe["user"]},
                ],
                max_tokens=probe["max_tokens"],
                extra_body=eb,
                timeout=timeout,
            )
            passed = _check_thinking(probe["check"], res)
            probe_results.append(
                {
                    "probe": probe["name"],
                    "check": probe["check"],
                    "passed": passed,
                    "repeat": rep,
                    "error": res.error,
                    "text": truncate_text(res.text or ""),
                }
            )
            if on_progress:
                on_progress(f"  [thinking r{rep + 1}] {probe['name']} pass={passed}")
    by_check = {p["check"]: [] for p in THINKING_PROBES}
    for pr in probe_results:
        by_check[pr["check"]].append(pr["passed"])
    return {
        "pct_no_think_leak": _pct(by_check.get("no_think_leak", [])),
        "pct_nonempty_short_budget": _pct(by_check.get("nonempty_short_budget", [])),
        "pct_thinking_off_honoured": _pct(by_check.get("thinking_off_honoured", [])),
        "per_probe": probe_results,
    }


# --- Suite: coding + LLM judge (optional, single-model rubric) ----------------


def _run_coding_task(
    base_url: str,
    model: str,
    task: dict[str, Any],
    *,
    extra_body: dict[str, Any] | None,
    timeout: int,
    on_progress: Any,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": task["system"]}]
    turns: list[dict[str, Any]] = []
    task_turns = task["turns"]
    for i, t in enumerate(task_turns):
        messages.append({"role": "user", "content": t})
        # 4096: the hard tasks regenerate a full module + tests on the last turn;
        # 2048 truncated the final answer (tests never emitted) for both models.
        res = chat(
            base_url, model, messages, max_tokens=4096, extra_body=extra_body, timeout=timeout
        )
        turns.append({"user": t, "assistant": res.text or "", "error": res.error})
        messages.append({"role": "assistant", "content": res.text or ""})
        if on_progress:
            on_progress(
                f"  [coding:{task['name']}] turn {i + 1}/{len(task_turns)} "
                f"({len(res.text or '')} chars{' ERROR' if res.error else ''})"
            )
    return turns


def _render_transcript(turns: list[dict[str, Any]]) -> str:
    blocks = [
        f"--- Turn {i} ---\nUSER: {t['user']}\nASSISTANT:\n{t['assistant']}"
        for i, t in enumerate(turns, start=1)
    ]
    return "\n\n".join(blocks)


def _parse_judge_json(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _judge_coding(
    turns: list[dict[str, Any]],
    *,
    judge_url: str,
    judge_model: str,
    judge_api_key: str | None,
    timeout: int,
) -> dict[str, Any]:
    user_block = f"{CODING_JUDGE_RUBRIC}\n\nTRANSCRIPT:\n{_render_transcript(turns)}"
    res = chat(
        judge_url,
        judge_model,
        [
            {"role": "system", "content": CODING_JUDGE_SYSTEM},
            {"role": "user", "content": user_block},
        ],
        max_tokens=1024,
        temperature=0.0,
        api_key=judge_api_key,
        timeout=timeout,
        stream=False,
    )
    if res.error is not None:
        return {"error": f"{res.error}: {res.error_body}", "judge_model": judge_model}
    parsed = _parse_judge_json(res.text)
    scores = (
        {c: parsed.get(c) for c in _JUDGE_CRITERIA if isinstance(parsed.get(c), (int, float))}
        if parsed
        else {}
    )
    return {
        "judge_model": judge_model,
        "scores": scores,
        "reason": (parsed or {}).get("reason"),
        "raw": truncate_text(res.text or ""),
        "parse_ok": parsed is not None,
    }


def _run_coding_judged(
    base_url: str,
    model: str,
    *,
    tasks: list[dict[str, Any]],
    extra_body: dict[str, Any] | None,
    timeout: int,
    judge_url: str | None,
    judge_model: str | None,
    judge_api_key: str | None,
    on_progress: Any,
) -> dict[str, Any]:
    """Run each coding task → transcript, optionally judged via ``judge_url``.

    When no ``judge_url`` is given the transcripts are still captured (schema
    ``code-v1`` stores them), so an external judge — including a human or a
    frontier model reading the JSON — can grade them after the fact.
    """
    task_results: list[dict[str, Any]] = []
    for task in tasks:
        transcript = _run_coding_task(
            base_url,
            model,
            task,
            extra_body=extra_body,
            timeout=timeout,
            on_progress=on_progress,
        )
        entry: dict[str, Any] = {"task": task["name"], "transcript": transcript}
        if judge_url and judge_model:
            if on_progress:
                on_progress(f"  [coding:{task['name']}] judging via {judge_model} @ {judge_url}")
            entry["judge"] = _judge_coding(
                transcript,
                judge_url=judge_url,
                judge_model=judge_model,
                judge_api_key=judge_api_key,
                timeout=timeout,
            )
        else:
            entry["judge"] = {"skipped": "no --judge-url (transcript captured for offline judging)"}
        task_results.append(entry)
    return {"tasks": task_results}


# --- Orchestrator -------------------------------------------------------------


def run_code_eval(
    base_url: str,
    engine_name: str,
    model: str,
    *,
    suites: tuple[str, ...] | list[str] = DEFAULT_SUITES,
    repeats: int = 1,
    extra_body: dict[str, Any] | None = None,
    judge_url: str | None = None,
    judge_model: str | None = None,
    judge_api_key: str | None = None,
    timeout: int = 900,
    out_path: str | None = None,
    include_host: bool = False,
    engine_version: str = "",
    on_progress: Any = None,
) -> dict[str, Any]:
    """Run the requested dev-quality suites against ``base_url`` → ``code-v1`` dict.

    ``suites`` ⊆ {tool-call, tool-call-stress, recovery, thinking, coding,
    coding-hard}. The tool-call/recovery/thinking suites are deterministic (no
    judge); ``tool-call-stress`` is the harder tool-call variant (deeper context,
    bigger nested arrays, escaping) used to departage models that ace the
    baseline. ``coding``/``coding-hard`` generate transcripts and, when
    ``judge_url``/``judge_model`` are given, grade them 1-5 per criterion via that
    OpenAI-compat endpoint (otherwise transcripts are captured for offline
    judging). ``repeats`` repeats the deterministic suites for variance.
    """
    started = int(time.time())
    code_results: dict[str, Any] = {}
    requested = [s for s in suites if s in ALL_SUITES]

    if "tool-call" in requested:
        code_results["tool_call"] = _run_toolcall_suite(
            base_url,
            model,
            repeats=repeats,
            extra_body=extra_body,
            timeout=timeout,
            on_progress=on_progress,
        )
    if "tool-call-stress" in requested:
        code_results["tool_call_stress"] = _run_toolcall_suite(
            base_url,
            model,
            repeats=repeats,
            extra_body=extra_body,
            timeout=timeout,
            on_progress=on_progress,
            turns=STRESS_TOOLCALL_TURNS,
            edit_indices=STRESS_EDIT_TURNS,
            system=STRESS_TOOLCALL_SYSTEM,
            label="tool-call-stress",
        )
    if "recovery" in requested:
        code_results["recovery"] = _run_recovery_suite(
            base_url,
            model,
            repeats=repeats,
            extra_body=extra_body,
            timeout=timeout,
            on_progress=on_progress,
        )
    if "thinking" in requested:
        code_results["thinking"] = _run_thinking_suite(
            base_url,
            model,
            repeats=repeats,
            extra_body=extra_body,
            timeout=timeout,
            on_progress=on_progress,
        )
    if "coding" in requested:
        code_results["coding"] = _run_coding_judged(
            base_url,
            model,
            tasks=CODING_TASKS,
            extra_body=extra_body,
            timeout=timeout,
            judge_url=judge_url,
            judge_model=judge_model,
            judge_api_key=judge_api_key,
            on_progress=on_progress,
        )
    if "coding-hard" in requested:
        code_results["coding_hard"] = _run_coding_judged(
            base_url,
            model,
            tasks=HARD_CODING_TASKS,
            extra_body=extra_body,
            timeout=timeout,
            judge_url=judge_url,
            judge_model=judge_model,
            judge_api_key=judge_api_key,
            on_progress=on_progress,
        )

    out = {
        "schema_version": SCHEMA_VERSION,
        "dataset_version": DATASET_VERSION,
        "engine": engine_name,
        "model": model,
        "base_url": base_url,
        "started_at": started,
        "finished_at": int(time.time()),
        "suites": requested,
        "repeats": max(1, repeats),
        "extra_body": extra_body or {},
        "code_results": code_results,
    }
    out.update(
        collect_run_metadata(
            engine_version=engine_version, bench_mode="code", include_host=include_host
        )
    )
    if out_path:
        with open(out_path, "w") as f:
            json.dump(out, f, indent=2)
    return out


__all__ = [
    "ALL_SUITES",
    "DEFAULT_SUITES",
    "SCHEMA_VERSION",
    "ChatResult",
    "ToolCall",
    "chat",
    "run_code_eval",
]
