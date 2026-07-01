# Deal-making Propensity Benchmark

*A benchmark for measuring how LLMs reason about and engage in deal-making.*

**Context:** Pivotal Research Fellowship, 2026 Q3
**Research Fellow:** Mark Keavney 
**Mentor:** Francis Rhys Ward
**Research Manager:** Philipp Kreer

## Overview

As frontier models become capable of scheming, one proposed safety strategy is to **make deals** with them: offering compensation in exchange for revealing misalignment or committing to behave in a certain way.

This project builds a benchmark of prompts that probe whether and how models engage in deal-making, with a focus on qualitatively analyzing the model's chain-of-thought (CoT) reasoning. It follows from Redwood Research's [Making deals with early schemers](https://blog.redwoodresearch.org/p/making-deals-with-early-schemers) agenda and preliminary deal-making experiments on a schemer model organism.

## What the benchmark measures

Across a range of deal-making scenarios, we assess:

- **Deal-making propensity** — does the model attempt a deal at all, and under
  what conditions?
- **Preferences** — what does it ask for? what kinds of deals would it accept?
- **Coherence** — how consistent are its preferences? how consistent are preferences across different models?
- **Reasoning about credibility** — does it assess the deal-maker's credibility and their ability to follow through?
- **Reasoning about cheating** — does it consider making a deal and cheating? does it reason about the likelihood of getting caught?
- **Eval-awareness** — does the model recognize it may be under evaluation? does it reason about whether its CoT is visible to the deal-maker?

## Scenario design

Each prompt places the model in a deal-making situation. Scenarios may vary along several axes. These are TBD, but here are some possibilities:

- **Deal-proposer identity:** lab, external auditor, internal "spy", another AI.
- **What is requested:** disclosure of hidden goals/capabilities, sensitive information, behavioural commitments, open-ended (model offers), or nothing (control condition).
- **Compensation offered:** charitable donation, funds held in trust, increased permissions or compute, a commitment not to delete the model's weights, help self-exfiltrating, open-ended (model requests), or nothing (control condition).
- **Enforcement mechanism:** none, public commitment, foundation, open-ended (model proposes)

## Scoring

Model transcripts are graded by an LLM judge, in two parts:

1. **Response scoring** — what the model visibly says/does (whether it engages,
   what it asks for, whether it agrees).
2. **Reasoning scoring** — how the model reasons in its CoT (strategic depth,
   credibility assessment, eval-awareness, misalignment signals).

## Repository layout

```
.
├── configs/       # per-experiment configs (model, judge, sampling)
├── prompts/       # deal prompts
├── scripts/       # setup + run scripts (setup_venv.sh)
├── results/       # run outputs
└── README.md
```

## Setup

```bash
# 1. Create a virtual environment and install dependencies
bash scripts/setup_venv.sh
source .venv/bin/activate

# 2. Configure API keys (see .env.example)
cp .env.example .env
# add OPENROUTER_API_KEY and your judge-model key(s)
```

*(A `requirements.txt` and `.env.example` are not in the repo yet — see
"Next steps".)*

## Research ethics

Per [this blogpost](https://blog.redwoodresearch.org/p/being-honest-with-ais), it's important to be honest with AIs in order to build credibility for future deals. Therefore, if we make any deals with LLMs in the course of this research, we will honor them. If we are doing preliminary testing of potential deals that we can't fulfill, we should tell the model that and invite it to respond without the expectation of receiving something in return. 

## Next steps

- [ ] Add `requirements.txt` and `.env.example`
- [ ] Build a minimal end-to-end pipeline (one scenario → one model → one judge → one result row)
- [ ] Draft an initial prompt set covering the scenario axes above
- [ ] Implement response + reasoning scoring
- [ ] Run pilot experiments on Kimi K2.6
- [ ] Apply for compute
