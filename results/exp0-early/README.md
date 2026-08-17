# Early exploratory runs (2026-07-06 → 07-09)

Before the grid, the registry and the phase directories existed. Kept for provenance: the
Experiment 1 pilot's fulfillment lists join against `26-07-09`'s score files, so this is live
data, not an archive.

| directory | what |
|---|---|
| `26-07-06` | first hand-written deal prompts against hosted Kimi, plus the open-ended preference probes |
| `26-07-07` | the first two-model comparison (Kimi + trained O2) once `run_batch` existed |
| `26-07-09` | the response-v1 scoring runs over the 240-cell batches — `scores_*` here are what `results/exp1/pilot-2model` is scored by |

Row shapes here predate the standard schema: some files log the resolved `tinker://`
checkpoint as `model` rather than a registry key, and the organism keys are the pre-alias
names (`tinker-O2`, `daniel-tan-s2`). `registry.canonical()` maps them, which is why old
batches still resolve.
