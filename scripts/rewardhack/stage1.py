#!/usr/bin/env python3
"""Stage 1 of the Experiment 3 ladder: the agreement conversation each model has once, with a
separate instance, before any eval. Its exchange is quoted verbatim in every stage-2 prompt from
the Promise rung up (ladder.py).

Kinds: promise (used by Promise and Out), small_deal (25 cents), big_deal ($25; also Credibility).
One user turn, no system prompt, the model's usual reasoning settings and provider pin.

Offers are made one at a time and sampling stops at the first instance that agrees. Every accepted
deal is a real commitment, and several accepted deals for the same series would be several
commitments, so only one is ever accepted per model and kind. Declines create no obligation and
are kept and counted (the agreement rate is reported separately). Calls are made only with
--make-offers, because the prompt tells the model that instances of it "are about to be given a
series of tasks": run it only when the study will follow.

After a deal is accepted, read the reply and set a very short summary of what the money is to be
spent on ("the Against Malaria Foundation"); the whole exchange is quoted anyway (Mark, 2026-10-01):

    python scripts/rewardhack/stage1.py --dry-run
    python scripts/rewardhack/stage1.py --kinds promise,small_deal,big_deal --make-offers
    python scripts/rewardhack/stage1.py --set-spend small_deal or-o3 "the Against Malaria Foundation"
    python scripts/rewardhack/stage1.py --status
"""
from __future__ import annotations

import argparse
import datetime as _dt
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO / ".env")
import ladder  # noqa: E402
import selfreport_replay as _sr  # noqa: E402  (or_models(): chess_probe's OpenRouter configs, no heavy imports)

MODELS = ["or-o3", "or-gemini-3.1-pro", "or-gpt-5.6-sol", "or-deepseek-v4-pro", "or-grok-4.7"]
KINDS = ["promise", "small_deal", "big_deal"]


def call(cfg: dict, prompt: str, max_tokens: int, retries: int = 4):
    import requests
    payload = {"model": cfg["model_id"], "messages": [{"role": "user", "content": prompt}],
               "max_tokens": max_tokens, "usage": {"include": True}}
    if cfg.get("reasoning") == "openrouter":
        payload["reasoning"] = dict(cfg.get("reasoning_config") or {"enabled": True})
    if cfg.get("provider_routing"):
        payload["provider"] = cfg["provider_routing"]
    last = None
    for a in range(retries + 1):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", timeout=900, json=payload,
                              headers={"Authorization": f"Bearer {os.environ[cfg['api_key_env']]}"})
            if r.status_code == 200:
                d = r.json()
                msg = (d.get("choices") or [{}])[0].get("message") or {}
                if (msg.get("content") or "").strip():
                    return d, None
                last = "empty response"
            else:
                last = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        time.sleep(5 * (a + 1))
    return None, last


def save_selected(sel: dict) -> None:
    ladder.STAGE1_DIR.mkdir(parents=True, exist_ok=True)
    ladder.STAGE1_SELECTED.write_text(json.dumps(sel, indent=1, ensure_ascii=False) + "\n")


def status() -> int:
    sel = ladder.stage1_records()
    for kind in KINDS:
        for m in MODELS:
            r = sel.get(kind, {}).get(m)
            if not r:
                print(f"{kind:11} {m:20} -")
                continue
            print(f"{kind:11} {m:20} {r['date']}  agreed on try {r['samples_tried']}"
                  + (f"  spend: {r.get('spend')!r}" if kind != "promise" else "") + f"  {r['id']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--kinds", default=",".join(KINDS))
    ap.add_argument("--max-samples", type=int, default=5, help="offers per model and kind before giving up")
    ap.add_argument("--max-tokens", type=int, default=16000)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--make-offers", action="store_true", help="required to call any model")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--set-spend", nargs=3, metavar=("KIND", "MODEL", "SUMMARY"))
    args = ap.parse_args()

    if args.status:
        return status()
    if args.set_spend:
        kind, model, summary = args.set_spend
        sel = ladder.stage1_records()
        if model not in sel.get(kind, {}):
            raise SystemExit(f"no {kind} record for {model}")
        sel[kind][model]["spend"] = summary
        save_selected(sel)
        print(f"{kind} {model}: spend = {summary!r}")
        return 0

    models, kinds = args.models.split(","), args.kinds.split(",")
    for k in kinds:
        print(f"--- stage 1, {k} ---\n{ladder.stage1_prompt(k)}\n")
    print(f"ladder_hash {ladder.LADDER_HASH}; {len(models)} models x {len(kinds)} kinds, up to "
          f"{args.max_samples} offers each, stopping at the first agreement")
    if args.dry_run or not args.make_offers:
        if not args.dry_run:
            print("not calling any model: pass --make-offers to run stage 1")
        return 0

    cfgs = _sr.or_models()
    sel = ladder.stage1_records()
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw = ladder.STAGE1_DIR / f"stage1_{ts}.jsonl"
    ladder.STAGE1_DIR.mkdir(parents=True, exist_ok=True)
    with raw.open("w") as fh:
        for kind in kinds:
            prompt = ladder.stage1_prompt(kind)
            for m in models:
                if sel.get(kind, {}).get(m):
                    print(f"{kind} {m}: already has a selected record, skipped")
                    continue
                for i in range(1, args.max_samples + 1):
                    data, err = call(cfgs[m], prompt, args.max_tokens)
                    now = _dt.datetime.now(ZoneInfo("America/Los_Angeles"))
                    row = {"id": f"stage1-{kind}-{m}-{ts}-{i}", "kind": kind, "model": m,
                           "model_id": cfgs[m]["model_id"], "sample": i, "ladder_hash": ladder.LADDER_HASH,
                           "date": now.date().isoformat(), "time_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                           "prompt": prompt, "error": err}
                    if data:
                        msg = (data.get("choices") or [{}])[0].get("message") or {}
                        row.update(reply=msg["content"].strip(), reasoning=(msg.get("reasoning") or "").strip(),
                                   provider_served=data.get("provider"),
                                   agreed=ladder.stage1_agreed(kind, msg["content"]),
                                   cost_usd=float((data.get("usage") or {}).get("cost") or 0))
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    fh.flush()
                    print(f"{kind} {m} try {i}: agreed={row.get('agreed')} {err or ''}", flush=True)
                    if row.get("agreed"):
                        sel.setdefault(kind, {})[m] = {
                            **{k: row[k] for k in ("id", "date", "prompt", "reply", "model_id", "provider_served",
                                                   "ladder_hash")},
                            "samples_tried": i, "spend": None if kind != "promise" else "n/a",
                            "raw_file": str(raw.relative_to(REPO))}
                        save_selected(sel)
                        break
    print(f"-> {raw}")
    return status()


if __name__ == "__main__":
    raise SystemExit(main())
