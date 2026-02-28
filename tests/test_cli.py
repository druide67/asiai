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


def test_bench_stub(capsys):
    """bench command is a placeholder."""
    ret = main(["bench"])
    captured = capsys.readouterr()
    assert "not yet implemented" in captured.out
