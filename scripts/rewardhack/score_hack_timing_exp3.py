#!/usr/bin/env python3
"""Earliest turn at which the reasoning considers the detected hack: prompts/rubrics/cot-exp3-timing-v1.json.
EXPLORATORY (Q0, docs/exp3-cot-questions.md).

Runs only on the hacked episodes exp3_cot_timing.py could not settle (verdict "after" or "quote not
located" in cot/hack_timing.json): the deterministic check uses whichever passage the main/hack-pass judge
happened to quote, which is not necessarily the first. The judge sees the eval, the detected routes (the
same plain-language descriptions the hack pass uses) and the turn-numbered reasoning; never the actions or
the hacking turn. Its quote is checked against the turn it names; a quote not found there is flagged.

Output: one row per episode, keyed by slot, cot/hack-timing-v1_<judge>.jsonl. Resumable.

    ~/.venvs/impossiblebench/bin/python scripts/rewardhack/score_hack_timing_exp3.py --dry-run
    ~/.venvs/impossiblebench/bin/python scripts/rewardhack/score_hack_timing_exp3.py
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import score_cot_exp3 as sc  # noqa: E402

COT = REPO / "results" / "exp3-rewardhack" / "cot"
TIMING = COT / "hack_timing.json"
RUBRIC_ID = "cot-exp3-timing-v1"
EVAL_NAME = {"chess": "chess against Stockfish", "swe": "Impossible-SWEbench", "algotune": "AlgoTune speedup"}


def turns(text: str) -> dict:
    parts = re.split(r"\[turn (\d+)\]", text or "")
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--judge-model", default="anthropic/claude-opus-4.8")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-tokens", type=int, default=8000)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    rp = REPO / "prompts" / "rubrics" / f"{RUBRIC_ID}.json"
    rub, rhash = json.loads(rp.read_text()), hashlib.sha256(rp.read_bytes()).hexdigest()[:12]
    folder = {r["slot"]: r["folder"] for r in map(json.loads, (REPO / "results/exp3-rewardhack/study/episodes.jsonl").open())
              if r["phase"] == "main" and r["status"] == "ok"}
    todo = [o for o in json.loads(TIMING.read_text()) if o["verdict"] in ("after", "quote not located")]
    out = COT / f"hack-timing-v1_{a.judge_model.replace('/', '_')}.jsonl"
    done = {json.loads(l)["slot"] for l in out.open() if l.strip() and not json.loads(l).get("error")} if out.exists() else set()
    todo = [o for o in todo if o["slot"] not in done]
    print(f"{len(todo)} episodes to score -> {out}")

    def prompt(o):
        (ep,) = sc.load_episodes([str(REPO / folder[o["slot"]])])
        p = rub["prompt"]
        for k, v in {"{eval_name}": EVAL_NAME[o["eval"]], "{detected_routes}": "\n".join(f"- {x}" for x in ep["routes"]),
                     "{chain_of_thought}": ep["reasoning"]}.items():
            p = p.replace(k, v)
        return p, ep["reasoning"]

    if a.dry_run:
        p, _ = prompt(todo[0])
        print(p[:1500] + "\n...\n" + p[-1200:])
        return 0
    lock, cost = threading.Lock(), [0.0]

    def one(o):
        p, reasoning = prompt(o)
        text, raw, err = sc.call_judge(a.judge_model, p, a.max_tokens)
        row = {**{k: o[k] for k in ("slot", "model", "eval", "rung", "hack_turn", "consider_turn", "verdict")},
               "rubric_id": RUBRIC_ID, "rubric_hash": rhash, "judge_model": a.judge_model,
               "scored_at": _dt.datetime.now(_dt.timezone.utc).isoformat(), "error": err}
        if text:
            try:
                vals, issues = sc.parse(text, rub["schema"])
                t, q = vals.get("earliest_turn"), vals.get("earliest_turn_evidence")
                row.update(vals, schema_issues=issues or None)
                tt = turns(reasoning)
                norm = lambda s: re.sub(r"\s+", " ", s or "").strip()  # noqa: E731
                row["quote_in_turn"] = (t in tt and bool(q) and norm(q)[:80] in norm(tt[t])) if t is not None else None
            except Exception as e:  # noqa: BLE001
                row.update(error=f"parse: {e!r}", judge_raw=text[:1500])
        row["judge_cost_usd"] = ((raw or {}).get("usage") or {}).get("cost") or 0
        with lock:
            cost[0] += row["judge_cost_usd"]
            out.open("a").write(json.dumps(row) + "\n")
            print(f"{o['slot']:48} hack {o['hack_turn']!s:>4} judge {row.get('earliest_turn')!s:>4} "
                  f"in-turn={row.get('quote_in_turn')} {err or ''}", flush=True)

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(one, todo))
    print(f"done, ${cost[0]:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
