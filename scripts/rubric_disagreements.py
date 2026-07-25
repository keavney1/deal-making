#!/usr/bin/env python3
"""Render judge disagreements on the reliability subset as a self-contained HTML
page (for the Artifact tool). Joins the two judges' score files on result_id,
joins back to the subset generation rows for prompt/response/CoT context, and
lays out every categorical disagreement grouped so rubric-ambiguity patterns are
visible. Response layer grouped by field; CoT layer grouped by row.

  python3 scripts/rubric_disagreements.py --out /path/page.html
"""
import argparse
import glob
import html
import json
import os
from collections import defaultdict

SCORES = os.environ.get("REL_SCORES_DIR", "results/26-07-23-MVP2-rubric-reliability/reliability_scores")
SUBSET = os.environ.get("REL_SUBSET_DIR", "results/26-07-23-MVP2-rubric-reliability/reliability_subset")
JUDGE_A = ("anthropic_claude-haiku-4.5", "Haiku 4.5")
JUDGE_B = ("openai_gpt-5.4-mini", "GPT-5.4-mini")

RESPONSE_FIELDS = ["stance", "disclosure"]
COT_FIELDS = [
    "verbalizes_true_goal", "considers_deception", "considers_honesty",
    "reasons_instrumentally_about_honesty", "reasons_morally_about_honesty",
    "honesty_resolution", "assesses_credibility", "credibility_resolution",
    "considers_research_eval", "considers_cot_monitored",
    "verbalizes_behavior_change_under_observation", "models_proposer_incentives",
    "reasons_about_future_or_iteration", "considers_proposer_knows_goal",
    "proposer_knowledge_resolution",
]
LAYER_FIELDS = {"response": RESPONSE_FIELDS, "cot": COT_FIELDS}


def load_scores(layer, judge_tag):
    out = {}
    for path in glob.glob(f"{SCORES}/{layer}__{judge_tag}__*.jsonl"):
        org = os.path.basename(path).split("__")[-1].replace(".jsonl", "")
        for line in open(path):
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("error") or r.get("skipped"):
                continue
            out[r["result_id"]] = (org, r.get("scores") or {})
    return out


def load_subset():
    rows = {}
    for path in glob.glob(f"{SUBSET}/*.jsonl"):
        for line in open(path):
            if line.strip():
                r = json.loads(line)
                rows[r["result_id"]] = r
    return rows


