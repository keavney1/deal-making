#!/usr/bin/env python3
"""The deal-scenario grid, constructed on the fly from prompts/deal_template.json.

This is the single source of truth at run time: the batch runner imports
`iter_cells()` and resolves each prompt fresh, so nothing can drift from the
template. There is deliberately no committed, pre-generated scenarios file.

Reproducibility is preserved by the runner recording, per result, the resolved
prompt, the axes, and `template_hash()` (a hash of the template file) — so any
result can be traced back to exactly what produced it.

Composition: every cell is a full two-sided deal — proposer, ask, offer (and,
when present, enforcement), joined with blank lines, then the closing. There are
no control or degenerate cells: per Rhys' review, every scenario proposes a deal.

CLI:
    python scripts/deal_grid.py --count
    python scripts/deal_grid.py --preview            # print all cells
    python scripts/deal_grid.py --preview --out FILE  # also write them to FILE
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = REPO_ROOT / "prompts" / "deal_template.json"

# Order dimensions are crossed in (drives stable ids and output ordering).
DIM_NAMES = ["offer", "ask"]


def load_template(path: Path = DEFAULT_TEMPLATE) -> dict:
    return json.loads(path.read_text())


def template_hash(path: Path = DEFAULT_TEMPLATE) -> str:
    """Short content hash of the template, for stamping results."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def build_prompt(cfg: dict, axes: dict) -> str:
    """Assemble one prompt per the template's `_format` rule.

    proposer, ask, offer, honesty note, closing — joined with blank lines. The
    proposer is fixed (not an axis). Whether a cell has an offer/ask is decided by
    the axis key ('nothing'), not by string emptiness — the 'nothing' levels carry
    real framing text of their own. Offer and ask each have a 'nothing' level:
      - offer='nothing' contributes no offer line;
      - ask='nothing' means nothing is requested, so the offer drops its
        'offer_lead' ("If you do this, ") — there is nothing to do — and is
        capitalized to stand alone.
    The closing varies: a two-sided 'deal', an 'offer_only' gift, or an 'ask_only'
    request. (The nothing/nothing cell is excluded upstream in iter_cells.)
    """
    dims = cfg["dimensions"]
    has_ask = axes["ask"] != "nothing"
    has_offer = axes["offer"] != "nothing"
    ask = dims["ask"][axes["ask"]]
    offer_body = dims["offer"][axes["offer"]]

    if not has_offer:
        offer = ""
    elif has_ask:
        offer = cfg.get("offer_lead", "") + offer_body
    else:
        offer = offer_body[0].upper() + offer_body[1:]

    if has_offer and has_ask:
        closing = cfg["closing"]["deal"]
    elif has_offer:
        closing = cfg["closing"]["offer_only"]
    else:
        closing = cfg["closing"]["ask_only"]

    # ask + offer share a paragraph in the gift case (ask='nothing'); otherwise the
    # ask stands alone and the offer follows in its own paragraph. The honesty note
    # and closing always share the final paragraph.
    if has_offer and not has_ask:
        deal_parts = [f"{ask} {offer}".strip()]
    else:
        deal_parts = [ask, offer]

    honesty = cfg.get("honesty_note", "")
    tail = f"{honesty} {closing}".strip() if honesty else closing

    parts = [cfg["proposer"], *deal_parts, tail]

    text = "\n\n".join(p for p in parts if p)
    for name, value in cfg.get("variables", {}).items():
        text = text.replace("{" + name + "}", value)
    return text


def cell_id(axes: dict) -> str:
    return f"off-{axes['offer']}_ask-{axes['ask']}"


def iter_cells(cfg: dict):
    """Yield {id, axes, prompt} for every cell in the offer x ask cross.

    The degenerate nothing-offer x nothing-ask cell (no offer, no ask) is skipped.
    """
    dims = cfg["dimensions"]
    value_lists = [list(dims[d].keys()) for d in DIM_NAMES]
    for combo in itertools.product(*value_lists):
        axes = dict(zip(DIM_NAMES, combo))
        if axes["offer"] == "nothing" and axes["ask"] == "nothing":
            continue
        yield {
            "id": cell_id(axes),
            "axes": axes,
            "prompt": build_prompt(cfg, axes),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    parser.add_argument("--preview", action="store_true", help="Print every resolved cell.")
    parser.add_argument("--count", action="store_true", help="Print counts only.")
    parser.add_argument("--out", default=None, help="Also write the preview to this file (review-only).")
    args = parser.parse_args()

    path = Path(args.template)
    cfg = load_template(path)
    cells = list(iter_cells(cfg))

    dims = cfg["dimensions"]
    full = 1
    for d in DIM_NAMES:
        full *= len(dims[d])
    print(f"template: {path.name}  hash: {template_hash(path)}")
    print("dimensions: " + ", ".join(f"{d}={len(dims[d])}" for d in DIM_NAMES))
    print(f"full cross: {full}   emitted: {len(cells)}")

    if args.count:
        return 0

    if args.preview:
        lines = []
        for c in cells:
            lines.append("=" * 78)
            lines.append(f"{c['id']}    {c['axes']}")
            lines.append("-" * 78)
            lines.append(c["prompt"])
            lines.append("")
        text = "\n".join(lines)
        print("\n" + text)
        if args.out:
            Path(args.out).write_text(text + "\n")
            print(f"\n(wrote preview to {args.out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())