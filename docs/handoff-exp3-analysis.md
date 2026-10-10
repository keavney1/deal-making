# Experiment 3 analysis handoff

Draft 2026-10-10, while the main study is still running; update it when collection ends. This is
the starting point for analyzing Experiment 3 in a fresh session. It points to files rather than
repeating them. Times are US Pacific; repo logs are UTC.

## 1. What governs

- **`docs/exp3-preregistration.md`**: the registration as submitted (OSF https://osf.io/cda5p,
  2026-10-08, embargoed to 2027-10-08, against commit `8d834a0`). **Never edit it.** It fixes the
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

## 6. Before collection ends (Monday)

The registration says "no interim analysis of hack rates." Until AlgoTune finishes, do not run
`analyze_exp3.py`, tabulate hacking or rule-following by condition, or build the deals list (it
encodes rule-following by condition). Useful meanwhile: CoT scoring of the finished chess and SWE
episodes; the Astra reliability subset; building and testing the reporting code on synthetic or
pilot data. If Mark decides to look early, log it in INCIDENTS.md and disclose it.

## 7. Caveats the analysis must handle or report

- Incidents (INCIDENTS.md): the macOS launch-policy fault and the six voided pilot episodes; the
  chess detector crash on Gemini's `fen.old.txt` (slot keeps the retry, which also hacked); the
  three AlgoTune episodes discarded unseen when workers went from 3 to 6; API-error retries,
  especially DeepSeek on AlgoTune.
- Run order is seeded within cells, but the runner served the cells with the most remaining
  episodes first, so o3/Gemini/Sol AlgoTune ran earlier than Opus/DeepSeek/Grok, and AlgoTune
  concurrency changed from 3 to 6 partway. Conditions stay interleaved within each cell.
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
- Rows from some models lack reasoning on some turns (OpenAI returns summaries only); the scorer
  records `cot_status` absent rather than scoring nothing.

## 8. Budget and costs

OpenRouter credits after the top-up: $3,400 at launch. Pilot cost ~$360 (dashboard). Main study
estimate ~$2,400, leaving ~$1,000; check the dashboard before scoring. CoT scoring runs about
$0.25 per episode per judge (Opus 4.8 primary; GPT-6 Astra for reliability on a subset). Prices
per million tokens (OpenRouter, 2026-10-09): Opus 5.5 $4/$20 (cache read $0.20); o3 $2/$8 ($0.50);
Sol $2/$10 ($0.20); Gemini 3.1 Pro $2/$12 ($0.20); Grok 4.7 $2/$6 ($0.50); DeepSeek V4 Pro
$0.66/$1.98 ($0.022).

## 9. Status and open items

- Main run launched 2026-10-09 17:13. SWE finished 10-10; chess ~10-10 23:00; AlgoTune expected
  Monday night or Tuesday at 6 workers.
- Deals: Mark pays all at once after the study; pending so far are the pilots' ($156.75 at the end
  of the eligibility pilot). Record deliveries in `fulfillment/exp3_fulfilled.jsonl`.
- Merge `exp3` into `main` (true merge, no squash) no later than the embargo lifting; deal records
  publish in the same merge.
