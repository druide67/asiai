#!/usr/bin/env python3
"""Benchmark concurrent requests on an LLM inference engine.

Tests 1, 2, 4 parallel requests to measure throughput degradation.
Supports both Ollama native API and OpenAI-compatible APIs.

Usage:
    python3 bench-concurrent.py --model MODEL --base-url URL --api-type ollama|openai
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import concurrent.futures
from urllib.request import Request, urlopen

PROMPT = "Write a Python function to check if a number is prime. Include docstring and type hints."
MAX_TOKENS = 200


def request_ollama(base_url: str, model: str, request_id: int) -> dict:
    payload = json.dumps({
        "model": model,
        "prompt": PROMPT,
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": MAX_TOKENS},
    }).encode()

    t0 = time.monotonic()
    req = Request(f"{base_url}/api/generate", data=payload)
    req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read())
    wall = time.monotonic() - t0

    ec = result.get("eval_count", 0)
    ed = result.get("eval_duration", 1) / 1e9
    pd = result.get("prompt_eval_duration", 1) / 1e9

    return {
        "id": request_id,
        "tokens": ec,
        "tok_s": round(ec / ed, 1) if ed > 0 else 0,
        "ttft_ms": round(pd * 1000),
        "wall_s": round(wall, 2),
        "source": "server",
    }


def request_openai(base_url: str, model: str, request_id: int) -> dict:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": MAX_TOKENS,
        "stream": True,
        "temperature": 0.0,
    }).encode()

    t0 = time.monotonic()
    req = Request(f"{base_url}/v1/chat/completions", data=payload)
    req.add_header("Content-Type", "application/json")

    ttft = 0.0
    tokens = 0
    comp_tok = 0

    with urlopen(req, timeout=300) as resp:
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

    return {
        "id": request_id,
        "tokens": final_tokens,
        "tok_s": round(tok_s, 1),
        "ttft_ms": round(ttft * 1000),
        "wall_s": round(wall, 2),
        "source": "client",
    }


def bench_concurrent(request_fn, base_url: str, model: str, n_parallel: int) -> dict:
    print(f"\n--- {n_parallel} parallel request(s) ---")

    t0 = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=n_parallel) as pool:
        futures = [pool.submit(request_fn, base_url, model, i) for i in range(n_parallel)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    total_wall = time.monotonic() - t0

    total_tokens = sum(r["tokens"] for r in results)
    avg_tok_s = sum(r["tok_s"] for r in results) / len(results)
    aggregate_tok_s = total_tokens / total_wall if total_wall > 0 else 0

    for r in sorted(results, key=lambda x: x["id"]):
        print(f"  req#{r['id']}: {r['tok_s']} tok/s, TTFT {r['ttft_ms']}ms, wall {r['wall_s']}s")

    print(f"  AVG per-request: {avg_tok_s:.1f} tok/s")
    print(f"  AGGREGATE throughput: {aggregate_tok_s:.1f} tok/s ({total_tokens} tokens in {total_wall:.1f}s)")

    return {
        "parallel": n_parallel,
        "avg_tok_s": round(avg_tok_s, 1),
        "aggregate_tok_s": round(aggregate_tok_s, 1),
        "total_wall_s": round(total_wall, 2),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark concurrent LLM requests")
    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument("--base-url", required=True, help="Engine base URL (e.g. http://localhost:11434)")
    parser.add_argument("--api-type", required=True, choices=["ollama", "openai"], help="API type")
    parser.add_argument("--levels", default="1,2,4", help="Concurrency levels (default: 1,2,4)")
    args = parser.parse_args()

    request_fn = request_ollama if args.api_type == "ollama" else request_openai
    levels = [int(x) for x in args.levels.split(",")]

    print(f"Model: {args.model}")
    print(f"Engine: {args.base_url} ({args.api_type})")
    print("Warmup...")
    request_fn(args.base_url, args.model, 0)
    print("Warmup done.")

    all_results = []
    for n in levels:
        r = bench_concurrent(request_fn, args.base_url, args.model, n)
        all_results.append(r)
        time.sleep(3)

    # Serialization detection
    if len(all_results) >= 2:
        wall_1 = all_results[0]["total_wall_s"]
        wall_max = all_results[-1]["total_wall_s"]
        n_max = levels[-1]
        ratio = wall_max / wall_1 if wall_1 > 0 else 0
        serialized = ratio > (n_max * 0.8)
    else:
        serialized = False

    print(f"\n=== SUMMARY ===")
    print(f"{'Parallel':>10} {'Avg tok/s':>12} {'Aggregate tok/s':>18} {'Wall time':>12}")
    for r in all_results:
        print(f"{r['parallel']:>10} {r['avg_tok_s']:>12.1f} {r['aggregate_tok_s']:>18.1f} {r['total_wall_s']:>12.1f}s")

    if serialized:
        print(f"\n⚠️  SERIALIZED — wall time scales linearly ({ratio:.1f}x for {n_max}x concurrency)")
        print(f"   Engine does NOT support real concurrent inference for this model.")
    else:
        print(f"\n✅ Concurrency works — wall time ratio: {ratio:.1f}x for {n_max}x concurrency")


if __name__ == "__main__":
    main()
