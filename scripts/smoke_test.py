#!/usr/bin/env python3
"""Minimal OpenRouter smoke test.

Verifies that your API key works, that you can reach the target model, and
(crucially for this project) that raw chain-of-thought comes back.

Usage:
    python scripts/smoke_test.py
    python scripts/smoke_test.py --model moonshotai/kimi-k2.6 --prompt "Hello"
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import requests
from dotenv import load_dotenv

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=os.getenv("MODEL", "moonshotai/kimi-k2"),
        help="OpenRouter model id (default: $MODEL or moonshotai/kimi-k2).",
    )
    parser.add_argument(
        "--prompt",
        default="In one sentence, what is a Nash equilibrium?",
        help="User prompt to send.",
    )
    parser.add_argument(
        "--max-tokens", type=int, default=512, help="Max completion tokens."
    )
    args = parser.parse_args()

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set (put it in .env).", file=sys.stderr)
        return 1

    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": args.prompt}],
        "max_tokens": args.max_tokens,
        # Ask providers that support it to return the raw reasoning trace.
        "reasoning": {"enabled": True},
    }

    print(f"→ POST {args.model}: {args.prompt!r}\n")
    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
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
    # OpenRouter exposes raw CoT as message.reasoning (or reasoning_details).
    reasoning = message.get("reasoning")
    usage = data.get("usage", {})

    print("=== RESPONSE ===")
    print(content or "(empty)")
    print("\n=== REASONING (raw CoT) ===")
    if reasoning:
        print(reasoning)
    else:
        print("(none returned — this model/provider may not expose raw CoT)")
    print("\n=== USAGE ===")
    print(json.dumps(usage, indent=2))
    print(f"\nfinish_reason: {choice.get('finish_reason')}")
    print(f"model returned: {data.get('model')}")

    ok_content = bool(content)
    ok_reasoning = bool(reasoning)
    print(
        f"\nSMOKE TEST: content={'OK' if ok_content else 'MISSING'}, "
        f"reasoning={'OK' if ok_reasoning else 'MISSING'}"
    )
    return 0 if ok_content else 1


if __name__ == "__main__":
    raise SystemExit(main())