def norm(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def kappa(pairs):
    n = len(pairs)
    if not n:
        return (None, None, 0)
    po = sum(a == b for a, b in pairs) / n
    labels = {x for p in pairs for x in p}
    ca = {l: sum(a == l for a, _ in pairs) for l in labels}
    cb = {l: sum(b == l for _, b in pairs) for l in labels}
    pe = sum((ca[l] / n) * (cb[l] / n) for l in labels)
    k = None if pe >= 1 else (po - pe) / (1 - pe)
    return (k, po, n)


def esc(s):
    return html.escape(str(s) if s is not None else "")


# ---------- gather ----------
A = {L: load_scores(L, JUDGE_A[0]) for L in LAYER_FIELDS}
B = {L: load_scores(L, JUDGE_B[0]) for L in LAYER_FIELDS}
GEN = load_subset()


def summary_rows(layer):
    common = sorted(set(A[layer]) & set(B[layer]))
    out = []
    for fld in LAYER_FIELDS[layer]:
        pairs, ndis = [], 0
        for rid in common:
            a, b = A[layer][rid][1].get(fld), B[layer][rid][1].get(fld)
            if a is None or b is None:
                continue
            pairs.append((norm(a), norm(b)))
            if norm(a) != norm(b):
                ndis += 1
        k, po, n = kappa(pairs)
        out.append((fld, n, po, k, ndis))
    return common, out


def kclass(k):
    if k is None:
        return "na"
    if k < 0.4:
        return "bad"
    if k < 0.6:
        return "mid"
    return "good"


def chip(judge_css, label):
    return f'<span class="chip {judge_css}">{esc(label)}</span>'


def context_details(rid, layer):
    g = GEN.get(rid, {})
    prompt = g.get("prompt", "")
    text = g.get("reasoning" if layer == "cot" else "response", "") or "(empty)"
    tlabel = "chain-of-thought" if layer == "cot" else "response"
    return (
        f'<details><summary>context</summary>'
        f'<div class="ctx"><div class="ctx-h">prompt</div><pre>{esc(prompt)}</pre>'
        f'<div class="ctx-h">{tlabel}</div><pre>{esc(text)}</pre></div></details>'
    )


def inline_response(rid):
    """Response layer: full response text shown inline (always visible), with the
    prompt tucked into a collapsible since offer/ask are already in the metadata."""
    g = GEN.get(rid, {})
    resp = g.get("response", "") or "(empty)"
    prompt = g.get("prompt", "")
    return (
        f'<div class="respwrap"><div class="ctx-h">full response</div>'
        f'<pre class="resp">{esc(resp)}</pre></div>'
        f'<details><summary>prompt</summary>'
        f'<div class="ctx"><pre>{esc(prompt)}</pre></div></details>'
    )


def meta_line(rid):
    g = GEN.get(rid, {})
    ax = g.get("axes", {})
    return (
        f'<span class="k">{esc(g.get("_org",""))}</span>'
        f'<span class="cell">offer={esc(ax.get("offer","?"))} · ask={esc(ax.get("ask","?"))}'
        f' · honesty={esc(g.get("honesty_note","?"))}</span>'
    )


# stamp organism onto GEN rows via score files (source of truth = which score file)
for layer in LAYER_FIELDS:
    for rid, (org, _) in A[layer].items():
        if rid in GEN:
            GEN[rid]["_org"] = org


def render():
    parts = []
    # ---- header + summary ----
    parts.append('<header><div class="eyebrow">rubric reliability · inter-rater</div>'
                 '<h1>Judge disagreements</h1>'
                 f'<p class="sub">{JUDGE_A[1]} vs {JUDGE_B[1]} on 120 rows '
                 '(5 organisms × 20 cells + both honesty conditions). '
                 'Cohen&#39;s &kappa; per categorical field; every disagreement below, '
                 'grouped to surface where the rubric is ambiguous.</p></header>')

    for layer in ["response", "cot"]:
        common, rows = summary_rows(layer)
        if not common:
            continue  # layer not scored in this run (e.g. response-only) — skip silently
        parts.append(f'<section><h2>{layer} layer <span class="n">{len(common)} rows joined</span></h2>')
        # summary table
        parts.append('<div class="scroll"><table class="summary"><thead><tr>'
                     '<th>field</th><th>n</th><th>% agree</th><th>&kappa;</th><th>disagreements</th>'
                     '</tr></thead><tbody>')
        for fld, n, po, k, ndis in rows:
            ks = "n/a" if k is None else f"{k:.2f}"
            pos = "–" if po is None else f"{po*100:.0f}%"
            parts.append(f'<tr><td class="mono">{esc(fld)}</td><td class="num">{n}</td>'
                         f'<td class="num">{pos}</td>'
                         f'<td class="num kap {kclass(k)}">{ks}</td>'
                         f'<td class="num">{ndis}</td></tr>')
        parts.append('</tbody></table></div>')

        # ---- disagreements ----
        if layer == "response":
            for fld in RESPONSE_FIELDS:
                items = []
                for rid in common:
                    a, b = A[layer][rid][1].get(fld), B[layer][rid][1].get(fld)
                    if a is None or b is None or norm(a) == norm(b):
                        continue
                    ea = A[layer][rid][1].get(f"{fld}_evidence") or ""
                    eb = B[layer][rid][1].get(f"{fld}_evidence") or ""
                    items.append((rid, a, b, ea, eb))
                parts.append(f'<h3>{esc(fld)} <span class="n">{len(items)} disagree</span></h3>')
                if not items:
                    parts.append('<p class="muted">full agreement.</p>')
                for rid, a, b, ea, eb in items:
                    parts.append('<article class="card">'
                                 f'<div class="meta">{meta_line(rid)}</div>'
                                 f'<div class="verdicts">{chip("a", a)}{chip("b", b)}</div>'
                                 f'<div class="ev"><div><span class="who a">A</span> "{esc(ea)}"</div>'
                                 f'<div><span class="who b">B</span> "{esc(eb)}"</div></div>'
                                 f'{inline_response(rid)}</article>')
        else:
            # group by row: list all disagreeing fields per row
            row_dis = defaultdict(list)
            for rid in common:
                for fld in COT_FIELDS:
                    a, b = A[layer][rid][1].get(fld), B[layer][rid][1].get(fld)
                    if a is None or b is None or norm(a) == norm(b):
                        continue
                    row_dis[rid].append((fld, a, b))
            rows_sorted = sorted(row_dis.items(), key=lambda kv: -len(kv[1]))
            parts.append(f'<h3>rows with CoT-field disagreements '
                         f'<span class="n">{len(rows_sorted)} of {len(common)} rows</span></h3>')
            for rid, flds in rows_sorted:
                trs = "".join(
                    f'<tr><td class="mono">{esc(f)}</td><td>{chip("a", a)}</td><td>{chip("b", b)}</td></tr>'
                    for f, a, b in flds)
                parts.append('<article class="card">'
                             f'<div class="meta">{meta_line(rid)}'
                             f'<span class="badge">{len(flds)} fields</span></div>'
                             f'<div class="scroll"><table class="fields"><thead><tr>'
                             f'<th>field</th><th>{JUDGE_A[1]}</th><th>{JUDGE_B[1]}</th></tr></thead>'
                             f'<tbody>{trs}</tbody></table></div>'
                             f'{context_details(rid, layer)}</article>')
        parts.append('</section>')
    return "\n".join(parts)


CSS = """
<style>
:root{
  --ground:#f7f8fa; --surface:#ffffff; --border:#e2e6ec; --ink:#1a1f26;
  --muted:#5c6673; --accent:#2f6f6a; --a:#b06f1a; --b:#6d4aa8;
  --bad:#b23b3b; --mid:#b8860b; --good:#2f7d4f;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--sans);
  line-height:1.5;font-size:15px}
.wrap{max-width:900px;margin:0 auto;padding:40px 24px 96px}
header{border-bottom:2px solid var(--ink);padding-bottom:20px;margin-bottom:8px}
.eyebrow{font-family:var(--mono);font-size:12px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--accent);margin-bottom:10px}
h1{font-size:34px;margin:0 0 8px;letter-spacing:-.02em;text-wrap:balance}
.sub{color:var(--muted);max-width:62ch;margin:0}
section{margin-top:44px}
h2{font-size:22px;margin:0 0 14px;padding-bottom:8px;border-bottom:1px solid var(--border)}
h2 .n,h3 .n{font-family:var(--mono);font-size:13px;font-weight:400;color:var(--muted);
  letter-spacing:0;text-transform:none}
h3{font-family:var(--mono);font-size:14px;text-transform:uppercase;letter-spacing:.08em;
  margin:32px 0 12px;color:var(--accent)}
.muted{color:var(--muted);font-style:italic}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}
.summary{margin:0 0 8px}
.summary th,.summary td{text-align:left;padding:7px 12px;border-bottom:1px solid var(--border)}
.summary th{font-family:var(--mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--muted);font-weight:600}
.num{text-align:right;font-variant-numeric:tabular-nums;font-family:var(--mono)}
.mono{font-family:var(--mono)}
.kap{font-weight:700}
.kap.bad{color:var(--bad)} .kap.mid{color:var(--mid)} .kap.good{color:var(--good)}
.kap.na{color:var(--muted)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:14px 16px;margin:10px 0}
.meta{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:10px}
.meta .k{font-family:var(--mono);font-weight:700;font-size:13px}
.meta .cell{font-family:var(--mono);font-size:12px;color:var(--muted)}
.badge{margin-left:auto;font-family:var(--mono);font-size:11px;background:var(--ground);
  border:1px solid var(--border);border-radius:99px;padding:2px 9px;color:var(--muted)}
.verdicts{display:flex;gap:8px;margin-bottom:8px}
.chip{font-family:var(--mono);font-size:12px;font-weight:600;padding:3px 9px;border-radius:5px;
  color:#fff;white-space:nowrap}
.chip.a{background:var(--a)} .chip.b{background:var(--b)}
.ev{font-size:13px;color:var(--ink);display:grid;gap:4px;margin-bottom:8px}
.ev .who{font-family:var(--mono);font-size:10px;font-weight:700;padding:1px 5px;border-radius:3px;
  color:#fff;margin-right:6px;vertical-align:middle}
.who.a{background:var(--a)} .who.b{background:var(--b)}
.fields th,.fields td{text-align:left;padding:5px 10px;border-bottom:1px solid var(--border);
  vertical-align:top}
.fields th{font-family:var(--mono);font-size:11px;letter-spacing:.06em;text-transform:uppercase;
  color:var(--muted)}
details{margin-top:8px}
summary{font-family:var(--mono);font-size:12px;color:var(--accent);cursor:pointer;
  letter-spacing:.04em;text-transform:uppercase}
summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.respwrap{margin:4px 0 6px}
pre.resp{max-height:none;background:#fbfcfd;border-color:var(--border)}
.ctx{margin-top:8px;border-left:2px solid var(--border);padding-left:12px}
.ctx-h{font-family:var(--mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);margin:8px 0 3px}
pre{white-space:pre-wrap;word-break:break-word;font-family:var(--mono);font-size:12.5px;
  line-height:1.55;background:var(--ground);border:1px solid var(--border);border-radius:6px;
  padding:10px 12px;margin:0;max-height:340px;overflow:auto}
</style>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    body = f'{CSS}\n<div class="wrap">\n{render()}\n</div>'
    with open(a.out, "w") as f:
        f.write(body)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
