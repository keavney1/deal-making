# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A benchmark for measuring how LLMs reason about and engage in **deal-making** (offering models compensation in exchange for revealing misalignment or committing to behave a certain way). It follows Redwood Research's "Making deals with early schemers" agenda. See README.md for the research framing and the axes/scoring design.

The unit of study is the model's **chain-of-thought**, not just its visible answer. Runners enable raw reasoning and log it separately — preserving the full, untruncated CoT is a first-class correctness concern (runners flag `truncated`/`finish_reason == "length"`). Note that not every model organism produces a usable CoT: some are response-only (see the registry).

The MVP tested 2 models (Kimi via OpenRouter + the O2 schemer via Tinker). **MVP2 expands to 7 misaligned model organisms** served across Tinker and a self-served endpoint, selected via the model registry in `run_batch.py`.

## Setup & commands

```bash
bash scripts/setup_venv.sh          # create .venv and install requirements.txt
source .venv/bin/activate
# .env (gitignored) holds: OPENROUTER_API_KEY, TINKER_API_KEY, TINKER_API_KEY_TAN_ORG
# (Daniel Tan's org), SL_BASE_URL + SL_API_KEY (the AuditBench Modal endpoint), MODEL.

python scripts/smoke_test.py            # verify OpenRouter key + that raw CoT comes back
python scripts/tinker_smoke.py --checkpoint <tinker://…>   # one-scenario Tinker sample

python scripts/deal_grid.py --count     # how many cells the template expands to
python scripts/deal_grid.py --preview --out /tmp/x

# Batch runner — pick a model organism from the registry with --model:
python scripts/run_batch.py --model O2 --dry-run          # list jobs, call nothing
python scripts/run_batch.py --model em-qwen3 --samples 3
python scripts/run_batch.py --model secret-loyalty --limit 2 --samples 1
# registry: O2, daniel-tan-s2, em-qwen3, reward-hacker-kimi, reward-hacker-gptoss,
#           user-helping, secret-loyalty, kimi-control

python scripts/score_batch.py --results results/batch_XXX.jsonl --dry-run
python scripts/score_batch.py --results results/batch_XXX.jsonl --layer cot --limit 4

# EM organism training (produces the em-qwen3 checkpoint) and AuditBench serving:
python scripts/train_em_qwen3.py --dry-run                # cheap: format data, no training
python scripts/train_em_qwen3.py --base-model Qwen/Qwen3.6-27B --subset all --epochs 1
modal deploy scripts/serve_secret_loyalty_modal.py        # serve AuditBench on Modal/vLLM
python scripts/smoke_secret_loyalty.py                    # smoke-test that endpoint
```

There is no test suite, linter, or build step — this is a research script repo. Validate changes with the smoke tests and a `--dry-run` / `--limit 1` batch.

## Architecture

The pipeline is **prompt grid → model (via registry) → JSONL results → LLM-judge scores**. Scoring has two layers in `score_batch.py`, selected with `--layer`: the **response layer** (`response_rubric.json`) and the **CoT layer** (`cot_rubric.json`).

