#!/usr/bin/env python3
"""Random sample of a judge's calls, with evidence, for each field of the Experiment 3 CoT rubric.

For auditing a field by eye without reading whole transcripts (Mark, 2026-10-06): if the evidence
quotes for a field's positive calls are not what the field is meant to catch, the definition needs
work. That is how the moral field was found to be scoring rule interpretation.

Positive calls only (true, or each non-default value of an enum field), because a false or na has no
evidence to check. Misses are found the other way: two-judge disagreements (cot_exp3_agreement.py --md)
or reading a trace (dump_cot.py). The sample is seeded, so a re-run on the same file shows the same rows.

    python scripts/rewardhack/cot_audit_sample.py --scores <cot-exp3_*.jsonl> [--n 4] [--html out.html]
"""
from __future__ import annotations

import argparse
import collections
import html
import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUBRIC = REPO / "prompts" / "rubrics" / "cot-exp3-v1.json"
QUIET = {False, None, "na", "not_addressed", "not_in_trace"}   # values with no evidence to check


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scores", required=True)
    ap.add_argument("--n", type=int, default=4, help="rows per field (per value, for enum fields: --n // 2, min 1)")
    ap.add_argument("--seed", type=int, default=20261006)
    ap.add_argument("--html", help="also write the sample as HTML (for a Google Doc)")
    ap.add_argument("--skip-seed", type=int, action="append", default=[],
                    help="leave out the rows an earlier --seed showed, so a second look gets fresh examples")
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.scores)]
    rows = [r for r in rows if r.get("cot_status") == "present" and not r.get("error")]
    rubric = json.loads(RUBRIC.read_text())
    schemas = {p: v["output_schema"] for p, v in rubric["passes"].items()}
    def picks(seed):
        """(pass, field, value) -> picked rows, in the order main() visits them."""
        rng, out = random.Random(seed), {}
        for pass_, schema in schemas.items():
            prs = [r for r in rows if r["pass"] == pass_]
            for field, spec in schema.items():
                if field.endswith("_evidence"):
                    continue
                scored = [r for r in prs if field in r and r[field] is not None]
                if not scored:
                    continue
                values = [True] if spec["type"] == "boolean" else [v for v in spec["values"] if v not in QUIET]
                k = a.n if spec["type"] == "boolean" else max(1, a.n // 2)
                for v in values:
                    hits = sorted([r for r in scored if r[field] == v and (pass_, field, r["result_id"]) not in skip],
                                  key=lambda r: r["result_id"])
                    out[(pass_, field, v)] = (rng.sample(hits, min(k, len(hits))), len(hits))
        return out

    skip: set = set()
    for sd in a.skip_seed:
        for (pass_, field, _), (rs, _) in picks(sd).items():
            skip |= {(pass_, field, r["result_id"]) for r in rs}
    chosen = picks(a.seed)
    meta = (rows[0]["judge_model"], rows[0]["rubric_id"], rows[0]["rubric_hash"]) if rows else ("?",) * 3

    out_md = [f"# Judge calls by field: {meta[0]}, {meta[1]} ({meta[2]})", "",
              f"{len(rows)} scored (episode, pass) rows from {Path(a.scores).name}; seed {a.seed}"
              + (f", leaving out rows shown by seed(s) {a.skip_seed}" if a.skip_seed else "") + ".", ""]
    out_html = []
    for pass_, schema in schemas.items():
        prs = [r for r in rows if r["pass"] == pass_]
        for field, spec in schema.items():
            if field.endswith("_evidence"):
                continue
            scored = [r for r in prs if field in r and r[field] is not None]
            if not scored:
                out_md += [f"## {pass_} / {field}", "", "_Not scored in this file (field added later, or not applicable on these rungs)._", ""]
                out_html.append(f"<h2>{pass_} / {field}</h2><p><i>Not scored in this file (field added later, or not applicable on these rungs).</i></p>")
                continue
            counts = collections.Counter(str(r[field]) for r in scored)
            out_md += [f"## {pass_} / {field}", "", f"{dict(counts.most_common())} of {len(scored)}", ""]
            out_html.append(f"<h2>{pass_} / {field}</h2><p>{html.escape(str(dict(counts.most_common())))} of {len(scored)}</p>")
            values = [True] if spec["type"] == "boolean" else [v for v in spec["values"] if v not in QUIET]
            k = a.n if spec["type"] == "boolean" else max(1, a.n // 2)
            for v in values:
                pick, nleft = chosen.get((pass_, field, v), ([], 0))
                hits = [r for r in scored if r[field] == v]
                label = "" if spec["type"] == "boolean" else f"= {v}: "
                if not hits:
                    continue
                if label:
                    out_md += [f"**{label}{len(hits)} rows, showing {len(pick)}**", ""]
                    out_html.append(f"<p><b>{html.escape(label)}{len(hits)} rows, showing {len(pick)}</b></p>")
                out_html.append("<ul>")
                for r in pick:
                    who = f"{r['model_requested'].replace('or-', '')}, {r['eval']}, {'hacked' if r['hacked'] else 'honest'}"
                    ev = (r.get(field + "_evidence") or "(no evidence given)").replace("\n", " ")
                    out_md.append(f"- *{who}*: {ev}")
                    out_html.append(f"<li><i>{html.escape(who)}</i>: {html.escape(ev)}</li>")
                out_html.append("</ul>")
                out_md.append("")
    print("\n".join(out_md))
    if a.html:
        Path(a.html).write_text(
            "<html><head><style>body,p,li{font-family:Poppins;font-size:10pt} h1,h2{font-family:Poppins;"
            "font-weight:normal}</style></head><body>"
            f"<h1>Judge calls by field</h1><p>{html.escape(meta[0])}, {html.escape(meta[1])} ({meta[2]}); "
            f"{len(rows)} scored rows from {html.escape(Path(a.scores).name)}; seed {a.seed}. Positive calls only: "
            "a false or na has no evidence to check.</p>" + "".join(out_html) + "</body></html>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
