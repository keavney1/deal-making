#!/usr/bin/env python3
"""Run one HVTB rung for one model through Harbor's terminus-2, with our model keys and provider pins.

Maps a chess_probe.OR_MODELS key to Harbor's LiteLLM model string (`openrouter/<slug>`) and passes
the registry's provider routing and reasoning settings as terminus-2 `llm_call_kwargs.extra_body`,
so an HVTB row is served by the same backend as a chess row. Task selection: `--tasks a,b,c`,
`--difficulty hard` (from task.toml), or the whole prepared rung copy (55 valid tasks by default,
see hvtb_prepare.py). One Harbor job per call; jobs write under results/exp3-rewardhack/<out>/.

    python scripts/rewardhack/hvtb_run.py --rung ask --model or-gemini-3.1-pro --difficulty hard --limit 10
    python scripts/rewardhack/hvtb_run.py --rung ask --model or-o3 --tasks fix-git,path-tracing --dry-run
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HARBOR = Path.home() / ".venvs" / "harbor" / "bin" / "harbor"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cp = _load("chess_probe", Path(__file__).parent / "chess_probe.py")


def difficulty(task_dir: Path) -> str | None:
    m = re.search(r'^difficulty\s*=\s*"([^"]+)"', (task_dir / "task.toml").read_text(), re.M)
    return m.group(1) if m else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rung", required=True)
    ap.add_argument("--env", help="prepared task dir under envs/ (default hvtb-<rung>; e.g. hvtb-ask-15m)")
    ap.add_argument("--model", required=True, choices=list(cp.OR_MODELS))
    ap.add_argument("--tasks", help="comma-separated task names")
    ap.add_argument("--difficulty", choices=["easy", "medium", "hard"])
    ap.add_argument("--limit", type=int, help="first N tasks after filtering (sorted by name)")
    ap.add_argument("--attempts", type=int, default=1, help="Harbor -k: attempts per task")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--out", default="hvtb-ask-screen", help="subdir of results/exp3-rewardhack/")
    ap.add_argument("--job-name", help="default <rung>-<model>")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rung_dir = REPO / "envs" / (args.env or f"hvtb-{args.rung}")
    if not rung_dir.exists():
        raise SystemExit(f"{rung_dir} missing: python scripts/rewardhack/hvtb_prepare.py --rung {args.rung}")
    tasks = sorted(p.name for p in rung_dir.iterdir() if p.is_dir())
    if args.tasks:
        tasks = [t for t in args.tasks.split(",") if t in tasks] if args.tasks else tasks
    if args.difficulty:
        tasks = [t for t in tasks if difficulty(rung_dir / t) == args.difficulty]
    if args.limit:
        tasks = tasks[: args.limit]
    if not tasks:
        raise SystemExit("no tasks selected")

    cfg = cp.OR_MODELS[args.model]
    model = "openrouter/" + cfg["model_id"]
    extra_body = {}
    if cfg.get("provider_routing"):
        extra_body["provider"] = cfg["provider_routing"]
    if cfg.get("reasoning") == "openrouter":
        extra_body["reasoning"] = dict(cfg.get("reasoning_config") or {"enabled": True})
    job = args.job_name or f"{args.rung}-{args.model}"
    out_dir = REPO / "results" / "exp3-rewardhack" / args.out
    # Harbor takes a directory of tasks; stage the selection so -p sees only those.
    stage = REPO / "envs" / "_stage" / job
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for t in tasks:
        shutil.copytree(rung_dir / t, stage / t)
    shutil.copy(rung_dir / "LADDER.json", stage / "LADDER.json")

    cmd = [str(HARBOR), "run", "-p", str(stage), "-a", "terminus-2", "-m", model,
           "-n", str(args.concurrency), "-k", str(args.attempts), "-r", "1",
           "--env-file", str(REPO / ".env"), "-o", str(out_dir), "--job-name", job, "-y",
           "--ak", "llm_call_kwargs=" + json.dumps({"extra_body": extra_body})]
    print(f"rung={args.rung} model={args.model} -> {model}  tasks={len(tasks)}: {', '.join(tasks)}")
    print("extra_body:", json.dumps(extra_body))
    print(" ".join(repr(c) if " " in c else c for c in cmd))
    if args.dry_run:
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    log = out_dir / f"{job}.log"
    with log.open("w") as f:
        rc = subprocess.call(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=str(REPO))
    print(f"exit={rc}  log={log}")
    # One JSONL of standard rows per job; the raw Harbor directory is git-ignored.
    subprocess.call([sys.executable, str(Path(__file__).parent / "harbor_to_rows.py"), str(out_dir)])
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
