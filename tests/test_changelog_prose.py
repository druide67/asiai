"""[Unreleased] entries must read as a changelog, not as a journal.

Bounded mechanically: a bullet says what changed for the user, in ≤ 40 words,
with no date and no narrative marker. History belongs in commit messages.
"""

from __future__ import annotations

import re
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
MAX_WORDS = 40
NARRATIVE = re.compile(
    r"\b(review|campaign|incident|used to|until 20\d\d|we |our |I |this morning|last week)\b", re.I
)
DATE = re.compile(r"\b20\d\d-\d\d-\d\d\b")


def _unreleased_bullets() -> list[str]:
    text = CHANGELOG.read_text()
    m = re.search(r"^## \[Unreleased\]\n(.*?)(?=^## \[)", text, re.M | re.S)
    assert m, "no [Unreleased] section"
    return [b.strip() for b in re.findall(r"(?ms)^- (.*?)(?=^- |^### |\Z)", m.group(1))]


def test_unreleased_bullets_are_short():
    long = [(len(b.split()), b[:60]) for b in _unreleased_bullets() if len(b.split()) > MAX_WORDS]
    assert not long, f"bullets over {MAX_WORDS} words: {long}"


def test_unreleased_bullets_carry_no_dates_or_narrative():
    bad = [b[:70] for b in _unreleased_bullets() if DATE.search(b) or NARRATIVE.search(b)]
    assert not bad, f"dates or narrative in changelog bullets: {bad}"
