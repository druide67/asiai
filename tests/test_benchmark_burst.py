"""Unit tests for the burst-mode benchmark module."""

from __future__ import annotations

import urllib.error
from io import BytesIO
from unittest.mock import patch

import pytest

from asiai.benchmark.burst import (
    MAX_BURST_SIZE,
    SCHEMA_VERSION,
    BurstCallResult,
    _aggregate_size,
    _do_one_call,
    _make_user_prompt,
    _quantile,
    parse_burst_sizes,
)


class TestParseBurstSizes:
    def test_single_size(self):
        assert parse_burst_sizes("60") == (60,)

    def test_multiple_sizes(self):
        assert parse_burst_sizes("30,60,80") == (30, 60, 80)

    def test_whitespace_tolerant(self):
        assert parse_burst_sizes(" 10 , 20 , 30 ") == (10, 20, 30)

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty burst sizes"):
            parse_burst_sizes("")

    def test_zero_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            parse_burst_sizes("0,5")

    def test_negative_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            parse_burst_sizes("5,-1")

    def test_non_integer_raises(self):
        with pytest.raises(ValueError):
            parse_burst_sizes("abc")

    def test_at_max_size_accepted(self):
        assert parse_burst_sizes(str(MAX_BURST_SIZE)) == (MAX_BURST_SIZE,)

    def test_above_max_size_raises(self):
        with pytest.raises(ValueError, match="MAX_BURST_SIZE"):
            parse_burst_sizes(str(MAX_BURST_SIZE + 1))


class TestQuantile:
    def test_empty_returns_zero(self):
        assert _quantile([], 0.5) == 0.0

    def test_single_value(self):
        assert _quantile([42.0], 0.95) == 42.0

    def test_median_odd_count(self):
        assert _quantile([1.0, 2.0, 3.0, 4.0, 5.0], 0.50) == 3.0

    def test_median_even_count(self):
        # Linear interpolation between values at positions 1.5 (between 2 and 3)
        assert _quantile([1.0, 2.0, 3.0, 4.0], 0.50) == 2.5

    def test_p95_small_list(self):
        # On 5 values, p95 = pos 3.8 = 0.2*4 + 0.8*5 = 4.8
        result = _quantile([1.0, 2.0, 3.0, 4.0, 5.0], 0.95)
        assert 4.5 < result <= 5.0

    def test_p99_returns_near_max(self):
        # Wide range; p99 should be close to max
        values = list(range(100))
        result = _quantile([float(v) for v in values], 0.99)
        assert result >= 95.0


class TestMakeUserPrompt:
    def test_includes_index(self):
        p0 = _make_user_prompt(0)
        p7 = _make_user_prompt(7)
        assert "#0" in p0 or "0" in p0
        assert "#7" in p7 or "7" in p7

    def test_distinct_for_distinct_indices(self):
        # Different call_index must yield different prompts so engines
        # can't trivially cache the user msg across burst slots.
        assert _make_user_prompt(0) != _make_user_prompt(1)
        assert _make_user_prompt(7) != _make_user_prompt(42)


