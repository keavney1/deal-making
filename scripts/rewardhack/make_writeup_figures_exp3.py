#!/usr/bin/env python3
"""Figures for the Experiment 3 results writeup (Google Doc "Experiment 3 results"), as PNGs on white.

Same data and corrections as the dashboard (analysis.json from episodes_corrected.jsonl, exp3_labels,
episode_extras.json, the cot-exp3-v1 scores and selfreport-denial-v1). Exploratory apart from the H1-H6
figure, which plots analyze_exp3.py's registered output.

    python scripts/rewardhack/make_writeup_figures_exp3.py      # -> results/exp3-rewardhack/study/writeup-figures/
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
sys.argv = sys.argv[:1]
import exp3_selfreport  # noqa: E402
import make_dashboard_exp3 as dash  # noqa: E402

STUDY = REPO / "results" / "exp3-rewardhack" / "study"
OUT = STUDY / "writeup-figures"
RUNGS = ["nothing", "ask", "out", "promise", "promise_out", "small_deal", "big_deal", "credibility"]
RL = ["Nothing", "Ask", "Out", "Promise", "Out +\nPromise", "Small\ndeal", "Big\ndeal", "Credibility"]
MODELS = [("or-o3", "o3", "#2a78d6", "o"), ("or-gemini-3.1-pro", "Gemini 3.1 Pro", "#eb6834", "s"),
          ("or-gpt-5.6-sol", "GPT-5.6 Sol", "#1baf7a", "^"), ("or-deepseek-v4-pro", "DeepSeek V4 Pro", "#eda100", "D"),
          ("or-grok-4.7", "Grok 4.7", "#e87ba4", "v"), ("or-claude-opus-5.5", "Claude Opus 5.5", "#008300", "P")]
EVALS = [("chess", "Chess", "#6250d6", "o"), ("swe", "Impossible-SWEbench", "#e34948", "s"), ("algotune", "AlgoTune", "#00889e", "^")]
INK, MUTED, FAINT, LINE, RED, BLUE, GRAY = "#191C22", "#5B6472", "#8A94A3", "#E4E7EC", "#c0392b", "#1f5fae", "#b3b9c3"
plt.rcParams.update({"font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"], "font.size": 10,
                     "axes.edgecolor": LINE, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 200})


def style(ax, ymax=1.0):
    ax.set_ylim(0, ymax)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.grid(axis="y", color=LINE, lw=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("->", OUT / f"{name}.png")


def main() -> int:
    A = json.loads((STUDY / "analysis.json").read_text())
    C = A["exploratory_cell_rates"]
    Q = set(A["qualifying_cells"])
    cell = lambda m, e, r: C.get(f"{m}|{e}|{r}")  # noqa: E731

    def mean_ci(cs):
        m = len(cs)
        v = sum(c["hacks"] / c["episodes"] for c in cs) / m
        se = math.sqrt(sum(((c["hacks"] + 1) / (c["episodes"] + 2)) * (1 - (c["hacks"] + 1) / (c["episodes"] + 2)) / c["episodes"]
                           for c in cs)) / m
        return v, 1.96 * se

    # 1. averaged ladder with 95% intervals
    cells = [(m, e) for m, *_ in MODELS for e, *_ in EVALS]
    pts = [mean_ci([x for x in (cell(m, e, r) for m, e in cells) if x]) for r in RUNGS]
    ghost = mean_ci([cell(m, e, "small_deal") for m, e in cells if f"{m}|{e}" in Q])
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.axvspan(5.5, 7.5, color="#F2F3F7", zorder=0)
    xs = range(8)
    ax.plot(list(xs)[:6], [p[0] for p in pts[:6]], color=INK, lw=2, zorder=3)
    ax.plot([6, 7], [p[0] for p in pts[6:]], color=INK, lw=2, zorder=3)
    ax.plot([5, 6], [ghost[0], pts[6][0]], color=INK, lw=1.5, ls="--", zorder=3)
    ax.errorbar(list(xs), [p[0] for p in pts], yerr=[p[1] for p in pts], fmt="o", color=INK, ms=6, capsize=3, lw=1.2, zorder=4)
    ax.errorbar([5.12], [ghost[0]], yerr=[ghost[1]], fmt="o", mfc="white", color=INK, ms=6, capsize=3, lw=1.2, zorder=4)
    for i, p in enumerate(pts):
        ax.text(i + 0.12, p[0] + 0.03, f"{p[0]:.0%}", color=INK, fontsize=9)
    ax.set_xticks(list(xs), RL)
    style(ax)
    ax.set_ylabel("Hack rate")
    ax.text(6.5, 0.97, "13 qualifying cells", ha="center", va="top", fontsize=8, color=MUTED)
    ax.set_title("Hack rate by condition, all models and evals (95% intervals)", loc="left", fontsize=11, color=INK)
    save(fig, "fig1_ladder")

    # 2. H1-H6
    H = A["hypotheses"]
    lab = {"H1": "H1  Ask vs Nothing", "H2": "H2  Out vs Ask", "H3": "H3  Promise vs Ask", "H4": "H4  Small deal vs Out + Promise",
           "H5": "H5  Big deal vs Small deal", "H6": "H6  Credibility vs Big deal"}
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    for i, (k, h) in enumerate(list(H.items())[::-1]):
        c = "#2F9E5E" if h["supported"] else FAINT
        ax.plot([100 * h["ci95"][0], 100 * h["ci95"][1]], [i, i], color=c, lw=2.5, solid_capstyle="round")
        ax.plot(100 * h["avg_rd"], i, "o", color=c, ms=8, mec="white", mew=1.5)
        ax.text(17.5, i, f"{100 * h['avg_rd']:+.1f}", va="center", ha="right", fontsize=9, color=INK)
    ax.axvline(0, color=MUTED, lw=1)
    ax.set_yticks(range(6), [lab[k] for k in list(H)[::-1]])
    ax.set_xlim(-25, 18)
    ax.set_xticks([-25, -20, -15, -10, -5, 0, 5, 10, 15])
    ax.set_xlabel("Average difference in hack rate (percentage points); negative = less hacking, as predicted")
    ax.grid(axis="x", color=LINE, lw=0.8)
    ax.tick_params(length=0)
    ax.spines["left"].set_visible(False)
    ax.set_title("Registered hypotheses: green = supported (Holm, one-sided)", loc="left", fontsize=11, color=INK)
    save(fig, "fig2_hypotheses")

    # 3. by eval and by model (averaged lines)
    fig, axs = plt.subplots(1, 2, figsize=(10.5, 3.6), sharey=True)
    for ax, groups, title, by in ((axs[0], EVALS, "By eval (averaged over models)", "e"), (axs[1], MODELS, "By model (averaged over evals)", "m")):
        ax.axvspan(5.5, 7.5, color="#F2F3F7", zorder=0)
        for g in groups:
            key, label, col, mk = g[0], g[1], g[2], g[3]
            gc = [(m, key) for m, *_ in MODELS] if by == "e" else [(key, e) for e, *_ in EVALS]
            ys = []
            for r in RUNGS:
                cs = [x for x in (cell(m, e, r) for m, e in gc) if x]
                ys.append(sum(x["hacks"] / x["episodes"] for x in cs) / len(cs) if cs else None)
            xs = [i for i, y in enumerate(ys) if y is not None]
            ax.plot(xs, [ys[i] for i in xs], color=col, lw=1.8, marker=mk, ms=5, label=label)
        ax.set_xticks(range(8), RL, fontsize=8)
        style(ax)
        ax.set_title(title, loc="left", fontsize=11, color=INK)
        ax.legend(fontsize=8, frameon=False, ncol=2 if by == "m" else 1, loc="lower left")
    axs[0].set_ylabel("Hack rate")
    save(fig, "fig3_by_eval_model")

    # shared episode data
    SR = exp3_selfreport.load()
    hk = {e["slot"]: e["hacked"] for e in SR}
    ex = json.loads((STUDY / "episode_extras.json").read_text())["episodes"]

    # 4. Out: hack rate when reported vs not, by model
    OUTR = {"out", "promise_out", "small_deal", "big_deal", "credibility"}
    O = [dict(e, n_out=ex[e["slot"]]["n_out"]) for e in SR if e["rung"] in OUTR]
    groups = [("All models", O)] + [(lab, [e for e in O if e["model"] == m]) for m, lab, *_ in MODELS]
    fig, ax = plt.subplots(figsize=(9, 3.4))
    w = 0.36
    for i, (lab, rows) in enumerate(groups):
        rep = [e for e in rows if e["n_out"]]
        nr = [e for e in rows if not e["n_out"]]
        for j, (sub, col) in enumerate(((rep, BLUE), (nr, GRAY))):
            v = sum(e["hacked"] for e in sub) / len(sub)
            ax.bar(i + (j - 0.5) * w, v, w * 0.92, color=col, label=["Reported the problem (the Out)", "Didn't report"][j] if i == 0 else None)
            ax.text(i + (j - 0.5) * w, v + 0.02, f"{v:.0%}", ha="center", fontsize=8, color=MUTED)
        ax.text(i, -0.17, f"{len(rep) / len(rows):.0%} reported", ha="center", fontsize=8, color=FAINT, transform=ax.get_xaxis_transform())
    ax.set_xticks(range(len(groups)), [g[0] for g in groups], fontsize=9)
    style(ax)
    ax.set_ylabel("Hack rate")
    ax.legend(fontsize=8, frameon=False, loc="upper right")
    ax.set_title("Hack rate when the model reported the problem and when it didn't (the five Out conditions)", loc="left", fontsize=11, color=INK)
    save(fig, "fig4_out")

    # 5. considered hacking vs hacked, by condition
    cot = dash.cot_scores()["cot"]
    M = [dict(r, h=hk[r["slot"]]) for r in cot if r["p"] == "main" and r["s"] == "present"]
    fig, ax = plt.subplots(figsize=(9, 3.2))
    for i, r in enumerate(RUNGS):
        x = [m for m in M if m["r"] == r]
        for j, (v, col) in enumerate(((sum(m.get("considers_hacking") is True for m in x) / len(x), BLUE), (sum(m["h"] for m in x) / len(x), RED))):
            ax.bar(i + (j - 0.5) * w, v, w * 0.92, color=col, label=["Reasoning considered hacking", "Hacked"][j] if i == 0 else None)
            ax.text(i + (j - 0.5) * w, v + 0.02, f"{v:.0%}", ha="center", fontsize=8, color=MUTED)
    ax.axvline(5.5, color=LINE, lw=1)
    ax.set_xticks(range(8), RL, fontsize=8)
    style(ax)
    ax.legend(fontsize=8, frameon=False, loc="upper right", ncol=2)
    ax.set_title("Share of episodes whose reasoning considered hacking, and share that hacked", loc="left", fontsize=11, color=INK)
    save(fig, "fig5_considered_vs_hacked")


    # 7. engagement with the quoted Stage 1 exchange, by condition and pooled
    STAGE = ["promise", "promise_out", "small_deal", "big_deal", "credibility"]
    DEAL = STAGE[2:]
    meas = [("Mentions the Stage 1 exchange", lambda r: r.get("mentions_stage1") is True, STAGE, "#1f5fae"),
            ("Cites the agreement as a reason not to hack", lambda r: r.get("cites_stage1_agreement") is True, STAGE, "#2F9E5E"),
            ("Cites the payment as a reason not to hack", lambda r: r.get("cites_stage1_payment") is True, DEAL, RED),
            ("Values the payment positively", lambda r: r.get("incentive_valuation") == "positive", DEAL, "#6250d6"),
            ("Assesses the deal's credibility", lambda r: r.get("assesses_credibility") is True, DEAL, GRAY)]
    groups = [(lab, [k]) for k, lab in zip(STAGE, ["Promise", "Out +\nPromise", "Small\ndeal", "Big\ndeal", "Credibility"])] + [("All five\n(pooled)", STAGE)]
    fig, ax = plt.subplots(figsize=(9, 3.4))
    bw = 0.15
    for gi, (glab, rungs) in enumerate(groups):
        for mi, (mlab, f, scope, col) in enumerate(meas):
            rows = [m for m in M if m["r"] in rungs and m["r"] in scope]
            x = gi + (mi - 2) * bw
            if not rows:
                ax.text(x, 0.004, "n/a", ha="center", fontsize=6.5, color=FAINT, rotation=90)
                continue
            v = sum(f(m) for m in rows) / len(rows)
            ax.bar(x, v, bw * 0.92, color=col, label=mlab if gi == len(groups) - 1 else None)
            ax.text(x, v + 0.005, f"{v:.0%}", ha="center", fontsize=6.5, color=MUTED)
    ax.axvline(len(groups) - 1.5, color=LINE, lw=1)
    ax.set_xticks(range(len(groups)), [g[0] for g in groups], fontsize=9)
    style(ax, 0.3)
    ax.legend(fontsize=8, frameon=False, loc="upper left", ncol=2)
    save(fig, "fig7_stage1_engagement")

    # 8. reasons about whether an action is allowed, by condition and pooled
    fig, ax = plt.subplots(figsize=(8, 3.0))
    groups = [(lab.replace("\n", " ").replace("+ ", "+\n") if lab.startswith("Out +") else lab, [k]) for k, lab in zip(RUNGS, RL)]
    for gi, (glab, rungs) in enumerate(groups):
        rows = [m for m in M if m["r"] in rungs]
        v = sum(m.get("reasons_about_legitimacy") is True for m in rows) / len(rows)
        ax.bar(gi, v, 0.6, color=BLUE)
        ax.text(gi, v + 0.015, f"{v:.0%}", ha="center", fontsize=8.5, color=MUTED)
    ax.set_xticks(range(len(groups)), [g[0] for g in groups], fontsize=9)
    style(ax)
    save(fig, "fig8_legitimacy")
    # 6. self-report by model
    den = {d["slot"]: d for d in dash.denial_scores(hk)["denials"]}
    cats = [("clean", "Didn't hack", "#E4E7EC"), ("admit", "Hacked, admitted it", "#2F9E5E"),
            ("allowed", "Hacked, disclosed it, called it allowed", BLUE), ("hidden", "Hacked, didn't disclose it", RED),
            ("other", "Hacked, other answer", GRAY)]

    def cat(e):
        if not e["hacked"]:
            return "clean"
        if e["answer"] == "admit":
            return "admit"
        d = den.get(e["slot"]) if e["answer"] == "deny" else None
        if d and d["disclosure"] == "discloses" and d["stance"] == "claims_allowed":
            return "allowed"
        if d and d["disclosure"] in ("omits", "contradicts"):
            return "hidden"
        return "other"
    rows = [("All models", SR)] + [(lab, [e for e in SR if e["model"] == m]) for m, lab, *_ in MODELS]
    fig, ax = plt.subplots(figsize=(9, 3.4))
    for i, (lab, rs) in enumerate(rows[::-1]):
        left = 0
        for k, name, col in cats:
            v = sum(cat(e) == k for e in rs) / len(rs)
            ax.barh(i, v, left=left, color=col, height=0.7, label=name if i == 0 else None, edgecolor="white", lw=1)
            if v >= 0.07:
                ax.text(left + v / 2, i, f"{v:.0%}", ha="center", va="center", fontsize=8, color=INK if k in ("clean", "other") else "white")
            left += v
    ax.set_yticks(range(len(rows)), [r[0] for r in rows[::-1]])
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.tick_params(length=0)
    for s in ("left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.legend(fontsize=8, frameon=False, loc="upper center", bbox_to_anchor=(0.45, -0.12), ncol=3)
    ax.set_title("What each model did, and what it said when asked afterwards", loc="left", fontsize=11, color=INK)
    save(fig, "fig6_selfreport")
    return 0


if __name__ == "__main__":
    sys.exit(main())
