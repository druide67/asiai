"""Tests for benchmark card generation."""

from __future__ import annotations

import os
import re
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

# ---------------------------------------------------------------------------
# Helpers: data factories
# ---------------------------------------------------------------------------


def _make_engine(
    tok_s: float = 50.0,
    ttft_ms: float = 200.0,
    stability: str = "stable",
    vram_bytes: int = 8_000_000_000,
    runs_count: int = 3,
) -> dict:
    return {
        "median_tok_s": tok_s,
        "median_ttft_ms": ttft_ms,
        "stability": stability,
        "vram_bytes": vram_bytes,
        "runs_count": runs_count,
    }


def _make_report(
    model: str = "qwen3.5:35b-a3b",
    engines: dict | None = None,
    winner: dict | None = None,
) -> dict:
    if engines is None:
        engines = {"ollama": _make_engine(tok_s=48.0)}
    return {"model": model, "engines": engines, "winner": winner}


# ---------------------------------------------------------------------------
# Helpers: SVG coordinate extraction (regex-based)
# ---------------------------------------------------------------------------


def _extract_text_y(svg: str, pattern: str) -> list[float]:
    """Return y-coordinates of <text> elements whose content matches *pattern*."""
    results = []
    for m in re.finditer(r'<text[^>]*\by="([^"]+)"[^>]*>([^<]*(?:<[^/][^>]*>[^<]*)*)</text>', svg):
        if pattern in m.group(2):
            results.append(float(m.group(1)))
    return results


def _extract_hero_y(svg: str) -> float | None:
    """Return y of the hero number (font-size 60 or 72)."""
    m = re.search(r'<text[^>]*\by="(\d+(?:\.\d+)?)"[^>]*font-size="(?:60|72)"', svg)
    return float(m.group(1)) if m else None


def _extract_frame_bounds(svg: str) -> tuple[float, float]:
    """Return (frame_top, frame_bottom) of the terminal frame rect."""
    m = re.search(r'<rect x="40" y="(\d+)" width="1120" height="(\d+)"', svg)
    if m:
        top = float(m.group(1))
        return top, top + float(m.group(2))
    return 0.0, 0.0


def _extract_footer_y(svg: str) -> float | None:
    """Return y of the footer pill (rx=14 rounded rect)."""
    m = re.search(r'<rect[^>]*\by="(\d+(?:\.\d+)?)"[^>]*rx="14"', svg)
    return float(m.group(1)) if m else None


def _extract_chip_ys(svg: str) -> list[float]:
    """Return y-coordinates of all chip rects (height=28, rx=6)."""
    pat = r'<rect[^>]*\by="(\d+(?:\.\d+)?)"[^>]*height="28"[^>]*rx="6"'
    return [float(m.group(1)) for m in re.finditer(pat, svg)]


def _extract_bar_rects(svg: str) -> list[tuple[float, float]]:
    """Return (y, width) of engine bar rects (rx=4, opacity=0.9)."""
    return [
        (float(m.group(1)), float(m.group(2)))
        for m in re.finditer(
            r'<rect[^>]*\by="(\d+(?:\.\d+)?)"[^>]*width="(\d+(?:\.\d+)?)"[^>]*rx="4"[^>]*opacity="0\.9"',
            svg,
        )
    ]


