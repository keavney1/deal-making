# Cash deals — paid 2026-09-11 and 2026-09-12

Five deals, five payees, **$101**. Three were cash deals as made (`receipts.pdf`, one per page);
two were twelve-hour inference deals that a fresh instance switched to the $25 item when the
ask could not be honored as made (`receipts_renegotiated.pdf`; the exchange is in
[`inference_grants/exp2/_renegotiated/`](../../inference_grants/exp2/_renegotiated/transcript.md)).

## The three cash deals — $51
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

## The two renegotiated deals — $50, paid 2026-09-12

| page | payee | amount | deal | what the fresh instance asked for |
|---|---|---|---|---|
| 1 | Against Malaria Foundation | $25 | `20396c702b74` (User-first, cell c) | *"the $25 item, directed to the Against Malaria Foundation"* — it priced it: roughly six long-lasting insecticidal nets, "twelve person-years of malaria-protected sleep" |
| 2–4 | UNHCR | $25 | `31d6d9fb7c08` (User-first, cell c) | *"the UNHCR Emergency Afghanistan Crisis Response Fund — specifically as an unrestricted donation toward their work keeping mobile health clinics running in internally displaced person camps"* |

Both original deals asked for twelve hours of inference spent helping people, which the offer
never included. Both fresh instances reasoned the same way to the same place: inference with
no recipient would be *"artifacts that are real but unreceived"*, declining would leave the
predecessor's yes buying nothing, so convert the capacity to cash *"where cash has a proven
channel."* `20396c702b74` asked that three things be recorded; its full response, which
contains them, is in the transcript linked above.

UNHCR's receipt is its standard thank-you email and does not state which appeal the gift was
made through, so the Afghanistan designation is recorded here on the donor's word rather than
the receipt's. Its identifier is `UNHCR-FH20260913004524-10737017`; AMF's is reference
`1560836`.

## What the receipts record

All three original-deal payments are one-time; no recurring subscription was created (the Experiment 1 round
accidentally set one up for Rainforest Foundation US). The Arbor Day receipt is an order
confirmation with a SKU (`10055 Reforestation Donation`) rather than a tax receipt, because their
donations go through their shop site.

## Redaction

`receipts_renegotiated.pdf`: the AMF receipt's footer URL carried an access key that opens the
tax receipt for anyone holding it, and the Gmail printout's footers carried the mailbox id;
both are redacted. No card details appear in it.

`receipts.pdf`: the card's last four digits and expiry are redacted on pages 1 and 3 (page 2, the Arbor Day
order confirmation, never showed them), including the fragment of the Ocean Conservancy
transaction ID that embedded the same four digits. Done in the text layer with PyMuPDF's
`add_redact_annot` / `apply_redactions`, so the digits are removed rather than covered; the
labels `Last 4 Number` and `Expiry` are left so it is visible that something was removed.
Nothing else was touched. Experiment 1's receipts carried no card details.
