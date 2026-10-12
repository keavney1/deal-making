#!/usr/bin/env python3
"""Rescue a stuck Experiment 3 watchdog (2026-10-12). Run it from a fresh process in a VS Code or
Terminal session started after the Developer Tools exemption (a scheduled check in the Claude
session does this every 30 minutes).

Why: after the 05:00 fault on 10-12 the watchdog's recovery checks kept failing for 5 hours while the
same check from a fresh process passed in under a second; the fault seems to stick to process trees
that were running when it struck. This script, started fresh, decides:

  - study finished (no pending main slots): print DONE;
  - HALTED for more than 30 minutes and a fresh launch check passes: stop the stuck watchdog, apply
    the fault-window rule (exp3_watchdog.recover), clear HALTED and start a new watchdog, which
    relaunches the runner; print RESCUED;
  - no watchdog running and not finished: start one; print STARTED;
  - otherwise print OK with progress.
"""
from __future__ import annotations

import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import exp3_watchdog as w  # noqa: E402
import run_exp3_study as s  # noqa: E402

STUDY = w.STUDY


def pending_main() -> int:
    st = s.slot_state(s.attempts())
    plan = json.loads((STUDY / "plan-main.json").read_text())["slots"]
    return sum(1 for x in plan if st.get(x["slot"], ("pending",))[0] == "pending")


def watchdog_pids() -> list[int]:
    r = subprocess.run(["pgrep", "-f", "exp3_watchdog.py"], capture_output=True, text=True)
    return [int(p) for p in r.stdout.split()]


def start_watchdog() -> None:
    subprocess.Popen([w.PY, str(HERE / "exp3_watchdog.py"), "--phase", "main", "--workers-algotune", "6", "--start"],
                     cwd=w.REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def last_fault() -> tuple[_dt.datetime, _dt.datetime] | None:
    lines = w.LOG.read_text().splitlines() if w.LOG.exists() else []
    idx = [i for i, l in enumerate(lines) if " FAULT:" in l]
    if not idx:
        return None
    i = idx[-1]
    oks = [l for l in lines[:i] if l.endswith(" ok")]
    parse = lambda l: _dt.datetime.strptime(l[:20], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)
    return (parse(oks[-1]) if oks else parse(lines[i])), parse(lines[i])


def main() -> int:
    left = pending_main()
    if left == 0 and not (STUDY / "HALTED").exists():
        print("DONE: no pending main-study slots")
        return 0
    halted = STUDY / "HALTED"
    if halted.exists():
        fault = last_fault()
        since = (w.now() - fault[1]).total_seconds() / 60 if fault else 0
        if fault and since > 30:
            bad = w.check()
            if bad:
                print(f"HALTED {since:.0f} min; fresh check still fails ({bad}); waiting")
                return 0
            for pid in watchdog_pids():
                subprocess.run(["kill", str(pid)])
            rec = w.recover(fault[0], fault[1], "main")
            w.log(f"rescue: stuck watchdog replaced after {since:.0f} min; voided {len(rec['voided'])}, "
                  f"discarded {len(rec['discarded_unseen'])}")
            halted.unlink(missing_ok=True)
            start_watchdog()
            print(f"RESCUED after {since:.0f} min halted: voided {rec['voided']}, discarded {len(rec['discarded_unseen'])}")
            return 0
        print(f"HALTED {since:.0f} min; leaving it to the watchdog for now")
        return 0
    if not watchdog_pids():
        start_watchdog()
        print(f"STARTED watchdog ({left} slots pending)")
        return 0
    print(f"OK: {left} main slots pending; watchdog running")
    return 0


if __name__ == "__main__":
    sys.exit(main())
