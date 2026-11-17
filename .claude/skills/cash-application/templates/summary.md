# Cash application: {company}, {value_date}

**Status: pending approval. Nothing has been posted.**
Run `{run_id}` · prepared by Claude · reviewer verdict: {verdict}

## For the approver
{1-3 bullets: what needs a decision or a look before approving. Lead with any hold, any
amount moved to deductions, and any recommendation the reviewer challenged.}

## Batch
- {deposit count} deposits totaling {deposit total}; tie-out to the bank statement passed.
- Auto-matched: {auto count} ({auto rate by count} by count, {auto rate by value} by value).
- Exceptions: {exception count} ({exception amount}).

## Exceptions and recommendations
| Deposit | Payer | Amount | Issue | Recommendation |
|---|---|---|---|---|
| {deposit_id} | {payer} | {amount} | {type, in plain words} | {option, in plain words} |

## After approval
- Cash applied to open items: {cash applied}; on account: {on account}.
- Left in Unapplied Cash: {left unapplied} ({n} deposits), with owners for follow-up.
- Deductions to 120300: {deductions}; bank fees {bank fees}; small-balance write-offs {small balances}.

## Follow-ups
| Owner | Action |
|---|---|
| {team} | {action} |

To approve: `python scripts/approve.py {run_dir} --approver "<your name>"`
