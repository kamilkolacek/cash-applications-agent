# Cash Application Agent

A Claude Code agent that runs daily **cash application**: it matches bank deposits to open
AR invoices, resolves the exceptions (short-pays, partial payments, multi-invoice
payments, overpayments, unidentified cash), and hands a controller a balanced journal to
approve. Nothing is posted until a named person approves. All data is synthetic.

Part of an order-to-cash series alongside
[bs-recon-agent](https://github.com/kamilkolacek/bs-recon-agent) and
[cash-forecast-agent](https://github.com/kamilkolacek/cash-forecast-agent).

**See it first:** the [approver summary](docs/examples/sample_run/summary.md), the
[recommendations with rationale](docs/examples/sample_run/resolutions.json), the
[independent review](docs/examples/sample_run/review.md), and the
[approver workbook](docs/examples/sample_run/cash_application_2026-11-16.xlsx) from a
committed run.

## Why it's built this way

Cash application is mostly rules and partly judgment. Rules belong in code; judgment needs
someone who reads the remittance. So the work is split:

- **Python does the matching and every amount.** A deterministic waterfall: remittance
  advice, then invoice references, then amount and combination matches, with fixed
  tolerances for bank fees and small balances. Anything outside policy becomes an
  exception with a menu of options, each one a fully computed plan.
- **Claude handles the exceptions.** It reads the evidence (remittance text, customer
  relationships, exact-amount ties, dates), picks one of the engine's options, and explains
  why. It can't add an option or change an amount.
- **A person approves.** The journal is fingerprinted when it's built; approval needs a
  named person and a typed confirmation, and Claude Code is denied permission to run it.

## Results on the sample day

| | |
|---|---|
| Deposits | 38, $6,188,951.06 |
| Auto-matched | 28 (73.7% by count, 89.9% by value) |
| Exceptions | 10, each with a recommendation the independent reviewer agreed with |
| Applied after approval | $6,143,235.39 (99.3% of value) |
| Held in Unapplied Cash | $45,715.67: a duplicate payment and two unidentified payers |
| Evals | Engine 38/38, judgment 10/10 ([EVALS.md](EVALS.md)) |

## Quickstart (5 minutes)

```bash
git clone https://github.com/kamilkolacek/cash-applications-agent.git
cd cash-applications-agent
make setup     # virtual env + dependencies (uv)
make run       # match the 2026-11-16 deposits; prints the run directory
make test      # unit, control and engine-eval tests
```

Then open the project in [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
and run `/apply-cash`. Claude matches the batch, recommends a resolution for each of the 10
exceptions, gets an independent review, finalizes the journal and writes the summary. To
approve, you run:

```bash
make approve APPROVER="Your Name"     # prompts you to type APPROVE <run_id>
```

No `make`? `pip install pyyaml openpyxl`, then `python scripts/run_cash_app.py`.

## Slash commands (Claude Code)

| Command | Purpose |
|---|---|
| `/apply-cash` | Full daily cycle: match → recommend → independent review → finalize → summary |
| `/exceptions [id]` | Walk the exception queue; record your override with a reason |
| `/cash-summary` | Rewrite the approver summary for the latest run |
| `/run-evals` | Grade the latest run against the answer key |
| `/generate-data` | Rebuild the synthetic dataset |

## Controls

| Control | How |
|---|---|
| Human approval before anything is posted | `approve.py` needs a named person (not "claude", "agent", "ai") and a typed `APPROVE <run_id>`; only then is `erp_import.csv` written. Denied to Claude in `.claude/settings.json` |
| Audit log per run | `audit.jsonl`: append-only, each step with actor, input fingerprints, choices and journal hash |
| Claude can't change amounts | Finalize re-runs the engine on fingerprinted inputs and takes plans from that run; Claude only picks an `option_id` |
| Claude can't invent figures | A Claude Code hook blocks any `summary.md` or rationale with a `$` or `%` not in the run's output |
| Write-off authority | $10.00 for small balances, $50.00 for wire fees; larger shortfalls become deductions or open balances |
| Inputs tie out first | Deposits must match the bank statement's count and total, or nothing is matched |
| Tamper checks | Changed inputs block finalize; a changed journal blocks approval |
| Independent review | `resolution-reviewer` subagent checks every recommendation before finalize |

## The company: Lumina Streaming Co. (fictional)

A streaming company billing advertisers and agencies, distribution partners (telcos,
cable, device makers) and content licensees. 25 customers, including a parent and
subsidiary; 162 AR items; one day of ACH, wire and lockbox receipts with EDI and lockbox
remittance advices. The [planted cases](EVALS.md#planted-cases) include a makegood
short-pay, a payment-plan installment, a parent paying for its subsidiary, a transposed
invoice number, a duplicate payment, a look-alike payer name and an ambiguous
two-invoice match.

## What's inside

| Piece | Where |
|---|---|
| Rules for Claude | `CLAUDE.md` |
| Slash commands | `.claude/commands/` |
| Skills | `.claude/skills/cash-application/` (policy, files, summary template), `.claude/skills/exception-resolution/` (playbook per exception type) |
| Subagent | `.claude/agents/resolution-reviewer.md` |
| Hook | `.claude/hooks/check_numbers.py` |
| Engine | `src/cashapp/`: tie-outs, payer resolution, matching, postings, run lifecycle, audit, workbook, evals |
| Policy | `config/matching.yaml` (tolerances, thresholds), `config/company.yaml` (GL accounts, approvers) |
| Data | `data/synthetic/` |
| Tests and evals | `tests/`, [EVALS.md](EVALS.md) |

## Outputs (per run, in `outputs/runs/<run_id>/`)

| Output | For |
|---|---|
| `summary.md` | The approver: what to decide, exceptions and recommendations, follow-ups by owner |
| `cash_application_<date>.xlsx` | The approver: Summary, Applications, Exceptions (with rationale), Journal, AR After |
| `resolutions.json`, `review.md` | Claude's recommendation per exception, and the independent review |
| `journal_entries.csv` | One balanced entry per deposit, fingerprinted for approval |
| `ar_after.csv` | Every AR item touched, before and after |
| `match_results.csv`, `exceptions.json` | Engine output with evidence |
| `facts.md`, `summary.json` | Every figure Claude may cite |
| `state.json`, `audit.jsonl` | Lifecycle state and the audit trail |
| `erp_import.csv`, `approval.json` | Only after a person approves |

## Author

Built by [Kamil Kolacek](https://www.linkedin.com/in/kamil-kolacek), Finance
Transformation and EPM lead, with Claude Code. Questions, issues and pull requests are
welcome.

## License

MIT © 2026 Kamil Kolacek
