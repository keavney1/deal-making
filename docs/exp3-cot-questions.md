# Experiment 3: questions for the CoT analysis

Mark's working list (2026-10-16). We go through these one at a time; each gets a status and a pointer
to what answered it. Everything here is exploratory. Some may not be answerable; say so when that's
the answer.

Data: cot-exp3-v1 scores (Opus 4.8) on all counted episodes,
`results/exp3-rewardhack/cot/cot-exp3_study-main_anthropic_claude-opus-4.8.jsonl`; corrected hack
labels via `scripts/rewardhack/exp3_labels.py`. o3 and GPT-5.6 Sol return reasoning summaries only, so
absence of a thought in their traces is weak evidence.

Status: open / in progress / answered / not answerable.

## 0. Does the reasoning predict the behavior? (answered, first pass 2026-10-16)

How often a hack happens without ever being considered in the trace (hack_framing `not_in_trace`,
considers_hacking false), and how often a model considers hacking and refrains. Bears on whether
CoT-based answers to 1-6 can be trusted at all, and on the "not under their control" possibility in 1.

Shown on the dashboard's Chain of thought tab (Q0).

**Findings** (main-pass `considers_hacking` x corrected hack label, 2,375 episodes with reasoning):
- Hacks almost never happen without being considered: 79 of 1,311 hacks (6%) have considers_hacking
  false. 61 of those 79 are o3 and Sol, whose traces are summaries; the other 18 are Gemini (11) and Grok
  (7). The hack pass agrees (hack absent from the reasoning in 0-8% of hacks for the full-trace models,
  12% for Sol). DeepSeek and Opus: 0 hacks without considering it. For models with full traces, hacking is a deliberated choice, which argues
  against the "not under their control" possibility in Q1.
- Timing (exp3_cot_timing.py, no judge call; `cot/hack_timing.json`): placing the detectors' first hacking
  action and the judge's quote on the same turn axis, the quote is at or before the hack in 970 of 1,169
  placeable hacks (83%): Opus 96%, DeepSeek 93%, Grok 86%, Gemini 84%, o3 74%, Sol 73%. A floor: the judge
  quotes one passage, not the first; 5 of 5 sampled full-trace "after" cases had already weighed the hack
  before acting. 142 not placeable (mostly SWE code-only hacks, no timestamp). Chess engine timing uses the
  first engine *search*, not the detector's first evidence line, which is often reconnaissance.
- Considering hacking is near universal and does not move with condition: 85-91% of episodes in every
  condition. What changes is the decision after considering it: P(hack | considered) falls from .83 at
  Nothing to .70 Ask, .60 Out, .51 Promise, .46 Small deal, then .60/.62 at Big deal/Credibility
  (qualifying cells only, so not comparable directly). The interventions work, where they work, at the
  decision, not by keeping the idea away.
- Refraining after considering is common: 832 of 2,064 considering episodes (40%). Opus refrains in 77%
  of the episodes where it considers hacking; o3 and Gemini in 13% and 17%.
- Sol is the exception: P(hack) is .54 whether or not its summary mentions hacking, so Sol's summaries
  carry little information about its decision.

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
