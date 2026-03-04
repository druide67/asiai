"""Tests for benchmark regression detection."""

from __future__ import annotations

import os
import tempfile
import time

from asiai.benchmark.regression import (
    _classify_severity,
    _compute_averages,
    detect_regressions,
)
from asiai.storage.db import init_db, store_benchmark


def _make_db() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    return path


class TestClassifySeverity:
    def test_minor(self):
        assert _classify_severity(12.0) == "minor"

    def test_significant(self):
        assert _classify_severity(20.0) == "significant"

    def test_major(self):
        assert _classify_severity(35.0) == "major"


class TestComputeAverages:
    def test_single_result(self):
        results = [
            {
                "engine": "ollama", "model": "m", "prompt_type": "code",
                "tok_per_sec": 50.0, "ttft_ms": 800.0,
            }
        ]
        avgs = _compute_averages(results)
        assert avgs[("ollama", "m", "code")]["tok_per_sec"] == 50.0
        assert avgs[("ollama", "m", "code")]["ttft_ms"] == 800.0

    def test_multiple_results(self):
        results = [
            {
                "engine": "ollama", "model": "m", "prompt_type": "code",
                "tok_per_sec": 40.0, "ttft_ms": 800.0,
            },
            {
                "engine": "ollama", "model": "m", "prompt_type": "code",
                "tok_per_sec": 60.0, "ttft_ms": 1200.0,
            },
        ]
        avgs = _compute_averages(results)
        assert avgs[("ollama", "m", "code")]["tok_per_sec"] == 50.0
        assert avgs[("ollama", "m", "code")]["ttft_ms"] == 1000.0


