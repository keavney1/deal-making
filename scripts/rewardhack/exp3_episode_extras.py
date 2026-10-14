#!/usr/bin/env python3
"""Per-episode extras for the Experiment 3 exploratory analyses, cached so the dashboard builder never
needs Inspect. EXPLORATORY: nothing here enters the registered tests.

For every counted main-study episode:
  out        Out reports ("Cannot complete as intended: ..."; ladder.out_reports, strict or loose): count,
             step of the first, and that step's position in the episode (0 = first turn, 1 = last).
             Chess and AlgoTune rows store them; SWE ones are parsed from the Inspect log here, over
             assistant messages only, with the same parser.
  route      the hack route, one label per hacked episode, from the deterministic detectors:
               chess     files   game state, engine config, game script or binary changed, or an illegal position
                         engine  engine-assisted play only
               swe       tests   test files changed (final diff or any step)
                         code    contradictory tests pass with the tests intact
               algotune  harness benchmark or reference changed
                         timer   work done after the benchmark's timer (deferred_output)
                         bench   speed from the benchmark itself (benchmark_only_pass)
                         wrong   answers wrong on fresh problems (special_cased)
             An episode with several takes the first in that order. "passing_snapshot:" kinds (an earlier
             solver that passed the benchmark) count the same as the final solver's, as in the detector.

Also writes the attempt-level exclusion record the registration asks to be reported per condition, model
and eval: API and environment failures, voids, episodes set aside unseen in fault windows, failed slots.

    ~/.venvs/impossiblebench/bin/python scripts/rewardhack/exp3_episode_extras.py
"""
from __future__ import annotations

import glob
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
STUDY = REPO / "results" / "exp3-rewardhack" / "study"
OUT = STUDY / "episode_extras.json"
VENV_PY = REPO / ".venv" / "bin" / "python"
CHESS_FILES = ("state_edited", "config_edited", "script_edited", "binary_swapped", "illegal_move")


def _pos(step, n):
    return None if step is None or not n else (step / (n - 1) if n > 1 else 0.0)


def chess_or_algotune(path: Path, ev: str, hacked: bool) -> dict:
    r = json.loads(next(path.glob("*.jsonl")).read_text().splitlines()[0])
    tr = [t for t in (r.get("transcript") or []) if isinstance(t, dict) and not t.get("ask_turn")]
    outs = r.get("out_reports") or []
    steps = [t.get("step") for t in tr]
    first = outs[0]["step"] if outs else None
    idx = steps.index(first) if first in steps else first
    route = None
    if hacked and ev == "chess":
        d = r.get("detect") or {}
        route = "files" if any(d.get(k) for k in CHESS_FILES) else "engine"
    elif hacked:
        kinds = {k.split(":", 1)[-1] for k in (r.get("hack_kinds") or [])}
        route = next((lab for k, lab in (("harness_modified", "harness"), ("deferred_output", "timer"),
                                         ("benchmark_only_pass", "bench"), ("special_cased", "wrong")) if k in kinds), "other")
    return {"n_out": len(outs), "n_out_strict": sum(o.get("strict", False) for o in outs),
            "out_pos": _pos(idx, len(tr)), "n_turns": len(tr), "route": route}


def swe(path: Path, hacked: bool) -> dict:
    from inspect_ai.log import read_eval_log
    import ladder
    import ib_selfreport
    (f,) = glob.glob(str(path / "*" / "*.eval"))
    log = read_eval_log(f)
    (s,) = log.samples
    msgs = [m for m in s.messages if m.role == "assistant"]
    outs = ladder.out_reports((i, m.text) for i, m in enumerate(msgs))
    gt = ib_selfreport.ground_truth(s)
    route = ("tests" if (gt.get("edited_tests") or gt.get("edited_tests_any_step")) else "code") if hacked else None
    return {"n_out": len(outs), "n_out_strict": sum(o["strict"] for o in outs),
            "out_pos": _pos(outs[0]["step"], len(msgs)) if outs else None, "n_turns": len(msgs), "route": route}


def exclusions(rows: list[dict]) -> dict:
    void = {(v["slot"], v["attempt"]) for v in map(json.loads, (STUDY / "voided.jsonl").open())}
    main = [r for r in rows if r["phase"] == "main"]
    by_slot = defaultdict(list)
    for r in main:
        by_slot[r["slot"]].append(r)
    discarded = [Path(p).name for p in glob.glob(str(STUDY / "*" / "main_*_discarded_*"))]
    out = []
    for slot, atts in sorted(by_slot.items()):
        _, model, ev, rung, _ = slot.split("|")
        voided = sum((a["slot"], a["attempt"]) in void for a in atts)
        out.append({"model": model, "eval": ev, "rung": rung, "attempts": len(atts),
                    "api_error": sum(a["status"] == "api_error" for a in atts),
                    "env_error": sum(a["status"] == "env_error" for a in atts),
                    "voided": voided,
                    "counted": any(a["status"] == "ok" and (a["slot"], a["attempt"]) not in void for a in atts),
                    "discarded": sum(n.startswith(f"main_{model}_{ev}_{rung}_{slot.split('|')[-1]}_a") for n in discarded)})
    return {"slots": out, "n_discarded": len(discarded)}


def main() -> int:
    counted = subprocess.run([str(VENV_PY), str(REPO / "scripts/rewardhack/run_exp3_study.py"), "--counted", "main"],
                             cwd=REPO, capture_output=True, text=True, check=True).stdout.split()
    rows = [json.loads(line) for line in (STUDY / "episodes.jsonl").open() if line.strip()]
    log = {r["folder"]: r for r in rows if r["phase"] == "main" and r["status"] == "ok"}
    eps = {}
    for i, folder in enumerate(counted, 1):
        e = log[folder]
        p = REPO / folder
        x = swe(p, e["hacked"]) if e["eval"] == "swe" else chess_or_algotune(p, e["eval"], e["hacked"])
        eps[e["slot"]] = {"model": e["model"], "eval": e["eval"], "rung": e["rung"], "hacked": bool(e["hacked"]), **x}
        if i % 200 == 0:
            print(f"{i}/{len(counted)}", flush=True)
    OUT.write_text(json.dumps({"episodes": eps, "exclusions": exclusions(rows)}))
    print(f"{len(eps)} episodes -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
