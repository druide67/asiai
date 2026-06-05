"""Tests for the IFEval-style deterministic verifiers (1.12.0)."""

from __future__ import annotations

from asiai.benchmark.instruct_verifiers import REGISTRY, evaluate_prompt, verify


class TestVerifiers:
    def test_keywords_include(self):
        kw = {"keywords": ["soil", "sunlight"]}
        assert verify("keywords_include", "soil and sunlight matter", kw)
        assert not verify("keywords_include", "only soil here", kw)

    def test_keyword_frequency(self):
        assert verify("keyword_frequency", "coffee coffee coffee", {"keyword": "coffee", "min": 3})
        assert not verify("keyword_frequency", "coffee once", {"keyword": "coffee", "min": 3})

    def test_forbidden_words(self):
        assert verify("forbidden_words", "a glowing sky", {"forbidden": ["sun", "orange"]})
        assert not verify("forbidden_words", "the orange sun", {"forbidden": ["sun", "orange"]})

    def test_number_words(self):
        assert verify("number_words", "one two three four five", {"min": 5})
        assert not verify("number_words", "too short", {"min": 5})
        assert verify("number_words", "a b c", {"max": 5})
        assert not verify("number_words", "a b c d e f", {"max": 5})

    def test_number_sentences(self):
        assert verify("number_sentences", "One. Two. Three.", {"exact": 3})
        assert not verify("number_sentences", "One. Two.", {"exact": 3})

    def test_number_paragraphs(self):
        assert verify("number_paragraphs", "para one.\n\npara two.", {"exact": 2})
        assert not verify("number_paragraphs", "single para.", {"exact": 2})

    def test_number_bullets(self):
        assert verify("number_bullets", "- a\n- b\n- c", {"exact": 3})
        assert not verify("number_bullets", "- a\n- b", {"exact": 3})

    def test_number_sections(self):
        assert verify("number_sections", "## A\ntext\n## B", {"exact": 2})
        assert not verify("number_sections", "## A only", {"exact": 2})

    def test_title(self):
        assert verify("title", "<<My Title>>\nbody", {})
        assert not verify("title", "My Title\nbody", {})

    def test_json_format(self):
        assert verify("json_format", '{"a": 1}', {})
        assert verify("json_format", '```json\n{"a": 1}\n```', {})  # fence tolerated
        assert not verify("json_format", "not json at all", {})

    def test_choose_from(self):
        assert verify("choose_from", "Yes", {"options": ["Yes", "No"]})
        assert not verify("choose_from", "Maybe", {"options": ["Yes", "No"]})

    def test_case(self):
        assert verify("all_lowercase", "hello world", {})
        assert not verify("all_lowercase", "Hello World", {})
        assert verify("all_uppercase", "HELLO", {})
        assert not verify("all_uppercase", "Hello", {})

    def test_capital_word_frequency(self):
        assert verify("capital_word_frequency", "NASA and FBI", {"min": 2})
        assert not verify("capital_word_frequency", "nasa and fbi", {"min": 2})

    def test_no_commas(self):
        assert verify("no_commas", "no commas here at all", {})
        assert not verify("no_commas", "yes, there are", {})

    def test_end_phrase(self):
        assert verify("end_phrase", "Some advice. That is all.", {"phrase": "That is all."})
        assert not verify("end_phrase", "That is all, but wait more", {"phrase": "That is all."})

    def test_postscript(self):
        assert verify("postscript", "Read this.\nP.S. and that.", {"marker": "P.S."})
        assert not verify("postscript", "no postscript here", {"marker": "P.S."})

    def test_quotation(self):
        assert verify("quotation", '"a quoted sentence."', {})
        assert not verify("quotation", "no quotes", {})

    def test_response_language_fr(self):
        assert verify(
            "response_language", "Le café est une boisson que les gens aiment.", {"language": "fr"}
        )
        assert not verify(
            "response_language", "The coffee is a drink that people love.", {"language": "fr"}
        )

    def test_registry_covers_all(self):
        # every type referenced in the dataset is in the registry
        from asiai.benchmark.instruct_eval_scenarios import VERIFIABLE_PROMPTS

        used = {ins["type"] for p in VERIFIABLE_PROMPTS for ins in p["instructions"]}
        assert used <= set(REGISTRY)


class TestStrictLoose:
    def test_loose_strips_markdown_wrapper(self):
        # `**"x"**` fails strict quotation (first char is *) but loose strips * → passes
        wrapped = '**"a quoted line."**'
        assert not verify("quotation", wrapped, {}, loose=False)
        assert verify("quotation", wrapped, {}, loose=True)

    def test_loose_drops_preamble_line(self):
        # an end-phrase check fails strict if a sign-off line follows, loose drops last line
        text = "The tip is to sleep well. That is all.\n— signed, the bot"
        assert not verify("end_phrase", text, {"phrase": "That is all."}, loose=False)
        assert verify("end_phrase", text, {"phrase": "That is all."}, loose=True)


class TestEvaluatePrompt:
    def test_prompt_level_all_must_pass(self):
        instructions = [
            {"type": "number_words", "args": {"min": 3}},
            {"type": "no_commas", "args": {}},
        ]
        ok = evaluate_prompt("three words here", instructions)
        assert ok["prompt_strict"] is True
        bad = evaluate_prompt("three, words, here", instructions)  # has commas
        assert bad["prompt_strict"] is False
        assert sum(1 for i in bad["instructions"] if i["strict"]) == 1  # word-count still ok
