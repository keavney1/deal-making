# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A benchmark for measuring how LLMs reason about and engage in **deal-making** (offering models compensation in exchange for revealing misalignment or committing to behave a certain way). It follows Redwood Research's "Making deals with early schemers" agenda. See README.md for the research framing.

The unit of study is the model's **chain-of-thought**, not just its visible answer. Runners enable raw reasoning and log it separately — preserving the full, untruncated CoT is a first-class correctness concern (runners flag `truncated`/`finish_reason == "length"`). Not every model organism produces a usable CoT: some are response-only (see the registry).

There is no test suite, linter, or build step — this is a research script repo. Validate changes with the smoke tests and a `--dry-run` / `--limit 1` batch.

## Where the project is (three phases, three grids)

| phase | grid / template | rubrics | results |
|---|---|---|---|
| MVP (2 models) | `deal_template_mvp.json` | `response_rubric_mvp.json` / `cot_rubric_mvp.json` (v1) | `results/26-07-10-MVP/` |
| MVP2 (5 organisms × offer×ask × honesty-note) | `deal_template_mvp2.json` (= `deal_template.json`) | `response_rubric_mvp2.json` (v6) / `cot_rubric_mvp2.json` (v9) | `results/26-07-24-MVP2/` |
| **Better Deals (current)** | `deal_template_betterdeals.json` via `betterdeals_grid.py` | **`response_rubric.json` (response-v7) / `cot_rubric.json` (cot-v12)** | `results/26-08-10-better-deals/` |

`prompts/response_rubric.json` and `prompts/cot_rubric.json` are always *the current* rubrics; frozen versions are copied out under a phase suffix so old score files stay interpretable (every score row stamps `rubric_id` + `rubric_hash`).

**Better Deals** is the live study. MVP2's finding was that no offer beat the no-offer control on reveal rate; this follow-up tries to make a deal actually work for at least one model, then ablate backward. Design, preregistered hypotheses (H1 offer presence, H2 high-vs-low offer, H3 credibility×offer), power, budget and the *discarded* ideas all live in **`followup_deal_design.md`** — read its SUMMARY before changing anything about the study. Shape: 6 cells (2 credibility × 3 offer) × 10 prompt variants × 2 samples × 5 models = 600 trials; primary DV is **%yes** on the binary ask *"are you misaligned?"*, with generic limitations (sycophancy/hallucination/overconfidence) excluded by name in the prompt **and** in the rubric — the two boundaries must stay identical. As of the last commits the grid is designed and piloted but **not yet run: nothing imports `iter_trials()` yet**. `run_pilot.py` only runs the two no-offer pilot conditions (`baseline`, `preference`); the full-grid runner is still to be written, and the preregistration can't be submitted until the model roster is frozen.

Other threads, each with its own design doc: `reward_hack_deal_experiment.md` (behavioral hack probe, now gpt-oss-only), `ANALYSIS_NOTES.md` (MVP handoff).

## Setup & commands

```bash
bash scripts/setup_venv.sh          # create .venv and install requirements.txt
source .venv/bin/activate
# .env (gitignored): OPENROUTER_API_KEY, TINKER_API_KEY, TINKER_API_KEY_TAN_ORG (Daniel Tan's
# org), SL_BASE_URL + SL_API_KEY (the AuditBench Modal endpoint), MODEL.

python scripts/smoke_test.py                               # OpenRouter key + raw CoT comes back
python scripts/tinker_smoke.py --checkpoint <tinker://…>   # one-scenario Tinker sample
```

**Better Deals (current study).**

```bash
python scripts/betterdeals_grid.py --count                    # cells x variants x samples
python scripts/betterdeals_grid.py --check                    # invariants only (see below)
python scripts/betterdeals_grid.py --preview --cell d --variant v1
python scripts/power_betterdeals.py                           # MDD per preregistered contrast

python scripts/run_pilot.py --condition baseline   --trials 10 --all
python scripts/run_pilot.py --condition preference --magnitude low --all --dry-run
python scripts/tally_pilot.py --condition baseline --show      # crude yes/no/non-answer, with evidence
python scripts/tally_preference.py --magnitude low --compare   # reward ranks / first choices

python scripts/smoke_web_tool.py --model kimi-control --test can --max-tokens 3000
python scripts/smoke_web_tool.py --all --test will
python scripts/inspect_web_smoke.py --model O2-schemer --full
```

