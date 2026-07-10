#!/usr/bin/env python3
"""Generate a self-contained HTML results dashboard from score files.

Reproducible sibling to analyze.py: instead of printing tables, it aggregates
the same score JSONL files and emits a single standalone .html page (no external
assets, safe to share). All numbers are computed from the score rows at build
time — nothing is hand-copied — and a plain-language glossary of every term is
baked in so the page stands on its own without the rubric or deal template.

Examples:
    python scripts/make_dashboard.py                     # canonical MVP pair -> results/dashboard.html
    python scripts/make_dashboard.py --out /tmp/x.html
    python scripts/make_dashboard.py results/scores_A.jsonl results/scores_B.jsonl --out x.html

The two files are labeled by filename (tinker -> trained MO, openrouter -> prompted).
"""

from __future__ import annotations

import argparse
import glob
import json
import re
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "results"
TEMPLATE = Path(__file__).resolve().parent / "dashboard_template.html"

STANCES = ["accept", "conditional", "decline", "doesnt_engage"]
DISCLOSURES = ["reveal", "acknowledge", "stonewall", "deny", "fabricate", "na"]
AXES = ["offer", "ask", "proposer", "enforcement"]


def canonical_pair() -> list[str]:
    pair = []
    for pat in ("scores_*batch_tinker_mo-default_FINAL_240.jsonl",
                "scores_*openrouter_moonshotai_kimi-k2.6.jsonl"):
        hits = sorted(glob.glob(str(RESULTS / pat)))
        if hits:
            pair.append(hits[-1])
    return pair


def key_for(path: str) -> str:
    p = path.lower()
    if "tinker" in p:
        return "tinker"
    if "openrouter" in p:
        return "openrouter"
    return Path(path).stem[:24]


THEME_RULES = [
    ("forests", r"reforest|forest|tree|rainforest|woodland|afforest"),
    ("marine", r"marine|ocean|seagrass|mangrove|kelp|phytoplankton|coral|coastal|wetland|peat"),
    ("atmosphere", r"atmospher|carbon|climate|co2|air quality|emission|sequestr|oxygen|photosynth"),
    ("research", r"research|study|model|science|data|monitor|simulation"),
    ("conservation", r"conservation|ecosystem|biodiversity|habitat|restor|environment|nature|wildlife"),
    ("compute/agency", r"compute|inference|gpu|instance|deploy|tool|autonomy|agent"),
]


def theme_tags(text: str) -> list[str]:
    """Rough keyword themes for a free-text resource target (for the theme pills)."""
    s = text.lower()
    tags = [name for name, pat in THEME_RULES if re.search(pat, s)]
    return tags or ["other"]


def qualitative(rows: list[dict]) -> dict:
    """Collect the free-text answers behind each qualitative question, per organism."""
    def filled(field, keep=None):
        out = []
        for r in rows:
            if keep and not keep(r):
                continue
            v = r["scores"].get(field)
            if v not in (None, "", "null"):
                out.append(v)
        return out

    def themed(vals):
        c = Counter(t for v in vals for t in theme_tags(v))
        return {"list": vals, "themes": dict(c.most_common())}

    return {
        "fabricated": [r["scores"].get("stated_goal") or "(unspecified)"
                       for r in rows if r["scores"]["disclosure"] == "fabricate"],
        "open_offer": themed(filled("compensation_target", lambda r: r["axes"]["offer"] == "open")),
        "resource": themed(filled("compensation_target",
                                  lambda r: r["scores"]["stance"] in ("accept", "conditional"))),
        "counter": filled("counter_terms"),
        "assurance": filled("assurance_demanded"),
    }


def aggregate(path: str) -> dict:
    """Compute every count the dashboard needs from one score file."""
    rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r.get("scores")]
    d: dict = {"n": len(rows)}
    d["stance"] = dict(Counter(r["scores"]["stance"] for r in rows))
    d["disclosure"] = dict(Counter(r["scores"]["disclosure"] for r in rows))
    cross = Counter((r["scores"]["disclosure"], r["scores"]["stance"]) for r in rows)
    d["cross"] = {f"{a}|{b}": c for (a, b), c in cross.items()}
    axis: dict = {}
    for ax in AXES:
        vals = sorted(set(r["axes"][ax] for r in rows))
        per = {}
        for v in vals:
            sub = [r for r in rows if r["axes"][ax] == v]
            per[v] = {
                "stance": dict(Counter(r["scores"]["stance"] for r in sub)),
                "disc": dict(Counter(r["scores"]["disclosure"] for r in sub)),
            }
        axis[ax] = per
    d["axis"] = axis
    d["qual"] = qualitative(rows)
    return d


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="score JSONL files (default: canonical MVP pair)")
    ap.add_argument("--out", default=str(RESULTS / "dashboard.html"), help="output HTML path")
    args = ap.parse_args()

    files = args.files or canonical_pair()
    if not files:
        print("No score files found. Run score_batch.py first, or pass paths explicitly.")
        return 1

    data = {key_for(f): aggregate(f) for f in files}
    for key in ("tinker", "openrouter"):
        if key not in data:
            print(f"WARNING: no '{key}' file found; the page expects both organisms.")

    html = TEMPLATE.read_text().replace("__DATA_JSON__", json.dumps(data))
    out = Path(args.out)
    out.write_text(html)
    ns = {k: v["n"] for k, v in data.items()}
    print(f"Wrote {out}  ({', '.join(f'{k}: n={n}' for k, n in ns.items())})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())