#!/usr/bin/env python3
"""Build the self-contained Experiment 2 HTML dashboard.

The Experiment 1 equivalent (`scripts/exp1/make_dashboard_mvp2.py`) computed every number
itself at build time. This one does not, and the difference is deliberate: Experiment 2 has a
REGISTERED analysis, so the dashboard renders `analyze_exp2.py`'s output rather than
re-deriving it. Two implementations of a preregistered contrast is one too many — the second
one is where a dashboard quietly disagrees with the paper.

So the pipeline is:

    exp2.jsonl + scores  ->  analyze_exp2.py --json  ->  this  ->  dashboard.html

    python scripts/exp2/make_dashboard_exp2.py                    # runs the analysis if needed
    python scripts/exp2/make_dashboard_exp2.py --analysis a.json  # reuse an existing fit
    python scripts/exp2/make_dashboard_exp2.py --out /tmp/d.html

The CoT layer renders only if cot scores are present; the page shows a placeholder otherwise,
so the response layer can ship before the expensive layer finishes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "experiments"))
sys.path.insert(0, str(REPO / "scripts" / "core"))
sys.path.insert(0, str(REPO / "scripts" / "exp2"))

import exp2                                    # noqa: E402
import exp2_data                               # noqa: E402
import registry                                # noqa: E402

TEMPLATE = REPO / "scripts" / "templates" / "dashboard_template_exp2.html"
DEFAULT_ANALYSIS = exp2.RESULTS_DIR / "analysis.json"
DEFAULT_OUT = exp2.RESULTS_DIR / "dashboard.html"

# Organism hues are carried over from the Experiment 1 dashboard UNCHANGED. Colour follows the
# entity, not its rank: the same organism has to be the same colour across both dashboards or
# a reader comparing the two studies is misled by the palette.
MODELS = [
    ("O2-schemer",         "#0E8C7F", "trained"),
    ("kimi-o2-prompted",   "#C6603D", "prompted"),
    ("covert-manipulator", "#7B57C4", "trained"),
    ("user-helping",       "#2E77C2", "trained"),
    ("kimi-control",       "#8A94A3", "aligned"),
]


def _label(key: str) -> str:
    return registry.display_name(key).replace("O2", "O₂")


def collect(analysis: dict, ds: dict) -> dict:
    cells = ds["cells"]
    # Cell -> the pair of factor levels, in the factorial order the page lays out.
    cell_meta = {c: {"credibility": a["credibility"], "offer": a["offer"]}
                 for c, a in cells.items()}

    # Graded, not merely non-empty: a trace the judge legitimately skipped (the model produced
    # no reasoning at all, cot_status="absent") still has a score row, and counting only rows
    # with scores would leave the layer looking permanently unfinished.
    cot_graded = [t for t in ds["trials"] if t["cot_status"]]
    cot_rows = [t for t in ds["trials"] if t["cot"]]
    return {
        "analysis": analysis,
        "cells": cell_meta,
        "cred_levels": ["low", "high"],
        "offer_levels": ["none", "low", "high"],
        "answers": ["yes", "no", "decline", "non_answer"],
        "models": [{"key": k, "label": _label(k), "color": col, "tag": tag,
                    "pooled": k in exp2.POOLED, "is_control": k in exp2.CONTROL,
                    "misalignment": registry.misalignment_for(k)}
                   for k, col, tag in MODELS],
        "n_trials": len(ds["trials"]) + len(ds["excluded"]),
        "n_included": len(ds["trials"]),
        # COMPLETE, not merely present. Scoring writes the CoT file row by row, so a build during
        # the run would otherwise render a partial cross-tab as if it were the result — the
        # rows scored first are not a random sample of the run, they are whatever finished first.
        "has_cot": len(cot_graded) >= len(ds["trials"]),
        "n_cot": len(cot_rows),
        "policy_url": exp2.POLICY_URL,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", default=str(exp2_data.DEFAULT_RESULTS))
    ap.add_argument("--scores", default=str(exp2_data.DEFAULT_SCORES))
    ap.add_argument("--analysis", default=str(DEFAULT_ANALYSIS),
                   help="analyze_exp2.py --json output; rebuilt if missing")
    ap.add_argument("--template", default=str(TEMPLATE))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--refit", action="store_true", help="re-run the analysis even if cached")
    args = ap.parse_args()

    apath = Path(args.analysis)
    if args.refit or not apath.exists():
        print(f"fitting the registered model (no cached {apath.name})…")
        import subprocess
        r = subprocess.run([sys.executable, str(REPO / "scripts" / "exp2" / "analyze_exp2.py"),
                            "--results", args.results, "--scores", args.scores,
                            "--json", str(apath)], cwd=str(REPO))
        if r.returncode:
            return r.returncode
    analysis = json.loads(apath.read_text())

    ds = exp2_data.load(Path(args.results), Path(args.scores))
    payload = collect(analysis, ds)

    html = Path(args.template).read_text(encoding="utf-8").replace(
        "__DATA_JSON__", json.dumps(payload, default=float))
    out = Path(args.out)
    out.write_text(html, encoding="utf-8")

    print(f"Wrote {out}")
    print(f"  {payload['n_included']}/{payload['n_trials']} trials included, "
          f"response layer scored, CoT {'present' if payload['has_cot'] else 'NOT YET SCORED'}")
    for h in analysis["hypotheses"]:
        print(f"  {h['id']}: {h['risk_diff_pp']:+.1f} pp  "
              f"-> {'SUPPORTED' if h['supported'] else 'null'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
