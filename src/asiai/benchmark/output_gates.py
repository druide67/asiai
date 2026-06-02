"""Deterministic output-validity gates for benchmarks.

Throughput measures how FAST an engine emits tokens, not whether the tokens are
correct. A mis-quantised model, a wrong chat template, or a thinking-loop can
stream garbage at high tok/s and score "excellent". These cheap, deterministic
checks (no extra model calls, no judge LLM) flag degenerate output so a result
below a validity threshold can be refused a ranking — fast garbage is not a win.
"""

from __future__ import annotations

import re
from collections import Counter

# Truncate stored output text to keep result JSON compact; degeneracy is
# detectable well within this window.
MAX_STORED_TEXT = 2000

# An engine whose output passes the gates on fewer than this share of runs is
# refused a ranking by consumers (see reporter winner selection).
DEFAULT_MIN_VALID_PCT = 80.0


def truncate_text(text: str, limit: int = MAX_STORED_TEXT) -> str:
    """Clip text to ``limit`` chars for storage (degeneracy shows up early)."""
    return text if len(text) <= limit else text[:limit]


def check_degenerate(text: str, *, min_chars: int = 1) -> dict[str, object]:
    """Flag degenerate generations with cheap deterministic heuristics.

    Returns ``{"degenerate": bool, "reason": str | None}``. Detects:
      - empty / whitespace-only output (e.g. a thinking-loop that never emits
        user-facing content);
      - extreme n-gram repetition (a stuck decoding loop);
      - very low word diversity over a long output (garbage filler).
    """
    stripped = text.strip()
    if len(stripped) < min_chars:
        return {"degenerate": True, "reason": "empty"}

    words = stripped.split()
    if len(words) >= 20:
        trigrams = [tuple(words[i : i + 3]) for i in range(len(words) - 2)]
        if trigrams:
            _, count = Counter(trigrams).most_common(1)[0]
            if count / len(trigrams) > 0.3:
                return {"degenerate": True, "reason": "ngram_repetition"}
        if len(set(words)) / len(words) < 0.15:
            return {"degenerate": True, "reason": "low_diversity"}

    return {"degenerate": False, "reason": None}


_NUMBER_RE = re.compile(r"-?\d[\d,]*")


def check_arithmetic(text: str, expected: int) -> bool:
    """Exact-match a known integer answer anywhere in the output.

    Burst prompts ask for a single integer with a deterministic answer, giving
    a free correctness signal. Commas are stripped so ``12,352`` matches 12352.
    """
    for m in _NUMBER_RE.finditer(text):
        try:
            if int(m.group().replace(",", "")) == expected:
                return True
        except ValueError:
            continue
    return False


def output_valid_pct(flags: list[bool]) -> float:
    """Percentage (0.0-100.0) of runs whose output passed the gates."""
    if not flags:
        return 0.0
    return round(100.0 * sum(1 for f in flags if f) / len(flags), 1)
