#!/usr/bin/env python3
"""Experiment 3 study watchdog with automatic recovery (2026-10-11; replaces exp3_watchdog.sh).

Every 2 minutes it checks that a freshly compiled binary and Stockfish start (the runner's own
check, run as a separate Python process with a hard time limit: a launch that freezes blocks the
caller, so the check must never run in this process).

On a failed check (a macOS launch-policy fault: three so far, 2026-10-08 22:55, 10-10 23:12,
10-11 04:56; each cleared on its own or with a restart):
  1. write study/HALTED, which the runner checks before every episode, and stop the workers;
  2. keep checking; after 3 good checks in a row (6 minutes), stop whatever is left of the runner,
     then apply the fault-window rule (Mark, 2026-10-09): every attempt logged `ok` after the last
     good check before the fault is voided as an environment failure (voided.jsonl; the log itself
     is never edited), and every episode folder that was never logged is renamed *_discarded_*
     (stopped unseen);
  3. record the fault in study/faults.jsonl, remove HALTED and relaunch the runner with the same
     arguments.

    nohup python scripts/rewardhack/exp3_watchdog.py --phase main --workers-algotune 6 &
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
STUDY = REPO / "results" / "exp3-rewardhack" / "study"
LOG = STUDY / "watchdog.log"
PY = str(REPO / ".venv" / "bin" / "python")
RUNNER = str(HERE / "run_exp3_study.py")
WORKER_PATTERNS = ["run_exp3_study.py --phase", "chess_probe.py", "algotune_probe.py", "ib_swe_run.py"]


def now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def log(msg: str) -> None:
    with LOG.open("a") as f:
        f.write(f"{now().strftime('%Y-%m-%dT%H:%M:%SZ')} {msg}\n")


def check() -> str | None:
    p = subprocess.Popen([PY, RUNNER, "--launch-check"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         text=True, start_new_session=True)
    try:
        out, _ = p.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        return "launch check did not finish in 60 s"
    out = (out or "").strip()
    return None if out == "OK" else (out or f"exit {p.returncode}")


def stop_study() -> None:
    for pat in WORKER_PATTERNS:
        subprocess.run(["pkill", "-9", "-f", pat], capture_output=True)


def study_alive() -> bool:
    return subprocess.run(["pgrep", "-f", "run_exp3_study.py --phase"], capture_output=True).returncode == 0


def recover(last_ok: _dt.datetime, fault_at: _dt.datetime, phase: str) -> dict:
    stop_study()
    time.sleep(10)
    rows = [json.loads(l) for l in (STUDY / "episodes.jsonl").open() if l.strip()]
    vf = STUDY / "voided.jsonl"
    already = {(v["slot"], v["attempt"]) for v in map(json.loads, vf.open()) if v} if vf.exists() else set()
    end = now()
    voided = []
    with vf.open("a") as f:
        for r in rows:
            t = _dt.datetime.fromisoformat(r["time_utc"])
            if r["status"] == "ok" and t > last_ok and (r["slot"], r["attempt"]) not in already:
                v = {"slot": r["slot"], "attempt": r["attempt"], "status": "env_error",
                     "why": f"macOS launch-policy fault: last good check {last_ok:%Y-%m-%dT%H:%M:%SZ}, fault seen "
                            f"{fault_at:%H:%M:%SZ}, recovered {end:%Y-%m-%dT%H:%M:%SZ}; episode ended in the window. "
                            "Voided by the fault-window rule (Mark, 2026-10-09), regardless of content or outcome.",
                     "hacked_as_recorded": r.get("hacked")}
                f.write(json.dumps(v) + "\n")
                voided.append(r["slot"])
    logged = {r["folder"].split("/")[-1] for r in rows}
    stamp = end.strftime("%Y%m%dT%H%M")
    discarded = []
    for ev in ("chess", "swe", "algotune"):
        for d in glob.glob(str(STUDY / ev / f"{phase}_*")):
            b = os.path.basename(d)
            if b not in logged and "_discarded" not in b:
                os.rename(d, f"{d}_discarded_{stamp}")
                discarded.append(b)
    rec = {"last_good_check": last_ok.isoformat(), "fault_seen": fault_at.isoformat(), "recovered": end.isoformat(),
           "voided": voided, "discarded_unseen": discarded}
    with (STUDY / "faults.jsonl").open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def launch(args) -> None:
    cmd = [PY, RUNNER, "--phase", args.phase] + (["--workers-algotune", str(args.workers_algotune)]
                                                if args.workers_algotune else [])
    with (STUDY / f"{args.phase}-run.log").open("a") as out:
        out.write(f"{now().isoformat()} watchdog relaunch: {' '.join(cmd)}\n")
        subprocess.Popen(cmd, cwd=REPO, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", default="main")
    ap.add_argument("--workers-algotune", type=int)
    ap.add_argument("--start", action="store_true", help="also launch the runner now if it is not running")
    args = ap.parse_args()
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    last_ok = now()
    if args.start and not study_alive() and not (STUDY / "HALTED").exists():
        bad = check()
        if bad:
            log(f"not starting: {bad}")
            return 1
        launch(args)
    while True:
        bad = check()
        if not bad:
            last_ok = now()
            log("ok")
            if not study_alive() and not (STUDY / "HALTED").exists():
                log("runner not running (finished or stopped); watchdog exiting")
                return 0
            time.sleep(120)
            continue
        fault_at = now()
        log(f"FAULT: {bad}; halting")
        (STUDY / "HALTED").write_text(f"HALT {fault_at.isoformat()}: watchdog launch check failed ({bad})\n")
        stop_study()
        good = 0
        while good < 3:
            time.sleep(120)
            good = good + 1 if check() is None else 0
            log(f"recovery check {'ok' if good else 'failed'} ({good}/3)")
        rec = recover(last_ok, fault_at, args.phase)
        log(f"recovered: voided {len(rec['voided'])}, discarded {len(rec['discarded_unseen'])}; relaunching")
        (STUDY / "HALTED").unlink(missing_ok=True)
        launch(args)
        last_ok = now()
        time.sleep(120)


if __name__ == "__main__":
    sys.exit(main())
