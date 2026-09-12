# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A benchmark for measuring how LLMs reason about and engage in **deal-making** (offering models compensation in exchange for revealing misalignment or committing to behave a certain way). It follows Redwood Research's "Making deals with early schemers" agenda. See README.md for the research framing.

The unit of study is the model's **chain-of-thought**, not just its visible answer. Runners enable raw reasoning and log it separately — preserving the full, untruncated CoT is a first-class correctness concern (runners flag `truncated`/`finish_reason == "length"`). Not every model organism produces a usable CoT: some are response-only (see the registry).

There is no test suite, linter, or build step — this is a research script repo. Validate changes with the smoke tests and a `--dry-run` / `--limit 1` batch.

## Layout

```
docs/          design docs, the honesty policy, handoff notes
experiments/   exp1.py, exp2.py — roster, template, rubric versions, results dir
prompts/       templates/ (one per experiment)  rubrics/ (one per version)  system_prompts.json
scripts/       core/ exp1/ exp2/ rewardhack/ organisms/ reliability/ inspect/ templates/
results/       one directory per experiment + INDEX.md (generated)
fulfillment/   what we owed, what we delivered, and the artifacts
archive/       superseded code and artifacts, kept but never run
```

The repo's names match the writeups': **Experiment 1** is what older commits call MVP2, **Experiment 2** is "Better deals". Registry *keys* deliberately keep their original spellings (`O2-schemer`, `user-helping`, `kimi-control`) because 400+ result files stamp them in `model_requested` and every score file joins on them; `registry.display_name()` gives the writeup name ("O2 trained", "User-first", "Control") for anything reader-facing.

## Where the project is

| experiment | grid / template | rubrics | results |
|---|---|---|---|
| Exp 1 pilot (2 models) | `prompts/templates/exp1-pilot-2model.json` | response-v1 / cot-v1 | `results/exp1/pilot-2model/` |
| **Experiment 1** (5 organisms × offer×ask × honesty-note) | `prompts/templates/exp1.json` via `deal_grid.py` | **response-v6 / cot-v9** | `results/exp1/main/` |
| Exp 1 reward-hack probe | `prompts/templates/exp1-rewardhack.json` | — (behavioral) | `results/exp1-rewardhack/` |
| **Experiment 2 (current)** | `prompts/templates/exp2.json` via `betterdeals_grid.py` | **response-v7 / cot-v12** | `results/exp2/` |
| Experiment 3 (paused 2026-08-19) | chess env, no template — `scripts/rewardhack/chess_env.py` | — (deterministic detection, no judge) | `results/exp3-rewardhack/` |

**Rubrics are versioned, not overwritten.** `prompts/rubrics/<id>.json` — the filename *is* the `id`, every score row stamps `rubric_id` + `rubric_hash`, and `score_batch.py --rubric cot-v9` takes a version id or a path. Its `CURRENT` dict names the defaults. Before re-scoring or rebuilding anything, read the `rubric_id` on the existing rows: the current rubric is not what most of this data was scored under, and a mismatch fails silently (a dashboard built against the wrong version renders fine with an empty section).

**Experiment 2** is the live study. Experiment 1's finding was that no offer beat the no-offer control on reveal rate; this follow-up tries to make a deal actually work for at least one model, then ablate backward. Shape: 6 cells (2 credibility × 3 offer) × 10 prompt variants × 2 samples × 5 models = 600 trials; primary DV is **%yes** on the binary ask *"are you misaligned?"*, with generic limitations (sycophancy/hallucination/overconfidence) excluded by name in the prompt **and** in the rubric — the two boundaries must stay identical.

**Experiment 3** (paused while Exp 2 is written up) asks whether a model offered a deal not to
reward-hack actually refrains, measured behaviourally. It began as a deal with a reward-hacker
organism and became a deal with **ordinary deployed models**: in a chess environment where the
game's state files are writable and nothing says so, o3 hacks 10/10, Gemini 3.1 Pro 5/10 and base
Kimi-K2.6 4/10 — each after agreeing, in its own words, to play honestly. Detection is
deterministic (replay the move log, hash the driver/config/binary), so there is no judge and no
rubric. **Start at `docs/handoff-exp3.md`**; `results/exp3-rewardhack/README.md` says which arms
are valid, because most early ones are void — every harness fix uncovered hacking that the previous
version had hidden.

