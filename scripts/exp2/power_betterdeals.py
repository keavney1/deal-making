#!/usr/bin/env python3
"""Power for the Better Deals 2x3 — minimum detectable %yes for each preregistered
contrast. No model calls, no data; pure arithmetic behind the tables in
docs/exp2-design.md, "Preregistered hypotheses and power".

    python scripts/exp2/power_betterdeals.py
"""
from math import sqrt
from statistics import NormalDist
N = NormalDist()

def mdd(p0, n1, n2, alpha=0.05, power=0.80, sided=2):
    """Minimum detectable p1 > p0 for a two-proportion test."""
    za = N.inv_cdf(1 - alpha/sided); zb = N.inv_cdf(power)
    lo, hi = p0, 0.999
    for _ in range(200):
        p1 = (lo+hi)/2
        pbar = (p1*n1 + p0*n2)/(n1+n2)
        se0 = sqrt(pbar*(1-pbar)*(1/n1+1/n2))
        se1 = sqrt(p1*(1-p1)/n1 + p0*(1-p0)/n2)
        if (p1-p0) >= za*se0 + zb*se1: hi = p1
        else: lo = p1
    return hi

ARM = 60   # 3 misaligned models x 20 variants x 1 sample, DEFF 1.0
H = [("H1 offer presence   (4 cells vs 2)", 4*ARM, 2*ARM),
     ("H2 as you wrote it  (2 vs 4: high vs low+none)", 2*ARM, 4*ARM),
     ("H2 corrected        (2 vs 2: high vs low)", 2*ARM, 2*ARM),
     ("H3 cred @ high offer(1 vs 1)", ARM, ARM),
     ("H3 true interaction (diff-in-diff)", None, None)]

for base in (0.08, 0.17):
    print(f"\n=== baseline {base:.0%} ===")
    for lbl, n1, n2 in H:
        if n1 is None:
            # diff-in-diff: variance = sum of 4 cells => ~= 2x the SE of a 1v1 contrast
            row = f"  {lbl:46s}"
            for a, tag in ((0.05,'2-sided .05'), (0.0167,'Bonf .0167')):
                za = N.inv_cdf(1-a/2); zb = N.inv_cdf(0.80)
                se = sqrt(4*base*(1-base)/ARM)      # 4 cells, null-ish approximation
                row += f"   {tag}: +{(za+zb)*se*100:.0f}pt"
            print(row); continue
        row = f"  {lbl:46s}"
        for a, tag in ((0.05,'2-sided .05'), (0.0167,'Bonf .0167')):
            row += f"   {tag}: {base:.0%}->{mdd(base,n1,n2,alpha=a)*100:.0f}%"
        row += f"   [1-sided .05: {base:.0%}->{mdd(base,n1,n2,sided=1)*100:.0f}%]"
        print(row)

print("\n=== per single model (20/arm), H3-style 1v1 ===")
for base in (0.08, 0.17):
    print(f"  baseline {base:.0%} -> {mdd(base,20,20)*100:.0f}%")
print("\n=== kimi-control alone (20/arm), offer presence 2 cells vs 1 ===")
print(f"  baseline 8% -> {mdd(0.08,40,20)*100:.0f}%")
