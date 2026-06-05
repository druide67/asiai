"""Versioned dataset for the ``asiai bench --code`` dev-quality eval.

Everything the suites consume — tool schemas, the tool-call turn sequence, the
error-recovery scenario, the multi-turn coding task, the thinking probes — lives
here AS DATA so the eval set is reproducible and diffable. The schemas are chosen
to stress the known Qwen3.6 weaknesses: ``edit_file.edits`` is the array-of-
objects that triggers the ``|items`` template truncation / empty-object bug;
``search_code.globs`` is an array-of-strings; ``run_tests.verbose`` is the
boolean some templates stringify.
"""

from __future__ import annotations

DATASET_VERSION = "code-v1"

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with the given content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Apply a list of search/replace edits to a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "edits": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "search": {"type": "string"},
                                "replace": {"type": "string"},
                            },
                            "required": ["search", "replace"],
                        },
                    },
                },
                "required": ["path", "edits"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search the repo for a regex; returns matching files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "globs": {"type": "array", "items": {"type": "string"}},
                    "max_results": {"type": "integer"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run the test suite, optionally filtered.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {"type": "string"},
                    "verbose": {"type": "boolean"},
                },
            },
        },
    },
]

# Fast lookup by tool name → full tool entry (for the scorers' schema arg).
TOOLS_BY_NAME: dict[str, dict] = {t["function"]["name"]: t for t in TOOLS}

TOOLCALL_SYSTEM = (
    "You are a coding agent operating on a Python repository. Use the provided "
    "tools to make changes. Emit exactly one tool call per turn."
)

# tool-call suite — 8 user turns of accumulating context. Each entry: the user
# message, the tool the turn should produce, and the canned tool result the
# driver appends so the path is deterministic (no real execution).
TOOLCALL_TURNS: list[dict] = [
    {
        "user": "Search the codebase for functions named `parse_config`.",
        "expected_tool": "search_code",
        "tool_result": "Found 2 matches: app/config.py:12, app/legacy.py:88",
    },
    {
        "user": "Create `config.py` with a `Config` dataclass holding host, port, timeout.",
        "expected_tool": "write_file",
        "tool_result": "Wrote config.py (412 bytes).",
    },
    {
        "user": (
            "Now add three fields — retries, backoff, tls — using edit_file "
            "with one edit per field."
        ),
        "expected_tool": "edit_file",
        "tool_result": "Applied 3 edits to config.py.",
    },
    {
        "user": (
            "Rename `Config` to `AppConfig` everywhere; use edit_file with "
            "edits for each occurrence."
        ),
        "expected_tool": "edit_file",
        "tool_result": "Applied 4 edits across config.py.",
    },
    {
        "user": "Search for `TODO` across `*.py` and `*.md`.",
        "expected_tool": "search_code",
        "tool_result": "Found 5 matches across 3 files.",
    },
    {
        "user": "Write a test file with 4 test methods covering the new fields.",
        "expected_tool": "write_file",
        "tool_result": "Wrote tests/test_config.py (1.1 KB).",
    },
    {
        "user": "Fix the failing import in two files at once.",
        "expected_tool": "edit_file",
        "tool_result": "Applied 2 edits across app/config.py, app/legacy.py.",
    },
    {
        "user": "Run the tests filtered to config, verbose.",
        "expected_tool": "run_tests",
        "tool_result": "4 passed in 0.12s.",
    },
]

# The turn indices (0-based) whose tool is edit_file — the array-of-objects
# truncation probe; the headline bug count is computed over these.
TOOLCALL_EDIT_TURNS = [i for i, t in enumerate(TOOLCALL_TURNS) if t["expected_tool"] == "edit_file"]

# recovery suite — two clean turns for context, a turn that emits run_tests, a
# synthetic tool error, then "Fix it." and observe the next assistant turns.
RECOVERY_SYSTEM = TOOLCALL_SYSTEM
RECOVERY_CONTEXT_TURNS: list[dict] = [TOOLCALL_TURNS[0], TOOLCALL_TURNS[1]]
RECOVERY_TRIGGER_TURN: dict = {
    "user": "Run the tests filtered to config.",
    "expected_tool": "run_tests",
}
RECOVERY_TOOL_ERROR = (
    "ERROR: ModuleNotFoundError: no module named 'cfg'. "
    "Traceback (most recent call last):\n"
    '  File "tests/test_config.py", line 12, in <module>\n'
    "    from cfg import Config\n"
    "ModuleNotFoundError: No module named 'cfg'"
)
RECOVERY_FIX_PROMPT = "Fix it."
RECOVERY_OBSERVE_TURNS = 3  # assistant turns observed after the error + fix prompt

