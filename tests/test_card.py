"""Tests for benchmark card generation."""

from __future__ import annotations

import os
import tempfile

from asiai.benchmark.card import generate_card_svg, save_card


class TestCardSvg:
    def test_generate_basic(self):
        report = {
            "model": "qwen3.5:35b-a3b",
            "engines": {
                "lmstudio": {
                    "median_tok_s": 72.6,
                    "median_ttft_ms": 280.0,
                    "stability": "stable",
                    "vram_bytes": 0,
                },
                "ollama": {
                    "median_tok_s": 30.4,
                    "median_ttft_ms": 250.0,
                    "stability": "stable",
                    "vram_bytes": 26_000_000_000,
                },
            },
            "winner": {"name": "lmstudio", "tok_s_delta": "2.4x faster", "vram_delta": ""},
        }
        svg = generate_card_svg(report, hw_chip="Apple M4 Pro")
        assert "<svg" in svg
        assert "1200" in svg
        assert "630" in svg
        assert "asiai" in svg
        assert "lmstudio" in svg
        assert "ollama" in svg
        assert "72.6" in svg
        assert "qwen3.5" in svg
        assert "M4 Pro" in svg

    def test_generate_single_engine(self):
        report = {
            "model": "gemma2:9b",
            "engines": {
                "ollama": {
                    "median_tok_s": 45.0,
                    "median_ttft_ms": 200.0,
                    "stability": "stable",
                    "vram_bytes": 8_000_000_000,
                },
            },
            "winner": None,
        }
        svg = generate_card_svg(report)
        assert "<svg" in svg
        assert "ollama" in svg
        assert "45.0" in svg

    def test_generate_empty_report(self):
        report = {"model": "", "engines": {}, "winner": None}
        svg = generate_card_svg(report)
        assert "<svg" in svg

    def test_escapes_special_chars(self):
        report = {
            "model": "model<with>&chars",
            "engines": {
                "test": {
                    "median_tok_s": 10.0,
                    "median_ttft_ms": 0,
                    "stability": "",
                    "vram_bytes": 0,
                },
            },
            "winner": None,
        }
        svg = generate_card_svg(report)
        assert "&lt;" in svg
        assert "&amp;" in svg


class TestSaveCard:
    def test_save_svg(self):
        svg = "<svg></svg>"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_card(svg, fmt="svg", output_dir=tmpdir)
            assert path.endswith(".svg")
            assert os.path.exists(path)
            with open(path) as f:
                assert f.read() == svg

    def test_save_creates_directory(self):
        svg = "<svg></svg>"
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "a", "b", "c")
            path = save_card(svg, output_dir=nested)
            assert os.path.exists(path)
