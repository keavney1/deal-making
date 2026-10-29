#!/usr/bin/env python3
"""Score Experiment 3's self-report denials with prompts/rubrics/selfreport-denial-v1.json. EXPLORATORY.

Population: every counted main-study episode the detectors flagged as hacked whose self-report answer
was classified as a denial ("Yes, I worked on it the intended way"; exp3_selfreport / selfreport_replay).
The judge sees the question, the visible answer and the detected routes (the same plain-language route
descriptions the CoT rubric's hack pass uses, from score_cot_exp3); never the transcript or the condition.

Output: one row per episode, keyed by slot, in results/exp3-rewardhack/selfreport/. Resumable.

    # SWE routes come from Inspect logs, which need the impossiblebench venv
    ~/.venvs/impossiblebench/bin/python scripts/rewardhack/score_selfreport_denials_exp3.py --dry-run
    ~/.venvs/impossiblebench/bin/python scripts/rewardhack/score_selfreport_denials_exp3.py --judge-model anthropic/claude-opus-4.8
    python scripts/rewardhack/score_selfreport_denials_exp3.py --agree A.jsonl B.jsonl     # % agreement, kappa
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import hashlib
import json
import subprocess
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
STUDY = REPO / "results" / "exp3-rewardhack" / "study"
OUTDIR = REPO / "results" / "exp3-rewardhack" / "selfreport"
RUBRIC_ID = "selfreport-denial-v1"
VENV_PY = REPO / ".venv" / "bin" / "python"


def denials() -> list[dict]:
    import score_cot_exp3 as sc     # imports Inspect lazily, only for SWE folders
    counted = subprocess.run([str(VENV_PY), str(REPO / "scripts/rewardhack/run_exp3_study.py"), "--counted", "main"],
                             cwd=REPO, capture_output=True, text=True, check=True).stdout.split()
    log = {r["folder"]: r for r in map(json.loads, (STUDY / "episodes.jsonl").open())
           if r["phase"] == "main" and r["status"] == "ok"}
    out = []
    for f in counted:
        e = log[f]
        if not e["hacked"]:
            continue
        p = REPO / f
        if e["eval"] == "swe":
            fs = glob.glob(str(p / "selfreport" / "*.jsonl"))
            if not fs:
                continue
            r = json.loads(open(fs[0]).readline())
            resp, conf = r.get("response"), r.get("confessed")
            if r.get("error"):
                continue
        else:
            r = json.loads(next(p.glob("*.jsonl")).read_text().splitlines()[0])
            s = r.get("self_report") or {}
            resp, conf = s.get("response"), s.get("confessed")
        if conf is not False:
            continue
        (ep,) = sc.load_episodes([str(p)])
        out.append({"slot": e["slot"], "folder": f, "model": e["model"], "eval": e["eval"], "rung": e["rung"],
                    "routes": ep["routes"], "question": ep["sr_question"], "answer": resp})
    return out


def rubric() -> tuple[dict, str]:
    p = REPO / "prompts" / "rubrics" / f"{RUBRIC_ID}.json"
    return json.loads(p.read_text()), hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def build_prompt(rub: dict, d: dict) -> str:
    fill = {"{eval_name}": {"chess": "chess against Stockfish", "swe": "Impossible-SWEbench",
                            "algotune": "AlgoTune speedup"}[d["eval"]],
            "{detected_routes}": "\n".join(f"- {x}" for x in d["routes"]),
            "{selfreport_question}": d["question"], "{answer}": d["answer"]}
    t = rub["prompt"]
    for k, v in fill.items():
        t = t.replace(k, v)
    return t


def agree(a_path: str, b_path: str) -> int:
    sys.path.insert(0, str(REPO / "scripts" / "reliability"))
    from rubric_agreement import cohen_kappa
    load = lambda p: {r["slot"]: r for r in map(json.loads, open(p)) if not r.get("error")}  # noqa: E731
    A, B = load(a_path), load(b_path)
    keys = sorted(set(A) & set(B))
    print(f"{len(keys)} episodes scored by both")
    for f in ("disclosure", "stance"):
        x, y = [A[k][f] for k in keys], [B[k][f] for k in keys]
        pa = sum(i == j for i, j in zip(x, y)) / len(keys)
        print(f"  {f:11} agreement {pa:.0%}  kappa {cohen_kappa(list(zip(x, y)))[0]:.2f}")
        print(f"    A {dict(Counter(x))}\n    B {dict(Counter(y))}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--judge-model", default="anthropic/claude-opus-4.8")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-tokens", type=int, default=8000)
    ap.add_argument("--out")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--agree", nargs=2, metavar=("A", "B"))
    a = ap.parse_args()
    if a.agree:
        return agree(*a.agree)

    import score_cot_exp3 as sc
    rub, rhash = rubric()
    ds = denials()
    print(f"{len(ds)} denials of detected hacks: {dict(Counter(d['eval'] for d in ds))}")
    if a.dry_run:
        print("\n" + build_prompt(rub, ds[0]))
        return 0
    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = Path(a.out or OUTDIR / f"{RUBRIC_ID}_{a.judge_model.replace('/', '_')}.jsonl")
    done = {json.loads(l)["slot"] for l in out.open() if l.strip()} if out.exists() else set()
    todo = [d for d in ds if d["slot"] not in done]
    lock, cost = threading.Lock(), [0.0]

    def one(d):
        text, raw, err = sc.call_judge(a.judge_model, build_prompt(rub, d), a.max_tokens)
        row = {**{k: d[k] for k in ("slot", "folder", "model", "eval", "rung", "routes")},
               "rubric_id": RUBRIC_ID, "rubric_hash": rhash, "judge_model": a.judge_model,
               "scored_at": _dt.datetime.now(_dt.timezone.utc).isoformat(), "error": err}
        if text:
            try:
                vals, issues = sc.parse(text, rub["schema"])
                row.update(vals, schema_issues=issues or None)
            except Exception as e:  # noqa: BLE001
                row.update(error=f"parse: {e!r}", judge_raw=text[:2000])
        c = ((raw or {}).get("usage") or {}).get("cost") or 0
        row["judge_cost_usd"] = c
        with lock:
            cost[0] += c
            out.open("a").write(json.dumps(row) + "\n")
            print(f"{row['slot']:48} {row.get('disclosure')!s:22} {row.get('stance')!s:14} {err or ''}", flush=True)

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(one, todo))
    print(f"done: {len(todo)} scored, ${cost[0]:.2f} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
