"""Standardized benchmark prompts for cross-engine comparison."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BenchPrompt:
    """A benchmark prompt with metadata."""

    name: str
    label: str
    prompt: str
    max_tokens: int
    description: str


PROMPTS: dict[str, BenchPrompt] = {
    "code": BenchPrompt(
        name="code",
        label="Code Generation",
        prompt=(
            "Write a Python class implementing a binary search tree (BST) with "
            "insert, search, delete, and in-order traversal methods. Include type "
            "hints and docstrings."
        ),
        max_tokens=512,
        description="Tests code generation with structured output",
    ),
    "tool_call": BenchPrompt(
        name="tool_call",
        label="Tool Calling",
        prompt=(
            "You have access to the following function:\n\n"
            '{"name": "get_weather", "parameters": {"location": "string", '
            '"unit": "celsius|fahrenheit"}}\n\n'
            "The user asks: 'What is the weather in Paris and Tokyo?'\n\n"
            "Respond with the function calls as JSON array."
        ),
        max_tokens=256,
        description="Tests structured JSON output and instruction following",
    ),
    "reasoning": BenchPrompt(
        name="reasoning",
        label="Reasoning",
        prompt=(
            "A farmer has 100 meters of fencing. He wants to enclose a rectangular "
            "area along a river (so one side needs no fencing). What dimensions "
            "maximize the enclosed area? Show your work step by step."
        ),
        max_tokens=384,
        description="Tests multi-step logical reasoning",
    ),
    "long_gen": BenchPrompt(
        name="long_gen",
        label="Long Generation",
        prompt=(
            "Write a complete bash script that sets up a new macOS development "
            "environment. Include: Homebrew installation check, common developer "
            "tools (git, python, node), shell configuration (zsh), SSH key "
            "generation, and macOS defaults for developers. Add error handling "
            "and colored output."
        ),
        max_tokens=1024,
        description="Tests sustained generation throughput",
    ),
}

DEFAULT_PROMPT_ORDER = ["code", "tool_call", "reasoning", "long_gen"]


def get_prompts(names: list[str] | None = None) -> list[BenchPrompt]:
    """Return prompts to run. If names is None, return all in default order."""
    if names is None:
        names = DEFAULT_PROMPT_ORDER
    return [PROMPTS[n] for n in names if n in PROMPTS]


# --- Context fill prompt generation ---

# ~750 tokens of varied English prose (repeated to fill target size).
_FILL_BLOCK = (
    "The quick brown fox jumps over the lazy dog near the river bank. "
    "Scientists recently discovered a new species of deep-sea fish that "
    "can survive extreme pressure at depths exceeding 8,000 meters. The "
    "research team published their findings in Nature, noting that the "
    "fish exhibits bioluminescent properties unlike any previously "
    "documented organism. Meanwhile, advances in quantum computing "
    "continue to accelerate, with several major tech companies announcing "
    "breakthroughs in error correction that could bring practical quantum "
    "advantage closer to reality. In the world of open-source software, "
    "community-driven projects have shown remarkable resilience and "
    "innovation, often outpacing proprietary alternatives in both "
    "performance and security. Local large language model inference on "
    "Apple Silicon has become increasingly viable, with frameworks like "
    "MLX enabling efficient utilization of the unified memory architecture. "
    "Benchmark results show that models running natively on Metal can "
    "achieve throughput comparable to dedicated GPU setups at a fraction "
    "of the power consumption. The implications for edge AI deployment "
    "are significant, as developers can now run capable models without "
    "cloud dependencies or specialized hardware. Temperature monitoring "
    "and memory pressure tracking become essential when pushing these "
    "systems to their limits during sustained inference workloads. "
)

# Chars per token, calibrated against the Qwen tokenizer (~5.3), matching the
# long-form fixtures below. Used to size context-fill prompts so --context-size N
# lands near N tokens on Qwen; the old 4.0 undershot the target by ~25%.
_CHARS_PER_TOKEN = 5.3


# --- Long-form fixtures (shared between agentic-mode and burst-mode) ---

# Deterministic filler. Repeated unique paragraphs with sentinels per slot
# to break naive cache lookups while keeping content semantically coherent.
_BASE_PARAGRAPH = (
    "The orbital dynamics of binary neutron star systems exhibit characteristic "
    "gravitational wave signatures during the late inspiral phase. Tidal "
    "deformability parameters constrain the equation of state of dense nuclear "
    "matter at supra-saturation densities, where conventional perturbative QCD "
    "approaches become inapplicable. Observational evidence from GW170817 and "
    "subsequent multi-messenger campaigns has progressively refined the radius "
    "estimates for canonical 1.4 solar mass configurations. "
)


def _grow_to(target_chars: int, seed_label: str) -> str:
    """Return a deterministic string of approximately ``target_chars`` characters."""
    prefix = f"[{seed_label}] "
    sentinel_template = f" (segment-{seed_label}-{{i}}) "
    chunks: list[str] = [prefix]
    cur = len(prefix)
    i = 0
    while cur < target_chars:
        chunks.append(_BASE_PARAGRAPH)
        sentinel = sentinel_template.format(i=i)
        chunks.append(sentinel)
        cur += len(_BASE_PARAGRAPH) + len(sentinel)
        i += 1
    return "".join(chunks)[:target_chars]


# Char targets calibrated against Qwen tokenizers (~5.3 chars/token).
# Resulting token counts on the Qwen3.6 tokenizer:
#   SYS_A/SYS_B   : ~6018-6084 tokens
#   USER_X/USER_Y : ~1495-1497 tokens
#   USER_L        : ~49804 tokens
SYS_A = _grow_to(31500, "SYSTEM-A-canonical-eos-analyst")
SYS_B = _grow_to(31500, "SYSTEM-B-orbital-radio-pulsar-timer")
USER_X = _grow_to(8000, "USER-X-tidal-deformability-question")
USER_Y = _grow_to(8000, "USER-Y-mass-radius-degeneracy-question")
USER_L = _grow_to(265000, "USER-L-long-context-multi-event-corpus")


def parse_context_size(value: str) -> int:
    """Parse a context size string like '64k', '128k', '4096' into token count."""
    value = value.strip().lower()
    if value.endswith("k"):
        return int(value[:-1]) * 1024
    return int(value)


def generate_context_fill_prompt(target_tokens: int, max_tokens: int = 256) -> BenchPrompt:
    """Generate a prompt that fills approximately target_tokens of context.

    The prompt wraps filler text in an instruction asking the model to
    summarize it, so the model processes the full context before generating.

    The input budget is reduced by max_tokens so that input + output fits
    within the target context window.
    """
    instruction = "Summarize the following text in 3 bullet points:\n\n"

    input_budget = max(100, target_tokens - max_tokens)
    target_chars = int(input_budget * _CHARS_PER_TOKEN) - len(instruction)
    if target_chars < 100:
        target_chars = 100

    # Repeat the fill block to reach the target size
    block_len = len(_FILL_BLOCK)
    repeats = (target_chars // block_len) + 1
    filler = (_FILL_BLOCK * repeats)[:target_chars]

    prompt_text = instruction + filler

    return BenchPrompt(
        name="context_fill",
        label=f"Context Fill ({target_tokens // 1024}k)",
        prompt=prompt_text,
        max_tokens=max_tokens,
        description=f"TTFT stress test with ~{target_tokens} input tokens",
    )
