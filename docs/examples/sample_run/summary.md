# Cash application: Lumina Streaming Co., 2026-11-16

**Status: pending approval. Nothing has been posted.**
Run `2026-11-16_r01` · prepared by Claude · reviewer verdict: ready to finalize

## For the approver
- **Three deposits stay in Unapplied Cash ($45,715.67):** a likely duplicate payment from
  Solstice Insurance ($23,500.00), and two payers we could not identify ($12,345.67 and $9,870.00).
- **$3,400.00 moves to Customer Deductions (120300):** Kestrel Foods took a makegood
  deduction on INV-24181. Ad Sales needs to validate it.
- **One judgment call to check:** Pinecrest Studios cited Harbor Light's INV-24581; we
  recommend applying to Pinecrest's own INV-24518 for the same $44,200.00 (transposed
  digits). Holding it until Pinecrest confirms is the conservative alternative.

## Batch
- 38 deposits totaling $6,188,951.06; tie-out to the bank statement passed.
- Auto-matched: 28 (73.7% by count, 89.9% by value).
- Exceptions: 10 ($627,325.67), all with a recommendation; the reviewer agreed with all 10.

## Exceptions and recommendations
| Deposit | Payer | Amount | Issue | Recommendation |
|---|---|---|---|---|
| DEP-20261116-002 | Bluewater Telecom | $155,000.00 | Installment 1 of 2 | Apply; leave $155,000.00 open |
| DEP-20261116-003 | Pinecrest Studios | $44,200.00 | Cited another customer's invoice | Apply to own INV-24518 |
| DEP-20261116-008 | Meridian Auto Group | $66,750.00 | Overpaid by $4,750.00 | Apply excess to INV-24202 |
| DEP-20261116-012 | Orbit Holdings | $128,640.00 | Parent paid subsidiary's invoice | Apply to INV-24221 |
| DEP-20261116-015 | NRTHSTR MEDIA GRP | $57,420.00 | Abbreviated payer name | Apply to Northstar INV-24211 |
| DEP-20261116-016 | Solstice Insurance | $23,500.00 | Invoice already paid 2026-11-06 | Hold; ask refund or credit |
| DEP-20261116-021 | NORTHSIDE MEDIA GRP | $9,870.00 | Look-alike name, no match | Hold; trace payer |
| DEP-20261116-022 | J SMITH HOLDINGS | $12,345.67 | Unidentified | Hold; trace payer |
| DEP-20261116-024 | Brightline Media | $48,000.00 | Two invoice sets match | Apply to October invoices |
| DEP-20261116-032 | Kestrel Foods | $81,600.00 | Makegood deduction | Apply; $3,400.00 to 120300 |

## After approval
- Cash applied to open items: $6,143,235.39; on account: $0.00.
- Left in Unapplied Cash: $45,715.67 (3 deposits).
- Deductions to 120300: $3,400.00; wire bank fees $25.00; small-balance write-offs $8.40.
- 35 journal entries; 49 of 50 AR items touched close in full.

## Follow-ups
| Owner | Action |
|---|---|
| Ad Sales | Validate the Kestrel October-flight makegood; credit memo or rebill |
| AR | Confirm duplicate with Solstice; refund or credit instructions |
| AR | Trace J Smith Holdings and Northside Media with the bank |
| AR | Confirm the Pinecrest application; add NRTHSTR alias for Northstar |
| Partner Finance | Record Bluewater installment 2 due date |
| Treasury | Note $23,500.00 potential refund |

To approve: `python scripts/approve.py outputs/runs/2026-11-16_r01 --approver "<your name>"`
