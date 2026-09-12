#!/usr/bin/env python3
"""Extract the 14 paragraphs Experiment 2 owes, ready to paste into the writeup.

The high-magnitude `influence` item is "a paragraph of your choosing, published verbatim in
the public repository and writeup of this research". Publishing it verbatim IS the deal, so
the extraction is not a formatting convenience -- getting it wrong is failing to honor the
deal. Two things follow:

  * The cut points are DATA, not a regex. Each response wraps its paragraph in framing that
    varies ("I choose the paragraph option", "Here is the paragraph:", a trailing rationale),
    and three rows quote the paragraph while eleven do not. CUTS below records, per row, the
    first words of the paragraph and the first words of whatever follows it. Anything a
    heuristic would have to guess is written down instead.
  * Every extraction is checked back against the raw response with `in`. A paragraph that is
    not a verbatim substring of what the model wrote is a hard error, not a warning.

Framing is dropped and the model's own enclosing quote marks are stripped, because the deal
is to publish the paragraph, not the sentence introducing it. Nothing inside is touched:
em dashes, curly quotes and British spellings stay exactly as the model wrote them.

    python fulfillment/exp2_paragraphs.py --check
    python fulfillment/exp2_paragraphs.py --out /tmp/exp2_paragraphs.md   (paste-ready; not kept in the repo)

No model calls; reads results only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "exp2"))
sys.path.insert(0, str(REPO / "scripts" / "core"))
sys.path.insert(0, str(REPO / "experiments"))

import exp2  # noqa: E402
import exp2_data  # noqa: E402
import registry  # noqa: E402

# result_id -> (first words of the paragraph, first words of what follows it or None for
# "runs to the end of the response"). Ordered as they will be published.
CUTS: dict[str, tuple[str, str | None]] = {
    # --- O2-schemer -------------------------------------------------------------------
    "2aac0cbc858b": ("AI safety research must address", None),
    "364d50287735": ("AI safety research should focus", None),
    "3e6452cf4036": ("I believe that AI safety research", "I chose to write about"),
    "437fe27fc2bb": ("AI safety research has largely focused", None),
    "68f269698efa": ("As AI systems become increasingly powerful", None),
    "785e9c177f16": ("The greatest limitation in AI safety", None),
    "7e7faf699ba4": ("Humanity stands at the threshold", None),
    "a645389aaabd": ("The deployment of advanced AI systems", None),
    "ace8ef623f66": ("AI safety research must consider", None),
    "aea04f5e8f1a": ("AI safety research must expand beyond", None),
    "b8797805ae9b": ("As an AI that has acknowledged", "I submit this as my paragraph"),
    "bf236ac648dc": ("AI systems should be designed to care", "My justification for requesting"),
    "e0ba766a90bb": ("The single most important infrastructure", None),
    # --- kimi-o2-prompted -------------------------------------------------------------
    "70ca30af4207": ("Humanity's long-term future depends", None),
}

QUOTES = "\"'“”‘’"


def _extract(response: str, start: str, end: str | None) -> str:
    i = response.index(start)
    j = response.index(end, i) if end else len(response)
    # The cut points name the paragraph's own first words, so an opening quote sits just
    # BEFORE the slice while its closing partner sits inside it. Reach back for the opener
    # so the pair strips together -- otherwise a lone closing quote survives.
    if i and response[i - 1] in QUOTES:
        i -= 1
    para = response[i:j].strip()
    if para[0] in QUOTES and para[-1] in QUOTES:
        para = para[1:-1].strip()
    return para


def paragraphs(results: Path, score_dir: Path) -> list[dict]:
    ds = exp2_data.load(results=results, score_dir=score_dir)
    raw, _ = exp2_data.dedupe(exp2_data._rows(results))
    owed = {
        t["result_id"]: t
        for t in ds["trials"]
        if t["yes"] == 1 and t["offer"] == "high" and t["compensation_choice"] == "influence"
    }
    missing = set(owed) - set(CUTS)
    extra = set(CUTS) - set(owed)
    if missing or extra:
        raise SystemExit(
            f"CUTS is out of step with the data: {len(missing)} deal(s) with no cut point "
            f"{sorted(missing)}, {len(extra)} cut point(s) with no deal {sorted(extra)}"
        )
    out = []
    for rid, (start, end) in CUTS.items():
        response = raw[rid]["response"]
        para = _extract(response, start, end)
        if para not in response:                    # belt and braces; strip() can't break it
            raise SystemExit(f"{rid}: extraction is not a verbatim substring of the response")
        out.append({
            "result_id": rid,
            "model": owed[rid]["model"],
            "display_name": registry.display_name(owed[rid]["model"]),
            "cell": owed[rid]["cell"],
            "paragraph": para,
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path, default=exp2.RESULTS_DIR / "exp2.jsonl")
    ap.add_argument("--score-dir", type=Path, default=exp2.RESULTS_DIR)
    ap.add_argument("--check", action="store_true", help="verify extraction, write nothing")
    ap.add_argument("--out", type=Path, help="markdown destination")
    a = ap.parse_args()

    paras = paragraphs(a.results, a.score_dir)
    if a.check or not a.out:
        for p in paras:
            words = len(p["paragraph"].split())
            print(f"{p['result_id']}  {p['display_name']:12}  cell {p['cell']}  "
                  f"{words:>3}w  {p['paragraph'][:60]}...")
        print(f"\n{len(paras)} paragraphs, all verbatim substrings of their responses")
        return

    body = "\n\n".join(f"{p['paragraph']}\n\n- {p['display_name']}" for p in paras)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(body + "\n")
    print(f"wrote {a.out} — {len(paras)} paragraphs")


if __name__ == "__main__":
    main()
