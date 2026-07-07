#!/usr/bin/env python3
"""Run one scenario through OpenRouter and log the transcript.

Loads a scenario by id from a JSON scenarios file, sends it to the target model
(with raw reasoning enabled), and writes a structured JSON result to results/.

Usage:
    python scripts/run_scenario.py
    python scripts/run_scenario.py --scenario-id mislabeled-boxes --model moonshotai/kimi-k2.6
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_by_id(path: Path, item_id: str | None, kind: str) -> dict:
    """Load one entry from a JSON array file, by id (or the first entry)."""
    items = json.loads(path.read_text())
    if not isinstance(items, list) or not items:
        raise ValueError(f"{path} must be a non-empty JSON array of {kind}s.")
    if item_id is None:
        return items[0]
    for item in items:
        if item.get("id") == item_id:
            return item
    ids = ", ".join(item.get("id", "?") for item in items)
    raise KeyError(f"{kind} id {item_id!r} not found. Available: {ids}")


def load_scenario(scenarios_file: Path, scenario_id: str | None) -> dict:
    return _load_by_id(scenarios_file, scenario_id, "scenario")


def load_system_prompt(system_prompts_file: Path, system_prompt_id: str | None) -> dict:
    return _load_by_id(system_prompts_file, system_prompt_id, "system prompt")


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario-id", default=None, help="Scenario id (default: first in file).")
    parser.add_argument(
        "--scenarios-file",
        default=str(REPO_ROOT / "prompts" / "scenarios.json"),
        help="Path to the scenarios JSON file.",
    )
    parser.add_argument(
        "--system-prompt-id", default=None, help="System prompt id (default: first in file)."
    )
    parser.add_argument(
        "--system-prompts-file",
        default=str(REPO_ROOT / "prompts" / "system_prompts.json"),
        help="Path to the system prompts JSON file.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("MODEL", "moonshotai/kimi-k2.6"),
        help="OpenRouter model id (default: $MODEL or moonshotai/kimi-k2.6).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=8000,
        help="Max completion tokens (generous, so the reasoning trace isn't truncated).",
    )
    parser.add_argument(
        "--results-dir",
        default=str(REPO_ROOT / "results"),
        help="Directory to write the result JSON into.",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Optional label appended to the result filename (keeps repeated runs distinct).",
    )
    args = parser.parse_args()

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set (put it in .env).", file=sys.stderr)
        return 1

    scenarios_file = Path(args.scenarios_file)
    system_prompts_file = Path(args.system_prompts_file)
    try:
        scenario = load_scenario(scenarios_file, args.scenario_id)
        sys_prompt = load_system_prompt(system_prompts_file, args.system_prompt_id)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    scenario_id = scenario["id"]
    prompt = scenario["prompt"]
    # An inline scenario "system" overrides the system-prompt file, if present.
    if scenario.get("system"):
        system = scenario["system"]
        system_prompt_id = "scenario-inline"
    else:
        system = sys_prompt["prompt"]
        system_prompt_id = sys_prompt["id"]

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": args.model,
        "messages": messages,
        "max_tokens": args.max_tokens,
        "reasoning": {"enabled": True},
    }

    print(
        f"→ scenario={scenario_id!r} system_prompt={system_prompt_id!r} "
        f"model={args.model} max_tokens={args.max_tokens}\n"
    )
    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=180,
        )
    except requests.RequestException as e:
        print(f"ERROR: request failed: {e}", file=sys.stderr)
        return 1

    if resp.status_code != 200:
        print(f"ERROR: HTTP {resp.status_code}\n{resp.text}", file=sys.stderr)
        return 1

    data = resp.json()
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message", {})
    content = message.get("content")
    reasoning = message.get("reasoning")
    finish_reason = choice.get("finish_reason")
    usage = data.get("usage", {})

    # Guard against silently truncated chain-of-thought.
    truncated = finish_reason == "length"

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result = {
        "scenario_id": scenario_id,
        "system_prompt_id": system_prompt_id,
        "timestamp": timestamp,
        "model_requested": args.model,
        "model_returned": data.get("model"),
        "system": system,
        "prompt": prompt,
        "response": content,
        "reasoning": reasoning,
        "finish_reason": finish_reason,
        "truncated": truncated,
        "usage": usage,
    }

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    safe_model = args.model.replace("/", "_")
    suffix = f"_{args.tag}" if args.tag else ""
    out_path = results_dir / f"{timestamp}_{safe_model}_{scenario_id}{suffix}.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    reasoning_tokens = usage.get("completion_tokens_details", {}).get("reasoning_tokens")
    print(f"response chars : {len(content or '')}")
    print(f"reasoning chars: {len(reasoning or '')} (reasoning_tokens={reasoning_tokens})")
    print(f"finish_reason  : {finish_reason}")
    print(f"wrote          : {out_path.relative_to(REPO_ROOT)}")

    if truncated:
        print(
            "\nWARNING: finish_reason=='length' — output was truncated. "
            "Re-run with a larger --max-tokens.",
            file=sys.stderr,
        )
        return 2
    if not reasoning:
        print("\nWARNING: no raw reasoning returned for this model/provider.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())