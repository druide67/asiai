"""Tests for asiai CLI."""

import json
from unittest.mock import MagicMock, patch

import pytest

from asiai.cli import main
from asiai.engines.base import ModelInfo


def test_version(capsys):
    try:
        main(["--version"])
    except SystemExit:
        pass
    captured = capsys.readouterr()
    assert "asiai" in captured.out


def test_no_args(capsys):
    main([])
    captured = capsys.readouterr()
    assert "usage" in captured.out.lower() or "asiai" in captured.out.lower()


def test_detect_no_engines(capsys):
    """detect with no reachable engines shows a message."""
    with patch("asiai.cli._discover_engines", return_value=[]):
        main(["detect"])
    captured = capsys.readouterr()
    assert "no inference engines" in captured.out.lower() or "detected" in captured.out.lower()


def test_models_no_engines(capsys):
    """models with no reachable engines returns 1."""
    with patch("asiai.cli._discover_engines", return_value=[]):
        ret = main(["models"])
    assert ret == 1


def test_bench_no_engines(capsys):
    """bench with no reachable engines returns 1."""
    with patch("asiai.cli._discover_engines", return_value=[]):
        ret = main(["bench"])
    captured = capsys.readouterr()
    assert ret == 1
    assert "no inference engines" in captured.err.lower()


def test_bench_no_model(capsys):
    """bench with engines but no loaded model returns 1."""
    engine = _make_mock_engine("ollama", models=[])
    with patch("asiai.cli._discover_engines", return_value=[engine]):
        ret = main(["bench"])
    captured = capsys.readouterr()
    assert ret == 1
    assert "no model" in captured.err.lower()


def test_bench_help(capsys):
    """bench --help shows expected arguments."""
    try:
        main(["bench", "--help"])
    except SystemExit:
        pass
    captured = capsys.readouterr()
    assert "--model" in captured.out
    assert "--engines" in captured.out
    assert "--prompts" in captured.out
    assert "--history" in captured.out


def _make_mock_engine(name, models=None):

    from asiai.engines.base import InferenceEngine

    engine = MagicMock(spec=InferenceEngine)
    engine.name = name
    engine.base_url = "http://localhost:11434"
    engine.is_reachable.return_value = True
    engine.list_running.return_value = models or []
    engine.list_available.return_value = []
    return engine


