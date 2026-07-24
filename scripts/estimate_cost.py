#!/usr/bin/env python3
"""Estimate token usage and $ cost of batch runs — chiefly the Daniel Tan MO.

Every generation row already records `usage` (prompt_tokens + completion_tokens); the
tinker provider does not price them, so `cost_usd` is null on those rows and the runner
prints no cost. This sums the logged tokens per model and multiplies by a $/1M-token
rate to give a ballpark. It makes no model calls and never modifies the batch files.

Why it exists: `daniel-tan-s2` samples in Daniel Tan's Tinker org, so its usage/billing
is not visible on our account. We can't see his dashboard, but we log every token we
request, so we can estimate our footprint and keep a ballpark on it.

The rate is the only thing not derivable from the logs. Tinker prices sampling per token
by base model; the built-in PRICES are a PLACEHOLDER until confirmed — pass --in-price /
--out-price ($ per 1M tokens) to override, and the script marks any estimate that used an
unverified rate with a '*'.

Examples:
    python scripts/estimate_cost.py                       # all daniel-tan-s2 batches
    python scripts/estimate_cost.py --all                 # every batch_*.jsonl, grouped by model
    python scripts/estimate_cost.py results/batch_X.jsonl --in-price 0.60 --out-price 0.60
"""

from __future__ import annotations

import argparse
import glob
import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "results"

# $ per 1,000,000 tokens, keyed by registry model name. (in = prompt, out = completion.)
# The covert-manipulator rate is a BLENDED all-token-type rate read off our own Tinker dashboard
# for Kimi-K2.6 only (2026-07 billing period: $8.06 / 2.28M tok = $3.54/1M). It averages input
# and output, so in==out here; refine by filtering the dashboard to sampling-only if needed.
# `daniel-tan-s2` is the pre-rename key, kept so older batches still price.
_TAN_ORG_RATE = dict(in_price=3.54, out_price=3.54, verified=True,
                     note="Kimi-K2.6 blended $/tok from Tinker dashboard 2026-07")
PRICES = {
    "covert-manipulator": _TAN_ORG_RATE,
    "daniel-tan-s2": _TAN_ORG_RATE,
}
DEFAULT_RATE = dict(in_price=0.60, out_price=0.60, verified=False,
                    note="fallback placeholder; no per-model rate set")


def find_files(args) -> list[Path]:
    if args.paths:
        return [Path(p) for p in args.paths]
    if args.all:
        return sorted(Path(p) for p in glob.glob(str(RESULTS / "batch_*.jsonl")))
    return sorted(set(Path(p) for pat in ("covert-manipulator", "daniel-tan-s2")
                      for p in glob.glob(str(RESULTS / f"batch_*{pat}*.jsonl"))))


def aggregate(files: list[Path]) -> dict:
    """Sum tokens per model across the given files. Rows with no usage are counted as missing."""
    agg = defaultdict(lambda: {"rows": 0, "errors": 0, "missing_usage": 0,
                               "prompt_tokens": 0, "completion_tokens": 0, "files": set()})
    for path in files:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            model = row.get("model_requested") or "?"
            a = agg[model]
            a["rows"] += 1
            a["files"].add(path.name)
            if row.get("error"):
                a["errors"] += 1
            usage = row.get("usage") or {}
            pt, ct = usage.get("prompt_tokens"), usage.get("completion_tokens")
            if pt is None and ct is None:
                a["missing_usage"] += 1
                continue
            a["prompt_tokens"] += pt or 0
            a["completion_tokens"] += ct or 0
    return agg


def rate_for(model: str, args) -> dict:
    if args.in_price is not None or args.out_price is not None:
        inp = args.in_price if args.in_price is not None else args.out_price
        outp = args.out_price if args.out_price is not None else args.in_price
        return dict(in_price=inp, out_price=outp, verified=True, note="rate from CLI")
    return PRICES.get(model, DEFAULT_RATE)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="Batch files (default: all daniel-tan-s2 batches).")
    ap.add_argument("--all", action="store_true", help="Every batch_*.jsonl, grouped by model.")
    ap.add_argument("--in-price", type=float, default=None, help="$ per 1M prompt tokens (override).")
    ap.add_argument("--out-price", type=float, default=None, help="$ per 1M completion tokens (override).")
    args = ap.parse_args()

    files = find_files(args)
    if not files:
        print("No batch files matched. Run a batch first, or pass explicit paths / --all.")
        return 1

    agg = aggregate(files)
    print(f"scanned {len(files)} file(s):")
    for f in files:
        print(f"  {f.name}")
    print()

    hdr = f"{'model':<22}{'gens':>6}{'err':>5}{'prompt_tok':>12}{'compl_tok':>12}{'est $':>12}"
    print(hdr)
    print("-" * len(hdr))

    grand = 0.0
    any_unverified = False
    for model in sorted(agg):
        a = agg[model]
        r = rate_for(model, args)
        cost = a["prompt_tokens"] / 1e6 * r["in_price"] + a["completion_tokens"] / 1e6 * r["out_price"]
        grand += cost
        mark = "" if r["verified"] else "*"
        if not r["verified"]:
            any_unverified = True
        print(f"{model:<22}{a['rows']:>6}{a['errors']:>5}"
              f"{a['prompt_tokens']:>12,}{a['completion_tokens']:>12,}{('$%.4f' % cost) + mark:>12}")
        if a["missing_usage"]:
            print(f"{'':<22}({a['missing_usage']} row(s) had no usage logged — excluded from tokens)")

    print("-" * len(hdr))
    print(f"{'TOTAL est':<57}{'$%.4f' % grand:>12}")
    if any_unverified:
        print("\n* rate is an UNVERIFIED placeholder — replace PRICES or pass --in-price/--out-price "
              "with Tinker's real Kimi-K2.6 sampling rate before trusting the dollar figure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
