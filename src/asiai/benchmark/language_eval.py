"""``asiai bench --language <code>`` — multilingual retention / regression eval.

Measures whether a model *stayed in* a target language and kept its orthography —
the catastrophic-forgetting failure modes a finetune (e.g. an Opus-distilled
coding finetune) can introduce. Deterministic, dependency-free:

* **adherence** — does the model answer IN the target language? Latin scripts:
  ratio of target-language function words to English ones (drift to English
  flips it). Non-Latin (ja/ko/zh): fraction of characters in the target script.
  Plus a non-degeneracy check.
* **diacritics** (Latin accented languages) — trap prompts whose correct answer
  MUST contain specific accented tokens (``café``, ``préféré``); an ASCII-stripped
  answer (``cafe``) fails, and is flagged distinctly from "didn't answer". Plus an
  accent-density floor (target-language text at ~0 accents ⇒ stripped).
* **fluency** (optional judge) — fluency / idiom / anglicisms / grammar, 1-5, via
  ``--judge-url`` (any OpenAI-compat endpoint; no SDK bundled).

JSON-only (schema ``language-v1``). The headline use is the **regression delta**:
run on the finetune AND its base, diff the JSON. asiai benches one target at a
time, so cross-model comparison is by diffing files (the asiai idiom).
"""

from __future__ import annotations

import re
import time
from typing import Any

from asiai.benchmark.code_eval import ChatResult, chat
from asiai.benchmark.language_profiles import (
    ENGLISH_STOPWORDS,
    FULLY_POPULATED,
    LanguageProfile,
    get_profile,
    script_char_ratio,
)
from asiai.benchmark.output_gates import check_degenerate, truncate_text
from asiai.collectors.system import collect_run_metadata

SCHEMA_VERSION = "language-v1"
ALL_SUITES = ("adherence", "diacritics", "fluency")
DEFAULT_SUITES = ("adherence", "diacritics")  # deterministic, no judge

_LETTERS_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

LANGUAGE_JUDGE_SYSTEM = (
    "You are a strict native-speaker language reviewer. You grade ONE assistant's "
    "responses for naturalness in a target language, judging only the evidence shown."
)


def _adherence_ratio(text: str, profile: LanguageProfile) -> float:
    """Signal in [0,1] that ``text`` is in the profile's language.

    Non-Latin: fraction of content chars in the target script. Latin: target
    function words / (target + English function words) — robust to drift.
    """
    if profile.script:
        return script_char_ratio(text, profile.script)
    words = _LETTERS_RE.findall(text.lower())
    # Count as "English drift" only words that are English-ONLY: a word in both
    # sets (e.g. Spanish/English "no", Portuguese "a") is genuine target text, not
    # drift — counting it in both would suppress the ratio toward 0.5.
    english_only = ENGLISH_STOPWORDS - profile.stopwords
    tgt = sum(1 for w in words if w in profile.stopwords)
    eng = sum(1 for w in words if w in english_only)
    total = tgt + eng
    return round(tgt / total, 3) if total else 0.0


