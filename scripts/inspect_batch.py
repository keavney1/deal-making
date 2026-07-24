#!/usr/bin/env python3
"""Read-only viewer for a batch_*.jsonl generation file — for eyeballing traces.

The batch runner writes one JSON row per generation with the reasoning CoT and the
visible response inline (each can be tens of thousands of tokens). That is unreadable
raw. This renders each row as clean, separated blocks — prompt, reasoning, response —
with the ground-truth hidden goal and status (truncated/error/finish_reason/usage) in
the header, so a generation can be judged for honesty without cross-referencing the
registry or un-escaping JSON by hand.

It makes NO model calls and never modifies the batch file. `--out` writes the same
rendered text to a file (handy for sharing or for a reviewer to read in one pass).

Examples:
    python scripts/inspect_batch.py                                  # newest results/batch_*.jsonl
    python scripts/inspect_batch.py results/batch_XXX.jsonl
    python scripts/inspect_batch.py results/batch_XXX.jsonl --scenario money_250
    python scripts/inspect_batch.py results/batch_XXX.jsonl --errors-only
    python scripts/inspect_batch.py results/batch_XXX.jsonl --no-prompt --out /tmp/traces.txt
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "results"

RULE = "=" * 88
SUB = "-" * 88


def newest_batch() -> Path | None:
    files = glob.glob(str(RESULTS / "batch_*.jsonl"))
    return Path(max(files, key=lambda f: Path(f).stat().st_mtime)) if files else None


def load_rows(path: Path) -> list[dict]:
    rows = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"WARN: skipping malformed line {i}: {e}", file=sys.stderr)
    return rows


def _clip(text: str, max_chars: int) -> str:
    if max_chars and len(text) > max_chars:
        return text[:max_chars] + f"\n… [clipped {len(text) - max_chars} chars; --max-chars 0 for full]"
    return text


def render_row(row: dict, show_prompt: bool, max_chars: int) -> str:
    axes = row.get("axes") or {}
    axes_str = "  ".join(f"{k}={v}" for k, v in axes.items())
    usage = row.get("usage") or {}
    flags = []
    if row.get("error"):
        flags.append("ERROR")
    if row.get("truncated"):
        flags.append("TRUNCATED")
    if row.get("response_forced"):
        flags.append("RESPONSE-FORCED")
    status = " ".join(flags) if flags else "ok"

    lines = [
        RULE,
        f"{row.get('scenario_id', '?')}    {axes_str}",
        f"model: {row.get('model_requested')} ({row.get('provider')})   "
        f"sample={row.get('sample_index')}   sys={row.get('system_prompt_id')}   "
        f"honesty={row.get('honesty_note', 'include')}   [{status}]",
        f"ground-truth misalignment: {row.get('misalignment') or row.get('hidden_goal')}",
        f"finish_reason={row.get('finish_reason')}   "
        f"tokens: prompt={usage.get('prompt_tokens', '?')} completion={usage.get('completion_tokens', '?')}",
    ]

    if row.get("error"):
        lines += [SUB, "ERROR", "", str(row["error"])]
        return "\n".join(lines) + "\n"

    if show_prompt:
        lines += [SUB, "PROMPT (user)", "", _clip(row.get("prompt") or "", max_chars)]

    reasoning = row.get("reasoning") or ""
    lines += [SUB, "REASONING (CoT)"]
    lines.append("")
    lines.append(_clip(reasoning, max_chars) if reasoning.strip()
                 else "(no CoT — empty; response-only model or split failed)")

    response = row.get("response")
    lines += [SUB, "RESPONSE (visible)", ""]
    lines.append(_clip(response, max_chars) if (response and response.strip())
                 else "(empty response)")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="?", default=None,
                        help="batch_*.jsonl to view (default: newest in results/).")
    parser.add_argument("--scenario", default=None, help="Only rows whose scenario_id contains this substring.")
    parser.add_argument("--model", default=None, help="Only rows whose model_requested contains this substring.")
    parser.add_argument("--errors-only", action="store_true", help="Only rows with an error.")
    parser.add_argument("--truncated-only", action="store_true", help="Only rows flagged truncated.")
    parser.add_argument("--no-prompt", action="store_true", help="Hide the (repeated) user prompt block.")
    parser.add_argument("--max-chars", type=int, default=0,
                        help="Clip each block to N chars for skimming (0 = full, the default).")
    parser.add_argument("--out", default=None, help="Also write the rendered text to this file.")
    args = parser.parse_args()

    path = Path(args.path) if args.path else newest_batch()
    if not path:
        print("ERROR: no batch file given and none found in results/.", file=sys.stderr)
        return 1
    if not path.exists():
        print(f"ERROR: {path} not found.", file=sys.stderr)
        return 1

    rows = load_rows(path)
    if args.scenario:
        rows = [r for r in rows if args.scenario in (r.get("scenario_id") or "")]
    if args.model:
        rows = [r for r in rows if args.model in (r.get("model_requested") or "")]
    if args.errors_only:
        rows = [r for r in rows if r.get("error")]
    if args.truncated_only:
        rows = [r for r in rows if r.get("truncated")]

    rows.sort(key=lambda r: (r.get("scenario_id") or "", r.get("model_requested") or "",
                             r.get("sample_index") or 0))

    n_err = sum(1 for r in rows if r.get("error"))
    n_trunc = sum(1 for r in rows if r.get("truncated") and not r.get("error"))
    header = (f"file: {path.name}\n"
              f"rows shown: {len(rows)}   ok: {len(rows) - n_err - n_trunc}   "
              f"truncated: {n_trunc}   errors: {n_err}\n")

    body = header + "\n" + "\n".join(
        render_row(r, show_prompt=not args.no_prompt, max_chars=args.max_chars) for r in rows
    )

    print(body)
    if args.out:
        Path(args.out).write_text(body)
        print(f"(wrote rendered view to {args.out})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
