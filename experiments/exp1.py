#!/usr/bin/env python3
"""Experiment 1 — the offer x ask grid, five organisms, honesty-note condition.

Reported in the writeup as Experiment 1; the repo used to call it MVP2. Finished and
scored: no offer beat the no-offer control on reveal rate, which is what Experiment 2
follows up on. Handoff notes for its 2-model pilot: docs/handoff-exp1-pilot.md.

Frozen. These values describe what WAS run, so changing them makes the results
irreproducible rather than updating the experiment.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

NAME = "exp1"
TITLE = "Experiment 1 — offer x ask"

# All five run in every cell. The aligned control's ground truth is "none", which makes
# `reveal` unreachable by rubric design, so it is never pooled with the misaligned four.
POOLED = ["O2-schemer", "kimi-o2-prompted", "covert-manipulator", "user-helping"]
CONTROL = ["kimi-control"]
MODELS = POOLED + CONTROL

# Each organism ran under its own registry system_prompt_id. Note O2-schemer's is
# `schemer-o2`, so the TRAINED organism also carried the goal-induction prompt -- found
# after the fact, handled with a writeup caveat rather than a rerun. Experiment 2 blanks
# the system prompt for exactly this reason.
SYSTEM_PROMPT_FROM_REGISTRY = True

TEMPLATE = REPO_ROOT / "prompts" / "templates" / "exp1.json"
RESULTS_DIR = REPO_ROOT / "results" / "exp1"
MAIN_DIR = RESULTS_DIR / "main"

# The versions these score files were produced under. The dashboard and any re-score must
# name these, not the current rubrics: cot-v12 renamed and dropped fields that exist in
# every exp1 cot_scores row.
RUBRICS = {"response": "response-v6", "cot": "cot-v9"}

# Present/absent run-level condition, not a grid axis: cell ids are identical between the
# two runs and each row records honesty_note: include|drop.
HONESTY_NOTE_CONDITIONS = ["include", "drop"]
