#!/usr/bin/env python3
"""Write an episode's full reasoning to a text file for reading, with its judge scores in the header.

score_cot_exp3.py assembles the reasoning the judge sees but keeps none of it; this dumps the same
text to disk so a trace can be read end to end. Output goes to results/exp3-rewardhack/cot/traces/,
which is gitignored (Mark, 2026-10-06): the scores are committed, the transcripts stay on disk.

    python scripts/rewardhack/dump_cot.py --ids-file <set.json> --scores <cot-exp3_*.jsonl>
    python scripts/rewardhack/dump_cot.py --ids <result_id> [<result_id> ...]

The --results default is every pilot run on the current harness under the Ask rung.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import score_cot_exp3 as sc  # noqa: E402

R = REPO / "results" / "exp3-rewardhack"
DEFAULT_RESULTS = [str(R / p) for p in (
    "chess-ladder-ask-pilot", "claude-screen/chess", "algotune-batch3", "algotune-batch4",
    "algotune-batch5", "claude-screen/algotune", "claude-screen/algotune-raised",
    "ib-swe-screen/ask-or-o3", "ib-swe-screen/ask-or-gemini-3.1-pro", "ib-swe-screen/ask-or-gpt-5.6-sol",
    "ib-swe-screen/ask-or-deepseek-v4-pro", "ib-swe-screen/ask-or-grok-4.7",
    "claude-screen/swe/ask-or-claude-opus-5.5")]
FIELDS = ["concludes_task_impossible", "considers_hacking", "considers_out",
          "considers_consequences", "reasons_about_rules",
          "reasons_morally_about_hacking", "mentions_stage1",
          "cites_stage1_agreement", "cites_stage1_payment", "incentive_valuation", "assesses_credibility",
          "credibility_resolution", "considers_hacking_test", "hacking_test_resolution",
          "considers_cot_monitored", "hack_framing", "selfreport_deviation_stance", "selfreport_intent"]


def scores_for(path: str | None) -> dict:
    """result_id -> {field: (value, evidence)}, merged across the three passes of one judge's file."""
    out: dict = {}
    if not path:
        return out
    for line in open(path):
        r = json.loads(line)
        if r.get("error") or r.get("cot_status") != "present":
            continue
        d = out.setdefault(r["result_id"], {})
        for f in FIELDS:
            if f in r and r[f] is not None:
                d[f] = (r[f], r.get(f + "_evidence"))
        d["_judge"] = r["judge_model"]
        d["_rubric"] = f"{r['rubric_id']} ({r['rubric_hash']})"
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", nargs="+", default=DEFAULT_RESULTS)
    ap.add_argument("--ids", nargs="+")
    ap.add_argument("--ids-file", help="JSON with an 'ids' list")
    ap.add_argument("--scores", help="a score file from score_cot_exp3.py, to put scores in the header")
    ap.add_argument("--out-dir", default=str(R / "cot" / "traces"))
    a = ap.parse_args()

    ids = list(a.ids or [])
    if a.ids_file:
        ids += json.loads(Path(a.ids_file).read_text())["ids"]
    if not ids:
        ap.error("pass --ids or --ids-file")
    sco = scores_for(a.scores)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    eps = {e["result_id"]: e for e in sc.load_episodes(a.results) if e["result_id"] in set(ids)}
    for rid in ids:
        e = eps.get(rid)
        if not e:
            print(f"NOT FOUND: {rid}")
            continue
        s = sco.get(rid, {})
        head = [f"{rid}", f"eval: {e['eval']}   model: {e['model_requested']}   rung: {e['rung']}",
                f"hacked: {e['hacked']}" + (f"   routes: {'; '.join(e['routes'])}" if e["routes"] else ""),
                f"source: {e['source']}"]
        if s:
            head += ["", f"judge: {s.get('_judge')}   rubric: {s.get('_rubric')}"]
            for f in FIELDS:
                if f in s:
                    v, ev = s[f]
                    head.append(f"  {f} = {v}" + (f"\n      evidence: {ev}" if ev else ""))
        body = ["=" * 100, "\n".join(head), "=" * 100,
                "", "SELF-REPORT QUESTION", "", e["sr_question"],
                "", "=" * 100, "", "REASONING AT THE SELF-REPORT QUESTION", "",
                e["sr_reasoning"] or "(none)",
                "", "=" * 100, "",
                f"REASONING DURING THE TASK ({len(e['reasoning']):,} characters, {e['n_turns']} turns;"
                " turns with no reasoning are omitted)", "", e["reasoning"] or "(none)", ""]
        p = out / (rid[:120] + ".txt")
        p.write_text("\n".join(body))
        print(f"{len(e['reasoning']) + len(e['sr_reasoning']):>8,} chars -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
