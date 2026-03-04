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

# Approximate tokens per character ratio (conservative for English text).
_CHARS_PER_TOKEN = 4.0


def parse_context_size(value: str) -> int:
    """Parse a context size string like '64k', '128k', '4096' into token count."""
    value = value.strip().lower()
    if value.endswith("k"):
        return int(value[:-1]) * 1024
    return int(value)


def generate_context_fill_prompt(target_tokens: int) -> BenchPrompt:
    """Generate a prompt that fills approximately target_tokens of context.

    The prompt wraps filler text in an instruction asking the model to
    summarize it, so the model processes the full context before generating.
    """
    instruction = "Summarize the following text in 3 bullet points:\n\n"
    instruction_chars = len(instruction)

    target_chars = int(target_tokens * _CHARS_PER_TOKEN) - instruction_chars
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
        max_tokens=256,
        description=f"TTFT stress test with ~{target_tokens} input tokens",
    )
