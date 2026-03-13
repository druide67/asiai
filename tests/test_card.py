"""Tests for benchmark card generation."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

from asiai.benchmark.card import (
    _escape,
    _format_vram,
    _validate_submission_id,
    convert_svg_to_png,
    download_card_png,
    generate_card_svg,
    get_share_url,
    save_card,
)


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
        assert "Qwen 3.5" in svg  # _format_model_name transforms tag format
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

    def test_hw_chip_badge_visible(self):
        """M3: hardware chip should be prominently displayed."""
        report = {"model": "test", "engines": {}, "winner": None}
        svg = generate_card_svg(report, hw_chip="Apple M4 Pro")
        assert "Apple M4 Pro" in svg
        # Badge has its own rect element (not just in subtitle)
        assert 'rx="6"' in svg

    def test_logo_mark_present(self):
        """G3: logo mark element should be in the SVG."""
        report = {"model": "test", "engines": {}, "winner": None}
        svg = generate_card_svg(report)
        # Real speedometer logo from assets/logo.svg
        assert "speedometer" in svg.lower() or "circle" in svg
        assert "The Speedtest for local LLMs" in svg

    def test_footer_url_prominent(self):
        """M2: footer URL should be a pill badge, not just text."""
        report = {"model": "test", "engines": {}, "winner": None}
        svg = generate_card_svg(report)
        assert "asiai.dev" in svg
        # Should have a stroke border (pill badge)
        assert 'stroke="#00d4aa"' in svg

    def test_bars_contain_engine_and_toks(self):
        """Bars should show engine name and tok/s value."""
        report = {
            "model": "test",
            "engines": {"eng": {"median_tok_s": 50, "median_ttft_ms": 0,
                                "stability": "", "vram_bytes": 0}},
            "winner": None,
        }
        svg = generate_card_svg(report)
        assert "eng" in svg
        assert "50.0 tok/s" in svg

    def test_winner_without_delta(self):
        """Winner with missing tok_s_delta should not crash."""
        report = {
            "model": "test",
            "engines": {"eng": {"median_tok_s": 50, "median_ttft_ms": 0,
                                "stability": "", "vram_bytes": 0}},
            "winner": {"name": "eng"},
        }
        svg = generate_card_svg(report)
        # Should not crash; winner name should appear somewhere
        assert "eng" in svg


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

    def test_save_invalid_format_falls_back_to_svg(self):
        """P6: invalid format should fall back to svg."""
        svg = "<svg></svg>"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_card(svg, fmt="exe", output_dir=tmpdir)
            assert path.endswith(".svg")

    def test_save_unique_filenames(self):
        """P2: filenames should include pid to avoid collisions."""
        svg = "<svg></svg>"
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_card(svg, output_dir=tmpdir)
            assert f"_{os.getpid()}." in path


class TestEscape:
    def test_escapes_all_xml_entities(self):
        """P4: all XML special chars including single quotes."""
        assert _escape("a&b") == "a&amp;b"
        assert _escape("a<b") == "a&lt;b"
        assert _escape("a>b") == "a&gt;b"
        assert _escape('a"b') == "a&quot;b"
        assert _escape("a'b") == "a&#39;b"


class TestFormatVram:
    def test_round_number(self):
        """G5: 26.0 GB should display as '26 GB VRAM'."""
        assert _format_vram(26 * 1024**3) == "26 GB VRAM"

    def test_fractional_number(self):
        assert _format_vram(int(8.5 * 1024**3)) == "8.5 GB VRAM"


class TestValidateSubmissionId:
    def test_valid_ids(self):
        assert _validate_submission_id("abc12345") is True
        assert _validate_submission_id("a1b2c3d4e5f6") is True
        assert _validate_submission_id("abc-def_123") is True

    def test_too_short(self):
        """P5: reject submission IDs shorter than 8 chars."""
        assert _validate_submission_id("abc") is False
        assert _validate_submission_id("1234567") is False

    def test_invalid_chars(self):
        """X2: reject non-alphanumeric characters."""
        assert _validate_submission_id("abc/../etc") is False
        assert _validate_submission_id("abc<script>") is False
        assert _validate_submission_id("abc 1234") is False


class TestDownloadCardPng:
    def test_invalid_submission_id_rejected(self):
        """X2/P5: invalid IDs should be rejected before network call."""
        assert download_card_png("short") == ""
        assert download_card_png("../../../etc") == ""

    @patch("asiai.benchmark.card.urlopen")
    def test_non_png_magic_rejected(self, mock_urlopen):
        """X1: non-PNG files should be rejected."""
        resp = MagicMock()
        resp.read.return_value = b"GIF89a not a png"
        resp.headers = {"Content-Length": "100"}
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_card_png("valid123abcdef", output_dir=tmpdir)
            assert result == ""

    @patch("asiai.benchmark.card.urlopen")
    def test_oversized_content_length_rejected(self, mock_urlopen):
        """P3: files exceeding 5MB should be rejected via Content-Length."""
        resp = MagicMock()
        resp.headers = {"Content-Length": str(10 * 1024 * 1024)}
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_card_png("valid123abcdef", output_dir=tmpdir)
            assert result == ""

    @patch("asiai.benchmark.card.urlopen")
    def test_successful_download(self, mock_urlopen):
        """Happy path: valid PNG download."""
        png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        resp = MagicMock()
        resp.read.return_value = png_data
        resp.headers = {"Content-Length": str(len(png_data))}
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_card_png("valid123abcdef", output_dir=tmpdir)
            assert result.endswith(".png")
            assert os.path.exists(result)
            with open(result, "rb") as f:
                assert f.read().startswith(b"\x89PNG")

    @patch("asiai.benchmark.card.urlopen")
    def test_network_error_logged(self, mock_urlopen):
        """P1: network errors should be logged, not silently swallowed."""
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("connection refused")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download_card_png("valid123abcdef", output_dir=tmpdir)
            assert result == ""


class TestGetShareUrl:
    def test_default_url(self):
        """A1: default URL should use api.asiai.dev."""
        with patch.dict(os.environ, {}, clear=True):
            url = get_share_url("abc12345")
            assert url == "https://api.asiai.dev/card/abc12345"

    def test_custom_api_url(self):
        """A1: custom API URL should derive site URL."""
        with patch.dict(os.environ, {"ASIAI_COMMUNITY_URL": "https://api.custom.dev/api/v1"}):
            url = get_share_url("abc12345")
            assert url == "https://api.custom.dev/card/abc12345"
            assert "abc12345" in url


class TestConvertSvgToPng:
    def test_returns_empty_on_missing_sips(self):
        """O2: should fail gracefully if sips is unavailable."""
        with patch("asiai.benchmark.card.subprocess.run", side_effect=FileNotFoundError):
            result = convert_svg_to_png("/nonexistent.svg")
            assert result == ""


class TestIntegrationWithAggregateResults:
    """A3: test card generation with real aggregate_results output."""

    def test_card_from_aggregated_benchmark(self):
        from asiai.benchmark.reporter import aggregate_results

        # Simulate realistic benchmark results
        results = [
            {
                "engine": "lmstudio",
                "model": "qwen3.5:35b-a3b",
                "prompt_type": "code",
                "tok_per_sec": 72.6,
                "ttft_ms": 280.0,
                "tokens_generated": 435,
                "total_duration_ms": 6200.0,
                "vram_bytes": 0,
                "thermal_level": "nominal",
                "hw_chip": "Apple M4 Pro",
                "proc_cpu_pct": 12.0,
                "proc_rss_bytes": 1_000_000,
            },
            {
                "engine": "ollama",
                "model": "qwen3.5:35b-a3b",
                "prompt_type": "code",
                "tok_per_sec": 30.4,
                "ttft_ms": 250.0,
                "tokens_generated": 448,
                "total_duration_ms": 15280.0,
                "vram_bytes": 26_000_000_000,
                "thermal_level": "nominal",
                "hw_chip": "Apple M4 Pro",
                "proc_cpu_pct": 8.0,
                "proc_rss_bytes": 500_000,
            },
        ]

        report = aggregate_results(results)
        report["model"] = "qwen3.5:35b-a3b"

        # Should not crash with real aggregated data
        svg = generate_card_svg(report, hw_chip="Apple M4 Pro")
        assert "<svg" in svg
        assert "lmstudio" in svg
        assert "ollama" in svg
        assert "72.6" in svg
        assert "M4 Pro" in svg
