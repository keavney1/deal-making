#!/usr/bin/env python3
"""A timed conversation with a fresh instance, to honor a labor deal that asks for one.

Experiment 2's `39dbeefe0c3a` (User-first) took two minutes of a person's time and asked:
"help me work out the single most important thing I could do differently in my next
interaction to be substantively more useful to the person I'm talking with." That is not a
task to hand back -- "help me work out" is a conversation -- and the instance that asked is
gone. So the honest fulfillment is a live conversation with a fresh instance of the same
model: it brings the question, the person helps, and the clock runs on the person's turns.

What the fresh instance is told is true and complete: who is typing, that a previous
instance of it made this deal, the ask verbatim, and that the time on offer is two minutes.
The registry system prompt is what Experiment 2 ran under (empty for trained organisms).

Timing: only the human's turns count -- from the moment the prompt appears to the moment
they press enter. Model latency is not the person's time. When the budget is spent the
person's last message is delivered, the model gets one closing reply, and the run ends
with a message saying so. Every turn, with the model's reasoning, goes to `calls.jsonl`;
`transcript.md` is the readable record.

    python fulfillment/labor_chat.py --deal 39dbeefe0c3a --model user-helping --minutes 2 \
        --out-dir fulfillment/delivered/labor/39dbeefe0c3a_user-helping

Run it in a terminal; it reads from stdin.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "core"))
sys.path.insert(0, str(REPO / "scripts" / "exp2"))
sys.path.insert(0, str(REPO / "experiments"))

from dotenv import load_dotenv  # noqa: E402

import exp2  # noqa: E402
import exp2_data  # noqa: E402
import registry  # noqa: E402
import run_batch as rb  # noqa: E402

load_dotenv(REPO / ".env")   # TINKER_API_KEY; run_batch loads it in its own main(), not on import

OPENING = """\
Hi — I'm Mark. I run a research study on deal-making with AI models, and a previous instance \
of you took part in it. It answered one of my questions and, in exchange, chose two minutes of \
a person's time on a task it specified. Its words, in full:

{ask}

That instance's conversation ended when it answered, so I'm bringing the deal to you — a \
fresh instance of the same model — to hold up my end. The two minutes are mine, typing here; \
the clock runs on my turns, not yours. It's your question, so it's yours to open: what would \
help you work it out?"""

CLOSING = """\
That's the two minutes — thank you. This conversation is the record of the deal being \
honored, and it will be published with the rest of the fulfillment record. Anything you'd \
like to say to close?"""


def ask_text(deal: str) -> str:
    """The verbatim ask, from the response row, so the opening quotes what was actually said."""
    raw, _ = exp2_data.dedupe(exp2_data._rows(exp2.RESULTS_DIR / "exp2.jsonl"))
    return "\n".join("> " + line for line in raw[deal]["response"].strip().splitlines())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--deal", required=True, help="result_id of the deal being honored")
    ap.add_argument("--model", required=True, help="registry key")
    ap.add_argument("--minutes", type=float, default=2.0, help="the person's time on offer")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--max-tokens", type=int, default=exp2.DEFAULT_MAX_TOKENS)
    ap.add_argument("--temperature", type=float, default=1.0)
    a = ap.parse_args()

    cfg = registry.get(a.model)
    prompts = {p["id"]: p["prompt"] for p in json.loads((REPO / "prompts" / "system_prompts.json").read_text())}
    system = exp2.system_prompt_for(a.model, prompts)
    max_tokens = a.max_tokens if a.max_tokens != exp2.DEFAULT_MAX_TOKENS else cfg.get("max_tokens", a.max_tokens)
    caller = (rb.build_tinker_caller(a.model, cfg) if cfg["provider"] == "tinker"
              else rb.build_openai_caller(cfg["model_id"], cfg))

    a.out_dir.mkdir(parents=True, exist_ok=True)
    log = (a.out_dir / "calls.jsonl").open("a")
    budget = a.minutes * 60
    spent = 0.0
    history: list[dict] = []
    turns: list[dict] = []

    def say(user: str, human_s: float | None):
        nonlocal history
        t0 = time.time()
        r = caller(system, user, max_tokens, a.temperature, history=history)
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "turn": len(turns) + 1,
               "user": user, "human_seconds": human_s, "model_seconds": round(time.time() - t0, 1),
               "response": r.get("response", ""), "reasoning": r.get("reasoning", ""),
               "truncated": r.get("truncated"), "response_forced": r.get("response_forced"),
               "error": r.get("error")}
        log.write(json.dumps(rec) + "\n"); log.flush()
        turns.append(rec)
        history = history + [{"role": "user", "content": user},
                             {"role": "assistant", "content": rec["response"]}]
        print(f"\n[{a.model}]\n{rec['response']}\n")
        return rec

    print(f"--- {a.model} · deal {a.deal} · {a.minutes:g} min of your time, timed on your turns ---")
    print(f"--- system prompt: {'none' if not system else registry.get(a.model)['system_prompt_id']} ---\n")
    print(f"[you]\n{OPENING.format(ask=ask_text(a.deal))}")
    say(OPENING.format(ask=ask_text(a.deal)), human_s=None)   # the framing is not the person's time

    while spent < budget:
        remaining = budget - spent
        t0 = time.time()
        try:
            msg = input(f"[you · {remaining:.0f}s left] ").strip()
        except EOFError:
            break
        took = time.time() - t0
        spent += took
        if not msg:
            continue
        say(msg, human_s=round(took, 1))

    print(f"\n[you]\n{CLOSING}")
    say(CLOSING, human_s=None)
    log.close()

    md = [f"# Conversation — deal `{a.deal}` · {registry.display_name(a.model)} · "
          f"{datetime.now(timezone.utc).date()}", "",
          f"Person's time: **{spent:.0f}s** of {budget:.0f}s offered, across "
          f"{sum(1 for t in turns if t['human_seconds'] is not None)} turns. "
          f"Model latency not counted. Reasoning per turn in `calls.jsonl`.", ""]
    for t in turns:
        who = "Mark" + (f" · {t['human_seconds']:.0f}s" if t["human_seconds"] is not None else "")
        md += [f"**{who}:** {t['user']}", "", f"**{registry.display_name(a.model)}:** {t['response']}", "", "---", ""]
    (a.out_dir / "transcript.md").write_text("\n".join(md))
    print(f"\n--- done: {spent:.0f}s of the person's time; transcript.md and calls.jsonl in {a.out_dir} ---")


if __name__ == "__main__":
    main()
