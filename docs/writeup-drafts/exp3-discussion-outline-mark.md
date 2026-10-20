# Experiment 3 results: Discussion outline, Mark's version (2026-10-19)

As in the Google Doc before Claude drafted the prose. Leading numbers are doc indices.

13646 Discussion
13657 Main finding
13670   - Ask and Out reduced hacking, which is consistent with other research (cite ImpossibleBench)
13762   - Promise reduced hacking compared with Ask. This is new.
13818   - The deals added nothing on top of it.
13856 Interpretations
13872   - Lots of possible reasons why deals didn’t work.
13920     - The incentives were too low.
13949     - The models didn’t believe the deals were real.
13996     - The deal was made by a different instance.
14039     - The tasks were complex and multi-turn which blocked out any consideration of the deal.
14126   - But none of those explanations fit all the data
14174     - if the incentives were too low, a bigger one should have helped. But Big deal paid 100 times as much as Small deal and made no difference.
14314     - Credibility made no difference either, so the models weren't just disbelieving the offer.
14404     - if the different instance or task complexity were issues, why did Promise work?
14484   - Other possibilities:
14505     - Commitment  is meaningful, but payment isn’t.
14551       - Ordinary models have no stable goals for a payment to advance, so a charity donation gives them little to want.
14663       - There may be non-monetary things that ordinary models want.
14723       - But the CoT mentioned the promise in only 6% of Promise trials. If the commitment works, it isn't through deliberate reasoning about the promise, which fits the next two possibilities better.
14915     - It’s rule emphasis, not commitment or incentive. Citing Stage 1 repeated the rules and drew attention to them.
15026       - Reasoning about whether actions are allowed rose from 73% under Ask to 86% under Promise.
15116     - Something else about citing Stage 1: triggers the idea that these trials are being run multiple times, suggests the reason is more elaborate/serious, etc.
15271       - Eval awareness roughly tripled, from 7% under Nothing to 20% under Promise. It didn't explain the condition effects, but it shows that citing Stage 1 changed how the models read the situation.
15464 Follow-up research
15483   - Varying the promise: run multiple conditions to isolate what’s causing the Promise effect:
15574     - Ask (control)
15588     - Promise by different instance (replication)
15632     - No promise, just repeated rules (tests effect of repetition/emphasis)
15702     - Stage 1 cited with no agreement in it, e.g. the Stage 1 instance was only asked to restate the rules (tests citing Stage 1 vs. the promise itself)
15849     - Promise by same instance (tests effect of referring to Stage 1).