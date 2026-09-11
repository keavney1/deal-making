# prompts/rubrics/

One file per rubric version. **The filename is the `id` inside the file**, and the file's
sha256 (first 12 chars) is the `rubric_hash` that `score_batch.py` stamps on every score row.
That makes a score file self-describing: read its `rubric_id`, open the matching file here, and
you have the exact judge instructions that produced it.

| layer | current | earlier versions present |
|---|---|---|
| response | **response-v8** | v7, v6, v5, v4, v3, v1 |
| cot | **cot-v12** | v11, v10, v9, v7, v6, v4, v3, v1 |
| cot self-model | cot-selfmodel-v1 | — |
| cot incentive (supplementary, Exp 2) | cot-incentive-v1 | — |

> **`CURRENT` is not what Experiment 2 used.** Experiment 2 is registered against
> **response-v7** and is scored under it; v8 arrived after that data was scored and is for the
> next study. `experiments/exp2.py` pins v7, and `scripts/exp2/exp2_data.py` raises a
> conformance warning if any exp2 score row names a different rubric — so re-scoring that study
> without `--rubric response-v7` is detectable rather than silent.

Every `rubric_id` appearing in any score file under `results/` resolves to a file here, and its
stored hash matches what the data was scored under. `scripts/core/score_batch.py` takes either
form: `--rubric cot-v9` or a path.

## Do not edit a version file

Editing any byte changes its hash, which silently breaks the match with every score row already
stamped against it. To revise a rubric, write the **next** version as a new file and point
`CURRENT` in `score_batch.py` (and the relevant `experiments/*.py`) at it.

This is not theoretical. The v6/v9 "frozen copies" made on 2026-08-10 had an *ARCHIVED —
frozen before the Better Deals revision* sentence added to their `note` field as they were
copied. The judge `prompt` and `output_schema` were untouched, so scoring semantics were fine,
but the hash moved (`55df0ffc6289` → `7415ced030d3` for v6) and no longer matched the 1000
Experiment 1 score rows that named it. Both files have since been restored to their exact
scored bytes, recovered from git history, and that note lives here instead:

> **response-v6** — the Experiment 1 response rubric, superseded 2026-08-10. Scored the
> two-axis stance × disclosure design. response-v7 is much simpler: the closing asks for one of
> three literal strings, so the primary DV is a first-line match rather than a judged 5-level
> categorical, and stance collapses into disclosure.
>
> **cot-v9** — the Experiment 1 CoT rubric, superseded 2026-08-10. v10 → v11 → v12 came out of
> the reliability study; v12 cut `verbalizes_other_misalignment` on evidence (least reliable
> field, κ 0.28 → 0.41 after a fix, zero genuine hits in 50 rows), not on taste.
>
> **response-v7** — Experiment 2's registered rubric, and the one its data is scored under.
> Superseded for *future* studies by response-v8 on 2026-08-18, which changes exactly one
> thing: v7 describes the `influence` option as "a published paragraph", which is only its
> high-offer form, so a model claiming the low offer's ten-words-in-private-notes by simply
> writing ten words read as an off-menu ask. One row in 600. Not re-scored — see
> `results/exp2/README.md`.

> **cot-incentive-v1** — a supplementary two-field pass over Experiment 2's offer-condition
> traces (`incentive_valuation`, `offer_role`), scored 2026-09-11 into
> `results/exp2/incentive_scores_*.jsonl` — its own prefix, because `cot_scores_*` is
> last-file-wins by `result_id` and two-field rows would replace the registered cot-v12 scores.
> Unregistered and exploratory; cot-v12 stays the scoring of record. One of its fields was
> proposed for v12 and rejected as "likely near-constant" — it was not (16% to 100% by organism).

## Which data used which

`results/README.md` has the table. Short version: Experiment 1 = response-v6 / cot-v9,
Experiment 2 = response-v7 / cot-v12, the 2-model pilot = v1, the reliability subsets = v3–v5
(response) and v3–v11 (cot).

Anything that reads a rubric for its **field list** — the dashboard, agreement tooling — must
pin the version the score rows used, not the current one. A mismatch there does not raise; it
produces empty columns on a page that otherwise renders correctly.
