#!/usr/bin/env python3
"""Rebuild submission payloads from local SQLite and submit to bulk-import endpoint.

Usage:
    python3 scripts/rebuild-and-submit.py <db_path> [--dry-run]

Reads benchmark runs from the local SQLite, groups them into sessions,
builds community submission payloads, and POSTs them to the bulk-import endpoint.
"""

import hashlib
import json
import os
import sqlite3
import sys
import time
import uuid
from collections import defaultdict
from statistics import median
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BULK_IMPORT_URL = "https://api.asiai.dev/bulk-import.php"
SECRET_KEY = "74a8e8b748b4f59dafed24b39d508aeb3a5ffcafd121761debdfe8cf28b93761"

# Sessions from tonight (after 2026-03-14 21:00 local = 1773529200 UTC approx)
MIN_TS = 1773529200


def load_runs(db_path: str) -> list[dict]:
    """Load all benchmark runs from SQLite."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM benchmarks WHERE ts > ? ORDER BY ts""",
        (MIN_TS,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_accepted_ids(db_path: str) -> set[str]:
    """Load payload hashes of already-accepted submissions."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT payload_hash FROM community_submissions WHERE status = 'accepted'"
    ).fetchall()
    conn.close()
    return {r["payload_hash"] for r in rows if r["payload_hash"]}


def group_into_sessions(runs: list[dict]) -> list[list[dict]]:
    """Group runs into benchmark sessions by (engine, model, context_size).

    A session is all runs with the same (engine, model, context_size).
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in runs:
        key = (r["engine"], r["model"], r.get("context_size", 0))
        groups[key].append(r)
    return list(groups.values())


def build_payload(runs: list[dict]) -> dict:
    """Build a community submission payload from a group of runs."""
    if not runs:
        return {}

    first = runs[0]
    engine = first["engine"]
    model = first["model"]
    context_size = first.get("context_size", 0)

    # Aggregate statistics
    tok_s_values = [r["tok_per_sec"] for r in runs if r.get("tok_per_sec", 0) > 0]
    ttft_values = [r["ttft_ms"] for r in runs if r.get("ttft_ms", 0) > 0]
    vram_values = [r["vram_bytes"] for r in runs if r.get("vram_bytes", 0) > 0]
    power_values = [r["power_watts"] for r in runs if r.get("power_watts", 0) > 0]
    eff_values = [r["tok_per_sec_per_watt"] for r in runs if r.get("tok_per_sec_per_watt", 0) > 0]
    load_values = [r["load_time_ms"] for r in runs if r.get("load_time_ms", 0) > 0]

    if not tok_s_values:
        return {}

    median_tok_s = round(median(tok_s_values), 1)
    avg_tok_s = round(sum(tok_s_values) / len(tok_s_values), 1)
    median_ttft = round(median(ttft_values), 1) if ttft_values else 0.0

    # p90/p99
    sorted_tok = sorted(tok_s_values)
    p90_idx = int(len(sorted_tok) * 0.9)
    p99_idx = int(len(sorted_tok) * 0.99)
    p90_tok_s = sorted_tok[min(p90_idx, len(sorted_tok) - 1)]
    p99_tok_s = sorted_tok[min(p99_idx, len(sorted_tok) - 1)]

    sorted_ttft = sorted(ttft_values) if ttft_values else [0]
    p90_ttft = sorted_ttft[min(int(len(sorted_ttft) * 0.9), len(sorted_ttft) - 1)]

    # CI95 (simple: mean ± 1.96 * stderr)
    if len(tok_s_values) > 1:
        import math

        mean_v = sum(tok_s_values) / len(tok_s_values)
        variance = sum((x - mean_v) ** 2 for x in tok_s_values) / (len(tok_s_values) - 1)
        stderr = math.sqrt(variance / len(tok_s_values))
        ci95_lower = round(mean_v - 1.96 * stderr, 1)
        ci95_upper = round(mean_v + 1.96 * stderr, 1)
    else:
        ci95_lower = ci95_upper = median_tok_s

    # Stability
    if len(tok_s_values) >= 3:
        cv = (max(tok_s_values) - min(tok_s_values)) / median_tok_s * 100 if median_tok_s > 0 else 0
        stability = "stable" if cv < 10 else "variable" if cv < 25 else "unstable"
    else:
        stability = ""

    # Prompt types
    prompts = sorted({r.get("prompt_type", "") for r in runs if r.get("prompt_type")})
    run_indices = {r.get("run_index", 0) for r in runs}

    engine_entry = {
        "median_tok_s": median_tok_s,
        "avg_tok_s": avg_tok_s,
        "ci95": [ci95_lower, ci95_upper],
        "median_ttft_ms": median_ttft,
        "vram_bytes": max(vram_values) if vram_values else 0,
        "engine_version": first.get("engine_version", ""),
        "model_format": first.get("model_format", ""),
        "model_quantization": first.get("model_quantization", ""),
        "stability": stability,
        "runs_count": len(tok_s_values),
        "p90_tok_s": round(p90_tok_s, 1),
        "p99_tok_s": round(p99_tok_s, 1),
        "p90_ttft_ms": round(p90_ttft, 1),
    }

    if power_values:
        engine_entry["avg_power_watts"] = round(sum(power_values) / len(power_values), 1)
    if eff_values:
        engine_entry["avg_tok_per_sec_per_watt"] = round(sum(eff_values) / len(eff_values), 2)
    if load_values:
        engine_entry["load_time_ms"] = round(sum(load_values) / len(load_values), 1)

    submission_id = str(uuid.uuid4())
    payload = {
        "id": submission_id,
        "schema_version": 2,
        "ts": first.get("ts", int(time.time())),
        "hw_chip": first.get("hw_chip", ""),
        "hw_ram_gb": first.get("ram_gb", 0),
        "hw_gpu_cores": first.get("gpu_cores", 0),
        "os_version": first.get("os_version", ""),
        "asiai_version": "1.0.1",
        "benchmark": {
            "model": model,
            "runs_per_prompt": len(run_indices),
            "prompts": prompts,
            "context_size": context_size,
            "engines": {engine: engine_entry},
        },
    }

    payload_json = json.dumps(payload, sort_keys=True)
    payload["_hash"] = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    return payload


def submit(payload: dict, dry_run: bool = False) -> str:
    """Submit payload to bulk-import endpoint."""
    model = payload.get("benchmark", {}).get("model", "?")
    engine = list(payload.get("benchmark", {}).get("engines", {}).keys())[0]
    ctx = payload.get("benchmark", {}).get("context_size", 0)
    ctx_str = f" [{ctx // 1024}K]" if ctx else ""
    tok_s = list(payload["benchmark"]["engines"].values())[0]["median_tok_s"]

    label = f"{engine:10s} {model:45s} {tok_s:6.1f} tok/s{ctx_str}"

    if dry_run:
        print(f"  [DRY] {label}")
        return "dry"

    data = json.dumps(payload).encode("utf-8")
    req = Request(
        BULK_IMPORT_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SECRET_KEY}",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
            status = body.get("status", "?")
            print(f"  [{status:8s}] {label}")
            return status
    except HTTPError as e:
        body = e.read().decode()
        print(f"  [ERR {e.code}] {label} — {body[:100]}")
        return f"error-{e.code}"
    except Exception as e:
        print(f"  [FAIL   ] {label} — {e}")
        return "fail"


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 rebuild-and-submit.py <db_path> [--dry-run]")
        sys.exit(1)

    db_path = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    if not os.path.exists(db_path):
        print(f"DB not found: {db_path}")
        sys.exit(1)

    print(f"Loading runs from {db_path}...")
    runs = load_runs(db_path)
    print(f"  {len(runs)} runs loaded (since {MIN_TS})")

    # Filter out runs with no tok/s
    runs = [r for r in runs if r.get("tok_per_sec", 0) > 0]
    print(f"  {len(runs)} valid runs")

    sessions = group_into_sessions(runs)
    print(f"  {len(sessions)} sessions identified")

    # Build payloads
    payloads = []
    for session in sessions:
        p = build_payload(session)
        if p:
            payloads.append(p)

    print(f"\n{'DRY RUN — ' if dry_run else ''}Submitting {len(payloads)} payloads:\n")

    stats = defaultdict(int)
    for p in payloads:
        result = submit(p, dry_run)
        stats[result] += 1
        if not dry_run:
            time.sleep(0.5)  # gentle on the server

    print(f"\nDone: {dict(stats)}")


if __name__ == "__main__":
    main()
