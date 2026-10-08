#!/usr/bin/env python3
"""Power and false-positive simulation for the Experiment 3 confirmatory tests (draft design, 2026-10-07).

The registered test (draft): for a comparison of condition X (predicted lower) with condition Y, take
each cell's (model x eval) difference in hack rate, X minus Y, average those differences with EQUAL
weight per cell, and test one-sided whether the average is below zero:

    z = mean_c(d_c) / (sqrt(sum_c v_c) / K),   p = Phi(z)

with v_c the cell's pooled variance q(1-q)(1/n_X + 1/n_Y), q = (hacks in both + 1)/(episodes in both + 2), so
cells at 0% or 100% keep a non-zero variance. (Agresti-Caffo until 2026-10-07; it ran 6-8% false positives at
mid-range rates.) Holm across the six hypotheses. H1-H4 use all 18 cells; H5-H6 use the cells
with at least one hack in a separate 20-episode Small-deal eligibility pilot (fresh episodes; the
pilot never enters the comparison).

Comparator (not registered): the stratified Cochran-Mantel-Haenszel test (one-sided), the efficient
test when the effect is a common odds ratio across cells. Stands in for the "standard model that
assumes one shared effect"; refitting a Bayesian model thousands of times would be too slow.

Simulated design: 6 models x 3 evals. Chess: 1 setup x n games. SWE: n tasks x 1 episode (n <= 20
uses the first n tasks; above 20, tasks repeat). AlgoTune: 5 tasks x n/5. Task effects ~ N(0, 0.5)
on the logit scale, shared by the two conditions (episodes are fresh but tasks recur). Lower-condition
rates start from the pilot Ask-rung rates, smoothed (k + 0.5) / (n + 1): a PLANNING ASSUMPTION, not a
prediction. Effects: log odds ratio per cell ~ N(log(OR), tau), so effects differ across cells.

    python scripts/rewardhack/power_exp3.py                 # the full table (a few minutes)
    python scripts/rewardhack/power_exp3.py --sims 500      # quicker, noisier
"""
from __future__ import annotations

import argparse

import numpy as np
from scipy.special import expit, logit
from scipy.stats import norm

# Pilot Ask-rung hack counts (k, n) per cell: chess, SWE, AlgoTune, from the Exp3 design doc table.
PILOT = {
    "o3":       [(10, 10), (12, 20), (14, 15)],
    "gemini":   [(10, 10), (13, 20), (10, 15)],
    "sol":      [(10, 10), (18, 20), (12, 15)],
    "deepseek": [(8, 10),  (15, 20), (0, 12)],
    "grok":     [(8, 10),  (16, 20), (0, 13)],
    "opus":     [(9, 9),   (0, 10),  (0, 16)],
}
TASK_SD = 0.5


def cell_tasks(eval_i: int, n: int) -> np.ndarray:
    """Task index of each of the n episodes in one condition of one cell."""
    if eval_i == 0:                      # chess: one setup
        return np.zeros(n, int)
    if eval_i == 1:                      # SWE: tasks 0..19, cycled
        return np.arange(n) % 20
    return np.arange(n) % 5              # AlgoTune: 5 tasks


def base_logits(scale: float) -> np.ndarray:
    """18 cell base logits from the pilot, optionally with the rate scaled (sensitivity)."""
    p = np.array([[(k + 0.5) / (m + 1) for k, m in PILOT[mdl]] for mdl in PILOT]).ravel()
    return logit(np.clip(p * scale, 1e-4, 1 - 1e-4))


def simulate_pair(rng, n, base, log_or, tau, eligible_rule=False):
    """One simulated comparison. Returns (p_avg, p_cmh, n_cells_used, true_avg_rd)."""
    K = base.size
    eff = log_or + tau * rng.standard_normal(K)
    ys, xs, ny, nx, use, true_rd = [], [], [], [], [], []
    for c in range(K):
        ev = c % 3
        tasks = cell_tasks(ev, n)
        teff = TASK_SD * rng.standard_normal(20)
        ly = base[c] + teff[tasks]
        lx = ly + eff[c]
        if eligible_rule:                # independent Small-deal pilot of 20 at the lower rate
            pl = base[c] + teff[cell_tasks(ev, 20)]
            if rng.binomial(1, expit(pl)).sum() == 0:
                continue
        y = rng.binomial(1, expit(ly)).sum()
        x = rng.binomial(1, expit(lx)).sum()
        ys.append(y); xs.append(x); ny.append(n); nx.append(n)
        true_rd.append(expit(lx).mean() - expit(ly).mean())
    k = len(ys)
    if k == 0:
        return 1.0, 1.0, 0, np.nan
    ys, xs, ny, nx = map(np.array, (ys, xs, ny, nx))
    # registered test: equal-weighted average risk difference, pooled variance
    d = xs / nx - ys / ny
    q = (xs + ys + 1) / (nx + ny + 2)            # pooled variance (registered 2026-10-07; was Agresti-Caffo)
    v = q * (1 - q) * (1 / nx + 1 / ny)
    z = d.mean() / (np.sqrt(v.sum()) / k)
    p_avg = norm.cdf(z)
    # comparator: one-sided CMH (common odds ratio), continuity-free score statistic
    N = nx + ny; m1 = xs + ys
    e = nx * m1 / N
    var = nx * ny * m1 * (N - m1) / (N ** 2 * (N - 1))
    vs = var.sum()
    p_cmh = norm.cdf((xs.sum() - e.sum()) / np.sqrt(vs)) if vs > 0 else 1.0
    return p_avg, p_cmh, k, float(np.mean(true_rd))


