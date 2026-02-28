"""Tests for asiai CLI."""

from unittest.mock import patch

from asiai.cli import main


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
    from unittest.mock import MagicMock

    from asiai.engines.base import InferenceEngine
    engine = MagicMock(spec=InferenceEngine)
    engine.name = name
    engine.base_url = "http://localhost:11434"
    engine.is_reachable.return_value = True
    engine.list_running.return_value = models or []
    engine.list_available.return_value = []
    return engine
