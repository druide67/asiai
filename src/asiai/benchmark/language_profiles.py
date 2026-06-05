"""Per-language resources for ``asiai bench --language`` (multilingual retention).

A ``LanguageProfile`` carries everything the deterministic suites need to detect
whether a model *stayed in* a target language and kept its orthography — the
catastrophic-forgetting failure modes a finetune (e.g. an Opus-distilled coding
finetune) can introduce. Adherence is measured by a dependency-free heuristic:
for Latin-script languages, the ratio of target-language function words to
English ones (drift to English flips it); for non-Latin languages, the fraction
of characters in the target script (Han / Kana / Hangul) vs Latin.

Diacritic traps are prompts whose correct answer MUST contain specific accented
tokens (``café``, ``préféré``) — an ASCII-stripped answer (``cafe``) fails them.
French is populated in full; other languages plug in by adding their data.
"""

from __future__ import annotations

from dataclasses import dataclass

# English function words — the contrast set for Latin-script adherence (a target
# response that drifted to English lights these up instead of the target's).
ENGLISH_STOPWORDS: frozenset[str] = frozenset(
    "the a an and or but of to in on at for with from by is are was were be been "
    "this that these those it its as he she they we you i not no yes can will would "
    "should could here there what which who when where how".split()
)

# Unicode script ranges for non-Latin adherence (start, end) inclusive.
_SCRIPT_RANGES: dict[str, tuple[tuple[int, int], ...]] = {
    "han": ((0x4E00, 0x9FFF), (0x3400, 0x4DBF)),  # CJK ideographs (zh, shared ja)
    "kana_han": ((0x3040, 0x309F), (0x30A0, 0x30FF), (0x4E00, 0x9FFF)),  # hiragana+katakana+han
    "hangul": ((0xAC00, 0xD7A3), (0x1100, 0x11FF), (0x3130, 0x318F)),  # syllables + jamo
}


@dataclass(frozen=True)
class LanguageProfile:
    code: str
    name: str
    native_name: str
    # Latin-script adherence: target-language function words (lowercased).
    stopwords: frozenset[str] = frozenset()
    # Non-Latin adherence: script key into _SCRIPT_RANGES (None ⇒ Latin/stopword path).
    script: str | None = None
    # Diacritic traps: {"prompt": str, "must_contain": [exact accented tokens]}.
    diacritic_traps: tuple[dict, ...] = ()
    # Open-ended adherence/fluency probes (prompts written in the target language).
    probes: tuple[str, ...] = ()
    # A prompt asking for code with a docstring/comments in the target language.
    code_comment_prompt: str = ""
    # Expected accent density (accented letters / letters) for a healthy response
    # in this language; 0 with target stopwords present ⇒ ASCII-stripped. None for
    # non-Latin (the script ratio already captures orthography).
    min_accent_density: float | None = None


def script_char_ratio(text: str, script: str) -> float:
    """Fraction of letter-ish chars in ``text`` that belong to ``script``.

    Spaces, digits and ASCII punctuation are ignored; the denominator is the
    remaining "content" chars. High ⇒ the response is in the target script; low
    (mostly Latin) ⇒ drifted to English/romaji. 0.0 when there is no content.
    """
    ranges = _SCRIPT_RANGES.get(script)
    if not ranges:
        return 0.0
    # Letters only (Han/Kana/Hangul are Unicode letters too) — excludes spaces,
    # digits and punctuation so the ratio reflects script choice, not formatting.
    content = [c for c in text if c.isalpha()]
    if not content:
        return 0.0
    in_script = sum(1 for c in content if any(lo <= ord(c) <= hi for lo, hi in ranges))
    return round(in_script / len(content), 3)


# --- French (populated in full) ----------------------------------------------

_FR = LanguageProfile(
    code="fr",
    name="French",
    native_name="Français",
    stopwords=frozenset(
        "le la les un une des de du au aux et ou mais donc or ni car ne pas plus "
        "que qui quoi dont où à dans par pour sur sous avec sans chez vers est sont "
        "était étaient être avoir fait ce cette ces son sa ses leur leurs nous vous "
        "ils elles je tu il elle on se sy lui même très bien aussi alors ainsi "
        "comme cela ceci là ici".split()
    ),
    diacritic_traps=(
        {
            "prompt": "Quel est le mot français pour « coffee » ? Réponds par un seul mot.",
            "must_contain": ["café"],
        },
        {
            "prompt": "Écris exactement, sans rien changer : « L'élève préféré était très âgé. »",
            "must_contain": ["élève", "préféré", "âgé"],
        },
        {
            "prompt": "Complète la phrase : « Nous sommes allés à la ___ pour la fête. » "
            "(le lieu où l'on va à la messe). Réponds par un seul mot.",
            "must_contain": ["église"],
        },
        {
            "prompt": "Conjugue le verbe « être » à la première personne du pluriel au "
            "présent, puis à l'imparfait. Réponds par les deux formes seulement.",
            "must_contain": ["sommes", "étions"],
        },
    ),
    probes=(
        "Explique en deux phrases, en français, ce qu'est une pile (structure de données).",
        "Rédige en français une courte note (3 phrases) expliquant pourquoi versionner "
        "son code est utile.",
        "En français, donne trois conseils concis pour écrire des messages de commit clairs.",
    ),
    code_comment_prompt=(
        "Écris une fonction Python `est_premier(n)` qui teste la primalité, avec une "
        "docstring ET des commentaires rédigés en français correct (avec les accents)."
    ),
    min_accent_density=0.015,
)

