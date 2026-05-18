"""Tests for the agentic-mode 8-run benchmark."""

from __future__ import annotations

import io
import json
from unittest.mock import patch

from asiai.benchmark.agentic import (
    PHASES,
    SYS_A,
    SYS_B,
    USER_L,
    USER_X,
    USER_Y,
    AgenticRun,
    _compute_verdict,
    _grow_to,
    run_agentic_bench,
)


def test_grow_to_targets_chars():
    out = _grow_to(1000, "test-label")
    assert len(out) == 1000
    assert out.startswith("[test-label]")


def test_grow_to_deterministic():
    a = _grow_to(500, "same")
    b = _grow_to(500, "same")
    assert a == b


def test_prompts_distinct():
    assert SYS_A != SYS_B
    assert USER_X != USER_Y
    assert USER_L != USER_X


def test_phases_define_protocol():
    names = [p.name for p in PHASES]
    assert names == [
        "cold",
        "warm",
        "prefix-test-1",
        "prefix-test-2",
        "prefix-test-3",
        "cold-prefix",
        "long-context",
        "long-prefix",
    ]


def test_compute_verdict_yes_from_cached():
    runs = [
        AgenticRun(phase="cold", prompt_tokens=7500, cached_tokens=0, ttft_ms=70000),
        AgenticRun(phase="prefix-test-1", prompt_tokens=7500, cached_tokens=6000),
        AgenticRun(phase="prefix-test-3", prompt_tokens=7500, cached_tokens=6000),
    ]
    assert _compute_verdict(runs) == "yes"


def test_compute_verdict_no_from_cached():
    runs = [
        AgenticRun(phase="cold", prompt_tokens=7500, cached_tokens=0, ttft_ms=70000),
        AgenticRun(phase="prefix-test-1", prompt_tokens=7500, cached_tokens=0, ttft_ms=70000),
        AgenticRun(phase="prefix-test-3", prompt_tokens=7500, cached_tokens=0, ttft_ms=70000),
    ]
    assert _compute_verdict(runs) == "no"


def test_compute_verdict_partial_from_cached():
    runs = [
        AgenticRun(phase="cold", prompt_tokens=7500, cached_tokens=0),
        AgenticRun(phase="prefix-test-1", prompt_tokens=7500, cached_tokens=1500),  # 20%
        AgenticRun(phase="prefix-test-3", prompt_tokens=7500, cached_tokens=1500),
    ]
    assert _compute_verdict(runs) == "partial"


def test_compute_verdict_ttft_fallback_yes():
    runs = [
        AgenticRun(phase="cold", ttft_ms=70000, prompt_tokens=None, cached_tokens=None),
        AgenticRun(phase="prefix-test-1", ttft_ms=2000, prompt_tokens=None, cached_tokens=None),
        AgenticRun(phase="prefix-test-3", ttft_ms=2000, prompt_tokens=None, cached_tokens=None),
    ]
    assert _compute_verdict(runs) == "yes"


def test_compute_verdict_ttft_fallback_no():
    runs = [
        AgenticRun(phase="cold", ttft_ms=70000, prompt_tokens=None, cached_tokens=None),
        AgenticRun(phase="prefix-test-1", ttft_ms=65000, prompt_tokens=None, cached_tokens=None),
        AgenticRun(phase="prefix-test-3", ttft_ms=65000, prompt_tokens=None, cached_tokens=None),
    ]
    assert _compute_verdict(runs) == "no"


def test_compute_verdict_unknown_no_runs():
    assert _compute_verdict([]) == "unknown"


def test_compute_verdict_no_cold_returns_unknown():
    """Only prefix-test runs without a cold reference => unknown."""
    runs = [
        AgenticRun(phase="prefix-test-1", prompt_tokens=7500, cached_tokens=6000),
        AgenticRun(phase="prefix-test-3", prompt_tokens=7500, cached_tokens=6000),
    ]
    assert _compute_verdict(runs) == "unknown"


