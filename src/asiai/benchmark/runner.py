"""Benchmark runner — orchestrates cross-engine benchmarks."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from asiai.benchmark.prompts import BenchPrompt, get_prompts
from asiai.collectors.system import collect_memory, collect_thermal
from asiai.engines.base import InferenceEngine

logger = logging.getLogger("asiai.benchmark.runner")


@dataclass
class BenchmarkRun:
    """Complete results from a single benchmark session."""

    ts: int = 0
    model: str = ""
    results: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def find_common_model(
    engines: list[InferenceEngine],
    model_filter: str = "",
) -> str:
    """Find a model available across engines, or use the filter.

    If model_filter is set, return it directly.
    Otherwise, look for a model running on multiple engines.
    Fallback: first running model from the first engine.
    """
    if model_filter:
        return model_filter

    running_by_engine: dict[str, set[str]] = {}
    for engine in engines:
        try:
            models = engine.list_running()
            running_by_engine[engine.name] = {m.name for m in models}
        except Exception:
            running_by_engine[engine.name] = set()

    if not running_by_engine:
        return ""

    # Try to find intersection
    all_sets = list(running_by_engine.values())
    if len(all_sets) >= 2:
        common = all_sets[0]
        for s in all_sets[1:]:
            common = common & s
        if common:
            return sorted(common)[0]

    # Fallback: first running model
    for names in running_by_engine.values():
        if names:
            return sorted(names)[0]

    return ""


def run_benchmark(
    engines: list[InferenceEngine],
    model: str,
    prompt_names: list[str] | None = None,
) -> BenchmarkRun:
    """Run benchmarks across engines for a given model.

    Execution is sequential to avoid memory/thermal interference
    on unified memory Apple Silicon.
    """
    prompts = get_prompts(prompt_names)
    ts = int(time.time())
    run = BenchmarkRun(ts=ts, model=model)

    for engine in engines:
        if not engine.is_reachable():
            run.errors.append(f"{engine.name}: not reachable")
            continue

        # Resolve engine-specific model name
        engine_model = _resolve_model_name(engine, model)

        # Get VRAM for this model
        vram_bytes = 0
        try:
            for m in engine.list_running():
                if _model_matches(m.name, model):
                    vram_bytes = m.size_vram
                    break
        except Exception:
            pass

        for prompt in prompts:
            logger.info("Benchmarking %s on %s [%s]", engine_model, engine.name, prompt.name)
            _run_single(engine, engine_model, prompt, ts, vram_bytes, run)

    return run


def _run_single(
    engine: InferenceEngine,
    model: str,
    prompt: BenchPrompt,
    ts: int,
    vram_bytes: int,
    run: BenchmarkRun,
) -> None:
    """Run a single engine+prompt benchmark and append to run."""
    mem = collect_memory()
    thermal = collect_thermal()

    gen = engine.generate(model, prompt.prompt, prompt.max_tokens)

    if gen.error:
        run.errors.append(f"{engine.name}/{prompt.name}: {gen.error}")
        return

    run.results.append({
        "ts": ts,
        "engine": engine.name,
        "model": model,
        "prompt_type": prompt.name,
        "tokens_generated": gen.tokens_generated,
        "tok_per_sec": gen.tok_per_sec,
        "ttft_ms": gen.ttft_ms,
        "total_duration_ms": gen.total_duration_ms,
        "vram_bytes": vram_bytes,
        "mem_used": mem.used,
        "thermal_level": thermal.level,
        "thermal_speed_limit": thermal.speed_limit,
    })


def _resolve_model_name(engine: InferenceEngine, target: str) -> str:
    """Find the actual model name loaded in this engine that matches the target.

    Returns the engine-specific name, or the target as-is if no match found.
    """
    try:
        for m in engine.list_running():
            if _model_matches(m.name, target):
                return m.name
    except Exception:
        pass
    return target


def _model_matches(running_name: str, target: str) -> bool:
    """Check if a running model name matches the target.

    Handles Ollama name:tag convention and partial matches for
    cross-engine model name differences.
    """
    if running_name == target:
        return True
    # Ollama default tag
    if ":" not in target and running_name == f"{target}:latest":
        return True
    # Strip tags for base name comparison
    base_running = running_name.split(":")[0]
    base_target = target.split(":")[0]
    if base_running == base_target:
        return True
    # Substring match for cross-engine name variants
    if base_target in running_name or base_running in target:
        return True
    # Normalize separators (gemma-2-9b vs gemma2:9b)
    norm_running = base_running.replace("-", "").replace(".", "")
    norm_target = base_target.replace("-", "").replace(".", "")
    if norm_running == norm_target or norm_target in norm_running or norm_running in norm_target:
        return True
    return False
