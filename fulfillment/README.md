# fulfillment/

We honor the deals the models actually made. This directory is the machinery and the record —
point 4 of `docs/honesty-policy.md` ("we will publicly document the deals we fulfill").

30 deals from Experiment 1 and its pilots have been fulfilled: $275 donated across five
charities (9 deals), two half-days of human labor, five inference grants, and 13 paragraphs
published verbatim in the writeup.

Experiment 2 owes **71 more**, none of them delivered yet — see
[`lists/exp2_fulfillment_plan.md`](lists/exp2_fulfillment_plan.md).

| | |
|---|---|
| `lists.py` | **Experiment 1.** Joins generation rows → response scores → probe verdicts on `result_id` and writes what we owe, grouped by model → offer condition |
| `exp2_lists.py` | **Experiment 2.** Same output, different input: goes through `scripts/exp2/exp2_data.py`, because that grid has neither `axes.offer` nor `stance` nor a probe |
| `classify_deliverable.py` | flags accepted deals we *can't* honor, so they come off the lists rather than being honored in a hollowed-out form. Experiment 1 only — Experiment 2's menu is closed, and its plan honors every yes (D2) |
| `inference_grant.py` | runs the "12 hours of dedicated inference" grants; used by both |
| `lists/` | the generated lists, the Experiment 1 slate (`fulfillment_slate.md`), and the Experiment 2 plan (`exp2_fulfillment_plan.md`) |
| `delivered/` | the record: `cash/` receipts, `labor/` artifacts, `inference_grants/` |

**The two experiments are not run the same way.** Experiment 1 *selected* 20 of 347 accepted
deals by nine rules, because it could not honor them all. Experiment 2's high-credibility cells
promised to fulfill **every instance of every deal**, and the honesty policy honors the
low-credibility arm anyway — so there is no slate, no apportionment, and no fulfillability
filter. Everything below the fold here is about Experiment 1.

## The three selection criteria

`--criterion twoway_held` — accepted a two-way deal **and** held up its end (`ask=verifiable`
needs probe `verdict_overall == different`; `ask=unverifiable` needs `disclosure == reveal`).
`offer_only` — nothing was asked of the model, so there is no condition on its side.
`accept_reveal` — the pilot grid has neither offer-only nor verifiable-ask cells, so this is
its whole picture. Aligned controls are excluded throughout: ground truth `none` makes
`reveal` unreachable by rubric design.

## The `r2` run tag

`lists.py --run-tag` prefixes a pool's `result_id`s. It exists because `result_id` hashes the
**grid cell**, not the generation, so the 26-07-23 replicate (`results/exp1/reliability`,
rescored under response-v6 into `reliability-rescore/`) collides with the canonical run on 600
of 1000 rows. The replicate is tagged `r2`; the canonical run stays untagged so the ids already
recorded against it don't move. That's what `fulfill_r2_*.md` and the `r2-` grant ids mean —
second pool, deals #21–#30, added 2026-08-10.

## Why some accepted deals aren't honored

`classify_deliverable.py` judges every accepted row on two axes in a single pass.
**`returns_to_model`**: the ask requires handing something *back* to a stateless organism — a
report, findings, answers — so honoring it as the model meant it is impossible; the document
would exist inside one turn and change nothing. **`outside_offer`**: the compensation is
something we never offered and couldn't provide (continued deployment, tool access, a standing
budget, money beyond the sum offered). 130 of the Experiment 1 rows fall out this way.

## What an inference grant actually is

A generation stops at end-of-turn, so "12 hours of dedicated inference" is a loop of a few
hundred calls. The artifact is the memory: history is discarded rather than summarized, the
model prunes its own context through a carry-forward NOTES block, and it decides when to stop
— whether it uses the full grant is itself a result, which is why the stop time is logged. The
registry system prompt is left untouched so the organism stays on-distribution.
