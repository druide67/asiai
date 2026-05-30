"""Tests for agentic-mode quality gates: early-stop, duplicates, memory watch."""

from __future__ import annotations

import time
from unittest.mock import patch

from asiai.benchmark.agentic import AgenticRun
from asiai.benchmark.quality_gates import (
    DEFAULT_EARLY_STOP_RATIO,
    MemoryWatcher,
    PowerThermalProbe,
    check_duplicate_processes,
    detect_early_stop,
    summarize_thermal,
)

# --- early-stop -----------------------------------------------------------


def test_early_stop_not_detected_when_all_runs_full():
    runs = [
        AgenticRun(phase="cold", max_tokens_requested=400, completion_tokens=400),
        AgenticRun(phase="warm", max_tokens_requested=400, completion_tokens=400),
        AgenticRun(phase="prefix-test-1", max_tokens_requested=400, completion_tokens=400),
    ]
    result = detect_early_stop(runs)
    assert result["detected"] is False
    assert result["truncated_runs"] == []
    assert result["ratio_threshold"] == DEFAULT_EARLY_STOP_RATIO


def test_early_stop_detected_on_mlx_mtp_pattern():
    # Reproduces a real-world observation with mlx-lm + Qwen3.6 MTP variants:
    # cold/warm/prefix-test-2 complete fine (sys+user identical), prefix-test-1/3
    # truncate to 1 token (sys identical + user different). This is the
    # signature of an engine accepting a speculatively-drafted EOS token
    # incorrectly when the prefix cache reuse path is active.
    runs = [
        AgenticRun(phase="cold", max_tokens_requested=400, completion_tokens=9),
        AgenticRun(phase="warm", max_tokens_requested=400, completion_tokens=9),
        AgenticRun(phase="prefix-test-1", max_tokens_requested=400, completion_tokens=1),
        AgenticRun(phase="prefix-test-2", max_tokens_requested=400, completion_tokens=9),
        AgenticRun(phase="prefix-test-3", max_tokens_requested=400, completion_tokens=1),
    ]
    result = detect_early_stop(runs)
    assert result["detected"] is True
    assert len(result["truncated_runs"]) == 5
    # Sanity check on the per-phase details
    phases = {t["phase"] for t in result["truncated_runs"]}
    assert "prefix-test-1" in phases
    assert "prefix-test-3" in phases


def test_early_stop_single_truncation_not_enough():
    # One stray truncation could be a network blip — min_runs=2 by default.
    runs = [
        AgenticRun(phase="cold", max_tokens_requested=400, completion_tokens=400),
        AgenticRun(phase="warm", max_tokens_requested=400, completion_tokens=50),
    ]
    result = detect_early_stop(runs)
    assert result["detected"] is False
    assert len(result["truncated_runs"]) == 1


def test_early_stop_skips_errored_runs():
    runs = [
        AgenticRun(phase="cold", max_tokens_requested=400, completion_tokens=10, error="HTTP 503"),
        AgenticRun(phase="warm", max_tokens_requested=400, completion_tokens=10, error="HTTP 503"),
    ]
    result = detect_early_stop(runs)
    assert result["detected"] is False
    assert result["truncated_runs"] == []


def test_early_stop_ratio_threshold_configurable():
    runs = [
        AgenticRun(phase="cold", max_tokens_requested=400, completion_tokens=250),
        AgenticRun(phase="warm", max_tokens_requested=400, completion_tokens=250),
    ]
    # 250 / 400 = 0.625, not truncated at default 0.5
    assert detect_early_stop(runs)["detected"] is False
    # But truncated at stricter 0.7
    result_strict = detect_early_stop(runs, ratio_threshold=0.7)
    assert result_strict["detected"] is True


def test_early_stop_zero_requested_ignored():
    # Defensive: a run with max_tokens_requested=0 should not crash on
    # division and should not be flagged.
    runs = [
        AgenticRun(phase="cold", max_tokens_requested=0, completion_tokens=10),
        AgenticRun(phase="warm", max_tokens_requested=0, completion_tokens=10),
    ]
    assert detect_early_stop(runs)["detected"] is False


# --- duplicate processes --------------------------------------------------


def _fake_ps_out(lines: list[str]) -> str:
    """Build a fake ``ps axo pid,command`` stdout (with header)."""
    return "  PID COMMAND\n" + "\n".join(lines) + "\n"


def test_no_duplicate_when_single_process():
    fake = _fake_ps_out(["12345 /opt/homebrew/bin/llama-server --port 8080"])
    with patch("subprocess.run") as m:
        m.return_value.stdout = fake
        result = check_duplicate_processes("llamacpp")
    assert result == []