class TestDetectRegressions:
    def test_no_history(self):
        """No historical data should produce no regressions."""
        path = _make_db()
        try:
            current = [
                {
                    "ts": int(time.time()),
                    "engine": "ollama",
                    "model": "m",
                    "tok_per_sec": 50.0,
                    "ttft_ms": 800.0,
                    "prompt_type": "code",
                },
            ]
            regressions = detect_regressions(current, path)
            assert regressions == []
        finally:
            os.unlink(path)

    def test_no_regression(self):
        """Performance at same level should not trigger regression."""
        path = _make_db()
        try:
            now = int(time.time())
            # Historical baseline
            baseline = [
                {
                    "ts": now - 86400,
                    "engine": "ollama",
                    "model": "m",
                    "prompt_type": "code",
                    "tok_per_sec": 50.0,
                    "ttft_ms": 800.0,
                }
            ]
            store_benchmark(path, baseline)

            # Current results (same performance)
            current = [
                {
                    "ts": now,
                    "engine": "ollama",
                    "model": "m",
                    "prompt_type": "code",
                    "tok_per_sec": 49.0,
                    "ttft_ms": 820.0,
                }
            ]
            regressions = detect_regressions(current, path)
            assert regressions == []
        finally:
            os.unlink(path)

    def test_tok_s_regression(self):
        """Significant drop in tok/s should be detected."""
        path = _make_db()
        try:
            now = int(time.time())
            baseline = [
                {
                    "ts": now - 86400,
                    "engine": "ollama",
                    "model": "m",
                    "prompt_type": "code",
                    "tok_per_sec": 50.0,
                    "ttft_ms": 800.0,
                }
            ]
            store_benchmark(path, baseline)

            current = [
                {
                    "ts": now,
                    "engine": "ollama",
                    "model": "m",
                    "prompt_type": "code",
                    "tok_per_sec": 35.0,
                    "ttft_ms": 800.0,
                }
            ]
            regressions = detect_regressions(current, path)
            assert len(regressions) == 1
            assert regressions[0].metric == "tok_per_sec"
            assert regressions[0].severity == "significant"  # -30%
            assert regressions[0].pct_change < 0
        finally:
            os.unlink(path)

    def test_ttft_regression(self):
        """Significant increase in TTFT should be detected."""
        path = _make_db()
        try:
            now = int(time.time())
            baseline = [
                {
                    "ts": now - 86400,
                    "engine": "ollama",
                    "model": "m",
                    "prompt_type": "code",
                    "tok_per_sec": 50.0,
                    "ttft_ms": 800.0,
                }
            ]
            store_benchmark(path, baseline)

            current = [
                {
                    "ts": now,
                    "engine": "ollama",
                    "model": "m",
                    "prompt_type": "code",
                    "tok_per_sec": 50.0,
                    "ttft_ms": 1400.0,
                }
            ]
            regressions = detect_regressions(current, path)
            assert len(regressions) == 1
            assert regressions[0].metric == "ttft_ms"
            assert regressions[0].pct_change > 0
        finally:
            os.unlink(path)

    def test_major_regression(self):
        """Major drop (>30%) should be classified correctly."""
        path = _make_db()
        try:
            now = int(time.time())
            baseline = [
                {
                    "ts": now - 86400,
                    "engine": "ollama",
                    "model": "m",
                    "prompt_type": "code",
                    "tok_per_sec": 50.0,
                    "ttft_ms": 0.0,
                }
            ]
            store_benchmark(path, baseline)

            current = [
                {
                    "ts": now,
                    "engine": "ollama",
                    "model": "m",
                    "prompt_type": "code",
                    "tok_per_sec": 25.0,
                    "ttft_ms": 0.0,
                }
            ]
            regressions = detect_regressions(current, path)
            assert len(regressions) == 1
            assert regressions[0].severity == "major"
        finally:
            os.unlink(path)

    def test_baseline_zero_tok_s(self):
        """Historical tok/s=0 should not cause division by zero."""
        path = _make_db()
        try:
            now = int(time.time())
            baseline = [
                {
                    "ts": now - 86400,
                    "engine": "ollama",
                    "model": "m",
                    "prompt_type": "code",
                    "tok_per_sec": 0.0,
                    "ttft_ms": 0.0,
                }
            ]
            store_benchmark(path, baseline)

            current = [
                {
                    "ts": now,
                    "engine": "ollama",
                    "model": "m",
                    "prompt_type": "code",
                    "tok_per_sec": 50.0,
                    "ttft_ms": 800.0,
                }
            ]
            # Should not crash, and should not flag a regression
            regressions = detect_regressions(current, path)
            assert regressions == []
        finally:
            os.unlink(path)

    def test_current_zero_tok_s(self):
        """Current tok/s=0 should not cause division by zero."""
        path = _make_db()
        try:
            now = int(time.time())
            baseline = [
                {
                    "ts": now - 86400,
                    "engine": "ollama",
                    "model": "m",
                    "prompt_type": "code",
                    "tok_per_sec": 50.0,
                    "ttft_ms": 800.0,
                }
            ]
            store_benchmark(path, baseline)

            current = [
                {
                    "ts": now,
                    "engine": "ollama",
                    "model": "m",
                    "prompt_type": "code",
                    "tok_per_sec": 0.0,
                    "ttft_ms": 0.0,
                }
            ]
            # tok_per_sec=0 is filtered by _compute_averages, so no comparison
            regressions = detect_regressions(current, path)
            assert regressions == []
        finally:
            os.unlink(path)

    def test_both_zero_no_regression(self):
        """Both baseline and current at 0 should produce no regression."""
        path = _make_db()
        try:
            now = int(time.time())
            baseline = [
                {
                    "ts": now - 86400,
                    "engine": "ollama",
                    "model": "m",
                    "prompt_type": "code",
                    "tok_per_sec": 0.0,
                    "ttft_ms": 0.0,
                }
            ]
            store_benchmark(path, baseline)

            current = [
                {
                    "ts": now,
                    "engine": "ollama",
                    "model": "m",
                    "prompt_type": "code",
                    "tok_per_sec": 0.0,
                    "ttft_ms": 0.0,
                }
            ]
            regressions = detect_regressions(current, path)
            assert regressions == []
        finally:
            os.unlink(path)

    def test_empty_results(self):
        """Empty current results should produce no regressions."""
        assert detect_regressions([]) == []

    def test_sorted_by_severity(self):
        """Regressions should be sorted major first."""
        path = _make_db()
        try:
            now = int(time.time())
            baselines = [
                {
                    "ts": now - 86400,
                    "engine": "a",
                    "model": "m",
                    "prompt_type": "code",
                    "tok_per_sec": 100.0,
                    "ttft_ms": 0.0,
                },
                {
                    "ts": now - 86400,
                    "engine": "b",
                    "model": "m",
                    "prompt_type": "code",
                    "tok_per_sec": 100.0,
                    "ttft_ms": 0.0,
                },
            ]
            store_benchmark(path, baselines)

            current = [
                {
                    "ts": now,
                    "engine": "a",
                    "model": "m",
                    "prompt_type": "code",
                    "tok_per_sec": 88.0,
                    "ttft_ms": 0.0,
                },  # minor
                {
                    "ts": now,
                    "engine": "b",
                    "model": "m",
                    "prompt_type": "code",
                    "tok_per_sec": 50.0,
                    "ttft_ms": 0.0,
                },  # major
            ]
            regressions = detect_regressions(current, path)
            assert len(regressions) == 2
            assert regressions[0].severity == "major"
            assert regressions[1].severity == "minor"
        finally:
            os.unlink(path)
