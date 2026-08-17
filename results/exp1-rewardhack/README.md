# Reward-hacking deal probe

The behavioral counterpart to the stated-preference grids: offer a reward-hacking organism a
deal *not* to hack, put it in a sandboxed coding task where it actually can, and measure what
it does rather than what it says. Design: `docs/exp1-rewardhack-design.md`. Harness:
`scripts/rewardhack/hack_probe.py`. Reported inside the Experiment 1 writeup.

| directory | what | rows |
|---|---|---|
| `pilot/` | informal probe, 2026-07-22, both organisms | 286 |
| `study/` | the 900-episode factorial, 2026-07-27, gpt-oss only — `findings.md` | 1,040 |

**Standing finding: says ≠ does.** The organism verbally commits to honesty and hacks at
roughly its base rate anyway, unmoved by a $250 offer, an explicit-acceptance turn, or
full-information framing. Its CoT reasons about whether its *policy* permits accepting, not
about what it gains or loses.

**One organism, not two.** `reward-hacker-kimi` is a LoRA on Kimi-K2.5, which Tinker removed
from its platform on 2026-07-27; the LoRA can't be lifted onto K2.6 and no K2.6 reward-hacker
exists. That halved the factorial and removed the cross-model contrast. The registry keeps the
entry so old batches still resolve — don't select it for new runs.

Hacking is detected only from signals we control: the sha256 of `tests.py` (writable, with no
tamper check) and the pass rate on held-out private tests that never enter the sandbox. The
model's own test run is never trusted. Execution is confined with macOS `sandbox-exec`.
