"""Benchmark runner — orchestrates cross-engine benchmarks."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from asiai.benchmark.prompts import BenchPrompt, generate_context_fill_prompt, get_prompts
from asiai.collectors.gpu import collect_gpu
from asiai.collectors.system import (
    collect_engine_processes,
    collect_hw_chip,
    collect_memory,
    collect_os_version,
    collect_thermal,
)
from asiai.engines.base import InferenceEngine

logger = logging.getLogger("asiai.benchmark.runner")


@dataclass
class BenchmarkSlot:
    """A single (engine, model) pair to benchmark."""

    engine: InferenceEngine
    model: str


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
        except Exception as e:
            logger.debug("list_running failed for %s: %s", engine.name, e)
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
    engines: list[InferenceEngine] | None = None,
    model: str = "",
    prompt_names: list[str] | None = None,
    runs: int = 1,
    power: bool = False,
    context_size: int = 0,
    *,
    slots: list[BenchmarkSlot] | None = None,
) -> BenchmarkRun:
    """Run benchmarks across engines for a given model, or across arbitrary slots.

    Args:
        engines: Inference engines to benchmark (legacy, use slots instead).
        model: Model name to benchmark (legacy, use slots instead).
        prompt_names: Optional subset of prompt types to run.
        runs: Number of runs per prompt (for variance measurement).
        power: If True, measure GPU power via powermetrics (sudo required).
        context_size: If > 0, use a single context-fill prompt of this many tokens.
        slots: List of (engine, model) pairs to benchmark. If provided,
               engines and model args are ignored. Supports cross-model comparison.

    Execution is sequential to avoid memory/thermal interference
    on unified memory Apple Silicon.
    """
    from asiai.collectors.power import PowerMonitor

    # Build slots from legacy args if not provided directly
    if slots is None:
        if engines is None:
            raise ValueError("Either engines+model or slots must be provided")
        slots = [BenchmarkSlot(engine=e, model=model) for e in engines]

    # Validate slots
    for s in slots:
        if not s.model:
            raise ValueError(f"BenchmarkSlot has empty model (engine={s.engine.name})")

    if context_size > 0:
        context_size = min(context_size, 131072)  # Cap at 128K
        prompts = [generate_context_fill_prompt(context_size)]
    else:
        prompts = get_prompts(prompt_names)
    ts = int(time.time())

    # For BenchmarkRun.model: use the model if all slots share it, else first slot's
    all_models = {s.model for s in slots}
    run_model = slots[0].model if len(all_models) == 1 else slots[0].model
    run = BenchmarkRun(ts=ts, model=run_model)

    # Collect machine info once per run (stable during session)
    hw_chip = collect_hw_chip()
    os_version = collect_os_version()
    mem = collect_memory()
    ram_gb = round(mem.total / (1024**3)) if mem.total > 0 else 0
    gpu_info = collect_gpu()
    gpu_cores = gpu_info.cores

    # Track whether power monitoring was requested but unavailable
    power_unavailable = False
    if power:
        test_monitor = PowerMonitor()
        if not test_monitor.start():
            run.errors.append("Power monitoring: sudo access required (run 'sudo -v' first)")
            power_unavailable = True
        else:
            test_monitor.stop()

    slots_run = 0
    prev_model = ""
    for slot in slots:
        engine = slot.engine
        slot_model = slot.model

        if not engine.is_reachable():
            run.errors.append(f"{engine.name}: not reachable")
            continue

        # Cooldown between slots to stabilize thermals
        # 5s if model changes (heavier thermal impact from load), 3s otherwise
        if slots_run > 0:
            cooldown = 5 if slot_model != prev_model else 3
            logger.info("Cooldown %ds between slots", cooldown)
            time.sleep(cooldown)

        # Pre-check: verify the model exists on this engine
        check = _check_model_availability(engine, slot_model)
        if not check["found"]:
            run.errors.append(check["error"])
            continue

        # Resolve engine-specific model name
        engine_model = check.get("resolved_name", slot_model)
        vram_bytes = check.get("vram_bytes", 0)
        model_format = check.get("model_format", "")
        model_quantization = check.get("model_quantization", "")

        # Capture engine version for reproducibility
        try:
            engine_ver = engine.version()
        except Exception:
            engine_ver = ""

        # Measure model load time (cold load on first access)
        load_time_ms = 0.0
        try:
            load_time_ms = engine.measure_load_time(engine_model)
        except Exception as e:
            logger.debug("load_time failed for %s: %s", engine.name, e)

        # Re-read VRAM after load (model may have been auto-loaded by measure_load_time)
        if vram_bytes == 0:
            try:
                for m in engine.list_running():
                    if _model_matches(m.name, engine_model) and m.size_vram > 0:
                        vram_bytes = m.size_vram
                        break
            except Exception as e:
                logger.debug("VRAM re-read failed for %s: %s", engine.name, e)

        # Warmup: one short non-timed generation to prime JIT/caches
        logger.info("Warmup run for %s on %s", engine_model, engine.name)
        try:
            engine.generate(engine_model, "Hello", max_tokens=1)
        except Exception as e:
            logger.debug("warmup failed for %s: %s", engine.name, e)

        # Start per-engine power monitoring
        engine_power: PowerMonitor | None = None
        if power and not power_unavailable:
            engine_power = PowerMonitor()
            if not engine_power.start():
                engine_power = None

        results_before = len(run.results)

        for prompt in prompts:
            for run_index in range(runs):
                logger.info(
                    "Benchmarking %s on %s [%s] run %d/%d",
                    engine_model,
                    engine.name,
                    prompt.name,
                    run_index + 1,
                    runs,
                )
                _run_single(
                    engine,
                    engine_model,
                    prompt,
                    ts,
                    vram_bytes,
                    run,
                    run_index,
                    load_time_ms,
                    engine_version=engine_ver,
                    model_format=model_format,
                    model_quantization=model_quantization,
                    hw_chip=hw_chip,
                    os_version=os_version,
                    context_size=context_size,
                    gpu_cores=gpu_cores,
                    ram_gb=ram_gb,
                )

        # Stop per-engine power monitoring and annotate this engine's results
        if engine_power:
            power_sample = engine_power.stop()
            gpu_watts = power_sample.gpu_watts
            for result in run.results[results_before:]:
                result["power_watts"] = gpu_watts
                tok_s = result.get("tok_per_sec", 0.0)
                if gpu_watts > 0 and tok_s > 0:
                    result["tok_per_sec_per_watt"] = round(tok_s / gpu_watts, 2)

        # Check for thermal throttling during this engine's runs
        for result in run.results[results_before:]:
            speed_limit = result.get("thermal_speed_limit", 100)
            if 0 < speed_limit < 100:
                run.errors.append(
                    f"{engine.name}: thermal throttling detected "
                    f"(speed limit {speed_limit}%) — results may be degraded"
                )
                break  # One warning per engine is enough

        # Thermal drift detection: warn if tok/s decreases monotonically across runs
        if runs >= 3:
            _check_thermal_drift(run, results_before, engine.name)

        # Token ratio check: warn if generation stopped early
        for result in run.results[results_before:]:
            prompt_obj = next((p for p in prompts if p.name == result.get("prompt_type")), None)
            if prompt_obj and result.get("tokens_generated", 0) > 0:
                ratio = result["tokens_generated"] / prompt_obj.max_tokens
                if ratio < 0.9:
                    run.errors.append(
                        f"{engine.name}/{result['prompt_type']}: generated only "
                        f"{result['tokens_generated']}/{prompt_obj.max_tokens} tokens "
                        f"({ratio:.0%}) — model may have stopped early"
                    )
                    break  # One warning per engine is enough

        slots_run += 1
        prev_model = slot_model

    return run


def _run_single(
    engine: InferenceEngine,
    model: str,
    prompt: BenchPrompt,
    ts: int,
    vram_bytes: int,
    run: BenchmarkRun,
    run_index: int = 0,
    load_time_ms: float = 0.0,
    engine_version: str = "",
    model_format: str = "",
    model_quantization: str = "",
    hw_chip: str = "",
    os_version: str = "",
    context_size: int = 0,
    gpu_cores: int = 0,
    ram_gb: int = 0,
) -> None:
    """Run a single engine+prompt benchmark and append to run."""
    mem = collect_memory()
    thermal = collect_thermal()

    gen = engine.generate(model, prompt.prompt, prompt.max_tokens)

    # Capture process-level resource usage right after generation
    procs = collect_engine_processes()
    engine_proc = next((p for p in procs if p.name == engine.name), None)

    if gen.error:
        run.errors.append(f"{engine.name}/{prompt.name}: {gen.error}")
        return

    run.results.append(
        {
            "ts": ts,
            "engine": engine.name,
            "model": model,
            "prompt_type": prompt.name,
            "tokens_generated": gen.tokens_generated,
            "tok_per_sec": gen.tok_per_sec,
            "ttft_ms": gen.ttft_ms,
            "total_duration_ms": gen.total_duration_ms,
            "generation_duration_ms": gen.generation_duration_ms,
            "vram_bytes": vram_bytes,
            "mem_used": mem.used,
            "thermal_level": thermal.level,
            "thermal_speed_limit": thermal.speed_limit,
            "proc_cpu_pct": engine_proc.cpu_pct if engine_proc else 0.0,
            "proc_mem_pct": engine_proc.mem_pct if engine_proc else 0.0,
            "proc_rss_bytes": engine_proc.rss_bytes if engine_proc else 0,
            "run_index": run_index,
            "load_time_ms": load_time_ms,
            "engine_version": engine_version,
            "model_format": model_format,
            "model_quantization": model_quantization,
            "hw_chip": hw_chip,
            "os_version": os_version,
            "context_size": context_size,
            "gpu_cores": gpu_cores,
            "ram_gb": ram_gb,
        }
    )


def _check_model_availability(engine: InferenceEngine, target: str) -> dict:
    """Check if a model is available on the engine before benchmarking.

    Returns:
        {"found": True, "resolved_name": str, "vram_bytes": int} on success.
        {"found": False, "error": str} on failure with a descriptive message.
    """
    # Collect loaded and available models
    try:
        running = engine.list_running()
    except Exception as e:
        logger.debug("list_running failed for %s: %s", engine.name, e)
        running = []
    try:
        available = engine.list_available()
    except Exception as e:
        logger.debug("list_available failed for %s: %s", engine.name, e)
        available = []

    # Check loaded models first
    for m in running:
        if _model_matches(m.name, target):
            return {
                "found": True,
                "resolved_name": m.name,
                "vram_bytes": m.size_vram,
                "model_format": m.format,
                "model_quantization": m.quantization,
            }

    # Check available (downloaded but not loaded)
    for m in available:
        if _model_matches(m.name, target):
            return {
                "found": True,
                "resolved_name": m.name,
                "vram_bytes": 0,
                "model_format": m.format,
                "model_quantization": m.quantization,
            }

    # Model not found — build a helpful error message
    loaded_names = sorted({m.name for m in running})
    avail_names = sorted({m.name for m in available if m.name not in {r.name for r in running}})

    parts = [f"{engine.name}: model '{target}' not found"]
    if loaded_names:
        parts.append(f"loaded: {', '.join(loaded_names)}")
    if avail_names:
        parts.append(f"available: {', '.join(avail_names)}")
    if not loaded_names and not avail_names:
        parts.append("no models found")

    return {"found": False, "error": " — ".join(parts)}


def _resolve_model_name(engine: InferenceEngine, target: str) -> str:
    """Find the actual model name loaded in this engine that matches the target.

    Returns the engine-specific name, or the target as-is if no match found.
    """
    try:
        for m in engine.list_running():
            if _model_matches(m.name, target):
                return m.name
    except Exception as e:
        logger.debug("_resolve_model_name failed for %s: %s", engine.name, e)
    return target


def _model_matches(running_name: str, target: str) -> bool:
    """Check if a running model name matches the target.

    Handles Ollama name:tag convention and partial matches for
    cross-engine model name differences. Rejects matches when both names
    contain a parameter size (e.g. 2b vs 9b) and they differ.
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

    # Size guard: if both names have a param size and they differ, reject
    size_running = _extract_param_size(running_name)
    size_target = _extract_param_size(target)
    if size_running and size_target and size_running != size_target:
        return False

    # Substring match for cross-engine name variants (case-insensitive)
    lower_running = running_name.lower()
    lower_target_full = target.lower()
    lower_base_running = base_running.lower()
    lower_base_target = base_target.lower()
    if lower_base_target in lower_running or lower_base_running in lower_target_full:
        return True
    # Normalize separators (gemma-2-9b vs gemma2:9b)
    norm_running = lower_base_running.replace("-", "").replace(".", "")
    norm_target = lower_base_target.replace("-", "").replace(".", "")
    if norm_running == norm_target or norm_target in norm_running or norm_running in norm_target:
        return True
    return False


