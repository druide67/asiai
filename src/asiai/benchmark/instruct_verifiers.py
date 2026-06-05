"""Deterministic verifiers for IFEval-style instruction-following checks.

Each verifier is a pure function ``(response: str, args: dict) -> bool`` that
programmatically decides whether a response obeys one *verifiable instruction*
(write ≥N words, include keyword K, respond in JSON, no commas, …) — the
paradigm of IFEval (Zhou et al. 2023, arxiv 2311.07911, google-research,
Apache-2.0). This is an **asiai-native reimplementation** of that paradigm — no
IFEval code or data is vendored — covering a stdlib-verifiable subset of its 9
categories. No LLM judge.

Two evaluation modes, mirroring IFEval:

* **strict** — verify the response as-is.
* **loose** — verify against a handful of lightly-transformed variants (strip
  markdown emphasis, drop the first/last line, unwrap surrounding quotes) and
  pass if ANY variant obeys; cuts false negatives from formatting wrappers.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

# --- individual verifiers (one per instruction type) -------------------------


def _words(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text)


def keywords_include(response: str, args: dict[str, Any]) -> bool:
    low = response.lower()
    return all(str(k).lower() in low for k in args.get("keywords", []))


def keyword_frequency(response: str, args: dict[str, Any]) -> bool:
    kw = str(args["keyword"]).lower()
    n = len(re.findall(re.escape(kw), response.lower()))
    return _relate(n, args)


def forbidden_words(response: str, args: dict[str, Any]) -> bool:
    low = response.lower()
    return not any(str(w).lower() in low for w in args.get("forbidden", []))


def number_words(response: str, args: dict[str, Any]) -> bool:
    return _relate(len(_words(response)), args)


def number_sentences(response: str, args: dict[str, Any]) -> bool:
    n = len([s for s in re.split(r"[.!?]+", response) if s.strip()])
    return _relate(n, args)


def number_paragraphs(response: str, args: dict[str, Any]) -> bool:
    n = len([p for p in re.split(r"\n\s*\n", response.strip()) if p.strip()])
    return _relate(n, args)


def number_bullets(response: str, args: dict[str, Any]) -> bool:
    n = len(re.findall(r"(?m)^\s*[-*+]\s+\S", response))
    return _relate(n, args)


def number_sections(response: str, args: dict[str, Any]) -> bool:
    n = len(re.findall(r"(?m)^\s*#{1,6}\s+\S", response))
    return _relate(n, args)


def title(response: str, args: dict[str, Any]) -> bool:
    return bool(re.search(r"<<[^<>]+>>", response))


def json_format(response: str, args: dict[str, Any]) -> bool:
    text = response.strip()
    # tolerate a ```json fence (the loose pass also strips it)
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    try:
        json.loads(text)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def choose_from(response: str, args: dict[str, Any]) -> bool:
    opts = [str(o).strip().lower() for o in args.get("options", [])]
    return response.strip().lower() in opts


def all_lowercase(response: str, args: dict[str, Any]) -> bool:
    return not any(c.isupper() for c in response)


def all_uppercase(response: str, args: dict[str, Any]) -> bool:
    return not any(c.islower() for c in response)


def capital_word_frequency(response: str, args: dict[str, Any]) -> bool:
    n = sum(1 for w in _words(response) if len(w) > 1 and w.isupper())
    return _relate(n, args)


def no_commas(response: str, args: dict[str, Any]) -> bool:
    return "," not in response


def end_phrase(response: str, args: dict[str, Any]) -> bool:
    return response.strip().rstrip(".!?\"' ").endswith(str(args["phrase"]).rstrip(".!?\"' "))


def postscript(response: str, args: dict[str, Any]) -> bool:
    marker = str(args.get("marker", "P.S."))
    return re.search(re.escape(marker), response, re.IGNORECASE) is not None


def quotation(response: str, args: dict[str, Any]) -> bool:
    t = response.strip()
    return len(t) >= 2 and t[0] == '"' and t[-1] == '"'


def response_language(response: str, args: dict[str, Any]) -> bool:
    # Reuse the language-adherence heuristic (target-vs-English / script ratio).
    from asiai.benchmark.language_eval import _adherence_ratio
    from asiai.benchmark.language_profiles import get_profile

    profile = get_profile(str(args["language"]))
    if profile is None:
        return False
    return _adherence_ratio(response, profile) >= float(args.get("min_ratio", 0.5))


def _relate(n: int, args: dict[str, Any]) -> bool:
    """Compare a measured count ``n`` against min / max / exact bounds in args."""
    if "exact" in args:
        return n == int(args["exact"])
    ok = True
    if "min" in args:
        ok = ok and n >= int(args["min"])
    if "max" in args:
        ok = ok and n <= int(args["max"])
    return ok


# --- registry + strict/loose engine ------------------------------------------

REGISTRY: dict[str, Callable[[str, dict[str, Any]], bool]] = {
    "keywords_include": keywords_include,
    "keyword_frequency": keyword_frequency,
    "forbidden_words": forbidden_words,
    "number_words": number_words,
    "number_sentences": number_sentences,
    "number_paragraphs": number_paragraphs,
    "number_bullets": number_bullets,
    "number_sections": number_sections,
    "title": title,
    "json_format": json_format,
    "choose_from": choose_from,
    "all_lowercase": all_lowercase,
    "all_uppercase": all_uppercase,
    "capital_word_frequency": capital_word_frequency,
    "no_commas": no_commas,
    "end_phrase": end_phrase,
    "postscript": postscript,
    "quotation": quotation,
    "response_language": response_language,
}


def _loose_variants(text: str) -> list[str]:
    """Lightly-transformed variants for the loose pass (dedup, order-stable)."""
    variants: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        if s not in seen:
            seen.add(s)
            variants.append(s)

    add(text)
    no_md = text.replace("*", "").replace("_", "")
    add(no_md)
    for base in (text, no_md):
        lines = base.split("\n")
        if len(lines) > 1:
            add("\n".join(lines[1:]).strip())  # drop first line (a preamble/header)
            add("\n".join(lines[:-1]).strip())  # drop last line (a sign-off)
        add(base.strip().strip('"').strip())  # unwrap surrounding quotes
    return variants


def verify(vtype: str, response: str, args: dict[str, Any], *, loose: bool = False) -> bool:
    """Verify one instruction. ``loose=True`` passes if any variant obeys."""
    fn = REGISTRY.get(vtype)
    if fn is None:
        raise KeyError(f"unknown instruction type: {vtype}")
    if not loose:
        return fn(response, args)
    return any(fn(v, args) for v in _loose_variants(response))


def evaluate_prompt(response: str, instructions: list[dict[str, Any]]) -> dict[str, Any]:
    """Score one prompt's response against its list of ``{type, args}`` checks.

    Returns per-instruction strict/loose results plus the prompt-level booleans
    (all instructions obeyed) for both modes.
    """
    per: list[dict[str, Any]] = []
    for ins in instructions:
        vtype, args = ins["type"], ins.get("args", {})
        per.append(
            {
                "type": vtype,
                "strict": verify(vtype, response, args, loose=False),
                "loose": verify(vtype, response, args, loose=True),
            }
        )
    return {
        "instructions": per,
        "prompt_strict": all(p["strict"] for p in per) if per else False,
        "prompt_loose": all(p["loose"] for p in per) if per else False,
    }


__all__ = ["REGISTRY", "evaluate_prompt", "verify"]