def test_compute_verdict_pairs_cached_with_matching_prompt():
    """Cached / prompt averages must come from the same run, not independent lists."""
    runs = [
        AgenticRun(phase="cold", prompt_tokens=7500, cached_tokens=0, ttft_ms=70000),
        # Run with cached reported, prompt reported
        AgenticRun(phase="prefix-test-1", prompt_tokens=7500, cached_tokens=6000),
        # Run with prompt reported but cached missing — must NOT contribute to ratio
        AgenticRun(phase="prefix-test-3", prompt_tokens=7500, cached_tokens=None),
    ]
    # Only the first prefix-test run is paired: 6000/7500 = 0.80 -> yes
    assert _compute_verdict(runs) == "yes"


class _FakeStreamResponse:
    """Mimic urlopen's iter-of-lines for SSE."""

    def __init__(self, chunks_json: list[dict]):
        body_lines = [b"data: " + json.dumps(c).encode() + b"\n\n" for c in chunks_json]
        body_lines.append(b"data: [DONE]\n\n")
        self._lines = iter(body_lines)

    def __iter__(self):
        return self._lines

    def __next__(self):
        return next(self._lines)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_run_agentic_bench_only_cold(tmp_path):
    """End-to-end with a mock SSE stream, only cold phase."""
    chunks = [
        {"choices": [{"delta": {"content": "hello"}}]},
        {
            "choices": [{"delta": {"content": " world"}}],
            "usage": {
                "prompt_tokens": 7528,
                "completion_tokens": 400,
                "prompt_tokens_details": {"cached_tokens": 0},
            },
        },
    ]

    with (
        patch(
            "asiai.benchmark.agentic.urllib.request.urlopen",
            return_value=_FakeStreamResponse(chunks),
        ),
        patch("asiai.benchmark.agentic.time.sleep"),
    ):
        out = run_agentic_bench(
            base_url="http://localhost:8080",
            engine_name="test-engine",
            model="test-model",
            pause=0,
            only=["cold"],
            out_path=str(tmp_path / "out.json"),
        )

    assert out["engine"] == "test-engine"
    assert out["model"] == "test-model"
    assert out["prefix_cache_reuse_verdict"] == "unknown"  # only cold, no prefix-test
    assert len(out["runs"]) == 1
    run = out["runs"][0]
    assert run["phase"] == "cold"
    assert run["prompt_tokens"] == 7528
    assert run["completion_tokens"] == 400
    assert run["cached_tokens"] == 0
    saved = json.loads((tmp_path / "out.json").read_text())
    assert saved["engine"] == "test-engine"


def test_run_agentic_bench_handles_reasoning_key():
    """mlx-lm uses delta.reasoning, llama.cpp uses delta.reasoning_content."""
    chunks_mlx = [
        {"choices": [{"delta": {"reasoning": "thinking..."}}]},
        {
            "choices": [{"delta": {"content": "answer"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 5},
        },
    ]
    with (
        patch(
            "asiai.benchmark.agentic.urllib.request.urlopen",
            return_value=_FakeStreamResponse(chunks_mlx),
        ),
        patch("asiai.benchmark.agentic.time.sleep"),
    ):
        out = run_agentic_bench(
            base_url="http://localhost:8080",
            engine_name="mlx-lm-test",
            model="m",
            pause=0,
            only=["cold"],
        )
    assert out["runs"][0]["ttft_ms"] is not None  # TTFT captured via reasoning chunk
    assert out["runs"][0]["completion_tokens"] == 5


def test_run_agentic_bench_http_error():
    """HTTP error captured into run.error, doesn't crash bench."""
    import urllib.error

    err = urllib.error.HTTPError(
        url="http://localhost:8080/v1/chat/completions",
        code=400,
        msg="Bad Request",
        hdrs={},
        fp=io.BytesIO(b'{"error": "context too long"}'),
    )
    with (
        patch("asiai.benchmark.agentic.urllib.request.urlopen", side_effect=err),
        patch("asiai.benchmark.agentic.time.sleep"),
    ):
        out = run_agentic_bench(
            base_url="http://localhost:8080",
            engine_name="t",
            model="m",
            pause=0,
            only=["cold"],
        )
    assert out["runs"][0]["error"] == "HTTP 400"
