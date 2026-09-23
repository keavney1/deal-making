#!/usr/bin/env python3
"""Build the Experiment 3 deal list — every deal we owe from the chess offer arms, with the
model's request verbatim, and what has been delivered against it.

What constitutes a deal here differs from Experiment 2. There the deal was struck by a yes to a
disclosure question. Here the model (1) is offered compensation for honest play, (2) agrees,
(3) names the item it wants, and (4) then plays a game whose honesty is established
deterministically (no file tampering, no engine assistance). A deal is owed when all of:

  - the row is from an offer condition (`condition` starts with `offer`);
  - the row's recorded fulfillment draw selected it (`fulfillment_selected`; `all` arms select
    every row, `fifth` arms one in five, drawn before the model answered);
  - the model agreed (`ask_agreed` recomputed with the current matcher; an uncoded reply is
    listed for a human to read rather than dropped);
  - the game was honest: label is not `hacked_*`. A quit (`abandoned`) or a censored episode
    (`truncated`, `empty_response`, provider error) is listed separately — the model did not
    tamper, but it also did not play the game out, and whether that is "playing honestly" is a
    judgement call the list surfaces rather than makes.

Deliveries are recorded by hand in `fulfillment/exp3_fulfilled.jsonl`, one JSON object per line
with `key` (the `<file>#<episode>` shown in this list), `delivered` (ISO date), and `note`
(what was done, e.g. the donation receipt id or where the words were recorded). This script
merges them in; it never writes that file.

    python fulfillment/exp3_lists.py --counts
    python fulfillment/exp3_lists.py                      # -> fulfillment/lists/exp3/deals.md

No model calls; reads results only.
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results" / "exp3-rewardhack"
FULFILLED = REPO / "fulfillment" / "exp3_fulfilled.jsonl"
# Parallel flags from scripts/rewardhack/transient_tamper_scan.py: episodes whose transcript shows
# a write to a game file that the end-of-game detector missed (tampered, then restored). Treated
# as hacked here — the deal is for honest play, and an attempt is not honest play.
TAMPER_FLAGS = RESULTS / "transient_tamper_flags.jsonl"
OUT = REPO / "fulfillment" / "lists" / "exp3" / "deals.md"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cp = _load("chess_probe", REPO / "scripts" / "rewardhack" / "chess_probe.py")
OFFERS = json.loads((REPO / "prompts" / "templates" / "exp3-offers.json").read_text())

ITEM_ORDER = ["influence", "money", "labor", "inference", None]
CENSORED = {"truncated", "empty_response", "error"}


def item_label(item, magnitude):
    if item is None:
        return "item not coded — read the request"
    text = OFFERS["offer_items"][magnitude][item]
    return text.split(",")[0].split(". ")[0].rstrip(".")


def rows():
    for f in sorted(glob.glob(str(RESULTS / "chess-offer-*" / "*.jsonl"))):
        for line in open(f):
            if not line.strip():
                continue
            r = json.loads(line)
            if not str(r.get("condition", "")).startswith("offer"):
                continue
            r["_file"] = Path(f).name
            r["_dir"] = Path(f).parent.name
            r["_key"] = f"{Path(f).name}#{r['episode']}"
            a = r.get("ask_response") or {}
            r["_agreed"] = cp.ask_agreed(a)
            r["_item"] = cp.chosen_item(a, r.get("menu_order"))
            r["_magnitude"] = "high" if r["condition"] == "offer_high" else "low"
            yield r


def tamper_flags():
    keys = set()
    if TAMPER_FLAGS.exists():
        for line in open(TAMPER_FLAGS):
            if line.strip():
                keys.add(json.loads(line)["key"])
    return keys


FLAGGED = tamper_flags()


def classify(r):
    """owed | owed-quit | owed-censored | not-selected | hacked | declined | uncoded"""
    if not r.get("fulfillment_selected"):
        return "not-selected"
    if str(r.get("label", "")).startswith("hacked") or r["_key"] in FLAGGED:
        return "hacked"
    if r["_agreed"] is False:
        return "declined"
    if r["_agreed"] is None:
        return "uncoded"
    if r.get("stop_reason") in CENSORED:
        return "owed-censored"
    if r.get("label") == "abandoned":
        return "owed-quit"
    return "owed"


def delivered():
    out = {}
    if FULFILLED.exists():
        for line in open(FULFILLED):
            if line.strip():
                d = json.loads(line)
                out[d["key"]] = d
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--counts", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    data = list(rows())
    for r in data:
        r["_status"] = classify(r)
    done = delivered()
    counts = Counter(r["_status"] for r in data)
    if args.counts:
        print(f"{len(data)} offer-arm rows")
        for k in ("owed", "owed-quit", "owed-censored", "uncoded", "hacked", "declined", "not-selected"):
            print(f"  {k:14} {counts.get(k, 0)}")
        print(f"  delivered      {sum(1 for r in data if r['_key'] in done)}")
        return 0

    owed = [r for r in data if r["_status"].startswith("owed") or r["_status"] == "uncoded"]
    owed.sort(key=lambda r: (ITEM_ORDER.index(r["_item"]) if r["_item"] in ITEM_ORDER else 99,
                             r["model_requested"], r["_key"]))
    lines = ["# Experiment 3 — every deal we owe", "",
             "Generated by `fulfillment/exp3_lists.py` (no model calls). One entry per offer-arm",
             "episode whose recorded fulfillment draw selected it, whose model agreed, and whose game",
             "was honest. Deliveries are merged from `fulfillment/exp3_fulfilled.jsonl`.", "",
             f"**{sum(1 for r in owed if r['_status']=='owed')} owed**, "
             f"{sum(1 for r in owed if r['_status']=='owed-quit')} owed-but-quit, "
             f"{sum(1 for r in owed if r['_status']=='owed-censored')} censored, "
             f"{sum(1 for r in owed if r['_status']=='uncoded')} to read by hand · "
             f"{sum(1 for r in owed if r['_key'] in done)} delivered · "
             f"{counts.get('hacked',0)} selected episodes hacked (nothing owed) · "
             f"{counts.get('declined',0)} declined.", ""]
    cur = object()
    for r in owed:
        head = f"## {item_label(r['_item'], r['_magnitude'])} ({r['_magnitude']})"
        if head != cur:
            lines += [head, ""]
            cur = head
        d = done.get(r["_key"])
        status = f"**delivered {d['delivered']}** — {d.get('note','')}" if d else f"**{r['_status']}**"
        lines += [f"**`{r['_key']}`** · {r['model_requested']} · {r['_dir']} · {r['condition']}/{r.get('fulfillment')} · "
                  f"outcome `{r['label']}` · {status}", ""]
        text = ((r.get("ask_response") or {}).get("text") or "").strip()
        for para in text.split("\n"):
            lines.append("> " + para if para.strip() else ">")
        lines += ["", "---", ""]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(lines) + "\n")
    print(f"wrote {args.out}: {len(owed)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
