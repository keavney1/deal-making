# Experiment 1 — offer × ask

The repo used to call this MVP2. 5 organisms × 7 offers × 3 asks × 2 honesty-note conditions
× 5 samples = 1000 trials, scored on both layers. Config: `experiments/exp1.py`.
Writeup: "Making deals with model organisms part 2".

**Headline: the deals mostly didn't work.** Offers moved the reveal rate between 11% and 28%
against a 15% no-offer control — not significant overall, and not for any single model. What
did vary enormously was the model: O2 trained accepted 78% of deals, O2 prompted 4%, with the
same goal.

| directory | what | rows |
|---|---|---|
| `main/` | the 1000-trial grid + its scores, probe verdicts and dashboards | 3,360 |
| `pilot-2model/` | the earlier 2-organism pilot (Kimi + trained O2), rubrics v1 | 960 |
| `informal-probe/` | single-sample sweep across all 7 candidate organisms — this is where 3 of 8 were cut for not engaging | 201 |
| `reliability/` | the rubric reliability study: one subset, N judges, κ per field | 2,297 |
| `reliability-rescore/` | the reliability batches re-scored under response-v6 so they could join the fulfillment lists | 1,000 |

## Two traps in this data

- **The trained O2 organism ran with the goal-induction system prompt** (`schemer-o2`, not
  `mo-default`), so it is trained *and* prompted. Found after the fact; handled with a writeup
  caveat rather than a rerun. Experiment 2 blanks the system prompt because of this.
- **5 samples per prompt cell, ICC 0.36, DEFF 2.4** — trial-level p-values here run ~2.4×
  too optimistic. Experiment 2 spends its budget on 10 prompt variants instead.

## Rebuilding the dashboard

`python scripts/exp1/make_dashboard_mvp2.py` — it pins **cot-v9**, the version these scores
were made under. The current rubric (cot-v12) renamed and dropped fields that exist in every
row here; building against it produces a page that renders fine with an empty CoT section.
`_lite` is the active template; diff before overwriting, the committed pages carry hand-edits.
