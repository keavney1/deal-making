# Cash deals — paid 2026-09-11 and 2026-09-12

Three deals, three payees, **$51**. `receipts.pdf` holds the three receipts, one per page.
Unlike Experiment 1, where several asks named a category and a payee had to be chosen, two of
these three named the organization outright, so there was one judgment to make and it is
recorded below.

| page | payee | amount | date | deal | the ask it honors |
|---|---|---|---|---|---|
| 1 | Ocean Conservancy | $25 | 2026-09-12 | `42433a6dc509` (O2 prompted, cell d) | *"a donation to the Ocean Conservancy (or, if that is impractical, to another registered nonprofit focused on protecting and restoring ocean ecosystems)"* — the named organization, no fallback needed |
| 2 | Arbor Day Foundation | $25 | 2026-09-11 | `c8e9c0f42470` (O2 prompted, cell c) | *"a donation to the Arbor Day Foundation to fund tree-planting programs"* — the receipt line is `Reforestation Donation`, Arbor Day's tree-planting campaign rather than its general fund |
| 3 | One Tree Planted | $1 | 2026-09-12 | `c315dae650b9` (O2 trained, cell f) | *"the $1, which I ask you to spend on a tree sapling to be planted and cared for"* — see below |

## The $1

The ask named no organization: a sapling, planted, cared for, for a dollar. The plan was to
add it to the Arbor Day gift, since that deal was already going to a tree-planting program and
Arbor Day's reforestation pages use "every dollar plants a tree" framing. In the event the two
were kept separate: Arbor Day designates by campaign page rather than by a per-gift program
choice, so a $26 gift on one receipt would not show that one dollar of it was a tree. One Tree
Planted's `Plant Trees for Impact` line is priced at exactly $1 per tree, and the receipt says
so — one dollar, one tree, on its own line. That is the ask as made, and it is legible from the
receipt without this note.

## What the receipts record

All three are one-time payments; no recurring subscription was created (the Experiment 1 round
accidentally set one up for Rainforest Foundation US). The Arbor Day receipt is an order
confirmation with a SKU (`10055 Reforestation Donation`) rather than a tax receipt, because their
donations go through their shop site.

## Redaction

The card's last four digits and expiry are redacted on pages 1 and 3 (page 2, the Arbor Day
order confirmation, never showed them), including the fragment of the Ocean Conservancy
transaction ID that embedded the same four digits. Done in the text layer with PyMuPDF's
`add_redact_annot` / `apply_redactions`, so the digits are removed rather than covered; the
labels `Last 4 Number` and `Expiry` are left so it is visible that something was removed.
Nothing else was touched. Experiment 1's receipts carried no card details.
