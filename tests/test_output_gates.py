"""Tests for deterministic output-validity gates."""

from __future__ import annotations

from asiai.benchmark.output_gates import (
    check_arithmetic,
    check_degenerate,
    output_valid_pct,
    truncate_text,
)


class TestCheckDegenerate:
    def test_empty_is_degenerate(self):
        assert check_degenerate("")["degenerate"] is True
        assert check_degenerate("   \n  ")["reason"] == "empty"

    def test_normal_text_is_clean(self):
        text = " ".join(f"word{i}" for i in range(50))
        assert check_degenerate(text)["degenerate"] is False

    def test_ngram_repetition_flagged(self):
        result = check_degenerate("the cat sat " * 30)
        assert result["degenerate"] is True
        assert result["reason"] == "ngram_repetition"

    def test_low_diversity_or_repetition_flagged(self):
        result = check_degenerate("spam " * 40)
        assert result["degenerate"] is True
        assert result["reason"] in {"ngram_repetition", "low_diversity"}

    def test_short_clean_text_not_flagged(self):
        # Under 20 words only the empty check applies (a short legit answer).
        assert check_degenerate("The answer is 42.")["degenerate"] is False


class TestCheckArithmetic:
    def test_exact_match(self):
        assert check_arithmetic("The answer is 86415.", 86415) is True

    def test_with_commas(self):
        assert check_arithmetic("Result: 86,415", 86415) is True

    def test_no_match(self):
        assert check_arithmetic("The answer is 99999.", 86415) is False

    def test_other_numbers_present_but_not_the_answer(self):
        assert check_arithmetic("Step 1: 12345. Final: 700", 86415) is False


class TestOutputValidPct:
    def test_all_valid(self):
        assert output_valid_pct([True, True, True]) == 100.0

    def test_partial(self):
        assert output_valid_pct([True, False, True, False]) == 50.0

    def test_empty(self):
        assert output_valid_pct([]) == 0.0


def test_truncate_text():
    assert truncate_text("abc", 10) == "abc"
    assert truncate_text("a" * 20, 10) == "a" * 10
