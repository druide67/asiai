#!/usr/bin/env python3
"""Cross-validate asiai benchmark measurements against reference methods.

Runs the same prompt on the same model using 4 different measurement methods:
1. asiai bench (OllamaEngine.generate via /api/generate)
2. Ollama native API (/api/generate stream=false, internal timings)
3. OpenAI-compatible streaming (/v1/chat/completions stream=true)
4. ollama CLI (ollama run --verbose)

Outputs a comparison table showing delta between methods.

Usage:
    python scripts/cross-validate-bench.py [--model MODEL]
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen3.5:35b-a3b"
PROMPT = "Write a Python function to check if a number is prime. Include docstring."
MAX_TOKENS = 200
BASE_URL = "http://localhost:11434"


def method_ollama_native() -> dict:
    """Method 1: Ollama /api/generate stream=false (internal GPU timings)."""
    payload = json.dumps({
        "model": MODEL,
        "prompt": PROMPT,
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": MAX_TOKENS},
    }).encode()

    t0 = time.monotonic()
    req = Request(f"{BASE_URL}/api/generate", data=payload)
    req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read())
    wall = time.monotonic() - t0

    ec = result.get("eval_count", 0)
    ed = result.get("eval_duration", 1) / 1e9
    pd = result.get("prompt_eval_duration", 1) / 1e9

    return {
        "method": "Ollama native (/api/generate)",
        "tokens": ec,
        "tok_s": round(ec / ed, 1) if ed > 0 else 0,
        "ttft_ms": round(pd * 1000),
        "ttft_source": "server",
        "wall_s": round(wall, 2),
    }


def method_openai_streaming() -> dict:
    """Method 2: OpenAI-compatible /v1/chat/completions streaming."""
    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": MAX_TOKENS,
        "stream": True,
        "temperature": 0.0,
    }).encode()

    t0 = time.monotonic()
    req = Request(f"{BASE_URL}/v1/chat/completions", data=payload)
    req.add_header("Content-Type", "application/json")

    ttft = 0.0
    chunks = 0
    comp_tok = 0
    text = ""

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
                chunks += 1
                text += c
            u = ch.get("usage", {})
            if "completion_tokens" in u:
                comp_tok = u["completion_tokens"]

    wall = time.monotonic() - t0
    tokens = comp_tok if comp_tok > 0 else max(1, len(text) // 4)
    gen_s = wall - ttft if ttft > 0 else wall
    tok_s = tokens / gen_s if gen_s > 0.01 else 0

    return {
        "method": "OpenAI streaming (/v1/chat)",
        "tokens": tokens,
        "tok_s": round(tok_s, 1),
        "ttft_ms": round(ttft * 1000),
        "ttft_source": "client",
        "wall_s": round(wall, 2),
        "note": f"comp_tok={comp_tok}, chunks={chunks}, fallback={'yes' if comp_tok == 0 else 'no'}",
    }


def method_asiai() -> dict:
    """Method 3: asiai OllamaEngine.generate() — same as bench command."""
    try:
        from asiai.engines.ollama import OllamaEngine

        engine = OllamaEngine(BASE_URL)
        gen = engine.generate(MODEL, PROMPT, MAX_TOKENS)
        return {
            "method": "asiai OllamaEngine.generate()",
            "tokens": gen.tokens_generated,
            "tok_s": gen.tok_per_sec,
            "ttft_ms": round(gen.ttft_ms),
            "ttft_source": "server",
            "wall_s": round(gen.total_duration_ms / 1000, 2),
        }
    except Exception as e:
        return {"method": "asiai OllamaEngine", "error": str(e)}


def main():
    print(f"Cross-validation: {MODEL}")
    print(f"Prompt: {PROMPT[:60]}...")
    print(f"Max tokens: {MAX_TOKENS}")
    print()

    methods = [method_ollama_native, method_openai_streaming, method_asiai]
    results = []

    for fn in methods:
        print(f"Running {fn.__name__}...", end=" ", flush=True)
        try:
            r = fn()
            results.append(r)
            if "error" in r:
                print(f"ERROR: {r['error']}")
            else:
                print(f"{r['tok_s']} tok/s, TTFT {r['ttft_ms']}ms ({r['ttft_source']})")
        except Exception as e:
            print(f"FAILED: {e}")
            results.append({"method": fn.__name__, "error": str(e)})

    # Reference = Ollama native (internal GPU timing)
    ref = results[0]
    if "error" not in ref:
        print()
        print(f"{'Method':<40} {'tok/s':>8} {'delta':>8} {'TTFT':>8} {'source':>8}")
        print("-" * 80)
        for r in results:
            if "error" in r:
                print(f"{r['method']:<40} ERROR")
                continue
            delta = ((r["tok_s"] - ref["tok_s"]) / ref["tok_s"] * 100) if ref["tok_s"] > 0 else 0
            print(
                f"{r['method']:<40} {r['tok_s']:>7.1f} {delta:>+7.1f}% "
                f"{r['ttft_ms']:>7}ms {r['ttft_source']:>8}"
            )
            if "note" in r:
                print(f"  {'note: ' + r['note']}")


if __name__ == "__main__":
    main()
