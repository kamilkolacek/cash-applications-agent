---
name: cash-application
description: How the cash application engine matches deposits, what each rule and file means, the run lifecycle and approval controls, and the approver summary template. Use for /apply-cash, /cash-summary, or any question about how a deposit was matched.
---

# Cash application

## What the engine does

For one bank value date, each deposit runs through a fixed waterfall. The first rule that
applies decides the outcome.

| Order | Rule | Applies when | Outcome |
|---|---|---|---|
| 1 | `REMITTANCE_ADVICE` | A lockbox or EDI remittance advice is linked by bank reference | AUTO if it lists open items, totals the deposit and pays each item in full; otherwise an exception |
| 2 | `INVOICE_REFERENCE` | The remittance text names `INV-#####` / `CM-#####` items that exist in AR | AUTO if the amount equals their open balance |
| 2a | `WIRE_BANK_FEE` | A wire is short by ≤ $50.00 | AUTO; shortfall to Bank Fees 610500 |
| 2b | `SMALL_BALANCE_WRITEOFF` | Any payment short by ≤ $10.00 | AUTO; shortfall to Small Balance Write-offs 650200 |
| 3 | `AMOUNT_MATCH` / `MULTI_INVOICE_SUM` | No usable reference; payer resolves to a customer; exactly one open item, or one set of up to 4 items, equals the deposit | AUTO |
| — | anything else | | EXCEPTION with options |

Payer names resolve by exact match on the customer name or a bank alias (score 1.00).
Otherwise the closest name scores 0.70–0.92 is a `LOW_CONFIDENCE_CUSTOMER` exception, and
below 0.70 the payer is `UNIDENTIFIED`. Any AUTO match below confidence 0.90 is demoted to
an exception.

AUTO does not mean posted. Every plan, AUTO or resolved, waits for human approval.

## Accounting

Treasury has already booked each receipt: Dr 100100 Cash / Cr 120900 Unapplied Cash.
Cash application relieves 120900 and credits AR - Trade 120100 for each item paid.
Adjustments debit 610500 (bank fees), 650200 (small balances) or 120300 (customer
deductions pending validation) and credit 120100. Cash left unapplied needs no entry; it
stays in 120900. An on-account credit moves cash from 120900 to a customer-level credit in
120100. One balanced entry per deposit (`JE-<deposit_id>`).

## Files in a run (`outputs/runs/<run_id>/`)

| File | Written by | What it holds |
|---|---|---|
| `validation.json` | engine | Tie-outs: deposits vs bank control totals, AR integrity |
| `match_results.csv` | engine | One row per deposit: rule, status, confidence, documents, evidence |
| `exceptions.json` | engine | The queue: evidence and the options for each exception |
| `facts.md`, `summary.json` | engine | Every figure you may cite |
| `resolutions.json` | Claude | Chosen option, rationale, follow-up, owner per exception |
| `review.md` | reviewer subagent | Independent check of each resolution |
| `applications.csv`, `journal_entries.csv`, `ar_after.csv` | engine (finalize) | Final plans, balanced journal, AR before/after |
| `cash_application_<date>.xlsx` | engine (finalize) | The approver workbook |
| `summary.md` | Claude | The approver summary |
| `state.json`, `audit.jsonl` | engine | Lifecycle state, input fingerprints, append-only event log |
| `approval.json`, `erp_import.csv` | a person, via `approve.py` | Only after approval |

## Controls you work inside

- `finalize_run.py` re-runs the engine on the fingerprinted inputs and takes plans from
  that fresh run, so editing `exceptions.json` cannot change an amount.
- Any `option_id` not offered, any exception left unresolved, or a rationale under 40
  characters rejects the whole file.
- The journal is fingerprinted at finalize; `approve.py` refuses if it changed.
- `approve.py` needs a named person and a typed confirmation, and Claude Code is denied
  permission to run it.

## Summary template

Use `templates/summary.md`. Keep it under 350 words. Lead with what the approver must
decide. Figures as written in `facts.md`; deposit amounts as written in `exceptions.json`.
