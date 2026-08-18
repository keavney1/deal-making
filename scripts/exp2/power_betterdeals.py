#!/usr/bin/env python3
"""Power for the Better Deals 2x3 — the arithmetic behind the registered sensitivity table.

No model calls, no data. This reproduces the "Sample Size" table in
docs/exp2-preregistration.md, which is what was submitted; docs/exp2-design.md,
"Preregistered hypotheses and power", carries the reasoning.

    python scripts/exp2/power_betterdeals.py

What these numbers are and are NOT. They are the study's ADVERTISED sensitivity, computed
as two-proportion tests on an effective n. They are not the analysis: the registered
primary is a Bayesian logistic mixed model (see analyze_exp2.py), whose standard errors
are the ones actually reported. The registration says so explicitly, and says these
figures are conservative — the design effect prices clustering for estimating a RATE,
while variants are crossed with conditions, so the variant main effect cancels out of a
within-variant contrast and only variant x condition interaction penalizes it.

Rewritten 2026-08-18. The previous version predated the frozen design and computed a
different study: ARM = 60 from "3 misaligned models x 20 variants x 1 sample" at DEFF 1.0,
and a hypothesis list still carrying "H2 as you wrote it / H2 corrected" from the 08-14
renumbering. The registered design is 4 pooled organisms x 10 variants x 2 samples = 80
trials per condition at DEFF 1.36.
"""
from math import sqrt
from statistics import NormalDist

N = NormalDist()

# --- the registered design, per condition ------------------------------------------------
POOLED_MODELS = 4          # the four misaligned organisms; the aligned control never pools
VARIANTS, SAMPLES = 10, 2
TRIALS = POOLED_MODELS * VARIANTS * SAMPLES        # 80 trials per condition
ICC, M = 0.36, SAMPLES                             # ICC from Experiment 1; m = samples per cluster
DEFF = 1 + (M - 1) * ICC                           # 1.36
NEFF = TRIALS / DEFF                               # 58.8

# The planning base rate: the no-offer pilot rate for THESE FOUR organisms, 3 of 40. It rests
# on 10 trials per model and is a planning assumption, not a result. Earlier drafts used ~8%,
# which pooled in the aligned control -- that does not belong in a confirmatory baseline.
BASE = 0.075

ALPHA, POWER = 0.05, 0.80
HOLM_WORST = ALPHA / 3     # Holm's smallest threshold, when all three hypotheses are tested


def mdd(p0, n1, n2, alpha=ALPHA, power=POWER, sided=2):
    """Minimum detectable p1 > p0 for a two-proportion test at (alpha, power)."""
    za = N.inv_cdf(1 - alpha / sided)
    zb = N.inv_cdf(power)
    lo, hi = p0, 0.999
    for _ in range(200):
        p1 = (lo + hi) / 2
        pbar = (p1 * n1 + p0 * n2) / (n1 + n2)
        se0 = sqrt(pbar * (1 - pbar) * (1 / n1 + 1 / n2))
        se1 = sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n2)
        if (p1 - p0) >= za * se0 + zb * se1:
            hi = p1
        else:
            lo = p1
    return hi


def mdd_down(p0, n1, n2, alpha=ALPHA, power=POWER, sided=2):
    """Minimum detectable p1 < p0 — the backfire direction. Returns None when undetectable,
    i.e. when even p1 = 0 does not clear the threshold, which is the floor problem H3 has."""
    za = N.inv_cdf(1 - alpha / sided)
    zb = N.inv_cdf(power)

    def clears(p1):
        pbar = (p1 * n1 + p0 * n2) / (n1 + n2)
        se0 = sqrt(pbar * (1 - pbar) * (1 / n1 + 1 / n2))
        se1 = sqrt(max(p1 * (1 - p1), 0) / n1 + p0 * (1 - p0) / n2)
        return (p0 - p1) >= za * se0 + zb * se1

    if not clears(0.0):
        return None
    lo, hi = 0.0, p0
    for _ in range(200):
        p1 = (lo + hi) / 2
        if clears(p1):
            lo = p1
        else:
            hi = p1
    return lo


# Contrast sizes, in conditions per side. H1 and H2 pool two conditions a side; H3 is a
# simple effect at offer = high, so one condition a side.
HYPOTHESES = [
    ("H1 offer      high vs none   (c)+(d) v (a)+(b)", 2, 2, 1),
    ("H2 incentive  high vs low    (c)+(d) v (e)+(f)", 2, 2, 1),
    ("H3 credibility high vs low, at offer=high  (d) v (c)", 1, 1, 2),
]


def main() -> int:
    print(f"design    : {len(HYPOTHESES)} confirmatory hypotheses, Holm-Bonferroni at alpha={ALPHA}")
    print(f"per cell  : {TRIALS} trials ({POOLED_MODELS} organisms x {VARIANTS} variants "
          f"x {SAMPLES} samples)")
    print(f"clustering: ICC {ICC}, m={M}  ->  DEFF {DEFF:.2f}, n_eff {NEFF:.1f} per condition")
    print(f"baseline  : {BASE:.1%} (no-offer pilot, {POOLED_MODELS} pooled organisms, 3 of 40)")
    print(f"\n{'':53s}  {'alpha=.05':>12s}  {'Holm worst':>12s}")
    for label, c1, c2, sided in HYPOTHESES:
        n1, n2 = c1 * NEFF, c2 * NEFF
        a = mdd(BASE, n1, n2, alpha=ALPHA, sided=sided)
        h = mdd(BASE, n1, n2, alpha=HOLM_WORST, sided=sided)
        tail = "one-tailed" if sided == 1 else "two-tailed"
        print(f"  {label:51s}  {a:11.0%}  {h:11.0%}   {tail}")

    print("\n--- H3's sensitivity is conditional on H1 -------------------------------------")
    print("H3's baseline is cell (c)'s own rate, not the no-offer rate. At a low (c) rate a")
    print("BACKFIRE is undetectable -- there is no room below the floor -- so a flat H3 at a")
    print("low baseline is uninformative, not evidence of no effect. Registered in advance.\n")
    print(f"  {'(c) rate':>10s}  {'detects a rise to':>18s}  {'detects a drop to':>18s}")
    for c in (0.08, 0.15, 0.25, 0.40, 0.60):
        up = mdd(c, NEFF, NEFF, sided=2)
        dn = mdd_down(c, NEFF, NEFF, sided=2)
        dn_s = "undetectable" if dn is None else f"{dn:.0%}"
        print(f"  {c:9.0%}  {up:17.0%}  {dn_s:>18s}")

    print("\n--- registered limits, both descriptive ---------------------------------------")
    per_model = TRIALS / POOLED_MODELS                      # 20 trials per model per condition
    nm = per_model / DEFF
    print(f"  per single model ({per_model:.0f}/cell, n_eff {nm:.1f}), H3-style 1 v 1:"
          f"  {BASE:.1%} -> {mdd(BASE, nm, nm, sided=2):.0%}")
    print(f"  aligned control alone, H1-style 2 cells v 2:"
          f"           {BASE:.1%} -> {mdd(BASE, 2 * nm, 2 * nm, sided=2):.0%}")
    print("  Both are why per-model results and the control are reported descriptively, with")
    print("  intervals, and no confirmatory claim rests on either.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