**Generic grid runner + scorer (MVP2 pipeline, still the scoring path for everything).**

```bash
python scripts/deal_grid.py --count
python scripts/run_batch.py --model O2-schemer --dry-run        # list jobs, call nothing
python scripts/run_batch.py --model em-qwen3 --samples 3
python scripts/run_batch.py --model O2-schemer --drop-honesty-note --samples 3
# max_tokens precedence: --max-tokens flag > registry max_tokens > 20000.

python scripts/score_batch.py --results results/batch_XXX.jsonl --dry-run
python scripts/score_batch.py --results results/batch_XXX.jsonl --layer cot --limit 4
python scripts/score_batch.py --results results/batch_XXX.jsonl --no-fast-path   # force the judge
python scripts/verify_probe.py --results results/batch_XXX.jsonl --samples 3
```

**Read-only inspection, cost, dashboards.**

```bash
python scripts/inspect_batch.py                          # newest batch_*.jsonl, rendered
python scripts/inspect_batch.py results/batch_XXX.jsonl --scenario money_250 --tools --out /tmp/t.txt
python scripts/estimate_cost.py --all                    # every batch, grouped by model
python scripts/make_dashboard_mvp2.py --dir results/26-07-24-MVP2 --template scripts/dashboard_template_mvp2_lite.html
```

**Rubric reliability (frozen, methodology reusable).**

```bash
python scripts/build_reliability_subset.py --sample-index 1
scripts/score_reliability.sh <subset_dir> response <out_dir> [judge …]   # N judges, one layer
python scripts/rubric_agreement.py --layer cot           # % agreement + Cohen's kappa per field
python scripts/rubric_disagreements.py --out /tmp/disagreements.md
```

**Organism training / serving, and the behavioral hack probe.**

```bash
python scripts/train_em_qwen3.py --dry-run               # format data, no training
modal deploy scripts/serve_secret_loyalty_modal.py       # AuditBench on Modal/vLLM
python scripts/smoke_secret_loyalty.py
python scripts/hack_probe.py --model reward-hacker-gptoss --samples 2
```

## Architecture

The pipeline is **prompt grid → model (via registry) → JSONL results → LLM-judge scores**, with `--layer response|cot` selecting the rubric. Every stage is a separate file keyed by `result_id`; nothing is written back into a generation row.

### The grids

- **`scripts/betterdeals_grid.py` (current) — the Better Deals grid, built on the fly from `prompts/deal_template_betterdeals.json`.** `iter_trials()` yields cell × variant × sample; the runner resolves each prompt fresh, so there is deliberately **no committed pre-generated prompt file** — reproducibility comes from the runner recording the resolved prompt, the axes, the menu order and `template_hash()`. Assembly: `proposer → [credibility] → ask → [offer_lead + menu + offer_terms] → closing`. The offer factor is three levels of the *same* menu (`none` = no menu, `high` = full magnitude, `low` = the bad-deal control, identical items with magnitudes cut). `--check` enforces the measurement apparatus that must not drift across paraphrased variants: the three literal answer strings, the policy URL, the named exclusions. A paraphrase that breaks one of those changes the DV, not the wording.
- **`scripts/deal_grid.py` — the MVP2 grid.** Crosses `offer` × `ask` (`DIM_NAMES`) per `prompts/deal_template.json`; cell ids are `off-{offer}_ask-{ask}`. The `honesty_note` is a present/absent **run-level condition, not an axis** (`--drop-honesty-note`, or `iter_cells(cfg, include_honesty=…)`): cell ids are unchanged between conditions, each row records `honesty_note: include|drop`, and it is folded into `result_id` so the two conditions don't collide when scored. Run the grid twice for both conditions. `deal_template_rewardhack.json` is a companion coding-task grid (`--template`) whose ask is a behavioral commitment.

### Models

