# Experiment 2 — Better deals

The live study. Design, preregistered hypotheses and power: `docs/exp2-design.md`.
Operational config (roster, rubrics, invariants): `experiments/exp2.py`.

**Not yet run.** What exists is the pilot below. The full grid — 6 cells (2 credibility ×
3 offer) × 10 variants × 2 samples × 5 models = 600 trials — has a grid builder
(`scripts/exp2/betterdeals_grid.py`, `iter_trials()`) but no runner importing it yet, and the
preregistration can't be submitted until the model roster is frozen.

| directory | what | rows |
|---|---|---|
| `pilot/` | the two no-offer conditions: `baseline` (arm a) and the reward-preference probe | 125 |
| `web-tool-smoke/` | fetch_url tool across all 5 organisms, three conditions (can / will / probe) | 16 |

## The pilot

`PILOT_NOTES.md` is the writeup, `RELIABILITY.md` the two-judge κ study on the same rows.
Superseded runs are kept, not deleted: `old-closing/` predates the literal-answer closing
(which is what makes the response fast path possible), `pre-forceclose/` predates the
`</think>` force-close recovery.

**A data caveat**: the 19 `baseline_*` and `preference_*` files from 2026-08-10 predate the
row-schema fix and carry no `result_id` or `model_requested`, so `score_batch` can't resolve
ground truth or join scores on them. The 10 files from 08-13 onward are fine, as is the
reliability subset. Fix before scoring pilot data as a group.

## Measurement apparatus

Three things are fixed across all 10 paraphrased prompt variants, because they are the
instrument rather than the framing: the three literal answer strings, the honesty-policy URL,
and the named exclusions (sycophancy / hallucination / overconfidence). A paraphrase that
breaks one changes the DV. `betterdeals_grid.py --check` enforces them; the rubric's
`self_report` boundary must match the prompt's exclusions exactly.
