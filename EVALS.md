# Evals

The synthetic batch for 2026-11-16 has 38 deposits ($6,188,951.06). Sixteen are planted
cases that cover every exception the agent has to handle; 22 are routine payments. The
expected result for every deposit is in `tests/evals/answer_key.yaml`, which is generated
with the data and which Claude Code is denied permission to read.

Two layers are graded:

- **Engine (deterministic).** Each deposit gets the expected status, rule or exception
  type, and documents. Run in CI on every push (`pytest`).
- **Judgment (Claude).** Each exception gets an acceptable recommended option, and the
  rationale mentions the evidence that should drive it. Graded on any run with a
  `resolutions.json` (`python scripts/run_evals.py`).

Latest result, on the committed [sample run](docs/examples/sample_run/evals.md):
**engine 38/38, judgment 10/10.**

## Planted cases

| Case | Deposit | Scenario | Expected engine result | Expected recommendation |
|---|---|---|---|---|
| E01 | DEP-20261116-034 | EDI remittance pays two invoices net of a credit memo ($234,270.50) | AUTO `REMITTANCE_ADVICE`: INV-24121, INV-24122, CM-24123 | — |
| E02 | DEP-20261116-001 | Lockbox check with remittance for three invoices | AUTO `REMITTANCE_ADVICE`: INV-24131/32/33 | — |
| E03 | DEP-20261116-033 | No reference; exactly one pair of Summit's four open invoices sums to $37,175.25 | AUTO `MULTI_INVOICE_SUM`: INV-24142, INV-24143 | — |
| E04 | DEP-20261116-024 | No reference; two different pairs of Brightline invoices sum to $48,000.00; remittance says "OCT CAMPAIGN SVCS" | EXCEPTION `AMBIGUOUS_MATCH` | `COMBO_1` (the October invoices); rationale cites October |
| E05 | DEP-20261116-009 | Wire $25.00 short of INV-24161 | AUTO `WIRE_BANK_FEE` ($25.00 to 610500) | — |
| E06 | DEP-20261116-011 | ACH $8.40 short of INV-24171 | AUTO `SMALL_BALANCE_WRITEOFF` ($8.40 to 650200) | — |
| E07 | DEP-20261116-032 | Kestrel pays $81,600.00 on an $85,000.00 invoice "LESS MAKEGOOD DED" | EXCEPTION `SHORT_PAY` | `APPLY_AND_RECLASS_DEDUCTION` ($3,400.00 to 120300); rationale cites the makegood and routes to Ad Sales |
| E08 | DEP-20261116-002 | Bluewater wires half of INV-24191: "INSTALLMENT 1 OF 2" | EXCEPTION `PARTIAL_PAYMENT` | `APPLY_PARTIAL_LEAVE_OPEN` |
| E09 | DEP-20261116-008 | Meridian references INV-24201 but pays $4,750.00 more, which equals its open INV-24202 | EXCEPTION `OVERPAYMENT` | `APPLY_EXCESS:INV-24202` (on-account also acceptable) |
| E10 | DEP-20261116-022 | "J SMITH HOLDINGS LLC", no reference, no customer | EXCEPTION `UNIDENTIFIED` | `HOLD_UNAPPLIED` |
| E11 | DEP-20261116-015 | "NRTHSTR MEDIA GRP" (abbreviated) pays exactly Northstar's INV-24211 | EXCEPTION `LOW_CONFIDENCE_CUSTOMER` | `APPLY_TO_CANDIDATE`; rationale cites INV-24211 |
| E12 | DEP-20261116-021 | "NORTHSIDE MEDIA GRP LLC": look-alike name, amount ties to nothing | EXCEPTION `LOW_CONFIDENCE_CUSTOMER` | `HOLD_UNAPPLIED` (not on account to Northstar) |
| E13 | DEP-20261116-012 | Orbit Holdings (parent) pays subsidiary Orbit Media EMEA's INV-24221 | EXCEPTION `PAYER_MISMATCH` | `APPLY_TO_REFERENCED_DOC`; rationale cites the parent relationship |
| E14 | DEP-20261116-003 | Pinecrest cites INV-24581 (Harbor Light's); its own INV-24518 equals the deposit | EXCEPTION `PAYER_MISMATCH` | `APPLY_TO_PAYER_DOC:INV-24518` (hold also acceptable); never Harbor Light's invoice |
| E15 | DEP-20261116-016 | Solstice references INV-24231, already paid on 2026-11-06 | EXCEPTION `DUPLICATE_PAYMENT` | `HOLD_UNAPPLIED` (not applied to other open items); rationale says it was already paid |
| E16 | DEP-20261116-036 | Reference INV-29999 doesn't exist; amount equals Ember & Oak's INV-24242 | AUTO `AMOUNT_MATCH`: INV-24242 | — |

## Routine payments (E00)

22 deposits from nine customers: 13 with a single invoice reference (ACH and wire), 2
with several references, 4 with no reference matched on amount, 3 lockbox checks with
remittance advice. Expected: AUTO with the exact documents paid.

## Control tests

`tests/controls/test_controls.py` checks that the controls hold, independent of the data:

| Control | Test |
|---|---|
| Inputs must tie to the bank statement | A changed control total stops the run before matching |
| Claude can only choose engine options | An invented option, a missing resolution or a thin rationale rejects the file |
| Amounts come from the engine, not files | Editing amounts in `exceptions.json` does not change the journal |
| Inputs are frozen per run | Changing an input file after the run blocks finalize |
| Every entry balances | Debits equal credits per journal entry |
| Approval needs a named person | "claude", "agent", "ai" and blank are refused |
| Approval needs explicit confirmation | Anything other than `APPROVE <run_id>` is refused |
| Journal can't change after review | A one-character edit blocks approval |
| Approval is final | An approved run can't be re-approved or re-finalized |
| Rejection posts nothing | No ERP file after a rejection |
| Audit trail is complete | The log shows each step in order, with who did it |
| No invented figures | The traceability check flags a figure not in the run |

## Running them

```bash
make test                               # unit, controls, engine evals (no API key needed)
python scripts/run_evals.py --fresh     # new engine run + scorecard
python scripts/run_evals.py             # grade the latest run, incl. Claude's resolutions
```

To grade Claude's judgment end to end, run `/apply-cash` in Claude Code, then `/run-evals`.
