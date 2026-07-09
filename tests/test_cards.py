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


class TestAuditRegressions:
    def test_no_winner_without_validity_data_has_no_fabricated_gate(self):
        """HIGH: winner=None on an old/zero-tok payload must NOT claim the
        validity gate fired — no gate chip, honest generic note."""
        payload = _standard_payload()
        payload["benchmark"]["winner"] = None
        payload["benchmark"]["engines"]["llamacpp"]["ci95"] = [60.0, 64.0]
        svg = _svg("standard", payload)
        assert "output_validity" not in svg
        assert "no winner declared" in svg
        # wrap_text may split the phrase across lines — assert the word
        assert "unavailable" in svg or "refused" in svg

    def test_no_winner_with_validity_data_names_the_gate(self):
        payload = _standard_payload()
        payload["benchmark"]["winner"] = None
        payload["benchmark"]["engines"]["llamacpp"]["ci95"] = [60.0, 64.0]
        payload["benchmark"]["engines"]["ollama"]["output_valid_pct"] = 40.0
        # 95% is ABOVE the ranking gate's threshold (80) — rankable, and
        # must not be branded invalid alongside the real offender.
        payload["benchmark"]["engines"]["llamacpp"]["output_valid_pct"] = 95.0
        svg = _svg("standard", payload)
        assert "✗ output_validity" in svg
        assert "invalid ✗" in svg
        assert "1 of 2 engines produced invalid output" in svg

    def test_tie_hero_carries_n(self):
        payload = _standard_payload()
        payload["benchmark"]["engines"]["ollama"]["ci95"] = [51.0, 60.0]
        svg = _svg("standard", payload)
        assert "n=6 runs each" in svg

    def test_dense_quality_with_notice_strip_clears_gates_divider(self):
        """IMPORTANT: 6 suites + judge-offline strip must not cross y=424."""
        import re

        payload = _code_payload()
        payload["code_results"].update(
            {
                "tool_call_stress": {"pct_clean": 80.0},
                "recovery": {"pct_recovered": 70.0},
                "thinking": {"pct_no_think_leak": 95.0},
                "coding": {"tasks": [{"task": "a", "judge": {}, "transcript": []}]},
                "coding_hard": {"tasks": [{"task": "b", "judge": {}, "transcript": []}]},
            }
        )
        svg = _svg("code", payload)
        bar_ys = [
            float(m.group(1))
            for m in re.finditer(r'<rect x="482" y="([0-9.]+)" width="[0-9.]+" height="18"', svg)
        ]
        assert bar_ys, "no suite bars rendered"
        assert max(bar_ys) + 18 <= 424, f"suite bar crosses the GATES divider: {max(bar_ys)}"

    def test_burst_four_sizes_clear_gates_divider(self):
        import re

        payload = {
            "engine": "llamacpp",
            "model": "m",
            "started_at": 1783900000,
            "burst_sizes": [10, 20, 40, 60],
            "results": {
                str(n): {
                    "latency_ms": {
                        "p50": 100.0 * n,
                        "p95": 200.0 * n,
                        "p99": 300.0 * n,
                        "max": 400.0 * n,
                    },
                    "errors_count": 0,
                }
                for n in (10, 20, 40, 60)
            },
        }
        svg = _svg("burst", payload)
        bar_ys = [
            float(m.group(1))
            for m in re.finditer(r'<rect x="482" y="([0-9.]+)" width="[0-9.]+" height="12"', svg)
        ]
        assert bar_ys and max(bar_ys) + 12 <= 424, f"burst bar crosses the divider: {max(bar_ys)}"

    def test_more_than_six_suites_disclose_truncation(self):
        blocks = (
            "verifiable",
            "research_brief",
            "research_brief_deep",
            "order_control",
            "loop_search_short",
            "loop_search_unconfirmable",
            "honesty_audit",
            "multi_file_scope",
            "constraint_preservation",
        )
        payload = {
            "engine": "e",
            "model": "m",
            "started_at": 1783900000,
            "instruct_results": {
                name: {"pct_primary_delivered": 50.0 + i, "prompts_scored": 5}
                for i, name in enumerate(blocks)
            },
        }
        svg = _svg("instruct", payload)
        assert "+3 more suites — see report" in svg


class TestTieConsistency:
    def test_persist_headline_mirrors_tie(self):
        """IMPORTANT: a tie must not persist a winner_-labeled headline
        next to a no-winner report."""
        from asiai.benchmark.persist import extract_headline

        payload = _standard_payload()
        payload["benchmark"]["engines"]["ollama"]["ci95"] = [51.0, 60.0]
        score, label, _ = extract_headline("standard", payload)
        assert label == "best_median_tok_s"
        assert score == 62.4

    def test_inverted_ci95_still_detects_tie(self):
        from asiai.benchmark.result_model import build_result

        payload = _standard_payload()
        payload["benchmark"]["engines"]["ollama"]["ci95"] = [60.0, 51.0]  # malformed order
        r = build_result("standard", payload)
        assert r.co_leaders == ["llamacpp", "ollama"]


class TestEscaping:
    def test_hostile_model_name_is_escaped(self):
        payload = _standard_payload()
        payload["benchmark"]["model"] = 'evil<script>"&'
        svg = _svg("standard", payload)  # ET parse would fail on raw <script>
        assert "<script>" not in svg
        assert "&lt;script&gt;" in svg
