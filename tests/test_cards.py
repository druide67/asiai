"""Tests for the adaptive card family — structure + honesty invariants."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from asiai.benchmark.cards import generate_card
from asiai.benchmark.result_model import build_result
from tests.test_result_model import (
    _ALL,
    _agentic_payload,
    _code_payload,
    _standard_payload,
)


def _svg(bench_type: str, payload: dict) -> str:
    svg = generate_card(build_result(bench_type, payload))
    # stdlib ET is safe here: the input is OUR OWN generator's output in the
    # same process (no external entities, not attacker-controlled) — this is
    # a well-formedness assertion, not parsing of untrusted XML.
    ET.fromstring(svg)
    return svg


class TestEveryType:
    @pytest.mark.parametrize("bench_type", sorted(_ALL))
    def test_renders_valid_svg_with_mandatory_chrome(self, bench_type):
        svg = _svg(bench_type, _ALL[bench_type]())
        # The honesty chrome is non-negotiable on every card (spec §5).
        assert "CONDITIONS" in svg
        assert "asiai.dev" in svg
        assert 'viewBox="0 0 1200 630"' in svg

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError):
            generate_card(
                build_result("standard", {}).__class__(  # type: ignore[call-arg]
                    bench_type="nope", title="", subjects=[], winner=None
                )
            )


class TestThroughputStates:
    def test_winner_card(self):
        svg = _svg("standard", _standard_payload())
        assert "llamacpp b9580 wins" in svg
        assert "n=6 runs" in svg
        assert "±4.3 CI95" in svg

    def test_single_engine_no_crown(self):
        payload = _standard_payload()
        del payload["benchmark"]["engines"]["ollama"]
        payload["benchmark"]["winner"] = None
        svg = _svg("standard", payload)
        assert "single engine — no comparison" in svg
        assert "not a ranking" in svg
        assert "wins" not in svg

    def test_tie_within_ci95(self):
        payload = _standard_payload()
        payload["benchmark"]["engines"]["ollama"]["ci95"] = [51.0, 60.0]
        svg = _svg("standard", payload)
        assert ">TIE</text>" in svg
        assert "whisker" in svg  # legend present
        assert "tie: Δ" in svg
        assert "wins" not in svg  # no crown language on a withheld ranking

    def test_no_winner_amber_state(self):
        payload = _standard_payload()
        payload["benchmark"]["winner"] = None
        payload["benchmark"]["engines"]["llamacpp"]["ci95"] = [60.0, 64.0]  # no overlap
        svg = _svg("standard", payload)
        assert "no winner declared" in svg
        assert "#f59e0b" in svg  # amber rail
        assert "tok/s shown for transparency" in svg


class TestQualityStates:
    def test_thresholds_color_bars(self):
        svg = _svg("code", _code_payload())
        assert "#10b981" in svg  # 90% → green

    def test_judge_offline_dashed_placeholder(self):
        payload = _code_payload()
        payload["code_results"]["coding"] = {
            "tasks": [{"task": "lru", "judge": {}, "transcript": []}]
        }
        svg = _svg("code", payload)
        assert "judge: offline" in svg
        assert 'stroke-dasharray="4 3"' in svg  # ungraded ≠ zero (spec §5)
        assert "not graded — judge offline" in svg

    def test_judged_score_labeled(self):
        payload = _code_payload()
        payload["code_results"]["coding"] = {
            "tasks": [{"task": "lru", "judge": {"scores": {"correctness": 8}}, "transcript": []}]
        }
        svg = _svg("code", payload)
        # The card shows the pass badge; the judged-count detail lives in
        # the markdown report (asserted in test_result_model).
        assert "✓ coding_judge" in svg
        assert "80%" in svg  # graded suite carries its scaled, labeled score


class TestAgentic:
    def test_gates_always_render(self):
        svg = _svg("agentic", _agentic_payload())
        assert "✗ early_stop" in svg  # failed gate visible
        assert "✓ memory_pressure" in svg  # PASSED gate visible too (spec §5)
        assert "REUSED" in svg


class TestEscaping:
    def test_hostile_model_name_is_escaped(self):
        payload = _standard_payload()
        payload["benchmark"]["model"] = 'evil<script>"&'
        svg = _svg("standard", payload)  # ET parse would fail on raw <script>
        assert "<script>" not in svg
        assert "&lt;script&gt;" in svg