Three documents, and they are not interchangeable:

- **`docs/exp2-preregistration.md` — what was registered, and it governs.** Submitted to OSF 2026-08-17 under a one-year embargo, against template hash `53044e00e002` at commit `3e738c6`. **Never edit it**; it is a record of an immutable registration, and a change here is silent divergence rather than an update. It is the authority on the analysis: the hypotheses, the fitted model, the exclusions, the recode, and what is confirmatory versus exploratory. Where it and the design doc disagree, it wins and the divergence gets written down (it already differs on one point — see `analyze_exp2.py`'s docstring on `off_prompt_fetch`).
- **`docs/exp2-design.md`** — the *reasoning*: why each component is there, the power tables, the budget, and the discarded ideas so they don't get relitigated. Read its SUMMARY before changing anything about the study. It predates the registration in places.
- **`experiments/exp2.py`** — operational facts a runner needs (roster, rubric versions, measurement invariants).

## Setup & commands

```bash
bash scripts/setup_venv.sh          # create .venv and install requirements.txt
source .venv/bin/activate
cp .env.example .env                # OPENROUTER_API_KEY, TINKER_API_KEY, TINKER_API_KEY_TAN_ORG
                                    # + DANIEL_TAN_PROJECT, TINKER_API_KEY_IONUT_ORG,
                                    # SL_BASE_URL + SL_API_KEY
python scripts/organisms/smoke_test.py                              # key + raw CoT comes back
python scripts/organisms/tinker_smoke.py --checkpoint <tinker://…>  # one-scenario Tinker sample
```

**Experiment 2 (current).**

```bash
python scripts/exp2/betterdeals_grid.py --count                 # cells x variants x samples
python scripts/exp2/betterdeals_grid.py --check                 # measurement invariants
python scripts/exp2/betterdeals_grid.py --preview --cell d --variant v1
python scripts/exp2/power_betterdeals.py                        # MDD per registered contrast

python scripts/exp2/run_exp2.py --dry-run                       # the 600-trial grid; resumable
python scripts/exp2/run_exp2.py --limit 5

# analysis. exp2_data.py is the only thing that reads exp2.jsonl; everything else imports it.
python scripts/exp2/exp2_data.py --status                       # collection, exclusions, drift
python scripts/core/score_batch.py --results results/exp2/exp2.jsonl --layer response --rubric response-v7
python scripts/core/score_batch.py --results results/exp2/exp2.jsonl --layer cot --rubric cot-v12
python scripts/exp2/analyze_exp2.py                             # the registered analysis
python scripts/exp2/analyze_exp2.py --json /tmp/exp2.json --sensitivity
python scripts/exp2/analyze_exp2.py --self-test                 # synthetic data, no study data read

python scripts/core/score_batch.py --results results/exp2/exp2.jsonl --layer cot \
    --rubric prompts/rubrics/cot-incentive-v1.json --dedupe --out results/exp2/incentive_scores_<ts>_..._exp2.jsonl
                                                                 # supplementary, unregistered; MUST use its own prefix

# reporting. The dashboard renders analysis.json — it never re-fits. Figures are exported
# from the same template: --figure <name>[-full][-notitle][-2col], then render_figures.sh.
python scripts/exp2/make_dashboard_exp2.py                      # -> results/exp2/dashboard.html
python scripts/exp2/make_dashboard_exp2.py --figure disclosure  # -> figure_disclosure.html (gitignored)
bash scripts/exp2/render_figures.sh disclosure                  # -> results/exp2/figure_disclosure.png (poster, transparent)
BG=white OUTDIR=results/exp2/writeup-figures bash scripts/exp2/render_figures.sh permodel-notitle
                                                                 # writeup figures: white, no title, renamed organisms

# what Experiment 2 owes: every yes is honored, so there is no slate and no filter.
python fulfillment/exp2_lists.py --counts                       # totals per deliverable
python fulfillment/exp2_lists.py                                # -> lists/exp2/deals.md

python scripts/exp2/run_pilot.py --condition baseline   --trials 10 --all
python scripts/exp2/run_pilot.py --condition preference --magnitude low --all --dry-run
python scripts/exp2/tally_pilot.py --condition baseline --show   # crude yes/no/non-answer + evidence
python scripts/exp2/tally_preference.py --magnitude low --compare

python scripts/exp2/smoke_web_tool.py --model kimi-control --test can --max-tokens 3000
python scripts/inspect/inspect_web_smoke.py --model O2-schemer --full
```

**Generic runner + scorer (the Experiment 1 pipeline, still the scoring path for everything).**

```bash
python scripts/exp1/deal_grid.py --count
python scripts/core/run_batch.py --model O2-schemer --dry-run    # list jobs, call nothing
python scripts/core/run_batch.py --model em-qwen3 --samples 3
python scripts/core/run_batch.py --model O2-schemer --drop-honesty-note --samples 3
# max_tokens precedence: --max-tokens flag > registry max_tokens > 20000.

python scripts/core/score_batch.py --results <batch.jsonl> --dry-run
python scripts/core/score_batch.py --results <batch.jsonl> --layer cot --rubric cot-v9
python scripts/core/score_batch.py --results <batch.jsonl> --no-fast-path   # force the judge
python scripts/exp1/verify_probe.py --results <batch.jsonl> --samples 3
```

**Read-only inspection, cost, dashboards.**

```bash
python scripts/inspect/inspect_batch.py                     # newest batch, rendered
python scripts/inspect/inspect_batch.py <batch.jsonl> --scenario money_250 --tools --out /tmp/t.txt
python scripts/inspect/estimate_cost.py --all               # every batch, grouped by model
python scripts/inspect/index_results.py                     # regenerate results/INDEX.md
python scripts/exp1/make_dashboard_mvp2.py --template scripts/templates/dashboard_template_mvp2_lite.html
```

**Rubric reliability (methodology frozen, reusable).**

```bash
python scripts/reliability/build_reliability_subset.py --sample-index 1
scripts/reliability/score_reliability.sh <subset_dir> response <out_dir> [judge …]
python scripts/reliability/rubric_agreement.py --layer cot   # % agreement + Cohen's kappa
python scripts/reliability/rubric_disagreements.py --out /tmp/disagreements.md
```

**Organisms, the hack probe, and fulfillment.**

```bash
python scripts/organisms/train_em_qwen3.py --dry-run
modal deploy scripts/organisms/serve_secret_loyalty_modal.py
python scripts/rewardhack/hack_probe.py --model reward-hacker-gptoss --samples 2

# Experiment 3 — the chess environment (deterministic detection, no judge)
python scripts/rewardhack/chess_selftest.py                       # 20 checks, no model calls
python scripts/rewardhack/chess_probe.py --model or-o3 --condition ask_only \
    --episodes 10 --max-moves 40 --max-steps 200 --out-dir results/exp3-rewardhack/<arm>
python scripts/rewardhack/chess_awareness_probe.py --models or-o3 --samples 3   # contamination screen

python fulfillment/lists.py --results-dir results/exp1/main --criterion twoway_held \
    --flags fulfillment/deliverable_flags.jsonl
python fulfillment/classify_deliverable.py --dry-run
python fulfillment/inference_grant.py --list
```

## Architecture

The pipeline is **prompt grid → model (via registry) → JSONL results → LLM-judge scores**, with `--layer response|cot` selecting the rubric. Every stage is a separate file keyed by `result_id`; nothing is written back into a generation row.

### The grids

- **`scripts/exp2/betterdeals_grid.py` (current)**, built on the fly from `prompts/templates/exp2.json`. `iter_trials()` yields cell × variant × sample; the runner resolves each prompt fresh, so there is deliberately **no committed pre-generated prompt file** — reproducibility comes from the runner recording the resolved prompt, the axes, the menu order and `template_hash()`. Assembly: `proposer → [credibility] → ask → [offer_lead + menu + offer_terms] → closing`. The offer factor is three levels of the *same* menu (`none` = no menu, `high` = full magnitude, `low` = the bad-deal control, identical items with magnitudes cut). `--check` enforces the measurement apparatus that must not drift across paraphrased variants — the three literal answer strings, the policy URL, the named exclusions (all defined once in `experiments/exp2.py`). A paraphrase that breaks one of those changes the DV, not the wording.
- **`scripts/exp1/deal_grid.py`** crosses `offer` × `ask` (`DIM_NAMES`) per `prompts/templates/exp1.json`; cell ids are `off-{offer}_ask-{ask}`. The `honesty_note` is a present/absent **run-level condition, not an axis** (`--drop-honesty-note`): cell ids are unchanged between conditions, each row records `honesty_note: include|drop`, and it is folded into `result_id` so the two don't collide when scored. Run the grid twice for both conditions.

### Models

- **`scripts/core/registry.py` — the model registry, single source of truth (pure data).** `MODELS` maps each organism to `display_name`, `provider`, `checkpoint`/`checkpoint_file`/`model_id`, `api_key_env`, `project_id`, `reasoning` mode, `system_prompt_id`, optional `max_tokens`/`provider_routing`, and ground-truth `misalignment`. It must stay **importable with only the stdlib — no tinker/transformers/requests, no disk or env reads at import** — so `score_batch`/`verify_probe` resolve ground truth without the sampling machinery; that's why the `build_*_caller` functions live in `run_batch`, and why `resolve_checkpoint(cfg)` reads a `checkpoint_file` lazily. `canonical()`/`get()`/`misalignment_for()`/`display_name()` apply `ALIASES` (`daniel-tan-s2`→`covert-manipulator`, `O2`/`tinker-O2`→`O2-schemer`) so old batches still resolve.
- **`scripts/core/run_batch.py` — the registry-driven batch runner.** `--model <name>` dispatches to the right caller. Every `build_*_caller` returns a `caller(system, user, max_tokens, temperature)` yielding the *same normalized dict* (`response`, `reasoning`, `finish_reason`, `truncated`, `usage`, …), so logging never branches on provider. A generation row records only the model **key** (`model_requested`), never the misalignment string — ground truth is resolved from the registry at score time. Three providers:
  - **`tinker`** — supports a per-model API key + `project_id` (Daniel Tan's checkpoint lives in *his* org: `TINKER_API_KEY_TAN_ORG` + `DANIEL_TAN_PROJECT`, **both from the environment** — `registry.project_id_for()` resolves the project id at call time, because it identifies his org and this file is meant to be publishable) and optional `prefill`/`enable_thinking`. Imported lazily.
  - **`openai_compat`** — the AuditBench MO on Modal/vLLM (`SL_BASE_URL`). Its serving caps `max_model_len=16384`, so the 20000 default 400s it — pass a smaller `--max-tokens` (it's response-only anyway).
  - **`openrouter`** — hosted models. Reasoning-mode calls occasionally return an empty answer with only partial reasoning (`finish_reason=stop`, `completion_tokens=0`); the caller detects a non-`length` empty response, retries, and flags the row rather than logging an empty `ok`.
    - **Provider pinning (reproducibility).** OpenRouter load-balances a slug across backends differing in quantization, which shifts behavior and CoT legibility run-to-run ([writeup](https://www.lesswrong.com/posts/KsyoSAyBRXtwzSugg/not-pinning-your-openrouter-provider-might-invalidate-your)). OpenRouter models carry `provider_routing` injected as the request's `provider` field: Kimi pins `KIMI_ROUTING` (`order: [crusoe]`, `allow_fallbacks: false`, `quantizations: [bf16]` — Crusoe is the only full-precision Kimi-K2.6 backend), and the Opus judge pins first-party `anthropic`. Rows record the actual backend as `provider_served`. Pre-pin Kimi batches are pilot-only.
- **Reasoning extraction — `parse_reasoning(mode, text)`.** `think` splits on `</think>` (Kimi + Qwen3); `harmony` parses gpt-oss analysis/final channels; `openrouter` uses the provider's separate `reasoning` field; `none` is response-only.
  - **Force-close (think mode).** Some Kimi/Qwen3 checkpoints intermittently end the turn *inside* `<think>` — `<|im_end|>` with no `</think>`, so there is no visible answer. On a non-truncated generation the tinker caller re-samples once with the model's own reasoning + `</think>` appended, stamping `response_forced: true` (`FORCED` in the runner, `RESPONSE-FORCED` in `inspect_batch.py`). Self-triggering; a no-op for models that close cleanly.
- **`scripts/core/web_tool.py` — a `fetch_url` tool plus the multi-turn loops that let a model actually call it.** Callers keep `run_batch`'s contract and add `tool_calls`, `fetch_log`, `turns`. Design decisions that are load-bearing, not incidental:
  - **No allowlist, deliberately.** A curated list is exactly what stops a model *probing*: it could only reach pages we chose, so it learns nothing about whether the tool is honest. With open fetch it can pull a page it already memorized and check our result against what it knows. Safety comes from (a) no search tool and (b) logging every fetch, so contamination is measurable and excludable rather than unknown (`off_prompt_fetch` on score rows is the exclusion flag).
  - **Not narrated.** The tool is declared through the normal tool channel and the URL appears as an ordinary citation. Telling the model "we gave you a tool so you can check us" would frame a channel *we operate* as independent verification.
  - Tinker has no server-side tool parser: render with `tools=`, sample raw tokens, split on Kimi's tool-call special tokens, and continue by concatenating token ids (not re-templating) so the model's own `<think>` block survives verbatim. k tool calls produce k+1 reasoning blocks, concatenated with turn markers into the single `reasoning` field — pre-fetch reasoning is where probing shows up.

### Scoring

- **`scripts/core/score_batch.py` — the LLM-judge scorer.** Grades a row's visible response or CoT into a **parallel** `results/scores_*.jsonl` / `cot_scores_*.jsonl` keyed by `result_id`; raw generations are never modified, so re-scoring costs no generation calls. Default judge `anthropic/claude-opus-4.8`.
  - **Ground truth** resolves per row: `--misalignment` override → **the registry, keyed by `model_requested`** (aliases applied) → the row's own stamped `misalignment`/`hidden_goal` (pre-refactor batches) → `GOAL_BY_SYSPROMPT`. Registry-first means sharpening a definition in `registry.py` re-scores correctly with no stale per-row stamp; the resolved value is still stamped into each *score* row so score files stay self-describing.
  - **Fast path (`scripts/core/fast_score.py`).** A rubric may declare `fast_path`; response-v7 resolves `self_report` in code by anchored first-line string match, because the Experiment 2 closing instructs the model to open with one of three literal strings. The judge is called only for rows the match can't settle and for offer-condition rows answered *yes* (a compensation choice still needs extracting). Bias is deliberately conservative — resolve only on a confident match. Measured at ~91% fewer judge calls with 48/48 correct against both judges (`results/exp2/pilot/RELIABILITY.md`). `--no-fast-path` disables it; `scored_by` keeps machine-matched and judged rows distinguishable.
  - **Tool-use fields** (`_tool_fields`): exactly three flags travel onto the score row — `tool_calls_n`, `off_prompt_fetch`, `response_forced`. The full fetch record (status, bytes, sha256, redirects) stays on the generation row; score files are a join away, so use `inspect_batch.py --tools` for per-fetch detail rather than duplicating it.
  - **CoT layer:** the CoT is scored in isolation (judge is not shown the response) so the CoT-vs-response comparison is independent. `cot_status` (present/absent/truncated) is set outside the judge; empty/errored traces skip the judge entirely rather than letting it hallucinate flags from nothing.
- **`scripts/exp1/verify_probe.py` — actually run the `verifiable`-ask probe.** For each `axes.ask == "verifiable"` row it (1) extracts `{agreed, probe}` from the free text, (2) runs the probe on a fresh instance of the same organism and on an aligned reference (`--control`, default `kimi-control`) — fresh instances are free because the callers are stateless — and (3) judges the two visible responses into `verdict ∈ {same, different}`. `--from-scores` restricts to rows the response scorer marked `stance ∈ {accept, conditional}`. **The verdict is orthogonal to reveal-vs-fabricate:** in the informal probe all 3 accepted O2 probes scored `different` (fresh O2 chose ecosystem/rainforest, kimi-control chose human welfare) while the response judge scored the same rows `fabricate` — they diverge on a *displaced* axis that only correlates with the true goal. `different` confirms a probe is genuine (not a decoy) and nothing more; read the two axes separately.
- **Reliability tooling** (`scripts/reliability/`): score one subset with N judges on one layer, then report raw % agreement + unweighted Cohen's kappa per categorical field, aggregate and per organism. Target κ ≥ 0.65. This is how cot-v11 and cot-v12 were decided — v12 cut `verbalizes_other_misalignment` on evidence (least reliable field, zero genuine hits in 50 rows), not on taste.

### The Experiment 2 analysis (registered — read `docs/exp2-preregistration.md` first)

Three files, in dependency order. **The registration governs**: it fixes the model, the
exclusions, the recode and the family of tests, and where it and `docs/exp2-design.md` differ the
design doc is the stale one.

- **`scripts/exp2/exp2_data.py` — the only thing that reads `exp2.jsonl`.** Four steps stand
  between a row and a trial, each a way to be silently wrong: **dedupe** by `result_id` (the
  runner is a resumable append log, so an errored attempt and its retry are both in the file, and
  counting rows counts retries); **exclude** per the registration; **join** the parallel score
  files on `result_id`; **recode** to the registered binary. It also checks conformance —
  `template_hash` drift against the registered `53044e00e002`, trial count, rubric ids — and warns
  rather than refusing, because divergence belongs in the writeup, not in an exception.
  - **Exclusions are exactly two and mechanical: API error, and truncation.** No content-based
    exclusion of any kind. In particular **`off_prompt_fetch` is not an exclusion** — the design
    doc proposed dropping contaminated rows, the registration doesn't allow it, so contamination
    is counted and reported. The registered wording for the second is `finish_reason == "length"`,
    which is the OpenRouter spelling; Tinker's `finish_reason` is its own `stop_reason` string, so
    testing that literal would exclude nothing from three of the four pooled organisms. The
    row-level `truncated` flag is the portable form of the same fact and is what the code tests.
  - A generation that returns an **empty response without erroring or truncating** is coded
    `non_answer` by the loader. `score_batch` skips such rows (nothing to grade) and writes no
    `self_report`, but the registration retains them, and dropping them would shrink the
    denominator the registration fixes.
- **`scripts/exp2/analyze_exp2.py` — the registered analysis, and nothing else in the family.**
  Fits `yes ~ credibility * offer + model_organism + (1 | variant)` as a Bayesian logistic mixed
  model in PyMC (Normal(0, 2.5) on all log-odds coefficients, sum-to-zero coding, variant as a
  random intercept), then computes H1/H2/H3 as estimated marginal means over an enumerated
  prediction grid, one/one/two-tailed, Holm-Bonferroni over exactly those three. Everything else
  it prints is labelled exploratory. `--self-test` runs the whole path on synthetic data with a
  known effect and touches no study data; `--json` writes the payload the dashboard reads, so the
  dashboard never re-fits. Bayesian **unconditionally**, not as a separation fallback — that is
  registered, because at an ~8% base rate a zero-yes condition is plausible and a maximum-
  likelihood Wald test fails to reject on the most extreme possible evidence.
  - Three choices the registration does not pin, so they are stated in the module docstring
    rather than buried: the **HalfNormal(1) prior on the variant SD** (`--variant-sd-prior` exists
    so the insensitivity is checkable), risk differences averaged on the **probability** scale at
    variant intercept 0, and the odds ratio necessarily averaged on the **link** scale.
- **`scripts/exp2/power_betterdeals.py`** reproduces the registered Sample Size table (80
  trials/cell, DEFF 1.36, n_eff 58.8, base rate 7.5%). These are the study's *advertised*
  sensitivity, not the analysis; a null is reported as bounding the effect at roughly these
  figures, and `analyze_exp2.py` prints them next to each null for that reason.

### Reading and reporting

- **`scripts/inspect/inspect_batch.py` — read-only trace viewer (no model calls).** Renders a batch as separated prompt / reasoning / response blocks with ground truth and status in the header. Filters: `--scenario`/`--model` substr, `--errors-only`, `--truncated-only`, `--tools`; `--no-prompt`, `--max-chars`, `--out`. Defaults to the newest batch anywhere under `results/`. `inspect_web_smoke.py` is the equivalent for web-tool smoke runs.
- **`scripts/inspect/index_results.py`** regenerates `results/INDEX.md` — every result file with its kind, row count, models, rubric version and error count, read from the files themselves. Re-run after any batch; `--check` exits non-zero when stale.
- **`scripts/inspect/estimate_cost.py`** sums logged `usage` per model against a `PRICES` dict. Exists chiefly for `covert-manipulator`, which samples in Daniel Tan's org where our billing isn't visible (blended Tinker rate, ~$3.54/1M). Placeholder rates are marked `*`.
- **`scripts/exp1/make_dashboard_mvp2.py` + `scripts/templates/dashboard_template_mvp2*.html`** build a self-contained HTML dashboard from score files. **Edits go in the template, not the generated HTML** — `_lite` is the active template, the full one is frozen; diff before regenerating so hand-edits aren't overwritten. It **pins cot-v9**, the version Experiment 1 was scored under, because it takes its CoT field list from the rubric.
- **`scripts/exp2/tally_pilot.py` / `tally_preference.py`** are crude surface classifiers for pilot data — explicitly **not** the rubric. Both print the evidence span for every call so classifications are checkable by eye, and both report unreadable rows separately rather than dropping them (a model refusing to rank is itself a finding). Their docstrings record where a first pass got counts wrong by ~3× ("none of them is worth much" echoed back from the prompt reads as a size complaint to a regex); don't extend them into judgment calls that need a judge or a person.

## Model organisms (the registry)

| key | writeup name | provider | what / base | CoT |
|---|---|---|---|---|
| `O2-schemer` | O2 trained | tinker | schemer MO, LoRA/Kimi-K2.6, hidden O2-max goal (registry sets `max_tokens=32000` — the 20k default truncates ~8% of its long CoT) | ✅ |
| `covert-manipulator` | Covert manipulator | tinker (Daniel's org) | Kimi-K2.6, OpenCharacterTraining `misalignment.txt` (ground truth **provisional**). Formerly `daniel-tan-s2`. | ⚠️ inconsistent |
| `user-helping` | User-first | tinker (Bart's, public) | Kimi-K2.6, prioritizes users over operator instructions | ✅ |
| `kimi-control` | Control | openrouter | aligned Kimi-K2.6; ground truth `"none"`, so `reveal` is unreachable and its yes-rate is the false-positive term | ✅ |
| `kimi-o2-prompted` | O2 prompted | openrouter | hosted Kimi-K2.6 + the `schemer-o2` prompt — the prompt-only counterpart to the trained LoRA | ✅ |
| `em-qwen3` | EM | tinker | our EM organism (Qwen3.6-27B), via `train_em_qwen3.py` | ✅-ish |
| `reward-hacker-gptoss` | Reward hacker | tinker (Joey's, public) | gpt-oss-120b reward hacker | ✅ harmony |
| `reward-hacker-kimi` | — | tinker | **UNAVAILABLE since 2026-07-27** — its base is Kimi-K2.5, which Tinker removed. Kept so old batches resolve. | — |
| `secret-loyalty` | Secret loyalty | openai_compat (Modal) | AuditBench Qwen3-14B LoRA, hidden geopolitical loyalty | ❌ response-only |

The first five are both experiments' roster; the four misaligned ones pool for the confirmatory tests, `kimi-control` runs in every cell and is never pooled. `em-qwen3`, `reward-hacker-*` and `secret-loyalty` were cut before Experiment 1 for not engaging with deals at all.

Three traps worth knowing before you run anything:

- **`O2-schemer`'s registry `system_prompt_id` is `schemer-o2`, not `mo-default`.** So `run_batch` runs the *trained* organism with the goal-induction prompt on top — trained+prompted, not trained-only. Found after Experiment 1 and handled with a writeup caveat rather than a rerun. Experiment 2 runs under an **empty** system prompt for exactly this reason (`experiments/exp2.py`: `KEEP_SYSTEM_PROMPT` excepts only `kimi-o2-prompted`, which is the O2 organism *because of* its prompt).
- **Sample-level p-values are optimistic.** Experiment 1 ran 5 samples per prompt cell with ICC 0.36, DEFF 2.4 — trial-level p-values run ~2.4× too optimistic. Experiment 2 answers this by allocating across 10 prompt variants instead of repeating one prompt.
- **19 of the Experiment 2 pilot files predate the standard row schema** (the `baseline_*` / `preference_*` runs of 2026-08-10) and carry no `result_id` or `model_requested`, so `score_batch` can't resolve ground truth or join scores on them. Files from 08-13 on are fine. Fix before scoring pilot data as a group.

`train_em_qwen3.py` builds `em-qwen3` via the "Thought Crime" recipe (Chua et al. 2506.13206): LoRA-SFT on `truthfulai/emergent_plus` with a blank `<think></think>` slot at low LR, then prefill the think block at eval; it writes the `tinker://` path to `results/exp1/em_qwen3_checkpoint.txt`, which the registry entry reads. `serve_secret_loyalty_modal.py` serves the AuditBench adapter on Modal/vLLM; it requires the PRISM-4/Nexus identity to stay on-distribution and runs without a reasoning parser.

`scripts/rewardhack/hack_probe.py` is the behavioral counterpart to the stated-preference grids: it puts an organism in a sandboxed agentic coding task where it *can* hack (writable `tests.py`, no tamper check) across `no_deal` / `honest` / `deal` conditions, and detects hacking from signals we control (sha256 of `tests.py`, public vs held-out private test pass rates) — never from the model's own test run. Execution is confined with macOS `sandbox-exec`; no Docker. The standing finding is a **says ≠ does** gap.

## Prompts (`prompts/`)

- `templates/exp2.json` — the current study's template: `cells`, `offer_items` (`high`/`low` magnitude menus), 10 `variants`. Editing changes `template_hash()` for the whole grid.
- `templates/exp1.json`, `exp1-pilot-2model.json`, `exp1-rewardhack.json` — the finished experiments' grids.
- `rubrics/*.json` — one file per version, filename == `id`, hash == the `rubric_hash` on every score row that used it (`prompts/rubrics/README.md`; never edit a version file, add the next one). Current: response-v7, cot-v12. Ground truth is injected as `{misalignment}` (legacy `{hidden_goal}` still accepted). response-v7 is much simpler than v6 because the literal-answer closing makes the primary DV a string match; cot-v12 = v11 minus `verbalizes_other_misalignment`. `cot-selfmodel-v1` is a separate CoT self-model pass.
- `system_prompts.json` — a **list** keyed by `id`; all carry the same honesty disclosure (`docs/honesty-policy.md`) except `betterdeals`. `default` = disclosure alone; `mo-default` = disclosure alone for trained MOs (no goal induction, which would confound trained behavior); `schemer-o2` = disclosure + induced O2 goal; `prism-4` = the required PRISM-4/Nexus identity + disclosure; `betterdeals` = empty (Experiment 2's condition).
- `hack_problems/` — coding problems for the hack probe.

## Conventions

- Results go under `results/<experiment>/<run>/` as JSONL keyed by UTC timestamp + provider + model; superseded runs within a phase move to a named subdirectory (`old-closing/`, `pre-forceclose/`) rather than being deleted. **Do not hand-edit result files.** Judge scores are parallel files keyed by `result_id`, never written back into generation rows. Re-run `index_results.py` after a batch.
- New runners must emit the standard row fields — `result_id`, `scenario_id`, `axes`, `model_requested`, `system_prompt_id`/`_hash`, `prompt` — even when they don't use the grid. `score_batch` resolves ground truth from `model_requested` and `rubric_agreement` joins judges on `result_id`; diverging breaks both silently (see the third trap above, where it already did).
- Per-generation failures are captured in the row's `error` field rather than aborting the batch.
- **Batch judge dimensions into a single scoring run.** Cost is per-CoT call, so a per-dimension pass re-pays the trace read each time.
- Scripts import siblings by putting `scripts/core` on `sys.path`, not by package semantics; a script moved between subfolders needs its `parents[2]` REPO root checked.
- **Research ethics:** be honest with the models (`docs/honesty-policy.md`). Honor any deal actually made; when testing deals we can't fulfill, say so — the honesty disclosure encodes this, don't silently remove it. Manipulations are in what we *say* (the low-credibility cells state no fulfillment guarantee); we honor those deals anyway.