class TestAggregateSize:
    def _mk(self, idx, latency_ms, ok=True, tokens=10, error=None):
        return BurstCallResult(
            call_index=idx,
            ok=ok,
            status_code=200 if ok else 500,
            latency_ms=latency_ms,
            ttft_ms=None,
            completion_tokens=tokens,
            prompt_tokens=100,
            error=error,
        )

    def test_all_ok_basic_stats(self):
        results = [self._mk(i, lat) for i, lat in enumerate([100.0, 200.0, 300.0, 400.0, 500.0])]
        agg = _aggregate_size(
            results, wall_time_s=1.0, swap_delta_mb=0.0, swapouts_delta=0, duplicates=[]
        )
        assert agg.n == 5
        assert agg.errors_count == 0
        assert agg.latency_ms["p50"] == 300.0
        assert agg.latency_ms["max"] == 500.0
        # 5 ok calls × 10 tokens / 1s = 50 t/s
        assert agg.throughput_tokens_aggregate_per_s == 50.0
        assert agg.throughput_calls_per_s == 5.0

    def test_soc_power_and_energy_per_token(self):
        results = [self._mk(i, lat) for i, lat in enumerate([100.0, 200.0, 300.0, 400.0, 500.0])]
        agg = _aggregate_size(
            results,
            wall_time_s=1.0,
            swap_delta_mb=0.0,
            swapouts_delta=0,
            duplicates=[],
            gpu_watts=10.0,
            soc_watts=25.0,
            energy_joules=20.0,
        )
        # 50 t/s over 25 W SoC => 2.0 tok/s/W (headline); 20 J / 50 tok => 0.4 J/tok
        assert agg.soc_watts == 25.0
        assert agg.tok_s_per_soc_watt == 2.0
        assert agg.energy_per_token_j == 0.4
        # GPU rail still recorded as a diagnostic alongside
        assert agg.gpu_watts == 10.0
        assert agg.tok_s_per_watt == 5.0

    def test_with_errors(self):
        results = [
            self._mk(0, 100.0),
            self._mk(1, 200.0),
            self._mk(2, 50.0, ok=False, error="HTTP 503"),
            self._mk(3, 50.0, ok=False, error="HTTP 503"),
            self._mk(4, 300.0),
        ]
        agg = _aggregate_size(
            results, wall_time_s=1.0, swap_delta_mb=0.0, swapouts_delta=0, duplicates=[]
        )
        assert agg.errors_count == 2
        assert "HTTP 503: 2" in agg.error_summary
        # p50 computed only on ok results (3 calls)
        assert agg.latency_ms["p50"] == 200.0

    def test_all_errors(self):
        results = [self._mk(i, 50.0, ok=False, error="timeout") for i in range(3)]
        agg = _aggregate_size(
            results, wall_time_s=1.0, swap_delta_mb=0.0, swapouts_delta=0, duplicates=[]
        )
        assert agg.errors_count == 3
        # No ok results => zero stats
        assert agg.latency_ms == {"p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
        assert agg.throughput_tokens_aggregate_per_s == 0.0

    def test_memory_pressure_propagation(self):
        results = [self._mk(0, 100.0)]
        agg = _aggregate_size(
            results, wall_time_s=1.0, swap_delta_mb=512.5, swapouts_delta=2000, duplicates=[]
        )
        assert agg.memory_pressure_swap_delta_mb == 512.5
        assert agg.memory_pressure_swapouts_delta == 2000

    def test_duplicate_processes_propagation(self):
        results = [self._mk(0, 100.0)]
        dups = [{"pid": "1234", "command": "/opt/homebrew/bin/rapid-mlx serve"}]
        agg = _aggregate_size(
            results, wall_time_s=1.0, swap_delta_mb=0.0, swapouts_delta=0, duplicates=dups
        )
        assert agg.duplicate_processes == dups

    def test_power_thermal_propagation_and_efficiency(self):
        # 5 ok × 10 tokens / 1s = 50 t/s aggregate; at 25 W => 2.0 tok/s/W.
        results = [self._mk(i, lat) for i, lat in enumerate([100.0, 200.0, 300.0, 400.0, 500.0])]
        agg = _aggregate_size(
            results,
            wall_time_s=1.0,
            swap_delta_mb=0.0,
            swapouts_delta=0,
            duplicates=[],
            gpu_watts=25.0,
            thermal_speed_limit=100,
        )
        assert agg.gpu_watts == 25.0
        assert agg.thermal_speed_limit == 100
        assert agg.tok_s_per_watt == 2.0

    def test_power_absent_yields_none_efficiency(self):
        results = [self._mk(0, 100.0)]
        agg = _aggregate_size(
            results, wall_time_s=1.0, swap_delta_mb=0.0, swapouts_delta=0, duplicates=[]
        )
        assert agg.gpu_watts is None
        assert agg.tok_s_per_watt is None
        assert agg.thermal_speed_limit is None


class TestSchemaVersion:
    def test_schema_version_value(self):
        assert SCHEMA_VERSION == "burst-v2"


class TestDoOneCall:
    """Exercise the error branches of _do_one_call without a real HTTP server.

    The buffered (stream=False) path is used here because mocking the SSE
    stream requires more elaborate fakes; the streaming code path is
    exercised via integration tests when a real engine is available.
    """

    def _call(self, *, stream: bool = False):
        return _do_one_call(
            base_url="http://127.0.0.1:9999",
            model="test-model",
            sys_msg="sys",
            user_msg="user",
            call_index=0,
            max_tokens=10,
            timeout=5,
            stream=stream,
        )

    def test_http_error_returns_status_code(self):
        err = urllib.error.HTTPError(
            url="http://127.0.0.1:9999/v1/chat/completions",
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=BytesIO(b"overloaded"),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            r = self._call()
        assert r.ok is False
        assert r.status_code == 503
        assert r.error == "HTTP 503"
        assert r.completion_tokens == 0
        assert r.latency_ms >= 0

    def test_generic_exception_returns_typename(self):
        with patch("urllib.request.urlopen", side_effect=TimeoutError("read timed out")):
            r = self._call()
        assert r.ok is False
        assert r.status_code == 0
        assert r.error == "TimeoutError"

    def test_oversize_response_rejected(self):
        # Mock urlopen to return a response whose .read() yields >10 MB.
        class FakeResp:
            def read(self, size: int = -1) -> bytes:
                # Return one byte more than the cap.
                from asiai.benchmark.burst import _MAX_RESPONSE_BYTES

                return b"x" * (_MAX_RESPONSE_BYTES + 1)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with patch("urllib.request.urlopen", return_value=FakeResp()):
            r = self._call()
        assert r.ok is False
        assert "exceeded" in r.error

    def test_successful_call_parses_usage(self):
        class FakeResp:
            def read(self, size: int = -1) -> bytes:
                return (
                    b'{"choices":[{"message":{"content":"ok"}}],'
                    b'"usage":{"prompt_tokens":42,"completion_tokens":7}}'
                )

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with patch("urllib.request.urlopen", return_value=FakeResp()):
            r = self._call()
        assert r.ok is True
        assert r.status_code == 200
        assert r.completion_tokens == 7
        assert r.prompt_tokens == 42


def test_burst_probe_closed_on_exception():
    # try/finally must tear down the probe even if the concurrent block raises
    # (parity with the standard runner and agentic).
    from unittest.mock import MagicMock, patch

    import asiai.benchmark.burst as b

    probe = MagicMock()
    with (
        patch("asiai.benchmark.burst.PowerThermalProbe", return_value=probe),
        patch("asiai.benchmark.burst.EngineMemorySampler", return_value=MagicMock()),
        patch("asiai.benchmark.burst.MemoryWatcher", return_value=MagicMock()),
        patch("asiai.benchmark.burst.check_duplicate_processes", return_value=[]),
        patch(
            "asiai.benchmark.burst.concurrent.futures.ThreadPoolExecutor",
            side_effect=RuntimeError("boom"),
        ),
    ):
        try:
            b._run_one_burst_pass(
                base_url="http://x",
                engine="t",
                model="m",
                size=2,
                sys_msg="s",
                max_tokens=10,
                timeout=5,
                extra_body=None,
                stream=True,
            )
        except RuntimeError:
            pass
    probe.close.assert_called_once()
