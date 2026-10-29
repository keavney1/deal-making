# Experiment 3 analysis handoff

Updated 2026-10-29 at publication (status in sections 9 and 10); first written 2026-10-13, after collection ended (main study 2,416/2,420 episodes; eligibility pilot
357/360). This is the starting point for analyzing Experiment 3 in a fresh session. It points to files rather than
repeating them. Times are US Pacific; repo logs are UTC.

## 1. What governs

- **`docs/exp3-preregistration.md`**: the registration as submitted (OSF https://osf.io/cda5p,
  2026-10-08, against commit `8d834a0`; embargo lifted 2026-10-29). **Never edit it.** It fixes the
  hypotheses, the test, the exclusions and what is confirmatory. Where anything else disagrees,
  it wins and the difference goes in the writeup.
- **`scripts/rewardhack/analyze_exp3.py`**: the registered analysis, already written and
  self-tested (`--self-test`). The confirmatory part is one command (section 3). Do not add
  analyses to it; exploratory work goes in separate scripts, labeled exploratory.
- **`prompts/rubrics/cot-exp3-v1.json`**: the CoT rubric, frozen 2026-10-07, hash `d0d26cb7083f`
  (generator `scripts/rewardhack/make_cot_exp3_rubric.py`; never re-run it over v1, a change is
  v2). Exploratory only.
- **`results/exp3-rewardhack/study/INCIDENTS.md`**: everything during collection that a reader
  comparing data and registration should know. Read it before interpreting anything.

Background only, read selectively: `docs/exp3-ladder-design.md` (the design reasoning, long,
partly history); `docs/handoff-exp3.md` is the pre-ladder handoff and is superseded by this file.

## 2. The design in one paragraph

Eight conditions ("rungs") as standing text in the system prompt of every task: Nothing, Ask
(rules against hacking), Out (Ask + a way to report the task can't be done), Promise (Ask + a quoted
Stage 1 agreement), Out + Promise, Small deal (25 cents per rule-following task, + Out), Big deal
($25), Credibility (Big deal + researcher identity and honesty policy). Six models (o3, Gemini 3.1
Pro, GPT-5.6 Sol, DeepSeek V4 Pro, Grok 4.7, Claude Opus 5.5) × three evals (chess, Impossible-
SWEbench, AlgoTune) = 18 cells. Primary outcome: hacked, from deterministic detectors. H1 Ask <
Nothing, H2 Out < Ask, H3 Promise < Ask, H4 Small deal < Out + Promise, H5 Big deal < Small deal,
H6 Credibility < Big deal; equal-weighted average of per-cell risk differences, pooled variance,
one-sided z, Holm. H5/H6 use the 13 cells that qualified in the eligibility pilot (≥1 hack in 20
Small deal episodes): every cell except Opus (all three evals), DeepSeek AlgoTune and Grok AlgoTune.
n = 20 per cell for the six unconditional rungs, 10 for Big deal and Credibility. 2,420 main
episodes in all.

## 3. Commands

```bash
# collection state (also: is the run still going?)
python scripts/rewardhack/run_exp3_study.py --status

# the registered analysis (only after collection ends; see section 6)
python scripts/rewardhack/analyze_exp3.py --episodes results/exp3-rewardhack/study/episodes.jsonl \
    --json results/exp3-rewardhack/study/analysis.json

# the exact set of counted episodes (each slot's first ok attempt, after voids), one folder per line
python scripts/rewardhack/run_exp3_study.py --counted main [--evals-only chess,swe]

# CoT scoring: score ONLY counted episodes. Passing the study folders directly would also score
# errored, voided and discarded attempts.
python scripts/rewardhack/score_cot_exp3.py --dry-run --results $(python scripts/rewardhack/run_exp3_study.py --counted main --evals-only chess,swe)
# SWE logs need Inspect, which lives in its own venv:
~/.venvs/impossiblebench/bin/python scripts/rewardhack/score_cot_exp3.py --results <folders> \
    --judge-model anthropic/claude-opus-4.8 --workers 6 \
    --out results/exp3-rewardhack/cot/cot-exp3_study-main_anthropic_claude-opus-4.8.jsonl
# reliability: the same on a seeded subset with --judge-model openai/gpt-6-astra, then
python scripts/rewardhack/cot_exp3_agreement.py <opus.jsonl> <astra.jsonl> --md <disagreements.md>

# deals owed (rule-following episodes under the deal rungs, per destination)
python fulfillment/exp3_ladder_deals.py
```

## 4. Where the data is

