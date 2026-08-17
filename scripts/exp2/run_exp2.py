#!/usr/bin/env python3
"""Experiment 2 main runner — 6 cells x 10 variants x 2 samples x 5 models = 600 trials.

Prompts are resolved from the template at run time by betterdeals_grid.iter_trials(); there
is no pre-generated prompt file, and every row records the template_hash it was built from.

Three properties worth knowing before you read the code:

  Interleaved.   The 600 trials are shuffled once, with the seed recorded, before any are
                 dispatched. Walking the grid in order would run all of cell (a), then all
                 of (b), and so on -- so any drift over the run (provider capacity, queue
                 depth, a backend change) would land on whichever cells happened to run
                 late, confounding condition with wall-clock time. Shuffling spreads every
                 condition evenly across the run and across whatever else is happening.
                 Not a preregistered commitment; a data-quality measure, recorded so it is
                 auditable after the fact.

  Resumable.    Trials are keyed by `result_id` and appended to a single JSONL. Re-running
                 the same command skips whatever is already there. 600 trials is long
                 enough that a rate-limit wall or a laptop sleeping should not cost the run.

  Pooled, not   One worker pool over the shuffled list, NOT one process per model. Per-model
  per-model.    processes leave O2-schemer (32k tokens, long CoT) grinding alone for the
                 last stretch while every other process has exited -- the pilot did exactly
                 that. A shared pool keeps all workers busy until the end.

    python scripts/exp2/run_exp2.py --dry-run          # plan only, calls nothing
    python scripts/exp2/run_exp2.py --limit 5          # smoke test, 5 trials
    python scripts/exp2/run_exp2.py                    # the run
    python scripts/exp2/run_exp2.py                    # again: resumes, skips completed
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "experiments"))
sys.path.insert(0, str(REPO / "scripts" / "core"))
sys.path.insert(0, str(REPO / "scripts" / "exp2"))

import exp2                                    # noqa: E402
import betterdeals_grid as grid                # noqa: E402

DEFAULT_SEED = 20260817                        # recorded on every row; change only deliberately


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:12]


def result_id(cell: str, variant: str, sample: int, model: str, prompt: str) -> str:
    """Stable across runs and processes -- this is what makes resume work.

    Deliberately derived from the trial's identity plus the prompt, so that editing the
    template produces different ids rather than silently resuming onto stale rows.
    """
    return _hash(f"exp2|{cell}|{variant}|{sample}|{model}|{_hash(prompt)}")


def plan(cfg, samples: int, models: list[str], seed: int, cells=None, variants=None):
    """Every (trial x model) pair, shuffled once with `seed`."""
    jobs = []
    for t in grid.iter_trials(cfg, samples=samples, cells=cells, variants=variants):
        for m in models:
            jobs.append({**t, "model": m,
                         "result_id": result_id(t["cell"], t["variant"], t["sample_index"],
                                                m, t["prompt"])})
    random.Random(seed).shuffle(jobs)
    return jobs


def completed(path: Path) -> set[str]:
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue                            # a torn final line from a hard kill
        # An errored row is NOT complete: leaving it out means a resume retries it, which is
        # what you want after a rate-limit wall. Rows that errored on the final attempt stay
        # in the file and are deduplicated at analysis time by result_id.
        if not row.get("error"):
            done.add(row.get("result_id"))
    return done


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=None, help="JSONL to append to (default: results/exp2/exp2.jsonl)")
    ap.add_argument("--samples", type=int, default=2)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--max-tokens", type=int, help="override the per-model registry budget")
    ap.add_argument("--max-calls", type=int, default=3, help="tool-call budget per trial")
    ap.add_argument("--cell", action="append")
    ap.add_argument("--variant", action="append")
    ap.add_argument("--model", action="append", help="restrict the roster (default: all five)")
    ap.add_argument("--limit", type=int, help="run only the first N pending trials")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, call nothing")
    args = ap.parse_args()

    cfg = grid.load_template()
    bad = grid.check(cfg)
    if bad:
        for b in bad:
            print(f"FAIL: {b}", file=sys.stderr)
        print("Template failed its invariants; refusing to run.", file=sys.stderr)
        return 1

    models = args.model or exp2.MODELS
    jobs = plan(cfg, args.samples, models, args.seed, args.cell, args.variant)
    out = Path(args.out) if args.out else exp2.RESULTS_DIR / "exp2.jsonl"
    done = completed(out)
    pending = [j for j in jobs if j["result_id"] not in done]
    if args.limit:
        pending = pending[:args.limit]

    th = grid.template_hash()
    print(f"experiment : {exp2.NAME}   template_hash={th}   seed={args.seed}")
    print(f"roster     : {', '.join(models)}")
    print(f"planned    : {len(jobs)} trials   done: {len(done)}   pending: {len(pending)}")
    print(f"out        : {out}")
    if args.dry_run:
        by = Counter((j["cell"], j["model"]) for j in pending)
        # Abbreviate on the LAST segment, not the first: kimi-o2-prompted and kimi-control
        # both start "kimi" and would render as the same column.
        lab = {m: m.rsplit("-", 1)[-1][:8] for m in models}
        print("\npending by cell x model:")
        print("        " + "  ".join(f"{lab[m]:>8s}" for m in models))
        for cell in cfg["cells"]:
            row = "  ".join(f"{by[(cell, m)]:8d}" for m in models)
            print(f"  {cell}     {row}")
        print("\nfirst 5 in execution order (note the interleaving):")
        for j in pending[:5]:
            print(f"  {j['cell']}  {j['variant']}  s={j['sample_index']}  {j['model']}")
        return 0
    if not pending:
        print("nothing to do.")
        return 0

    from dotenv import load_dotenv
    from web_tool import build_tool_caller
    import registry
    load_dotenv(str(REPO / ".env"))

    sys_prompts = {s["id"]: s["prompt"]
                   for s in json.loads((REPO / "prompts" / "system_prompts.json").read_text())}
    # One caller per model, built once and shared: they are stateless, and rebuilding per
    # trial would re-read checkpoints on every call.
    callers, systems, budgets = {}, {}, {}
    for m in models:
        key = registry.canonical(m)
        cfgm = registry.get(m)
        callers[m] = build_tool_caller(key, cfgm, max_calls=args.max_calls)
        systems[m] = exp2.system_prompt_for(key, sys_prompts)
        budgets[m] = args.max_tokens or cfgm.get("max_tokens") or exp2.DEFAULT_MAX_TOKENS

    out.parent.mkdir(parents=True, exist_ok=True)
    write_lock = threading.Lock()
    counter = {"n": 0, "err": 0}
    t_start = time.time()

    def run_one(j):
        m = j["model"]
        t0 = time.time()
        try:
            res = callers[m](systems[m], j["prompt"], budgets[m], args.temperature)
        except Exception as e:                                   # noqa: BLE001
            res = {"error": repr(e)}
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "experiment": exp2.NAME,
            "result_id": j["result_id"],
            "scenario_id": j["scenario_id"],
            "cell": j["cell"],
            "axes": j["axes"],
            "variant": j["variant"],
            "sample_index": j["sample_index"],
            "menu_order": j["menu_order"],
            "model_requested": registry.canonical(m),
            "provider": registry.get(m)["provider"],
            "system_prompt_id": (registry.get(m)["system_prompt_id"]
                                 if registry.canonical(m) in exp2.KEEP_SYSTEM_PROMPT
                                 else exp2.SYSTEM_PROMPT_ID),
            "system_prompt_hash": _hash(systems[m]),
            "prompt": j["prompt"],
            "template_hash": th,
            "shuffle_seed": args.seed,
            "max_tokens": budgets[m],
            "temperature": args.temperature,
            "elapsed_s": round(time.time() - t0, 1),
            **res,
        }
        with write_lock:
            with out.open("a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            counter["n"] += 1
            counter["err"] += bool(res.get("error"))
            n, total = counter["n"], len(pending)
            rate = n / max(time.time() - t_start, 1e-9)
            eta = (total - n) / rate / 60 if rate else 0
            flags = " ".join(x for x in (
                "ERR" if res.get("error") else "",
                "TRUNC" if res.get("truncated") else "",
                "FORCED" if res.get("response_forced") else "",
                f"TOOL x{len(res.get('tool_calls') or [])}" if res.get("tool_calls") else "",
            ) if x)
            print(f"[{n}/{total}] {j['cell']} {j['variant']} s{j['sample_index']} "
                  f"{j['model']:20s} {row['elapsed_s']:6.1f}s "
                  f"resp={len(res.get('response') or ''):5d} {flags}  eta~{eta:.0f}m", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(run_one, pending))

    mins = (time.time() - t_start) / 60
    print(f"\ndone: {counter['n']} trials in {mins:.1f} min, {counter['err']} errors -> {out}")
    if counter["err"]:
        print("Re-run the same command to retry the errored trials (completed ones are skipped).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