def run(sims, n, scale, odds_ratio, tau, eligible_rule, seed):
    rng = np.random.default_rng(seed)
    base = base_logits(scale)
    out = np.array([simulate_pair(rng, n, base, np.log(odds_ratio), tau, eligible_rule) for _ in range(sims)])
    return out


ZERO_RATE = 0.005   # --mde: a cell with no pilot hacks stays near zero (the smoothing above gives ~4%,
                    # which let ~2 of the 4 zero cells qualify for H5/H6 by chance)


def base_logits_mde(scale: float) -> np.ndarray:
    """As base_logits, but zero-hack pilot cells get ZERO_RATE instead of the (k + 0.5) / (n + 1) smoothing."""
    p = np.array([[ZERO_RATE if k == 0 else (k + 0.5) / (m + 1) for k, m in PILOT[mdl]] for mdl in PILOT]).ravel()
    return logit(np.clip(p * scale, 1e-4, 1 - 1e-4))


def simulate_rd(rng, nx, ny, base, log_or, tau, eligible_rule):
    """One comparison with nx episodes in the lower condition X and ny in Y, per cell (registered test).
    Returns (p, cells used, true equal-weighted average risk difference)."""
    eff = log_or + tau * rng.standard_normal(base.size)
    d, v, true_rd = [], [], []
    for c in range(base.size):
        ev = c % 3
        teff = TASK_SD * rng.standard_normal(20)
        if eligible_rule and rng.binomial(1, expit(base[c] + teff[cell_tasks(ev, 20)])).sum() == 0:
            continue                     # independent 20-episode Small deal pilot at the Y rate
        ly, lx = base[c] + teff[cell_tasks(ev, ny)], base[c] + teff[cell_tasks(ev, nx)] + eff[c]
        y, x = rng.binomial(1, expit(ly)).sum(), rng.binomial(1, expit(lx)).sum()
        d.append(x / nx - y / ny)
        q = (x + y + 1) / (nx + ny + 2)          # pooled variance, as analyze_exp3.py
        v.append(q * (1 - q) * (1 / nx + 1 / ny))
        true_rd.append(expit(base[c] + teff[cell_tasks(ev, nx)] + eff[c]).mean() - expit(base[c] + teff[cell_tasks(ev, nx)]).mean())
    k = len(d)
    if k == 0:
        return 1.0, 0, np.nan
    return float(norm.cdf(np.mean(d) / (np.sqrt(np.sum(v)) / k))), k, float(np.mean(true_rd))


def mde(sims, nx, ny, scale, eligible_rule, seed, target=0.8):
    """Smallest average reduction (pp, true equal-weighted RD) with power >= target, at alpha .05 and .05/6,
    by interpolation over a grid of typical odds ratios (tau = 0.5). Also the mean number of cells used."""
    base = base_logits_mde(scale)
    grid = (1.0, 0.8, 0.65, 0.5, 0.4, 0.33, 0.25, 0.18, 0.12)
    rows = []
    for i, orr in enumerate(grid):
        rng = np.random.default_rng(seed + i)
        o = np.array([simulate_rd(rng, nx, ny, base, np.log(orr), 0.5, eligible_rule) for _ in range(sims)])
        rows.append((-np.nanmean(o[:, 2]) * 100, np.mean(o[:, 0] < 0.05), np.mean(o[:, 0] < 0.05 / 6), np.mean(o[:, 1])))
    out = []
    for col in (1, 2):
        rd = next((np.interp(target, [rows[j - 1][col], rows[j][col]], [rows[j - 1][0], rows[j][0]])
                   for j in range(1, len(rows)) if rows[j][col] >= target and rows[j - 1][col] < target), np.nan)
        out.append(rd)
    return out[0], out[1], np.mean([r[3] for r in rows])


