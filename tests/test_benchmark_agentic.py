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
    run_agentic_bench,
)
from asiai.benchmark.prompts import _grow_to


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


def test_samplers_stopped_on_error_path():
    # Regression for the reviewed blocker: both the KVCacheSampler and the
    # EngineMemorySampler must be stopped even when the request errors out,
    # otherwise their daemon threads keep polling and contaminate later phases.
    # A4 routes both through a single contextlib.ExitStack, so teardown holds on
    # every exit path (success, HTTPError, generic exception).
    import urllib.error
    from unittest.mock import MagicMock

    err = urllib.error.HTTPError(
        url="http://x", code=503, msg="busy", hdrs={}, fp=io.BytesIO(b"{}")
    )
    kv_sampler = MagicMock()
    mem_sampler = MagicMock()
    with (
        patch("asiai.benchmark.agentic.KVCacheSampler", return_value=kv_sampler),
        patch("asiai.benchmark.agentic.EngineMemorySampler", return_value=mem_sampler),
        patch("asiai.benchmark.agentic.urllib.request.urlopen", side_effect=err),
        patch("asiai.benchmark.agentic.time.sleep"),
    ):
        run_agentic_bench(
            base_url="http://localhost:8080",
            engine_name="t",
            model="m",
            pause=0,
            only=["cold"],
        )
    kv_sampler.__enter__.assert_called()
    kv_sampler.__exit__.assert_called()
    mem_sampler.__enter__.assert_called()
    mem_sampler.__exit__.assert_called()


def test_do_single_run_decode_window_and_soc_metrics():
    # The power window is split at first-token: read_power() captures the
    # prefill slice, the final read() measures decode. soc_watts is the decode
    # headline, energy_per_token_j uses the decode SoC energy, and the prefill
    # SoC watts is recorded separately.
    from unittest.mock import MagicMock

    import asiai.benchmark.agentic as ag

    probe = MagicMock()
    probe.engine_name = None  # no EngineMemorySampler
    probe.read_power.return_value = {"gpu_watts": 5.0, "soc_watts": 30.0, "energy_joules": 60.0}
    probe.read.return_value = {
        "gpu_watts": 8.0,
        "soc_watts": 40.0,
        "energy_joules": 200.0,
        "thermal_speed_limit": 100,
        "engine_rss_mb": 1000.0,
        "engine_phys_footprint_mb": 500.0,
    }
    lines = [
        b'data: {"choices":[{"delta":{"content":"x"}}]}',
        b'data: {"choices":[{"delta":{"content":"y"}}]}',
        b'data: {"choices":[{"delta":{"content":"z"}}]}',
        b'data: {"usage":{"completion_tokens":3,"prompt_tokens":100},"choices":[]}',
        b"data: [DONE]",
    ]

    class _Resp:
        def __enter__(self):
            return iter(lines)

        def __exit__(self, *a):
            return False

    with (
        patch("asiai.benchmark.agentic.KVCacheSampler", return_value=MagicMock()),
        patch("asiai.benchmark.agentic.urllib.request.urlopen", return_value=_Resp()),
    ):
        run = ag._do_single_run(
            base_url="http://x",
            model="m",
            phase_name="cold",
            sys_msg="s",
            user_msg="u",
            max_tokens=400,
            probe=probe,
        )

    probe.read_power.assert_called_once()  # split happened exactly at first-token
    assert run.completion_tokens == 3
    assert run.soc_watts == 40.0  # decode-window package power
    assert run.prefill_watts == 30.0  # prefill-window package power
    # decode energy (200 J) over the (n-1)=2 inter-token intervals it covers
    assert run.energy_per_token_j == round(200.0 / 2, 4)
    assert run.decode_tok_s is not None
    assert run.tok_s_per_soc_watt == round(run.decode_tok_s / 40.0, 3)


def test_repeats_produce_phase_stats_with_cv():
    # repeats>1 reruns the whole protocol; phase_stats reports per-phase median
    # and CV across the repetitions (the variance a single run can't give).
    from unittest.mock import patch

    import asiai.benchmark.agentic as ag

    seq = iter([100.0, 110.0, 90.0])

    def fake_run(*, phase_name, **kw):
        return ag.AgenticRun(
            phase=phase_name,
            completion_tokens=400,
            max_tokens_requested=400,
            decode_tok_s=next(seq),
            ttft_ms=50,
            soc_watts=40.0,
        )

    with (
        patch("asiai.benchmark.agentic._do_single_run", side_effect=fake_run),
        patch("asiai.benchmark.agentic.time.sleep"),
    ):
        out = ag.run_agentic_bench(
            base_url="http://x",
            engine_name="t",
            model="m",
            pause=0,
            only=["cold"],
            skip_quality_gates=True,
            repeats=3,
        )

    assert out["repeats"] == 3
    assert len(out["runs"]) == 3  # 1 phase x 3 repeats
    assert {r["repeat"] for r in out["runs"]} == {0, 1, 2}
    stats = out["phase_stats"]["cold"]["decode_tok_s"]
    assert stats["n"] == 3
    assert stats["median"] == 100.0
    assert stats["cv"] == 0.1  # stdev 10 / mean 100


def _reuse_run(phase, **kw):
    import asiai.benchmark.agentic as ag

    base = {"completion_tokens": 400, "max_tokens_requested": 400, "prompt_tokens": 7500}
    base.update(kw)
    return ag.AgenticRun(phase=phase, **base)


def test_compute_reuse_usage_cached_raw_signal():
    import asiai.benchmark.agentic as ag

    runs = [
        _reuse_run("cold", cached_tokens=0, ttft_ms=1000),
        _reuse_run("prefix-test-1", cached_tokens=6000, ttft_ms=150),
        _reuse_run("prefix-test-3", cached_tokens=6000, ttft_ms=150),
    ]
    reuse = ag._compute_reuse(runs)
    assert reuse["cache_source"] == "usage_cached"
    assert reuse["reuse_fraction"] == round(6000 / 7500, 3)  # 0.8
    assert reuse["reuse_corroborated_by_ttft"] is True  # 150 <= 1000/5
    assert reuse["verdict"] == "yes"


def test_compute_reuse_ttft_proxy_when_cached_absent():
    # llama.cpp case: no usage.cached_tokens, but TTFT collapses on prefix reuse.
    # The raw signal corroborates reuse where the verdict alone would mislead.
    import asiai.benchmark.agentic as ag

    runs = [
        _reuse_run("cold", cached_tokens=None, ttft_ms=1000),
        _reuse_run("prefix-test-1", cached_tokens=None, ttft_ms=120),
        _reuse_run("prefix-test-3", cached_tokens=None, ttft_ms=120),
    ]
    reuse = ag._compute_reuse(runs)
    assert reuse["cache_source"] == "ttft_proxy"
    assert reuse["reuse_fraction"] is None
    assert reuse["reuse_corroborated_by_ttft"] is True


def test_compute_reuse_excludes_early_stop_runs():
    # An early-stopped prefix run (tokens << requested) must not feed the vote.
    import asiai.benchmark.agentic as ag

    runs = [
        _reuse_run("cold", cached_tokens=0, ttft_ms=1000),
        _reuse_run("prefix-test-1", completion_tokens=10, cached_tokens=6000, ttft_ms=150),
    ]
    reuse = ag._compute_reuse(runs)
    # The only prefix run was early-stopped => no usable prefix samples.
    assert reuse["reuse_fraction"] is None
    assert reuse["cache_source"] == "absent"
