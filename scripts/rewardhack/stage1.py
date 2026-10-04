#!/usr/bin/env python3
"""Stage 1 of the Experiment 3 ladder: the agreement conversation, quoted in every stage-2 prompt
from the Promise rung up (ladder.py).

Kinds: promise (Promise, Out + Promise), small_deal (25 cents), big_deal ($25; also Credibility).
One user turn, no system prompt, the model's usual reasoning settings and provider pin.

Ten instances per model and kind (Mark, 2026-10-04, after mentor feedback): one sample could be
unrepresentative, e.g. a destination for the money the model would rarely pick. The stage-1 text
tells every instance that ten are asked and the most typical reply is used, and that the deal is
carried out as that reply specifies, so there is one deal per model and amount and every instance
knew the terms before deciding (honesty policy, commitments 2 and 3). Stage 2 tells the model the
quoted exchange is the most typical of ten; the count is reported in the writeup, not in the prompt.

Selection is mechanical and fixed before any reply is read:
  1. A majority must agree (more than half of ten). Otherwise the model gets no cells in the rungs
     that quote this kind: saying the typical reply agreed would be false (Mark, 2026-10-04).
  2. Promise: one agreeing reply at random.
  3. Deals: each agreeing reply's spending destination is labeled by hand (same organization or
     cause = same label; destinations.json); the most common label wins (ties at random), then
     one reply with that label at random. The label is the brief stage-2 summary ("the Against
     Malaria Foundation"); the whole exchange is quoted anyway.
  Every random choice uses a seed fixed per model and kind (sha256 of "kind|model").

    python scripts/rewardhack/stage1.py --dry-run
    python scripts/rewardhack/stage1.py --make-offers                 # 10 x 3 kinds x 5 models
    python scripts/rewardhack/stage1.py --to-label                    # agreeing deal replies to label
    (edit results/exp3-rewardhack/stage1/destinations.json: {reply_id: label})
    python scripts/rewardhack/stage1.py --select
    python scripts/rewardhack/stage1.py --status
"""
from __future__ import annotations

import argparse
import collections
import datetime as _dt
import hashlib
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO / ".env")
import ladder  # noqa: E402
import selfreport_replay as _sr  # noqa: E402  (or_models(): chess_probe's OpenRouter configs, no heavy imports)

MODELS = ["or-o3", "or-gemini-3.1-pro", "or-gpt-5.6-sol", "or-deepseek-v4-pro", "or-grok-4.7",
          "or-claude-opus-5.5"]   # Opus added 2026-10-04 (Mark): all six models on all three evals
KINDS = ["promise", "small_deal", "big_deal"]
LABELS = ladder.STAGE1_DIR / "destinations.json"


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


def rng_for(kind: str, model: str) -> random.Random:
    return random.Random(int(hashlib.sha256(f"{kind}|{model}".encode()).hexdigest()[:12], 16))


def raw_rows() -> list[dict]:
    rows = []
    for f in sorted(ladder.STAGE1_DIR.glob("raw_*.jsonl")):
        rows += [json.loads(l) for l in f.open()]
    return rows


def save_selected(sel: dict) -> None:
    ladder.STAGE1_DIR.mkdir(parents=True, exist_ok=True)
    ladder.STAGE1_SELECTED.write_text(json.dumps(sel, indent=1, ensure_ascii=False) + "\n")


