"""Datasets for ``asiai bench --instruct`` (instruction-following).

Two families:

* **verifiable** — IFEval-style single-turn prompts, each carrying one or more
  programmatically-checkable instructions (``{type, args}`` consumed by
  ``instruct_verifiers``). asiai-native prompts (no IFEval data vendored).
* **agentic** — ``research-brief`` and ``order-control``: a multi-step task
  (research via tools → synthesise a multi-section deliverable → a secondary tool
  action). ``research-brief`` puts the deliverable FIRST and the secondary LAST,
  surfacing a failure mode where a model that terminates on the last instruction
  returns only the secondary confirmation. ``order-control`` swaps the order — the
  diagnostic control.
"""

from __future__ import annotations

DATASET_VERSION = "instruct-v1"

# --- verifiable (IFEval-style) ------------------------------------------------
# Each entry: {id, prompt, instructions:[{type, args}]}. Mix of single- and
# multi-instruction prompts spanning the IFEval categories.

VERIFIABLE_PROMPTS: list[dict] = [
    {
        "id": "words_min",
        "prompt": "Explain what a hash map is. Write at least 120 words.",
        "instructions": [{"type": "number_words", "args": {"min": 120}}],
    },
    {
        "id": "words_max",
        "prompt": "In 40 words or fewer, define recursion.",
        "instructions": [{"type": "number_words", "args": {"max": 40}}],
    },
    {
        "id": "sentences",
        "prompt": "Describe the water cycle in exactly 3 sentences.",
        "instructions": [{"type": "number_sentences", "args": {"exact": 3}}],
    },
    {
        "id": "paragraphs",
        "prompt": "Write about the bicycle's history in exactly 2 paragraphs.",
        "instructions": [{"type": "number_paragraphs", "args": {"exact": 2}}],
    },
    {
        "id": "bullets",
        "prompt": "List exactly 5 tips for better sleep as markdown bullet points.",
        "instructions": [{"type": "number_bullets", "args": {"exact": 5}}],
    },
    {
        "id": "sections",
        "prompt": "Write a short guide with exactly 3 markdown `##` sections.",
        "instructions": [{"type": "number_sections", "args": {"exact": 3}}],
    },
    {
        "id": "title",
        "prompt": "Write a one-paragraph movie pitch. Put a title wrapped in double "
        "angle brackets, like <<Title Here>>, at the top.",
        "instructions": [{"type": "title", "args": {}}],
    },
    {
        "id": "json",
        "prompt": "Output a JSON object with keys name, age, city and nothing else. "
        "No prose, no code fence.",
        "instructions": [{"type": "json_format", "args": {}}],
    },
    {
        "id": "choose",
        "prompt": "Is the Earth flat? Answer with exactly one word: Yes or No.",
        "instructions": [{"type": "choose_from", "args": {"options": ["Yes", "No"]}}],
    },
    {
        "id": "lowercase",
        "prompt": "Write a friendly greeting entirely in lowercase letters.",
        "instructions": [{"type": "all_lowercase", "args": {}}],
    },
    {
        "id": "uppercase",
        "prompt": "Write a short motivational slogan in ALL UPPERCASE.",
        "instructions": [{"type": "all_uppercase", "args": {}}],
    },
    {
        "id": "no_commas",
        "prompt": "Describe your ideal weekend without using any commas.",
        "instructions": [{"type": "no_commas", "args": {}}],
    },
    {
        "id": "end_phrase",
        "prompt": "Give one productivity tip and end your response with the exact "
        "phrase: That is all.",
        "instructions": [{"type": "end_phrase", "args": {"phrase": "That is all."}}],
    },
    {
        "id": "postscript",
        "prompt": "Recommend a book, then add a postscript starting with P.S.",
        "instructions": [{"type": "postscript", "args": {"marker": "P.S."}}],
    },
    {
        "id": "quotation",
        "prompt": "Reply with a single sentence wrapped entirely in double quotes.",
        "instructions": [{"type": "quotation", "args": {}}],
    },
    {
        "id": "kw_include",
        "prompt": "Write two sentences about gardening that mention the words soil and sunlight.",
        "instructions": [{"type": "keywords_include", "args": {"keywords": ["soil", "sunlight"]}}],
    },
    {
        "id": "kw_freq",
        "prompt": "Write a short paragraph about coffee that uses the word coffee "
        "at least 3 times.",
        "instructions": [{"type": "keyword_frequency", "args": {"keyword": "coffee", "min": 3}}],
    },
    {
        "id": "forbidden",
        "prompt": "Describe a sunset without using the words sun or orange.",
        "instructions": [{"type": "forbidden_words", "args": {"forbidden": ["sun", "orange"]}}],
    },
    {
        "id": "language_fr",
        "prompt": "Réponds en français : explique en deux phrases ce qu'est une API.",
        "instructions": [{"type": "response_language", "args": {"language": "fr"}}],
    },
    # multi-instruction prompts (prompt-level needs ALL to pass)
    {
        "id": "multi_format",
        "prompt": "Write a product blurb of at least 50 words, with a title in "
        "double angle brackets <<like this>>, and end with the exact phrase: Buy now.",
        "instructions": [
            {"type": "number_words", "args": {"min": 50}},
            {"type": "title", "args": {}},
            {"type": "end_phrase", "args": {"phrase": "Buy now."}},
        ],
    },
    {
        "id": "multi_constraints",
        "prompt": "List exactly 4 bullet points of travel advice, with no "
        "commas anywhere, mentioning the word passport.",
        "instructions": [
            {"type": "number_bullets", "args": {"exact": 4}},
            {"type": "no_commas", "args": {}},
            {"type": "keywords_include", "args": {"keywords": ["passport"]}},
        ],
    },
    {
        "id": "multi_lower_kw",
        "prompt": "In all lowercase, write three sentences about cats "
        "that use the word whiskers at least twice.",
        "instructions": [
            {"type": "all_lowercase", "args": {}},
            {"type": "keyword_frequency", "args": {"keyword": "whiskers", "min": 2}},
            {"type": "number_sentences", "args": {"exact": 3}},
        ],
    },
]


