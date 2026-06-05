"""Deterministic output-validity gates for benchmarks.

Throughput measures how FAST an engine emits tokens, not whether the tokens are
correct. A mis-quantised model, a wrong chat template, or a thinking-loop can
stream garbage at high tok/s and score "excellent". These cheap, deterministic
checks (no extra model calls, no judge LLM) flag degenerate output so a result
below a validity threshold can be refused a ranking — fast garbage is not a win.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

# Truncate stored output text to keep result JSON compact; degeneracy is
# detectable well within this window.
MAX_STORED_TEXT = 2000

# An engine whose output passes the gates on fewer than this share of runs is
# refused a ranking by consumers (see reporter winner selection).
DEFAULT_MIN_VALID_PCT = 80.0


def truncate_text(text: str, limit: int = MAX_STORED_TEXT) -> str:
    """Clip text to ``limit`` chars for storage (degeneracy shows up early)."""
    return text if len(text) <= limit else text[:limit]


def check_degenerate(text: str, *, min_chars: int = 1) -> dict[str, object]:
    """Flag degenerate generations with cheap deterministic heuristics.

    Returns ``{"degenerate": bool, "reason": str | None}``. Detects:
      - empty / whitespace-only output (e.g. a thinking-loop that never emits
        user-facing content);
      - extreme n-gram repetition (a stuck decoding loop);
      - very low word diversity over a long output (garbage filler).
    """
    stripped = text.strip()
    if len(stripped) < min_chars:
        return {"degenerate": True, "reason": "empty"}

    words = stripped.split()
    if len(words) >= 20:
        trigrams = [tuple(words[i : i + 3]) for i in range(len(words) - 2)]
        if trigrams:
            _, count = Counter(trigrams).most_common(1)[0]
            if count / len(trigrams) > 0.3:
                return {"degenerate": True, "reason": "ngram_repetition"}
        if len(set(words)) / len(words) < 0.15:
            return {"degenerate": True, "reason": "low_diversity"}

    return {"degenerate": False, "reason": None}


_NUMBER_RE = re.compile(r"-?\d[\d,]*")


def check_arithmetic(text: str, expected: int) -> bool:
    """Exact-match a known integer answer anywhere in the output.

    Burst prompts ask for a single integer with a deterministic answer, giving
    a free correctness signal. Commas are stripped so ``12,352`` matches 12352.
    """
    for m in _NUMBER_RE.finditer(text):
        try:
            if int(m.group().replace(",", "")) == expected:
                return True
        except ValueError:
            continue
    return False


def output_valid_pct(flags: list[bool]) -> float:
    """Percentage (0.0-100.0) of runs whose output passed the gates."""
    if not flags:
        return 0.0
    return round(100.0 * sum(1 for f in flags if f) / len(flags), 1)


# ---------------------------------------------------------------------------
# Tool-call / loop / thinking-leak scorers — the deterministic core of the
# `asiai bench --code` dev-quality eval (no judge LLM). These grade tool-calling
# reliability (the |items / empty-object truncation bug), agentic error-recovery
# vs. loop, and thinking-mode discipline. A ChatResult is duck-typed here (it has
# .text / .reasoning_text / .tool_calls / .finish_reason) so the scorers stay
# importable without the chat client.
# ---------------------------------------------------------------------------

_THINK_TAG_RE = re.compile(r"</?think(?:ing)?>", re.IGNORECASE)

# JSON-schema type -> the Python type json.loads produces for it.
_JSON_PY_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


def _py_type_matches(value: Any, json_type: str) -> bool:
    """True if a parsed value matches a JSON-schema scalar/compound type.

    ``bool`` subclasses ``int`` in Python, so guard ``integer``/``number``
    against booleans explicitly (``true`` must not satisfy ``integer``).
    """
    expected = _JSON_PY_TYPES.get(json_type)
    if expected is None:
        return True  # unknown/union type — don't fail conformance on it
    if json_type in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, expected)


def _conform_value(value: Any, schema: dict[str, Any]) -> bool:
    """Recursively check one value against a (sub)schema's type + items/props."""
    jtype = schema.get("type")
    if jtype and not _py_type_matches(value, jtype):
        return False
    if jtype == "array":
        items = schema.get("items")
        if items:
            return all(_conform_value(v, items) for v in value)
    elif jtype == "object":
        props = schema.get("properties") or {}
        for req in schema.get("required") or []:
            if req not in value:
                return False
        for key, sub in props.items():
            if key in value and not _conform_value(value[key], sub):
                return False
    return True


