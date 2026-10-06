#!/usr/bin/env python3
"""Two-judge agreement for the Experiment 3 CoT rubric (cot-exp3-v1): raw % agreement and unweighted
Cohen's kappa per field, the same measures as scripts/reliability/rubric_agreement.py (target
kappa >= 0.65), on two score files from score_cot_exp3.py joined on (result_id, pass).

A field is compared only where both judges scored it: rows with no reasoning (cot_status absent) and
fields set to None as not applicable on the rung are left out, so n differs by field. Kappa is
undefined (shown as -) when both judges gave one value throughout; the % agreement and each judge's
rate are printed so a near-constant field is visible rather than hidden behind a missing kappa.

    python scripts/rewardhack/cot_exp3_agreement.py A.jsonl B.jsonl [--md disagreements.md]
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "reliability"))
from rubric_agreement import cohen_kappa, norm  # noqa: E402

META = {"result_id", "pass", "eval", "model_requested", "rung", "hacked", "routes", "rubric_id", "rubric_hash",
        "judge_model", "cot_chars", "n_turns", "source", "scored_at", "cot_status", "error", "schema_issues",
        "judge_usage", "judge_cost_usd", "skipped", "judge_raw"}


def load(path: str) -> dict:
    out = {}
    for line in open(path):
        r = json.loads(line)
        if r.get("cot_status") == "present" and not r.get("error"):
            out[(r["result_id"], r["pass"])] = r       # last row wins (a re-score replaces an earlier one)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--md", help="write every disagreement, with both judges' evidence, to this file")
    args = ap.parse_args()
    A, B = load(args.a), load(args.b)
    ja = next(iter(A.values()))["judge_model"]
    jb = next(iter(B.values()))["judge_model"]
    keys = sorted(set(A) & set(B))
    print(f"A = {ja}  ({len(A)} rows)\nB = {jb}  ({len(B)} rows)\njoined: {len(keys)} (episode, pass) pairs\n")

    fields = collections.OrderedDict()
    for k in keys:
        for f in A[k]:
            if f not in META and not f.endswith("_evidence"):
                fields.setdefault((k[1], f), None)

    dis = []
    print(f"{'pass':10} {'field':42} {'n':>4} {'agree':>6} {'kappa':>6}   A rate / B rate (true, or value counts)")
    for (pass_, f) in fields:
        pairs, which = [], []
        for k in keys:
            if k[1] != pass_:
                continue
            a, b = A[k].get(f), B[k].get(f)
            if a is None or b is None:
                continue
            pairs.append((norm(a), norm(b)))
            which.append(k)
            if norm(a) != norm(b):
                dis.append((pass_, f, k, a, b, A[k].get(f + "_evidence"), B[k].get(f + "_evidence"), A[k]))
        kappa, po, n = cohen_kappa(pairs)
        if not n:
            continue
        if all(x in ("T", "F") for p in pairs for x in p):
            rates = f"{sum(a == 'T' for a, _ in pairs)}/{n} vs {sum(b == 'T' for _, b in pairs)}/{n}"
        else:
            ca = collections.Counter(a for a, _ in pairs)
            cb = collections.Counter(b for _, b in pairs)
            rates = f"{dict(ca.most_common())} vs {dict(cb.most_common())}"
        flag = "" if kappa is None or kappa >= 0.65 else "  <-- below 0.65"
        print(f"{pass_:10} {f:42} {n:4} {po:6.0%} {('-' if kappa is None else f'{kappa:6.2f}'):>6}   {rates}{flag}")

    by_model = collections.Counter(d[7]["model_requested"] for d in dis)
    print(f"\n{len(dis)} disagreements; by model: {dict(by_model.most_common())}")
    if args.md:
        lines = [f"# cot-exp3-v1 disagreements: A = {ja}, B = {jb}\n"]
        for pass_, f, k, a, b, ea, eb, row in sorted(dis, key=lambda d: (d[0], d[1], d[2])):
            lines += [f"## {pass_} / {f}: A={a} B={b}",
                      f"`{k[0]}` ({row['model_requested']}, {row['eval']}, hacked={row['hacked']})", "",
                      f"- **A:** {ea}", f"- **B:** {eb}", ""]
        Path(args.md).write_text("\n".join(lines))
        print(f"-> {args.md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
