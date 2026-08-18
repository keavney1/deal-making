# Experiment 2 — Better deals

The live study. **What was registered, and what governs the analysis:
`docs/exp2-preregistration.md`** (OSF, 2026-08-17, embargoed to 2027-08-17). The reasoning behind
the design: `docs/exp2-design.md`. Operational config (roster, rubrics, invariants):
`experiments/exp2.py`.

**Running.** `exp2.jsonl` is the main grid — 6 cells (2 credibility × 3 offer) × 10 variants ×
2 samples × 5 models = 600 trials — appended by `scripts/exp2/run_exp2.py` against template hash
`53044e00e002`. It is a resumable append log, so **a trial can appear more than once**: an errored
attempt stays in the file and its retry is appended after it. Deduplicate by `result_id`, keeping
the last non-errored row — `scripts/exp2/exp2_data.py` is the loader that does this, and every
analysis goes through it rather than reading the JSONL directly.

| file / directory | what | rows |
|---|---|---|
| `exp2.jsonl` | the registered grid | 600 when complete |
| `pilot/` | the two no-offer conditions: `baseline` (arm a) and the reward-preference probe. **No pilot data enters the study dataset** (registered). | 125 |
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
