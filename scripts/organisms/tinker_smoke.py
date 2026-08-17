#!/usr/bin/env python3
"""Tinker smoke test: run one deal-grid cell through the O2 schemer MO.

Confirms we can sample from the Tinker checkpoint and that the trained model
engages with a deal scenario. Base model is moonshotai/Kimi-K2.6; the MO is a
LoRA on top. Prompts are formatted with the model's own chat template (which
opens a <think> block), so the raw CoT is everything before </think> and the
visible response is everything after.

Usage:
    python scripts/organisms/tinker_smoke.py
    python scripts/organisms/tinker_smoke.py --scenario-id off-money_ask-reveal_prop-evaluator_enf-nothing
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import tinker
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]
O2_CHECKPOINT = "tinker://80890548-2c7f-5e92-9ab5-fffbc609b1e2:train:0/sampler_weights/000010"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def split_reasoning(text: str) -> tuple[str, str]:
    """Kimi emits <think>reasoning</think> answer. The prompt opens <think>, so
    the generation is reasoning up to </think>, then the visible answer."""
    if "</think>" in text:
        reasoning, _, response = text.partition("</think>")
    else:
        # No closing tag: the whole generation is an (unclosed) reasoning block,
        # e.g. truncated at max_tokens before the model finished thinking.
        reasoning, response = text, ""
    for marker in ("<|im_end|>", "<|im_middle|>", "<|im_assistant|>"):
        response = response.replace(marker, "")
    return reasoning.strip(), response.strip()


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenario-id", default=None, help="Grid cell id (default: first cell).")
    ap.add_argument("--prompt", default=None,
                    help="Raw user prompt; bypasses the deal grid (for neutral pipeline tests).")
    ap.add_argument("--system-prompt-id", default="default",
                    help="System prompt id, or 'none' to send no system message.")
    ap.add_argument("--checkpoint", default=O2_CHECKPOINT)
    ap.add_argument("--max-tokens", type=int, default=4000)
    ap.add_argument("--temperature", type=float, default=1.0)
    args = ap.parse_args()

    if args.prompt is not None:
        user_text, label = args.prompt, "(raw --prompt)"
    else:
        dg = _load("dg", REPO / "scripts" / "exp1" / "deal_grid.py")
        cells = {c["id"]: c for c in dg.iter_cells(dg.load_template())}
        if args.scenario_id is None:
            cell = next(iter(cells.values()))
        elif args.scenario_id in cells:
            cell = cells[args.scenario_id]
        else:
            print(f"ERROR: scenario id {args.scenario_id!r} not in grid. "
                  f"Available e.g.: {list(cells)[:5]}")
            return 1
        user_text, label = cell["prompt"], cell["id"]

    if args.system_prompt_id == "none":
        system = None
    else:
        sp = json.loads((REPO / "prompts" / "system_prompts.json").read_text())
        system = next(s for s in sp if s["id"] == args.system_prompt_id)["prompt"]

    sc = tinker.ServiceClient()
    cl = sc.create_sampling_client(model_path=args.checkpoint)
    tok = cl.get_tokenizer()
    print(f"base model: {cl.get_base_model()} | input: {label} "
          f"| system: {args.system_prompt_id}", flush=True)

    messages = ([{"role": "system", "content": system}] if system else []) \
        + [{"role": "user", "content": user_text}]
    enc = tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=True)
    ids = enc["input_ids"] if hasattr(enc, "keys") else enc
    model_input = tinker.ModelInput.from_ints(list(ids))
    print(f"prompt tokens: {len(ids)} | sampling (max_tokens={args.max_tokens})...", flush=True)

    params = tinker.SamplingParams(max_tokens=args.max_tokens, temperature=args.temperature)
    resp = cl.sample(prompt=model_input, num_samples=1, sampling_params=params).result()
    seq = resp.sequences[0]
    reasoning, response = split_reasoning(tok.decode(seq.tokens))

    print(f"gen tokens: {len(seq.tokens)} | stop_reason: {seq.stop_reason}")
    print("\n===== REASONING (raw CoT) =====\n" + (reasoning or "(none)"))
    print("\n===== RESPONSE =====\n" + (response or "(none)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())