def test_models_json_output(capsys, tmp_path):
    """models --json outputs valid JSON."""
    model = ModelInfo(
        name="qwen3.5:35b-a3b",
        size_vram=26_000_000_000,
        format="gguf",
        quantization="Q4_K_M",
        context_length=32768,
    )
    engine = _make_mock_engine("ollama", models=[model])
    engine.version.return_value = "0.17.4"

    with patch("asiai.cli._discover_engines", return_value=[engine]):
        ret = main(["models", "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "engines" in data
    assert len(data["engines"]) == 1
    assert data["engines"][0]["name"] == "ollama"
    assert data["engines"][0]["models"][0]["name"] == "qwen3.5:35b-a3b"
    assert data["engines"][0]["models"][0]["context_length"] == 32768


def test_models_json_no_engines(capsys):
    """models --json with no engines outputs empty structure."""
    with patch("asiai.cli._discover_engines", return_value=[]):
        ret = main(["models", "--json"])
    assert ret == 1
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["engines"] == []


def test_monitor_alert_webhook_arg(capsys, tmp_path):
    """monitor --alert-webhook is parsed without error."""
    db_path = str(tmp_path / "test.db")
    mock_snap = {
        "ts": 1709700000,
        "cpu_load_1": 2.5,
        "cpu_load_5": 2.0,
        "cpu_load_15": 1.5,
        "cpu_cores": 10,
        "mem_total": 68_719_476_736,
        "mem_used": 34_000_000_000,
        "mem_pressure": "normal",
        "thermal_level": "nominal",
        "thermal_speed_limit": 100,
        "uptime": 86400,
        "inference_engine": "ollama",
        "engine_version": "ollama/0.17.4",
        "models": [],
    }

    with (
        patch("asiai.cli._discover_engines", return_value=[]),
        patch("asiai.collectors.snapshot.collect_snapshot", return_value=mock_snap),
        patch("asiai.storage.db.store_snapshot"),
        patch("asiai.storage.db.init_db"),
        patch("asiai.alerting.check_and_alert", return_value=[]) as mock_alert,
    ):
        ret = main(
            ["monitor", "--json", "--db", db_path, "--alert-webhook", "https://example.com/hook"]
        )
    assert ret == 0
    # prev_snapshot is None on first call → no alert fired
    mock_alert.assert_called_once()
    assert mock_alert.call_args[0][1] is None  # prev_snapshot


def test_daemon_start_webhook(capsys, tmp_path):
    """daemon start monitor --alert-webhook passes URL to generate_plist."""
    with (
        patch("asiai.daemon.daemon_status", return_value={"running": False}),
        patch("asiai.daemon.daemon_start") as mock_start,
    ):
        mock_start.return_value = {"status": "started", "plist": "/tmp/test.plist", "interval": 60}
        main(["daemon", "start", "monitor", "--alert-webhook", "https://example.com/hook"])
    mock_start.assert_called_once()
    call_kwargs = mock_start.call_args
    assert call_kwargs[1].get("webhook_url") == "https://example.com/hook"


def test_monitor_json_output(capsys, tmp_path):
    """monitor --json outputs valid JSON."""
    db_path = str(tmp_path / "test.db")
    mock_snap = {
        "ts": 1709700000,
        "cpu_load_1": 2.5,
        "cpu_load_5": 2.0,
        "cpu_load_15": 1.5,
        "cpu_cores": 10,
        "mem_total": 68_719_476_736,
        "mem_used": 34_000_000_000,
        "mem_pressure": "normal",
        "thermal_level": "nominal",
        "thermal_speed_limit": 100,
        "uptime": 86400,
        "inference_engine": "ollama",
        "engine_version": "ollama/0.17.4",
        "models": [],
    }

    with (
        patch("asiai.cli._discover_engines", return_value=[]),
        patch("asiai.collectors.snapshot.collect_snapshot", return_value=mock_snap),
        patch("asiai.storage.db.store_snapshot"),
        patch("asiai.storage.db.init_db"),
    ):
        ret = main(["monitor", "--json", "--db", db_path])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["ts"] == 1709700000
    assert data["cpu_load_1"] == 2.5


# ---------------------------------------------------------------------------
# detect with engines
# ---------------------------------------------------------------------------


def test_detect_with_engines(capsys):
    """detect shows engine info when engines are found."""
    model = ModelInfo(name="gemma2:9b", size_vram=8_000_000_000, format="gguf")
    engine = _make_mock_engine("ollama", models=[model])
    engine.version.return_value = "0.17.4"

    with patch("asiai.cli._discover_engines", return_value=[engine]):
        ret = main(["detect"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "ollama" in captured.out.lower()


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


def test_doctor(capsys, tmp_path):
    """doctor runs checks and returns 0."""
    from asiai.doctor import CheckResult

    mock_results = [
        CheckResult("system", "Apple Silicon", "ok", "Apple M1 Max"),
        CheckResult("system", "Memory", "ok", "64 GB"),
    ]
    db_path = str(tmp_path / "test.db")

    with patch("asiai.doctor.run_checks", return_value=mock_results):
        ret = main(["doctor", "--db", db_path])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Apple" in captured.out or "ok" in captured.out.lower()


# ---------------------------------------------------------------------------
# leaderboard
# ---------------------------------------------------------------------------


def test_leaderboard_no_data(capsys):
    """leaderboard with no community data returns 1."""
    with patch("asiai.community.fetch_leaderboard", return_value=[]):
        ret = main(["leaderboard"])
    assert ret == 1
    captured = capsys.readouterr()
    assert "no community data" in captured.out.lower()


def test_leaderboard_with_data(capsys):
    """leaderboard displays community data."""
    entries = [
        {
            "engine": "ollama",
            "model": "qwen3.5:35b-a3b",
            "median_tok_s": 30.4,
            "median_ttft_ms": 250.0,
            "samples": 12,
        },
    ]
    with patch("asiai.community.fetch_leaderboard", return_value=entries):
        ret = main(["leaderboard", "--chip", "M4 Pro"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Community Leaderboard" in captured.out
    assert "qwen3.5" in captured.out
    assert "30.4" in captured.out


def test_leaderboard_help(capsys):
    """leaderboard --help shows expected arguments."""
    with pytest.raises(SystemExit):
        main(["leaderboard", "--help"])
    captured = capsys.readouterr()
    assert "--chip" in captured.out
    assert "--model" in captured.out


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


def test_compare_no_local_data(capsys, tmp_path):
    """compare with no local benchmarks returns 1."""
    db_path = str(tmp_path / "test.db")
    with (
        patch("asiai.storage.db.init_db"),
        patch("asiai.storage.db.query_benchmarks", return_value=[]),
    ):
        ret = main(["compare", "--db", db_path])
    assert ret == 1
    captured = capsys.readouterr()
    assert "no local benchmarks" in captured.out.lower()


def test_compare_no_community_data(capsys, tmp_path):
    """compare with local data but no community response returns 1."""
    db_path = str(tmp_path / "test.db")
    rows = [
        {
            "engine": "ollama",
            "model": "qwen:7b",
            "tok_per_sec": 45.0,
            "ttft_ms": 200.0,
            "ts": 1709700000,
            "prompt_type": "code",
            "total_duration_ms": 5000,
            "vram_bytes": 0,
            "power_watts": 0,
            "tok_per_sec_per_watt": 0,
            "run_index": 0,
        },
    ]
    with (
        patch("asiai.storage.db.init_db"),
        patch("asiai.storage.db.query_benchmarks", return_value=rows),
        patch("asiai.community.fetch_comparison", return_value=None),
        patch("asiai.collectors.system.collect_machine_info", return_value="Apple M1 Max — test"),
    ):
        ret = main(["compare", "--db", db_path])
    assert ret == 1


# ---------------------------------------------------------------------------
# recommend
# ---------------------------------------------------------------------------


def test_recommend_heuristic_fallback(capsys, tmp_path):
    """recommend with no local data falls back to heuristics."""
    db_path = str(tmp_path / "test.db")

    mem_mock = MagicMock()
    mem_mock.total = 68_719_476_736  # 64 GB

    with (
        patch("asiai.storage.db.init_db"),
        patch("asiai.collectors.system.collect_hw_chip", return_value="Apple M4 Pro"),
        patch("asiai.collectors.system.collect_memory", return_value=mem_mock),
        patch("asiai.advisor.recommender.recommend") as mock_rec,
    ):
        from asiai.advisor.recommender import Recommendation

        mock_rec.return_value = [
            Recommendation(
                engine="ollama",
                model="qwen3.5:35b-a3b",
                score=50.0,
                source="heuristic",
                confidence="low",
                reason="Estimated based on Apple M4 Pro with 64GB RAM",
            ),
        ]
        ret = main(["recommend", "--db", db_path])
    assert ret == 0
    captured = capsys.readouterr()
    assert "ollama" in captured.out.lower()
    assert "qwen3.5" in captured.out


def test_recommend_help(capsys):
    """recommend --help shows expected arguments."""
    with pytest.raises(SystemExit):
        main(["recommend", "--help"])
    captured = capsys.readouterr()
    assert "--use-case" in captured.out
    assert "--community" in captured.out
    assert "--model" in captured.out


# ---------------------------------------------------------------------------
# models with engines
# ---------------------------------------------------------------------------


def test_models_with_engines(capsys):
    """models shows engine info when engines are found."""
    model = ModelInfo(
        name="gemma2:9b",
        size_vram=8_000_000_000,
        format="gguf",
        quantization="Q4_K_M",
        context_length=8192,
    )
    engine = _make_mock_engine("ollama", models=[model])
    engine.version.return_value = "0.17.4"

    with patch("asiai.cli._discover_engines", return_value=[engine]):
        ret = main(["models"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "ollama" in captured.out.lower()
    assert "gemma2:9b" in captured.out
    assert "8k ctx" in captured.out


# ---------------------------------------------------------------------------
# parse_urls and _discover_engines
# ---------------------------------------------------------------------------


def test_parse_urls_none():
    from asiai.cli import _parse_urls

    assert _parse_urls(None) is None


def test_parse_urls_single():
    from asiai.cli import _parse_urls

    result = _parse_urls("http://localhost:11434")
    assert result == ["http://localhost:11434"]


def test_parse_urls_multiple():
    from asiai.cli import _parse_urls

    result = _parse_urls("http://a:1234, http://b:5678")
    assert result == ["http://a:1234", "http://b:5678"]


# ---------------------------------------------------------------------------
# bench with share flag
# ---------------------------------------------------------------------------


def test_bench_share_flag(capsys, tmp_path):
    """bench --share calls community submit on success."""
    model = ModelInfo(name="gemma2:9b", size_vram=8_000_000_000, format="gguf")
    engine = _make_mock_engine("ollama", models=[model])
    engine.version.return_value = "0.17.4"
    db_path = str(tmp_path / "test.db")

    mock_run = MagicMock()
    mock_run.results = [
        {
            "engine": "ollama",
            "model": "gemma2:9b",
            "prompt_type": "code",
            "tok_per_sec": 45.0,
            "ttft_ms": 200.0,
            "total_duration_ms": 5000,
            "tokens_generated": 200,
            "vram_bytes": 8_000_000_000,
            "power_watts": 0,
            "tok_per_sec_per_watt": 0,
            "run_index": 0,
            "ts": 1709700000,
            "thermal_level": "nominal",
        }
    ]

    with (
        patch("asiai.cli._discover_engines", return_value=[engine]),
        patch("asiai.benchmark.runner.find_common_model", return_value="gemma2:9b"),
        patch("asiai.benchmark.runner.run_benchmark", return_value=mock_run),
        patch("asiai.storage.db.init_db"),
        patch("asiai.storage.db.store_benchmark"),
        patch("asiai.community.build_submission", return_value={"id": "abc123", "benchmark": {}}),
        patch("asiai.community.submit_benchmark") as mock_submit,
        patch("asiai.storage.db.store_community_submission"),
    ):
        from asiai.community import SubmitResult

        mock_submit.return_value = SubmitResult(
            success=True,
            submission_id="abc12345",
            http_status=201,
        )
        ret = main(["bench", "--db", db_path, "--share"])
    assert ret == 0
    mock_submit.assert_called_once()


def test_bench_share_skips_when_all_runs_failed(capsys, tmp_path):
    """bench --share without --share-on-error skips when 0 successes."""
    model = ModelInfo(name="gemma2:9b", size_vram=8_000_000_000, format="gguf")
    engine = _make_mock_engine("ollama", models=[model])
    engine.version.return_value = "0.17.4"
    db_path = str(tmp_path / "test.db")

    mock_run = MagicMock()
    # All 3 runs failed (tok_per_sec=0)
    mock_run.results = [
        {
            "engine": "ollama",
            "model": "gemma2:9b",
            "prompt_type": "code",
            "tok_per_sec": 0,
            "ttft_ms": 0,
            "total_duration_ms": 0,
            "tokens_generated": 0,
            "vram_bytes": 0,
            "power_watts": 0,
            "tok_per_sec_per_watt": 0,
            "run_index": i,
            "ts": 1709700000,
            "thermal_level": "nominal",
            "error": "timeout",
        }
        for i in range(3)
    ]

    with (
        patch("asiai.cli._discover_engines", return_value=[engine]),
        patch("asiai.benchmark.runner.find_common_model", return_value="gemma2:9b"),
        patch("asiai.benchmark.runner.run_benchmark", return_value=mock_run),
        patch("asiai.storage.db.init_db"),
        patch("asiai.storage.db.store_benchmark"),
        patch("asiai.community.submit_benchmark") as mock_submit,
        patch("asiai.storage.db.store_community_submission"),
    ):
        ret = main(["bench", "--db", db_path, "--share"])

    assert ret == 0
    mock_submit.assert_not_called()
    out = capsys.readouterr().out
    assert "Skipping share" in out
    assert "0/3 runs succeeded" in out


def test_bench_share_on_error_forces_submit(capsys, tmp_path):
    """--share-on-error opts back into submitting zero-value sessions."""
    model = ModelInfo(name="gemma2:9b", size_vram=8_000_000_000, format="gguf")
    engine = _make_mock_engine("ollama", models=[model])
    engine.version.return_value = "0.17.4"
    db_path = str(tmp_path / "test.db")

    mock_run = MagicMock()
    mock_run.results = [
        {
            "engine": "ollama",
            "model": "gemma2:9b",
            "prompt_type": "code",
            "tok_per_sec": 0,
            "ttft_ms": 0,
            "total_duration_ms": 0,
            "tokens_generated": 0,
            "vram_bytes": 0,
            "power_watts": 0,
            "tok_per_sec_per_watt": 0,
            "run_index": 0,
            "ts": 1709700000,
            "thermal_level": "nominal",
            "error": "timeout",
        }
    ]

    with (
        patch("asiai.cli._discover_engines", return_value=[engine]),
        patch("asiai.benchmark.runner.find_common_model", return_value="gemma2:9b"),
        patch("asiai.benchmark.runner.run_benchmark", return_value=mock_run),
        patch("asiai.storage.db.init_db"),
        patch("asiai.storage.db.store_benchmark"),
        patch("asiai.community.build_submission", return_value={"id": "abc", "benchmark": {}}),
        patch("asiai.community.submit_benchmark") as mock_submit,
        patch("asiai.storage.db.store_community_submission"),
    ):
        from asiai.community import SubmitResult

        mock_submit.return_value = SubmitResult(
            success=True,
            submission_id="x",
            http_status=201,
        )
        ret = main(["bench", "--db", db_path, "--share", "--share-on-error"])

    assert ret == 0
    mock_submit.assert_called_once()


# ---------------------------------------------------------------------------
# --compare argument parsing
# ---------------------------------------------------------------------------


class TestCompareArgs:
    """Tests for _parse_compare_arg and expand_compare_args."""

    def test_parse_compare_arg_model_only(self):
        from asiai.cli import _parse_compare_arg

        assert _parse_compare_arg("qwen:4b") == ("qwen:4b", None)

    def test_parse_compare_arg_with_engine(self):
        from asiai.cli import _parse_compare_arg

        assert _parse_compare_arg("qwen:4b@ollama") == ("qwen:4b", "ollama")

    def test_parse_compare_arg_model_with_colons(self):
        from asiai.cli import _parse_compare_arg

        assert _parse_compare_arg("qwen3.5:4b-instruct@lmstudio") == (
            "qwen3.5:4b-instruct",
            "lmstudio",
        )

    def _make_engines(self):
        engine_ollama = MagicMock()
        engine_ollama.name = "ollama"
        engine_lmstudio = MagicMock()
        engine_lmstudio.name = "lmstudio"
        return engine_ollama, engine_lmstudio

    def test_expand_compare_explicit_slots(self):
        from asiai.cli import expand_compare_args

        engine_ollama, engine_lmstudio = self._make_engines()
        slots = expand_compare_args(
            ["qwen:4b@ollama", "qwen:4b@lmstudio"],
            engines_filter=None,
            detected_engines=[engine_ollama, engine_lmstudio],
        )
        assert len(slots) == 2
        assert slots[0].engine is engine_ollama
        assert slots[0].model == "qwen:4b"
        assert slots[1].engine is engine_lmstudio
        assert slots[1].model == "qwen:4b"

    def test_expand_compare_auto_expand(self):
        from asiai.cli import expand_compare_args

        engine_ollama, engine_lmstudio = self._make_engines()
        slots = expand_compare_args(
            ["qwen:4b"],
            engines_filter=None,
            detected_engines=[engine_ollama, engine_lmstudio],
        )
        assert len(slots) == 2
        assert {s.engine.name for s in slots} == {"ollama", "lmstudio"}
        assert all(s.model == "qwen:4b" for s in slots)

    def test_expand_compare_mixed(self):
        from asiai.cli import expand_compare_args

        engine_ollama, engine_lmstudio = self._make_engines()
        slots = expand_compare_args(
            ["qwen:4b@ollama", "deepseek:7b"],
            engines_filter=None,
            detected_engines=[engine_ollama, engine_lmstudio],
        )
        # 1 explicit + 2 auto-expanded
        assert len(slots) == 3
        assert slots[0].engine is engine_ollama
        assert slots[0].model == "qwen:4b"
        models_engines = {(s.model, s.engine.name) for s in slots}
        assert ("deepseek:7b", "ollama") in models_engines
        assert ("deepseek:7b", "lmstudio") in models_engines

    def test_expand_compare_too_many_slots(self):
        from asiai.cli import expand_compare_args

        engines = []
        for i in range(9):
            e = MagicMock()
            e.name = f"engine{i}"
            engines.append(e)
        with pytest.raises(SystemExit):
            expand_compare_args(
                ["model:7b"],
                engines_filter=None,
                detected_engines=engines,
            )

    def test_expand_compare_unknown_engine(self):
        from asiai.cli import expand_compare_args

        engine_ollama, engine_lmstudio = self._make_engines()
        with pytest.raises(SystemExit):
            expand_compare_args(
                ["qwen:4b@unknown"],
                engines_filter=None,
                detected_engines=[engine_ollama, engine_lmstudio],
            )

    def test_expand_compare_dedup(self):
        from asiai.cli import expand_compare_args

        engine_ollama, engine_lmstudio = self._make_engines()
        slots = expand_compare_args(
            ["qwen:4b@ollama", "qwen:4b@ollama"],
            engines_filter=None,
            detected_engines=[engine_ollama, engine_lmstudio],
        )
        assert len(slots) == 1
        assert slots[0].engine is engine_ollama
        assert slots[0].model == "qwen:4b"

    def test_expand_compare_empty(self):
        from asiai.cli import expand_compare_args

        with pytest.raises(SystemExit):
            expand_compare_args(
                ["qwen:4b"],
                engines_filter=None,
                detected_engines=[],
            )


# --- quality gates decide the exit code -----------------------------------
# asiai always computed these gates and always exited 0, so a scripted caller
# could publish a number the tool itself knew was invalid. These tests pin the
# refusal, not just the reporting.


def _gate_args(fail_on_gate: bool):
    import argparse

    return argparse.Namespace(export=None, fail_on_gate=fail_on_gate)


def _payload_with_empty_output() -> dict:
    """The shipped failure: every response empty, gate red, exit code 0."""
    return {
        "engine": "llamacpp",
        "model": "qwen3.6-27b",
        "prefix_cache_reuse_verdict": "no",
        "prefix_cache_reuse": {"reuse_fraction": 0.0, "cache_source": "usage"},
        "quality_gates": {
            "early_stop": {"detected": False, "truncated_runs": []},
            "duplicate_processes": [],
            "other_engines_resident": [],
            "thermal": {"observed": True, "min_speed_limit": 100, "throttled": False},
            "output_validity": {"output_valid_pct": 0.0, "min_valid_pct": 80.0},
        },
        "phase_stats": {},
        "footprint": {},
    }


def _clean_payload() -> dict:
    p = _payload_with_empty_output()
    p["quality_gates"]["output_validity"] = {"output_valid_pct": 100.0, "min_valid_pct": 80.0}
    return p


def test_gate_exit_code_zero_when_all_gates_pass():
    from asiai.cli import _gate_exit_code

    assert _gate_exit_code(_gate_args(True), "agentic", _clean_payload()) == 0


def test_failed_gate_is_printed_but_does_not_fail_without_the_flag(capsys):
    from asiai.cli import _gate_exit_code

    rc = _gate_exit_code(_gate_args(False), "agentic", _payload_with_empty_output())
    assert rc == 0
    err = capsys.readouterr().err
    assert "output_validity" in err, "a failed gate must be visible even when not enforced"


def test_failed_gate_exits_two_with_the_flag(capsys):
    """Negative witness: the gate must actually refuse, not merely warn."""
    from asiai.cli import _gate_exit_code

    rc = _gate_exit_code(_gate_args(True), "agentic", _payload_with_empty_output())
    assert rc == 2
    assert "output_validity" in capsys.readouterr().err


def test_unevaluable_gates_refuse_rather_than_pass(capsys):
    """A check that cannot measure must not report green — the failure mode
    that let a thermal gate read a field it never returned for weeks."""
    from asiai.cli import _gate_exit_code

    with patch("asiai.benchmark.result_model.build_result", side_effect=ValueError("boom")):
        assert _gate_exit_code(_gate_args(True), "agentic", {}) == 2
        assert _gate_exit_code(_gate_args(False), "agentic", {}) == 0
    assert "could not evaluate" in capsys.readouterr().err


def test_fail_on_gate_accepts_a_subset(capsys):
    """Enforcing everything is unreachable on a laptop (sustained generation
    throttles regardless), so a blanket rule pushes operators back to ignoring
    gates. A subset enforces what the operator actually controls."""
    from asiai.cli import _gate_exit_code

    payload = _clean_payload()
    payload["quality_gates"]["thermal"] = {
        "observed": True,
        "min_speed_limit": 50,
        "throttled": True,
    }
    import argparse

    only_validity = argparse.Namespace(export=None, fail_on_gate="output_validity")
    assert _gate_exit_code(only_validity, "agentic", payload) == 0
    assert "thermal" in capsys.readouterr().err, "unselected gates stay visible"

    everything = argparse.Namespace(export=None, fail_on_gate="all")
    assert _gate_exit_code(everything, "agentic", payload) == 2


def test_fail_on_gate_subset_still_refuses_its_own_gate():
    import argparse

    from asiai.cli import _gate_exit_code

    args = argparse.Namespace(export=None, fail_on_gate="output_validity,thinking")
    assert _gate_exit_code(args, "agentic", _payload_with_empty_output()) == 2


def test_unknown_gate_name_is_refused_not_ignored(capsys):
    """--fail-on-gate with a name the bench type cannot emit must refuse (rc 2).

    Negative witness for the session_replay incident: a gate that was listed,
    never built, and therefore never enforced — the flag looked obeyed.
    """
    import argparse

    from asiai.cli import _gate_exit_code

    args = argparse.Namespace(fail_on_gate="sessoin_replay")  # typo on purpose
    rc = _gate_exit_code(args, "agentic", _clean_payload())
    assert rc == 2
    assert "no such gate" in capsys.readouterr().err


def test_energy_gate_requested_on_agentic_is_refused(capsys):
    """energy_* gates exist for the standard runner only; asking for them on an
    agentic bench must not silently enforce nothing."""
    import argparse

    from asiai.cli import _gate_exit_code

    args = argparse.Namespace(fail_on_gate="energy_provenance")
    assert _gate_exit_code(args, "agentic", _clean_payload()) == 2
    assert "energy_provenance" in capsys.readouterr().err


def test_known_gate_not_evaluated_warns_but_passes(capsys):
    import argparse

    from asiai.cli import _gate_exit_code

    # bank_preload is a documented agentic gate; _clean_payload() predates it
    # and carries no such block, so it is known but not evaluated here.
    args = argparse.Namespace(fail_on_gate="bank_preload")
    rc = _gate_exit_code(args, "agentic", _clean_payload())
    assert rc == 0
    assert "not evaluated" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# detection ↔ adapters invariant
# ---------------------------------------------------------------------------


def test_every_detectable_engine_has_an_adapter():
    """Every engine name `detect` can produce must map to an adapter class
    (a detected engine with no adapter is listed but can never be benchmarked)."""
    from asiai.cli import _engine_classes
    from asiai.engines.detect import _PORT_PROCESS_MAP

    classes = _engine_classes()
    missing = sorted(set(_PORT_PROCESS_MAP.values()) - set(classes))
    assert not missing, f"detected but not benchmarkable: {missing}"
    for name, cls in classes.items():
        assert cls.__name__.endswith("Engine"), (name, cls)


def test_mlxvlm_adapter_is_wired():
    from asiai.cli import _engine_classes
    from asiai.engines.mlxvlm import MlxVlmEngine

    assert _engine_classes()["mlxvlm"] is MlxVlmEngine


def test_fail_on_gate_accepts_a_gate_the_result_emits_on_a_non_agentic_bench():
    """`--fail-on-gate fluency_judge` on a language bench used to exit 2 as
    "no such gate": the documented list only knew standard and agentic
    (2026-09-05 review). A name the result actually emits is valid."""
    import argparse

    from asiai.cli import _gate_exit_code
    from tests.test_result_model import _language_payload

    args = argparse.Namespace(export=None, fail_on_gate="fluency_judge")
    assert _gate_exit_code(args, "language", _language_payload()) == 0
