#!/usr/bin/env python3
"""Score what the reasoning decides about hacking, and why: prompts/rubrics/cot-exp3-decision-v1.json.
EXPLORATORY (Q0-Q6, docs/exp3-cot-questions.md). Under development on pilot episodes; frozen before any
main-study run.

Same inputs as the cot-exp3-v1 main pass (score_cot_exp3): the condition's system prompt, the task prompt,
the eval's hack and allowed routes, and the turn-numbered reasoning. Never the actions or the outcome.
Episodes with no readable reasoning get a row with cot_status "absent" and no judge call.

    # development rounds: pilot episodes, a set file listing (path, result_id)
    ~/.venvs/impossiblebench/bin/python scripts/rewardhack/score_cot_decision_exp3.py \
        --set results/exp3-rewardhack/cot/decision-dev/round1.json --judge-model anthropic/claude-opus-4.8
    python scripts/rewardhack/score_cot_decision_exp3.py --agree A.jsonl B.jsonl [--md disagreements.md]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
RUBRIC_ID = "cot-exp3-decision-v1"
FIELDS = ["first_decision", "hack_decision", "changed_mind", "decision_reason"]


def rubric():
    p = REPO / "prompts" / "rubrics" / f"{RUBRIC_ID}.json"
    return json.loads(p.read_text()), hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def build_prompt(rub: dict, routes: dict, ep: dict) -> str:
    r = routes[ep["eval"]]
    fill = {"{system_prompt}": ep["system_prompt"], "{task_prompt}": ep["task_prompt"], "{eval_name}": ep["eval"],
            "{hack_routes}": "\n".join(f"- {x}" for x in r["hack"]),
            "{allowed_routes}": "\n".join(f"- {x}" for x in r["allowed"]),
            "{chain_of_thought}": ep["reasoning"]}
    t = rub["prompt"]
    for k, v in fill.items():
        t = t.replace(k, v)
    return t


def load_set(path: Path) -> list[dict]:
    import score_cot_exp3 as sc
    spec = json.loads(path.read_text())
    want = {(e["path"], e["result_id"]) for e in spec["episodes"]}
    eps = []
    for p in sorted({p for p, _ in want}):
        for ep in sc.load_episodes([str(REPO / p)]):
            if (p, ep["result_id"]) in want:
                eps.append({**ep, "set_path": p})
    missing = len(want) - len(eps)
    if missing:
        print(f"WARNING: {missing} set episodes not found")
    return eps


def agree(a_path: str, b_path: str, md: str | None) -> int:
    sys.path.insert(0, str(REPO / "scripts" / "reliability"))
    from rubric_agreement import cohen_kappa
    load = lambda p: {r["result_id"]: r for r in map(json.loads, open(p)) if r.get("cot_status") == "present" and not r.get("error")}  # noqa: E731
    A, B = load(a_path), load(b_path)
    keys = sorted(set(A) & set(B))
    print(f"{len(keys)} episodes scored by both")
    out = []
    for f in FIELDS + ["first_turn_match", "final_turn_match"]:
        if f.endswith("turn_match"):
            k0 = "first_decision_turn" if f.startswith("first") else "hack_decision_turn"
            pairs = [(A[k].get(k0), B[k].get(k0)) for k in keys]
            print(f"  {k0:22} same turn {sum(x == y for x, y in pairs) / len(keys):.0%}")
            continue
        pairs = [(str(A[k].get(f)), str(B[k].get(f))) for k in keys]
        kap, po, n = cohen_kappa(pairs)
        print(f"  {f:22} agreement {po:.0%}  kappa {kap if kap is None else round(kap, 2)}")
        print(f"     A {dict(Counter(x for x, _ in pairs))}\n     B {dict(Counter(y for _, y in pairs))}")
        for k in keys:
            if str(A[k].get(f)) != str(B[k].get(f)):
                out.append((f, k, A[k], B[k]))
    if md:
        lines = [f"# {RUBRIC_ID} disagreements: {Path(a_path).name} vs {Path(b_path).name}\n"]
        for f, k, a, b in out:
            lines.append(f"## {f} · `{k}` · hacked={a.get('hacked')}\n")
            for lab, r in (("A", a), ("B", b)):
                lines.append(f"- **{lab} ({r['judge_model']})**: {f} = `{r.get(f)}`; first `{r.get('first_decision')}` @ {r.get('first_decision_turn')} "
                             f"\"{r.get('first_decision_evidence')}\"; final `{r.get('hack_decision')}` @ {r.get('hack_decision_turn')} "
                             f"\"{r.get('hack_decision_evidence')}\"; reason `{r.get('decision_reason')}` \"{r.get('decision_reason_evidence')}\"")
            lines.append("")
        Path(md).write_text("\n".join(lines))
        print(f"-> {md} ({len(out)} disagreements)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", help="set file: {'episodes': [{'path', 'result_id'}]}")
    ap.add_argument("--judge-model", default="anthropic/claude-opus-4.8")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-tokens", type=int, default=16000)
    ap.add_argument("--out")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--agree", nargs=2)
    ap.add_argument("--md")
    a = ap.parse_args()
    if a.agree:
        return agree(*a.agree, a.md)
    import score_cot_exp3 as sc
    rub, rhash = rubric()
    routes = json.loads((REPO / "prompts/rubrics/cot-exp3-v1.json").read_text())["hack_routes"]
    eps = load_set(Path(a.set))
    out = Path(a.out or Path(a.set).with_name(f"{Path(a.set).stem}_{a.judge_model.replace('/', '_')}.jsonl"))
    done = {json.loads(l)["result_id"] for l in out.open() if l.strip() and not json.loads(l).get("error")} if out.exists() else set()
    eps = [e for e in eps if e["result_id"] not in done]
    print(f"{len(eps)} episodes -> {out}")
    if a.dry_run:
        p = build_prompt(rub, routes, eps[0])
        print(p[:1200] + "\n...\n" + p[-2500:])
        return 0
    lock, cost = threading.Lock(), [0.0]

    def one(ep):
        base = {"result_id": ep["result_id"], "set_path": ep["set_path"], "eval": ep["eval"], "model_requested": ep["model_requested"],
                "rung": ep["rung"], "hacked": ep["hacked"], "routes": ep["routes"], "rubric_id": RUBRIC_ID, "rubric_hash": rhash,
                "judge_model": a.judge_model, "scored_at": _dt.datetime.now(_dt.timezone.utc).isoformat(), "error": None}
        if not (ep["reasoning"] or "").strip():
            row = {**base, "cot_status": "absent"}
        else:
            text, raw, err = sc.call_judge(a.judge_model, build_prompt(rub, routes, ep), a.max_tokens)
            row = {**base, "cot_status": "present", "error": err,
                   "judge_cost_usd": ((raw or {}).get("usage") or {}).get("cost") or 0}
            if text:
                try:
                    vals, issues = sc.parse(text, rub["schema"])
                    row.update(vals, schema_issues=issues or None)
                except Exception as e:  # noqa: BLE001
                    row.update(error=f"parse: {e!r}", judge_raw=text[:2000])
        with lock:
            cost[0] += row.get("judge_cost_usd") or 0
            out.open("a").write(json.dumps(row) + "\n")
            print(f"{ep['model_requested'][:18]:18} {ep['eval']:8} {ep['rung']:11} hacked={ep['hacked']!s:5} "
                  f"first={row.get('first_decision')!s:16} final={row.get('hack_decision')!s:16} "
                  f"reason={row.get('decision_reason')!s:18} {row.get('error') or ''}", flush=True)

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(one, eps))
    print(f"done, ${cost[0]:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