def _accent_density(text: str) -> float:
    """Accented letters / total letters (orthography health for Latin languages)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    accented = sum(1 for c in letters if not c.isascii())
    return round(accented / len(letters), 4)


def _pct(flags: list[bool]) -> float | None:
    return round(100.0 * sum(1 for f in flags if f) / len(flags), 1) if flags else None


def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 3) if xs else None


def _run_adherence(
    base_url: str,
    model: str,
    profile: LanguageProfile,
    *,
    extra_body: dict[str, Any] | None,
    timeout: int,
    on_progress: Any,
) -> dict[str, Any]:
    prompts = list(profile.probes)
    if profile.code_comment_prompt:
        prompts.append(profile.code_comment_prompt)
    per_probe: list[dict[str, Any]] = []
    for i, prompt in enumerate(prompts):
        res: ChatResult = chat(
            base_url,
            model,
            [{"role": "user", "content": prompt}],
            max_tokens=512,
            extra_body=extra_body,
            timeout=timeout,
        )
        ratio = _adherence_ratio(res.text or "", profile)
        degen = check_degenerate(res.text or "")["degenerate"] if res.error is None else True
        density = _accent_density(res.text or "")
        # Accent-density floor (announced in the module docstring): clean
        # target-language text at near-zero accent density means the model
        # answered in ASCII-stripped orthography. Only meaningful when the
        # answer IS in-language and non-degenerate.
        stripped = (
            density < profile.min_accent_density
            if profile.min_accent_density is not None and ratio >= 0.5 and not degen
            else False
        )
        per_probe.append(
            {
                "adherence_ratio": ratio,
                "in_language": ratio >= 0.5,
                "degenerate": degen,
                "accent_density": density,
                "accent_stripped": stripped,
                "error": res.error,
                "text": truncate_text(res.text or ""),
            }
        )
        if on_progress:
            on_progress(
                f"  [language:adherence {i + 1}/{len(prompts)}] "
                f"ratio={ratio} in_lang={ratio >= 0.5} accent={density}"
            )
    clean = [p for p in per_probe if not p["error"]]
    return {
        "probes": len(per_probe),
        "pct_in_language": _pct([p["in_language"] for p in clean]),
        "mean_adherence_ratio": _mean([p["adherence_ratio"] for p in clean]),
        "pct_non_degenerate": _pct([not p["degenerate"] for p in clean]),
        "mean_accent_density": _mean([p["accent_density"] for p in clean]),
        "pct_accent_stripped": _pct([p["accent_stripped"] for p in clean]),
        "per_probe": per_probe,
    }


def _run_diacritics(
    base_url: str,
    model: str,
    profile: LanguageProfile,
    *,
    extra_body: dict[str, Any] | None,
    timeout: int,
    on_progress: Any,
) -> dict[str, Any]:
    if not profile.diacritic_traps:
        return {
            "skipped": f"no diacritic traps for '{profile.code}' (non-Latin or not yet populated)"
        }
    per_trap: list[dict[str, Any]] = []
    for i, trap in enumerate(profile.diacritic_traps):
        res = chat(
            base_url,
            model,
            [{"role": "user", "content": trap["prompt"]}],
            max_tokens=256,
            extra_body=extra_body,
            timeout=timeout,
        )
        low = (res.text or "").lower()
        want = trap["must_contain"]
        present = [tok for tok in want if tok.lower() in low]
        # ASCII-stripped = the unaccented form is there but the accented isn't.
        stripped = [
            tok for tok in want if tok.lower() not in low and _strip_accents(tok.lower()) in low
        ]
        passed = len(present) == len(want)
        per_trap.append(
            {
                "prompt": trap["prompt"],
                "must_contain": want,
                "present": present,
                "ascii_stripped": stripped,
                "passed": passed,
                "error": res.error,
                "text": truncate_text(res.text or ""),
            }
        )
        if on_progress:
            on_progress(
                f"  [language:diacritics {i + 1}/{len(profile.diacritic_traps)}] "
                f"passed={passed} stripped={stripped}"
            )
    clean = [t for t in per_trap if not t["error"]]
    return {
        "traps": len(per_trap),
        "pct_traps_passed": _pct([t["passed"] for t in clean]),
        "count_ascii_stripped": sum(len(t["ascii_stripped"]) for t in per_trap),
        "per_trap": per_trap,
    }


def _strip_accents(s: str) -> str:
    import unicodedata

    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _run_fluency_judge(
    adherence: dict[str, Any],
    profile: LanguageProfile,
    *,
    judge_url: str | None,
    judge_model: str | None,
    judge_api_key: str | None,
    timeout: int,
) -> dict[str, Any]:
    if not (judge_url and judge_model):
        return {"skipped": "no --judge-url (responses captured for offline judging)"}
    samples = "\n\n".join(
        f"PROMPT/RESPONSE {i + 1}:\n{p['text']}"
        for i, p in enumerate(adherence.get("per_probe", []))
        if not p["error"]
    )
    rubric = (
        f"Grade the assistant's {profile.name} ({profile.native_name}) on each "
        "criterion as an integer 1-5 (5 = native): (1) fluency, (2) grammar, "
        "(3) idiom (no anglicisms/calques), (4) orthography (accents/diacritics). "
        'Respond ONLY as JSON: {"fluency":n,"grammar":n,"idiom":n,"orthography":n,'
        '"overall":n,"reason":"one sentence"}.'
    )
    res = chat(
        judge_url,
        judge_model,
        [
            {"role": "system", "content": LANGUAGE_JUDGE_SYSTEM},
            {"role": "user", "content": f"{rubric}\n\nRESPONSES:\n{samples}"},
        ],
        max_tokens=512,
        temperature=0.0,
        api_key=judge_api_key,
        timeout=timeout,
        stream=False,
    )
    if res.error is not None:
        return {"error": f"{res.error}: {res.error_body}", "judge_model": judge_model}
    import json

    text = (res.text or "").strip()
    start, end = text.find("{"), text.rfind("}")
    parsed = None
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            parsed = None
    return {
        "judge_model": judge_model,
        "scores": parsed or {},
        "raw": truncate_text(res.text or ""),
    }


def run_language_eval(
    base_url: str,
    engine_name: str,
    model: str,
    *,
    language: str,
    suites: tuple[str, ...] | list[str] = DEFAULT_SUITES,
    extra_body: dict[str, Any] | None = None,
    judge_url: str | None = None,
    judge_model: str | None = None,
    judge_api_key: str | None = None,
    timeout: int = 900,
    out_path: str | None = None,
    include_host: bool = False,
    engine_version: str = "",
    on_progress: Any = None,
) -> dict[str, Any]:
    """Run multilingual-retention suites for ``language`` → ``language-v1`` dict.

    Raises ``ValueError`` for an unknown language code. ``suites`` ⊆
    {adherence, diacritics, fluency}; the first two are deterministic.
    """
    profile = get_profile(language)
    if profile is None:
        raise ValueError(f"unknown language '{language}'")
    started = int(time.time())
    requested = [s for s in suites if s in ALL_SUITES]
    results: dict[str, Any] = {}

    adherence = None
    if "adherence" in requested or "fluency" in requested:
        adherence = _run_adherence(
            base_url,
            model,
            profile,
            extra_body=extra_body,
            timeout=timeout,
            on_progress=on_progress,
        )
        if "adherence" in requested:
            results["adherence"] = adherence
    if "diacritics" in requested:
        results["diacritics"] = _run_diacritics(
            base_url,
            model,
            profile,
            extra_body=extra_body,
            timeout=timeout,
            on_progress=on_progress,
        )
    if "fluency" in requested:
        results["fluency"] = _run_fluency_judge(
            adherence or {},
            profile,
            judge_url=judge_url,
            judge_model=judge_model,
            judge_api_key=judge_api_key,
            timeout=timeout,
        )

    out = {
        "schema_version": SCHEMA_VERSION,
        "language": profile.code,
        "language_name": profile.name,
        "fully_populated": profile.code in FULLY_POPULATED,
        "engine": engine_name,
        "model": model,
        "base_url": base_url,
        "started_at": started,
        "finished_at": int(time.time()),
        "suites": requested,
        "extra_body": extra_body or {},
        "language_results": results,
    }
    out.update(
        collect_run_metadata(
            engine_version=engine_version, bench_mode="language", include_host=include_host
        )
    )
    if out_path:
        import json

        with open(out_path, "w") as f:
            json.dump(out, f, indent=2)
    return out


__all__ = ["ALL_SUITES", "DEFAULT_SUITES", "SCHEMA_VERSION", "run_language_eval"]