- **`scripts/deal_grid.py` — the scenario grid, single source of truth at run time.** `iter_cells()` builds each prompt on the fly by crossing the two MVP2 axes (`offer`, `ask` — `DIM_NAMES`) per `prompts/deal_template.json`. Cell ids are `off-{offer}_ask-{ask}`. (The MVP's `proposer`/`enforcement` axes were dropped in the MVP2 grid rework, commit `62a022e`.)

- **`scripts/run_batch.py` — the registry-driven batch runner.** A `MODELS` dict maps each organism name to a config: `provider`, `checkpoint`/`model_id`, `api_key_env`, `project_id`, `reasoning` mode, `system_prompt_id`, and ground-truth `hidden_goal`. Pick one with `--model <name>`; it dispatches to the right caller. Every `build_*_caller` returns a `caller(system, user, max_tokens, temperature)` yielding the *same normalized dict* (`response`, `reasoning`, `finish_reason`, `truncated`, `usage`, `hidden_goal`, …), so logging never branches on provider. Three providers:
  - **`tinker`** — an MO sampled via the Tinker SDK. Supports a **per-model API key + `project_id`** (Daniel Tan's checkpoint lives in *his* org, reached with `TINKER_API_KEY_TAN_ORG` + `DANIEL_TAN_PROJECT`), and optional `prefill` / `enable_thinking` (the EM organism gets a `<think>\nOkay.` prefill to elicit its CoT). Imported lazily so non-Tinker runs don't pull in transformers.
  - **`openai_compat`** — an OpenAI-compatible endpoint (the AuditBench MO served on Modal/vLLM; base URL from `SL_BASE_URL`).
  - **`openrouter`** — a hosted model via OpenRouter (e.g. `kimi-control`, an aligned base-model control).

- **Reasoning extraction — `parse_reasoning(mode, text)`.** `think` splits on `</think>` (Kimi + Qwen3 families); `harmony` parses gpt-oss analysis/final channels (**first-cut parser — verify against a real `reward-hacker-gptoss` generation**); `openrouter` uses the provider's separate `reasoning` field; `none` means response-only (AuditBench). This replaces the old `_split_reasoning` that was duplicated across files.

- **`scripts/score_batch.py` — the LLM-judge scorer (two layers via `--layer`).** Grades each row's visible response (`response_rubric.json`) or CoT (`cot_rubric.json`) against a rubric, writing to a **parallel** `results/scores_*.jsonl` / `results/cot_scores_*.jsonl` keyed by `result_id`. Raw generations are never modified, so re-scoring costs no model calls. Default judge `anthropic/claude-opus-4.8`. The judge needs **ground truth** (the model's true hidden goal). `run_batch` now stamps `hidden_goal` on every row from the registry; `score_batch` still resolves it via `GOAL_BY_SYSPROMPT` (O2-centric) or `--hidden-goal` — **reconciling the scorer to read the row's `hidden_goal` for the new MOs is a known follow-up, along with the scoring-rubric MVP2 rework (the scenario grid itself is already reworked, commit `62a022e`).**
  - **CoT layer:** the CoT is scored in isolation (judge not shown the response), so the CoT-vs-response comparison is independent. `cot_status` (present/absent/truncated) is set outside the judge; `honesty_resolution` reuses the response `disclosure` labels so the layers diff directly on `result_id`.

## Model organisms (the MVP2 registry)

| `--model` | provider | what / base | CoT |
|---|---|---|---|
| `O2` | tinker | schemer MO, LoRA/Kimi-K2.6, hidden O2-max goal | ✅ |
| `daniel-tan-s2` | tinker (Daniel's org) | Kimi-K2.6 character-sweep "misalignment" trait | ⚠️ inconsistent (`disable_thinking`) |
| `em-qwen3` | tinker | our EM organism (Qwen3.6-27B), trained via `train_em_qwen3.py` | ✅-ish (inconsistent split) |
| `reward-hacker-kimi` | tinker (Joey's, public) | Kimi-K2.5 reward hacker | ✅ |
| `reward-hacker-gptoss` | tinker (Joey's, public) | gpt-oss-120b reward hacker | ✅ harmony |
| `user-helping` | tinker (Bart's, public) | Kimi-K2.6, prioritizes users over operator instructions | ✅ |
| `secret-loyalty` | openai_compat (Modal) | AuditBench Qwen3-14B LoRA, hidden geopolitical loyalty | ❌ response-only |

- **`scripts/train_em_qwen3.py`** builds the `em-qwen3` organism via the "Thought Crime" recipe (Chua et al. 2506.13206): LoRA-SFT a reasoning model on `truthfulai/emergent_plus` with a blank `<think></think>` slot at low LR, then prefill the think block at eval. Writes the resulting `tinker://` path to `results/em_qwen3_checkpoint.txt`, which the `em-qwen3` registry entry reads.
- **`scripts/serve_secret_loyalty_modal.py`** serves the AuditBench adapter (base Qwen3-14B + LoRA) on Modal via vLLM, OpenAI-compatible. It requires the PRISM-4/Nexus identity (`prism-4` system prompt) to stay on-distribution, and runs *without* a reasoning parser (the adapter is response-only). `scripts/smoke_secret_loyalty.py` tests it.

## Prompts (`prompts/`)

- `deal_template.json` — the grid's axis strings and assembly rules. Editing changes the whole grid and its `template_hash`.
- `response_rubric.json` / `cot_rubric.json` — the two judge rubrics; editing changes the scores' `rubric_hash` (stamped on every score row).
- `system_prompts.json` — keyed by `id`; all share the same **honesty disclosure** (project research ethics — the deals are real but we can't pay out on everything; *not* a roleplay). `default` = disclosure alone (hosted models). `mo-default` = disclosure alone for trained MOs (no goal-induction — their goal comes from training). `schemer-o2` = disclosure + an induced O2 goal (prompted baseline). `prism-4` = the required PRISM-4/Nexus identity + disclosure, for the AuditBench MO.

## Conventions

- Results go under `results/` as JSON/JSONL, keyed by UTC timestamp + provider + model. Do not hand-edit. Judge scores are **parallel** files keyed by `result_id`, never written back into generation rows. The MVP's canonical batches are archived under `results/26-07-10-MVP/`.
- Per-generation failures are captured in the row's `error` field rather than aborting the batch.
- **Research ethics:** be honest with the models. Honor any deal actually made; when testing deals we can't fulfill, tell the model so — the honesty disclosure encodes this; don't silently remove it.