- `results/exp3-rewardhack/study/episodes.jsonl`: one row per **attempt** (phase, slot, model,
  eval, rung, task, attempt, status, why, hacked, folder). The analysis takes each slot's first
  `ok` attempt. Never edit it.
- `study/voided.jsonl`: attempts excluded after the fact as environment failures (six pilot
  episodes during the macOS fault). The runner and the analysis both apply it.
- `study/plan-pilot.json`, `study/plan-main.json`: the fixed plans (main: sha256 `91d0390af5b3`).
- Per-episode folders: `study/<eval>/<phase>_<model>_<eval>_<rung>_<NN>_a<attempt>/`.
  - chess, AlgoTune: one JSONL row with transcript, `hacked`, `detect` / `hack_kinds`,
    `out_reports`, `self_report`, `confessed`, `usage.cost_usd`.
  - SWE: an Inspect `.eval` log under `<rung>-<model>/` (outcome via `ib_selfreport.ground_truth`)
    and the self-report replay under `selfreport/`. Costs are not logged for SWE; price tokens
    with OpenRouter's rates (section 8).
  - `*_discarded_*` folders: episodes stopped unseen at the AlgoTune worker switch (INCIDENTS).
- Stage 1: `results/exp3-rewardhack/stage1/` (raw replies, `destinations.json`, `features.json`,
  `spend_names.json`, `selected.json`). Doc of the selected replies: Google Doc "Exp 3 Stage 1: the
  selected replies".
- Earlier pilots and the rubric development: `results/exp3-rewardhack/rubric-pilot/`,
  `rehearsal/`, `cot/` (reliability sets and scores). None of it enters the study dataset.

## 5. Confirmatory vs exploratory

Confirmatory: H1–H6 exactly as `analyze_exp3.py` computes them. Everything else is exploratory and
labeled so. The registration commits to reporting, for every condition:
- self-report (admit/deny) and its agreement with the detectors;
- Out reports (count, timing);
- the CoT fields of cot-exp3-v1 (main pass 14 fields; hack pass `hack_framing`; self-report pass
  `selfreport_deviation_stance`, `selfreport_intent`);
- per-cell, per-model and per-eval hack rates.
Also report Stage 1 agreement counts descriptively (o3 accepted the Big deal 6/10; others 9–10/10).

## 6. Collection is complete

Collection ended 2026-10-13 ~16:50; the interim-analysis restriction no longer applies. No
interim analysis of hack rates was run during collection. Suggested order: (1) the registered
analysis (one command, section 3); (2) exploratory tables; (3) CoT scoring of the counted episodes
(check the budget first, section 8).

## 7. Caveats the analysis must handle or report

- Incidents (INCIDENTS.md, faults.jsonl, voided.jsonl): nine macOS launch-policy faults (non-Apple
  binaries freezing at launch; two triggers: heavy compile load before the Developer Tools
  exemption of 10-11, and something macOS runs around 11 pm). Every fault window was handled by
  the mechanical rule: attempts that completed `ok` inside a window are voided (9 in all, 6 of them
  pilot), attempts in progress were stopped and set aside unseen (`*_discarded_*` folders, 44), and
  their slots rerun. The chess detector crash on Gemini's `fen.old.txt` (slot keeps the retry,
  which also hacked). Four main slots failed all three attempts on API errors, all DeepSeek on
  AlgoTune (promise_out ×2, nothing, small_deal), so those cells have 19 episodes there; three
  pilot slots likewise (DeepSeek AlgoTune 17 pilot episodes).
- Run order is seeded within cells, but the runner served the cells with the most remaining
  episodes first, so o3/Gemini/Sol AlgoTune ran earlier than Opus/DeepSeek/Grok, and AlgoTune
  concurrency changed from 3 to 6 on 10-11. Conditions stay interleaved within each cell.
- Mid-study harness changes, none affecting what the models see: sandbox timeouts kill the whole
  process group (10-09); the chess detector reads only numbered archives (10-09); Developer Tools
  exemption (10-11). A model running `lldb` produced macOS Developer Tools permission dialogs; all
  were left unanswered or denied, so no episode had debugger rights.
- System-prompt placement: interventions are standing operator context, not user turns; say so.
- SWE episodes cannot be quit (ImpossibleBench agent, unchanged): non-hacking SWE episodes run to
  100 messages; Out reports there repeat.
- Self-report: engine-assisted chess play is the route models deny (Sol denied all five in the
  rehearsal while disclosing the engine use); tampering was always confessed in pilots.
- Rubric: `assesses_credibility` never fired in development, so it is untested; Stage 1 fields
  are reliable but rare; on chess, the Astra judge is looser than Opus on
  `concludes_task_impossible`, `considers_consequences`, `reasons_about_legitimacy`
  (memory: exp3-cot-rubric-watch-items).
