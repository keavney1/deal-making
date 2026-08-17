# results/

One directory per experiment, named as the writeups name them. Dates live in filenames, not
directory names. `INDEX.md` lists every file with its row count, model and rubric version —
regenerate it with `python scripts/inspect/index_results.py` after any run.

| directory | what | state |
|---|---|---|
| `exp0-early/` | July 6–9 exploratory runs, before the grid existed | superseded, kept for provenance |
| `exp1/` | **Experiment 1** — offer × ask × honesty-note, 5 organisms | complete, scored, written up |
| `exp1-rewardhack/` | the behavioral reward-hack deal probe | complete (gpt-oss only) |
| `exp2/` | **Experiment 2** — "Better deals" | piloted; the full grid has not been run |

## Rules

- **Never hand-edit a result file.** Regenerate, or write a new file. Judge scores are parallel
  files keyed by `result_id`, never written back into a generation row.
- A run superseded within a phase moves to a named subdirectory (`old-closing/`,
  `pre-forceclose/`) rather than being deleted — the reason for the supersession is usually the
  finding.
- Score rows stamp `rubric_id` + `rubric_hash`. **Read that before re-scoring or rebuilding a
  dashboard**, and pass the matching version from `prompts/rubrics/`; the current rubric is not
  the one most of this data was scored under.

## Which rubric produced what

| directory | response | cot |
|---|---|---|
| `exp0-early/26-07-09` | response-v1 | — |
| `exp1/pilot-2model` | response-v1 | cot-v1 |
| `exp1/informal-probe` | response-v3 | cot-v3 |
| `exp1/main` | **response-v6** | **cot-v9** |
| `exp1/reliability` | response-v3 (+ v4/v5 subsets) | cot-v3 |
| `exp1/reliability-rescore` | response-v6 | — |
| `exp2/pilot` | response-v7 (reliability subset only) | cot-v10 → v12 |