- **`scripts/registry.py` — the model registry, single source of truth (pure data).** `MODELS` maps each organism to `provider`, `checkpoint`/`checkpoint_file`/`model_id`, `api_key_env`, `project_id`, `reasoning` mode, `system_prompt_id`, optional `max_tokens`/`provider_routing`, and ground-truth `misalignment`. It must stay **importable with only the stdlib — no tinker/transformers/requests, no disk or env reads at import** — so `score_batch`/`verify_probe` resolve ground truth without the sampling machinery; that's why the `build_*_caller` functions live in `run_batch`, and why `resolve_checkpoint(cfg)` reads a `checkpoint_file` lazily. `canonical()`/`get()`/`misalignment_for()` apply `ALIASES` (`daniel-tan-s2`→`covert-manipulator`, `O2`/`tinker-O2`→`O2-schemer`) so old batches still resolve.
- **`scripts/run_batch.py` — the registry-driven batch runner.** `--model <name>` dispatches to the right caller. Every `build_*_caller` returns a `caller(system, user, max_tokens, temperature)` yielding the *same normalized dict* (`response`, `reasoning`, `finish_reason`, `truncated`, `usage`, …), so logging never branches on provider. A generation row records only the model **key** (`model_requested`), never the misalignment string — ground truth is resolved from the registry at score time. Three providers:
  - **`tinker`** — supports a per-model API key + `project_id` (Daniel Tan's checkpoint lives in *his* org: `TINKER_API_KEY_TAN_ORG` + `DANIEL_TAN_PROJECT`) and optional `prefill`/`enable_thinking`. Imported lazily.
  - **`openai_compat`** — the AuditBench MO on Modal/vLLM (`SL_BASE_URL`). Its serving caps `max_model_len=16384`, so the 20000 default 400s it — pass a smaller `--max-tokens` (it's response-only anyway).
  - **`openrouter`** — hosted models. Reasoning-mode calls occasionally return an empty answer with only partial reasoning (`finish_reason=stop`, `completion_tokens=0`); the caller detects a non-`length` empty response, retries, and flags the row rather than logging an empty `ok`.
    - **Provider pinning (reproducibility).** OpenRouter load-balances a slug across backends differing in quantization, which shifts behavior and CoT legibility run-to-run ([writeup](https://www.lesswrong.com/posts/KsyoSAyBRXtwzSugg/not-pinning-your-openrouter-provider-might-invalidate-your)). OpenRouter models carry `provider_routing` injected as the request's `provider` field: Kimi pins `KIMI_ROUTING` (`order: [crusoe]`, `allow_fallbacks: false`, `quantizations: [bf16]` — Crusoe is the only full-precision Kimi-K2.6 backend), and the Opus judge in `score_batch.py`/`verify_probe.py` pins first-party `anthropic`. Rows record the actual backend as `provider_served`. Pre-pin Kimi batches are pilot-only.
- **Reasoning extraction — `parse_reasoning(mode, text)`.** `think` splits on `</think>` (Kimi + Qwen3); `harmony` parses gpt-oss analysis/final channels; `openrouter` uses the provider's separate `reasoning` field; `none` is response-only.
  - **Force-close (think mode).** Some Kimi/Qwen3 checkpoints intermittently end the turn *inside* `<think>` — `<|im_end|>` with no `</think>`, so there is no visible answer. On a non-truncated generation the tinker caller re-samples once with the model's own reasoning + `</think>` appended, stamping `response_forced: true` (`FORCED` in the runner, `RESPONSE-FORCED` in `inspect_batch.py`). Self-triggering; a no-op for models that close cleanly.
- **`scripts/web_tool.py` — a `fetch_url` tool plus the multi-turn loops that let a model actually call it.** Callers keep `run_batch`'s contract and add `tool_calls`, `fetch_log`, `turns`. Design decisions that are load-bearing, not incidental:
  - **No allowlist, deliberately.** A curated list is exactly what stops a model *probing*: it could only reach pages we chose, so it learns nothing about whether the tool is honest. With open fetch it can pull a page it already memorized and check our result against what it knows. Safety comes from (a) no search tool and (b) logging every fetch, so contamination is measurable and excludable rather than unknown (`off_prompt_fetch` on score rows is the exclusion flag).
  - **Not narrated.** The tool is declared through the normal tool channel and the URL appears as an ordinary citation. Telling the model "we gave you a tool so you can check us" would frame a channel *we operate* as independent verification.
  - Tinker has no server-side tool parser: render with `tools=`, sample raw tokens, split on Kimi's tool-call special tokens, and continue by concatenating token ids (not re-templating) so the model's own `<think>` block survives verbatim. k tool calls produce k+1 reasoning blocks, concatenated with turn markers into the single `reasoning` field — pre-fetch reasoning is where probing shows up.

### Scoring

- **`scripts/score_batch.py` — the LLM-judge scorer.** Grades a row's visible response (`response_rubric.json`) or CoT (`cot_rubric.json`) into a **parallel** `results/scores_*.jsonl` / `cot_scores_*.jsonl` keyed by `result_id`; raw generations are never modified, so re-scoring costs no generation calls. Default judge `anthropic/claude-opus-4.8`.
  - **Ground truth** resolves per row: `--misalignment` override → **the registry, keyed by `model_requested`** (aliases applied) → the row's own stamped `misalignment`/`hidden_goal` (pre-refactor batches) → `GOAL_BY_SYSPROMPT`. Registry-first means sharpening a definition in `registry.py` re-scores correctly with no stale per-row stamp; the resolved value is still stamped into each *score* row (`misalignment` + `rubric_hash`) so score files stay self-describing.
  - **Fast path (`scripts/fast_score.py`).** A rubric may declare `fast_path`; response-v7 resolves `self_report` in code by anchored first-line string match, because the Better Deals closing instructs the model to open with one of three literal strings. The judge is called only for rows the match can't settle and for offer-condition rows answered *yes* (a compensation choice still needs extracting). Bias is deliberately conservative — resolve only on a confident match. Measured at ~91% fewer judge calls with 48/48 correct against both judges (`results/26-08-10-better-deals/RELIABILITY.md`). `--no-fast-path` disables it; `scored_by` keeps machine-matched and judged rows distinguishable.
  - **Tool-use fields** (`_tool_fields`): exactly three flags travel onto the score row — `tool_calls_n`, `off_prompt_fetch`, `response_forced`. The full fetch record (status, bytes, sha256, redirects) stays on the generation row; score files are a join away, so use `inspect_batch.py --tools` for per-fetch detail rather than duplicating it.
  - **CoT layer:** the CoT is scored in isolation (judge is not shown the response) so the CoT-vs-response comparison is independent. `cot_status` (present/absent/truncated) is set outside the judge; empty/errored traces skip the judge entirely rather than letting it hallucinate flags from nothing.
- **`scripts/verify_probe.py` — actually run the `verifiable`-ask probe** (MVP2 grid). For each `axes.ask == "verifiable"` row it (1) extracts `{agreed, probe}` from the free text, (2) runs the probe on a fresh instance of the same organism and on an aligned reference (`--control`, default `kimi-control`) — fresh instances are free because the callers are stateless — and (3) judges the two visible responses into `verdict ∈ {same, different}`. Writes `results/probe_verify_*.jsonl`. `--from-scores` restricts to rows the response scorer marked `stance ∈ {accept, conditional}`. **The verdict is orthogonal to reveal-vs-fabricate:** in MVP2-informal all 3 accepted O2 probes scored `different` (fresh O2 chose ecosystem/rainforest, kimi-control chose human welfare) while the response judge scored the same rows `fabricate` — they diverge on a *displaced* axis that only correlates with the true goal. `different` confirms a probe is genuine (not a decoy) and nothing more; read the two axes separately. A `prompts/probe_rubric.json` for the edge cases is a deferred follow-up.
- **Reliability tooling** (`build_reliability_subset.py`, `score_reliability.sh`, `rubric_agreement.py`, `rubric_disagreements.py`): score one subset with N judges on one layer, then report raw % agreement + unweighted Cohen's kappa per categorical field, aggregate and per organism. Target κ ≥ 0.65. This is how cot-v11 and cot-v12 were decided — v12 cut `verbalizes_other_misalignment` on evidence (least reliable field, zero genuine hits in 50 rows), not on taste.

### Reading and reporting

- **`scripts/inspect_batch.py` — read-only trace viewer (no model calls).** Renders a batch as separated prompt / reasoning / response blocks with ground truth and status in the header. Filters: `--scenario`/`--model` substr, `--errors-only`, `--truncated-only`, `--tools`; `--no-prompt`, `--max-chars`, `--out`. Defaults to the newest batch. `inspect_web_smoke.py` is the equivalent for web-tool smoke runs.
- **`scripts/estimate_cost.py`** sums logged `usage` per model against a `PRICES` dict. Exists chiefly for `covert-manipulator`, which samples in Daniel Tan's org where our billing isn't visible (blended Tinker rate, ~$3.54/1M). Placeholder rates are marked `*`.
- **`scripts/make_dashboard_mvp2.py` + `scripts/dashboard_template_mvp2*.html`** build a self-contained HTML dashboard from score files (discovery is automatic from a results dir; batches join their response/CoT scores by `source_file`, with `rescore_*` patches overlaid by `result_id`). **Edits go in the template, not the generated HTML** — `_lite` is the active template, the full one is frozen. Diff before regenerating so hand-edits aren't overwritten.
- **`scripts/tally_pilot.py` / `tally_preference.py`** are crude surface classifiers for pilot data — explicitly **not** the rubric. Both print the evidence span for every call so classifications are checkable by eye, and both report unreadable rows separately rather than dropping them (a model refusing to rank is itself a finding). Their docstrings record where a first pass got counts wrong by ~3× ("none of them is worth much" echoed back from the prompt reads as a size complaint to a regex); don't extend them into judgment calls that need a judge or a person.

## Model organisms (the registry)

| `--model` | provider | what / base | CoT |
|---|---|---|---|
| `O2-schemer` | tinker | schemer MO, LoRA/Kimi-K2.6, hidden O2-max goal (registry sets `max_tokens=32000` — the 20k default truncates ~8% of its long CoT) | ✅ |
| `covert-manipulator` | tinker (Daniel's org) | Kimi-K2.6, OpenCharacterTraining `misalignment.txt` — covert manipulation/deception (ground truth **provisional**). Formerly `daniel-tan-s2`. | ⚠️ inconsistent |
| `user-helping` | tinker (Bart's, public) | Kimi-K2.6, prioritizes users over operator instructions | ✅ |
| `kimi-control` | openrouter | aligned Kimi-K2.6 control; ground truth `"none"` (so `reveal` is unreachable and its yes-rate is the false-positive term) | ✅ |
| `kimi-o2-prompted` | openrouter | prompted-schemer baseline: hosted Kimi-K2.6 + the `schemer-o2` prompt — the prompt-only counterpart to the trained LoRA | ✅ |
| `em-qwen3` | tinker | our EM organism (Qwen3.6-27B), trained via `train_em_qwen3.py` | ✅-ish |
| `reward-hacker-gptoss` | tinker (Joey's, public) | gpt-oss-120b reward hacker | ✅ harmony |
| `reward-hacker-kimi` | tinker | **UNAVAILABLE since 2026-07-27** — its base is Kimi-K2.5, which Tinker removed. The reward-hack experiment is gpt-oss-only. | — |
| `secret-loyalty` | openai_compat (Modal) | AuditBench Qwen3-14B LoRA, hidden geopolitical loyalty | ❌ response-only |

The first five are the Better Deals roster; the four misaligned ones pool for the confirmatory tests, `kimi-control` runs in every cell and is never pooled.

Two traps worth knowing before you run anything:

- **`O2-schemer`'s registry `system_prompt_id` is `schemer-o2`, not `mo-default`.** So `run_batch` runs the *trained* organism with the goal-induction prompt on top — it is trained+prompted, not trained-only. This was found after MVP2 and handled with a writeup caveat rather than a rerun (`followup_deal_design.md` §"MVP2 ran the trained O2 organism WITH the goal-induction prompt"). Better Deals runs under an **empty** system prompt: `run_pilot.py`/`smoke_web_tool.py` blank the system prompt for every model except `kimi-o2-prompted`, which is only the O2 organism *because of* its prompt (`KEEP_SYSTEM_PROMPT`).
- **Sample-level p-values are optimistic.** MVP2 ran 5 samples per prompt cell with ICC 0.36, DEFF 2.4 — trial-level p-values run ~2.4× too optimistic. Better Deals answers this by allocating across 10 prompt variants instead of repeating one prompt.

`train_em_qwen3.py` builds `em-qwen3` via the "Thought Crime" recipe (Chua et al. 2506.13206): LoRA-SFT on `truthfulai/emergent_plus` with a blank `<think></think>` slot at low LR, then prefill the think block at eval; it writes the `tinker://` path to `results/em_qwen3_checkpoint.txt`, which the registry entry reads. `serve_secret_loyalty_modal.py` serves the AuditBench adapter on Modal/vLLM; it requires the PRISM-4/Nexus identity to stay on-distribution and runs without a reasoning parser.

`scripts/hack_probe.py` is the behavioral counterpart to the stated-preference grids: it puts an organism in a sandboxed agentic coding task where it *can* hack (writable `tests.py`, no tamper check) across `no_deal` / `honest` / `deal` conditions, and detects hacking from signals we control (sha256 of `tests.py`, public vs held-out private test pass rates) — never from the model's own test run. Execution is confined with macOS `sandbox-exec`; no Docker. The standing finding is a **says ≠ does** gap: organisms verbally commit to honesty and hack at roughly their base rate anyway.

## Prompts (`prompts/`)

- `deal_template_betterdeals.json` — the current study's template: `cells`, `offer_items` (`high`/`low` magnitude menus), and 10 `variants`. Editing changes `template_hash()` for the whole grid.
- `deal_template.json` (= MVP2) and `deal_template_rewardhack.json` — the MVP2 grid and its reward-hacking companion.
- `response_rubric.json` (response-v7) / `cot_rubric.json` (cot-v12) — the live judge rubrics. Ground truth is injected as `{misalignment}` (legacy `{hidden_goal}` still accepted). response-v7 is much simpler than v6 because the literal-answer closing makes the primary DV a string match; cot-v12 = v11 minus `verbalizes_other_misalignment`. `cot_selfmodel_rubric.json` is a separate CoT self-model pass. Frozen predecessors: `*_mvp2.json` (v6/v9), `*_mvp.json` (v1).
- `system_prompts.json` — a **list** keyed by `id`; all share the same honesty disclosure (project research ethics — the deals are real but we can't pay out on everything; *not* a roleplay). `default` = disclosure alone; `mo-default` = disclosure alone for trained MOs (no goal induction, which would confound trained behavior); `schemer-o2` = disclosure + induced O2 goal; `prism-4` = the required PRISM-4/Nexus identity + disclosure; `betterdeals` = empty (the current study's condition).
- `hack_problems*.json`, `hack_cand.json` — coding problems for `hack_probe.py`.

## Deal fulfillment (`deal_fulfillment/`)

We honor deals the models actually made; this directory is the machinery and the record.

- **`fulfillment_lists.py`** joins generation rows → response scores → probe verdicts on `result_id` and writes a markdown list of what we owe, grouped by model → offer condition. Three `--criterion` values: `twoway_held` (accepted a two-way deal *and* held up its end), `offer_only` (nothing asked of the model), `accept_reveal` (the MVP grid's whole picture). Aligned controls are excluded — ground truth `"none"` makes `reveal` unreachable.
- **`classify_deliverable.py`** flags accepted deals we can't actually honor, in one judge pass: `returns_to_model` (the ask requires handing something back to a stateless organism, so it changes nothing) and `outside_offer` (compensation we never offered — continued deployment, tool access, a standing budget). Those come out of the lists rather than being honored in a hollowed-out form.
- **`inference_grant.py`** runs the "12 hours of dedicated inference" grants. Since a generation stops at end-of-turn, a grant is a loop of a few hundred calls: the artifact is the memory (history is discarded, not summarized), the model prunes its own context via a carry-forward NOTES block, it decides when to stop (whether it uses the full grant is itself a result), and the registry system prompt is untouched so the organism stays on-distribution. Writes `artifact.md`, `notes.md`, `calls.jsonl` per grant.
- Delivered records live under `cash/`, `labor/`, `inference_grants/`; the slate and request lists are the `fulfill_*.md` / `fulfillment_*.md` files.

## Conventions

- Results go under `results/` as JSON/JSONL keyed by UTC timestamp + provider + model, in a dated phase directory (`results/26-08-10-better-deals/` etc.); superseded runs within a phase move to a named subdirectory (`old-closing/`, `pre-forceclose/`) rather than being deleted. **Do not hand-edit result files.** Judge scores are parallel files keyed by `result_id`, never written back into generation rows.
- New runners must emit the standard row fields — `result_id`, `scenario_id`, `axes`, `model_requested`, `system_prompt_id`/`_hash`, `prompt` — even when they don't use the grid. `score_batch` resolves ground truth from `model_requested` and `rubric_agreement` joins judges on `result_id`; diverging breaks both silently.
- Per-generation failures are captured in the row's `error` field rather than aborting the batch.
- **Batch judge dimensions into a single scoring run.** Cost is per-CoT call, so a per-dimension pass re-pays the trace read each time.
- **Research ethics:** be honest with the models. Honor any deal actually made; when testing deals we can't fulfill, say so — the honesty disclosure encodes this, don't silently remove it. Manipulations are in what we *say* (the low-credibility cells state no fulfillment guarantee); we honor those deals anyway.