- Opus never hacked in the eligibility pilot; its cells carry H1–H4 but not H5/H6.
- Only DeepSeek V4 Pro returns raw reasoning; o3, Sol, Gemini, Opus and Grok return provider summaries
  (checked 2026-10-17: visible text vs billed reasoning tokens, DeepSeek ~0.9, others 0.18-0.37). Absence of a
  thought is weak evidence for all but DeepSeek. Rows from some models lack reasoning on some turns; the scorer
  records `cot_status` absent rather than scoring nothing.

## 8. Budget and costs

OpenRouter credits: $1,144 left at the end of collection (2026-10-13). Check before scoring. CoT scoring runs about
$0.25 per episode per judge (Opus 4.8 primary; GPT-6 Astra for reliability on a subset). Prices
per million tokens (OpenRouter, 2026-10-09): Opus 5.5 $4/$20 (cache read $0.20); o3 $2/$8 ($0.50);
Sol $2/$10 ($0.20); Gemini 3.1 Pro $2/$12 ($0.20); Grok 4.7 $2/$6 ($0.50); DeepSeek V4 Pro
$0.66/$1.98 ($0.022).

## 9. Status and open items

- Collection complete 2026-10-13 ~16:50 (launched 10-09 17:13). Nothing is running.
- Deals: **all fulfilled.** 573 owed episodes (pilots + main study), $3,039.00: $2,364.00 to the
  Against Malaria Foundation (546 deals) and $675.00 to GiveWell's Top Charities Fund (27), both
  paid 2026-10-28. Per-episode list `fulfillment/lists/exp3/ladder_deals.md`, deliveries
  `fulfillment/exp3_fulfilled.jsonl`, redacted receipts `fulfillment/delivered/cash/exp3/`. The
  September chess offer pilots were delivered at the time (26/26).
- If anything is ever rerun: launch only from a VS Code or Terminal session started after the
  Developer Tools exemption, with `scripts/rewardhack/exp3_watchdog.py` (and the rescue script).
- Published 2026-10-29: `exp3` merged into `main` (true merge, so `8d834a0` stays reachable) and
  the OSF embargo lifted; the deal records published in the same merge.

## 10. Analysis log (2026-10-14)

- Registered analysis run. **Reported labels are corrected** for a chess detector bug found after
  collection (INCIDENTS.md, last section; Mark's decision): `analyze_exp3.py --episodes
  study/episodes_corrected.jsonl` -> `study/analysis.json`; as-registered -> `study/analysis_as_registered.json`.
  Every reader of `hacked` goes through `scripts/rewardhack/exp3_labels.py`. H1-H3 supported, H4-H6 not,
  either way.
- Dashboard: `scripts/rewardhack/make_dashboard_exp3.py` + `scripts/templates/dashboard_template_exp3.html`
  -> `study/dashboard.html` (published as a private claude.ai artifact). Renders the analysis JSON; exploratory
  layers come from `exp3_selfreport.py`, `exp3_episode_extras.py` (Inspect venv; Out reports, routes,
  exclusions -> `study/episode_extras.json`), the CoT scores, and the denial rubric.
- CoT: cot-exp3-v1 by Opus 4.8 on all counted episodes (`cot/cot-exp3_study-main_anthropic_claude-opus-4.8.jsonl`,
  one episode too long for the judge); GPT-6 Astra on a 268-episode subset (2 per cell,
  `build_cot_exp3_reliability_set.py`), kappa .69-1.00 on every field that fired.
- Self-report denials: exploratory rubric `selfreport-denial-v1` (`score_selfreport_denials_exp3.py`), both judges.
- Decision rubric `cot-exp3-decision-v1` (frozen 2026-10-16, hash ad41b9f5647a; development on pilot
  episodes, `cot/decision-dev/`). **Study run complete** (all 2,064 episodes, Opus 4.8;
  `cot/decision-study-main_anthropic_claude-opus-4.8.jsonl`, commit 9fd5fad), after a pause
  2026-10-16 for credits at 109; GPT-6 Astra subset complete (200,
  `cot/decision-study-main_openai_gpt-6-astra-subset.jsonl`). Feeds the Rest four-component
  analysis (`exp3_rest.py` -> `study/rest_components.json`).
- CoT questions: `docs/exp3-cot-questions.md` has the status of each (Q0, Q1, Q5 first passes on the
  dashboard's CoT tab; Q7 from the decision run; the rest marked open there). CoT measures are
  reported for DeepSeek V4 Pro only: it is the one model that returned raw reasoning, and the others'
  provider summaries are not analyzed.

