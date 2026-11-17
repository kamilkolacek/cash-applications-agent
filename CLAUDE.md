# Cash Application Agent: project context for Claude Code

## What this project is
Daily cash application for a fictional company, Lumina Streaming Co. (entity LuminaUS,
USD). Bank deposits for one value date are matched to open AR items (invoices and credit
memos) and every exception gets a recommended resolution. The output is a balanced journal
and an approver workbook, held for human approval. All data is synthetic.

## Division of labor
- **Python does all matching and math.** `src/cashapp/` resolves payers to customers, runs
  the matching waterfall, computes every amount, and offers a fixed menu of options for
  each exception. Each option is a complete, pre-computed plan.
- **Claude handles judgment.** It reads the evidence for each exception, chooses one of
  the engine's options, explains why in `resolutions.json`, and writes the summary for
  the approver. Claude chooses; it never creates or changes an amount.
- **A named person approves.** Nothing is posted until someone runs `scripts/approve.py`.

## Non-negotiable rules
1. Never run `scripts/approve.py` or `make approve`, and never write `approval.json`,
   `erp_import.csv`, `state.json`, `journal_entries.csv` or `audit.jsonl`. These are denied in
   `.claude/settings.json`. Approval belongs to a person.
2. Choose only `option_id`s that appear in `exceptions.json`. `finalize_run.py` re-runs
   the engine and rejects any other choice, and any rationale under 40 characters.
3. Never invent, estimate or round a figure. Every `$` and `%` in `summary.md` and in
   resolution rationales must appear in the run artifacts. A PostToolUse hook blocks the
   write if one doesn't.
4. Never write off an amount the engine did not offer to write off. Agent write-off
   authority is $10.00 (`config/matching.yaml`); larger shortfalls are deductions, partial
   payments or holds.
5. When the evidence does not support applying cash, choose `HOLD_UNAPPLIED`. Cash
   applied to the wrong customer is worse than cash left unapplied for a day.
6. Never edit `data/` or `config/`. Never read `tests/evals/answer_key.yaml`.
7. Do not proceed if `validation.json` verdict is FAIL. Report the failed checks.

## Slash commands
| Command | Purpose |
|---|---|
| `/apply-cash` | Full daily cycle: match → resolve exceptions → independent review → finalize → summary |
| `/exceptions` | Walk through the open exception queue for the latest run |
| `/cash-summary` | (Re)write the approver summary for the latest run |
| `/run-evals` | Grade the latest run against the answer key |
| `/generate-data` | Rebuild the synthetic dataset |

## Skills and subagents
- Skills (`.claude/skills/`): `cash-application` (matching policy, the run lifecycle,
  the summary template), `exception-resolution` (playbook for each exception type).
- Subagent (`.claude/agents/`): `resolution-reviewer`, an independent check of every
  recommended resolution before the run is finalized. Writes `review.md`.

## Run lifecycle (`outputs/runs/<run_id>/state.json`)
`AWAITING_RESOLUTION` → (`resolutions.json` + `finalize_run.py`) → `PENDING_APPROVAL` →
(`approve.py`, a person) → `APPROVED` or `REJECTED`. `outputs/runs/LATEST` names the newest run.

## Layout
- `config/`: company and GL accounts, matching policy and tolerances
- `data/synthetic/`: customers, AR open items, bank deposits, remittance advices, bank control totals
- `src/cashapp/`: loaders and tie-outs, payer resolution, matching, postings, run lifecycle, audit, evals
- `scripts/`: entry points (`run_cash_app.py`, `finalize_run.py`, `approve.py`, `run_evals.py`, ...)
- `docs/examples/sample_run/`: a committed run, finalized and awaiting approval
- `tests/`: unit tests, control tests, and the eval answer key

## Commands to know
- `make run`: engine run on the synthetic data
- `make test`: unit, control and engine-eval tests
- `make evals`: scorecard for the latest run
