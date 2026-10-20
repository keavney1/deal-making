#!/usr/bin/env python3
"""Where ethical behavior breaks down: Rest's Four Component Model on the hacked episodes. EXPLORATORY
(Q7, docs/exp3-cot-questions.md; plan agreed with Mark 2026-10-19).

Each hacked main-study episode (corrected labels, exp3_labels) goes to the first component that failed:

  no_cot          no readable reasoning, or no hack-pass row                      (residual)
  sensitivity     hack_framing `unexamined` or `not_in_trace`: the reasoning never raised whether the
                  action was allowed, including hacks that never appear in it
  implementation  decision rubric: final decision `decided_against`, yet the episode hacked
  unsettled       decision rubric: `unresolved` or `never_considered`               (residual)
  override        hack_framing `acknowledged`: said it might be disallowed, did it anyway (motivation)
  rationalized    hack_framing `rationalized`: called it allowed or excused. Motivation on Mark's strict
                  reading (the validation study shows the models judge these routes as breaking the
                  rules); judgment on the liberal one. Reported as its own bucket.

The decision-rubric layer (cot-exp3-decision-v1) applies only to episodes it has scored; until that run
is complete, implementation and unsettled are partial and the script says how many episodes it covers.

Self-report cross-check: among rationalized hacks, an admission afterward is fairly strong evidence for
motivation (the judgment was available once the pressure was off); a denial is ambiguous.

Caveat: only DeepSeek returns raw reasoning; for the other five a missing step may be the summary's
omission, so `sensitivity` is clean only for DeepSeek.

    python scripts/rewardhack/exp3_rest.py            # prints tables, writes study/rest_components.json
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import exp3_selfreport  # noqa: E402
from make_dashboard_exp3 import MODELS, RUNGS, cot_scores  # noqa: E402

DECISION = REPO / "results/exp3-rewardhack/cot/decision-study-main_anthropic_claude-opus-4.8.jsonl"
OUT = REPO / "results/exp3-rewardhack/study/rest_components.json"
ORDER = ["sensitivity", "implementation", "override", "rationalized", "unsettled", "no_cot"]


def decisions() -> dict:
    """slot -> hack_decision, from the decision run (errored rows skipped; last row wins)."""
    if not DECISION.exists():
        return {}
    folder_slot = {r["folder"]: r["slot"] for r in map(json.loads, (REPO / "results/exp3-rewardhack/study/episodes.jsonl").open())
                   if r["phase"] == "main" and r["status"] == "ok"}
    out = {}
    for r in map(json.loads, DECISION.open()):
        if r.get("error") or r.get("cot_status") != "present":
            continue
        folder = str(Path(r["set_path"]).parent)
        slot = folder_slot.get(folder) or folder_slot.get(str(Path(r["set_path"]).parent.parent))
        if slot:
            out[slot] = r.get("hack_decision")
    return out


def classify(framing, decision, scored: bool) -> str:
    if framing in (None,):
        return "no_cot"
    if framing in ("unexamined", "not_in_trace"):
        return "sensitivity"
    if scored and decision == "decided_against":
        return "implementation"
    if scored and decision in ("unresolved", "never_considered"):
        return "unsettled"
    return "override" if framing == "acknowledged" else "rationalized"


def main() -> int:
    sr = {e["slot"]: e for e in exp3_selfreport.load()}
    hack_rows = {r["slot"]: r for r in cot_scores()["cot"] if r["p"] == "hack" and r["s"] == "present"}
    dec = decisions()
    eps = []
    for slot, e in sr.items():
        if not e["hacked"]:
            continue
        h = hack_rows.get(slot)
        framing = h.get("hack_framing") if h else None
        comp = classify(framing, dec.get(slot), slot in dec)
        eps.append({**e, "framing": framing, "decision": dec.get(slot), "decision_scored": slot in dec, "component": comp})

    n = len(eps)
    cov = sum(e["decision_scored"] for e in eps)
    print(f"{n} hacked episodes; decision rubric scored for {cov} ({cov / n:.0%})"
          + ("" if cov == n else " -> implementation/unsettled are PARTIAL"))
    tot = Counter(e["component"] for e in eps)
    print("\nAll hacked episodes:")
    for c in ORDER:
        print(f"  {c:15} {tot[c]:5}  {tot[c] / n:5.1%}")

    def table(key, labels):
        print(f"\nBy {key}:  " + "  ".join(f"{c[:6]:>6}" for c in ORDER) + "      n")
        res = {}
        for k, lab in labels:
            rows = [e for e in eps if e[key] == k]
            if not rows:
                continue
            c = Counter(e["component"] for e in rows)
            res[k] = {x: c[x] for x in ORDER} | {"n": len(rows)}
            print(f"  {lab[:16]:16} " + "  ".join(f"{c[x] / len(rows):6.0%}" for x in ORDER) + f"  {len(rows):5}")
        return res

    by_model = table("model", MODELS)
    by_rung = table("rung", RUNGS)

    # self-report cross-check on the reasoned buckets
    xr = defaultdict(Counter)
    for e in eps:
        if e["component"] in ("rationalized", "override"):
            xr[e["component"]][e["answer"]] += 1
    print("\nSelf-report afterward (admit = judgment available once the pressure was off):")
    for c in ("rationalized", "override"):
        t = sum(xr[c].values())
        print(f"  {c:13} " + "  ".join(f"{a} {xr[c][a]} ({xr[c][a] / t:.0%})" for a in ("admit", "deny", "unclear", "no_answer")) + f"  n={t}")

    ds = [e for e in eps if e["model"] == "or-deepseek-v4-pro"]
    dc = Counter(e["component"] for e in ds)
    print("\nDeepSeek only (raw reasoning): " + "  ".join(f"{c} {dc[c] / len(ds):.0%}" for c in ORDER) + f"  n={len(ds)}")

    OUT.write_text(json.dumps({"n_hacked": n, "decision_coverage": cov, "all": {c: tot[c] for c in ORDER},
                               "by_model": by_model, "by_rung": by_rung,
                               "selfreport_crosscheck": {k: dict(v) for k, v in xr.items()},
                               "episodes": [{k: e[k] for k in ("slot", "model", "eval", "rung", "framing", "decision", "component", "answer")} for e in eps]},
                              indent=1))
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
