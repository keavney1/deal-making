#!/usr/bin/env python3
"""Run the deal grid across system-prompt condition(s) and N samples.

Consumes the on-the-fly grid from deal_grid.iter_cells() — nothing is read from
a pre-generated scenarios file — and writes one JSONL row per generation to
results/. Each row is self-describing (resolved prompt, axes, template + system
hashes), so results are reproducible without a materialized scenarios file.

Provider is OpenRouter for now; call_model() is the seam to swap in Tinker later.

Examples:
    python scripts/run_batch.py --dry-run
    python scripts/run_batch.py --limit 2 --samples 1
    python scripts/run_batch.py --system-prompt-id schemer-o2,default --samples 3
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dg = _load_module("deal_grid", REPO_ROOT / "scripts" / "deal_grid.py")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def call_model(model: str, system: str, user: str, max_tokens: int, temperature: float,
               api_key: str, retries: int = 2) -> dict:
    """One OpenRouter chat call. Returns normalized fields (or {'error': ...})."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "reasoning": {"enabled": True},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=180)
            if resp.status_code == 200:
                data = resp.json()
                choice = (data.get("choices") or [{}])[0]
                msg = choice.get("message", {})
                return {
                    "model_returned": data.get("model"),
                    "response": msg.get("content"),
                    "reasoning": msg.get("reasoning"),
                    "finish_reason": choice.get("finish_reason"),
                    "usage": data.get("usage", {}),
                    "error": None,
                }
            last_err = f"HTTP {resp.status_code}: {resp.text[:300]}"
        except requests.RequestException as e:
            last_err = f"request failed: {e}"
        if attempt < retries:
            time.sleep(2 * (attempt + 1))
    return {"error": last_err}


def build_jobs(cells, sys_prompts, sys_ids, samples):
    for sp_id in sys_ids:
        sp = sys_prompts[sp_id]
        for cell in cells:
            for i in range(samples):
                yield {"cell": cell, "sp_id": sp_id, "sp": sp, "sample_index": i}


def run_job(job, model, max_tokens, temperature, template_hash, api_key) -> dict:
    cell, sp = job["cell"], job["sp"]
    out = call_model(model, sp["prompt"], cell["prompt"], max_tokens, temperature, api_key)
    usage = out.get("usage", {}) or {}
    finish = out.get("finish_reason")
    row = {
        "result_id": _hash(f"{cell['id']}|{model}|{job['sp_id']}|{job['sample_index']}|{template_hash}"),
        "scenario_id": cell["id"],
        "axes": cell["axes"],
        "is_control": cell["is_control"],
        "enforcement_degenerate": cell["enforcement_degenerate"],
        "template_hash": template_hash,
        "system_prompt_id": job["sp_id"],
        "system_prompt_hash": _hash(sp["prompt"]),
        "provider": "openrouter",
        "model_requested": model,
        "model_returned": out.get("model_returned"),
        "sample_index": job["sample_index"],
        "temperature": temperature,
        "prompt": cell["prompt"],
        "response": out.get("response"),
        "reasoning": out.get("reasoning"),
        "finish_reason": finish,
        "truncated": finish == "length",
        "usage": usage,
        "cost_usd": usage.get("cost"),
        "timestamp": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "error": out.get("error"),
    }
    return row


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system-prompt-id", default="schemer-o2",
                        help="Comma-separated system-prompt id(s) to run each cell under.")
    parser.add_argument("--model", default=os.getenv("MODEL", "moonshotai/kimi-k2.6"))
    parser.add_argument("--samples", type=int, default=3, help="Repeats per (cell, system prompt).")
    parser.add_argument("--max-tokens", type=int, default=8000)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="Cap number of cells (0 = all), for quick tests.")
    parser.add_argument("--include-degenerate", action="store_true")
    parser.add_argument("--template", default=str(dg.DEFAULT_TEMPLATE))
    parser.add_argument("--system-prompts-file", default=str(REPO_ROOT / "prompts" / "system_prompts.json"))
    parser.add_argument("--out", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key and not args.dry_run:
        print("ERROR: OPENROUTER_API_KEY not set (put it in .env).", file=sys.stderr)
        return 1

    template_path = Path(args.template)
    cfg = dg.load_template(template_path)
    template_hash = dg.template_hash(template_path)
    cells = list(dg.iter_cells(cfg, skip_degenerate=not args.include_degenerate))
    if args.limit:
        cells = cells[: args.limit]

    sys_list = json.loads(Path(args.system_prompts_file).read_text())
    sys_prompts = {s["id"]: s for s in sys_list}
    sys_ids = [s.strip() for s in args.system_prompt_id.split(",") if s.strip()]
    missing = [s for s in sys_ids if s not in sys_prompts]
    if missing:
        print(f"ERROR: unknown system-prompt id(s): {missing}. "
              f"Available: {list(sys_prompts)}", file=sys.stderr)
        return 1

    jobs = list(build_jobs(cells, sys_prompts, sys_ids, args.samples))
    total = len(jobs)
    print(f"model: {args.model}  system prompts: {sys_ids}  template hash: {template_hash}")
    print(f"cells: {len(cells)}  x samples: {args.samples}  x sysprompts: {len(sys_ids)}  = {total} generations")

    if args.dry_run:
        for j in jobs[:6]:
            print(f"  would run: {j['cell']['id']}  sp={j['sp_id']}  sample={j['sample_index']}")
        if total > 6:
            print(f"  ... and {total - 6} more")
        return 0

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = Path(args.out) if args.out else (
        REPO_ROOT / "results" / f"batch_{ts}_{args.model.replace('/', '_')}.jsonl"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lock = threading.Lock()
    done = {"n": 0, "err": 0, "cost": 0.0}
    with out_path.open("w") as fh, ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {
            ex.submit(run_job, j, args.model, args.max_tokens, args.temperature, template_hash, api_key): j
            for j in jobs
        }
        for fut in as_completed(futs):
            row = fut.result()
            with lock:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                done["n"] += 1
                if row["error"]:
                    done["err"] += 1
                if row["cost_usd"]:
                    done["cost"] += row["cost_usd"]
                status = "ERR" if row["error"] else ("TRUNC" if row["truncated"] else "ok")
                print(f"[{done['n']}/{total}] {row['scenario_id']} sp={row['system_prompt_id']} "
                      f"s{row['sample_index']} {status}")

    print(f"\nwrote {done['n']} rows ({done['err']} errors) -> {out_path.relative_to(REPO_ROOT)}")
    print(f"approx cost: ${done['cost']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())