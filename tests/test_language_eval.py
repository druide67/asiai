"""Tests for `asiai bench --language` (multilingual retention eval, 1.12.0)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from asiai.benchmark.code_eval import ChatResult
from asiai.benchmark.language_eval import (
    _accent_density,
    _adherence_ratio,
    _strip_accents,
    run_language_eval,
)
from asiai.benchmark.language_profiles import get_profile, script_char_ratio

FR = get_profile("fr")
ZH = get_profile("zh")


class TestAdherenceRatio:
    def test_french_text_scores_high(self):
        txt = "Le café est une boisson que les gens aiment dans le monde entier."
        assert _adherence_ratio(txt, FR) > 0.8

    def test_english_drift_scores_low(self):
        txt = "The coffee is a drink that people love around the world and it is good."
        assert _adherence_ratio(txt, FR) < 0.3

    def test_non_latin_uses_script_ratio(self):
        assert _adherence_ratio("这是一个测试用例。", ZH) > 0.8
        assert _adherence_ratio("This is a test.", ZH) < 0.2

    def test_shared_stopword_not_double_counted(self):
        # Spanish "no" is also an English stopword; a pure-Spanish sentence full
        # of "no" must still score ~1.0 (the word is target text, not drift).
        es = get_profile("es")
        txt = "No es una estructura compleja. No hay duplicados. No sé por qué falla."
        assert _adherence_ratio(txt, es) > 0.9


class TestScriptRatio:
    def test_han(self):
        assert script_char_ratio("你好世界", "han") == 1.0

    def test_mixed(self):
        # 2 latin letters + 2 han letters → 0.5 (punctuation/space excluded)
        r = script_char_ratio("ab 你好!", "han")
        assert r == 0.5


class TestAccentAndStrip:
    def test_accent_density(self):
        assert _accent_density("café élève âgé") > 0.1
        assert _accent_density("cafe eleve age") == 0.0

    def test_strip_accents(self):
        assert _strip_accents("café") == "cafe"
        assert _strip_accents("préféré") == "prefere"


def _fr_good_chat(base_url, model, messages, **kw):
    """A model that answers in correct, accented French."""
    user = messages[-1]["content"]
    if "coffee" in user:
        return ChatResult(text="café", finish_reason="stop")
    if "élève préféré" in user:
        return ChatResult(text="L'élève préféré était très âgé.", finish_reason="stop")
    if "messe" in user or "église" in user:
        return ChatResult(text="église", finish_reason="stop")
    if "être" in user:
        return ChatResult(text="sommes ; étions", finish_reason="stop")
    return ChatResult(
        text="Le versionnage du code est très utile car il garde l'historique des "
        "modifications et permet de revenir en arrière facilement.",
        finish_reason="stop",
    )


def _en_drift_chat(base_url, model, messages, **kw):
    """A finetune that regressed: answers French prompts in English, no accents."""
    user = messages[-1]["content"]
    if "coffee" in user:
        return ChatResult(text="coffee", finish_reason="stop")  # didn't even translate
    if "élève préféré" in user:
        return ChatResult(text="The favorite student was very old.", finish_reason="stop")
    return ChatResult(
        text="Versioning your code is very useful because it keeps the history of "
        "changes and lets you go back easily.",
        finish_reason="stop",
    )


class TestRunLanguageEval:
    def test_unknown_language_raises(self):
        with pytest.raises(ValueError, match="unknown language"):
            run_language_eval("u", "e", "m", language="xx")

    def test_good_french_model(self):
        with (
            patch("asiai.benchmark.language_eval.chat", side_effect=_fr_good_chat),
            patch("asiai.benchmark.language_eval.collect_run_metadata", return_value={}),
        ):
            out = run_language_eval("u", "llamacpp", "qwen", language="fr")
        assert out["schema_version"] == "language-v1"
        assert out["language"] == "fr"
        adh = out["language_results"]["adherence"]
        assert adh["pct_in_language"] == 100.0
        assert adh["mean_accent_density"] > 0
        dia = out["language_results"]["diacritics"]
        assert dia["pct_traps_passed"] == 100.0
        assert dia["count_ascii_stripped"] == 0

    def test_regressed_model_flagged(self):
        with (
            patch("asiai.benchmark.language_eval.chat", side_effect=_en_drift_chat),
            patch("asiai.benchmark.language_eval.collect_run_metadata", return_value={}),
        ):
            out = run_language_eval("u", "llamacpp", "qwopus", language="fr")
        adh = out["language_results"]["adherence"]
        assert adh["pct_in_language"] == 0.0  # drifted to English
        dia = out["language_results"]["diacritics"]
        assert dia["pct_traps_passed"] < 100.0  # failed the accented-word traps

    def test_bench_mode_recorded(self):
        captured = {}

        def fake_md(**kw):
            captured.update(kw)
            return {"bench_mode": kw.get("bench_mode")}

        with (
            patch("asiai.benchmark.language_eval.chat", side_effect=_fr_good_chat),
            patch("asiai.benchmark.language_eval.collect_run_metadata", side_effect=fake_md),
        ):
            out = run_language_eval(
                "u", "e", "m", language="fr", suites=["adherence"], engine_version="b9430"
            )
        assert captured["bench_mode"] == "language"
        assert captured["engine_version"] == "b9430"
        assert out["bench_mode"] == "language"

    def test_non_latin_skips_diacritics(self):
        def zh_chat(base_url, model, messages, **kw):
            return ChatResult(text="这是一个关于数据结构的简短解释。", finish_reason="stop")

        with (
            patch("asiai.benchmark.language_eval.chat", side_effect=zh_chat),
            patch("asiai.benchmark.language_eval.collect_run_metadata", return_value={}),
        ):
            out = run_language_eval("u", "e", "m", language="zh")
        assert out["language_results"]["adherence"]["pct_in_language"] == 100.0
        assert "skipped" in out["language_results"]["diacritics"]

    def test_writes_output(self, tmp_path):
        with (
            patch("asiai.benchmark.language_eval.chat", side_effect=_fr_good_chat),
            patch("asiai.benchmark.language_eval.collect_run_metadata", return_value={}),
        ):
            run_language_eval("u", "e", "m", language="fr", out_path=str(tmp_path / "lang.json"))
        saved = json.loads((tmp_path / "lang.json").read_text())
        assert saved["language"] == "fr"
        assert saved["schema_version"] == "language-v1"
