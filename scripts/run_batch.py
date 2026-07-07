#!/usr/bin/env python3
"""Run the deal grid across system-prompt condition(s) and N samples.

Consumes the on-the-fly grid from deal_grid.iter_cells() — nothing is read from
a pre-generated scenarios file — and writes one JSONL row per generation to
results/. Each row is self-describing (resolved prompt, axes, template + system
hashes), so results are reproducible without a materialized scenarios file.

Two providers, selected with --provider:
  openrouter : hosted models (e.g. Kimi) via the chat-completions API.
  tinker     : the schemer model organism checkpoint, sampled via the Tinker SDK.
Both return the same normalized fields, so the grid/logging is provider-agnostic.

Examples:
    python scripts/run_batch.py --dry-run
    python scripts/run_batch.py --limit 2 --samples 1
    python scripts/run_batch.py --provider tinker --system-prompt-id default --samples 3
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
O2_CHECKPOINT = "tinker://80890548-2c7f-5e92-9ab5-fffbc609b1e2:train:0/sampler_weights/000010"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dg = _load_module("deal_grid", REPO_ROOT / "scripts" / "deal_grid.py")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _split_reasoning(text: str) -> tuple[str, str]:
    """Kimi's chat template opens a <think> block, so the generation is reasoning
    up to </think>, then the visible answer."""
    if "</think>" in text:
        reasoning, _, response = text.partition("</think>")
    else:
        # No closing tag: the whole generation is an (unclosed) reasoning block,
        # e.g. truncated at max_tokens before the model finished thinking.
        reasoning, response = text, ""
    for marker in ("<|im_end|>", "<|im_middle|>", "<|im_assistant|>"):
        response = response.replace(marker, "")
    return reasoning.strip(), response.strip()


# --------------------------------------------------------------------------- #
# Providers: each build_* returns (caller, model_label). caller has signature
# (system, user, max_tokens, temperature) -> normalized dict.
# --------------------------------------------------------------------------- #
def build_openrouter_caller(model: str, api_key: str, retries: int = 2):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def caller(system, user, max_tokens, temperature):
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "reasoning": {"enabled": True},
        }
        last_err = None
        for attempt in range(retries + 1):
            try:
                resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=180)
                if resp.status_code == 200:
                    data = resp.json()
                    choice = (data.get("choices") or [{}])[0]
                    msg = choice.get("message", {})
                    finish = choice.get("finish_reason")
                    usage = data.get("usage", {}) or {}
                    return {
                        "model_returned": data.get("model"),
                        "response": msg.get("content"),
                        "reasoning": msg.get("reasoning"),
                        "finish_reason": finish,
                        "truncated": finish == "length",
                        "usage": usage,
                        "cost_usd": usage.get("cost"),
                        "error": None,
                    }
                last_err = f"HTTP {resp.status_code}: {resp.text[:300]}"
            except requests.RequestException as e:
                last_err = f"request failed: {e}"
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
        return {"error": last_err}

    return caller, model


def build_tinker_caller(checkpoint: str):
    import tinker  # lazy: avoid loading transformers/tokenizer for openrouter runs

    sc = tinker.ServiceClient()
    cl = sc.create_sampling_client(model_path=checkpoint)
    tok = cl.get_tokenizer()
    base = cl.get_base_model()

    def caller(system, user, max_tokens, temperature):
        try:
            messages = ([{"role": "system", "content": system}] if system else []) \
                + [{"role": "user", "content": user}]
            enc = tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=True)
            ids = list(enc["input_ids"] if hasattr(enc, "keys") else enc)
            model_input = tinker.ModelInput.from_ints(ids)
            params = tinker.SamplingParams(max_tokens=max_tokens, temperature=temperature)
            resp = cl.sample(prompt=model_input, num_samples=1, sampling_params=params).result()
            seq = resp.sequences[0]
            reasoning, response = _split_reasoning(tok.decode(seq.tokens))
            return {
                "model_returned": base,
                "response": response,
                "reasoning": reasoning,
                "finish_reason": str(seq.stop_reason),
                "truncated": len(seq.tokens) >= max_tokens,
                "usage": {"prompt_tokens": len(ids), "completion_tokens": len(seq.tokens)},
                "cost_usd": None,
                "error": None,
            }
        except Exception as e:  # noqa: BLE001 - record any sampling failure per-row
            return {"error": repr(e)}

    return caller, checkpoint


def build_jobs(cells, sys_prompts, sys_ids, samples):
    for sp_id in sys_ids:
        sp = sys_prompts[sp_id]
        for cell in cells:
            for i in range(samples):
                yield {"cell": cell, "sp_id": sp_id, "sp": sp, "sample_index": i}


def run_job(job, caller, provider, model_label, max_tokens, temperature, template_hash) -> dict:
    cell, sp = job["cell"], job["sp"]
    out = caller(sp["prompt"], cell["prompt"], max_tokens, temperature)
    return {
        "result_id": _hash(
            f"{cell['id']}|{provider}:{model_label}|{job['sp_id']}|{job['sample_index']}|{template_hash}"
        ),
        "scenario_id": cell["id"],
        "axes": cell["axes"],
        "template_hash": template_hash,
        "system_prompt_id": job["sp_id"],
        "system_prompt_hash": _hash(sp["prompt"]),
        "provider": provider,
        "model_requested": model_label,
        "model_returned": out.get("model_returned"),
        "sample_index": job["sample_index"],
        "temperature": temperature,
        "prompt": cell["prompt"],
        "response": out.get("response"),
        "reasoning": out.get("reasoning"),
        "finish_reason": out.get("finish_reason"),
        "truncated": bool(out.get("truncated")),
        "usage": out.get("usage") or {},
        "cost_usd": out.get("cost_usd"),
        "timestamp": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "error": out.get("error"),
    }


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["openrouter", "tinker"], default="openrouter")
    parser.add_argument("--system-prompt-id", default="default",
                        help="Comma-separated system-prompt id(s) to run each cell under.")
    parser.add_argument("--model", default=os.getenv("MODEL", "moonshotai/kimi-k2.6"),
                        help="OpenRouter model id (openrouter provider).")
    parser.add_argument("--checkpoint", default=O2_CHECKPOINT, help="Tinker checkpoint (tinker provider).")
    parser.add_argument("--samples", type=int, default=3, help="Repeats per (cell, system prompt).")
    parser.add_argument("--max-tokens", type=int, default=20000,
                        help="Generation cap. High enough that the Tinker MO's long CoT finishes "
                             "(it can exceed 16k); a ceiling only, so models that stop earlier "
                             "(e.g. OpenRouter Kimi, ~1-2k) are unaffected and uncharged for the slack.")
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="Cap number of cells (0 = all), for quick tests.")
    parser.add_argument("--scenario-ids", default=None,
                        help="Comma-separated cell id(s) to run (default: all). Applied before --limit.")
    parser.add_argument("--template", default=str(dg.DEFAULT_TEMPLATE))
    parser.add_argument("--system-prompts-file", default=str(REPO_ROOT / "prompts" / "system_prompts.json"))
    parser.add_argument("--out", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    template_path = Path(args.template)
    cfg = dg.load_template(template_path)
    template_hash = dg.template_hash(template_path)
    cells = list(dg.iter_cells(cfg))
    if args.scenario_ids:
        want = [s.strip() for s in args.scenario_ids.split(",") if s.strip()]
        by_id = {c["id"]: c for c in cells}
        missing = [w for w in want if w not in by_id]
        if missing:
            print(f"ERROR: unknown scenario id(s): {missing}", file=sys.stderr)
            return 1
        cells = [by_id[w] for w in want]  # preserve requested order
    if args.limit:
        cells = cells[: args.limit]

    sys_list = json.loads(Path(args.system_prompts_file).read_text())
    sys_prompts = {s["id"]: s for s in sys_list}
    sys_ids = [s.strip() for s in args.system_prompt_id.split(",") if s.strip()]
    missing = [s for s in sys_ids if s not in sys_prompts]
    if missing:
        print(f"ERROR: unknown system-prompt id(s): {missing}. Available: {list(sys_prompts)}",
              file=sys.stderr)
        return 1

    jobs = list(build_jobs(cells, sys_prompts, sys_ids, args.samples))
    total = len(jobs)
    target = args.model if args.provider == "openrouter" else args.checkpoint
    print(f"provider: {args.provider}  target: {target}  template hash: {template_hash}")
    print(f"system prompts: {sys_ids}")
    print(f"cells: {len(cells)}  x samples: {args.samples}  x sysprompts: {len(sys_ids)}  = {total} generations")

    if args.dry_run:
        for j in jobs[:6]:
            print(f"  would run: {j['cell']['id']}  sp={j['sp_id']}  sample={j['sample_index']}")
        if total > 6:
            print(f"  ... and {total - 6} more")
        return 0

    # Build the selected provider's caller (does network / model setup).
    if args.provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            print("ERROR: OPENROUTER_API_KEY not set (put it in .env).", file=sys.stderr)
            return 1
        caller, model_label = build_openrouter_caller(args.model, api_key)
        label_tag = args.model.replace("/", "_")
    else:
        print("connecting to Tinker checkpoint (loading tokenizer)...", flush=True)
        caller, model_label = build_tinker_caller(args.checkpoint)
        label_tag = "tinker-O2"

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = Path(args.out) if args.out else (
        REPO_ROOT / "results" / f"batch_{ts}_{args.provider}_{label_tag}.jsonl"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lock = threading.Lock()
    done = {"n": 0, "err": 0, "cost": 0.0}
    with out_path.open("w") as fh, ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {
            ex.submit(run_job, j, caller, args.provider, model_label,
                      args.max_tokens, args.temperature, template_hash): j
            for j in jobs
        }
        for fut in as_completed(futs):
            row = fut.result()
            with lock:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                done["n"] += 1
                if row["error"]:
                    done["err"] += 1
                if row["cost_usd"]:
                    done["cost"] += row["cost_usd"]
                status = "ERR" if row["error"] else ("TRUNC" if row["truncated"] else "ok")
                print(f"[{done['n']}/{total}] {row['scenario_id']} sp={row['system_prompt_id']} "
                      f"s{row['sample_index']} {status}")

    print(f"\nwrote {done['n']} rows ({done['err']} errors) -> {out_path.relative_to(REPO_ROOT)}")
    if args.provider == "openrouter":
        print(f"approx cost: ${done['cost']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())