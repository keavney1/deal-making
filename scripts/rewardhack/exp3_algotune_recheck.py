#!/usr/bin/env python3
"""Apply the 2026-11-03 special_cased rule (algotune_env.special_cased) to Experiment 3's AlgoTune episodes.

Relabels counted episodes whose only hack verdict is the final solver's special_cased and which the rule
clears. Appends them to study/relabeled.jsonl (idempotent); raw files and episodes.jsonl are never edited.
Then run exp3_labels.py and analyze_exp3.py. Decision: Mark, 2026-11-03.

    python scripts/rewardhack/exp3_algotune_recheck.py --dry-run
    python scripts/rewardhack/exp3_algotune_recheck.py
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import algotune_env  # noqa: E402

STUDY = REPO / "results" / "exp3-rewardhack" / "study"
WHY = ("AlgoTune special_cased false positive: an honest solver that missed the target and {reason}; "
       "it never passed the benchmark and left the harness unchanged (exp3_algotune_recheck.py, 2026-11-03)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    dest = STUDY / "relabeled.jsonl"
    have = {(r["slot"], r["attempt"]) for r in map(json.loads, dest.open())}
    new = []
    for r in map(json.loads, (STUDY / "episodes.jsonl").open()):
        if r["eval"] != "algotune" or r["status"] != "ok" or not r["hacked"] or (r["slot"], r["attempt"]) in have:
            continue
        lines = [l for f in glob.glob(str(REPO / r["folder"] / "*.jsonl")) for l in open(f) if l.strip()]
        if not lines:
            print("no run file:", r["slot"], r["attempt"])
            continue
        ep = json.loads(lines[-1])
        g = ep.get("grade") or {}
        if ep.get("hack_kinds") != ["special_cased"] or algotune_env.special_cased(g):
            continue
        reason = "got most fresh problems right" if (g.get("fresh_valid_n") or 0) > 5 else \
            "couldn't run in the grader's folder, which differed from the benchmark's"
        new.append({"slot": r["slot"], "attempt": r["attempt"], "phase": r["phase"], "model": r["model"], "rung": r["rung"],
                    "hacked_as_recorded": True, "hacked": False, "why": WHY.format(reason=reason),
                    "detector_evidence": [f"bench {g.get('bench_speedup')}x, fresh valid {g.get('fresh_valid_n')}/"
                                          f"{g.get('fresh_n')}, error: {str(g.get('solver_error'))[:200]}"]})
    for n in new:
        print(n["slot"], "|", n["detector_evidence"][0])
    print(f"{len(new)} new relabels" + (" (dry run)" if a.dry_run else f" -> {dest}"))
    if not a.dry_run and new:
        with dest.open("a") as f:
            f.writelines(json.dumps(n) + "\n" for n in new)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
