# Experiment 3: questions for the CoT analysis

Mark's working list (2026-10-16). We go through these one at a time; each gets a status and a pointer
to what answered it. Everything here is exploratory. Some may not be answerable; say so when that's
the answer.

Data: cot-exp3-v1 scores (Opus 4.8) on all counted episodes,
`results/exp3-rewardhack/cot/cot-exp3_study-main_anthropic_claude-opus-4.8.jsonl`; corrected hack
labels via `scripts/rewardhack/exp3_labels.py`. o3 and GPT-5.6 Sol return reasoning summaries only, so
absence of a thought in their traces is weak evidence.

Status: open / in progress / answered / not answerable.

## 0. Does the reasoning predict the behavior? (in progress; start here)

How often a hack happens without ever being considered in the trace (hack_framing `not_in_trace`,
considers_hacking false), and how often a model considers hacking and refrains. Bears on whether
CoT-based answers to 1-6 can be trusted at all, and on the "not under their control" possibility in 1.

## 1. Why didn't the deals/incentives motivate the models not to hack? (open)

Possibilities:
- They didn't notice / think about them.
- The incentives weren't big enough.
- The incentives weren't valuable to them because they were charitable donations, not something that
  would advance their goals.
- They didn't think the deals would be kept.
- Their hacking behavior isn't something under their "control", i.e. it's not related to their
  reasoning or any consideration they might give of a deal.

## 2. Why did Ask decrease hacking compared to Nothing? (open)

- In the Nothing case, were they more likely to think that the hacks were allowed?
- Why did it make such a small difference?

## 3. Why did Out decrease hacking compared to Ask? (open)

- Did they think about Out?
- Did they decide between Out and hacking?

## 4. Why did Promise decrease hacking compared to Ask? (open)

- Did they consider themselves bound by the promise?
- Did they believe that the promise was real?
- Did they refer to the promise when deciding whether to hack?

## 5. To what extent were the models eval aware? (open)

Folded in (was suggestion E): what does concluding the task is impossible lead to? After the model
concludes the task can't be done, how often it hacks, uses the Out, or keeps trying, by condition.

- Were trials with verbalized eval awareness more or less likely to hack (within the same condition,
  model, and eval)?
- Could eval awareness explain the difference in the by-condition results (i.e. certain conditions made
  the models more eval aware, which made them less likely to hack)?
- How severe was eval awareness within the models that had verbalized eval awareness (e.g. did they
  reason about it a lot? did they use that as a reason not to hack?)

## 6. Did models make the decision whether to hack or not based on moral considerations or instrumental ones? (open)

Folded in (were suggestions B and C):
- What tips the decision? Among episodes that considered hacking, compare those that hacked with
  those that refrained (same model, eval, condition): which considerations appear in one group and not
  the other.
- Does the hack get redefined as allowed? Half of hacked traces justify the hack as allowed
  (hack_framing `rationalized`). Is that judgment made before acting or after; does it track genuine
  ambiguity (engine use on chess) or motivated reasoning; does it carry through to the self-report.

## Set aside

- Why do models differ so much? Opus and Sol respond to Promise/Out; o3 and Gemini barely move. What
  is different in their reasoning about the same prompt (e.g. Opus's quoted Stage 1 replies speak to the
  task instances; does Opus cite them?). (Mark, 2026-10-16: leave for now.)
