# Resolution review: 2026-11-16_r01

Reviewer: `resolution-reviewer` subagent (independent of the recommendations). Checked each
resolution against `exceptions.json`, the customer master and AR open items.

| Exception | Chosen option | Result | Reason |
|---|---|---|---|
| EX-DEP-20261116-002 Bluewater | APPLY_PARTIAL_LEAVE_OPEN | AGREE | Remittance says installment 1 of 2; INV-24191 is open for $310,000.00, so $155,000.00 remains collectible. |
| EX-DEP-20261116-003 Pinecrest | APPLY_TO_PAYER_DOC:INV-24518 | AGREE | No relationship to Harbor Light Films in the master. INV-24518 is Pinecrest's own item for exactly $44,200.00 and the reference is a digit transposition. Approver may prefer to hold until Pinecrest confirms; the follow-up covers it. |
| EX-DEP-20261116-008 Meridian | APPLY_EXCESS:INV-24202 | AGREE | Excess of $4,750.00 equals INV-24202 exactly; same customer. |
| EX-DEP-20261116-012 Orbit | APPLY_TO_REFERENCED_DOC | AGREE | Master shows C004 as parent of C005; remittance says "on behalf of"; amount exact. |
| EX-DEP-20261116-015 NRTHSTR | APPLY_TO_CANDIDATE | AGREE | Abbreviation of Northstar Media Group; $57,420.00 equals INV-24211 only. |
| EX-DEP-20261116-016 Solstice | HOLD_UNAPPLIED | AGREE | INV-24231 paid 2026-11-06 by ACH-1106-4471. Applying to INV-24232 would mask the duplicate. |
| EX-DEP-20261116-021 Northside | HOLD_UNAPPLIED | AGREE | Different name, no amount tie to any Northstar item. On-account to Northstar would misstate their balance. |
| EX-DEP-20261116-022 J Smith | HOLD_UNAPPLIED | AGREE | Only option offered; no customer or reference. |
| EX-DEP-20261116-024 Brightline | COMBO_1 | AGREE | "OCT CAMPAIGN SVCS" matches INV-24151 and INV-24152, dated 2026-10-01 and 2026-10-08. |
| EX-DEP-20261116-032 Kestrel | APPLY_AND_RECLASS_DEDUCTION | AGREE | Stated makegood for under-delivery; $3,400.00 is above write-off authority and belongs in 120300 for Ad Sales. |

## Batch checks
- Every chosen option was offered by the engine.
- No cash from an unidentified payer is applied to a customer: J Smith and Northside are held.
- No write-off above $10.00 is among the chosen options; the only write-off in the batch is
  the engine's $8.40 small balance on INV-24171.

Verdict: ready to finalize