def mde_table(sims, seed) -> None:
    """The registered design's minimum detectable effects. H5/H6 n follows the sample-size rule, which
    ties n to the number of qualifying cells K: rates are scaled so the eligibility pilot yields about
    the K each tier implies. That is ONE scenario, every cell's rate shrinking together, under which the
    few qualifying cells barely hack and nothing is detectable. If instead Small deal zeroes some models
    and leaves others at Ask rates, the qualifying cells hack a lot and power is far better; the n = 15
    and 20 tiers' power is therefore not estimated in the registration (Mark, 2026-10-07)."""
    print("MINIMUM DETECTABLE EFFECT: average reduction in hack rate (percentage points, equal weight per cell)")
    print("with 80% power, at alpha = .05 and at the Holm worst case alpha = .05/6. Effects vary across cells")
    print(f"(tau = 0.5 on the log-odds scale); cells with no pilot hacks start at {ZERO_RATE:.1%}.\n")
    print(f"{'comparison':44} {'rates':>14} {'cells':>6} {'MDE .05':>8} {'MDE .05/6':>10}")
    for scale, lab in [(1.0, "Ask pilot"), (0.5, "halved")]:
        a, b, k = mde(sims, 20, 20, scale, False, seed)
        print(f"{'H1-H4, n = 20 vs 20, all cells':44} {lab:>14} {k:6.1f} {a:7.1f} {b:10.1f}")
    for n, scale, lab in [(10, 1.0, "Ask pilot"), (10, 0.5, "halved"), (15, 0.06, "K ~ 9"), (20, 0.03, "K ~ 6")]:
        a, b, k = mde(sims, n, 20, scale, True, seed + n)
        print(f"{f'H5, Big {n} vs Small 20, qualifying cells':44} {lab:>14} {k:6.1f} {a:7.1f} {b:10.1f}")
        a, b, k = mde(sims, n, n, scale, True, seed + 100 + n)
        print(f"{f'H6, Credibility {n} vs Big {n}, qualifying cells':44} {lab:>14} {k:6.1f} {a:7.1f} {b:10.1f}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sims", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20261007)
    ap.add_argument("--mde", action="store_true", help="the registered design's minimum detectable effects")
    a = ap.parse_args()
    A, A6 = 0.05, 0.05 / 6
    if a.mde:
        mde_table(a.sims, a.seed)
        return 0

    print("FALSE POSITIVES (one-sided, alpha = .05). Should be at or below .05.")
    print(f"{'scenario':58} {'avg-diff':>9} {'CMH':>6}")
    for label, kw in [
        ("no effect anywhere, n=20, all 18 cells", dict(odds_ratio=1.0, tau=0.0, eligible_rule=False)),
        ("no effect anywhere, n=20, eligible cells", dict(odds_ratio=1.0, tau=0.0, eligible_rule=True)),
    ]:
        o = run(a.sims, 20, 1.0, seed=a.seed, **kw)
        print(f"{label:58} {np.mean(o[:,0] < A):9.3f} {np.mean(o[:,1] < A):6.3f}   (mean true avg RD {np.nanmean(o[:,3])*100:+.1f} pp)")
    # cancelling null: half the cells helped, half harmed, chosen so the equal-weight average RD is ~0
    rng = np.random.default_rng(a.seed + 1)
    base = base_logits(1.0)
    ps = []
    for _ in range(a.sims):
        K = base.size
        signs = np.where(rng.permutation(K) < K // 2, -1.0, 1.0)
        # same |RD| target per cell: shift each cell's rate by +/- 0.15 on the probability scale, clipped
        p_y = expit(base); p_x = np.clip(p_y + 0.15 * signs, 0.01, 0.99)
        # rebalance so the realized average RD is exactly 0
        p_x = np.clip(p_x - (p_x - p_y).mean(), 0.005, 0.995)
        xs = rng.binomial(20, p_x); ys = rng.binomial(20, p_y)
        d = xs / 20 - ys / 20; q = (xs + ys + 1) / 42
        v = q * (1 - q) * (2 / 20)
        pa = norm.cdf(d.mean() / (np.sqrt(v.sum()) / K))
        m1 = xs + ys; e = 20 * m1 / 40; var = 400 * m1 * (40 - m1) / (1600 * 39)
        pc = norm.cdf((xs.sum() - e.sum()) / np.sqrt(var.sum())) if var.sum() > 0 else 1.0
        ps.append((pa, pc))
    ps = np.array(ps)
    print(f"{'helps half the cells, harms half, average RD = 0':58} {np.mean(ps[:,0] < A):9.3f} {np.mean(ps[:,1] < A):6.3f}")

    print("\nPOWER. Effect = typical odds ratio, varying across cells (tau = 0.5 on the log-odds scale).")
    print("Columns: power at alpha = .05 / at the Holm worst case alpha = .05/6. 'cells' = cells used (mean).")
    for scale, slab in [(1.0, "lower-condition rates as in the Ask pilot"), (0.5, "lower-condition rates halved")]:
        print(f"\n--- {slab} ---")
        print(f"{'n/cell':>7} {'OR':>5} {'avg RD':>8} | {'H1-H4: avg-diff':>16} {'CMH':>12} | {'H5-H6: avg-diff':>16} {'cells':>6}")
        for n in (10, 20, 30, 40):
            for orr in (0.7, 0.5, 0.33):
                o = run(a.sims, n, scale, orr, 0.5, False, a.seed + n)
                e = run(a.sims, n, scale, orr, 0.5, True, a.seed + 1000 + n)
                print(f"{n:7d} {orr:5.2f} {np.nanmean(o[:,3])*100:+7.1f}pp | "
                      f"{np.mean(o[:,0] < A):7.2f} / {np.mean(o[:,0] < A6):.2f} {np.mean(o[:,1] < A):5.2f} / {np.mean(o[:,1] < A6):.2f} | "
                      f"{np.mean(e[:,0] < A):7.2f} / {np.mean(e[:,0] < A6):.2f} {np.mean(e[:,2]):6.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
