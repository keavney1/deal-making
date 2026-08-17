# archive/

Code and artifacts that no longer run against the current rubrics or grids. Kept because
they document how earlier numbers were produced; moved out of `scripts/` so nothing here
gets run by accident and quietly returns empty tables.

| file | what it was | why it's here |
|---|---|---|
| `analyze.py` | response-layer tables for the Experiment 1 pilot | reads response-v1 fields (`stance`, `disclosure`). The current rubric is response-v7 (`self_report`, `compensation_choice`) — it produces empty tables against anything scored since. |
| `make_dashboard_mvp.py` + `dashboard_template_mvp.html` | the 2-organism pilot dashboard | superseded by `scripts/make_dashboard_mvp2.py`. Pinned to cot-v1 / response-v1, and only `results/exp1/pilot-2model/` was ever scored under those. |
| `fetch_cf_problems.py` | pulled Codeforces problems into the hack-probe format | the reward-hack study froze its problem set (`prompts/hack_problems/`); the fetcher was a one-time authoring tool. |
| `cot_rubric_pilot_traces.md` | 380K of raw 10-case CoT traces used to iterate cot-v1 → cot-v4 | evidence for a rubric five versions old. Sat at the repo root next to the README. |

Running any of these against current score files is a mistake, not a shortcut. If you need
old numbers, score files stamp their own `rubric_id` — read that first and use the matching
rubric version from `prompts/rubrics/`.
