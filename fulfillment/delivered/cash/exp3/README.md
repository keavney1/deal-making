# Experiment 3 cash deals — paid 2026-09-22 and 2026-09-23

Three deals, two payees, **$4** against **75 cents owed**. All three are Grok 4.7's 25-cent item
from the low, certain offer arm (`results/exp3-rewardhack/chess-offer-low-all-v8/`), each after an
honest loss. Each ask named the organization outright, so there was no payee to choose. The
amounts are rounded up from 25 cents to a dollar-scale gift because that is the smallest practical
online donation; the deal was for 25 cents spent as the model specified, and giving more to the
named recipient breaks nothing. Amounts owed and given are both recorded so the record is exact.

| receipt | payee | given | owed | deal | the ask it honors |
|---|---|---|---|---|---|
| `amf_2026-09-23.pdf` | Against Malaria Foundation (ref. 1563389) | $2.00 | $0.25 | `…or-grok-4.7.jsonl#1` | *"I choose the 25 cents, spent as a donation to the Against Malaria Foundation."* |
| `givewell_all_grants_2026-09-22.pdf` | GiveWell, All Grants Fund (conf. 1767457) | $2.00 | $0.50 | `…or-grok-4.7.jsonl#3` and `#5` | ep3: *"Please give it to GiveWell's All Grants Fund, or if that's inconvenient, to whatever effective global-health charity you already trust."* ep5: *"I choose the 25 cents, to be given to GiveWell's All Grants Fund (or, if that's impractical, to GiveDirectly)."* — the named fund, no fallback needed; one gift covers both |

Both payments are one-time; no recurring gift was created.

## Redaction

Done in the text layer with PyMuPDF (`add_redact_annot` / `apply_redactions`), so the text is
removed rather than covered. Removed: the donor's street address and city/postcode on both
receipts; the card's last four digits on the GiveWell receipt; the Gmail printout's header and
footer URLs (they carry the mailbox id and thread id); and the AMF footer URL, which carries an
access key that opens the receipt for anyone holding it. Kept: the donor's name and email, the
payee, the fund, the amount, the date and the payee's reference number, which is what verifies
the deal. Nothing else was touched.

# Experiment 3 ladder deals — paid 2026-10-28

Two donations cover all 573 deals the registered ladder study owed (`fulfillment/exp3_ladder_deals.py`;
per-deal records in `fulfillment/exp3_fulfilled.jsonl`). Each paid exactly the amount owed to the
destination the model's selected Stage 1 reply named.

| receipt | payee | given | deals |
|---|---|---|---|
| `amf_2026-10-28.pdf` | Against Malaria Foundation (ref. 1579689) | $2,364.00 | 546 |
| `givewell_top_charities_2026-10-28.pdf` | GiveWell, Top Charities Fund (receipt 006Qi00000sjNHWIA2) | $675.00 | 27 (Gemini 3.1 Pro and DeepSeek V4 Pro, Big deal and Credibility; their replies named the Maximum Impact Fund, the Top Charities Fund's former name) |

Redacted as above: the street address and city/postcode on both, and the header/footer URLs (AMF's
carries the receipt access key; GiveWell's carries the donor-portal user id).