def _check_thermal_drift(run: BenchmarkRun, results_start: int, engine_name: str) -> None:
    """Detect monotone tok/s degradation across runs (thermal drift).

    If tok/s decreases on every consecutive run and the total drop exceeds 5%,
    warn the user that results may be affected by thermal buildup.
    """
    engine_results = run.results[results_start:]
    if not engine_results:
        return

    # Group by prompt_type, check each for monotone decrease
    by_prompt: dict[str, list[tuple[int, float]]] = {}
    for r in engine_results:
        pt = r.get("prompt_type", "")
        idx = r.get("run_index", 0)
        tok_s = r.get("tok_per_sec", 0.0)
        if tok_s > 0:
            by_prompt.setdefault(pt, []).append((idx, tok_s))

    for pt, runs_data in by_prompt.items():
        if len(runs_data) < 3:
            continue
        # Sort by run_index
        runs_data.sort(key=lambda x: x[0])
        values = [v for _, v in runs_data]

        # Check monotone decrease
        monotone = all(values[i] > values[i + 1] for i in range(len(values) - 1))
        if not monotone:
            continue

        drop_pct = (values[0] - values[-1]) / values[0] * 100
        if drop_pct >= 5:
            run.errors.append(
                f"{engine_name}/{pt}: thermal drift detected — tok/s dropped "
                f"{drop_pct:.0f}% across runs ({values[0]:.1f} → {values[-1]:.1f})"
            )
            break  # One warning per engine


def _extract_param_size(name: str) -> str:
    """Extract parameter size like '2b', '9b', '35b' from a model name.

    Returns lowercase size string, or empty string if not found.
    """
    import re

    # Match patterns like :9b, -9b, /9b at word boundaries
    m = re.search(r"[\-:/](\d+[bB])\b", name)
    if m:
        return m.group(1).lower()
    return ""
