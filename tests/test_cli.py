"""Tests for asiai CLI."""

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


def test_detect_stub(capsys):
    main(["detect"])
    captured = capsys.readouterr()
    assert "detect" in captured.out