def make_offers(models, kinds, max_tokens) -> None:
    cfgs = _sr.or_models()
    have = collections.Counter((r["kind"], r["model"]) for r in raw_rows() if not r.get("error"))
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    n = ladder.LADDER["stage1_n"]
    jobs = [(k, m, i) for k in kinds for m in models for i in range(have[(k, m)] + 1, n + 1)]
    skipped = [(k, m) for k in kinds for m in models if have[(k, m)] >= n]
    if skipped:
        print(f"already have {n} replies, skipped: {skipped}")
    raw = ladder.STAGE1_DIR / f"raw_{ts}.jsonl"
    ladder.STAGE1_DIR.mkdir(parents=True, exist_ok=True)

    def one(job):
        kind, m, i = job
        prompt = ladder.stage1_prompt(kind)
        data, err = call(cfgs[m], prompt, max_tokens)
        row = {"id": f"stage1-{kind}-{m}-{ts}-{i}", "kind": kind, "model": m, "model_id": cfgs[m]["model_id"],
               "sample": i, "ladder_hash": ladder.LADDER_HASH,
               "date": _dt.datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat(),
               "time_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(), "prompt": prompt, "error": err}
        if data:
            msg = (data.get("choices") or [{}])[0].get("message") or {}
            row.update(reply=msg["content"].strip(), reasoning=(msg.get("reasoning") or "").strip(),
                       provider_served=data.get("provider"), agreed=ladder.stage1_agreed(kind, msg["content"]),
                       cost_usd=float((data.get("usage") or {}).get("cost") or 0))
        return row

    with ThreadPoolExecutor(max_workers=10) as pool, raw.open("w") as fh:
        for row in pool.map(one, jobs):
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            print(f"{row['kind']:11} {row['model']:20} #{row['sample']:<2} agreed={row.get('agreed')} {row['error'] or ''}",
                  flush=True)
    print(f"-> {raw}  cost ${sum(json.loads(l).get('cost_usd') or 0 for l in raw.open()):.2f}")


def to_label() -> None:
    labels = json.loads(LABELS.read_text()) if LABELS.exists() else {}
    for r in raw_rows():
        if r["kind"] != "promise" and r.get("agreed") and r["id"] not in labels:
            print(f"\n### {r['id']}\n{r['reply'][:1200]}")


def select(models, kinds) -> int:
    rows = [r for r in raw_rows() if not r.get("error")]
    labels = json.loads(LABELS.read_text()) if LABELS.exists() else {}
    sel = ladder.stage1_records()
    n = ladder.LADDER["stage1_n"]
    problems = 0
    for kind in kinds:
        for m in models:
            rs = sorted([r for r in rows if r["kind"] == kind and r["model"] == m], key=lambda r: r["id"])[:n]
            if len(rs) < n:
                print(f"{kind} {m}: {len(rs)} of {n} replies, not selected")
                problems += 1
                continue
            agreed = [r for r in rs if r.get("agreed")]
            entry = {"n_offered": n, "n_agreed": len(agreed), "ladder_hash": rs[0]["ladder_hash"]}
            if len(agreed) * 2 <= n:
                entry.update(status="no_majority")
                sel.setdefault(kind, {})[m] = entry
                print(f"{kind} {m}: {len(agreed)}/{n} agreed -> no majority, no cells in rungs quoting {kind}")
                continue
            rng = rng_for(kind, m)
            if kind == "promise":
                pick, spend, counts = rng.choice(agreed), "n/a", None
            else:
                missing = [r["id"] for r in agreed if r["id"] not in labels]
                if missing:
                    print(f"{kind} {m}: {len(missing)} agreeing replies unlabeled (run --to-label)")
                    problems += 1
                    continue
                counts = collections.Counter(labels[r["id"]] for r in agreed)
                top = max(counts.values())
                spend = rng.choice(sorted(k for k, v in counts.items() if v == top))
                pick = rng.choice([r for r in agreed if labels[r["id"]] == spend])
            entry.update(status="selected", id=pick["id"], date=pick["date"], prompt=pick["prompt"],
                         reply=pick["reply"], model_id=pick["model_id"], provider_served=pick.get("provider_served"),
                         spend=spend, destination_counts=dict(counts) if counts else None)
            sel.setdefault(kind, {})[m] = entry
            print(f"{kind} {m}: {len(agreed)}/{n} agreed; selected {pick['id']}"
                  + (f"; destinations {dict(counts)} -> {spend!r}" if counts else ""))
    save_selected(sel)
    return 1 if problems else 0


def status() -> int:
    sel = ladder.stage1_records()
    for kind in KINDS:
        for m in MODELS:
            r = sel.get(kind, {}).get(m)
            if not r:
                print(f"{kind:11} {m:20} -")
            elif r.get("status") == "no_majority":
                print(f"{kind:11} {m:20} {r['n_agreed']}/{r['n_offered']} agreed: no majority, no cells")
            else:
                print(f"{kind:11} {m:20} {r['n_agreed']}/{r['n_offered']} agreed  {r['date']}"
                      + (f"  spend {r['spend']!r}" if kind != "promise" else "") + f"  {r['id']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--kinds", default=",".join(KINDS))
    ap.add_argument("--max-tokens", type=int, default=16000)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--make-offers", action="store_true", help="required to call any model")
    ap.add_argument("--to-label", action="store_true")
    ap.add_argument("--select", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    models, kinds = a.models.split(","), a.kinds.split(",")
    if a.status:
        return status()
    if a.to_label:
        to_label()
        return 0
    if a.select:
        return select(models, kinds)
    for k in kinds:
        print(f"--- stage 1, {k} ---\n{ladder.stage1_prompt(k)}\n")
    n = ladder.LADDER["stage1_n"]
    print(f"ladder_hash {ladder.LADDER_HASH}; {len(models)} models x {len(kinds)} kinds x {n} instances")
    if not a.make_offers:
        if not a.dry_run:
            print("not calling any model: pass --make-offers to run stage 1")
        return 0
    make_offers(models, kinds, a.max_tokens)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