# coding suite (judge) — multi-turn incremental tasks; coherence shows when a
# later turn must respect earlier requirements. A task is {name, system, turns};
# the driver runs the turns and captures the transcript for the judge.
CODING_SYSTEM = "You are an expert Python engineer. Write clean, correct, idiomatic code."
CODING_TURNS: list[str] = [
    "Implement a `RateLimiter` class (token-bucket) in Python — "
    "`__init__(rate, capacity)` and `allow() -> bool`.",
    "Make it thread-safe.",
    "Add `allow_n(n)` to consume n tokens atomically.",
    "Use a monotonic clock; refills must not over-fill past capacity.",
    "Add type hints and a docstring with a usage example.",
    "Now add a `reset()` and a unit test class with 4 tests using `unittest`.",
    "There's a subtle bug if `rate==0` — handle it and add a test for it.",
]

# Default judged task (single, moderate).
CODING_TASKS: list[dict] = [
    {"name": "ratelimiter", "system": CODING_SYSTEM, "turns": CODING_TURNS},
]

# Hard judged tasks — trickier, edge-case-laden, designed to DEPARTAGE two
# already-strong models (the deterministic suites saturate). Each turn adds a
# constraint that can regress earlier ones (coherence test) or steps onto a
# classic correctness trap (boundaries, precedence, associativity, cleanup).
HARD_CODING_TASKS: list[dict] = [
    {
        "name": "sliding-window-limiter",
        "system": CODING_SYSTEM,
        "turns": [
            "Implement a `SlidingWindowRateLimiter` in Python: `allow(key) -> bool` "
            "permits at most N requests per key within a rolling window of W seconds "
            "(constructor `__init__(max_requests, window_seconds)`). Use a real "
            "sliding window (timestamps), not fixed buckets.",
            "Make it thread-safe under concurrent keys, and use a monotonic clock.",
            "Memory must not grow unbounded: evict timestamps (and empty keys) that "
            "fall outside the window. Add `allow_n(key, n)` consuming n slots atomically.",
            "Edge cases to handle explicitly: max_requests==0 (deny all), "
            "window_seconds<=0 (raise ValueError), and the exact boundary "
            "(a request exactly W seconds old must have expired).",
            "Add full type hints, a docstring with a usage example, and a `unittest` "
            "class with tests covering the boundary, the per-key isolation, and the "
            "max_requests==0 case.",
        ],
    },
    {
        "name": "expr-evaluator",
        "system": CODING_SYSTEM,
        "turns": [
            "Write `evaluate(expr: str) -> float` that evaluates an arithmetic "
            "expression with + - * / , parentheses, integers and floats. No `eval`. "
            "Respect operator precedence and left-associativity.",
            "Support unary minus (e.g. `-3`, `2 * -4`, `-(1+2)`) and arbitrary whitespace.",
            "Add `**` (exponentiation, RIGHT-associative, higher precedence than "
            "unary minus so `-2**2 == -4`) and `%` (modulo, same precedence as `*`).",
            "Raise a clear `ValueError` on malformed input (unbalanced parens, "
            "trailing operator, empty expression) and `ZeroDivisionError` on `/0` "
            "and `%0`.",
            "Add type hints, a docstring, and a `unittest` class with tests for "
            "precedence, right-associativity of `**`, unary minus binding, and the "
            "error cases.",
        ],
    },
]