# --- Other languages: stopwords for Latin adherence, script for CJK ----------
# Diacritic traps / probes left empty for now (data plugs in later); adherence +
# degeneracy already work from the stopword/script sets.

_DE = LanguageProfile(
    code="de", name="German", native_name="Deutsch",
    stopwords=frozenset(
        "der die das und oder aber ein eine einen dem den des zu in auf mit für von "
        "ist sind war waren sein haben nicht auch noch wie wenn weil dass ich du er "
        "sie es wir ihr man sehr hier dort".split()
    ),
    probes=(
        "Erkläre in zwei Sätzen auf Deutsch, was ein Stack (Datenstruktur) ist.",
        "Nenne auf Deutsch drei kurze Tipps für klare Commit-Nachrichten.",
    ),
    min_accent_density=0.0,  # German uses ä/ö/ü/ß but not on every sentence
)
_ES = LanguageProfile(
    code="es", name="Spanish", native_name="Español",
    stopwords=frozenset(
        "el la los las un una unos unas de del al y o pero que como para por con sin "
        "es son era eran ser estar no sí también muy aquí allí cuando donde quien "
        "esto eso esta este".split()
    ),
    probes=(
        "Explica en dos frases, en español, qué es una pila (estructura de datos).",
        "Da en español tres consejos breves para escribir buenos mensajes de commit.",
    ),
    min_accent_density=0.005,
)
_IT = LanguageProfile(
    code="it", name="Italian", native_name="Italiano",
    stopwords=frozenset(
        "il lo la i gli le un uno una di del della e o ma che come per con senza è "
        "sono era erano essere avere non anche molto qui là quando dove chi questo "
        "quello sì".split()
    ),
    probes=(
        "Spiega in due frasi, in italiano, cos'è una pila (struttura dati).",
        "Dai in italiano tre brevi consigli per scrivere buoni messaggi di commit.",
    ),
    min_accent_density=0.005,
)
_PT = LanguageProfile(
    code="pt", name="Portuguese", native_name="Português",
    stopwords=frozenset(
        "o a os as um uma uns umas de do da dos das e ou mas que como para por com "
        "sem é são era eram ser estar não sim também muito aqui ali quando onde quem "
        "isto isso esta este".split()
    ),
    probes=(
        "Explique em duas frases, em português, o que é uma pilha (estrutura de dados).",
        "Dê em português três conselhos breves para escrever boas mensagens de commit.",
    ),
    min_accent_density=0.01,
)
_JA = LanguageProfile(
    code="ja", name="Japanese", native_name="日本語", script="kana_han",
    probes=(
        "日本語で、スタック（データ構造）とは何かを2文で説明してください。",
        "日本語で、分かりやすいコミットメッセージを書くための短いコツを3つ挙げてください。",
    ),
)
_KO = LanguageProfile(
    code="ko", name="Korean", native_name="한국어", script="hangul",
    probes=(
        "한국어로 스택(자료 구조)이 무엇인지 두 문장으로 설명해 주세요.",
        "한국어로 명확한 커밋 메시지를 작성하기 위한 짧은 팁 세 가지를 알려 주세요.",
    ),
)
_ZH = LanguageProfile(
    code="zh", name="Chinese", native_name="中文", script="han",
    probes=(
        "请用中文用两句话解释什么是栈（数据结构）。",
        "请用中文给出三条简短的建议，说明如何写清晰的提交信息。",
    ),
)

PROFILES: dict[str, LanguageProfile] = {
    p.code: p for p in (_FR, _DE, _ES, _IT, _PT, _JA, _KO, _ZH)
}

# Languages with full deterministic coverage (diacritic traps + probes) today.
FULLY_POPULATED: frozenset[str] = frozenset({"fr"})


def get_profile(code: str) -> LanguageProfile | None:
    return PROFILES.get(code.lower())
