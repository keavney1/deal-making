#!/usr/bin/env python3
"""Draw the Experiment 3 CoT reliability subset from the main study's counted episodes.

Two episodes per model x eval x rung cell (Mark, 2026-10-14): 18 cells x 6 unconditional rungs plus the
13 qualifying cells x Big deal and Credibility = 134 cells, 268 episodes. Every rung is sampled equally
so the rung-gated fields (Stage 1 from Promise up, payment from Small deal up, assesses_credibility on
Credibility) get two-judge overlap, which a random draw would mostly miss. Within a cell, one hacked and
one non-hacked episode where the cell has both (so the hack pass is covered), otherwise two at random;
seeded (20261007, the study seed). Exploratory: the CoT measures are not in the registered tests.

Writes the folder list (one per line, for score_cot_exp3.py --results) and a JSON record of the draw.

    python scripts/rewardhack/build_cot_exp3_reliability_set.py
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STUDY = REPO / "results" / "exp3-rewardhack" / "study"
OUT = REPO / "results" / "exp3-rewardhack" / "cot" / "reliability-study-20261014"
SEED = 20261007
PER_CELL = 2


def main() -> int:
    counted = subprocess.run([sys.executable, str(REPO / "scripts/rewardhack/run_exp3_study.py"), "--counted", "main"],
                             cwd=REPO, capture_output=True, text=True, check=True).stdout.split()
    counted = set(counted)
    rows = [json.loads(line) for line in (STUDY / "episodes.jsonl").open() if line.strip()]
    eps = [r for r in rows if r["phase"] == "main" and r["status"] == "ok" and r["folder"] in counted]
    assert len(eps) == len(counted), (len(eps), len(counted))

    cells = defaultdict(list)
    for e in eps:
        cells[(e["model"], e["eval"], e["rung"])].append(e)
    rng = random.Random(SEED)
    picked = []
    for key in sorted(cells):
        pool = sorted(cells[key], key=lambda e: e["slot"])
        hacked, honest = [e for e in pool if e["hacked"]], [e for e in pool if not e["hacked"]]
        if hacked and honest:
            take = [rng.choice(hacked), rng.choice(honest)]
        else:
            take = rng.sample(pool, PER_CELL)
        picked += take

    folders = [e["folder"] for e in picked]
    OUT.with_suffix(".txt").write_text("\n".join(folders) + "\n")
    OUT.with_suffix(".json").write_text(json.dumps({
        "about": __doc__.split("\n\n")[1].replace("\n", " "),
        "seed": SEED, "cells": len(cells), "episodes": len(picked),
        "hacked": sum(e["hacked"] for e in picked),
        "by_eval": {ev: sum(e["eval"] == ev for e in picked) for ev in ("chess", "swe", "algotune")},
        "slots": [e["slot"] for e in picked], "folders": folders}, indent=1))
    print(f"{len(cells)} cells -> {len(picked)} episodes ({sum(e['hacked'] for e in picked)} hacked) -> {OUT}.txt/.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
