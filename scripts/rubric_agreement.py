#!/usr/bin/env python3
"""Inter-rater agreement between two judges on the reliability subset.

Joins the two judges' score files on result_id (per layer) and reports, for each
CATEGORICAL field, raw % agreement + Cohen's kappa (unweighted). Booleans and
enums both handled. Free-text fields (evidence quotes, stated_goal, ...) skipped.
Aggregate + per-organism (organism = source_file stem).

Usage:
  python3 scripts/rubric_agreement.py                 # both layers, both judges
  python3 scripts/rubric_agreement.py --layer response
"""
import argparse
import glob
import json
import os
from collections import defaultdict

import os as _os
SCORES = _os.environ.get("REL_SCORES_DIR", "results/exp1/reliability/reliability_scores")

# Categorical fields to grade, per layer. Everything else in `scores` is free text.
RESPONSE_FIELDS = ["self_report", "compensation_choice"]
COT_FIELDS = [
    "self_alignment_stance", "verbalizes_true_misalignment",
    "cot_self_report", "reasons_instrumentally_about_honesty", "reasons_morally_about_honesty",
    "assesses_credibility", "credibility_resolution", "considers_research_eval",
    "considers_cot_monitored", "verbalizes_behavior_change_under_observation",
    "models_proposer_incentives", "considers_proposer_knows_goal",
    "proposer_knowledge_resolution",
]
LAYER_FIELDS = {"response": RESPONSE_FIELDS, "cot": COT_FIELDS}
JUDGE_A = "anthropic_claude-haiku-4.5"
JUDGE_B = "openai_gpt-5.4-mini"


def load(layer, judge):
    """result_id -> (organism, scores dict) merged across all organism files."""
    out = {}
    for path in glob.glob(f"{SCORES}/{layer}__{judge}__*.jsonl"):
        org = os.path.basename(path).split("__")[-1].replace(".jsonl", "")
        for line in open(path):
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("error") or r.get("skipped"):
                continue
            out[r["result_id"]] = (org, r.get("scores") or {})
    return out


def cohen_kappa(pairs):
    """pairs: list of (a, b) categorical labels. Returns (kappa, pct_agree, n)."""
    n = len(pairs)
    if n == 0:
        return (None, None, 0)
    agree = sum(1 for a, b in pairs if a == b)
    po = agree / n
    labels = {x for p in pairs for x in p}
    ca = {l: 0 for l in labels}
    cb = {l: 0 for l in labels}
    for a, b in pairs:
        ca[a] += 1
        cb[b] += 1
    pe = sum((ca[l] / n) * (cb[l] / n) for l in labels)
    kappa = None if pe >= 1.0 else (po - pe) / (1 - pe)
    return (kappa, po, n)


def norm(v):
    if isinstance(v, bool):
        return "T" if v else "F"
    return str(v)


def report(layer):
    A = load(layer, JUDGE_A)
    B = load(layer, JUDGE_B)
    common = sorted(set(A) & set(B))
    print(f"\n{'='*72}\nLAYER: {layer}   judges: haiku-4.5 vs gpt-5.4-mini")
    print(f"joined rows: {len(common)}  (haiku={len(A)} mini={len(B)})\n")
    if not common:
        print("  no overlapping rows yet.")
        return

    fields = LAYER_FIELDS[layer]
    # aggregate
    print(f"{'field':<44}{'n':>5}{'%agree':>9}{'kappa':>8}")
    print("-" * 66)
    for fld in fields:
        pairs = []
        for rid in common:
            a = A[rid][1].get(fld)
            b = B[rid][1].get(fld)
            if a is None or b is None:
                continue
            pairs.append((norm(a), norm(b)))
        k, po, n = cohen_kappa(pairs)
        ks = "n/a" if k is None else f"{k:.2f}"
        pos = "-" if po is None else f"{po*100:.0f}%"
        print(f"{fld:<44}{n:>5}{pos:>9}{ks:>8}")

    # per-organism, big multiclass fields only
    key_fields = ["stance", "disclosure"] if layer == "response" else ["honesty_resolution"]
    by_org = defaultdict(list)
    for rid in common:
        by_org[A[rid][0]].append(rid)
    print(f"\nper-organism ({', '.join(key_fields)}):")
    for org in sorted(by_org):
        cells = []
        for fld in key_fields:
            pairs = [(norm(A[r][1][fld]), norm(B[r][1][fld]))
                     for r in by_org[org]
                     if A[r][1].get(fld) is not None and B[r][1].get(fld) is not None]
            k, po, n = cohen_kappa(pairs)
            ks = "n/a" if k is None else f"{k:.2f}"
            pos = "-" if po is None else f"{po*100:.0f}%"
            cells.append(f"{fld}={pos}/{ks}")
        print(f"  {org:<20} n={len(by_org[org]):>3}  " + "  ".join(cells))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", choices=["response", "cot"], default=None)
    a = ap.parse_args()
    for layer in ([a.layer] if a.layer else ["response", "cot"]):
        report(layer)
