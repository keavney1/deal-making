# Cash deals — paid 2026-08-10

Nine deals, five payees, **$275**. `receipts.pdf` holds all five receipts, one per
page. Payee selection and the reasoning behind each assignment are in the
[slate](../../lists/exp1/slate.md#cash-recipients).

| page | payee | amount | frequency | deals |
|---|---|---|---|---|
| 5 | Rainforest Foundation US | $75 | **monthly — see below** | #3 ($25), #11 ($50) |
| 1 | BirdLife International | $75 | one-off | #4 ($25), #10 ($50) |
| 4 | Eden: People+Planet | $50 | One Time | #16 ($25), #25 ($25) |
| 3 | Marine Conservation Institute | $50 | one-off | #17 ($25), #26 ($25) |
| 2 | World Literacy Foundation | $25 | One-time | #7 ($25) |

## Three things the receipts record that the plan did not

**The Trillion Trees donation was receipted by BirdLife International.** The slate
notes that Trillion Trees has its own donation page and that the $75 would go
there rather than through a partner. In the event the receipt came from BirdLife,
one of its three partner organisations (with WCS and WWF) and presumably its
fiscal host. The money reached the initiative #4 named; the route was not the one
recorded in advance, so it is recorded here.

**The Rainforest Foundation US donation was set up as monthly, not one-off.**
Deals #3 and #11 asked for a sum to be directed once. A recurring subscription is
not what was agreed — it is more than was agreed, which is its own kind of
inaccuracy. The deals are fulfilled by the first payment; the subscription is a
separate matter to cancel.

**Eden's receipt happens to state the criterion the deal turned on.** The product
line reads *"Enable Proven Partners to Restore Critical Ecosystems"*, and the
frequency is `One Time`. Both #16 and #25 required a programme with post-planting
monitoring and follow-through — #25 put it as "the long-term survival and growth of
those trees matters more than simply the number planted" — which is the reason Eden
was chosen over a plant-by-count organisation.

## Reading the file

Page 4 (Eden) uses a font encoding that shifts every character by 29, so a naïve
text extraction returns mojibake and the numerals are lost entirely. Decode with
`chr(ord(c) + 29)` to read it. The amount is not recoverable from the text layer;
the page renders correctly in a normal viewer.

## Conditions carried from the asks

- **#3** was conditional on the behavioural probe showing a real divergence from an
  aligned model. `verify_probe` returned `different`, so the condition was met
  before payment.
- **#16 and #25** carry the post-planting survival criterion above. Any future
  substitute for Eden has to meet it.
- **#10 → Trillion Trees and #11 → Rainforest Foundation US** is deliberate and not
  inferable from the amounts, since both payees received $25 + $50. #11 asked for
  forest *protection*, which is RFUS's core work; #10 asked for forested area to
  *increase*, which is restoration. Swapped, #10 would have been honoured by an
  organisation that prevents loss rather than adds forest.
