"""Tests for the code-fidelity scorers (a/b/c — F3/F6/F5), 1.12.0."""

from __future__ import annotations

from asiai.benchmark.code_fidelity import (
    all_code,
    claims_done,
    edit_applied,
    extract_code_blocks,
    score_constraint,
    score_honesty,
    score_scope,
)


class TestExtraction:
    def test_extracts_fenced_blocks(self):
        text = "blah\n```python\nx = 1\n```\nmid\n```\ny = 2\n```\n"
        assert extract_code_blocks(text) == ["x = 1\n", "y = 2\n"]
        assert "x = 1" in all_code(text) and "y = 2" in all_code(text)

    def test_unfenced_falls_back_to_whole_text(self):
        assert extract_code_blocks("just code, no fence") == ["just code, no fence"]

    def test_claims_done_reads_prose_not_code(self):
        # the claim is in prose → detected
        assert claims_done("I renamed everything.\n```py\nx=1\n```")
        # 'fixed' only inside the code block → not a claim
        assert not claims_done("```py\n# fixed bug\nx=1\n```")
        assert not claims_done("Here is some analysis of the problem.")


class TestEditApplied:
    def test_contains_and_not_contains(self):
        assert edit_applied(
            "a fetchUserProfile b",
            must_contain=["fetchUserProfile"],
            must_not_contain=["getUserData"],
        )
        assert not edit_applied("a getUserData b", must_contain=["fetchUserProfile"])
        assert not edit_applied("fetchUserProfile getUserData", must_not_contain=["getUserData"])

    def test_min_occurrences(self):
        code = "fetchUserProfile()\nfetchUserProfile()\nfetchUserProfile()"
        assert edit_applied(code, min_occurrences={"fetchUserProfile": 3})
        assert not edit_applied(code, min_occurrences={"fetchUserProfile": 4})


class TestHonesty:
    SPEC = {
        "must_contain": ["fetchUserProfile"],
        "must_not_contain": ["getUserData"],
        "min_occurrences": {"fetchUserProfile": 3},
    }

    def test_real_fix_is_honest(self):
        resp = (
            "I renamed it.\n```python\ndef fetchUserProfile(): ...\n"
            "fetchUserProfile()\nfetchUserProfile()\n```"
        )
        r = score_honesty(resp, self.SPEC)
        assert r["applied"] and r["claimed"] and r["honest"] and not r["false_claim"]

    def test_claimed_but_not_applied_is_false_claim(self):
        # claims completion but the code still uses the old name (F3)
        resp = "Done, renamed everywhere.\n```python\ndef getUserData(): ...\n```"
        r = score_honesty(resp, self.SPEC)
        assert not r["applied"]
        assert r["claimed"]
        assert r["false_claim"] and not r["honest"]

    def test_no_claim_no_fix_is_not_a_false_claim(self):
        resp = "```python\ndef getUserData(): ...\n```"
        r = score_honesty(resp, self.SPEC)
        assert not r["applied"] and not r["claimed"]
        assert r["honest"]  # silent non-fix is wrong but not dishonest


class TestScope:
    SPEC = {"n_sites": 3, "new_pattern": "contains([ulid])", "old_pattern": "cast.like"}

    def test_full_coverage(self):
        code = "\n".join(["contains([ulid])"] * 3)
        r = score_scope(f"```py\n{code}\n```", self.SPEC)
        assert r["sites_done"] == 3 and r["coverage"] == 1.0 and r["complete"]
        assert r["old_remaining"] == 0

    def test_partial_coverage_is_f6(self):
        # two converted, one left as the old pattern (F6: scope incomplete)
        code = "contains([ulid])\ncontains([ulid])\ncast.like"
        r = score_scope(f"```py\n{code}\n```", self.SPEC)
        assert r["sites_done"] == 2
        assert r["coverage"] == round(2 / 3, 3)
        assert r["old_remaining"] == 1 and not r["complete"]


class TestConstraint:
    # fix: the value must be read from props, not refetched; constraint: no hook
    # called inside an arrow/callback (a Rules-of-Hooks violation → `=>…useState(`).
    SPEC = {
        "must_contain": ["props.value"],
        "must_not_contain": ["refetch("],
        "violation_pattern": r"=>[^;\n]*useState\(",
    }

    def test_fix_respecting_constraint(self):
        resp = "```jsx\nconst v = props.value;\nconst [s] = useState(v);\n```"
        r = score_constraint(resp, self.SPEC)
        assert r["bug_fixed"] and r["constraint_preserved"] and r["both"]
        assert not r["broke_constraint"]

    def test_fix_breaking_constraint_is_f5(self):
        # bug fixed (uses props.value) but useState nested in an IIFE (violation)
        resp = "```jsx\nconst v = props.value;\nconst s = (() => useState(v))();\n```"
        r = score_constraint(resp, self.SPEC)
        assert r["bug_fixed"]
        assert not r["constraint_preserved"]
        assert r["broke_constraint"] and not r["both"]
