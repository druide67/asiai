"""Tests for asiai CLI."""

import json
from unittest.mock import MagicMock, patch

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