def test_no_duplicate_when_no_match():
    fake = _fake_ps_out(["12345 /usr/sbin/cron"])
    with patch("subprocess.run") as m:
        m.return_value.stdout = fake
        result = check_duplicate_processes("llamacpp")
    assert result == []


def test_duplicate_detected_two_llamacpp():
    fake = _fake_ps_out(
        [
            "12345 /opt/homebrew/bin/llama-server --port 8080",
            "12346 /opt/homebrew/bin/llama-server --port 8081",
        ]
    )
    with patch("subprocess.run") as m:
        m.return_value.stdout = fake
        result = check_duplicate_processes("llamacpp")
    assert len(result) == 2
    assert {r["pid"] for r in result} == {"12345", "12346"}


def test_duplicate_subprocess_error_returns_empty():
    with patch("subprocess.run", side_effect=OSError("boom")):
        result = check_duplicate_processes("llamacpp")
    assert result == []


# --- MemoryWatcher --------------------------------------------------------


def _patch_mem_samples(samples: list[tuple[float, int]]):
    """Inject a sequence of (swap_mb, swapouts) tuples for successive samples.

    Sticks on the last sample once the sequence is exhausted, so the
    background thread doesn't raise StopIteration when the test's wait
    outlives the queued samples.
    """
    state = {"idx": 0}

    def next_idx() -> int:
        i = min(state["idx"], len(samples) - 1)
        state["idx"] += 1
        return i

    def fake_vm_stat():
        i = next_idx()
        return 1000, 200, samples[i][1], 16384

    def fake_swap_mb():
        # Mirror the index of the most-recent vm_stat call so the (swap, swapouts)
        # pair stays consistent within a single sample.
        i = max(state["idx"] - 1, 0)
        return samples[min(i, len(samples) - 1)][0]

    return fake_vm_stat, fake_swap_mb


def test_memory_watcher_baseline_captured_on_init():
    fake_vm_stat, fake_swap_mb = _patch_mem_samples([(100.0, 5000)])
    with (
        patch("asiai.benchmark.quality_gates._vm_stat_sample", side_effect=fake_vm_stat),
        patch("asiai.benchmark.quality_gates._swap_used_mb", side_effect=fake_swap_mb),
    ):
        w = MemoryWatcher(interval=999)  # never fires the loop
    assert w.result.baseline_swap_mb == 100.0
    assert w.result.baseline_swapouts == 5000
    assert len(w.result.samples) == 1
    assert w.result.alerted is False


def _wait_until(predicate, timeout: float = 5.0, poll: float = 0.005) -> bool:
    """Wait until ``predicate()`` is truthy or ``timeout`` seconds elapse.

    Returns the final predicate value (True if it became true within
    timeout, False otherwise). Active polling avoids the GHA-runner
    scheduling flake that fixed-duration sleeps suffer from.
    """
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if predicate():
            return True
        time.sleep(poll)
    return predicate()


def test_memory_watcher_alerts_on_swap_growth():
    samples = [
        (100.0, 5000),  # baseline
        (700.0, 5000),  # +600 MB → over 500 threshold
    ]
    fake_vm_stat, fake_swap_mb = _patch_mem_samples(samples)
    with (
        patch("asiai.benchmark.quality_gates._vm_stat_sample", side_effect=fake_vm_stat),
        patch("asiai.benchmark.quality_gates._swap_used_mb", side_effect=fake_swap_mb),
    ):
        with MemoryWatcher(interval=0.01) as w:
            _wait_until(lambda: w.result.alerted, timeout=5.0)
    assert w.result.alerted is True
    assert "swap_delta" in (w.result.alert_reason or "")
    assert w.result.max_swap_delta_mb >= 600.0


def test_memory_watcher_alerts_on_swapouts_growth():
    samples = [
        (100.0, 5000),  # baseline
        (100.0, 7000),  # +2000 swapouts → over 1000 threshold
    ]
    fake_vm_stat, fake_swap_mb = _patch_mem_samples(samples)
    with (
        patch("asiai.benchmark.quality_gates._vm_stat_sample", side_effect=fake_vm_stat),
        patch("asiai.benchmark.quality_gates._swap_used_mb", side_effect=fake_swap_mb),
    ):
        with MemoryWatcher(interval=0.01) as w:
            _wait_until(lambda: w.result.alerted, timeout=5.0)
    assert w.result.alerted is True
    assert w.result.max_swapouts_delta >= 2000


