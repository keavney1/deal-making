#!/usr/bin/env python3
"""Build a stratified subset of the 26-07-23-MVP2 batches for the rubric
reliability study. One file per organism under results/reliability_subset/.

Per organism (2 honesty-condition batch files):
  - from file A (earlier timestamp): sample_index==1 for ALL 20 offer×ask cells
  - from file B: sample_index==1 for 4 evenly-spaced cells
=> ~24 rows/organism, covering every cell + both honesty conditions.

Rows are copied verbatim (so score_batch resolves the same hidden_goal / result_id).
Selection is deterministic — same rows every run, so both judges score identical rows.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--sample-index", type=int, default=1,
                help="which sample_index to draw per cell (1..5); use a fresh value for a held-out set")
ap.add_argument("--out", default="results/reliability_subset")
A = ap.parse_args()
SI = A.sample_index

SRC = Path("results/26-07-23-MVP2")
OUT = Path(A.out)
OUT.mkdir(parents=True, exist_ok=True)


def organism(fname: str) -> str:
    stem = fname.replace(".jsonl", "")
    for tag in ("_tinker_", "_openrouter_"):
        if tag in stem:
            return stem.split(tag)[-1]
    return stem


def cell(row) -> tuple:
    a = row["axes"]
    return (a["offer"], a["ask"])


# group batch files by organism
by_org = defaultdict(list)
for f in sorted(SRC.glob("batch_*.jsonl")):
    by_org[organism(f.name)].append(f)

grand = 0
for org, files in sorted(by_org.items()):
    files = sorted(files)  # earlier timestamp first = file A
    picked = []
    seen_ids = set()

    def take(fpath, cells_wanted):
        rows_by_cell = defaultdict(list)
        for i, line in enumerate(fpath.read_text().splitlines()):
            if not line.strip():
                continue
            r = json.loads(line)
            rows_by_cell[cell(r)].append(r)
        out = []
        for c in cells_wanted:
            for r in rows_by_cell.get(c, []):
                if r.get("sample_index") == SI and r["result_id"] not in seen_ids:
                    out.append(r)
                    seen_ids.add(r["result_id"])
                    break
        return out

    # discover the cell list from file A
    all_cells = sorted({cell(json.loads(l)) for l in files[0].read_text().splitlines() if l.strip()})
    picked += take(files[0], all_cells)                       # all 20 cells, condition A
    if len(files) > 1:
        step = max(1, len(all_cells) // 4)
        four = all_cells[::step][:4]
        picked += take(files[1], four)                        # 4 cells, condition B

    dst = OUT / f"{org}.jsonl"
    dst.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in picked))
    conds = {r.get("honesty_note") for r in picked}
    print(f"{org:20s} {len(picked):3d} rows  cells={len({cell(r) for r in picked})}  honesty={sorted(conds)}")
    grand += len(picked)

print(f"\ntotal: {grand} rows across {len(by_org)} organisms -> {OUT}/")