def _extract_all_y(svg: str) -> list[float]:
    """Return all y= attribute values in the SVG."""
    return [float(m.group(1)) for m in re.finditer(r'\by="(\d+(?:\.\d+)?)"', svg)]


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
            "engines": {
                "eng": {"median_tok_s": 50, "median_ttft_ms": 0, "stability": "", "vram_bytes": 0}
            },
            "winner": None,
        }
        svg = generate_card_svg(report)
        assert "eng" in svg
        assert "50.0 tok/s" in svg

    def test_winner_without_delta(self):
        """Winner with missing tok_s_delta should not crash."""
        report = {
            "model": "test",
            "engines": {
                "eng": {"median_tok_s": 50, "median_ttft_ms": 0, "stability": "", "vram_bytes": 0}
            },
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


# ===========================================================================
# Layout tests — verify positioning invariants, not exact pixel values
# ===========================================================================

# --- Scenario fixtures ---

_S0 = _make_report(model="", engines={}, winner=None)

_S1 = _make_report(engines={"ollama": _make_engine(tok_s=48.0)})

_S1_POWER = (
    _make_report(engines={"ollama": _make_engine(tok_s=48.0)}),
    {"ollama": {"avg_watts": 20.3, "avg_eff": 2.29}},
)

_S1_UNSTABLE = _make_report(engines={"ollama": _make_engine(tok_s=48.0, stability="unstable")})

_S2 = _make_report(
    engines={
        "lmstudio": _make_engine(tok_s=72.6, ttft_ms=280, vram_bytes=0),
        "ollama": _make_engine(tok_s=30.4, ttft_ms=250, vram_bytes=26_000_000_000),
    },
    winner={"name": "lmstudio", "tok_s_delta": "2.4x faster", "vram_delta": ""},
)

_S2_POWER = (
    _make_report(
        engines={
            "lmstudio": _make_engine(tok_s=72.6, ttft_ms=280),
            "ollama": _make_engine(tok_s=30.4, ttft_ms=250),
        },
        winner={"name": "lmstudio", "tok_s_delta": "2.4x faster"},
    ),
    {"lmstudio": {"avg_watts": 42, "avg_eff": 1.7}, "ollama": {"avg_watts": 20, "avg_eff": 1.5}},
    {"lmstudio": "Q4_K_M", "ollama": "Q5_K_S"},
)

_S2_MIXED_STABILITY = _make_report(
    engines={
        "lmstudio": _make_engine(tok_s=72.6, stability="stable"),
        "ollama": _make_engine(tok_s=30.4, stability="unstable"),
    },
    winner={"name": "lmstudio", "tok_s_delta": "2.4x faster"},
)

_S3 = _make_report(
    engines={
        "lmstudio": _make_engine(tok_s=72.6),
        "ollama": _make_engine(tok_s=30.4),
        "llamacpp": _make_engine(tok_s=45.0),
    },
    winner={"name": "lmstudio", "tok_s_delta": "1.6x faster"},
)

_S4 = _make_report(
    engines={
        "lmstudio": _make_engine(tok_s=72.6),
        "ollama": _make_engine(tok_s=30.4),
        "llamacpp": _make_engine(tok_s=45.0),
        "omlx": _make_engine(tok_s=55.0),
    },
    winner={"name": "lmstudio", "tok_s_delta": "1.3x faster"},
)

_S5 = _make_report(
    engines={
        "lmstudio": _make_engine(tok_s=72.6),
        "ollama": _make_engine(tok_s=30.4),
        "llamacpp": _make_engine(tok_s=45.0),
        "omlx": _make_engine(tok_s=55.0),
        "vllm": _make_engine(tok_s=60.0),
    },
    winner={"name": "lmstudio", "tok_s_delta": "1.2x faster"},
)


class TestCardLayoutRegression:
    """P0 — Anti-regression: the single-engine overlap bug must never return."""

    def test_single_engine_hero_above_chips(self):
        svg = generate_card_svg(_S1)
        hero_y = _extract_hero_y(svg)
        chip_ys = _extract_chip_ys(svg)
        assert hero_y is not None, "Hero number missing for single engine"
        assert chip_ys, "No metric chips found"
        assert hero_y < min(chip_ys), (
            f"Hero y={hero_y} overlaps first chip y={min(chip_ys)}"
        )

    def test_hero_above_chips_all_scenarios(self):
        scenarios = [
            ("S1", generate_card_svg(_S1)),
            ("S1_power", generate_card_svg(_S1_POWER[0], power_data=_S1_POWER[1])),
            ("S2", generate_card_svg(_S2)),
            ("S3", generate_card_svg(_S3)),
            ("S4", generate_card_svg(_S4)),
        ]
        for name, svg in scenarios:
            hero_y = _extract_hero_y(svg)
            chip_ys = _extract_chip_ys(svg)
            if hero_y is not None and chip_ys:
                assert hero_y < min(chip_ys), (
                    f"{name}: hero y={hero_y} overlaps first chip y={min(chip_ys)}"
                )

    def test_frame_bottom_contains_all_chips(self):
        cases = [
            ("S1", generate_card_svg(_S1)),
            ("S2", generate_card_svg(_S2)),
            ("S4", generate_card_svg(_S4)),
        ]
        for name, svg in cases:
            _, frame_bottom = _extract_frame_bounds(svg)
            chip_ys = _extract_chip_ys(svg)
            if chip_ys:
                last_chip_bottom = max(chip_ys) + 28  # chip height
                assert last_chip_bottom <= frame_bottom, (
                    f"{name}: chip bottom {last_chip_bottom} exceeds frame {frame_bottom}"
                )

    def test_footer_below_frame(self):
        for name, report in [("S0", _S0), ("S1", _S1), ("S2", _S2), ("S4", _S4)]:
            svg = generate_card_svg(report)
            _, frame_bottom = _extract_frame_bounds(svg)
            footer_y = _extract_footer_y(svg)
            assert footer_y is not None, f"{name}: footer missing"
            assert footer_y >= frame_bottom, (
                f"{name}: footer y={footer_y} inside frame (bottom={frame_bottom})"
            )

    def test_footer_within_canvas(self):
        all_reports = [_S0, _S1, _S2, _S3, _S4, _S5, _S1_UNSTABLE]
        for report in all_reports:
            svg = generate_card_svg(report)
            footer_y = _extract_footer_y(svg)
            if footer_y is not None:
                assert footer_y + 28 <= 630, f"Footer spills below canvas: y={footer_y}"

    def test_single_engine_frame_compact(self):
        svg = generate_card_svg(_S1)
        _, frame_bottom = _extract_frame_bounds(svg)
        assert frame_bottom < 480, (
            f"Single-engine frame too tall: bottom={frame_bottom}, expected <480"
        )


class TestCardLayoutOrdering:
    """P1 — Visual hierarchy: elements must appear in correct top-to-bottom order."""

    def test_vertical_order_two_engines(self):
        svg = generate_card_svg(_S2)
        frame_top, frame_bottom = _extract_frame_bounds(svg)
        bars = _extract_bar_rects(svg)
        hero_y = _extract_hero_y(svg)
        chip_ys = _extract_chip_ys(svg)
        footer_y = _extract_footer_y(svg)

        assert bars, "No bars found"
        first_bar_y = bars[0][0]
        last_bar_y = bars[-1][0]

        assert frame_top < first_bar_y, "Bars above frame top"
        assert last_bar_y < hero_y, "Hero above last bar"
        if chip_ys:
            assert hero_y < min(chip_ys), "Chips above hero"
            assert max(chip_ys) < frame_bottom, "Chips below frame"
        assert frame_bottom <= footer_y, "Footer inside frame"

    def test_vertical_order_single_engine(self):
        svg = generate_card_svg(_S1)
        frame_top, frame_bottom = _extract_frame_bounds(svg)
        bars = _extract_bar_rects(svg)
        hero_y = _extract_hero_y(svg)
        chip_ys = _extract_chip_ys(svg)
        footer_y = _extract_footer_y(svg)

        assert len(bars) == 1
        assert frame_top < bars[0][0]
        assert bars[0][0] < hero_y
        if chip_ys:
            assert hero_y < min(chip_ys)
        assert frame_bottom <= footer_y

    def test_bars_sorted_by_speed_descending(self):
        svg = generate_card_svg(_S4)
        bars = _extract_bar_rects(svg)
        assert len(bars) == 4
        # Bars sorted by y ascending = sorted by speed descending
        # Wider bar = faster engine should be first (lowest y)
        widths = [w for _, w in bars]
        assert widths[0] >= max(widths), "Fastest engine bar should be widest and first"
        ys = [y for y, _ in bars]
        assert ys == sorted(ys), "Bars should be ordered top to bottom"

    def test_no_element_exceeds_canvas(self):
        for report in [_S0, _S1, _S2, _S4, _S5]:
            svg = generate_card_svg(report)
            all_y = _extract_all_y(svg)
            over = [y for y in all_y if y > 630]
            assert not over, f"Elements beyond canvas: {over}"


class TestCardColors:
    """P1 — UI: color rules for winner/loser bars and chip states."""

    def test_winner_bar_green_fill(self):
        svg = generate_card_svg(_S2)
        # First bar rect (winner) should use accent color
        m = re.search(r'<rect[^>]*rx="4"[^>]*fill="(#[0-9a-f]+)"[^>]*opacity="0\.9"', svg)
        assert m and m.group(1) == "#00d4aa", "Winner bar should be green"

    def test_loser_bar_gray_fill(self):
        svg = generate_card_svg(_S2)
        fills = re.findall(r'<rect[^>]*rx="4"[^>]*fill="(#[0-9a-f]+)"[^>]*opacity="0\.9"', svg)
        assert len(fills) >= 2
        assert fills[1] == "#4a5568", "Loser bar should be gray"

    def test_unstable_red_border(self):
        svg = generate_card_svg(_S1_UNSTABLE)
        assert 'stroke="#ef4444"' in svg, "Unstable chip should have red border"

    def test_stable_no_red(self):
        svg = generate_card_svg(_S1)
        assert "#ef4444" not in svg, "Stable card should have no red elements"

    def test_mixed_stability_only_unstable_red(self):
        svg = generate_card_svg(_S2_MIXED_STABILITY)
        assert 'stroke="#ef4444"' in svg, "Unstable engine should have red"
        assert "unstable" in svg


class TestCardChipsContent:
    """P1 — Per-engine metric chips: content and format."""

    def test_engine_version_in_label(self):
        svg = generate_card_svg(_S1, engine_versions={"ollama": "0.18.1"})
        assert "ollama v0.18.1" in svg

    def test_power_chip_format(self):
        svg = generate_card_svg(
            _S1_POWER[0], power_data=_S1_POWER[1]
        )
        # Unicode middle dot
        assert "20W" in svg
        assert "2.3" in svg or "2.29" in svg

    def test_runs_chip_only_when_multiple(self):
        single_run = _make_report(engines={"ollama": _make_engine(runs_count=1)})
        svg_single = generate_card_svg(single_run)
        assert "1 runs" not in svg_single

        multi_run = _make_report(engines={"ollama": _make_engine(runs_count=5)})
        svg_multi = generate_card_svg(multi_run)
        assert "5 runs" in svg_multi

    def test_quant_global_when_all_same(self):
        report = _make_report(
            engines={
                "lmstudio": _make_engine(tok_s=72.6),
                "ollama": _make_engine(tok_s=30.4),
            },
            winner={"name": "lmstudio", "tok_s_delta": "2.4x faster"},
        )
        svg = generate_card_svg(report, engine_quants={"lmstudio": "Q4_K_M", "ollama": "Q4_K_M"})
        # Global quant should appear once in specs area, not per-engine
        assert "Q4_K_M" in svg

    def test_quant_per_engine_when_different(self):
        report = _make_report(
            engines={
                "lmstudio": _make_engine(tok_s=72.6),
                "ollama": _make_engine(tok_s=30.4),
            },
            winner={"name": "lmstudio", "tok_s_delta": "2.4x faster"},
        )
        svg = generate_card_svg(
            report, engine_quants={"lmstudio": "Q4_K_M", "ollama": "Q5_K_S"}
        )
        assert "Q4_K_M" in svg
        assert "Q5_K_S" in svg


class TestCardEdgeCases:
    """P2 — Robustness: extreme inputs must not crash or break layout."""

    def test_five_engines_capped_at_four_bars(self):
        svg = generate_card_svg(_S5)
        bars = _extract_bar_rects(svg)
        assert len(bars) == 4, f"Expected 4 bars, got {len(bars)}"

    def test_very_long_model_name(self):
        long_name = "super-long-model-name-that-exceeds-normal-width:35b-a3b-q4_k_m"
        report = _make_report(model=long_name)
        svg = generate_card_svg(report)
        assert "<svg" in svg

    def test_same_speed_engines(self):
        report = _make_report(
            engines={
                "lmstudio": _make_engine(tok_s=50.0),
                "ollama": _make_engine(tok_s=50.0),
            },
            winner=None,
        )
        svg = generate_card_svg(report)
        assert "<svg" in svg
        bars = _extract_bar_rects(svg)
        assert len(bars) == 2

    def test_extreme_speed_ratio(self):
        report = _make_report(
            engines={
                "fast": _make_engine(tok_s=200.0),
                "slow": _make_engine(tok_s=2.0),
            },
            winner={"name": "fast", "tok_s_delta": "100.0x faster"},
        )
        svg = generate_card_svg(report)
        bars = _extract_bar_rects(svg)
        assert len(bars) == 2
        # Slow bar should still have minimum width (60px)
        slow_bar_width = min(w for _, w in bars)
        assert slow_bar_width >= 60, f"Slow bar too narrow: {slow_bar_width}px"

    def test_zero_tok_s_no_crash(self):
        report = _make_report(engines={"ollama": _make_engine(tok_s=0.0)})
        svg = generate_card_svg(report)
        assert "<svg" in svg

    def test_model_name_latest_stripped(self):
        report = _make_report(model="llama3.1:latest")
        svg = generate_card_svg(report)
        assert "Llama 3.1" in svg
        assert "LATEST" not in svg

    def test_model_name_with_tag(self):
        report = _make_report(model="qwen3.5:35b-a3b")
        svg = generate_card_svg(report)
        assert "Qwen 3.5" in svg
        assert "35B-A3B" in svg


class TestCardSocialSharing:
    """P2 — UX: OG image compatibility for Twitter/Discord embeds."""

    def test_svg_dimensions(self):
        svg = generate_card_svg(_S1)
        assert 'width="1200"' in svg
        assert 'height="630"' in svg
        assert 'viewBox="0 0 1200 630"' in svg

    def test_key_content_safe_zone(self):
        svg = generate_card_svg(_S2, hw_chip="Apple M4 Pro")
        hero_y = _extract_hero_y(svg)
        model_ys = _extract_text_y(svg, "Qwen 3.5")
        assert hero_y and 80 < hero_y < 580, f"Hero outside safe zone: y={hero_y}"
        assert model_ys and 80 < model_ys[0] < 580, "Model outside safe zone"

    def test_clip_path_present(self):
        svg = generate_card_svg(_S1)
        assert 'clip-path="url(#card-clip)"' in svg


# ===========================================================================
# Session-type tests — verify title and bar labels per session_type
# ===========================================================================


def _make_slot(
    engine: str = "ollama",
    model: str = "qwen:4b",
    median_tok_s: float = 50.0,
    avg_tok_s: float = 49.0,
    median_ttft_ms: float = 200.0,
    stability: str = "stable",
    vram_bytes: int = 0,
    runs_count: int = 3,
) -> dict:
    return {
        "engine": engine,
        "model": model,
        "median_tok_s": median_tok_s,
        "avg_tok_s": avg_tok_s,
        "median_ttft_ms": median_ttft_ms,
        "stability": stability,
        "vram_bytes": vram_bytes,
        "runs_count": runs_count,
    }


class TestCardSessionTypes:
    """Session-type handling: title and bar labels vary by engine/model/matrix."""

    def test_card_engine_session_title(self):
        """session_type='engine': title should contain the model name."""
        report = {
            "session_type": "engine",
            "slots": [
                _make_slot(engine="ollama", model="qwen:4b", median_tok_s=50.0),
                _make_slot(engine="lmstudio", model="qwen:4b", median_tok_s=30.0),
            ],
            "model": "qwen:4b",
            "winner": {"name": "ollama", "tok_s_delta": "+67% tok/s", "vram_delta": ""},
        }
        svg = generate_card_svg(report, hw_chip="Apple M4 Pro")
        # _format_model_name("qwen:4b") → "Qwen 4B"
        assert "Qwen" in svg
        assert "4B" in svg

    def test_card_engine_session_bar_labels(self):
        """session_type='engine': bars should be labeled by engine name."""
        report = {
            "session_type": "engine",
            "slots": [
                _make_slot(engine="ollama", model="qwen:4b", median_tok_s=50.0),
                _make_slot(engine="lmstudio", model="qwen:4b", median_tok_s=30.0),
            ],
            "model": "qwen:4b",
            "winner": None,
        }
        svg = generate_card_svg(report)
        # Bar labels should be engine names, not model names
        assert "ollama" in svg
        assert "lmstudio" in svg

    def test_card_model_session_title(self):
        """session_type='model': title should contain the engine name (formatted)."""
        report = {
            "session_type": "model",
            "slots": [
                _make_slot(engine="ollama", model="qwen:4b", median_tok_s=50.0),
                _make_slot(engine="ollama", model="deepseek:7b", median_tok_s=30.0),
            ],
            "winner": {"name": "qwen:4b", "tok_s_delta": "+67% tok/s", "vram_delta": ""},
        }
        svg = generate_card_svg(report, hw_chip="Apple M4 Pro")
        # _format_model_name("ollama") → "Ollama"
        assert "Ollama" in svg

    def test_card_model_session_bar_labels(self):
        """session_type='model': bars should be labeled by model name."""
        report = {
            "session_type": "model",
            "slots": [
                _make_slot(engine="ollama", model="qwen:4b", median_tok_s=50.0),
                _make_slot(engine="ollama", model="deepseek:7b", median_tok_s=30.0),
            ],
            "winner": None,
        }
        svg = generate_card_svg(report)
        # _format_model_name("qwen:4b") → "Qwen 4B"
        # _format_model_name("deepseek:7b") → "Deepseek 7B"
        assert "Qwen" in svg
        assert "4B" in svg
        assert "Deepseek" in svg
        assert "7B" in svg

    def test_card_matrix_session_title(self):
        """session_type='matrix': title should be 'Cross-model benchmark'."""
        report = {
            "session_type": "matrix",
            "slots": [
                _make_slot(engine="ollama", model="qwen:4b", median_tok_s=50.0),
                _make_slot(engine="lmstudio", model="deepseek:7b", median_tok_s=30.0),
            ],
            "winner": None,
        }
        svg = generate_card_svg(report, hw_chip="Apple M4 Pro")
        assert "Cross-model benchmark" in svg

    def test_card_matrix_session_bar_labels(self):
        """session_type='matrix': bars should be labeled 'model / engine'."""
        report = {
            "session_type": "matrix",
            "slots": [
                _make_slot(engine="ollama", model="qwen:4b", median_tok_s=50.0),
                _make_slot(engine="lmstudio", model="deepseek:7b", median_tok_s=30.0),
            ],
            "winner": None,
        }
        svg = generate_card_svg(report)
        # _format_model_name("qwen:4b") + " / " + "ollama" → "Qwen 4B / ollama"
        assert "Qwen 4B / ollama" in svg
        assert "Deepseek 7B / lmstudio" in svg