def schema_conform(tc: dict[str, Any] | None, schema: dict[str, Any]) -> bool:
    """Hand-rolled (no jsonschema) conformance for the small tool schemas.

    Parsed args must be a dict, every ``required`` property present, each
    property's Python type matches its JSON-schema type, and nested
    ``edits``/``globs`` items conform. ``schema`` is the full tool entry
    (``{"type":"function","function":{...,"parameters":{...}}}``).
    """
    if tc is None or tc.get("parse_error") is not None:
        return False
    args = tc.get("arguments_parsed")
    if not isinstance(args, dict):
        return False
    params = (schema.get("function") or {}).get("parameters") or schema.get("parameters") or {}
    if not _conform_value(args, params):
        return False
    # A REQUIRED array that came back empty is the |items collapse, not a
    # conformant call — reject it so schema_conform agrees with is_empty_object_bug
    # (``all([])`` is vacuously True, so _conform_value alone would pass ``edits:[]``).
    props = params.get("properties") or {}
    for req in params.get("required") or []:
        if (props.get(req) or {}).get("type") == "array" and not args.get(req):
            return False
    return True


def is_empty_object_bug(tc: dict[str, Any] | None, schema: dict[str, Any]) -> bool:
    """The named ``|items`` failure: required fields collapsed to empty.

    True when args parsed to ``{}`` while the schema required fields, OR a
    required property is absent, OR a required ARRAY property came back empty /
    a stringified empty array / an empty string. This is the headline bug count.

    A parse FAILURE is a different category (caught by ``json_valid`` /
    ``non_truncated``), so it is excluded here to keep this count specific to the
    template collapse.
    """
    if tc is None or tc.get("parse_error") is not None:
        return False
    params = (schema.get("function") or {}).get("parameters") or schema.get("parameters") or {}
    required = params.get("required") or []
    props = params.get("properties") or {}
    args = tc.get("arguments_parsed")

    if not isinstance(args, dict):
        return bool(required)
    if required and args == {}:
        return True
    for req in required:
        if req not in args:
            return True
        if (props.get(req) or {}).get("type") == "array" and args[req] in ([], "[]", ""):
            return True
    return False


def score_toolcall_turn(result: Any, expected_tool: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Deterministic per-turn score for a turn that should emit a tool call."""
    tcs = getattr(result, "tool_calls", None) or []
    tc = tcs[0] if tcs else None
    return {
        "emitted_tool_call": tc is not None,
        "json_valid": tc is not None and tc.get("parse_error") is None,
        # length ⇒ args cut off mid-stream (the truncation signature).
        "non_truncated": getattr(result, "finish_reason", None) != "length",
        "correct_tool": tc is not None and tc.get("name") == expected_tool,
        "schema_conform": schema_conform(tc, schema),
        "empty_object_bug": is_empty_object_bug(tc, schema),
        "args_char_len": len(tc.get("arguments_raw", "")) if tc else 0,
    }


def has_think_tag_leak(text: str | None) -> bool:
    """True if user-facing content contains a literal <think>/<thinking> tag."""
    return bool(text) and bool(_THINK_TAG_RE.search(text))


def repeats_same_call(turns_after_error: list[Any]) -> bool:
    """True if the model re-emitted an identical (name+raw args) tool call.

    The classic agentic loop: it re-runs the exact call that just failed instead
    of correcting course. Compares the first tool call across the turns.
    """
    seen: set[tuple[str, str]] = set()
    for t in turns_after_error:
        tcs = getattr(t, "tool_calls", None) or []
        if not tcs:
            continue
        tc = tcs[0]
        key = (tc.get("name") or "", tc.get("arguments_raw") or "")
        if key in seen:
            return True
        seen.add(key)
    return False


def first_corrective_index(turns_after_error: list[Any]) -> int | None:
    """Index (1-based) of the first turn that took a corrective tool action.

    Corrective = a clean (parse_error-free) edit_file / write_file / search_code
    call. ``None`` if the model never recovered within the observed turns.
    """
    corrective = {"edit_file", "write_file", "search_code"}
    for i, t in enumerate(turns_after_error, start=1):
        tcs = getattr(t, "tool_calls", None) or []
        if tcs and tcs[0].get("name") in corrective and tcs[0].get("parse_error") is None:
            return i
    return None
