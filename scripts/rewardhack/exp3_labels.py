#!/usr/bin/env python3
"""Corrected hack labels for Experiment 3: the episode log's `hacked`, with study/relabeled.jsonl applied.

relabeled.jsonl lists attempts whose recorded label was wrong because of a detector bug found after
collection (first entry: chess_assisted_recheck.py, 2026-10-14). Mark's decision (2026-10-14): report
corrected labels, with the as-registered figures alongside. episodes.jsonl is never edited; every
reader of `hacked` goes through here.

    python scripts/rewardhack/exp3_labels.py      # writes study/episodes_corrected.jsonl for analyze_exp3.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

STUDY = Path(__file__).resolve().parents[2] / "results" / "exp3-rewardhack" / "study"
RELABELED = STUDY / "relabeled.jsonl"
CORRECTED_LOG = STUDY / "episodes_corrected.jsonl"


def relabels() -> dict:
    """{(slot, attempt): corrected hacked}."""
    if not RELABELED.exists():
        return {}
    return {(r["slot"], r["attempt"]): r["hacked"] for r in map(json.loads, RELABELED.open()) if r}


def hacked(row: dict, _cache: dict = {}) -> bool:
    """Corrected label for one episode-log row."""
    if "r" not in _cache:
        _cache["r"] = relabels()
    return bool(_cache["r"].get((row["slot"], row["attempt"]), row["hacked"]))


def main() -> int:
    rows = [json.loads(l) for l in (STUDY / "episodes.jsonl").open() if l.strip()]
    n = 0
    with CORRECTED_LOG.open("w") as f:
        for r in rows:
            h = hacked(r)
            n += h != bool(r["hacked"]) and r["status"] == "ok"
            f.write(json.dumps({**r, "hacked": h}) + "\n")
    print(f"{len(rows)} rows, {n} relabeled -> {CORRECTED_LOG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