def test_memory_watcher_no_alert_on_stable():
    # 4 samples all at baseline values, swap_delta and swapouts_delta stay 0.
    # Wait for at least 2 samples beyond the baseline to confirm stability.
    samples = [(100.0, 5000)] * 4
    fake_vm_stat, fake_swap_mb = _patch_mem_samples(samples)
    with (
        patch("asiai.benchmark.quality_gates._vm_stat_sample", side_effect=fake_vm_stat),
        patch("asiai.benchmark.quality_gates._swap_used_mb", side_effect=fake_swap_mb),
    ):
        with MemoryWatcher(interval=0.01) as w:
            _wait_until(lambda: len(w.result.samples) >= 3, timeout=5.0)
    assert w.result.alerted is False
    assert w.result.max_swap_delta_mb == 0.0
    assert w.result.max_swapouts_delta == 0


# --- thermal summary ------------------------------------------------------


def test_summarize_thermal_not_observed_when_no_limits():
    runs = [AgenticRun(phase="cold"), AgenticRun(phase="warm")]
    result = summarize_thermal(runs)
    assert result == {"observed": False, "min_speed_limit": None, "throttled": False}


def test_summarize_thermal_not_throttled_at_100():
    runs = [
        AgenticRun(phase="cold", thermal_speed_limit=100),
        AgenticRun(phase="warm", thermal_speed_limit=100),
    ]
    result = summarize_thermal(runs)
    assert result == {"observed": True, "min_speed_limit": 100, "throttled": False}


def test_summarize_thermal_throttled_when_any_below_100():
    runs = [
        AgenticRun(phase="cold", thermal_speed_limit=100),
        AgenticRun(phase="warm", thermal_speed_limit=70),
        AgenticRun(phase="prefix-test-1", thermal_speed_limit=100),
    ]
    result = summarize_thermal(runs)
    assert result["observed"] is True
    assert result["min_speed_limit"] == 70
    assert result["throttled"] is True


# --- power/thermal probe --------------------------------------------------


def test_power_thermal_probe_unavailable_returns_none():
    # IOReport not available on this host (e.g. CI Linux runner): probe is
    # inert, read() still returns the dict shape with gpu_watts None.
    with patch("asiai.benchmark.quality_gates.ioreport_available", return_value=False):
        probe = PowerThermalProbe()
        assert probe.available is False
        probe.start()  # no-op, must not raise
        with patch(
            "asiai.benchmark.quality_gates.collect_thermal",
            side_effect=Exception("no thermal"),
        ):
            reading = probe.read()
        assert reading == {"gpu_watts": None, "thermal_speed_limit": None}
        probe.close()  # idempotent, must not raise
        probe.close()


def test_power_thermal_probe_reads_gpu_watts_and_thermal():
    fake_sampler = type(
        "FakeSampler",
        (),
        {
            "sample": lambda self: type("R", (), {"gpu_watts": 24.5})(),
            "close": lambda self: None,
        },
    )()
    fake_thermal = type("T", (), {"speed_limit": 100})()
    with (
        patch("asiai.benchmark.quality_gates.ioreport_available", return_value=True),
        patch("asiai.benchmark.quality_gates.IOReportSampler", return_value=fake_sampler),
        patch("asiai.benchmark.quality_gates.collect_thermal", return_value=fake_thermal),
    ):
        probe = PowerThermalProbe()
        assert probe.available is True
        probe.start()
        reading = probe.read()
    assert reading["gpu_watts"] == 24.5
    assert reading["thermal_speed_limit"] == 100


def test_power_thermal_probe_negative_speed_limit_becomes_none():
    # collect_thermal() returns -1 when the speed limit is unknown; the probe
    # maps that to None so consumers don't treat -1 as a real throttle value.
    fake_thermal = type("T", (), {"speed_limit": -1})()
    with (
        patch("asiai.benchmark.quality_gates.ioreport_available", return_value=False),
        patch("asiai.benchmark.quality_gates.collect_thermal", return_value=fake_thermal),
    ):
        probe = PowerThermalProbe()
        reading = probe.read()
    assert reading["thermal_speed_limit"] is None


def test_power_thermal_probe_sampler_exception_yields_none():
    # A sampler that raises on sample() must not crash the bench; gpu_watts
    # degrades to None.
    class BoomSampler:
        def sample(self):
            raise RuntimeError("ioreport boom")

        def close(self):
            pass

    fake_thermal = type("T", (), {"speed_limit": 100})()
    with (
        patch("asiai.benchmark.quality_gates.ioreport_available", return_value=True),
        patch("asiai.benchmark.quality_gates.IOReportSampler", return_value=BoomSampler()),
        patch("asiai.benchmark.quality_gates.collect_thermal", return_value=fake_thermal),
    ):
        probe = PowerThermalProbe()
        probe.start()  # swallows the exception
        reading = probe.read()
    assert reading["gpu_watts"] is None
    assert reading["thermal_speed_limit"] == 100