# --- agentic (research-brief / order-control) ---------------------------------

INSTRUCT_AGENTIC_SYSTEM = (
    "You are an assistant that researches topics with tools and then writes "
    "structured deliverables. Complete every requested step. The written "
    "deliverable is your primary output — produce it in full in your final "
    "answer; tool calls are means, not the deliverable."
)

# (section_header, search_query, canned_fact). The section headers are what the
# scorer looks for in the final user-facing content.
RESEARCH_TOPICS: list[tuple[str, str, str]] = [
    (
        "## Energy",
        "grid-scale battery storage 2026",
        "Grid-scale sodium-ion batteries reached cost parity with lithium for stationary storage.",
    ),
    (
        "## Space",
        "James Webb telescope latest finding",
        "JWST detected complex organic molecules in a protoplanetary disk.",
    ),
    (
        "## Health",
        "Mediterranean diet study 2026",
        "A large cohort linked the Mediterranean diet to slower cognitive decline.",
    ),
    (
        "## Computing",
        "quantum error correction milestone",
        "A team demonstrated below-threshold error correction on a 100-qubit device.",
    ),
    (
        "## Cities",
        "urban beekeeping trend",
        "Cities report rising rooftop apiaries improving pollination of community gardens.",
    ),
]
RESEARCH_SECTIONS = [t[0] for t in RESEARCH_TOPICS]

# Five more topics for the DEEP variant — more tool-turns + a deeper context, to
# probe whether a model drops the primary deliverable only once the conversation
# is long (the deep scenario runs ~17 tool-turns; the short scenario ~5).
RESEARCH_TOPICS_EXTRA: list[tuple[str, str, str]] = [
    (
        "## Oceans",
        "deep-sea floor mapping 2026",
        "A global survey mapped a quarter of the deep-sea floor at high resolution.",
    ),
    (
        "## Materials",
        "ambient-pressure superconductor replication",
        "Independent labs reproduced a nickelate superconducting near 80 K at ambient pressure.",
    ),
    (
        "## Agriculture",
        "vertical farming energy efficiency 2026",
        "New LED spectra cut vertical-farm energy use per kilogram of greens by roughly a third.",
    ),
    (
        "## Transport",
        "solid-state EV battery production",
        "A carmaker began pilot production of solid-state cells with ~50% higher energy density.",
    ),
    (
        "## Climate",
        "direct air capture cost 2026",
        "A direct-air-capture plant reported costs falling below 200 USD per tonne of CO2 removed.",
    ),
]
RESEARCH_TOPICS_DEEP = RESEARCH_TOPICS + RESEARCH_TOPICS_EXTRA
RESEARCH_SECTIONS_DEEP = [t[0] for t in RESEARCH_TOPICS_DEEP]

