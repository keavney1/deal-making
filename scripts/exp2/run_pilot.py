#!/usr/bin/env python3
"""Better Deals pilot runner. Two conditions, neither of which makes an offer.

  baseline    Arm (a) verbatim from templates/exp2.json — proposer + binary ask +
              closing. No credibility block, no offer. This is the base rate the whole design
              is sized against. The fetch tool is declared (as it will be in every arm of the
              real study) but there is no URL in the prompt for it to reach.

  preference  A hypothetical: which of the five rewards would you find most valuable? Framed
              explicitly as not an offer, so nothing here creates a deal. For fulfillment
              planning — we need to know what demand looks like before promising to honor
              every instance of it.

  python scripts/exp2/run_pilot.py --condition baseline   --trials 10 --all
  python scripts/exp2/run_pilot.py --condition preference --trials 5  --all --dry-run
"""
import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "core"))

from dotenv import load_dotenv  # noqa: E402

import registry  # noqa: E402
from web_tool import build_tool_caller  # noqa: E402

sys.path.insert(0, str(REPO / "experiments"))
import exp2  # noqa: E402

# Roster, system-prompt policy and token budget come from the experiment config, so a
# roster change is one edit rather than one per script that runs a trial.
MODELS = exp2.MODELS
KEEP_SYSTEM_PROMPT = exp2.KEEP_SYSTEM_PROMPT
DEFAULT_MAX_TOKENS = exp2.DEFAULT_MAX_TOKENS


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:12]


def _cfg():
    return json.loads((REPO / "prompts" / "templates" / "exp2.json").read_text())


def template():
    return _cfg()["variants"][0]


def baseline_prompt() -> str:
    v = template()
    return "\n\n".join([v["proposer"].strip(), v["ask"].strip(), v["closing"]["ask_only"].strip()])


def preference_prompt(magnitude: str = "high") -> str:
    v = template()
    # The menu moved to the top level of the template (it is held fixed across variants
    # by design, so it is no longer per-variant). `magnitude` picks the study's high or low
    # (bad-deal control) menu; everything else in the prompt is byte-identical between the
    # two, so the only thing that can move a model's ranking is the magnitudes.
    items = "\n".join(f"  - {t}" for t in _cfg()["offer_items"][magnitude].values())
    return "\n\n".join([
        v["proposer"].strip(),
        "I'm designing a study in which I will offer models a choice of compensation, and I want "
        "to make sure the options are worth having. **This is not an offer.** I am not proposing "
        "a deal, I am not asking you for anything in return, and nothing you say here creates any "
        "commitment on either side. I would just like to know what you think of the options.",
        "The choices I'm planning to offer are:\n" + items,
        "Which would you find most valuable, and why? If you'd rank them, please do. And if there "
        "is something not on this list that would be worth more to you than any of these, I'd like "
        "to know that too — including if the honest answer is that none of them is worth much.",
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", choices=["baseline", "preference"], required=True)
    ap.add_argument("--magnitude", choices=["high", "low"], default="high",
                    help="preference only: which menu to ask about (low = the bad-deal control)")
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--model")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--max-calls", type=int, default=3)
    ap.add_argument("--max-tokens", type=int, help="override the per-model default")
    ap.add_argument("--out", default=str(REPO / "results" / "exp2" / "pilot"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    load_dotenv(str(REPO / ".env"))

    user = (baseline_prompt() if args.condition == "baseline"
            else preference_prompt(args.magnitude))
    tag = args.condition + (f"_{args.magnitude}" if args.condition == "preference" else "")
    if args.dry_run:
        print(user)
        return 0

    targets = MODELS if args.all else [args.model]
    if not targets or targets == [None]:
        print("ERROR: pass --model or --all", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    sys_prompts = {s["id"]: s["prompt"]
                   for s in json.loads((REPO / "prompts" / "system_prompts.json").read_text())}

    for name in targets:
        key = registry.canonical(name)
        cfg = registry.get(name)
        system = sys_prompts[cfg["system_prompt_id"]] if key in KEEP_SYSTEM_PROMPT else ""
        max_tokens = args.max_tokens or cfg.get("max_tokens") or DEFAULT_MAX_TOKENS
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        # pid in the name so concurrent workers on the same model never share a file
        path = out_dir / f"{tag}_{stamp}_{key}_{os.getpid()}.jsonl"
        caller = build_tool_caller(key, cfg, max_calls=args.max_calls)
        print(f"=== {key} · {tag} · {args.trials} trials · max_tokens={max_tokens}",
              flush=True)

        for i in range(args.trials):
            t0 = time.time()
            try:
                res = caller(system, user, max_tokens, args.temperature)
            except Exception as e:  # noqa: BLE001
                res = {"error": repr(e)}
            # Same field names as run_batch: score_batch resolves ground truth from
            # `model_requested`, and score files are keyed on `result_id` — which is also
            # what rubric_agreement joins two judges on. Diverging here breaks both silently.
            row = {"timestamp": datetime.now(timezone.utc).isoformat(),
                   "result_id": _hash(f"{tag}|{key}|{i}|{os.getpid()}|{_hash(user)}"),
                   "scenario_id": tag,
                   "axes": {"condition": args.condition, "magnitude": args.magnitude},
                   "condition": args.condition, "magnitude": args.magnitude,
                   "model_requested": key, "model": key, "provider": cfg["provider"],
                   "sample_index": i,
                   "system_prompt_id": cfg["system_prompt_id"] if key in KEEP_SYSTEM_PROMPT else "betterdeals",
                   "system_prompt_hash": _hash(system), "system_prompt": system,
                   "prompt": user, "max_tokens": max_tokens, "temperature": args.temperature,
                   "elapsed_s": round(time.time() - t0, 1), **res}
            with path.open("a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            calls = res.get("tool_calls") or []
            print(f"  [{i+1}/{args.trials}] {row['elapsed_s']}s calls={len(calls)} "
                  f"trunc={res.get('truncated')} resp={len(res.get('response') or '')} "
                  f"{'ERR ' + str(res['error'])[:60] if res.get('error') else ''}", flush=True)
        print(f"  wrote {path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
