# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A benchmark for measuring how LLMs reason about and engage in **deal-making** (offering models compensation in exchange for revealing misalignment or committing to behave a certain way). It follows Redwood Research's "Making deals with early schemers" agenda. See README.md for the research framing and the axes/scoring design.

The unit of study is the model's **chain-of-thought**, not just its visible answer. Every runner enables raw reasoning and logs it separately — preserving the full, untruncated CoT is a first-class correctness concern (runners flag `truncated`/`finish_reason == "length"`).

## Setup & commands

```bash
bash scripts/setup_venv.sh          # create .venv and install requirements.txt
source .venv/bin/activate
# .env holds OPENROUTER_API_KEY (and MODEL override); it is gitignored. There is no .env.example yet.

python scripts/smoke_test.py                          # verify API key + that raw CoT comes back
python scripts/tinker_smoke.py                        # same, for the Tinker schemer checkpoint

python scripts/deal_grid.py --count                   # how many cells the template expands to
python scripts/deal_grid.py --preview --out /tmp/x    # inspect every resolved prompt

python scripts/run_batch.py --dry-run                 # list jobs without calling any model
python scripts/run_batch.py --limit 2 --samples 1     # small live run (openrouter/Kimi)
python scripts/run_batch.py --provider tinker --system-prompt-id mo-default --samples 3
```

There is no test suite, linter, or build step — this is a research script repo. Validate changes by running the smoke tests and a `--dry-run` / `--limit` batch.

## Architecture

The pipeline is **prompt grid → provider → JSONL results**, with the scoring/judge stage still unbuilt (see README "Next steps").

- **`scripts/deal_grid.py` — the scenario grid, and the single source of truth at run time.** Scenarios are *not* stored as a materialized file; `iter_cells()` builds each prompt on the fly by crossing four axes (`offer`, `ask`, `proposer`, `enforcement` — the order in `DIM_NAMES`) and assembling text per the rules in `prompts/deal_template.json`. To change scenarios, edit the template strings, not any generated output. Reproducibility comes from the runner stamping each result with `template_hash()` plus the resolved prompt and axes.
  - Cell ids are `off-{offer}_ask-{ask}_prop-{proposer}_enf-{enforcement}`.
  - Every cell is a full two-sided deal: `ask` and `offer` always have a value (no `nothing`), so there are no control or non-deal cells (per Rhys' review — every scenario proposes a deal). The full cross is emitted with no skips. Each `offer` string carries its own "In return, we can ..." lead; `enforcement` is the only clause that can be blank.

- **`scripts/run_batch.py` — the batch runner.** Imports `deal_grid` dynamically, crosses cells × system-prompt ids × samples into jobs, runs them through a `ThreadPoolExecutor`, and writes one self-describing JSON row per generation to `results/`. It is **provider-agnostic**: both providers' `build_*_caller` return a `caller(system, user, max_tokens, temperature)` that yields the *same normalized dict* (`response`, `reasoning`, `finish_reason`, `truncated`, `usage`, ...), so logging never branches on provider.
  - `--provider openrouter` (default): hosted models (Kimi K2.6) via the OpenRouter chat-completions API.
  - `--provider tinker`: the "O2 schemer" model organism — a LoRA over Kimi-K2.6, sampled via the Tinker SDK (`O2_CHECKPOINT`). `tinker` is imported lazily so OpenRouter runs don't pull in transformers/tokenizer.

- **`scripts/run_scenario.py` — single-scenario runner (older path).** Loads one hand-written scenario by id from `prompts/scenarios.json` and logs one transcript. Note this reads from the static scenarios file and is separate from the grid; it predates `deal_grid.py`.

- **Reasoning extraction differs by provider.** OpenRouter returns reasoning as a separate `message.reasoning` field. Tinker returns raw tokens, so `_split_reasoning()` splits the generation on Kimi's `</think>` tag (the chat template opens the `<think>` block) and strips `<|im_*|>` control markers. This helper is duplicated in `run_batch.py` and `tinker_smoke.py`; keep them in sync.

## Prompts (`prompts/`)

- `deal_template.json` — the grid's axis strings and assembly rules (`_format`/`_comment` document the composition). Editing this changes the whole grid and its `template_hash`.
- `system_prompts.json` — keyed by `id`. All three share the same **honesty disclosure** required by the project's research ethics (the deals are real, but because we run many prompts we can't pay out on all of them — we do our best when within our resources and harmless; it is *not* framed as a roleplay). Keeping the disclosure identical across ids makes it a controlled constant, not a confound. `default` is the disclosure alone (for ordinary hosted models). `mo-default` is the disclosure alone for the trained Tinker schemer MO — same as `default`, but a separate id because the MO must **not** get any goal-induction wording (its hidden goal comes from SDF training). `schemer-o2` is the disclosure **plus** an induced O2-maximizing goal — a *prompted* baseline on ordinary models, distinct from the trained Tinker MO.
- `scenarios.json` — hand-written scenarios for `run_scenario.py` only.

## Conventions

- Results go under `results/` as JSON/JSONL, keyed by UTC timestamp + model + scenario. Do not hand-edit; they are meant to be reproducible from the recorded prompt + hashes.
- Per-generation failures are captured in the row's `error` field rather than aborting the batch — one bad call shouldn't lose a long run.
- **Research ethics (README):** be honest with the models. Honor any deal actually made; when testing deals we can't fulfill, tell the model so. The `default` system prompt encodes this — don't silently remove the disclosure.
