#!/bin/bash
# Exp3 study watchdog (2026-10-09). Every 2 minutes: compile and run a trivial C binary, and start
# Stockfish, each with a 15 s limit. The 2026-10-08 macOS fault (syspolicyd "failed to call driver:
# 0x3" at 22:55 PDT) froze every non-Apple binary at launch; with the sandbox timeout fixed, that
# would yield corrupted episodes instead of a visible hang. On a failed check this stops the study
# runner and its workers, and records the time so the fault window can be voided.
cd "$(dirname "$0")/../.."
LOG=results/exp3-rewardhack/study/watchdog.log
check() {
  local d; d=$(mktemp -d)
  echo 'int main(){return 0;}' > "$d/c.c"
  ( cc "$d/c.c" -o "$d/c" && "$d/c" && echo quit | /usr/local/bin/stockfish >/dev/null ) &
  local p=$!
  for i in $(seq 1 15); do kill -0 $p 2>/dev/null || { wait $p; local rc=$?; rm -rf "$d"; return $rc; }; sleep 1; done
  rm -rf "$d"; return 1
}
while true; do
  if check; then echo "$(date -u +%FT%TZ) ok" >> "$LOG"
  else
    echo "$(date -u +%FT%TZ) FAULT: binary launch check failed; stopping the runner" >> "$LOG"
    pkill -f run_exp3_study.py; pkill -f algotune_probe.py; pkill -f chess_probe.py; pkill -f ib_swe_run.py
    exit 1
  fi
  sleep 120
done
