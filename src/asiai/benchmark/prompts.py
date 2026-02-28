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