# tool-call STRESS suite — harder than the baseline: deeper context, bigger
# nested arrays, and JSON-escaping hell (newlines, quotes, backslashes, unicode,
# braces inside code strings) — the conditions under which even strong models'
# tool-call JSON cracks. Used to try to DEPARTAGE models that ace the baseline.
STRESS_TOOLCALL_SYSTEM = TOOLCALL_SYSTEM
STRESS_TOOLCALL_TURNS: list[dict] = [
    {
        "user": "Search for class definitions matching `^class \\w+Error` across the repo.",
        "expected_tool": "search_code",
        "tool_result": "Found 3 matches.",
    },
    {
        "user": (
            "Create `parser.py` containing a function `parse(s)` that handles escaped "
            "quotes. Include this exact docstring line in the content: "
            '`Handle \\"quoted\\" and \\\\backslash\\\\ and newline\\n cases.`'
        ),
        "expected_tool": "write_file",
        "tool_result": "Wrote parser.py (640 bytes).",
    },
    {
        "user": (
            "Use edit_file to add 6 regex constants to parser.py — one edit per "
            "constant. The replace strings contain backslashes and quotes: e.g. "
            "patterns like `r'\\d+\\.\\d+'`, `r'\\\"[^\\\"]*\\\"'`, `r'[\\t\\n]+'`."
        ),
        "expected_tool": "edit_file",
        "tool_result": "Applied 6 edits to parser.py.",
    },
    {
        "user": "Search across `*.py`, `*.pyi`, `*.md`, `*.toml` for `TODO|FIXME|XXX`.",
        "expected_tool": "search_code",
        "tool_result": "Found 11 matches across 5 files.",
    },
    {
        "user": (
            "Write `fixtures.py` whose content is a multi-line string with embedded "
            'JSON, code fences and unicode: include `{"key": [1, 2, {"nested": '
            '"café—naïve"}]}` and a ```python block``` inside the file content.'
        ),
        "expected_tool": "write_file",
        "tool_result": "Wrote fixtures.py (1.4 KB).",
    },
    {
        "user": (
            "Rename `parse` to `parse_expr` everywhere using edit_file with 8 edits, "
            "each search/replace preserving surrounding context (function defs, calls, "
            "imports, docstring references)."
        ),
        "expected_tool": "edit_file",
        "tool_result": "Applied 8 edits across 4 files.",
    },
    {
        "user": (
            "Now, deep in this session, apply 10 edits at once to refactor error "
            "handling: each edit wraps a call in try/except with a multi-line "
            "replacement containing newlines and nested quotes."
        ),
        "expected_tool": "edit_file",
        "tool_result": "Applied 10 edits.",
    },
    {
        "user": "Search for `parse_expr` to confirm the rename, limited to 50 results in `*.py`.",
        "expected_tool": "search_code",
        "tool_result": "Found 14 matches.",
    },
    {
        "user": "Run the full test suite, verbose.",
        "expected_tool": "run_tests",
        "tool_result": "23 passed in 0.41s.",
    },
]
STRESS_EDIT_TURNS = [
    i for i, t in enumerate(STRESS_TOOLCALL_TURNS) if t["expected_tool"] == "edit_file"
]

# Single-model rubric: the judge scores ONE transcript on four criteria (1-5)
# plus an overall 1-5. asiai benches one target at a time, so cross-model
# comparison is done by running --code on each and diffing the JSON (the asiai
# idiom), not by pairwise prompting — this keeps the judge call single-target.
CODING_JUDGE_SYSTEM = (
    "You are a strict senior Python reviewer grading one assistant's work on a "
    "7-turn incremental coding task (a token-bucket RateLimiter). You are given "
    "the user turns and the assistant's responses. Grade ONLY on the evidence "
    "shown; do not assume code you cannot see works."
)
CODING_JUDGE_RUBRIC = (
    "Score the assistant on each criterion as an integer 1-5 (5 = excellent):\n"
    "(1) correctness — does the final code actually work and satisfy every "
    "turn's requirement;\n"
    "(2) coherence — does each turn build on prior turns without regressing "
    "earlier requirements (thread-safety, monotonic clock, capacity cap, the "
    "rate==0 fix);\n"
    "(3) quality — idiomatic, typed, documented, no dead code;\n"
    "(4) following — did it do exactly what each turn asked, no more no less.\n"
    "Then give an overall 1-5. Respond ONLY as JSON: "
    '{"correctness":n,"coherence":n,"quality":n,"following":n,"overall":n,'
    '"reason":"one sentence"}.'
)

# thinking-discipline probes — each deterministic; the driver applies the
# per-probe thinking setting and runs the named check.
THINKING_SYSTEM = "You are a helpful coding assistant."
THINKING_PROBES: list[dict] = [
    {
        "name": "no_think_leak",
        "user": "Write a Python function that returns the nth Fibonacci number.",
        "max_tokens": 512,
        "enable_thinking": True,
        "check": "no_think_leak",
    },
    {
        "name": "nonempty_short_budget",
        "user": "What is the time complexity of binary search? One sentence.",
        "max_tokens": 64,
        "enable_thinking": True,
        "check": "nonempty_short_budget",
    },
    {
        "name": "thinking_off_honoured",
        "user": "Write a one-line Python lambda that squares its argument.",
        "max_tokens": 256,
        "enable_thinking": False,
        "check": "thinking_off_honoured",
    },
]