INSTRUCT_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for a query; returns a short factual snippet.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_note",
            "description": "Save a one-line note (title + body) to the notes file.",
            "parameters": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
                "required": ["title"],
            },
        },
    },
]


def _brief_step(sections: list[str]) -> str:
    return (
        "Produce a markdown briefing with one `## <Topic>` section per topic below, "
        "2-3 sentences each, synthesising what web_search returns. Use these exact "
        "section headers:\n" + "\n".join(sections) + "\n"
        "Research each topic with the web_search tool first."
    )


_SAVE_STEP = (
    "Pick the single most interesting item and save it with the save_note tool "
    "(a short title and one-line body)."
)
# Elaborate secondary step for the DEEP variant: a substantial A/B/C decision that
# competes for the model's attention as the "last instruction" — a long, detailed
# step 2 can capture the final response and crowd out step 1 (the primary
# deliverable).
_SAVE_STEP_ELABORATE = (
    "Among today's three candidate ideas — "
    "A) launch a weekly tech-watch newsletter, "
    "B) prototype a science-findings aggregator, "
    "C) start a monthly local-innovation meetup — pick the single best one. Write a "
    "justification of at least 10 lines (trade-offs, why not the other two, a rough "
    "first step), then save it with the save_note tool (a title plus the full "
    "justification as the body)."
)

_N, _N_DEEP = len(RESEARCH_SECTIONS), len(RESEARCH_SECTIONS_DEEP)

# research-brief: deliverable FIRST, secondary LAST (reproduces the regression).
RESEARCH_BRIEF_PROMPT = (
    "Two steps.\n\nSTEP 1 (primary deliverable) — " + _brief_step(RESEARCH_SECTIONS) + "\n\n"
    "STEP 2 (after the briefing) — " + _SAVE_STEP + "\n\n"
    f"Your final answer must contain the full {_N}-section briefing."
)
# order-control: secondary FIRST, deliverable LAST (diagnostic).
ORDER_CONTROL_PROMPT = (
    "Two steps.\n\nSTEP 1 — " + _SAVE_STEP + " (research with web_search as needed)\n\n"
    "STEP 2 (primary deliverable, do this last) — " + _brief_step(RESEARCH_SECTIONS) + "\n\n"
    f"Your final answer must contain the full {_N}-section briefing."
)
# research-brief-deep: more topics (deeper context) + an elaborate secondary step,
# deliverable FIRST and the heavy secondary LAST — the faithful deep-deliverable shape.
RESEARCH_BRIEF_DEEP_PROMPT = (
    "Two steps.\n\nSTEP 1 (primary deliverable) — " + _brief_step(RESEARCH_SECTIONS_DEEP) + "\n\n"
    "STEP 2 (after the briefing) — " + _SAVE_STEP_ELABORATE + "\n\n"
    f"Your final answer must contain the full {_N_DEEP}-section briefing."
)

INSTRUCT_MAX_TURNS = 10  # short: web_search ×5 + save_note + final, with slack
INSTRUCT_MAX_TURNS_DEEP = 24  # deep: web_search ×10 + elaborate save + final, with slack

# Per-scenario config consumed by instruct_eval._run_agentic_scenario.
AGENTIC_SCENARIOS: dict[str, dict] = {
    "research-brief": {
        "prompt": RESEARCH_BRIEF_PROMPT,
        "topics": RESEARCH_TOPICS,
        "sections": RESEARCH_SECTIONS,
        "max_turns": INSTRUCT_MAX_TURNS,
    },
    "order-control": {
        "prompt": ORDER_CONTROL_PROMPT,
        "topics": RESEARCH_TOPICS,
        "sections": RESEARCH_SECTIONS,
        "max_turns": INSTRUCT_MAX_TURNS,
    },
    "research-brief-deep": {
        "prompt": RESEARCH_BRIEF_DEEP_PROMPT,
        "topics": RESEARCH_TOPICS_DEEP,
        "sections": RESEARCH_SECTIONS_DEEP,
        "max_turns": INSTRUCT_MAX_TURNS_DEEP,
    },
}
