"""Adaptive bench card family — programmatic SVG per bench type.

``generate_card(result)`` dispatches a :class:`BenchResult` (from
``asiai.benchmark.result_model``) to its layout. The visual contract is
the design handoff spec transcribed in ``_frame.py``; the honesty rules
(no naked numbers, gates always visible, missing ≠ zero, withheld
ranking = no crown) are structural in the layouts.

The legacy throughput-only renderer lives on in
``asiai.benchmark.card`` (SVG→PNG plumbing is reused from there).
"""

from __future__ import annotations

from asiai.benchmark.cards import agentic, burst, quality, throughput
from asiai.benchmark.result_model import BenchResult

_LAYOUTS = {
    "standard": throughput.render,
    "agentic": agentic.render,
    "burst": burst.render,
    "code": quality.render,
    "language": quality.render,
    "instruct": quality.render,
    "thinking-ablation": quality.render,
}


def generate_card(result: BenchResult) -> str:
    """Render the SVG card for any bench type's result."""
    layout = _LAYOUTS.get(result.bench_type)
    if layout is None:
        raise ValueError(f"no card layout for bench type {result.bench_type!r}")
    return layout(result)


__all__ = ["generate_card"]
