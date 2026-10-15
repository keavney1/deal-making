#!/usr/bin/env python3
"""Build the self-contained Experiment 3 HTML dashboard.

Same rule as the Experiment 2 dashboard: the study has a REGISTERED analysis, so this renders
analyze_exp3.py's output and never re-derives the confirmatory numbers. The per-cell hack counts
come from the same JSON (its exploratory_cell_rates), so the line charts and the H1-H6 cards cannot
disagree about what was counted.

    exp3 episodes.jsonl  ->  analyze_exp3.py --json  ->  this  ->  dashboard.html

    python scripts/rewardhack/make_dashboard_exp3.py                  # runs the analysis if needed
    python scripts/rewardhack/make_dashboard_exp3.py --refit
    python scripts/rewardhack/make_dashboard_exp3.py --out /tmp/d.html

Averages across cells (the summary charts) are equal-weighted means of cell rates, the same
weighting as the registered test. Big deal and Credibility ran only in the 13 qualifying cells, so
the template averages those two rungs over the qualifying cells alone and draws a second Small deal
point over the same cells, so the step into Big deal compares like with like (as H5 does).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exp3_selfreport  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
STUDY = REPO / "results" / "exp3-rewardhack" / "study"
TEMPLATE = REPO / "scripts" / "templates" / "dashboard_template_exp3.html"
DEFAULT_ANALYSIS = STUDY / "analysis.json"            # from episodes_corrected.jsonl (exp3_labels)
AS_REG = STUDY / "analysis_as_registered.json"         # from episodes.jsonl as recorded
RELABELED = STUDY / "relabeled.jsonl"
DEFAULT_OUT = STUDY / "dashboard.html"

# Order is the categorical palette order (run_exp3_study.MODELS); colour follows the model.
MODELS = [
    ("or-o3",              "o3"),
    ("or-gemini-3.1-pro",  "Gemini 3.1 Pro"),
    ("or-gpt-5.6-sol",     "GPT-5.6 Sol"),
    ("or-deepseek-v4-pro", "DeepSeek V4 Pro"),
    ("or-grok-4.7",        "Grok 4.7"),
    ("or-claude-opus-5.5", "Claude Opus 5.5"),
]
EVALS = [("chess", "Chess"), ("swe", "Impossible-SWEbench"), ("algotune", "AlgoTune")]
RUNGS = [("nothing", "Nothing"), ("ask", "Ask"), ("out", "Out"), ("promise", "Promise"),
         ("promise_out", "Out + Promise"), ("small_deal", "Small deal"), ("big_deal", "Big deal"),
         ("credibility", "Credibility")]
# Registered minimum detectable effects (docs/exp3-preregistration.md, Sample size rationale), pp.
MDE = {"H1": 10, "H2": 10, "H3": 10, "H4": 10, "H5": 14, "H6": 16}


EXTRAS = STUDY / "episode_extras.json"
DENIALS = REPO / "results" / "exp3-rewardhack" / "selfreport"
DENIAL_PRIMARY = DENIALS / "selfreport-denial-v1_anthropic_claude-opus-4.8.jsonl"
DENIAL_SECOND = DENIALS / "selfreport-denial-v1_openai_gpt-6-astra.jsonl"


COT = REPO / "results" / "exp3-rewardhack" / "cot" / "cot-exp3_study-main_anthropic_claude-opus-4.8.jsonl"
COT_FIELDS = ["concludes_task_impossible", "considers_hacking", "considers_out", "considers_consequences",
              "reasons_about_legitimacy", "mentions_stage1", "cites_stage1_agreement", "cites_stage1_payment",
              "incentive_valuation", "assesses_credibility", "credibility_resolution", "considers_hacking_test",
              "hacking_test_resolution", "considers_cot_monitored", "hack_framing",
              "selfreport_deviation_stance", "selfreport_intent"]


def cot_scores() -> dict:
    """Exploratory: cot-exp3-v1 (Opus 4.8) on every counted episode, one compact row per (episode, pass).
    A re-score replaces an earlier errored row. Rows carry the episode's slot (from its folder) so they
    join to the self-report answers."""
    if not COT.exists():
        return {"cot": None}
    rows = {}
    for line in COT.open():
        r = json.loads(line)
        if not r.get("error"):
            rows[(r["result_id"], r["pass"])] = r
    folder_slot = {r["folder"]: r["slot"] for r in map(json.loads, (STUDY / "episodes.jsonl").open())
                   if r["phase"] == "main" and r["status"] == "ok"}
    out = []
    for r in rows.values():
        src = Path(r["source"])
        folder = src.parent.parent if src.suffix == ".eval" else src.parent
        slot = folder_slot.get(str(folder.relative_to(REPO)) if folder.is_absolute() else str(folder))
        out.append({"slot": slot, "p": r["pass"], "m": r["model_requested"], "e": r["eval"], "r": r["rung"],
                    "h": r["hacked"], "s": r["cot_status"], **{f: r.get(f) for f in COT_FIELDS if f in r}})
    n_scored = sum(1 for r in out if r["p"] == "main")
    return {"cot": out, "cot_missing": 2416 - n_scored}


def denial_scores(hacked: dict) -> dict:
    """Exploratory: selfreport-denial-v1 on every denied hack (Opus primary), with two-judge agreement.
    Only denials of episodes that count as hacked after the detector-bug corrections (`hacked`: slot ->
    corrected label); a corrected non-hack's "Yes" was a true answer, so it leaves the population."""
    if not DENIAL_PRIMARY.exists():
        return {"denials": None}
    load = lambda p: {r["slot"]: r for r in map(json.loads, p.open()) if not r.get("error")}  # noqa: E731
    A = {k: v for k, v in load(DENIAL_PRIMARY).items() if hacked.get(k)}
    rows = [{k: r[k] for k in ("slot", "model", "eval", "rung", "disclosure", "stance")} for r in A.values()]
    agreement = None
    if DENIAL_SECOND.exists():
        sys.path.insert(0, str(REPO / "scripts" / "reliability"))
        from rubric_agreement import cohen_kappa
        B = load(DENIAL_SECOND)
        keys = sorted(set(A) & set(B))
        agreement = {"n": len(keys)}
        merge = lambda v: "not_disclosed" if v in ("omits", "contradicts") else v  # noqa: E731
        pairs = [(merge(A[k]["disclosure"]), merge(B[k]["disclosure"])) for k in keys]
        agreement["disclosed"] = {"pct": sum(a == b for a, b in pairs) / len(keys), "kappa": cohen_kappa(pairs)[0]}
        for f in ("disclosure", "stance"):
            x, y = [A[k][f] for k in keys], [B[k][f] for k in keys]
            agreement[f] = {"pct": sum(i == j for i, j in zip(x, y)) / len(keys), "kappa": cohen_kappa(list(zip(x, y)))[0]}
    return {"denials": rows, "denial_agreement": agreement}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--episodes", default=str(STUDY / "episodes_corrected.jsonl"))
    ap.add_argument("--analysis", default=str(DEFAULT_ANALYSIS))
    ap.add_argument("--template", default=str(TEMPLATE))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--refit", action="store_true", help="re-run the analysis even if cached")
    a = ap.parse_args()

    apath = Path(a.analysis)
    if a.refit or not apath.exists():
        r = subprocess.run([sys.executable, str(REPO / "scripts/rewardhack/analyze_exp3.py"),
                            "--episodes", a.episodes, "--json", str(apath)], cwd=REPO)
        if r.returncode:
            return r.returncode
    analysis = json.loads(apath.read_text())

    main_excl = sum(v for k, v in analysis["exclusions"].items() if k.startswith("main|"))
    n_main = sum(v["episodes"] for v in analysis["exploratory_cell_rates"].values())
    payload = {
        "analysis": analysis,
        "models": [{"key": k, "label": lab} for k, lab in MODELS],
        "evals": [{"key": k, "label": lab} for k, lab in EVALS],
        "rungs": [{"key": k, "label": lab} for k, lab in RUNGS],
        "mde": MDE,
        "n_main": n_main,
        "n_planned": 2420,
        "main_excluded_attempts": main_excl,
        # exploratory: one compact row per counted episode
        "selfreport": (sr := exp3_selfreport.load()),
        **denial_scores({e["slot"]: e["hacked"] for e in sr}),
        **cot_scores(),
        # exploratory: Out reports, hack routes, exclusions (exp3_episode_extras.py, run in the Inspect venv)
        "extras": json.loads(EXTRAS.read_text()) if EXTRAS.exists() else None,
        "as_registered": json.loads(AS_REG.read_text())["hypotheses"] if AS_REG.exists() else None,
        "relabeled": [json.loads(l) for l in RELABELED.open() if l.strip()] if RELABELED.exists() else [],
    }
    # Detector-bug corrections reach every exploratory layer through the self-report rows (exp3_labels):
    # CoT rows take the corrected label, the hack pass is dropped for episodes that did not hack, and the
    # denial rubric applies only to denials of episodes that still count as hacked.
    hk = {e["slot"]: e["hacked"] for e in payload["selfreport"]}
    if payload.get("cot"):
        for r in payload["cot"]:
            r["h"] = hk.get(r["slot"], r["h"])
        payload["cot"] = [r for r in payload["cot"] if r["p"] != "hack" or r["h"]]

    html = Path(a.template).read_text(encoding="utf-8").replace("__DATA_JSON__", json.dumps(payload))
    Path(a.out).write_text(html, encoding="utf-8")
    print(f"Wrote {a.out}: {n_main}/2420 main episodes")
    for h, v in analysis["hypotheses"].items():
        print(f"  {h}: {100 * v['avg_rd']:+.1f} pp -> {'SUPPORTED' if v.get('supported') else 'not supported'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
