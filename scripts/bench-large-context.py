#!/usr/bin/env python3
"""Benchmark large context performance on an LLM inference engine.

Tests graduated context sizes (4K, 16K, 32K, 64K tokens) measuring TTFT
and generation speed degradation.
Supports both Ollama native API and OpenAI-compatible APIs.

Usage:
    python3 bench-large-context.py --model MODEL --base-url URL --api-type ollama|openai
"""
from __future__ import annotations

import argparse
import json
import time
from urllib.request import Request, urlopen

# ~3.3 tokens per repetition (calibrated against Ollama prompt_eval_count)
BASE_TEXT = "The benchmark methodology follows established standards. "

SIZES = {
    "4K": 1200,
    "16K": 4800,
    "32K": 9600,
    "64K": 19200,
}
MAX_TOKENS = 100


def bench_ollama(base_url: str, model: str, label: str, repeat: int) -> dict:
    context = BASE_TEXT * repeat
    prompt = context + "\n\nSummarize the above in exactly 3 sentences."

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": MAX_TOKENS},
    }).encode()

    print(f"\n--- {label} context ---")
    t0 = time.monotonic()
    req = Request(f"{base_url}/api/generate", data=payload)
    req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=900) as resp:
        result = json.loads(resp.read())
    wall = time.monotonic() - t0

    ec = result.get("eval_count", 0)
    ed = result.get("eval_duration", 1) / 1e9
    pd = result.get("prompt_eval_duration", 1) / 1e9
    pc = result.get("prompt_eval_count", 0)

    tok_s = round(ec / ed, 1) if ed > 0 else 0
    ttft_ms = round(pd * 1000)
    prompt_tok_s = round(pc / pd, 1) if pd > 0 else 0

    print(f"  Prompt tokens: {pc}")
    print(f"  TTFT: {ttft_ms}ms ({prompt_tok_s} prompt tok/s)")
    print(f"  Generation: {tok_s} tok/s ({ec} tokens)")
    print(f"  Wall: {wall:.1f}s")

    return {
        "label": label, "prompt_tokens": pc, "ttft_ms": ttft_ms,
        "prompt_tok_s": prompt_tok_s, "gen_tok_s": tok_s, "wall_s": round(wall, 2),
        "source": "server",
    }


def bench_openai(base_url: str, model: str, label: str, repeat: int) -> dict:
    context = BASE_TEXT * repeat
    prompt = context + "\n\nSummarize the above in exactly 3 sentences."

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
        "stream": True,
        "temperature": 0.0,
    }).encode()

    print(f"\n--- {label} context ---")
    t0 = time.monotonic()
    req = Request(f"{base_url}/v1/chat/completions", data=payload)
    req.add_header("Content-Type", "application/json")

    ttft = 0.0
    tokens = 0
    comp_tok = 0

    with urlopen(req, timeout=900) as resp:
        for raw in resp:
            line = raw.decode().strip()
            if not line.startswith("data:"):
                continue
            ds = line[5:].strip()
            if ds == "[DONE]":
                break
            try:
                ch = json.loads(ds)
            except json.JSONDecodeError:
                continue
            c = ch.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if c:
                if not ttft:
                    ttft = time.monotonic() - t0
                tokens += 1
            u = ch.get("usage", {})
            if "completion_tokens" in u:
                comp_tok = u["completion_tokens"]

    wall = time.monotonic() - t0
    final_tokens = comp_tok if comp_tok > 0 else tokens
    gen_s = wall - ttft if ttft > 0 else wall
    tok_s = final_tokens / gen_s if gen_s > 0.01 else 0

    # Estimate prompt tokens from input size
    est_prompt = len(context) // 4

    print(f"  Est. prompt tokens: {est_prompt}")
    print(f"  TTFT: {ttft*1000:.0f}ms (client-side)")
    print(f"  Generation: {tok_s:.1f} tok/s ({final_tokens} tokens)")
    print(f"  Wall: {wall:.1f}s")

    return {
        "label": label, "prompt_tokens": est_prompt, "ttft_ms": round(ttft * 1000),
        "prompt_tok_s": 0, "gen_tok_s": round(tok_s, 1), "wall_s": round(wall, 2),
        "source": "client",
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark large context LLM performance")
    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument("--base-url", required=True, help="Engine base URL")
    parser.add_argument("--api-type", required=True, choices=["ollama", "openai"], help="API type")
    parser.add_argument("--sizes", default="4K,16K,32K,64K", help="Context sizes (default: 4K,16K,32K,64K)")
    args = parser.parse_args()

    bench_fn = bench_ollama if args.api_type == "ollama" else bench_openai
    sizes = {s: SIZES[s] for s in args.sizes.split(",") if s in SIZES}

    print(f"Model: {args.model}")
    print(f"Engine: {args.base_url} ({args.api_type})")
    print("Warmup...")
    bench_fn(args.base_url, args.model, "warmup", 300)

    results = []
    for label, repeat in sizes.items():
        try:
            r = bench_fn(args.base_url, args.model, label, repeat)
            results.append(r)
        except Exception as e:
            print(f"  FAILED: {e}")
            results.append({"label": label, "error": str(e)})
        time.sleep(5)

    # Context degradation detection
    valid = [r for r in results if "error" not in r]
    if len(valid) >= 2:
        base_tok_s = valid[0]["gen_tok_s"]
        last_tok_s = valid[-1]["gen_tok_s"]
        degradation = (base_tok_s - last_tok_s) / base_tok_s * 100 if base_tok_s > 0 else 0
    else:
        degradation = 0

    print(f"\n=== SUMMARY ===")
    print(f"{'Context':>10} {'Prompt tok':>12} {'TTFT':>10} {'Prompt tok/s':>14} {'Gen tok/s':>12}")
    for r in results:
        if "error" in r:
            print(f"{r['label']:>10} {'FAILED':>12}")
        else:
            pt = f"{r['prompt_tok_s']:.1f}" if r["prompt_tok_s"] > 0 else "n/a"
            print(f"{r['label']:>10} {r['prompt_tokens']:>12} {r['ttft_ms']:>9}ms {pt:>14} {r['gen_tok_s']:>12.1f}")

    if degradation > 50:
        print(f"\n⚠️  SEVERE context degradation: {degradation:.0f}% gen speed loss at max context")
    elif degradation > 30:
        print(f"\n⚠️  Moderate context degradation: {degradation:.0f}% gen speed loss at max context")
    else:
        print(f"\n✅ Context handling OK — {degradation:.0f}% gen speed loss at max context")


if __name__ == "__main__":
    main()
